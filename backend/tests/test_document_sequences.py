"""document_sequences numbering (ADR-BOS-005 / docs/ACCOUNTANT_REVIEW.md §1):

- `allocate_sequence()` is the generic atomic per-(company, kind, year)
  counter. The old SELECT-then-INSERT implementation had a documented,
  unfixed race on the *first* allocation for a given key — two concurrent
  transactions could both observe "no row yet" and both attempt the insert,
  with the loser raising an unhandled IntegrityError instead of retrying.
  The race is forced deterministically rather than hoped for via thread
  timing: session A allocates and is kept open (uncommitted), a second
  thread allocates on session B for the *same* key and is proven to
  genuinely block (thread still alive after a real wait) exactly where
  Postgres serializes the conflicting insert, then A commits and B's
  outcome is observed. This exercises the real production function end to
  end against a real Postgres (docs/12: no mocked databases).

- `next_order_number()` keeps the pre-existing year-scoped, reset-every-
  calendar-year behavior — unchanged by this slice.

- `next_invoice_number()` is new: continuous across calendar years (legally
  required, not a product choice — docs/ACCOUNTANT_REVIEW.md §1), ten
  zero-padded Arabic digits, no year prefix or dash.
"""

import os
import threading
import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("SERVICEFLOW_TEST_DATABASE_URL") is None,
    reason="SERVICEFLOW_TEST_DATABASE_URL not set",
)


def _seed_company(url: str, name: str, email: str) -> uuid.UUID:
    from business_os.identity.service import seed_company
    from business_os.shared_kernel.db import open_session

    for db in open_session(url):
        company = seed_company(db, name, "Owner", email, "парола-123")
        return company.id
    raise AssertionError("open_session yielded no session")


def _new_session(url: str) -> Session:
    """A standalone session the caller owns and closes explicitly — unlike
    open_session()'s single-iteration `for db in open_session(url):` idiom
    used elsewhere, this test needs to hold a session open *across* a
    thread-blocking window, so it replicates open_session()'s own setup
    directly rather than fighting the generator's one-shot shape."""
    from sqlalchemy.orm import sessionmaker

    from business_os.shared_kernel.db import get_engine

    return sessionmaker(bind=get_engine(url), expire_on_commit=False, class_=Session)()


# --- allocate_sequence(): generic concurrency safety ------------------------


def test_concurrent_first_allocation_never_duplicates_or_loses_a_number(
    client: TestClient,
) -> None:
    from business_os.shared_kernel.db import TenantContext
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Надпревара ЕООД", "race@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)
    kind = "race_test"
    year = datetime.now(UTC).year

    session_a = _new_session(url)
    number_a = service.allocate_sequence(session_a, ctx, kind=kind, year=year)
    # session_a is left uncommitted on purpose: its INSERT/UPSERT row is now
    # only visible to itself, exactly the state the old code's winner would
    # be in the instant before the loser's insert also arrives.

    result_b: list[int | BaseException] = []

    def allocate_b() -> None:
        session_b = _new_session(url)
        try:
            result_b.append(service.allocate_sequence(session_b, ctx, kind=kind, year=year))
            session_b.commit()
        except BaseException as exc:  # noqa: BLE001 — captured, asserted on below
            session_b.rollback()
            result_b.append(exc)
        finally:
            session_b.close()

    thread = threading.Thread(target=allocate_b)
    thread.start()

    # B must genuinely block here — it is trying to allocate the same
    # never-before-used (company, kind, year) key A is still holding open.
    # If this assertion ever fails, the rest of the test is not exercising
    # the race at all (e.g. a future change makes numbering non-blocking),
    # so it must be checked, not assumed.
    thread.join(timeout=1)
    assert thread.is_alive(), "session B did not block on the contested first allocation"

    session_a.commit()
    thread.join(timeout=10)
    assert not thread.is_alive(), "session B never unblocked after A committed"

    assert len(result_b) == 1
    result = result_b[0]
    # This is the assertion the documented race breaks: the old code's loser
    # raised IntegrityError here instead of allocating 2.
    assert not isinstance(result, BaseException), (
        f"concurrent first allocation raised instead of retrying: {result!r}"
    )
    assert {number_a, result} == {1, 2}

    from serviceflow.service_orders.models import DocumentSequence

    verify_session = _new_session(url)
    try:
        rows = verify_session.scalars(
            select(DocumentSequence).where(
                DocumentSequence.company_id == company_id,
                DocumentSequence.kind == kind,
            )
        ).all()
        assert len(rows) == 1, "concurrent first allocation created a duplicate sequence row"
        assert rows[0].current == 2, "concurrent first allocation lost an increment"
    finally:
        verify_session.close()

    session_a.close()


def test_concurrent_subsequent_allocation_never_duplicates_or_loses_a_number(
    client: TestClient,
) -> None:
    """The historical race was specific to the *first* allocation of a key
    (SELECT-then-INSERT never had a row to lock). This proves the same
    atomic-upsert guarantee also holds once a row already exists — i.e. for
    every allocation after the first, not just the documented bug case."""
    from business_os.shared_kernel.db import TenantContext
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Втора Надпревара ЕООД", "race2@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)
    kind = "race_test_subsequent"
    year = datetime.now(UTC).year

    seed_session = _new_session(url)
    try:
        first = service.allocate_sequence(seed_session, ctx, kind=kind, year=year)
        seed_session.commit()
    finally:
        seed_session.close()
    assert first == 1

    session_a = _new_session(url)
    number_a = service.allocate_sequence(session_a, ctx, kind=kind, year=year)

    result_b: list[int | BaseException] = []

    def allocate_b() -> None:
        session_b = _new_session(url)
        try:
            result_b.append(service.allocate_sequence(session_b, ctx, kind=kind, year=year))
            session_b.commit()
        except BaseException as exc:  # noqa: BLE001 — captured, asserted on below
            session_b.rollback()
            result_b.append(exc)
        finally:
            session_b.close()

    thread = threading.Thread(target=allocate_b)
    thread.start()
    thread.join(timeout=1)
    assert thread.is_alive(), "session B did not block on the contested subsequent allocation"

    session_a.commit()
    thread.join(timeout=10)
    assert not thread.is_alive(), "session B never unblocked after A committed"

    assert len(result_b) == 1
    result = result_b[0]
    assert not isinstance(result, BaseException), (
        f"concurrent subsequent allocation raised: {result!r}"
    )
    assert {number_a, result} == {2, 3}

    from serviceflow.service_orders.models import DocumentSequence

    verify_session = _new_session(url)
    try:
        rows = verify_session.scalars(
            select(DocumentSequence).where(
                DocumentSequence.company_id == company_id,
                DocumentSequence.kind == kind,
            )
        ).all()
        assert len(rows) == 1, "concurrent subsequent allocation created a duplicate sequence row"
        assert rows[0].current == 3, "concurrent subsequent allocation lost an increment"
    finally:
        verify_session.close()

    session_a.close()


def test_concurrent_first_allocation_keeps_companies_isolated(client: TestClient) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_a = _seed_company(url, "Фирма А", "a-race@race.bg")
    company_b = _seed_company(url, "Фирма Б", "b-race@race.bg")
    kind = "race_test_isolation"
    year = datetime.now(UTC).year

    barrier = threading.Barrier(2)
    results: list[int | BaseException] = [BaseException(), BaseException()]

    def run(index: int, company_id: uuid.UUID) -> None:
        ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)
        try:
            for db in open_session(url):
                barrier.wait(timeout=10)
                results[index] = service.allocate_sequence(db, ctx, kind=kind, year=year)
                db.commit()
        except BaseException as exc:  # noqa: BLE001 — captured, asserted on below
            results[index] = exc

    threads = [
        threading.Thread(target=run, args=(i, cid))
        for i, cid in enumerate([company_a, company_b])
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    for i, result in enumerate(results):
        assert not isinstance(result, BaseException), (
            f"thread {i} raised instead of allocating a number: {result!r}"
        )

    # Two different tenants racing the same kind/year at the same instant
    # must not share a sequence row or influence each other's numbering —
    # each is a fresh first allocation and should independently start at 1.
    assert results == [1, 1]


# --- next_order_number(): unchanged behavior ---------------------------


def test_order_numbering_still_resets_every_calendar_year(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Сервиз Поръчки ЕООД", "orders@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)

    for db in open_session(url):
        monkeypatch.setattr(service, "_now", lambda: datetime(2025, 12, 31, tzinfo=UTC))
        first = service.next_order_number(db, ctx)
        db.commit()

        monkeypatch.setattr(service, "_now", lambda: datetime(2026, 1, 1, tzinfo=UTC))
        second = service.next_order_number(db, ctx)
        db.commit()

    assert first == "2025-00001"
    assert second == "2026-00001"  # resets: a real, unchanged behavior for orders


# --- next_invoice_number(): the new, continuous sequence -----------------


def test_first_invoice_number_is_zero_padded_ten_digits(client: TestClient) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Фактурна ЕООД", "invoices@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)

    for db in open_session(url):
        number = service.next_invoice_number(db, ctx)
        db.commit()

    assert number == "0000000001"
    assert len(number) == 10
    assert number.isdigit()


def test_second_invoice_number_increments(client: TestClient) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Фактурна Втора ЕООД", "invoices2@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)

    for db in open_session(url):
        first = service.next_invoice_number(db, ctx)
        second = service.next_invoice_number(db, ctx)
        db.commit()

    assert first == "0000000001"
    assert second == "0000000002"


def test_invoice_numbering_does_not_reset_across_a_simulated_year_boundary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The core legal requirement (docs/ACCOUNTANT_REVIEW.md §1): unlike
    order numbers, invoice numbers must never reset on 1 January.
    `next_invoice_number()` never calls `_now()` at all — that omission is
    exactly the mechanism this test proves matters: the clock is advanced
    across two real year boundaries between allocations (the same
    simulated-time technique the sibling order-numbering test uses, where
    it *does* change the outcome) and invoice numbers keep incrementing
    regardless, because nothing about them is calendar-derived."""
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Фактура През Годините ЕООД", "invoices3@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)

    for db in open_session(url):
        monkeypatch.setattr(service, "_now", lambda: datetime(2025, 12, 31, tzinfo=UTC))
        first = service.next_invoice_number(db, ctx)
        db.commit()

        monkeypatch.setattr(service, "_now", lambda: datetime(2026, 1, 1, tzinfo=UTC))
        second = service.next_invoice_number(db, ctx)
        db.commit()

        monkeypatch.setattr(service, "_now", lambda: datetime(2027, 6, 15, tzinfo=UTC))
        third = service.next_invoice_number(db, ctx)
        db.commit()

    # Continuous across two simulated year boundaries — never "0000000001" again.
    assert [first, second, third] == ["0000000001", "0000000002", "0000000003"]


def test_invoice_numbering_isolated_per_company(client: TestClient) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_a = _seed_company(url, "Фактура Фирма А", "inv-a@race.bg")
    company_b = _seed_company(url, "Фактура Фирма Б", "inv-b@race.bg")

    for db in open_session(url):
        ctx_a = TenantContext(company_id=company_a, user_id=uuid.uuid4(), is_owner=True)
        a1 = service.next_invoice_number(db, ctx_a)
        a2 = service.next_invoice_number(db, ctx_a)
        db.commit()

        ctx_b = TenantContext(company_id=company_b, user_id=uuid.uuid4(), is_owner=True)
        b1 = service.next_invoice_number(db, ctx_b)
        db.commit()

    assert [a1, a2] == ["0000000001", "0000000002"]
    assert b1 == "0000000001"  # company B's own series, unaffected by A's count


def test_concurrent_invoice_allocation_is_safe_and_produces_no_duplicate(
    client: TestClient,
) -> None:
    """Exercises the real, production next_invoice_number() (not the generic
    allocate_sequence()) under the same deterministic blocking technique as
    the generic concurrency tests above, proving the invoice-specific
    wrapper inherits the atomic guarantee rather than reintroducing a race
    via its own formatting layer."""
    from business_os.shared_kernel.db import TenantContext
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Фактура Едновременно ЕООД", "inv-race@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)

    session_a = _new_session(url)
    number_a = service.next_invoice_number(session_a, ctx)

    result_b: list[str | BaseException] = []

    def allocate_b() -> None:
        session_b = _new_session(url)
        try:
            result_b.append(service.next_invoice_number(session_b, ctx))
            session_b.commit()
        except BaseException as exc:  # noqa: BLE001 — captured, asserted on below
            session_b.rollback()
            result_b.append(exc)
        finally:
            session_b.close()

    thread = threading.Thread(target=allocate_b)
    thread.start()
    thread.join(timeout=1)
    assert thread.is_alive(), "concurrent invoice allocation did not block as expected"

    session_a.commit()
    thread.join(timeout=10)
    assert not thread.is_alive()

    assert len(result_b) == 1
    result = result_b[0]
    assert not isinstance(result, BaseException), (
        f"concurrent invoice allocation raised: {result!r}"
    )
    # No duplicate: two distinct, sequential, zero-padded 10-digit numbers.
    assert {number_a, result} == {"0000000001", "0000000002"}

    session_a.close()
