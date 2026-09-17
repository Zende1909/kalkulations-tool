"""PDF-Exporte mit reportlab."""

from __future__ import annotations

import base64
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.export_models import (
    BaugruppeExportData,
    DashboardExportData,
    ExportInvestment,
    ExportMoneyRow,
    ExportTable,
    SpritzgussExportData,
)
from app.services.i18n_export import Locale, normalize_locale, t_business_case, t_common


def _fmt_dt(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%d.%m.%Y %H:%M")


def _money(amount: float | None, locale: Locale = "de") -> str:
    if amount is None:
        return t_common(locale)["no_data"]
    if normalize_locale(locale) == "en":
        return f"{amount:,.2f} EUR"
    return f"{amount:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _investition_export_table(
    investitionen: list[ExportInvestment],
    *,
    title: str,
    locale: Locale = "de",
) -> list:
    headers = list(t_common(locale)["investment_table_headers"])
    rows: list[list[str]] = []
    for inv in investitionen:
        cost = inv.cost_amount if inv.cost_amount is not None else inv.betrag
        rows.append(
            [
                inv.bezeichnung,
                inv.typ,
                _money(cost, locale),
                _money(inv.bottom_price, locale),
                _money(inv.revenue_amount, locale),
                _money(inv.margin_revenue_minus_cost, locale),
                _money(inv.margin_revenue_minus_bottom_price, locale),
                _money(inv.margin_bottom_price_minus_cost, locale),
                inv.hinweis,
            ]
        )
    return _export_table_block(ExportTable(title=title, headers=headers, rows=rows), locale=locale)


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


def _logo_image(*, width=3.2 * cm, height=1.6 * cm):
    """ReportLab-Image für das ZENDE-Logo, oder None wenn nicht vorhanden."""
    from app.services.branding import resolve_logo_path

    path = resolve_logo_path()
    if path is None:
        return None
    try:
        return Image(str(path), width=width, height=height, kind="proportional")
    except Exception:  # noqa: BLE001 – Logo darf Exporte nicht blockieren
        return None


def _header_block(company: str, title: str, meta: list[tuple[str, str]]) -> list:
    styles = getSampleStyleSheet()
    logo = _logo_image()
    title_style = ParagraphStyle(
        "BrandTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.HexColor("#0e7490"),
        spaceAfter=4,
    )
    company_style = ParagraphStyle(
        "BrandCompany",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#0f172a"),
    )
    left = []
    if logo is not None:
        left.append(logo)
        left.append(Spacer(1, 4))
    left.append(Paragraph(company, company_style))
    left.append(Spacer(1, 4))
    left.append(Paragraph(f"<b>{title}</b>", title_style))

    right_meta = [[k, v] for k, v in meta]
    right = []
    if right_meta:
        meta_table = Table(right_meta, colWidths=[3.2 * cm, 5.5 * cm])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )
        right.append(meta_table)

    header = Table([[left, right]], colWidths=[8.5 * cm, 7.5 * cm])
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDFA")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#99F6E4")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return [header, Spacer(1, 14)]


def _kv_table(title: str, rows: list[tuple[str, str]], *, locale: Locale = "de") -> list:
    story: list = [Paragraph(f"<b>{title}</b>", getSampleStyleSheet()["Heading2"]), Spacer(1, 6)]
    if not rows:
        story.append(Paragraph(t_common(locale)["no_data"], getSampleStyleSheet()["Normal"]))
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


def _money_table(title: str, rows: list[ExportMoneyRow], *, locale: Locale = "de") -> list:
    common = t_common(locale)
    data = [[common["position"], common["amount_eur"]]]
    for row in rows:
        data.append([row.label, _money(row.amount, locale)])
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


def _export_table_block(export_table: ExportTable, *, locale: Locale = "de") -> list:
    story: list = []
    if export_table.title:
        story.append(Paragraph(f"<b>{export_table.title}</b>", getSampleStyleSheet()["Heading2"]))
        story.append(Spacer(1, 6))
    if not export_table.rows:
        story.append(Paragraph(t_common(locale)["no_data"], getSampleStyleSheet()["Normal"]))
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


def _bar_chart_block(title: str, items: list[tuple[str, float]], *, locale: Locale = "de") -> list:
    story: list = [Paragraph(f"<b>{title}</b>", getSampleStyleSheet()["Heading2"]), Spacer(1, 6)]
    if not items:
        story.append(Paragraph(t_common(locale)["no_data"], getSampleStyleSheet()["Normal"]))
        return story
    max_val = max(v for _, v in items) or 1
    for label, value in items:
        bar_width = max(0.5, 10 * cm * (value / max_val))
        inner = Table([[""]], colWidths=[bar_width], rowHeights=[8])
        inner.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#0e7490"))]))
        row = Table(
            [[Paragraph(label[:40], getSampleStyleSheet()["Normal"]), inner]],
            colWidths=[6 * cm, 10 * cm],
        )
        story.extend([row, Paragraph(_money(value, locale), getSampleStyleSheet()["Normal"]), Spacer(1, 4)])
    story.append(Spacer(1, 8))
    return story


def _make_page_footer(locale: Locale = "de"):
    generated_label = t_common(locale)["generated"]

    def _page_footer(canvas, doc):  # noqa: ARG001
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#0e7490"))
        canvas.drawString(1.5 * cm, 1 * cm, "ZC PartCalc · ZENDE Consultant")
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawCentredString(
            A4[0] / 2, 1 * cm, f"{generated_label}: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )
        canvas.drawRightString(A4[0] - 1.5 * cm, 1 * cm, f"Seite {doc.page}" if locale == "de" else f"Page {doc.page}")
        canvas.restoreState()

    return _page_footer


def render_spritzguss_pdf(data: SpritzgussExportData, locale: Locale | str | None = "de") -> bytes:
    loc = normalize_locale(locale)
    common = t_common(loc)
    buffer = io.BytesIO()
    doc = _build_doc(buffer, common["part_calculation"])
    story = _header_block(
        data.company_name,
        common["part_calculation"],
        [
            (common["customer"], data.kunde or "–"),
            (common["project"], data.projekt or "–"),
            (common["part_number"], data.teilenummer),
            (common["part_name"], data.teilebezeichnung),
            (common["calculation_id"], str(data.calculation_id)),
            (common["created"], _fmt_dt(data.created_at)),
            (common["modified"], _fmt_dt(data.updated_at)),
        ],
    )
    story.extend(_kv_table(common["input_data"], [(r.label, r.value) for r in data.inputs], locale=loc))
    if data.teilbild_mime and data.teilbild_data:
        try:
            img_bytes = base64.b64decode(data.teilbild_data, validate=True)
            story.append(Spacer(1, 8))
            story.append(Paragraph(f"<b>{common['part_image']}</b>", getSampleStyleSheet()["Normal"]))
            story.append(Spacer(1, 4))
            story.append(
                Image(
                    io.BytesIO(img_bytes),
                    width=8 * cm,
                    height=6 * cm,
                    kind="proportional",
                )
            )
            story.append(Spacer(1, 8))
        except (ValueError, TypeError):
            pass
    story.extend(_money_table(common["cost_overview"], data.kosten, locale=loc))
    if data.veredelung_steps:
        story.extend(_money_table(common["finishing_steps"], data.veredelung_steps, locale=loc))
    if data.werkzeug_hinweis:
        story.append(
            Paragraph(
                f'<font color="red"><b>{data.werkzeug_hinweis}</b></font>',
                getSampleStyleSheet()["Normal"],
            )
        )
        story.append(Spacer(1, 8))
    if data.investitionen:
        story.extend(
            _investition_export_table(
                data.investitionen,
                title=common["investments_separate"],
                locale=loc,
            )
        )
    footer = _make_page_footer(loc)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_baugruppe_pdf(data: BaugruppeExportData, locale: Locale | str | None = "de") -> bytes:
    from app.services.baugruppe_export_detail import BaugruppeDetailKalkulation

    loc = normalize_locale(locale)
    common = t_common(loc)
    buffer = io.BytesIO()
    doc = _build_doc(buffer, common["assembly_detail_calculation"])
    export_date = data.export_date or datetime.now()
    # 1. Zusammenfassung
    story = _header_block(
        data.company_name,
        common["assembly_detail_calculation"],
        [
            (common["assembly_name"], data.name),
            (common["part_number"], data.teilenummer or "–"),
            (common["customer"], data.kunde or "–"),
            (common["program"], data.program or "–"),
            (common["project"], data.projekt or "–"),
            (common["country_region"], data.land or "–"),
            (common["plant_site"], data.werk or "–"),
            (common["status"], data.status or "–"),
            (common["annual_volume"], str(data.jahresstueckzahl)),
            (common["assembly_id"], str(data.assembly_id)),
            (common["structure_version"], str(data.structure_version)),
            (common["export_date"], _fmt_dt(export_date)),
            (common["manufacturing_cost"], _money(data.herstellkosten, loc)),
            (common["sga"], _money(data.vvgk, loc)),
            (common["full_cost"], _money(data.selbstkosten, loc)),
            (common["profit"], _money(data.gewinn, loc)),
            (common["cash_discount"], _money(data.skonto, loc) if data.skonto is not None else "–"),
            (common["net_selling_price"], _money(data.nettoverkaufspreis, loc)),
            (common["end_price_per_piece"], _money(data.baugruppenpreis_je_stueck, loc)),
            (common["annual_revenue"], _money(data.jahresumsatz, loc)),
            (common["created"], _fmt_dt(data.created_at)),
            (common["modified"], _fmt_dt(data.updated_at)),
        ],
    )
    if data.kosten_aufstellung:
        story.extend(_money_table(common["cost_breakdown"], data.kosten_aufstellung, locale=loc))

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
            _investition_export_table(
                data.investitionen,
                title="Investitionen (separat, nicht im Stückpreis)",
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
        story.extend(_kv_table(common["data_quality_hints"], hints, locale=loc))

    footer = _make_page_footer(loc)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_dashboard_pdf(data: DashboardExportData, locale: Locale | str | None = "de") -> bytes:
    loc = normalize_locale(locale)
    common = t_common(loc)
    buffer = io.BytesIO()
    doc = _build_doc(buffer, common["dashboard_report"])
    filters = []
    if data.filter_project:
        filters.append((common["project"], data.filter_project))
    if data.filter_customer:
        filters.append((common["customer"], data.filter_customer))
    if data.filter_status:
        filters.append((common["status"], data.filter_status))
    if data.filter_date_from or data.filter_date_to:
        filters.append(
            (
                common["period"],
                f"{data.filter_date_from or '–'} {common['period_to']} {data.filter_date_to or '–'}",
            )
        )
    if data.filter_kalkulationsart:
        filters.append((common["calculation_type"], data.filter_kalkulationsart))
    if not filters:
        filters.append((common["filter"], common["filter_none_overview"]))
    story = _header_block(data.company_name, common["dashboard_project_report"], filters)
    if data.empty_message:
        story.append(Paragraph(data.empty_message, getSampleStyleSheet()["Normal"]))
        story.append(Spacer(1, 12))
    story.extend(
        _kv_table(common["kpi_overview_sheet"], [(k.label, k.value) for k in data.kpis], locale=loc)
    )
    story.extend(_export_table_block(data.recent_calculations, locale=loc))
    story.extend(_export_table_block(data.assemblies, locale=loc))
    story.extend(_export_table_block(data.investments, locale=loc))
    if data.price_chart:
        story.extend(_bar_chart_block(common["top_end_prices"], data.price_chart[:10], locale=loc))
    if data.investment_chart:
        story.extend(
            _bar_chart_block(common["investment_volume_by_project"], data.investment_chart, locale=loc)
        )
    if data.revenue_chart:
        story.extend(
            _bar_chart_block(common["revenue_potential_by_project"], data.revenue_chart, locale=loc)
        )
    footer = _make_page_footer(loc)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def _fmt_optional_money(value: float | None, locale: Locale = "de") -> str:
    if value is None:
        return "–"
    return _money(value, locale)


def _fmt_optional_revenue(value: float | None, locale: Locale = "de") -> str:
    if value is None:
        return "–"
    whole = int(round(value))
    if normalize_locale(locale) == "en":
        return f"{whole:,} EUR"
    return f"{whole:,}".replace(",", ".") + " €"


def _fmt_integer(value: float | int | None, locale: Locale = "de") -> str:
    if value is None:
        return "–"
    if normalize_locale(locale) == "en":
        return f"{int(round(float(value))):,}"
    return f"{int(round(float(value))):,}".replace(",", ".")


def _pct_str(value: float | None, locale: Locale = "de") -> str:
    if value is None:
        return "–"
    if normalize_locale(locale) == "en":
        return f"{value:.2f}%"
    return f"{value:.2f} %".replace(".", ",")


def _tone_bg(value: float | None) -> colors.Color:
    if value is None:
        return colors.HexColor("#F8FAFC")
    if value > 0:
        return colors.HexColor("#DCFCE7")
    if value < 0:
        return colors.HexColor("#FEE2E2")
    return colors.HexColor("#F8FAFC")


def _section_heading(text: str, *, keep_with_next: bool = True) -> Paragraph:
    styles = getSampleStyleSheet()
    heading = ParagraphStyle(
        "BcSectionCentered",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=colors.HexColor("#0e7490"),
        alignment=1,  # TA_CENTER
        spaceBefore=4,
        spaceAfter=8,
        keepWithNext=keep_with_next,
    )
    return Paragraph(text.upper(), heading)


def _keep_section(heading: str, *flowables) -> KeepTogether:
    """Kleinen Abschnitt inkl. Überschrift zusammenhalten."""
    parts: list = [_section_heading(heading, keep_with_next=False), *flowables, Spacer(1, 10)]
    return KeepTogether(parts)


def _appendix_section(heading: str, *flowables) -> list:
    """Anhang: Überschrift bleibt beim Tabellenanfang, Tabelle darf umbrechen."""
    return [_section_heading(heading), *flowables, Spacer(1, 12)]


def _kpi_tile(
    label: str,
    value: str,
    hint: str | None = None,
    *,
    bg: colors.Color | None = None,
    width: float | None = None,
) -> Table:
    styles = getSampleStyleSheet()
    label_style = ParagraphStyle(
        "BcTileLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        textColor=colors.HexColor("#64748B"),
        leading=9,
        alignment=1,
    )
    value_style = ParagraphStyle(
        "BcTileValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#0F172A"),
        leading=13,
        alignment=1,
    )
    hint_style = ParagraphStyle(
        "BcTileHint",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        textColor=colors.HexColor("#94A3B8"),
        leading=8,
        alignment=1,
    )
    cells = [
        [Paragraph(label, label_style)],
        [Paragraph(value, value_style)],
        [Paragraph(hint or " ", hint_style)],
    ]
    table = Table(cells, colWidths=[width or 5.1 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), bg or colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 8),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                ("TOPPADDING", (0, 1), (-1, 1), 2),
                ("BOTTOMPADDING", (0, 1), (-1, 1), 2),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return table


def _kpi_tile_grid(tiles: list[tuple[str, str, str | None, colors.Color | None]], *, cols: int = 3) -> list:
    """Baut Kachel-Zeilen wie auf dem Business-Case-Dashboard."""
    story: list = []
    gap = 0.25 * cm
    usable = 16 * cm
    col_w = (usable - gap * (cols - 1)) / cols
    row_cells: list = []
    for idx, (label, value, hint, bg) in enumerate(tiles):
        row_cells.append(_kpi_tile(label, value, hint, bg=bg, width=col_w))
        if len(row_cells) == cols or idx == len(tiles) - 1:
            while len(row_cells) < cols:
                row_cells.append("")
            widths: list[float] = []
            data_row: list = []
            for i, cell in enumerate(row_cells):
                data_row.append(cell)
                widths.append(col_w)
                if i < cols - 1:
                    data_row.append("")
                    widths.append(gap)
            grid = Table([data_row], colWidths=widths)
            grid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.extend([grid, Spacer(1, 6)])
            row_cells = []
    return story


def _gauge_row(items: list[tuple[str, float | None, str]], *, locale: Locale = "de") -> list:
    tiles = [
        (label, _pct_str(value, locale), subtitle, _tone_bg(value))
        for label, value, subtitle in items
    ]
    return _kpi_tile_grid(tiles, cols=len(items) if 1 <= len(items) <= 3 else 3)


def _executive_headline(data, locale: Locale = "de") -> str:
    from app.services.business_case_export import format_revenue_compact, sum_display_revenue

    bc = t_business_case(locale)
    total = sum_display_revenue(data.revenue_by_year)
    ebit = data.kpis.get("ebit_actual_total_pct")
    roi = data.kpis.get("roi_incl_capex_actual_pct")
    parts = [
        f"{bc['headline_total_revenue']} {format_revenue_compact(total, locale)}",
        f"{bc['headline_ebit']} {_pct_str(ebit, locale)}",
        f"{bc['headline_roi']} {_pct_str(roi, locale)}",
    ]
    return " · ".join(parts)


def _para_cell(text: str, *, bold: bool = False, size: int = 7, align: str = "LEFT") -> Paragraph:
    styles = getSampleStyleSheet()
    alignment = {"LEFT": 0, "CENTER": 1, "RIGHT": 2}.get(align, 0)
    style = ParagraphStyle(
        f"BcCell_{bold}_{size}_{align}",
        parent=styles["Normal"],
        fontName="Helvetica-Bold" if bold else "Helvetica",
        fontSize=size,
        leading=size + 2,
        alignment=alignment,
        textColor=colors.HexColor("#0F172A"),
    )
    safe = (text or "–").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def _styled_data_table(
    headers: list[str],
    rows: list[list],
    col_widths: list[float],
    *,
    header_bg: str = "#0e7490",
) -> Table:
    styles = getSampleStyleSheet()
    hdr_style = ParagraphStyle(
        "BcHdrWhite",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9,
        alignment=1,
        textColor=colors.white,
    )
    header_row = [Paragraph(h.replace("&", "&amp;"), hdr_style) for h in headers]
    data = [header_row, *rows]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
                ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0FDFA")]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#99F6E4")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _compact_revenue_block(year_items: list[tuple[str, float]], *, locale: Locale = "de") -> list:
    """Kompakte Umsatzentwicklung als Tabelle + schlanke Balken – bleibt auf einer Seite."""
    if not year_items:
        return [Paragraph(t_common(locale)["no_data"], getSampleStyleSheet()["Normal"])]
    max_val = max(v for _, v in year_items) or 1
    bar_max = 7.5 * cm
    rows: list[list] = []
    for label, value in year_items:
        bar_w = max(0.3 * cm, bar_max * (value / max_val))
        bar = Table([[""]], colWidths=[bar_w], rowHeights=[7])
        bar.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#0e7490"))]))
        rows.append(
            [
                _para_cell(label, bold=True, size=8),
                bar,
                _para_cell(_fmt_optional_revenue(value, locale), size=8, align="RIGHT"),
            ]
        )
    table = Table(rows, colWidths=[2.2 * cm, 8.2 * cm, 5.6 * cm])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return [table]


def render_business_case_pdf(data, locale: str | None = "de") -> bytes:
    """Management-/Finance-Bericht: gleiche Dashboard-Kacheln wie die Business-Case-Seite."""
    from app.services.business_case_export import (
        BusinessCaseExportData,
        display_revenue_for_year,
        format_revenue_compact,
        revenue_period_label,
        sum_display_revenue,
    )

    if not isinstance(data, BusinessCaseExportData):
        raise TypeError("expected BusinessCaseExportData")

    loc = normalize_locale(locale)
    bc = t_business_case(loc)
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = _build_doc(buffer, str(bc["doc_title"]))

    # Header band with CI logo
    header_style = ParagraphStyle(
        "BcHeaderTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.white,
        leading=18,
    )
    sub_style = ParagraphStyle(
        "BcHeaderSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=colors.HexColor("#A5F3FC"),
        leading=11,
    )
    logo = _logo_image(width=2.8 * cm, height=1.4 * cm)
    text_block = [
        Paragraph(f"{data.company_name} – {bc['header_title_suffix']}", header_style),
        Spacer(1, 4),
        Paragraph(
            f"{str(bc['report_subtitle']).replace('&', '&amp;')}  ·  "
            f"{data.customer} / {data.program} / {data.project}  ·  "
            f"{bc['generated_at']} {_fmt_dt(data.generated_at)} UTC",
            sub_style,
        ),
    ]
    if logo is not None:
        logo_cell = Table([[logo]], colWidths=[3.2 * cm])
        logo_cell.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#67E8F9")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        header_inner = Table([[logo_cell, text_block]], colWidths=[3.6 * cm, 12.4 * cm])
    else:
        header_inner = Table([[text_block]], colWidths=[16 * cm])
    header_inner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0e7490")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story: list = [header_inner, Spacer(1, 8)]

    thesis_style = ParagraphStyle(
        "BcThesis",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor("#334155"),
        leading=12,
        alignment=1,
    )
    thesis_box = Table(
        [[Paragraph(_executive_headline(data, locale=loc), thesis_style)]],
        colWidths=[16 * cm],
    )
    thesis_box.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FDFA")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#99F6E4")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(thesis_box)
    story.append(Spacer(1, 8))

    total_display = sum_display_revenue(data.revenue_by_year)
    period = revenue_period_label(data.revenue_by_year) or "–"
    n_et = data.kpis.get("anzahl_einzelteile") or 0
    n_bg = data.kpis.get("anzahl_baugruppen") or 0
    ebit_bottom = data.kpis.get("ebit_bottom_total")
    ebit_actual = data.kpis.get("ebit_actual_total")

    story.append(
        _keep_section(
            str(bc["section_kpi_dashboard"]),
            *_kpi_tile_grid(
                [
                    (
                        str(bc["kpi_total_revenue"]),
                        format_revenue_compact(total_display, loc),
                        str(bc["hint_total_revenue"]),
                        colors.HexColor("#F8FAFC"),
                    ),
                    (
                        str(bc["kpi_ebit"]),
                        _pct_str(data.kpis.get("ebit_actual_total_pct"), loc),
                        str(bc["hint_ebit"]),
                        _tone_bg(data.kpis.get("ebit_actual_total_pct")),
                    ),
                    (
                        str(bc["kpi_roi"]),
                        _pct_str(data.kpis.get("roi_incl_capex_actual_pct"), loc),
                        str(bc["hint_roi"]),
                        _tone_bg(data.kpis.get("roi_incl_capex_actual_pct")),
                    ),
                    (
                        str(bc["kpi_period"]),
                        period,
                        str(bc["hint_period"]),
                        colors.HexColor("#F8FAFC"),
                    ),
                ],
                cols=4,
            ),
        )
    )

    story.append(
        _keep_section(
            str(bc["section_profitability"]),
            *_gauge_row(
                [
                    (str(bc["gauge_ebit"]), data.kpis.get("ebit_actual_total_pct"), str(bc["hint_gauge_ebit"])),
                    (
                        str(bc["gauge_ebit_bottom"]),
                        data.kpis.get("ebit_bottom_total_pct"),
                        str(bc["hint_gauge_ebit_bottom"]),
                    ),
                    (
                        str(bc["gauge_roi_capex"]),
                        data.kpis.get("roi_incl_capex_actual_pct"),
                        str(bc["hint_gauge_roi"]),
                    ),
                ],
                locale=loc,
            ),
        )
    )

    parts_hint = str(bc["hint_parts_assemblies_short"]).format(n_et=n_et, n_bg=n_bg)
    story.append(
        _keep_section(
            str(bc["section_operating"]),
            *_kpi_tile_grid(
                [
                    (
                        str(bc["kpi_bottom_revenue"]),
                        _fmt_optional_revenue(data.kpis.get("bottom_price_revenue_total"), loc),
                        str(bc["hint_bottom_revenue"]),
                        None,
                    ),
                    (
                        str(bc["kpi_actual_revenue"]),
                        _fmt_optional_revenue(data.kpis.get("actual_revenue_total"), loc),
                        str(bc["hint_actual_revenue"]),
                        None,
                    ),
                    (
                        str(bc["kpi_operating_cost"]),
                        _fmt_optional_money(data.kpis.get("operative_cost_total"), loc),
                        str(bc["hint_operating_cost_excel"]),
                        None,
                    ),
                    (
                        str(bc["kpi_ebit_bottom"]),
                        f"{_fmt_optional_money(ebit_bottom, loc)} ({_pct_str(data.kpis.get('ebit_bottom_total_pct'), loc)})",
                        str(bc["hint_ebit_no_capex"]),
                        _tone_bg(ebit_bottom if isinstance(ebit_bottom, (int, float)) else None),
                    ),
                    (
                        str(bc["kpi_ebit_actual"]),
                        f"{_fmt_optional_money(ebit_actual, loc)} ({_pct_str(data.kpis.get('ebit_actual_total_pct'), loc)})",
                        str(bc["hint_ebit_no_capex"]),
                        _tone_bg(ebit_actual if isinstance(ebit_actual, (int, float)) else None),
                    ),
                    (
                        str(bc["kpi_project_volume"]),
                        _fmt_integer(data.kpis.get("project_volume_total"), loc),
                        parts_hint,
                        None,
                    ),
                ],
                cols=3,
            ),
        )
    )

    roi_ops_hint = str(bc["hint_actual_roi"]).format(
        value=_pct_str(data.kpis.get("roi_operating_actual_pct"), loc)
    )
    story.append(
        _keep_section(
            str(bc["section_capital"]),
            *_kpi_tile_grid(
                [
                    (
                        str(bc["kpi_capex_total"]),
                        _fmt_optional_money(data.kpis.get("capex_cost_total"), loc),
                        str(bc["hint_capex"]),
                        None,
                    ),
                    (
                        str(bc["kpi_other_investment"]),
                        _fmt_optional_money(data.kpis.get("non_capex_investment_cost_total"), loc),
                        str(bc["hint_other_investment_excel"]),
                        None,
                    ),
                    (
                        str(bc["kpi_bound_capital"]),
                        _fmt_optional_money(data.kpis.get("bound_capital_total"), loc),
                        str(bc["hint_bound_capital"]),
                        None,
                    ),
                    (
                        str(bc["kpi_roi_bottom_capex"]),
                        _pct_str(data.kpis.get("roi_incl_capex_bottom_pct"), loc),
                        None,
                        _tone_bg(data.kpis.get("roi_incl_capex_bottom_pct")),
                    ),
                    (
                        str(bc["kpi_roi_actual_capex"]),
                        _pct_str(data.kpis.get("roi_incl_capex_actual_pct"), loc),
                        None,
                        _tone_bg(data.kpis.get("roi_incl_capex_actual_pct")),
                    ),
                    (
                        str(bc["kpi_roi_operating"]),
                        _pct_str(data.kpis.get("roi_operating_bottom_pct"), loc),
                        roi_ops_hint,
                        _tone_bg(data.kpis.get("roi_operating_bottom_pct")),
                    ),
                ],
                cols=3,
            ),
        )
    )

    # Seite 2: Charts & Szenario (nicht mitten in Seite-1-Kacheln abschneiden)
    story.append(PageBreak())

    year_items: list[tuple[str, float]] = []
    for year_row in sorted(data.revenue_by_year, key=lambda r: r.get("calendar_year") or 0):
        disp = display_revenue_for_year(year_row)
        if disp is None:
            continue
        year_items.append((str(year_row.get("calendar_year")), float(disp)))
    story.append(
        _keep_section(
            str(bc["section_revenue_by_year"]),
            *_compact_revenue_block(year_items, locale=loc),
        )
    )

    operating = (data.kpi_summary or {}).get("operating") or {}
    capital_sum = (data.kpi_summary or {}).get("capital") or {}
    scenario_headers = list(bc["scenario_headers"])
    scenario_rows = [
        [
            _para_cell(str(bc["scenario_revenue"]), bold=True, size=8),
            _para_cell(_fmt_optional_revenue(operating.get("bottom_price_revenue_total"), loc), size=8, align="RIGHT"),
            _para_cell(_fmt_optional_revenue(operating.get("actual_revenue_total"), loc), size=8, align="RIGHT"),
        ],
        [
            _para_cell(str(bc["scenario_operating_cost"]), bold=True, size=8),
            _para_cell(_fmt_optional_money(operating.get("cost_total"), loc), size=8, align="RIGHT"),
            _para_cell(_fmt_optional_money(operating.get("cost_total"), loc), size=8, align="RIGHT"),
        ],
        [
            _para_cell(str(bc["scenario_ebit"]), bold=True, size=8),
            _para_cell(_fmt_optional_money(operating.get("ebit_bottom"), loc), size=8, align="RIGHT"),
            _para_cell(_fmt_optional_money(operating.get("ebit_actual"), loc), size=8, align="RIGHT"),
        ],
        [
            _para_cell(str(bc["scenario_ebit_pct"]), bold=True, size=8),
            _para_cell(_pct_str(operating.get("ebit_bottom_pct"), loc), size=8, align="RIGHT"),
            _para_cell(_pct_str(operating.get("ebit_actual_pct"), loc), size=8, align="RIGHT"),
        ],
        [
            _para_cell(str(bc["scenario_roi_capex"]), bold=True, size=8),
            _para_cell(_pct_str(capital_sum.get("roi_incl_capex_bottom_pct"), loc), size=8, align="RIGHT"),
            _para_cell(_pct_str(capital_sum.get("roi_incl_capex_actual_pct"), loc), size=8, align="RIGHT"),
        ],
        [
            _para_cell(str(bc["scenario_roi_operating"]), bold=True, size=8),
            _para_cell(_pct_str(operating.get("roi_operating_bottom_pct"), loc), size=8, align="RIGHT"),
            _para_cell(_pct_str(operating.get("roi_operating_actual_pct"), loc), size=8, align="RIGHT"),
        ],
    ]
    scenario_table = _styled_data_table(
        [str(h) for h in scenario_headers],
        scenario_rows,
        [6 * cm, 5 * cm, 5 * cm],
    )
    story.append(_keep_section(str(bc["scenario_title"]), scenario_table))

    rev_bd = (data.kpi_summary or {}).get("revenue_breakdown") or {}
    cost_bd = (data.kpi_summary or {}).get("cost_breakdown") or {}
    if rev_bd or cost_bd:
        breakdown_rows = [
            [_para_cell(label, size=8), _para_cell(val, size=8, align="RIGHT")]
            for label, val in [
                (str(bc["breakdown_parts_bottom"]), _fmt_optional_revenue(rev_bd.get("parts_bottom_price_revenue"), loc)),
                (str(bc["breakdown_parts_actual"]), _fmt_optional_revenue(rev_bd.get("parts_actual_revenue"), loc)),
                (str(bc["breakdown_inv_bottom"]), _fmt_optional_revenue(rev_bd.get("investments_bottom_price_revenue"), loc)),
                (str(bc["breakdown_inv_actual"]), _fmt_optional_revenue(rev_bd.get("investments_actual_revenue"), loc)),
                (str(bc["breakdown_total_bottom"]), _fmt_optional_revenue(rev_bd.get("total_bottom_price_revenue"), loc)),
                (str(bc["breakdown_total_actual"]), _fmt_optional_revenue(rev_bd.get("total_actual_revenue"), loc)),
                (str(bc["breakdown_cost_parts"]), _fmt_optional_money(cost_bd.get("parts_standalone"), loc)),
                (str(bc["breakdown_cost_asm"]), _fmt_optional_money(cost_bd.get("assemblies"), loc)),
                (str(bc["breakdown_cost_capex"]), _fmt_optional_money(cost_bd.get("capex"), loc)),
                (str(bc["breakdown_cost_dev"]), _fmt_optional_money(cost_bd.get("entwicklung"), loc)),
                (str(bc["breakdown_cost_legacy"]), _fmt_optional_money(cost_bd.get("legacy"), loc)),
                (str(bc["breakdown_cost_ops"]), _fmt_optional_money(cost_bd.get("operative_total"), loc)),
                (str(bc["breakdown_bound_capital"]), _fmt_optional_money(cost_bd.get("bound_capital"), loc)),
            ]
        ]
        bd_table = _styled_data_table(
            [str(bc["col_position"]), str(bc["col_amount"])],
            breakdown_rows,
            [10 * cm, 6 * cm],
            header_bg="#334155",
        )
        story.append(_keep_section(str(bc["section_breakdown"]), bd_table))

    # Anhang ab neuer Seite – Tabellen lesbar mit umbrechenden Zellen
    story.append(PageBreak())

    position_body: list[list] = []
    for row in data.position_rows:
        position_body.append(
            [
                _para_cell(str(row[0] or ""), size=7),
                _para_cell(str(row[1] or ""), size=7),
                _para_cell(str(row[2] or ""), size=7),
                _para_cell(
                    _fmt_optional_money(row[3] if isinstance(row[3], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_money(row[4] if isinstance(row[4], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_money(row[5] if isinstance(row[5], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_integer(row[7] if isinstance(row[7], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_revenue(row[9] if isinstance(row[9], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _pct_str(row[14] if isinstance(row[14], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
            ]
        )
    mat_widths = [1.5 * cm, 2.2 * cm, 3.2 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.4 * cm, 1.7 * cm, 1.1 * cm]
    parts_headers = [str(h) for h in bc["appendix_parts_headers"]]
    if position_body:
        mat_table = _styled_data_table(parts_headers, position_body, mat_widths)
        story.extend(_appendix_section(str(bc["appendix_parts_title"]), mat_table))
    else:
        story.extend(
            _appendix_section(
                str(bc["appendix_parts_title"]),
                Paragraph(str(bc["no_parts"]), getSampleStyleSheet()["Normal"]),
            )
        )

    inv_body: list[list] = []
    for row in data.investment_rows:
        inv_body.append(
            [
                _para_cell(str(row[0] if row[0] is not None else "–"), size=7),
                _para_cell(str(row[1] if row[1] is not None else "–"), size=7),
                _para_cell(
                    _fmt_optional_money(row[7] if isinstance(row[7], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_money(row[8] if isinstance(row[8], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_money(row[9] if isinstance(row[9], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _fmt_optional_money(row[10] if isinstance(row[10], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
                _para_cell(
                    _pct_str(row[11] if isinstance(row[11], (int, float)) else None, loc),
                    size=7,
                    align="RIGHT",
                ),
            ]
        )
    inv_widths = [2.4 * cm, 4.2 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 2.0 * cm, 1.4 * cm]
    inv_headers = [str(h) for h in bc["appendix_inv_headers"]]
    if inv_body:
        inv_table = _styled_data_table(inv_headers, inv_body, inv_widths)
        story.extend(_appendix_section(str(bc["appendix_inv_title"]), inv_table))
    else:
        story.extend(
            _appendix_section(
                str(bc["appendix_inv_title"]),
                Paragraph(str(bc["no_inv"]), getSampleStyleSheet()["Normal"]),
            )
        )

    footer = _make_page_footer(loc)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
