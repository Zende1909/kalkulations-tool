"""PDF-Exporte mit reportlab."""

from __future__ import annotations

import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.export_models import (
    BaugruppeExportData,
    DashboardExportData,
    ExportMoneyRow,
    ExportTable,
    SpritzgussExportData,
)


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y %H:%M")


def _money(amount: float | None) -> str:
    if amount is None:
        return "Keine Daten"
    return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _build_doc(buffer: io.BytesIO, title: str):
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title=title,
    )
    doc.compress = 0
    doc.pageCompression = 0
    return doc


def _header_block(company: str, title: str, meta: list[tuple[str, str]]) -> list:
    styles = getSampleStyleSheet()
    story: list = [
        Paragraph(f"<b>{company}</b>", styles["Normal"]),
        Spacer(1, 6),
        Paragraph(f"<b>{title}</b>", styles["Title"]),
        Spacer(1, 12),
    ]
    rows = [[k, v] for k, v in meta]
    if rows:
        table = Table(rows, colWidths=[5 * cm, 11 * cm])
        table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.extend([table, Spacer(1, 12)])
    return story


def _kv_table(title: str, rows: list[tuple[str, str]]) -> list:
    story: list = [Paragraph(f"<b>{title}</b>", getSampleStyleSheet()["Heading2"]), Spacer(1, 6)]
    if not rows:
        story.append(Paragraph("Keine Daten", getSampleStyleSheet()["Normal"]))
        return story
    table = Table(rows, colWidths=[7 * cm, 9 * cm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([table, Spacer(1, 12)])
    return story


def _money_table(title: str, rows: list[ExportMoneyRow]) -> list:
    data = [["Position", "Betrag (€)"]]
    for row in rows:
        data.append([row.label, _money(row.amount)])
    story: list = [Paragraph(f"<b>{title}</b>", getSampleStyleSheet()["Heading2"]), Spacer(1, 6)]
    table = Table(data, colWidths=[10 * cm, 6 * cm])
    style = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
        ]
    )
    for i, row in enumerate(rows, start=1):
        if row.highlight:
            style.add("FONTNAME", (0, i), (-1, i), "Helvetica-Bold")
            style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fef9c3"))
    story.extend([table, Spacer(1, 12)])
    return story


def _export_table_block(export_table: ExportTable) -> list:
    story: list = [
        Paragraph(f"<b>{export_table.title}</b>", getSampleStyleSheet()["Heading2"]),
        Spacer(1, 6),
    ]
    if not export_table.rows:
        story.append(Paragraph("Keine Daten", getSampleStyleSheet()["Normal"]))
        story.append(Spacer(1, 12))
        return story
    data = [export_table.headers, *export_table.rows]
    col_width = 16 * cm / max(len(export_table.headers), 1)
    table = Table(data, colWidths=[col_width] * len(export_table.headers), repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.extend([table, Spacer(1, 12)])
    return story


def _bar_chart_block(title: str, items: list[tuple[str, float]]) -> list:
    story: list = [Paragraph(f"<b>{title}</b>", getSampleStyleSheet()["Heading2"]), Spacer(1, 6)]
    if not items:
        story.append(Paragraph("Keine Daten", getSampleStyleSheet()["Normal"]))
        return story
    max_val = max(v for _, v in items) or 1
    for label, value in items:
        bar_width = max(0.5, 10 * cm * (value / max_val))
        inner = Table([[""]], colWidths=[bar_width], rowHeights=[8])
        inner.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#475569"))]))
        row = Table(
            [[Paragraph(label[:40], getSampleStyleSheet()["Normal"]), inner]],
            colWidths=[6 * cm, 10 * cm],
        )
        story.extend([row, Paragraph(_money(value), getSampleStyleSheet()["Normal"]), Spacer(1, 4)])
    story.append(Spacer(1, 8))
    return story


def _page_footer(canvas, doc):  # noqa: ARG001
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(1.5 * cm, 1 * cm, f"Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, f"Seite {doc.page}")
    canvas.restoreState()


def render_spritzguss_pdf(data: SpritzgussExportData) -> bytes:
    buffer = io.BytesIO()
    doc = _build_doc(buffer, "Einzelteil-Kalkulation")
    story = _header_block(
        data.company_name,
        "Einzelteil-Kalkulation",
        [
            ("Kunde", data.kunde or "–"),
            ("Projekt", data.projekt or "–"),
            ("Teilenummer", data.teilenummer),
            ("Teilebezeichnung", data.teilebezeichnung),
            ("Kalkulations-ID", str(data.calculation_id)),
            ("Erstellt", _fmt_dt(data.created_at)),
            ("Geändert", _fmt_dt(data.updated_at)),
        ],
    )
    story.extend(_kv_table("Eingabedaten", [(r.label, r.value) for r in data.inputs]))
    story.extend(_money_table("Kostenübersicht", data.kosten))
    if data.veredelung_steps:
        story.extend(_money_table("Veredelungsschritte", data.veredelung_steps))
    if data.werkzeug_hinweis:
        story.append(
            Paragraph(
                f'<font color="red"><b>{data.werkzeug_hinweis}</b></font>',
                getSampleStyleSheet()["Normal"],
            )
        )
        story.append(Spacer(1, 8))
    if data.investitionen:
        inv_rows = [
            (i.bezeichnung, i.typ, _money(i.betrag), i.hinweis) for i in data.investitionen
        ]
        story.extend(
            _kv_table(
                "Investitionen (separat)",
                [(" / ".join(r[:3]), r[3]) for r in inv_rows],
            )
        )
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def render_baugruppe_pdf(data: BaugruppeExportData) -> bytes:
    buffer = io.BytesIO()
    doc = _build_doc(buffer, "Baugruppen-Kalkulation")
    export_date = data.export_date or datetime.now()
    story = _header_block(
        data.company_name,
        "Baugruppen-Kalkulation",
        [
            ("Baugruppenname", data.name),
            ("Teilenummer", data.teilenummer or "–"),
            ("Kunde", data.kunde or "–"),
            ("Projekt", data.projekt or "–"),
            ("Status", data.status or "–"),
            ("Jahresstückzahl", str(data.jahresstueckzahl)),
            ("Baugruppen-ID", str(data.assembly_id)),
            ("Strukturversion", str(data.structure_version)),
            ("Exportdatum", _fmt_dt(export_date)),
            ("Preis pro Stück", _money(data.baugruppenpreis_je_stueck)),
            ("Skonto", _money(data.skonto) if data.skonto is not None else "–"),
            ("Erstellt", _fmt_dt(data.created_at)),
            ("Geändert", _fmt_dt(data.updated_at)),
        ],
    )
    if data.kosten_aufstellung:
        story.extend(_money_table("Kostenaufstellung", data.kosten_aufstellung))
    if data.bom is not None:
        story.extend(_export_table_block(data.bom))
    story.extend(_export_table_block(data.einzelteile))
    story.extend(_export_table_block(data.kaufteile))
    story.extend(_export_table_block(data.veredelung))
    if data.zuschlagssaetze is not None:
        story.extend(_export_table_block(data.zuschlagssaetze))
    summary = [
        ("Einzelteile gesamt", _money(data.einzelteile_gesamt)),
        ("Kaufteile gesamt", _money(data.kaufteile_gesamt)),
        ("Montage/Veredelung gesamt", _money(data.veredelung_gesamt)),
        ("VVGK", _money(data.vvgk)),
        ("Gewinn", _money(data.gewinn)),
        ("Skonto", _money(data.skonto)),
        ("Nettoverkaufspreis", _money(data.nettoverkaufspreis)),
        ("Preis pro Stück", _money(data.baugruppenpreis_je_stueck)),
        ("Jahresumsatz", _money(data.jahresumsatz)),
        ("Gesamtergebnis", _money(data.gesamtergebnis)),
    ]
    story.extend(_kv_table("Gesamtpreis und Summen", summary))
    if data.investitionen:
        story.extend(
            _kv_table(
                "Investitionen (separat, nicht im Stückpreis)",
                [(i.bezeichnung, f"{_money(i.betrag)} – {i.hinweis}") for i in data.investitionen],
            )
        )
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def render_dashboard_pdf(data: DashboardExportData) -> bytes:
    buffer = io.BytesIO()
    doc = _build_doc(buffer, "Dashboard-Bericht")
    filters = []
    if data.filter_project:
        filters.append(("Projekt", data.filter_project))
    if data.filter_customer:
        filters.append(("Kunde", data.filter_customer))
    if data.filter_status:
        filters.append(("Status", data.filter_status))
    if data.filter_date_from or data.filter_date_to:
        filters.append(("Zeitraum", f"{data.filter_date_from or '–'} bis {data.filter_date_to or '–'}"))
    if data.filter_kalkulationsart:
        filters.append(("Kalkulationsart", data.filter_kalkulationsart))
    if not filters:
        filters.append(("Filter", "Keine (Gesamtübersicht)"))
    story = _header_block(data.company_name, "Dashboard-/Projektbericht", filters)
    if data.empty_message:
        story.append(Paragraph(data.empty_message, getSampleStyleSheet()["Normal"]))
        story.append(Spacer(1, 12))
    story.extend(_kv_table("KPI-Übersicht", [(k.label, k.value) for k in data.kpis]))
    story.extend(_export_table_block(data.recent_calculations))
    story.extend(_export_table_block(data.assemblies))
    story.extend(_export_table_block(data.investments))
    if data.price_chart:
        story.extend(_bar_chart_block("Top-Endpreise", data.price_chart[:10]))
    if data.investment_chart:
        story.extend(_bar_chart_block("Investitionsvolumen je Projekt", data.investment_chart))
    if data.revenue_chart:
        story.extend(_bar_chart_block("Umsatzpotenzial je Projekt", data.revenue_chart))
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()
