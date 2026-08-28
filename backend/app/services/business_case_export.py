"""Excel/PDF-Export für Business-Case-Übersicht."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy.orm import Session

from app.config import settings
from app.services.business_case_overview import build_project_business_case

EUR_FORMAT = '#,##0.00 "€"'
BOLD = Font(bold=True)


@dataclass
class BusinessCaseExportData:
    company_name: str
    customer: str
    program: str
    project: str
    generated_at: datetime
    kpis: dict
    parts: list[dict]
    assemblies: list[dict]
    investments: list[dict]
    position_headers: list[str] = field(default_factory=list)
    position_rows: list[list] = field(default_factory=list)
    investment_headers: list[str] = field(default_factory=list)
    investment_rows: list[list] = field(default_factory=list)


def _money(value: float | None) -> str | float | None:
    return value


def build_business_case_export(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    linked_project_id: int,
) -> BusinessCaseExportData:
    data = build_project_business_case(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    position_headers = [
        "Typ",
        "Materialnummer",
        "Bezeichnung",
        "Kosten/Stück",
        "Bottom Price/Stück",
        "Tatsächlicher Preis/Stück",
        "Richtpreis (15 %)",
        "Projektstückzahl",
        "Bottom-Price-Umsatz",
        "Tatsächlicher Umsatz",
        "Kosten gesamt",
        "Bottom-Marge gesamt",
        "Tatsächliche Marge gesamt",
    ]
    position_rows: list[list] = []
    for part in data["parts"]:
        position_rows.append(
            [
                "Einzelteil",
                part.get("material_number") or part.get("teilenummer"),
                part.get("bezeichnung"),
                _money(part.get("cost_per_piece")),
                _money(part.get("bottom_price_per_piece")),
                _money(part.get("actual_price_per_piece")),
                _money(part.get("guide_price_per_piece")),
                part.get("project_volume"),
                _money(part.get("bottom_price_revenue")),
                _money(part.get("actual_revenue")),
                _money(part.get("cost_total")),
                _money(part.get("margin_bottom_price_total")),
                _money(part.get("margin_actual_total")),
            ]
        )
    for asm in data["assemblies"]:
        position_rows.append(
            [
                "Baugruppe",
                asm.get("material_number") or asm.get("teilenummer"),
                asm.get("name"),
                _money(asm.get("cost_per_piece")),
                _money(asm.get("bottom_price_per_piece")),
                _money(asm.get("actual_price_per_piece")),
                _money(asm.get("guide_price_per_piece")),
                asm.get("project_volume"),
                _money(asm.get("bottom_price_revenue")),
                _money(asm.get("actual_revenue")),
                _money(asm.get("cost_total")),
                _money(asm.get("margin_bottom_price_total")),
                _money(asm.get("margin_actual_total")),
            ]
        )

    investment_headers = [
        "Bezeichnung",
        "Zuordnungstyp",
        "Materialnummer",
        "Kunde",
        "Programm",
        "Projekt",
        "Kosten einmalig",
        "Bottom Price einmalig",
        "Erlös einmalig",
        "Erlös − Kosten",
        "Erlös − Bottom Price",
        "Bottom Price − Kosten",
    ]
    investment_rows = [
        [
            inv.get("bezeichnung"),
            inv.get("assignment_type_label") or inv.get("assignment_type"),
            inv.get("material_number") or "",
            inv.get("customer_name"),
            inv.get("program_name"),
            inv.get("project_name"),
            inv.get("cost_amount"),
            inv.get("bottom_price"),
            inv.get("revenue_amount"),
            inv.get("margin_revenue_minus_cost"),
            inv.get("margin_revenue_minus_bottom_price"),
            inv.get("margin_bottom_price_minus_cost"),
        ]
        for inv in data["investments"]
    ]

    return BusinessCaseExportData(
        company_name=settings.COMPANY_NAME,
        customer=data["customer"],
        program=data.get("program", ""),
        project=data["project"],
        generated_at=datetime.now(timezone.utc),
        kpis=data["kpis"],
        parts=data["parts"],
        assemblies=data["assemblies"],
        investments=data["investments"],
        position_headers=position_headers,
        position_rows=position_rows,
        investment_headers=investment_headers,
        investment_rows=investment_rows,
    )


def render_business_case_excel(data: BusinessCaseExportData) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Business Case"
    ws["A1"] = f"{data.company_name} – Business Case"
    ws["A1"].font = BOLD
    ws["A2"] = f"{data.customer} / {data.program} / {data.project}"
    row = 4
    kpi_labels = [
        ("Gesamtkosten", data.kpis.get("cost_total")),
        ("Bottom-Price-Umsatz", data.kpis.get("bottom_price_revenue_total")),
        ("Tatsächlicher Umsatz", data.kpis.get("actual_revenue_total")),
        ("Bottom-Price-Marge", data.kpis.get("margin_bottom_price_total")),
        ("Tatsächliche Marge", data.kpis.get("margin_actual_total")),
        ("Projektstückzahl", data.kpis.get("project_volume_total")),
        ("Einzelteile", data.kpis.get("anzahl_einzelteile")),
        ("Baugruppen", data.kpis.get("anzahl_baugruppen")),
    ]
    for label, val in kpi_labels:
        ws.cell(row=row, column=1, value=label).font = BOLD
        cell = ws.cell(row=row, column=2, value=val)
        if isinstance(val, float):
            cell.number_format = EUR_FORMAT
        row += 1
    row += 1
    ws_pos = wb.create_sheet("Materialpositionen")
    for col, header in enumerate(data.position_headers, 1):
        ws_pos.cell(row=1, column=col, value=header).font = BOLD
    for i, prow in enumerate(data.position_rows, start=2):
        for col, val in enumerate(prow, 1):
            cell = ws_pos.cell(row=i, column=col, value=val)
            if isinstance(val, float):
                cell.number_format = EUR_FORMAT
    ws_inv = wb.create_sheet("Investitionen")
    for col, header in enumerate(data.investment_headers, 1):
        ws_inv.cell(row=1, column=col, value=header).font = BOLD
    for i, irow in enumerate(data.investment_rows, start=2):
        for col, val in enumerate(irow, 1):
            cell = ws_inv.cell(row=i, column=col, value=val)
            if isinstance(val, float):
                cell.number_format = EUR_FORMAT
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
