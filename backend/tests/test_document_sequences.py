"""document_sequences / next_number() concurrency (ADR-BOS-005): the old
SELECT-then-INSERT implementation had a documented, unfixed race on the
*first* allocation for a given (company_id, kind, year) — two concurrent
transactions could both observe "no row yet" and both attempt the insert,
with the loser raising an unhandled IntegrityError instead of retrying.

The race is forced deterministically rather than hoped for via thread
timing: session A calls next_number() and is kept open (uncommitted), a
second thread calls next_number() on session B for the *same* key and is
proven to genuinely block (thread still alive after a real wait) exactly
where Postgres serializes the conflicting insert, then A commits and B's
outcome is observed. This exercises the real production function end to
end against a real Postgres (docs/12: no mocked databases), not a
hand-rolled reproduction of the old code shape."""

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


def test_concurrent_first_allocation_never_duplicates_or_loses_a_number(
    client: TestClient,
) -> None:
    from business_os.shared_kernel.db import TenantContext
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_id = _seed_company(url, "Надпревара ЕООД", "race@race.bg")
    ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)
    kind = "race_test"

    session_a = _new_session(url)
    number_a = service.next_number(session_a, ctx, kind=kind)
    # session_a is left uncommitted on purpose: its INSERT/UPSERT row is now
    # only visible to itself, exactly the state the old code's winner would
    # be in the instant before the loser's insert also arrives.

    result_b: list[str | BaseException] = []

    def allocate_b() -> None:
        session_b = _new_session(url)
        try:
            result_b.append(service.next_number(session_b, ctx, kind=kind))
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
    # raised IntegrityError here instead of allocating "…-00002".
    assert not isinstance(result, BaseException), (
        f"concurrent first allocation raised instead of retrying: {result!r}"
    )

    year = datetime.now(UTC).year
    assert {number_a, result} == {f"{year}-00001", f"{year}-00002"}

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


def test_concurrent_first_allocation_keeps_companies_isolated(client: TestClient) -> None:
    from business_os.shared_kernel.db import TenantContext, open_session
    from serviceflow.service_orders import service

    url = os.environ["SERVICEFLOW_DATABASE_URL"]
    company_a = _seed_company(url, "Фирма А", "a-race@race.bg")
    company_b = _seed_company(url, "Фирма Б", "b-race@race.bg")
    kind = "race_test_isolation"

    barrier = threading.Barrier(2)
    results: list[str | BaseException] = [BaseException(), BaseException()]

    def run(index: int, company_id: uuid.UUID) -> None:
        ctx = TenantContext(company_id=company_id, user_id=uuid.uuid4(), is_owner=True)
        try:
            for db in open_session(url):
                barrier.wait(timeout=10)
                results[index] = service.next_number(db, ctx, kind=kind)
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

    year = datetime.now(UTC).year
    # Two different tenants racing the same kind/year at the same instant
    # must not share a sequence row or influence each other's numbering —
    # each is a fresh first allocation and should independently start at 1.
    assert results == [f"{year}-00001", f"{year}-00001"]
