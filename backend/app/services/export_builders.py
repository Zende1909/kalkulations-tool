"""Exportdaten aus gespeicherten Kalkulationen aufbauen."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.baugruppe import Baugruppe, BaugruppeSpritzgussZuordnung
from app.models.investition import Investition
from app.models.maschine import Maschine
from app.models.material import Material
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.services.dashboard import (
    BaugruppeRecord,
    InvestitionRecord,
    SpritzgussRecord,
    build_dashboard_summary,
    endpreis_aus_spritzguss,
    jahresumsatz_aus_baugruppe,
    preis_aus_baugruppe,
)
from app.services.export_models import (
    BaugruppeExportData,
    DashboardExportData,
    ExportInvestment,
    ExportMoneyRow,
    ExportRow,
    ExportTable,
    SpritzgussExportData,
)


def safe_filename_part(value: str, fallback: str = "export") -> str:
    cleaned = re.sub(r"[^\w\-]+", "_", (value or fallback).strip())
    return cleaned[:60] or fallback


def _euro_str(value: float | None) -> str:
    if value is None:
        return "Keine Daten"
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct_str(value: float) -> str:
    return f"{value:.2f} %".replace(".", ",")


def _float_from(obj: dict | None, key: str) -> float | None:
    if not isinstance(obj, dict):
        return None
    raw = obj.get(key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def _werkzeug_label(art: str) -> str:
    return "Amortisation" if art == "amortisation" else "Einmalzahlung"


def build_spritzguss_export(db: Session, calculation_id: int) -> SpritzgussExportData:
    obj = db.get(SpritzgussKalkulation, calculation_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden")
    if not isinstance(obj.ergebnis, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kalkulation wurde noch nicht gespeichert/berechnet – Export nicht möglich",
        )

    ergebnis = obj.ergebnis
    bloecke = obj.ergebnis_bloecke if isinstance(obj.ergebnis_bloecke, dict) else {}
    zusammenfassung = bloecke.get("zusammenfassung") if isinstance(bloecke.get("zusammenfassung"), dict) else {}

    material_name = "–"
    if obj.material_id:
        mat = db.get(Material, obj.material_id)
        if mat:
            material_name = f"{mat.bezeichnung} ({mat.material_nr})"

    maschine_name = "–"
    if obj.maschine_id:
        maschine = db.get(Maschine, obj.maschine_id)
        if maschine:
            maschine_name = f"{maschine.bezeichnung} ({maschine.maschinen_nr})"

    inputs = [
        ExportRow("Material", material_name),
        ExportRow("Teilegewicht netto", f"{obj.teilegewicht_netto_g:.2f} g"),
        ExportRow("Schussgewicht", f"{obj.schussgewicht_g:.2f} g"),
        ExportRow("Ausschussquote", _pct_str(obj.ausschussquote_pct)),
        ExportRow("Materialpreis", _euro_str(obj.materialpreis_pro_kg) + " / kg"),
        ExportRow("Maschine", maschine_name),
        ExportRow("Zykluszeit", f"{obj.zykluszeit_s:.2f} s"),
        ExportRow("Kavitäten", str(obj.kavitaeten)),
        ExportRow("Werkzeugmodus", _werkzeug_label(obj.werkzeug_abrechnungsart)),
        ExportRow("Werkzeugkosten", _euro_str(obj.werkzeugkosten_eur)),
        ExportRow(
            "Amortisationsvolumen",
            str(obj.amortisationsvolumen) if obj.amortisationsvolumen else "–",
        ),
        ExportRow("Jahresstückzahl", str(obj.jahresstueckzahl)),
        ExportRow("MGK", _pct_str(obj.mgk_pct)),
        ExportRow("FGK", _pct_str(obj.fgk_pct)),
        ExportRow("VVGK", _pct_str(obj.vvgk_pct)),
        ExportRow("Gewinn", _pct_str(obj.gewinn_pct)),
        ExportRow("Skonto", _pct_str(obj.skonto_pct)),
    ]

    def money(label: str, key: str, *, highlight: bool = False) -> ExportMoneyRow:
        val = _float_from(zusammenfassung, key)
        if val is None:
            val = _float_from(ergebnis, key)
        return ExportMoneyRow(label, val, highlight=highlight)

    kosten = [
        ExportMoneyRow(
            "Materialkosten",
            _float_from(ergebnis, "materialkosten_inkl_ausschuss")
            or _float_from(ergebnis, "materialkosten"),
        ),
        ExportMoneyRow("Materialgemeinkosten", _float_from(ergebnis, "materialgemeinkosten")),
        money("Maschinenkosten", "maschinenkosten"),
        money("Fertigungslohn", "fertigungslohn"),
        money("Fertigungsgemeinkosten", "fertigungsgemeinkosten"),
        money("Werkzeugkostenanteil je Stück", "werkzeugkostenanteil"),
        money("Veredelungskosten gesamt", "veredelung_gesamt"),
        money("Gesamte Herstellkosten", "gesamte_herstellkosten"),
        money("VVGK", "vvgk"),
        money("Selbstkosten", "selbstkosten"),
        money("Gewinn", "gewinn"),
        money("Nettoverkaufspreis gesamt", "nettoverkaufspreis_gesamt"),
        money("Skonto", "skonto"),
        ExportMoneyRow(
            "Endpreis je Stück",
            endpreis_aus_spritzguss(ergebnis),
            highlight=True,
        ),
    ]

    veredelung_steps: list[ExportMoneyRow] = []
    for schritt in ergebnis.get("veredelung_schritte", []) or []:
        if isinstance(schritt, dict):
            label = schritt.get("bezeichnung", "Veredelung")
            amount = _float_from(schritt, "kosten_gesamt")
            veredelung_steps.append(ExportMoneyRow(label, amount))

    if not veredelung_steps:
        veredel_block = bloecke.get("veredelung") if isinstance(bloecke.get("veredelung"), dict) else {}
        for key, val in (veredel_block or {}).items():
            if key != "veredelung_gesamt":
                veredelung_steps.append(ExportMoneyRow(key, float(val) if val is not None else None))

    investitionen_rows = db.scalars(
        select(Investition).where(Investition.calculation_id == calculation_id)
    ).all()
    investitionen = [
        ExportInvestment(
            bezeichnung=inv.description or inv.part_name,
            typ=inv.investment_type,
            betrag=float(inv.amount),
            status=inv.status,
            hinweis=(
                "Separat, nicht im Stückpreis enthalten"
                if inv.payment_type.casefold() == "einmalzahlung"
                else "Separat ausgewiesen"
            ),
        )
        for inv in investitionen_rows
    ]

    werkzeug_hinweis = None
    if obj.werkzeug_abrechnungsart == "einmalzahlung" and obj.werkzeugkosten_eur > 0:
        werkzeug_hinweis = "Separat, nicht im Stückpreis enthalten"
    elif _float_from(ergebnis, "werkzeug_einmalzahlung"):
        einmal = _float_from(ergebnis, "werkzeug_einmalzahlung") or 0
        if einmal > 0:
            werkzeug_hinweis = "Separat, nicht im Stückpreis enthalten"

    return SpritzgussExportData(
        company_name=settings.COMPANY_NAME,
        calculation_id=obj.id,
        teilebezeichnung=obj.teilebezeichnung,
        teilenummer=obj.teilenummer,
        kunde=obj.kunde,
        projekt=obj.projekt,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        inputs=inputs,
        kosten=kosten,
        veredelung_steps=veredelung_steps,
        investitionen=investitionen,
        werkzeug_hinweis=werkzeug_hinweis,
        endpreis=endpreis_aus_spritzguss(ergebnis),
    )


def build_baugruppe_export(db: Session, assembly_id: int) -> BaugruppeExportData:
    obj = db.get(Baugruppe, assembly_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")
    if not isinstance(obj.ergebnis, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Baugruppe wurde noch nicht gespeichert/berechnet – Export nicht möglich",
        )

    ergebnis = obj.ergebnis
    einzelteile_rows: list[list[str]] = []
    for p in ergebnis.get("einzelteile", []) or []:
        if isinstance(p, dict):
            einzelteile_rows.append(
                [
                    p.get("bezeichnung", ""),
                    p.get("detail", {}).get("teilenummer", "") if isinstance(p.get("detail"), dict) else "",
                    str(p.get("menge", "")),
                    _euro_str(_float_from(p, "einzelpreis")),
                    _euro_str(_float_from(p, "zwischensumme")),
                ]
            )

    kaufteile_rows: list[list[str]] = []
    for p in ergebnis.get("kaufteile", []) or []:
        if isinstance(p, dict):
            kaufteile_rows.append(
                [
                    p.get("bezeichnung", ""),
                    p.get("detail", {}).get("lieferant", "") if isinstance(p.get("detail"), dict) else "",
                    str(p.get("menge", "")),
                    _euro_str(_float_from(p, "einzelpreis")),
                    _euro_str(_float_from(p, "zwischensumme")),
                ]
            )

    veredelung_rows: list[list[str]] = []
    for p in ergebnis.get("veredelungen", []) or []:
        if isinstance(p, dict):
            veredelung_rows.append(
                [
                    str(p.get("reihenfolge", "")),
                    p.get("bezeichnung", ""),
                    _euro_str(_float_from(p, "kosten_je_stueck")),
                    str(p.get("mengenfaktor", "")),
                    _euro_str(_float_from(p, "zwischensumme")),
                ]
            )

    sg_zuordnungen = db.scalars(
        select(BaugruppeSpritzgussZuordnung).where(
            BaugruppeSpritzgussZuordnung.baugruppe_id == assembly_id
        )
    ).all()
    sg_ids = [r.spritzguss_kalkulation_id for r in sg_zuordnungen]

    conditions = [Investition.baugruppe_id == assembly_id]
    if sg_ids:
        conditions.append(Investition.calculation_id.in_(sg_ids))
    inv_rows = list(db.scalars(select(Investition).where(or_(*conditions))).all())
    seen: set[int] = set()
    investitionen: list[ExportInvestment] = []
    for inv in inv_rows:
        if inv.id in seen:
            continue
        seen.add(inv.id)
        investitionen.append(
            ExportInvestment(
                bezeichnung=inv.description or inv.part_name,
                typ=inv.investment_type,
                betrag=float(inv.amount),
                status=inv.status,
                hinweis="Separat, nicht im Stückpreis enthalten",
            )
        )

    return BaugruppeExportData(
        company_name=settings.COMPANY_NAME,
        assembly_id=obj.id,
        name=obj.name,
        teilenummer=obj.teilenummer,
        kunde=obj.kunde,
        projekt=obj.projekt,
        jahresstueckzahl=obj.jahresstueckzahl,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        einzelteile=ExportTable(
            "Einzelteile",
            ["Bezeichnung", "Teilenummer", "Menge", "Einzelpreis", "Zwischensumme"],
            einzelteile_rows,
        ),
        kaufteile=ExportTable(
            "Kaufteile",
            ["Bezeichnung", "Lieferant", "Menge", "Einzelpreis", "Zwischensumme"],
            kaufteile_rows,
        ),
        veredelung=ExportTable(
            "Montage / Veredelung",
            ["Reihenfolge", "Bezeichnung", "Kosten/St.", "Faktor", "Zwischensumme"],
            veredelung_rows,
        ),
        investitionen=investitionen,
        einzelteile_gesamt=_float_from(ergebnis, "einzelteile_gesamt") or 0,
        kaufteile_gesamt=_float_from(ergebnis, "kaufteile_gesamt") or 0,
        veredelung_gesamt=_float_from(ergebnis, "veredelung_gesamt") or 0,
        baugruppenpreis_je_stueck=preis_aus_baugruppe(ergebnis),
        jahresumsatz=jahresumsatz_aus_baugruppe(ergebnis, obj.jahresstueckzahl),
    )


def _load_dashboard_sources(db: Session) -> tuple[list[SpritzgussRecord], list[BaugruppeRecord], list[InvestitionRecord]]:
    from app.api.v1.dashboard import (
        _load_baugruppe_records,
        _load_investition_records,
        _load_spritzguss_records,
    )

    return (
        _load_spritzguss_records(db),
        _load_baugruppe_records(db),
        _load_investition_records(db),
    )


def build_dashboard_export(
    db: Session,
    *,
    project: str | None = None,
    customer: str | None = None,
) -> DashboardExportData:
    sg_rows, bg_rows, inv_rows = _load_dashboard_sources(db)
    summary = build_dashboard_summary(
        sg_rows, bg_rows, inv_rows, project=project, customer=customer
    )
    kpis = summary["kpis"]
    has_data = any(
        [
            kpis["anzahl_spritzguss_kalkulationen"],
            kpis["anzahl_baugruppen"],
            summary["investments"],
        ]
    )

    def kpi_row(label: str, key: str, *, money: bool = False, avg: bool = False) -> ExportRow:
        val = kpis[key]
        if avg and val is None:
            text = "Keine Daten"
        elif money or avg:
            text = _euro_str(val) if val is not None else "Keine Daten"
        else:
            text = str(val if val is not None else 0)
        return ExportRow(label, text)

    kpi_rows = [
        kpi_row("Anzahl Projekte", "anzahl_projekte"),
        kpi_row("Spritzguss-Kalkulationen", "anzahl_spritzguss_kalkulationen"),
        kpi_row("Anzahl Baugruppen", "anzahl_baugruppen"),
        kpi_row("Ø Endpreis je Einzelteil", "durchschnitt_endpreis_einzelteil", avg=True),
        kpi_row("Ø Baugruppenpreis je Stück", "durchschnitt_baugruppenpreis", avg=True),
        kpi_row("Investitionen gesamt", "investitionen_gesamt", money=True),
        kpi_row("Jahresstückzahl", "jahresstueckzahl"),
        kpi_row("Umsatzpotenzial / Jahr", "umsatzpotenzial_jahr", money=True),
    ]

    recent = ExportTable(
        "Letzte Kalkulationen",
        ["Art", "Bezeichnung", "Nummer", "Kunde", "Projekt", "Endpreis/St.", "Geändert"],
        [
            [
                r["kalkulationsart"],
                r["bezeichnung"],
                r["nummer"],
                r["kunde"],
                r["projekt"],
                _euro_str(r.get("endpreis_je_stueck")),
                r["updated_at"].strftime("%d.%m.%Y %H:%M")
                if isinstance(r["updated_at"], datetime)
                else str(r["updated_at"]),
            ]
            for r in summary["recent_calculations"]
        ],
    )

    assemblies = ExportTable(
        "Baugruppen",
        ["Name", "Teilenummer", "Kunde", "Projekt", "Preis/St.", "Jahresstückzahl", "Jahresumsatz"],
        [
            [
                r["name"],
                r["teilenummer"],
                r["kunde"],
                r["projekt"],
                _euro_str(r.get("preis_je_stueck")),
                str(r["jahresstueckzahl"]),
                _euro_str(r.get("jahresumsatz")),
            ]
            for r in summary["assemblies"]
        ],
    )

    investments = ExportTable(
        "Investitionen",
        ["Bezeichnung", "Typ", "Betrag", "Projekt", "Status", "Hinweis"],
        [
            [
                r["bezeichnung"],
                r["typ"],
                _euro_str(r["betrag"]),
                r["projekt"],
                r["status"],
                r["hinweis"],
            ]
            for r in summary["investments"]
        ],
    )

    price_comparison = ExportTable(
        "Preisvergleich Top 10",
        ["Bezeichnung", "Typ", "Endpreis"],
        [
            [r["label"], r["typ"], _euro_str(r["value"])]
            for r in summary["price_comparison"]
        ],
    )

    inv_by_proj = ExportTable(
        "Investitionen je Projekt",
        ["Projekt", "Betrag"],
        [[r["projekt"], _euro_str(r["betrag"])] for r in summary["investment_by_project"]],
    )

    rev_by_proj = ExportTable(
        "Umsatzpotenzial je Projekt",
        ["Projekt", "Betrag"],
        [[r["projekt"], _euro_str(r["betrag"])] for r in summary["revenue_by_project"]],
    )

    return DashboardExportData(
        company_name=settings.COMPANY_NAME,
        filter_project=project,
        filter_customer=customer,
        generated_at=datetime.now(timezone.utc),
        kpis=kpi_rows,
        recent_calculations=recent,
        assemblies=assemblies,
        investments=investments,
        price_comparison=price_comparison,
        investment_by_project=inv_by_proj,
        revenue_by_project=rev_by_proj,
        price_chart=[(r["label"], float(r["value"])) for r in summary["price_comparison"]],
        investment_chart=[(r["projekt"], float(r["betrag"])) for r in summary["investment_by_project"]],
        revenue_chart=[(r["projekt"], float(r["betrag"])) for r in summary["revenue_by_project"]],
        has_data=has_data,
        empty_message=None if has_data else "Keine Daten für die gewählten Filter vorhanden.",
    )


def spritzguss_export_filename(data: SpritzgussExportData, ext: str) -> str:
    return f"einzelteil_{safe_filename_part(data.teilenummer, str(data.calculation_id))}.{ext}"


def baugruppe_export_filename(data: BaugruppeExportData, ext: str) -> str:
    nummer = data.teilenummer or data.name
    return f"baugruppe_{safe_filename_part(nummer, str(data.assembly_id))}.{ext}"


def dashboard_export_filename(data: DashboardExportData, ext: str) -> str:
    parts = ["dashboard"]
    if data.filter_project:
        parts.append(safe_filename_part(data.filter_project, "projekt"))
    elif data.filter_customer:
        parts.append(safe_filename_part(data.filter_customer, "kunde"))
    else:
        parts.append("gesamt")
    return f"{'_'.join(parts)}.{ext}"
