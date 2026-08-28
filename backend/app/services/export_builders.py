"""Exportdaten aus gespeicherten Kalkulationen aufbauen."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import inspect as sa_inspect
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
    parse_json_dict,
    preis_aus_baugruppe,
)
from app.services.baugruppe_export_detail import build_baugruppe_detail_kalkulation
from app.services.dashboard_assembly import build_assembly_overview
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


def _pct_str(value: float | None) -> str:
    if value is None:
        return "–"
    return f"{value:.2f} %".replace(".", ",")


def _pct_applied_or_stored(
    ergebnis: dict | None, applied_key: str, stored: float | None
) -> str:
    applied = _float_from(ergebnis, applied_key)
    return _pct_str(applied if applied is not None else float(stored or 0))


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
    ergebnis = parse_json_dict(obj.ergebnis)
    if not ergebnis:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kalkulation wurde noch nicht gespeichert/berechnet – Export nicht möglich",
        )
    bloecke = parse_json_dict(obj.ergebnis_bloecke) or {}
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
        ExportRow("Teilegewicht netto (Information)", f"{obj.teilegewicht_netto_g:.2f} g"),
        ExportRow("Schussgewicht / Brutto (Materialbasis)", f"{obj.schussgewicht_g:.2f} g"),
        ExportRow("Material-Ausschussquote", _pct_str(obj.ausschussquote_pct)),
        ExportRow("Materialpreis", _euro_str(obj.materialpreis_pro_kg) + " / kg"),
        ExportRow(
            "Material-Nominierung",
            str(
                getattr(obj, "material_nominierung", None)
                or ergebnis.get("material_nominierung")
                or "–"
            ),
        ),
        ExportRow("Maschine", maschine_name),
        ExportRow("Zykluszeit", f"{obj.zykluszeit_s:.2f} s"),
        ExportRow("Kavitäten", str(obj.kavitaeten)),
        ExportRow("Jahresstückzahl", str(obj.jahresstueckzahl)),
        ExportRow(
            "Werk / Standort",
            (
                f"{(ergebnis.get('werk_snapshot') or {}).get('code', '–')} "
                f"({(ergebnis.get('werk_snapshot') or {}).get('currency', '')}, "
                f"FX {(ergebnis.get('werk_snapshot') or {}).get('fx_to_eur', '–')})"
                if isinstance(ergebnis.get("werk_snapshot"), dict)
                else "–"
            ),
        ),
        ExportRow(
            "Maschinenrate Quellwährung",
            (
                f"{(ergebnis.get('maschinen_rate_snapshot') or {}).get('stundensatz_source', '–')} "
                f"{(ergebnis.get('maschinen_rate_snapshot') or {}).get('source_currency', '')}/h"
                if isinstance(ergebnis.get("maschinen_rate_snapshot"), dict)
                else "–"
            ),
        ),
        ExportRow(
            "Losgröße (aktiv)",
            str(
                ergebnis.get("losgroesse_aktiv")
                or getattr(obj, "losgroesse", None)
                or ergebnis.get("losgroesse")
                or "–"
            ),
        ),
        ExportRow(
            "Losgrößen-Modus",
            str(ergebnis.get("losgroesse_modus") or "–"),
        ),
        ExportRow(
            "Durchschnittlicher Jahresbedarf",
            str(ergebnis.get("losgroesse_jahresbedarf") or obj.jahresstueckzahl or "–"),
        ),
        ExportRow(
            "Arbeitstage pro Jahr",
            str(ergebnis.get("arbeitstage_pro_jahr") or "–"),
        ),
        ExportRow(
            "Produktionsintervall (Arbeitstage)",
            str(ergebnis.get("produktionsintervall_arbeitstage") or "–"),
        ),
        ExportRow(
            "Automatische Losgröße",
            str(ergebnis.get("losgroesse_automatisch") or "–"),
        ),
        ExportRow(
            "Manuelle Losgröße",
            str(ergebnis.get("losgroesse_manuell") or getattr(obj, "losgroesse_manuell", None) or "–"),
        ),
        ExportRow(
            "Losgrößen-Hinweis",
            "Die automatische Losgröße basiert auf einem Produktionsintervall "
            "und ist keine lagerkostenoptimierte EOQ-/Andler-Losgröße.",
        ),
        ExportRow(
            "Setup aktiv",
            "ja" if ergebnis.get("setup_aktiv") else "nein",
        ),
        ExportRow(
            "Setup-Zeit",
            f"{float(ergebnis.get('setup_zeit_min') or 0):.1f} min",
        ),
        ExportRow(
            "Material-MGK",
            _pct_applied_or_stored(ergebnis, "applied_mgk_pct", obj.mgk_pct),
        ),
        ExportRow("FGK", _pct_applied_or_stored(ergebnis, "applied_fgk_pct", obj.fgk_pct)),
        ExportRow(
            "FGK-Basis",
            _euro_str(_float_from(ergebnis, "fgk_basis")),
        ),
        ExportRow("SG&A / VVGK", _pct_applied_or_stored(ergebnis, "applied_vvgk_pct", obj.vvgk_pct)),
        ExportRow("Profit / Gewinn", _pct_applied_or_stored(ergebnis, "applied_gewinn_pct", obj.gewinn_pct)),
        ExportRow("Skonto", _pct_applied_or_stored(ergebnis, "applied_skonto_pct", obj.skonto_pct)),
    ]

    def money(label: str, key: str, *, highlight: bool = False) -> ExportMoneyRow:
        val = _float_from(zusammenfassung, key)
        if val is None:
            val = _float_from(ergebnis, key)
        return ExportMoneyRow(label, val, highlight=highlight)

    kosten = [
        ExportMoneyRow(
            "Materialkosten vor Ausschuss",
            _float_from(ergebnis, "materialkosten"),
        ),
        ExportMoneyRow(
            "Materialausschuss",
            _float_from(ergebnis, "materialausschuss_betrag"),
        ),
        ExportMoneyRow(
            "Materialkosten inkl. Ausschuss / MGK-Basis",
            _float_from(ergebnis, "materialkosten_inkl_ausschuss")
            or _float_from(ergebnis, "materialkosten")
            or _float_from(ergebnis, "mgk_basis"),
        ),
        ExportMoneyRow("Material-MGK", _float_from(ergebnis, "materialgemeinkosten")),
        ExportMoneyRow(
            "Materialkosten inkl. MGK",
            _float_from(ergebnis, "materialkosten_gesamt"),
        ),
        ExportMoneyRow(
            "Bruttokapazität exakt (Stück/h)",
            _float_from(ergebnis, "bruttokapazitaet_exakt"),
        ),
        ExportMoneyRow(
            "Bruttokapazität ROUND (Stück/h)",
            _float_from(ergebnis, "bruttokapazitaet"),
        ),
        ExportMoneyRow(
            "Nettokapazität (Stück/h)",
            _float_from(ergebnis, "nettokapazitaet"),
        ),
        money("Maschinenkosten", "maschinenkosten"),
        money("Fertigungslohn", "fertigungslohn"),
        ExportMoneyRow(
            "Setup Maschinen je Teil (Anteil, gerundet)",
            _float_from(ergebnis, "setup_maschinenkosten_je_teil"),
        ),
        ExportMoneyRow(
            "Setup Lohn je Teil (Anteil, gerundet)",
            _float_from(ergebnis, "setup_lohnkosten_je_teil"),
        ),
        ExportMoneyRow(
            "Setup gesamt je Teil",
            _float_from(ergebnis, "setup_kosten_je_teil"),
        ),
        ExportMoneyRow("FGK-Basis", _float_from(ergebnis, "fgk_basis")),
        money("Fertigungsgemeinkosten (FGK)", "fertigungsgemeinkosten"),
        money("Spritzguss-Herstellkosten", "spritzguss_herstellkosten"),
        money("Veredelungskosten gesamt", "veredelung_gesamt"),
        money("Herstellkosten gesamt", "gesamte_herstellkosten"),
        money("SG&A / VVGK", "vvgk"),
        money("Selbstkosten", "selbstkosten"),
        money("Profit / Gewinn", "gewinn"),
        money("Nettoverkaufspreis", "nettoverkaufspreis_gesamt"),
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
            quote = _float_from(schritt, "ausschussquote_pct")
            if quote is not None and quote > 0:
                veredelung_steps.append(
                    ExportMoneyRow(
                        f"{label} – Ausschuss {_pct_str(quote)}",
                        _float_from(schritt, "ausschuss_zuschlag"),
                    )
                )
                veredelung_steps.append(
                    ExportMoneyRow(
                        f"{label} – Vorprodukt-Eingang",
                        _float_from(schritt, "vorprodukt_eingang"),
                    )
                )

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
            bezeichnung=inv.name or inv.description or inv.part_name,
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
    if investitionen:
        werkzeug_hinweis = "Investitionen separat ausgewiesen, nicht im Stückpreis enthalten"

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
    ergebnis = parse_json_dict(obj.ergebnis)
    if not ergebnis:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Baugruppe wurde noch nicht gespeichert/berechnet – Export nicht möglich",
        )

    overview = build_assembly_overview(db, assembly_id)
    einzelteile_rows: list[list[str]] = []
    kaufteile_rows: list[list[str]] = []
    veredelung_rows: list[list[str]] = []
    bom_rows: list[list[str]] = []

    legacy_teile = ergebnis.get("einzelteile") or []
    if isinstance(legacy_teile, list) and legacy_teile:
        for p in legacy_teile:
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
    legacy_kauf = ergebnis.get("kaufteile") or []
    if isinstance(legacy_kauf, list) and legacy_kauf:
        for p in legacy_kauf:
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
    legacy_vered = ergebnis.get("veredelungen") or []
    if isinstance(legacy_vered, list) and legacy_vered:
        for p in legacy_vered:
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

    for item in overview["bom"]:
        bom_rows.append(
            [
                str(item.get("position_type") or ""),
                str(item.get("bezeichnung") or ""),
                str(item.get("teilenummer") or ""),
                str(item.get("menge") or ""),
                _euro_str(item.get("einzelpreis")),
                _euro_str(item.get("zwischensumme")),
            ]
        )
        ptype = item.get("position_type")
        row_common = [
            str(item.get("bezeichnung") or ""),
            str(item.get("teilenummer") or ""),
            str(item.get("menge") or ""),
            _euro_str(item.get("einzelpreis")),
            _euro_str(item.get("zwischensumme")),
        ]
        if not legacy_teile and ptype in {"PART", "SUBASSEMBLY"}:
            einzelteile_rows.append(row_common)
        elif not legacy_kauf and ptype == "PURCHASED_PART":
            kaufteile_rows.append(
                [
                    str(item.get("bezeichnung") or ""),
                    "",
                    str(item.get("menge") or ""),
                    _euro_str(item.get("einzelpreis")),
                    _euro_str(item.get("zwischensumme")),
                ]
            )
        elif not legacy_vered and ptype == "PROCESS":
            veredelung_rows.append(
                [
                    "",
                    str(item.get("bezeichnung") or ""),
                    _euro_str(item.get("einzelpreis")),
                    str(item.get("mengenfaktor") or ""),
                    _euro_str(item.get("zwischensumme")),
                ]
            )

    sg_ids: list[int] = []
    bind = db.get_bind()
    if bind is not None and sa_inspect(bind).has_table("baugruppe_spritzguss_zuordnungen"):
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
                bezeichnung=inv.name or inv.description or inv.part_name,
                typ=inv.investment_type,
                betrag=float(inv.amount),
                status=inv.status,
                hinweis="Separat, nicht im Stückpreis enthalten",
            )
        )
    for inv in overview["investitionen"]:
        if inv["id"] in seen:
            continue
        seen.add(inv["id"])
        investitionen.append(
            ExportInvestment(
                bezeichnung=inv["bezeichnung"],
                typ=inv["typ"],
                betrag=float(inv["betrag"]),
                status=inv["status"],
                hinweis="Separat, nicht im Stückpreis enthalten",
            )
        )

    skonto = overview["skonto"]
    if skonto is None and "skonto" in ergebnis:
        skonto = 0.0

    export_date = datetime.now(timezone.utc)
    detail = build_baugruppe_detail_kalkulation(db, assembly_id)

    markup_rows = [
        [
            a.bezeichnung,
            f"{a.satz_prozent:.2f} %".replace(".", ",") if a.satz_prozent is not None else "–",
            _euro_str(a.betrag) if a.betrag is not None else (a.hinweis or "Satz (Stammdaten)"),
        ]
        for a in detail.assumptions
        if a.satz_prozent is not None or a.betrag is not None
    ]
    if not markup_rows:
        markup_rows = [
            [
                row["bezeichnung"],
                f"{row['satz_prozent']:.2f} %".replace(".", ",")
                if row.get("satz_prozent") is not None
                else "–",
                _euro_str(row.get("betrag")),
            ]
            for row in overview["zuschlagssaetze"]
        ]
    if not markup_rows and "skonto" in ergebnis:
        markup_rows = [
            ["SG&A / VVGK", "–", _euro_str(overview["vvgk"])],
            ["Profit / Gewinn", "–", _euro_str(overview["gewinn"])],
            ["Skonto", "–", _euro_str(skonto)],
        ]
    # Skonto immer ausweisen, wenn im Ergebnis vorhanden
    if markup_rows and not any("Skonto" in str(r[0]) for r in markup_rows) and "skonto" in ergebnis:
        markup_rows.append(["Skonto", "–", _euro_str(skonto)])

    jahresstueckzahl = (
        int(detail.jahresstueckzahl)
        if detail.jahresstueckzahl is not None
        else int(obj.jahresstueckzahl or 0)
    )
    endpreis = preis_aus_baugruppe(ergebnis)
    jahresumsatz = (
        float(detail.jahresumsatz)
        if detail.jahresumsatz is not None
        else (
            round(float(endpreis) * jahresstueckzahl, 2)
            if endpreis is not None
            else 0.0
        )
    )

    kosten_aufstellung = [
        ExportMoneyRow("Einzelteilkosten", overview["einzelteilkosten"]),
        ExportMoneyRow("Kaufteilkosten", overview["kaufteilkosten"]),
        ExportMoneyRow("Veredelungskosten", overview["veredelungskosten"]),
        ExportMoneyRow("Investitions-/Werkzeugkosten", overview["investitionskosten"]),
        ExportMoneyRow("FGK-Basis", _float_from(ergebnis, "fgk_basis")),
        ExportMoneyRow(
            "Fertigungsgemeinkosten (FGK)",
            _float_from(ergebnis, "fertigungsgemeinkosten"),
        ),
        ExportMoneyRow("Herstellkosten", overview["herstellkosten"]),
        ExportMoneyRow("SG&A / VVGK", overview["vvgk"]),
        ExportMoneyRow("Profit / Gewinn", overview["gewinn"]),
        ExportMoneyRow("Skonto", skonto),
        ExportMoneyRow("Nettoverkaufspreis", overview["nettoverkaufspreis"]),
        ExportMoneyRow(
            "Preis pro Stück",
            endpreis,
            highlight=True,
        ),
        ExportMoneyRow("Jahresumsatz", jahresumsatz, highlight=True),
        ExportMoneyRow("Gesamtergebnis", overview["gesamtsumme"], highlight=True),
    ]
    for yield_detail in ergebnis.get("process_yield_details") or []:
        if not isinstance(yield_detail, dict):
            continue
        name = yield_detail.get("name_snapshot") or yield_detail.get("label") or "Prozess"
        quote = _float_from(yield_detail, "ausschussquote_pct")
        kosten_aufstellung.append(
            ExportMoneyRow(
                f"ASSY/Prozess-Ausschuss {name}"
                + (f" ({_pct_str(quote)})" if quote is not None else ""),
                _float_from(yield_detail, "ausschuss_zuschlag"),
            )
        )

    # Detail-Tabellen für Excel/PDF (überschreiben Legacy-Kurzzeilen wenn vorhanden)
    if detail.parts:
        einzelteile_rows = []
        for p in detail.parts:
            einzelteile_rows.append(
                [
                    p.bezeichnung,
                    p.teilenummer,
                    str(p.menge),
                    p.price_basis,
                    p.material_name or "–",
                    _euro_str(p.materialpreis_pro_kg) + " / kg" if p.materialpreis_pro_kg is not None else "–",
                    f"{p.teilegewicht_netto_g:.2f} g" if p.teilegewicht_netto_g is not None else "–",
                    f"{p.schussgewicht_g:.2f} g" if p.schussgewicht_g is not None else "–",
                    _euro_str(p.materialkosten),
                    _pct_str(p.material_ausschussquote_pct),
                    _euro_str(p.materialkosten_inkl_ausschuss),
                    p.material_nominierung or "fehlend",
                    _pct_str(p.mgk_pct),
                    _euro_str(p.material_mgk),
                    _euro_str(p.maschinenkosten),
                    _euro_str(p.fertigungslohn),
                    _euro_str(p.spritzguss_ausgang),
                    _euro_str(p.veredelung_direkt_vor),
                    _euro_str(p.fgk_basis),
                    _pct_str(p.fgk_pct),
                    _euro_str(p.fgk_betrag),
                    _euro_str(p.herstellkosten),
                    _euro_str(p.zwischensumme),
                    "; ".join(p.hinweise) if p.hinweise else ("Legacy" if p.legacy else ""),
                ]
            )
    if detail.purchased:
        kaufteile_rows = []
        for k in detail.purchased:
            kaufteile_rows.append(
                [
                    k.bezeichnung,
                    k.artikelnummer,
                    k.lieferant,
                    str(k.menge),
                    _euro_str(k.einkaufspreis),
                    k.nominierung or "fehlend",
                    _pct_str(k.mgk_pct),
                    _euro_str(k.kaufteil_mgk),
                    _euro_str(k.preis_inkl_mgk),
                    _euro_str(k.zwischensumme),
                    "; ".join(k.hinweise) if k.hinweise else ("Legacy" if k.legacy else ""),
                ]
            )
    if detail.processes:
        veredelung_rows = []
        for proc in detail.processes:
            veredelung_rows.append(
                [
                    str(proc.sequence),
                    proc.bezeichnung,
                    _euro_str(proc.lohnkosten),
                    _euro_str(proc.maschinenkosten),
                    _euro_str(proc.verbrauchskosten),
                    _euro_str(proc.kosten_vor_ausschuss),
                    _pct_str(proc.ausschussquote_pct),
                    _pct_str(proc.ausbeute_pct),
                    _euro_str(proc.vorprodukt_eingang),
                    _euro_str(proc.ausschuss_zuschlag),
                    _euro_str(proc.kosten_nach_ausbeute),
                    _euro_str(proc.fgk_basis),
                    _pct_str(proc.fgk_pct),
                    _euro_str(proc.fgk_betrag),
                    _euro_str(proc.zwischensumme),
                ]
            )

    selbstkosten = _float_from(ergebnis, "selbstkosten")
    land_label = ""
    if detail.land_code or detail.land_name:
        land_label = f"{detail.land_code or ''} – {detail.land_name or ''}".strip(" –")
    werk_label = ""
    if detail.werk_code or detail.werk_name:
        werk_label = f"{detail.werk_code or ''} – {detail.werk_name or ''}".strip(" –")
    return BaugruppeExportData(
        company_name=settings.COMPANY_NAME,
        assembly_id=obj.id,
        name=obj.name,
        teilenummer=obj.teilenummer,
        kunde=detail.customer_name or obj.kunde,
        projekt=detail.project_name or obj.projekt,
        jahresstueckzahl=jahresstueckzahl,
        created_at=obj.created_at,
        updated_at=obj.updated_at,
        einzelteile=ExportTable(
            "Einzelteile / PART-Detail",
            [
                "Bezeichnung",
                "Teilenummer",
                "Menge",
                "Kostenbasis",
                "Material",
                "Materialpreis",
                "Netto-Gewicht",
                "Schussgewicht",
                "Material direkt",
                "Mat.-Ausschuss %",
                "Material inkl. Ausschuss",
                "Nominierung",
                "MGK %",
                "Material-MGK",
                "Maschinenkosten",
                "Fertigungslohn",
                "Spritzguss-Ausgang",
                "Veredelung direkt vor Ausschuss",
                "FGK-Basis",
                "FGK %",
                "FGK",
                "Herstellkosten",
                "Zwischensumme",
                "Hinweise",
            ]
            if detail.parts
            else ["Bezeichnung", "Teilenummer", "Menge", "Einzelpreis", "Zwischensumme"],
            einzelteile_rows,
        ),
        kaufteile=ExportTable(
            "Kaufteile",
            [
                "Bezeichnung",
                "Artikelnummer",
                "Lieferant",
                "Menge",
                "Einkaufspreis",
                "Nominierung",
                "MGK %",
                "Kaufteil-MGK",
                "Preis inkl. MGK",
                "Zwischensumme",
                "Hinweise",
            ]
            if detail.purchased
            else ["Bezeichnung", "Lieferant", "Menge", "Einzelpreis", "Zwischensumme"],
            kaufteile_rows,
        ),
        veredelung=ExportTable(
            "ASSY / Prozesskette",
            [
                "Reihenfolge",
                "Bezeichnung",
                "Lohn",
                "Maschine",
                "Verbrauch",
                "Direkt vor Ausschuss",
                "Ausschuss %",
                "Ausbeute %",
                "Vorprodukt",
                "Ausschusszuschlag",
                "Nach Ausbeute",
                "FGK-Basis",
                "FGK %",
                "FGK",
                "Zwischensumme",
            ]
            if detail.processes
            else ["Reihenfolge", "Bezeichnung", "Kosten/St.", "Faktor", "Zwischensumme"],
            veredelung_rows,
        ),
        investitionen=investitionen,
        einzelteile_gesamt=overview["einzelteilkosten"],
        kaufteile_gesamt=overview["kaufteilkosten"],
        veredelung_gesamt=overview["veredelungskosten"],
        baugruppenpreis_je_stueck=endpreis,
        jahresumsatz=jahresumsatz,
        export_date=export_date,
        structure_version=obj.structure_version,
        status=obj.status or "",
        bom=ExportTable(
            "BOM / Komponentenübersicht",
            ["Typ", "Bezeichnung", "Teilenummer", "Menge", "Einzelpreis", "Zwischensumme"],
            bom_rows,
        ),
        zuschlagssaetze=ExportTable(
            "Zuschlagssätze",
            ["Bezeichnung", "Satz", "Betrag"],
            markup_rows,
        ),
        kosten_aufstellung=kosten_aufstellung,
        herstellkosten=overview["herstellkosten"],
        vvgk=overview["vvgk"],
        gewinn=overview["gewinn"],
        skonto=skonto,
        nettoverkaufspreis=overview["nettoverkaufspreis"],
        gesamtergebnis=overview["gesamtsumme"],
        program=detail.program_name or "",
        selbstkosten=selbstkosten,
        detail=detail,
        land=land_label,
        werk=werk_label,
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
    status: str | None = None,
    date_from=None,
    date_to=None,
    kalkulationsart: str | None = None,
) -> DashboardExportData:
    sg_rows, bg_rows, inv_rows = _load_dashboard_sources(db)
    summary = build_dashboard_summary(
        sg_rows,
        bg_rows,
        inv_rows,
        project=project,
        customer=customer,
        status=status,
        date_from=date_from,
        date_to=date_to,
        kalkulationsart=kalkulationsart,
    )
    kpis = summary["kpis"]
    has_data = bool(summary.get("has_data")) or any(
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
        kpi_row("Einzelteilkalkulationen", "anzahl_spritzguss_kalkulationen"),
        kpi_row("Anzahl Baugruppen", "anzahl_baugruppen"),
        kpi_row("Ø Endpreis je Einzelteil", "durchschnitt_endpreis_einzelteil", avg=True),
        kpi_row("Ø Baugruppenpreis je Stück", "durchschnitt_baugruppenpreis", avg=True),
        kpi_row("Ø Preis pro Stück", "durchschnitt_preis_pro_stueck", avg=True),
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
        [
            "Name",
            "Teilenummer",
            "Kunde",
            "Projekt",
            "Status",
            "Preis/St.",
            "Jahresstückzahl",
            "Jahresumsatz",
        ],
        [
            [
                r["name"],
                r["teilenummer"],
                r["kunde"],
                r["projekt"],
                r.get("status") or "",
                _euro_str(r.get("preis_je_stueck")),
                str(r["jahresstueckzahl"]),
                _euro_str(r.get("jahresumsatz")),
            ]
            for r in summary["assemblies"]
        ],
    )

    investments = ExportTable(
        "Investitionen",
        [
            "Bezeichnung",
            "Typ",
            "Betrag",
            "Projekt",
            "Lieferant",
            "Status",
            "Bestelldatum",
            "Liefertermin",
            "Amortisationsvolumen",
            "Kostenanteil/Teil",
            "Hinweis",
        ],
        [
            [
                r["bezeichnung"],
                r["typ"],
                _euro_str(r["betrag"]),
                r["projekt"],
                r.get("lieferant") or "",
                r["status"],
                str(r.get("bestelldatum") or ""),
                str(r.get("liefertermin") or ""),
                str(r.get("amortisationsvolumen") or ""),
                _euro_str(r.get("kostenanteil_pro_teil")),
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
        empty_message=summary.get("empty_message")
        or (None if has_data else "Keine Daten für die gewählten Filter vorhanden."),
        filter_status=status,
        filter_date_from=str(date_from) if date_from else None,
        filter_date_to=str(date_to) if date_to else None,
        filter_kalkulationsart=kalkulationsart,
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
