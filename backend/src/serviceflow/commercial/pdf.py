"""Issued Invoice PDF (docs/ACCOUNTANT_REVIEW.md §11: server-generated,
no signature/stamp required — LAW-CONFIRMED not required, same basis the
intake protocol already relies on). Non-VAT-registered seller only; buyer
may be an individual or a domestic company, VAT-registered or not
(docs/ACCOUNTANT_REVIEW.md 'RepairFlow Invoice V1 Freeze' §5 / §4 B1) — the
caller (commercial/service.py's `get_issued`) is responsible for confirming
`status == "issued"` before this module is ever reached; nothing here
re-derives or trusts anything else about invoice state.

Generated on demand from the frozen `Invoice`/`InvoiceLine` snapshot on
every request — no `pdf_storage_key` write, no mutation, no commit. The
output is fully deterministic since none of its inputs can change once
issued (BR-4): re-requesting the same invoice's PDF always produces the
same bytes.

`to_pdf_data()` reads ONLY `Invoice.seller`/`.buyer` (the frozen JSONB
snapshot) — never live `Company`/`Customer` rows. That snapshot's entire
purpose is that a PDF printed months later still shows the seller/buyer
identity exactly as it was at Issue time, even if Company/Customer records
have since changed; reaching into current master data here would silently
defeat that.

DejaVu Sans is bundled here (assets/) for Cyrillic glyph coverage, the same
choice service_orders/protocol.py already made — duplicated rather than
imported: `service_orders.protocol` sits behind the
`service-orders-public-boundary` import-linter contract, off-limits to
`commercial`.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fpdf import FPDF
from fpdf.fonts import FontFace

from serviceflow.commercial.models import Invoice, InvoiceLine

_ASSETS = Path(__file__).parent / "assets"
_FONT_REGULAR = _ASSETS / "DejaVuSans.ttf"
_FONT_BOLD = _ASSETS / "DejaVuSans-Bold.ttf"

# ISO 4217 code -> display symbol. Phase A only ever produces "EUR"
# (commercial/service.py's `issue()` asserts it), but the renderer still
# follows the invoice's own persisted value rather than hardcoding "€" —
# an unrecognized code falls back to printing the code itself, never a
# fabricated symbol.
_CURRENCY_SYMBOLS = {"EUR": "€"}


@dataclass(frozen=True)
class InvoicePdfLine:
    description: str
    qty: int
    unit_price: Decimal


@dataclass(frozen=True)
class InvoicePdfData:
    """Immutable rendering input — every field already resolved from the
    frozen Invoice row, nothing left for the renderer to look up or
    recompute. `number` is already the final zero-padded 10-digit string
    (the one canonical padding convention this codebase uses everywhere
    else, e.g. `next_invoice_number()`/the frontend's own display) — the
    renderer never parses or re-pads it."""

    number: str
    issued_at: datetime
    tax_event_date: date
    seller_name: str
    seller_address: str
    seller_eik: str
    buyer_name: str
    buyer_address: str | None
    buyer_eik: str | None
    buyer_vat_number: str | None
    currency: str
    net: Decimal
    vat: Decimal
    gross: Decimal
    lines: list[InvoicePdfLine]


def to_pdf_data(invoice: Invoice, lines: list[InvoiceLine]) -> InvoicePdfData:
    """Maps an already-issued Invoice + its lines to the PDF DTO. Asserts
    (never silently coerces) that every Issue-owned field is actually
    populated — every one of them is guaranteed non-NULL once
    `status == "issued"` (commercial/service.py's `issue()` writes all of
    them atomically in the same transaction), so a violation here would
    mean the caller skipped the `get_issued()` status check, not a real
    data gap."""
    assert invoice.status == "issued"
    assert invoice.number is not None
    assert invoice.issued_at is not None
    assert invoice.tax_event_date is not None
    assert invoice.seller is not None
    assert invoice.buyer is not None
    assert invoice.net is not None
    assert invoice.vat is not None
    assert invoice.gross is not None

    return InvoicePdfData(
        number=f"{invoice.number:010d}",
        issued_at=invoice.issued_at,
        tax_event_date=invoice.tax_event_date,
        seller_name=str(invoice.seller.get("name", "")),
        seller_address=str(invoice.seller.get("address", "")),
        seller_eik=str(invoice.seller.get("eik", "")),
        buyer_name=str(invoice.buyer.get("name", "")),
        buyer_address=invoice.buyer.get("address"),
        buyer_eik=invoice.buyer.get("eik"),
        buyer_vat_number=invoice.buyer.get("vat_number"),
        currency=invoice.currency,
        net=invoice.net,
        vat=invoice.vat,
        gross=invoice.gross,
        lines=[
            InvoicePdfLine(description=line.description, qty=line.qty, unit_price=line.unit_price)
            for line in lines
        ],
    )


def _money(amount: Decimal, currency: str) -> str:
    symbol = _CURRENCY_SYMBOLS.get(currency, currency)
    return f"{amount:.2f} {symbol}"


def _pdf_with_fonts() -> FPDF:
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    return pdf


def generate_invoice_pdf(data: InvoicePdfData) -> bytes:
    pdf = _pdf_with_fonts()

    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 10, "ФАКТУРА", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 7, f"№ {data.number}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"Дата на издаване: {data.issued_at.strftime('%d.%m.%Y %H:%M')}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Дата на данъчно събитие: {data.tax_event_date.strftime('%d.%m.%Y')}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def _section(title: str) -> None:
        pdf.set_font("DejaVu", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 10)

    _section("ДОСТАВЧИК")
    pdf.cell(0, 6, data.seller_name, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Адрес: {data.seller_address}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"ЕИК: {data.seller_eik}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("ПОЛУЧАТЕЛ")
    pdf.cell(0, 6, data.buyer_name, new_x="LMARGIN", new_y="NEXT")
    if data.buyer_address is not None:
        pdf.cell(0, 6, f"Адрес: {data.buyer_address}", new_x="LMARGIN", new_y="NEXT")
    if data.buyer_eik is not None:
        pdf.cell(0, 6, f"ЕИК: {data.buyer_eik}", new_x="LMARGIN", new_y="NEXT")
    if data.buyer_vat_number is not None:
        pdf.cell(0, 6, f"ДДС №: {data.buyer_vat_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # fpdf2's table() context manager handles pagination-safe row wrapping
    # (a long description wraps within its cell and the row grows to fit)
    # and repeats the header row across a page break automatically — a
    # hand-rolled cell-by-cell table would have to reimplement both.
    pdf.set_font("DejaVu", "", 9)
    with pdf.table(
        col_widths=(10, 85, 25, 30, 30),
        text_align=("CENTER", "LEFT", "CENTER", "RIGHT", "RIGHT"),
        line_height=6,
    ) as table:
        header = table.row()
        for label in ("№", "Описание", "Количество", "Ед. цена", "Стойност"):
            header.cell(label, style=FontFace(emphasis="BOLD"))
        for i, line in enumerate(data.lines, start=1):
            row = table.row()
            row.cell(str(i))
            row.cell(line.description)
            row.cell(str(line.qty))
            row.cell(_money(line.unit_price, data.currency))
            row.cell(_money(line.qty * line.unit_price, data.currency))

    pdf.ln(4)

    def _totals_line(label: str, value: str, *, bold: bool = False) -> None:
        pdf.set_font("DejaVu", "B" if bold else "", 10)
        pdf.set_x(pdf.w - pdf.r_margin - 100)
        pdf.cell(65, 7, label, align="R")
        pdf.cell(35, 7, value, align="R", new_x="LMARGIN", new_y="NEXT")

    # "ДДС: не се начислява" is the exact courtesy wording already frozen
    # in docs/ACCOUNTANT_REVIEW.md §6 (T3/V4) for a non-VAT-registered
    # seller — not a statutory legal-basis citation (§6 explicitly says
    # none is required under the 2026 SME regime), and not "VAT 0%" (a
    # 0%-rated supply is a legally different, unrelated case, deferred
    # from V1 entirely).
    _totals_line("Данъчна основа:", _money(data.net, data.currency))
    _totals_line("ДДС: не се начислява", _money(data.vat, data.currency))
    _totals_line("Общо:", _money(data.gross, data.currency), bold=True)

    out = pdf.output()
    return bytes(out)
