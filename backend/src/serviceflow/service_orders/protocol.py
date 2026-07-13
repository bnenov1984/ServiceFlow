"""Приемо-предавателен протокол (intake variant) — docs/02 §13, docs/13 Етап-2 scope.

MINIMAL per the PO's Етап-2 narrowing: shop header, order №, date, customer,
asset, complaint, accessories, signature lines. No estimate range, no terms
text, no delivery variant — those are Етап-4 "разширени протоколи".

DejaVu Sans is bundled (assets/) for Cyrillic glyph coverage — the standard PDF
core fonts (Helvetica/Times/Courier) are Latin-only. Public-domain/permissive
license, see assets/DejaVuSans-LICENSE.txt.
"""

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fpdf import FPDF

_ASSETS = Path(__file__).parent / "assets"
_FONT_REGULAR = _ASSETS / "DejaVuSans.ttf"
_FONT_BOLD = _ASSETS / "DejaVuSans-Bold.ttf"


@dataclass(frozen=True)
class ProtocolData:
    company_name: str
    order_number: str
    created_on: date
    customer_name: str
    customer_phone: str
    asset_type_name: str
    asset_label: str
    asset_identifiers: list[tuple[str, str]]  # [(label, value), ...]
    complaint: str
    accessories: list[str] = field(default_factory=list)
    company_address: str = ""
    company_phone: str = ""


def _pdf_with_fonts() -> FPDF:
    pdf = FPDF(format="A4", unit="mm")
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    return pdf


def generate_intake_protocol(data: ProtocolData) -> bytes:
    pdf = _pdf_with_fonts()

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, data.company_name, new_x="LMARGIN", new_y="NEXT")
    if data.company_address or data.company_phone:
        pdf.set_font("DejaVu", "", 10)
        contact = " · ".join(p for p in (data.company_address, data.company_phone) if p)
        pdf.cell(0, 6, contact, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "Приемо-предавателен протокол", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 7, f"Поръчка № {data.order_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Дата: {data.created_on.strftime('%d.%m.%Y')}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    def _section(title: str) -> None:
        pdf.set_font("DejaVu", "B", 12)
        pdf.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 11)

    _section("Клиент")
    pdf.cell(0, 6, data.customer_name, new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, data.customer_phone, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("Актив")
    pdf.cell(0, 6, f"{data.asset_type_name}: {data.asset_label}", new_x="LMARGIN", new_y="NEXT")
    for label, value in data.asset_identifiers:
        pdf.cell(0, 6, f"{label}: {value}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("Оплакване")
    pdf.multi_cell(0, 6, data.complaint)
    pdf.ln(3)

    _section("Аксесоари")
    if data.accessories:
        for item in data.accessories:
            pdf.cell(0, 6, f"- {item}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, "(няма)", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(20)
    pdf.set_font("DejaVu", "", 11)
    line_y = pdf.get_y()
    pdf.line(20, line_y, 90, line_y)
    pdf.line(120, line_y, 190, line_y)
    pdf.set_xy(20, line_y + 2)
    pdf.cell(70, 6, "Клиент", align="C")
    pdf.set_xy(120, line_y + 2)
    pdf.cell(70, 6, "Приел", align="C")

    out = pdf.output()
    return bytes(out)
