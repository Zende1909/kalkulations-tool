"""Excel/PDF-Export für Business-Case-Übersicht (Management-/Finance-Bericht)."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.config import settings
from app.services.branding import resolve_logo_path
from app.services.business_case_overview import build_project_business_case
from app.services.i18n_export import Locale, normalize_locale, t_business_case

EUR_FORMAT = '#,##0.00 "€"'
EUR_WHOLE = '#,##0 "€"'
PCT_FORMAT = '0.00"%"'
INT_FORMAT = "#,##0"

BOLD = Font(bold=True, color="0F172A", name="Calibri", size=11)
TITLE_FONT = Font(bold=True, color="0F172A", name="Calibri", size=18)
SECTION_FONT = Font(bold=True, color="0e7490", name="Calibri", size=12)
TILE_LABEL_FONT = Font(bold=True, color="64748B", name="Calibri", size=9)
TILE_VALUE_FONT = Font(bold=True, color="0F172A", name="Calibri", size=14)
HINT_FONT = Font(color="64748B", name="Calibri", size=8)
WHITE_BOLD = Font(bold=True, color="FFFFFF", name="Calibri", size=11)

HEADER_FILL = PatternFill("solid", fgColor="0e7490")
STRIP_FILL = PatternFill("solid", fgColor="F0FDFA")
CARD_FILL = PatternFill("solid", fgColor="FFFFFF")
SECTION_FILL = PatternFill("solid", fgColor="CFFAFE")
POSITIVE_FILL = PatternFill("solid", fgColor="DCFCE7")
NEGATIVE_FILL = PatternFill("solid", fgColor="FEE2E2")
ACCENT_FILL = PatternFill("solid", fgColor="ECFCCB")

THIN = Border(
    left=Side(style="thin", color="CBD5E1"),
    right=Side(style="thin", color="CBD5E1"),
    top=Side(style="thin", color="CBD5E1"),
    bottom=Side(style="thin", color="CBD5E1"),
)


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
    investment_financial_summary: dict = field(default_factory=dict)
    revenue_by_year: list[dict] = field(default_factory=list)
    kpi_summary: dict = field(default_factory=dict)
    position_headers: list[str] = field(default_factory=list)
    position_rows: list[list] = field(default_factory=list)
    investment_headers: list[str] = field(default_factory=list)
    investment_rows: list[list] = field(default_factory=list)


def _revenue_export(value: float | None) -> int | None:
    if value is None:
        return None
    return int(round(value))


def _money(value: float | None) -> float | str | None:
    return value


def _pct(value: float | None) -> float | str | None:
    return value


def _position_row(item: dict, typ: str, label_key: str) -> list:
    return [
        typ,
        item.get("material_number") or item.get("teilenummer"),
        item.get(label_key),
        _money(item.get("cost_per_piece")),
        _money(item.get("bottom_price_per_piece")),
        _money(item.get("actual_price_per_piece")),
        _money(item.get("guide_price_per_piece")),
        item.get("project_volume"),
        _revenue_export(item.get("bottom_price_revenue")),
        _revenue_export(item.get("actual_revenue")),
        _money(item.get("cost_total")),
        _money(item.get("margin_bottom_price_total")),
        _pct(item.get("margin_bottom_price_total_pct")),
        _money(item.get("margin_actual_total")),
        _pct(item.get("margin_actual_total_pct")),
        _pct(item.get("margin_bottom_price_pct")),
        _pct(item.get("margin_actual_price_pct")),
    ]


def display_revenue_for_year(row: dict[str, Any]) -> float | None:
    """Wie Frontend: tatsächlicher Umsatz, sonst Bottom Price."""
    actual = row.get("actual_revenue")
    bottom = row.get("bottom_price_revenue")
    if actual is not None and isinstance(actual, (int, float)):
        return float(actual)
    if bottom is not None and isinstance(bottom, (int, float)):
        return float(bottom)
    return None


def sum_display_revenue(revenue_by_year: list[dict]) -> float | None:
    values = [v for v in (display_revenue_for_year(r) for r in revenue_by_year) if v is not None]
    if not values:
        return None
    return float(sum(values))


def revenue_period_label(revenue_by_year: list[dict]) -> str | None:
    years = [int(r["calendar_year"]) for r in revenue_by_year if r.get("calendar_year") is not None]
    if not years:
        return None
    lo, hi = min(years), max(years)
    return str(lo) if lo == hi else f"{lo}–{hi}"


def format_revenue_compact(value: float | None, locale: Locale = "de") -> str:
    """Kompakte Umsatzdarstellung (DE: Mio./k€, EN: m/k EUR)."""
    if value is None:
        return "–"
    loc = normalize_locale(locale)
    abs_v = abs(value)
    if loc == "en":
        if abs_v >= 1_000_000:
            return f"{value / 1_000_000:.2f}m EUR"
        if abs_v >= 10_000:
            return f"{value / 1_000:.1f}k EUR"
        return f"{int(round(value)):,} EUR"
    if abs_v >= 1_000_000:
        num = f"{value / 1_000_000:.2f}".replace(".", ",")
        return f"{num} Mio. €"
    if abs_v >= 10_000:
        num = f"{value / 1_000:.1f}".replace(".", ",")
        return f"{num} k€"
    return f"{int(round(value)):,} €".replace(",", ".")


def format_integer_de(value: float | int | None, locale: Locale = "de") -> str:
    if value is None:
        return "–"
    if normalize_locale(locale) == "en":
        return f"{int(round(float(value))):,}"
    return f"{int(round(float(value))):,}".replace(",", ".")


def build_business_case_export(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    linked_project_id: int,
    locale: Locale | str | None = "de",
) -> BusinessCaseExportData:
    loc = normalize_locale(locale)
    bc = t_business_case(loc)
    data = build_project_business_case(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    position_headers = list(bc["position_headers"])
    position_rows: list[list] = []
    for part in data["parts"]:
        position_rows.append(_position_row(part, bc["type_part"], "bezeichnung"))
    for asm in data["assemblies"]:
        position_rows.append(_position_row(asm, bc["type_assembly"], "name"))

    investment_headers = list(bc["investment_headers"])
    investment_rows = [
        [
            inv.get("payment_type"),
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
            _pct(inv.get("margin_revenue_minus_cost_pct")),
            inv.get("margin_revenue_minus_bottom_price"),
            _pct(inv.get("margin_revenue_minus_bottom_price_pct")),
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
        investment_financial_summary=data.get("investment_financial_summary") or {},
        revenue_by_year=list(data.get("revenue_by_year") or []),
        kpi_summary=dict(data.get("kpi_summary") or {}),
        position_headers=position_headers,
        position_rows=position_rows,
        investment_headers=investment_headers,
        investment_rows=investment_rows,
    )


def _tone_fill(value: float | None) -> PatternFill:
    if value is None:
        return CARD_FILL
    if value > 0:
        return POSITIVE_FILL
    if value < 0:
        return NEGATIVE_FILL
    return CARD_FILL


def _write_tile(
    ws,
    *,
    row: int,
    col: int,
    label: str,
    value,
    hint: str | None = None,
    number_format: str | None = None,
    fill: PatternFill | None = None,
) -> None:
    label_cell = ws.cell(row=row, column=col, value=label)
    label_cell.font = TILE_LABEL_FONT
    label_cell.fill = fill or STRIP_FILL
    label_cell.border = THIN
    label_cell.alignment = Alignment(wrap_text=True, vertical="center")

    value_cell = ws.cell(row=row + 1, column=col, value=value if value is not None else "–")
    value_cell.font = TILE_VALUE_FONT
    value_cell.fill = fill or STRIP_FILL
    value_cell.border = THIN
    value_cell.alignment = Alignment(vertical="center")
    if number_format and isinstance(value, (int, float)):
        value_cell.number_format = number_format

    hint_cell = ws.cell(row=row + 2, column=col, value=hint or "")
    hint_cell.font = HINT_FONT
    hint_cell.fill = fill or STRIP_FILL
    hint_cell.border = THIN
    hint_cell.alignment = Alignment(wrap_text=True, vertical="top")


def render_business_case_excel(
    data: BusinessCaseExportData,
    locale: Locale | str | None = "de",
) -> bytes:
    """Dashboard-first Excel: gleiche KPI-Kacheln wie die Business-Case-Seite."""
    loc = normalize_locale(locale)
    bc = t_business_case(loc)
    wb = Workbook()
    ws = wb.active
    ws.title = bc["sheet_dashboard"]

    # Header band
    ws.merge_cells("A1:F1")
    ws["A1"] = f"{data.company_name} – Business Case"
    ws["A1"].font = Font(bold=True, color="FFFFFF", name="Calibri", size=18)
    ws["A1"].fill = HEADER_FILL
    ws["A1"].alignment = Alignment(vertical="center")
    for col in range(1, 9):
        ws.cell(row=1, column=col).fill = HEADER_FILL
        ws.cell(row=2, column=col).fill = HEADER_FILL
    ws.row_dimensions[1].height = 48

    ws.merge_cells("A2:H2")
    ws["A2"] = (
        f"{bc['report_subtitle']}  ·  {data.customer} / {data.program} / {data.project}  ·  "
        f"{bc['generated_at']} {data.generated_at.strftime('%d.%m.%Y %H:%M')} UTC"
    )
    ws["A2"].font = Font(color="CFFAFE", name="Calibri", size=10)
    ws["A2"].fill = HEADER_FILL

    logo_path = resolve_logo_path()
    if logo_path is not None:
        try:
            img = XLImage(str(logo_path))
            img.width = 100
            img.height = 50
            ws.add_image(img, "G1")
            ws.column_dimensions["G"].width = 12
            ws.column_dimensions["H"].width = 12
        except Exception:  # noqa: BLE001
            pass

    total_display = sum_display_revenue(data.revenue_by_year)
    period = revenue_period_label(data.revenue_by_year)

    # KPI-Strip (wie BusinessCaseKpiStrip)
    ws.merge_cells("A4:H4")
    ws["A4"] = bc["section_kpi_dashboard"]
    ws["A4"].font = SECTION_FONT
    ws["A4"].fill = SECTION_FILL

    strip = [
        (bc["kpi_total_revenue"], total_display, EUR_WHOLE, bc["hint_total_revenue"], STRIP_FILL),
        (
            bc["kpi_ebit"],
            data.kpis.get("ebit_actual_total_pct"),
            PCT_FORMAT,
            bc["hint_ebit"],
            _tone_fill(data.kpis.get("ebit_actual_total_pct")),
        ),
        (
            bc["kpi_roi"],
            data.kpis.get("roi_incl_capex_actual_pct"),
            PCT_FORMAT,
            bc["hint_roi"],
            _tone_fill(data.kpis.get("roi_incl_capex_actual_pct")),
        ),
        (bc["kpi_period"], period or "–", None, bc["hint_period"], STRIP_FILL),
    ]
    for idx, (label, value, fmt, hint, fill) in enumerate(strip):
        col = 1 + idx * 2
        ws.merge_cells(start_row=5, start_column=col, end_row=5, end_column=col + 1)
        ws.merge_cells(start_row=6, start_column=col, end_row=6, end_column=col + 1)
        ws.merge_cells(start_row=7, start_column=col, end_row=7, end_column=col + 1)
        _write_tile(ws, row=5, col=col, label=label, value=value, hint=hint, number_format=fmt, fill=fill)

    # Profitabilitäts-Snapshot (Gauges als große %-Kacheln)
    ws.merge_cells("A9:H9")
    ws["A9"] = bc["section_profitability"]
    ws["A9"].font = SECTION_FONT
    ws["A9"].fill = SECTION_FILL

    gauges = [
        (bc["gauge_ebit"], data.kpis.get("ebit_actual_total_pct"), bc["hint_gauge_ebit"]),
        (bc["gauge_ebit_bottom"], data.kpis.get("ebit_bottom_total_pct"), bc["hint_gauge_ebit_bottom"]),
        (bc["gauge_roi_capex"], data.kpis.get("roi_incl_capex_actual_pct"), bc["hint_gauge_roi"]),
    ]
    for idx, (label, value, hint) in enumerate(gauges):
        col = 1 + idx * 2
        ws.merge_cells(start_row=10, start_column=col, end_row=10, end_column=col + 1)
        ws.merge_cells(start_row=11, start_column=col, end_row=11, end_column=col + 1)
        ws.merge_cells(start_row=12, start_column=col, end_row=12, end_column=col + 1)
        _write_tile(
            ws,
            row=10,
            col=col,
            label=label,
            value=value,
            hint=hint,
            number_format=PCT_FORMAT,
            fill=_tone_fill(value if isinstance(value, (int, float)) else None),
        )

    # Operative Wirtschaftlichkeit
    ws.merge_cells("A14:H14")
    ws["A14"] = bc["section_operating"]
    ws["A14"].font = SECTION_FONT
    ws["A14"].fill = SECTION_FILL

    operative = [
        (bc["kpi_bottom_revenue"], data.kpis.get("bottom_price_revenue_total"), EUR_WHOLE, bc["hint_bottom_revenue"]),
        (bc["kpi_actual_revenue"], data.kpis.get("actual_revenue_total"), EUR_WHOLE, bc["hint_actual_revenue"]),
        (bc["kpi_operating_cost"], data.kpis.get("operative_cost_total"), EUR_FORMAT, bc["hint_operating_cost_excel"]),
        (bc["kpi_ebit_bottom"], data.kpis.get("ebit_bottom_total"), EUR_FORMAT, bc["hint_ebit_no_capex"]),
        (bc["kpi_ebit_actual"], data.kpis.get("ebit_actual_total"), EUR_FORMAT, bc["hint_ebit_no_capex"]),
        (
            bc["kpi_project_volume"],
            data.kpis.get("project_volume_total"),
            INT_FORMAT,
            bc["hint_parts_assemblies_short"].format(
                n_et=data.kpis.get("anzahl_einzelteile") or 0,
                n_bg=data.kpis.get("anzahl_baugruppen") or 0,
            ),
        ),
    ]
    for idx, (label, value, fmt, hint) in enumerate(operative):
        r = 15 if idx < 3 else 18
        c = 1 + (idx % 3) * 2
        ws.merge_cells(start_row=r, start_column=c, end_row=r, end_column=c + 1)
        ws.merge_cells(start_row=r + 1, start_column=c, end_row=r + 1, end_column=c + 1)
        ws.merge_cells(start_row=r + 2, start_column=c, end_row=r + 2, end_column=c + 1)
        fill = (
            _tone_fill(value if isinstance(value, (int, float)) and "EBIT" in label else None)
            if "EBIT" in label
            else STRIP_FILL
        )
        _write_tile(ws, row=r, col=c, label=label, value=value, hint=hint, number_format=fmt, fill=fill)

    # Kapitalbindung
    ws.merge_cells("A21:H21")
    ws["A21"] = bc["section_capital"]
    ws["A21"].font = SECTION_FONT
    ws["A21"].fill = SECTION_FILL

    capital = [
        (bc["kpi_capex_total"], data.kpis.get("capex_cost_total"), EUR_FORMAT, bc["hint_capex"]),
        (
            bc["kpi_other_investment"],
            data.kpis.get("non_capex_investment_cost_total"),
            EUR_FORMAT,
            bc["hint_other_investment_excel"],
        ),
        (bc["kpi_bound_capital"], data.kpis.get("bound_capital_total"), EUR_FORMAT, bc["hint_bound_capital"]),
        (bc["kpi_roi_bottom_capex"], data.kpis.get("roi_incl_capex_bottom_pct"), PCT_FORMAT, None),
        (bc["kpi_roi_actual_capex"], data.kpis.get("roi_incl_capex_actual_pct"), PCT_FORMAT, None),
        (
            bc["kpi_roi_operating"],
            data.kpis.get("roi_operating_bottom_pct"),
            PCT_FORMAT,
            bc["hint_actual_roi"].format(value=data.kpis.get("roi_operating_actual_pct")),
        ),
    ]
    for idx, (label, value, fmt, hint) in enumerate(capital):
        r = 22 if idx < 3 else 25
        c = 1 + (idx % 3) * 2
        ws.merge_cells(start_row=r, start_column=c, end_row=r, end_column=c + 1)
        ws.merge_cells(start_row=r + 1, start_column=c, end_row=r + 1, end_column=c + 1)
        ws.merge_cells(start_row=r + 2, start_column=c, end_row=r + 2, end_column=c + 1)
        fill = _tone_fill(value if isinstance(value, (int, float)) and "ROI" in label else None) if "ROI" in label else STRIP_FILL
        _write_tile(ws, row=r, col=c, label=label, value=value, hint=hint, number_format=fmt, fill=fill)

    for col in range(1, 9):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.row_dimensions[6].height = 22
    ws.row_dimensions[11].height = 22

    # Umsatzentwicklung sheet
    ws_rev = wb.create_sheet(bc["sheet_revenue"])
    ws_rev["A1"] = bc["section_revenue_by_year"]
    ws_rev["A1"].font = SECTION_FONT
    headers = list(bc["revenue_headers"])
    for col, h in enumerate(headers, 1):
        cell = ws_rev.cell(row=3, column=col, value=h)
        cell.font = WHITE_BOLD
        cell.fill = HEADER_FILL
    for i, year_row in enumerate(sorted(data.revenue_by_year, key=lambda r: r.get("calendar_year") or 0), start=4):
        disp = display_revenue_for_year(year_row)
        ws_rev.cell(row=i, column=1, value=year_row.get("calendar_year"))
        vol = ws_rev.cell(row=i, column=2, value=year_row.get("project_volume"))
        vol.number_format = INT_FORMAT
        for col, key in ((3, "bottom_price_revenue"), (4, "actual_revenue")):
            cell = ws_rev.cell(row=i, column=col, value=_revenue_export(year_row.get(key)))
            cell.number_format = EUR_WHOLE
        disp_cell = ws_rev.cell(row=i, column=5, value=_revenue_export(disp))
        disp_cell.number_format = EUR_WHOLE
    for col in range(1, 6):
        ws_rev.column_dimensions[get_column_letter(col)].width = 22

    # Szenario sheet
    ws_sc = wb.create_sheet(bc["sheet_scenario"])
    ws_sc["A1"] = bc["scenario_title"]
    ws_sc["A1"].font = SECTION_FONT
    for col, h in enumerate(bc["scenario_headers"], 1):
        cell = ws_sc.cell(row=3, column=col, value=h)
        cell.font = WHITE_BOLD
        cell.fill = HEADER_FILL
    operating = (data.kpi_summary or {}).get("operating") or {}
    capital_sum = (data.kpi_summary or {}).get("capital") or {}
    scenario_rows = [
        (bc["scenario_revenue"], operating.get("bottom_price_revenue_total"), operating.get("actual_revenue_total"), EUR_WHOLE),
        (bc["scenario_operating_cost"], operating.get("cost_total"), operating.get("cost_total"), EUR_FORMAT),
        (bc["scenario_ebit"], operating.get("ebit_bottom"), operating.get("ebit_actual"), EUR_FORMAT),
        (bc["scenario_ebit_pct"], operating.get("ebit_bottom_pct"), operating.get("ebit_actual_pct"), PCT_FORMAT),
        (
            bc["scenario_roi_capex"],
            capital_sum.get("roi_incl_capex_bottom_pct"),
            capital_sum.get("roi_incl_capex_actual_pct"),
            PCT_FORMAT,
        ),
        (
            bc["scenario_roi_operating"],
            operating.get("roi_operating_bottom_pct"),
            operating.get("roi_operating_actual_pct"),
            PCT_FORMAT,
        ),
    ]
    for i, (label, bottom, actual, fmt) in enumerate(scenario_rows, start=4):
        ws_sc.cell(row=i, column=1, value=label).font = BOLD
        b = ws_sc.cell(row=i, column=2, value=bottom if bottom is not None else "–")
        a = ws_sc.cell(row=i, column=3, value=actual if actual is not None else "–")
        if isinstance(bottom, (int, float)):
            b.number_format = fmt
        if isinstance(actual, (int, float)):
            a.number_format = fmt
    for col in range(1, 4):
        ws_sc.column_dimensions[get_column_letter(col)].width = 28

    # Detail sheets (finance appendices)
    ws_pos = wb.create_sheet(bc["sheet_positions"])
    position_pct_cols = {13, 15, 16, 17}
    position_revenue_cols = {9, 10}
    for col, header in enumerate(data.position_headers, 1):
        cell = ws_pos.cell(row=1, column=col, value=header)
        cell.font = WHITE_BOLD
        cell.fill = HEADER_FILL
    for i, prow in enumerate(data.position_rows, start=2):
        for col, val in enumerate(prow, 1):
            cell = ws_pos.cell(row=i, column=col, value=val)
            if isinstance(val, float):
                cell.number_format = PCT_FORMAT if col in position_pct_cols else EUR_FORMAT
            elif col in position_revenue_cols and isinstance(val, int):
                cell.number_format = EUR_WHOLE
            elif col == 8 and isinstance(val, (int, float)):
                cell.number_format = INT_FORMAT

    ws_inv = wb.create_sheet(bc["sheet_investments"])
    inv_pct_cols = {12, 14}
    for col, header in enumerate(data.investment_headers, 1):
        cell = ws_inv.cell(row=1, column=col, value=header)
        cell.font = WHITE_BOLD
        cell.fill = HEADER_FILL
    for i, irow in enumerate(data.investment_rows, start=2):
        for col, val in enumerate(irow, 1):
            cell = ws_inv.cell(row=i, column=col, value=val)
            if isinstance(val, float):
                cell.number_format = PCT_FORMAT if col in inv_pct_cols else EUR_FORMAT
    summary_row = len(data.investment_rows) + 3
    ws_inv.cell(row=summary_row, column=1, value=bc["totals"]).font = BOLD
    fin = data.investment_financial_summary or {}
    summary_labels = [
        (bc["summary_capex"], fin.get("capex", {})),
        (bc["summary_development"], fin.get("entwicklung", {})),
        (bc["summary_legacy"], fin.get("legacy", {})),
        (bc["summary_total"], fin.get("totals", {})),
    ]
    for offset, (label, block) in enumerate(summary_labels, start=1):
        row_idx = summary_row + offset
        ws_inv.cell(row=row_idx, column=1, value=label)
        ws_inv.cell(row=row_idx, column=2, value=(block or {}).get("count"))
        cost_cell = ws_inv.cell(row=row_idx, column=8, value=(block or {}).get("cost_amount_total"))
        cost_cell.number_format = EUR_FORMAT

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
