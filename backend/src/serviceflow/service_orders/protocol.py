"""Приемо-предавателен протокол — two variants (docs/02 §13):

- Intake (`generate_intake_protocol`, docs/13 Етап-2 scope): shop header,
  order №, date, customer, asset, complaint, accessories, signature lines.
  Reads live order/customer/asset data — always current, since intake happens
  once and is never reprinted against changed history.
- Delivery (`generate_delivery_protocol`, Wave 4 Issue 7): reads ONLY a
  frozen `ServiceOrder.completion_snapshot` (never live Customer/Company/
  Asset/line rows) via `build_delivery_protocol_data` — the router is
  responsible for confirming a snapshot exists before calling this. No
  estimate range/terms text/e-signatures — those stay out of V1.

DejaVu Sans is bundled (assets/) for Cyrillic glyph coverage — the standard PDF
core fonts (Helvetica/Times/Courier) are Latin-only. Public-domain/permissive
license, see assets/DejaVuSans-LICENSE.txt.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

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


def _qty_label(qty: Decimal) -> str:
    """A whole qty prints without decimals ("2"); a fractional one (hourly
    labor, 1.5 ч.) keeps up to 2 (order-workflow-revamp WP-I, ADR-BOS-013 §8)."""
    return str(qty.to_integral_value()) if qty == qty.to_integral_value() else f"{qty:.2f}"


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


# --- Delivery protocol (Wave 4 Issue 7) -------------------------------------

@dataclass(frozen=True)
class DeliveryLaborLine:
    description: str
    # str, not int (order-workflow-revamp WP-I): the frozen snapshot stores
    # qty as a string (`Decimal` isn't JSON-serializable) — a snapshot built
    # before this change still has a plain int here, and `Decimal(...)`
    # accepts either at render time, so no migration of old snapshots is
    # needed (same "never rewrite a frozen snapshot" discipline as the rest
    # of this module).
    qty: str
    unit_price: str


@dataclass(frozen=True)
class DeliveryPartLine:
    name: str
    qty: int
    unit_price: str
    warranty_days: int | None


@dataclass(frozen=True)
class DeliveryAccessory:
    name: str
    qty: int
    returned: bool


@dataclass(frozen=True)
class DeliveryProtocolData:
    """Rendering input for the delivery variant — every field already
    resolved from the frozen snapshot, nothing left for the renderer to look
    up or recompute (same discipline commercial/pdf.py's InvoicePdfData
    follows for issued invoices)."""

    company_name: str
    company_address: str
    company_phone: str
    order_number: str
    delivered_on: datetime
    customer_name: str
    customer_phone: str
    asset_type_name: str
    asset_label: str
    asset_identifiers: list[tuple[str, str]]
    mileage: int | None
    complaint: str
    diagnosis_observed: str
    diagnosis_cause: str
    diagnosis_recommendation: str
    labor_lines: list[DeliveryLaborLine]
    part_lines: list[DeliveryPartLine]
    accessories: list[DeliveryAccessory]
    total: str
    technician_name: str | None
    labor_warranty_days: int | None
    # Issue 04: company-level warranty terms, frozen into the snapshot at
    # completion time. Absent on any snapshot built before this field
    # existed (`build_delivery_protocol_data` defaults those to "") — same
    # posture `completion_snapshot`'s own migration took toward pre-existing
    # orders: no retroactive reconstruction.
    warranty_standard_term: str
    warranty_conditions: str
    warranty_text: str
    warranty_additional_conditions: str


def build_delivery_protocol_data(snapshot: dict[str, Any]) -> DeliveryProtocolData:
    """Maps `ServiceOrder.completion_snapshot` (the dict
    `service_orders.service._build_completion_snapshot` wrote at delivery
    time) to the PDF DTO. The caller (the router) is responsible for
    confirming the snapshot exists at all — this assumes every key it wrote
    is present, since both functions are the only two places that shape
    ever passes through."""
    order = snapshot["order"]
    customer = snapshot["customer"]
    company = snapshot["company"]
    asset = snapshot["asset"]
    diagnosis = snapshot.get("diagnosis")

    return DeliveryProtocolData(
        company_name=company["name"], company_address=company["address"],
        company_phone=company["phone"],
        order_number=order["number"],
        delivered_on=datetime.fromisoformat(order["completed_at"]),
        customer_name=customer["name"], customer_phone=customer["phone"],
        asset_type_name=asset["type_name"], asset_label=asset["label"],
        asset_identifiers=[(label, value) for label, value in asset["identifiers"]],
        mileage=order["mileage"], complaint=order["complaint"],
        diagnosis_observed=diagnosis["observed"] if diagnosis else "",
        diagnosis_cause=diagnosis["cause"] if diagnosis else "",
        diagnosis_recommendation=diagnosis["recommendation"] if diagnosis else "",
        labor_lines=[
            DeliveryLaborLine(description=line["description"], qty=line["qty"],
                              unit_price=line["unit_price"])
            for line in snapshot["labor_lines"]
        ],
        part_lines=[
            DeliveryPartLine(name=p["name"], qty=p["qty"], unit_price=p["unit_price"],
                             warranty_days=p["warranty_days"])
            for p in snapshot["part_lines"]
        ],
        accessories=[
            DeliveryAccessory(name=a["name"], qty=a["qty"], returned=a["returned"])
            for a in snapshot["accessories"]
        ],
        total=snapshot["total"], technician_name=snapshot["technician_name"],
        labor_warranty_days=order["warranty_days"],
        warranty_standard_term=company.get("warranty_standard_term") or "",
        warranty_conditions=company.get("warranty_conditions") or "",
        warranty_text=company.get("warranty_text") or "",
        warranty_additional_conditions=company.get("warranty_additional_conditions") or "",
    )


def _warranty_text(days: int | None) -> str:
    """Labor (order-level) warranty only — stays day-granularity end to end
    (issue 05 only changed PART warranty's unit, not labor's). NULL -> "Не е
    посочена" (unspecified), 0 -> "Без гаранция" (explicitly none),
    positive -> plain day count."""
    if days is None:
        return "Не е посочена"
    if days == 0:
        return "Без гаранция"
    return f"{days} дни"


def _warranty_text_months(days: int | None) -> str:
    """Part-line warranty only (issue 05, audit correction: months-
    granularity at the UI/API boundary; `days` here is still the frozen
    snapshot's day count — same `PartLine.warranty_days` storage as always,
    converted only for display, same 30-days/month rule as the router's
    `_days_to_months`). NULL -> "Не е посочена", 0 -> "Без гаранция",
    positive -> "N месец"/"N месеца" (correct singular for exactly 1)."""
    if days is None:
        return "Не е посочена"
    if days == 0:
        return "Без гаранция"
    months = round(days / 30)
    if months == 0:
        # A positive day count that rounds down to 0 months (e.g. 10 days,
        # entered directly via a pre-issue-05 completion_snapshot or a
        # non-router write) — render the day count rather than falsely
        # claiming "Без гаранция", which 0 has its own distinct meaning for.
        return f"{days} дни"
    return f"{months} месец" if months == 1 else f"{months} месеца"


def generate_delivery_protocol(
    data: DeliveryProtocolData, *, include_warranty: bool = True,
) -> bytes:
    """`include_warranty=False` (issue 03: the plain "Изпрати протокол"
    email action) omits the labor/part warranty lines entirely — everything
    else is identical. The print button and the "+ гаранция" email action
    both use the default `True`, matching this function's original,
    unconditional behavior."""
    pdf = _pdf_with_fonts()

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, data.company_name, new_x="LMARGIN", new_y="NEXT")
    if data.company_address or data.company_phone:
        pdf.set_font("DejaVu", "", 10)
        contact = " · ".join(p for p in (data.company_address, data.company_phone) if p)
        pdf.cell(0, 6, contact, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, "Протокол за предаване", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 11)
    pdf.cell(0, 7, f"Поръчка № {data.order_number}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Дата на предаване: {data.delivered_on.strftime('%d.%m.%Y')}",
            new_x="LMARGIN", new_y="NEXT")
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
    if data.mileage is not None:
        pdf.cell(0, 6, f"Пробег: {data.mileage} км", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("Оплакване")
    pdf.multi_cell(0, 6, data.complaint)
    pdf.ln(3)

    if data.diagnosis_observed or data.diagnosis_cause or data.diagnosis_recommendation:
        _section("Диагноза")
        if data.diagnosis_observed:
            pdf.multi_cell(0, 6, f"Констатирано: {data.diagnosis_observed}")
        if data.diagnosis_cause:
            pdf.multi_cell(0, 6, f"Причина: {data.diagnosis_cause}")
        if data.diagnosis_recommendation:
            pdf.multi_cell(0, 6, f"Извършена работа: {data.diagnosis_recommendation}")
        pdf.ln(3)

    _section("Труд")
    if data.labor_lines:
        for line in data.labor_lines:
            line_qty = Decimal(line.qty)
            qty = f" x{_qty_label(line_qty)}" if line_qty > 1 else ""
            pdf.cell(0, 6, f"- {line.description}{qty} — {line.unit_price} €",
                     new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, "(няма)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 11)
    pdf.ln(2)
    if include_warranty:
        pdf.cell(0, 6, f"Гаранция за труд: {_warranty_text(data.labor_warranty_days)}",
                new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("Части")
    if data.part_lines:
        for p in data.part_lines:
            qty = f" x{p.qty}" if p.qty > 1 else ""
            warranty_suffix = (
                f" (гаранция: {_warranty_text_months(p.warranty_days)})" if include_warranty else ""
            )
            pdf.cell(0, 6,
                    f"- {p.name}{qty} — {p.unit_price} €{warranty_suffix}",
                    new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, "(няма)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 11)
    pdf.ln(3)

    if include_warranty and (
        data.warranty_standard_term or data.warranty_conditions
        or data.warranty_text or data.warranty_additional_conditions
    ):
        _section("Гаранционни условия")
        if data.warranty_standard_term:
            pdf.multi_cell(0, 6, f"Стандартен гаранционен срок: {data.warranty_standard_term}")
        if data.warranty_conditions:
            pdf.multi_cell(0, 6, data.warranty_conditions)
        if data.warranty_text:
            pdf.multi_cell(0, 6, data.warranty_text)
        if data.warranty_additional_conditions:
            pdf.multi_cell(0, 6, data.warranty_additional_conditions)
        pdf.ln(3)

    _section("Обща сума")
    pdf.cell(0, 6, f"{data.total} €", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    _section("Аксесоари")
    if data.accessories:
        for a in data.accessories:
            qty = f" x{a.qty}" if a.qty > 1 else ""
            returned = "върнат" if a.returned else "невърнат"
            pdf.cell(0, 6, f"- {a.name}{qty} ({returned})", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_font("DejaVu", "", 10)
        pdf.cell(0, 6, "(няма)", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("DejaVu", "", 11)
    pdf.ln(3)

    if data.technician_name:
        _section("Извършил ремонта")
        pdf.cell(0, 6, data.technician_name, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(3)

    pdf.ln(15)
    pdf.set_font("DejaVu", "", 11)
    line_y = pdf.get_y()
    pdf.line(20, line_y, 90, line_y)
    pdf.line(120, line_y, 190, line_y)
    pdf.set_xy(20, line_y + 2)
    pdf.cell(70, 6, "Клиент", align="C")
    pdf.set_xy(120, line_y + 2)
    pdf.cell(70, 6, "Предал", align="C")

    out = pdf.output()
    return bytes(out)
