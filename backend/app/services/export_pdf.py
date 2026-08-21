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
    from app.services.baugruppe_export_detail import BaugruppeDetailKalkulation

    buffer = io.BytesIO()
    doc = _build_doc(buffer, "Baugruppen-Detailkalkulation")
    export_date = data.export_date or datetime.now()
    # 1. Zusammenfassung
    story = _header_block(
        data.company_name,
        "Baugruppen-Detailkalkulation",
        [
            ("Baugruppenname", data.name),
            ("Teilenummer", data.teilenummer or "–"),
            ("Kunde", data.kunde or "–"),
            ("Programm", data.program or "–"),
            ("Projekt", data.projekt or "–"),
            ("Status", data.status or "–"),
            ("Jahresstückzahl", str(data.jahresstueckzahl)),
            ("Baugruppen-ID", str(data.assembly_id)),
            ("Strukturversion", str(data.structure_version)),
            ("Exportdatum", _fmt_dt(export_date)),
            ("Herstellkosten", _money(data.herstellkosten)),
            ("SG&A / VVGK", _money(data.vvgk)),
            ("Selbstkosten", _money(data.selbstkosten)),
            ("Profit / Gewinn", _money(data.gewinn)),
            ("Skonto", _money(data.skonto) if data.skonto is not None else "–"),
            ("Nettoverkaufspreis", _money(data.nettoverkaufspreis)),
            ("Endpreis je Stück", _money(data.baugruppenpreis_je_stueck)),
            ("Jahresumsatz", _money(data.jahresumsatz)),
            ("Erstellt", _fmt_dt(data.created_at)),
            ("Geändert", _fmt_dt(data.updated_at)),
        ],
    )
    if data.kosten_aufstellung:
        story.extend(_money_table("Kostenaufstellung", data.kosten_aufstellung))

    detail = data.detail if isinstance(data.detail, BaugruppeDetailKalkulation) else None

    # 2. zentrale Zuschlagssätze
    if detail and detail.assumptions:
        story.extend(
            _kv_table(
                "Zentrale Zuschlagssätze",
                [
                    (
                        a.bezeichnung,
                        (
                            f"{a.satz_prozent:.2f} %".replace(".", ",")
                            if a.satz_prozent is not None
                            else "–"
                        )
                        + f" – Basis: {a.kostenbasis}"
                        + (f" – {_money(a.betrag)}" if a.betrag is not None else "")
                        + (f" ({a.hinweis})" if a.hinweis else ""),
                    )
                    for a in detail.assumptions
                ],
            )
        )
    elif data.zuschlagssaetze is not None:
        story.extend(_export_table_block(data.zuschlagssaetze))

    # 3. BOM
    if data.bom is not None:
        story.extend(_export_table_block(data.bom))

    # 4 + 5. vollständige Kalkulation und Prozesskette je PART
    if detail:
        for part in detail.parts:
            story.extend(
                _kv_table(
                    f"PART-Detail: {part.bezeichnung}",
                    [
                        ("Teilenummer", part.teilenummer or "–"),
                        ("Menge", str(part.menge)),
                        ("Kostenbasis", part.price_basis),
                        ("Material", part.material_name or "–"),
                        (
                            "Materialpreis",
                            _money(part.materialpreis_pro_kg) + " / kg"
                            if part.materialpreis_pro_kg is not None
                            else "–",
                        ),
                        (
                            "Netto-Teilegewicht",
                            f"{part.teilegewicht_netto_g:.2f} g"
                            if part.teilegewicht_netto_g is not None
                            else "–",
                        ),
                        (
                            "Schussgewicht",
                            f"{part.schussgewicht_g:.2f} g"
                            if part.schussgewicht_g is not None
                            else "–",
                        ),
                        ("Materialkosten direkt", _money(part.materialkosten)),
                        (
                            "Material-Ausschuss",
                            f"{part.material_ausschussquote_pct:.2f} %".replace(".", ",")
                            if part.material_ausschussquote_pct is not None
                            else "–",
                        ),
                        ("Material inkl. Ausschuss", _money(part.materialkosten_inkl_ausschuss)),
                        ("Nominierung", part.material_nominierung or "fehlend"),
                        (
                            "MGK-Satz",
                            f"{part.mgk_pct:.2f} %".replace(".", ",")
                            if part.mgk_pct is not None
                            else "–",
                        ),
                        ("Material-MGK", _money(part.material_mgk)),
                        ("Maschinenkosten", _money(part.maschinenkosten)),
                        ("Fertigungslohn", _money(part.fertigungslohn)),
                        ("Spritzguss-Ausgang", _money(part.spritzguss_ausgang)),
                        ("Veredelung direkt vor Ausschuss", _money(part.veredelung_direkt_vor)),
                        ("FGK-Basis", _money(part.fgk_basis)),
                        (
                            "FGK-Satz",
                            f"{part.fgk_pct:.2f} %".replace(".", ",")
                            if part.fgk_pct is not None
                            else "–",
                        ),
                        ("FGK", _money(part.fgk_betrag)),
                        ("Herstellkosten", _money(part.herstellkosten)),
                        ("Zwischensumme", _money(part.zwischensumme)),
                    ],
                )
            )
            chain_rows = [
                ExportMoneyRow(
                    "Spritzguss-Ausgang (Mat. inkl. Ausschuss + MGK + Maschine + Lohn)",
                    part.spritzguss_ausgang,
                ),
                ExportMoneyRow(
                    f"Spritzguss-Materialausschuss ({part.material_ausschussquote_pct} %)"
                    if part.material_ausschussquote_pct is not None
                    else "Spritzguss-Materialausschuss",
                    (
                        (part.materialkosten_inkl_ausschuss or 0) - (part.materialkosten or 0)
                        if part.materialkosten_inkl_ausschuss is not None
                        else None
                    ),
                ),
            ]
            for step in part.process_steps:
                chain_rows.extend(
                    [
                        ExportMoneyRow(
                            f"{step.bezeichnung}: Lohn / Maschine / Verbrauch",
                            step.lohnkosten + step.maschinenkosten + step.verbrauchskosten,
                        ),
                        ExportMoneyRow(
                            f"{step.bezeichnung}: Vorprodukt vor Ausschuss",
                            step.vorprodukt_eingang,
                        ),
                        ExportMoneyRow(
                            f"{step.bezeichnung}: Prozess vor Ausschuss",
                            step.kosten_vor_ausschuss,
                        ),
                        ExportMoneyRow(
                            f"{step.bezeichnung}: Ausschuss "
                            f"({step.ausschussquote_pct} %, Ausbeute {step.ausbeute_pct} %)",
                            step.ausschuss_zuschlag,
                        ),
                        ExportMoneyRow(
                            f"{step.bezeichnung}: Nach Ausbeute",
                            step.kosten_nach_ausbeute,
                            highlight=True,
                        ),
                    ]
                )
            if part.fgk_betrag is not None:
                chain_rows.append(ExportMoneyRow(f"FGK ({part.fgk_pct} %)", part.fgk_betrag))
                chain_rows.append(
                    ExportMoneyRow("Herstellkosten fertig", part.herstellkosten, highlight=True)
                )
            story.extend(_money_table(f"Prozesskette {part.bezeichnung}", chain_rows))
    else:
        story.extend(_export_table_block(data.einzelteile))

    # 6. Kaufteil-Details
    story.extend(_export_table_block(data.kaufteile))

    # 7. ASSY-Prozesskette
    story.extend(_export_table_block(data.veredelung))
    if detail and detail.processes:
        for proc in detail.processes:
            story.extend(
                _kv_table(
                    f"ASSY {proc.bezeichnung} – Vorprodukte",
                    [
                        (
                            "Vorprodukte (gemeinsam durch Ausschuss belastet)",
                            ", ".join(proc.vorprodukt_komponenten)
                            if proc.vorprodukt_komponenten
                            else "–",
                        ),
                        ("Vorproduktkosten", _money(proc.vorprodukt_eingang)),
                        ("Direkt vor Ausschuss", _money(proc.kosten_vor_ausschuss)),
                        (
                            "Ausschuss / Ausbeute",
                            f"{proc.ausschussquote_pct} % / {proc.ausbeute_pct} %",
                        ),
                        ("Ausschusszuschlag", _money(proc.ausschuss_zuschlag)),
                        ("Nach Ausbeute", _money(proc.kosten_nach_ausbeute)),
                        ("FGK", _money(proc.fgk_betrag)),
                    ],
                )
            )

    # 8. Gesamtüberleitung
    if detail and detail.ueberleitung:
        story.extend(
            _money_table(
                "Gesamtüberleitung",
                [
                    ExportMoneyRow(line.label, line.amount, highlight=line.highlight)
                    for line in detail.ueberleitung
                    if line.amount is not None
                ],
            )
        )

    story.extend(
        _kv_table(
            "Gesamtpreis und Summen",
            [
                ("Einzelteile gesamt", _money(data.einzelteile_gesamt)),
                ("Kaufteile gesamt", _money(data.kaufteile_gesamt)),
                ("Montage/ASSY gesamt", _money(data.veredelung_gesamt)),
                ("Herstellkosten", _money(data.herstellkosten)),
                ("SG&A / VVGK", _money(data.vvgk)),
                ("Selbstkosten", _money(data.selbstkosten)),
                ("Gewinn", _money(data.gewinn)),
                ("Skonto", _money(data.skonto)),
                ("Nettoverkaufspreis", _money(data.nettoverkaufspreis)),
                ("Endpreis je Stück", _money(data.baugruppenpreis_je_stueck)),
                ("Jahresumsatz", _money(data.jahresumsatz)),
                ("Gesamtergebnis", _money(data.gesamtergebnis)),
            ],
        )
    )

    # 9. Investitionen
    if data.investitionen:
        story.extend(
            _kv_table(
                "Investitionen (separat, nicht im Stückpreis)",
                [
                    (i.bezeichnung, f"{_money(i.betrag)} – {i.hinweis}")
                    for i in data.investitionen
                ],
            )
        )
    else:
        story.extend(
            _kv_table(
                "Investitionen",
                [("Hinweis", "Keine – separat, nicht im Stückpreis enthalten")],
            )
        )

    # 10. Hinweise
    hints: list[tuple[str, str]] = []
    if detail and detail.jahresstueckzahl_hinweis:
        hints.append(("Jahresstückzahl", detail.jahresstueckzahl_hinweis))
    if detail:
        for i, w in enumerate(detail.warnings, start=1):
            hints.append((f"Hinweis {i}", w))
    if hints:
        story.extend(_kv_table("Datenqualität / Hinweise", hints))

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
