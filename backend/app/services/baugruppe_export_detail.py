"""Detaillierte Baugruppen-Kalkulationsdaten für Excel-/PDF-Export.

Lädt referenzierte Spritzguss-/Kaufteil-/Prozess-Stammdaten und rechnet Details
live nach (ohne DB-Mutation). Unterstützt assembly_positions und Legacy-Zuordnungen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe
from app.models.kaufteil import Kaufteil
from app.models.material import Material
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.services.assembly_calculation import (
    MarkupRates,
    PositionCalcInput,
    calculate_assembly,
)
from app.services.assembly_structure_service import (
    build_legacy_synthetic_items,
    load_positions,
)
from app.services.central_markup_rates import (
    CentralMarkupRates,
    CentralMarkupRatesError,
    load_central_markup_rates,
)
from app.services.dashboard import parse_json_dict
from app.services.project_volume_service import average_jahresstueckzahl_for_project
from app.services.spritzguss_gesamt_kalkulation import (
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class AssumptionRow:
    bezeichnung: str
    satz_prozent: float | None
    kostenbasis: str
    hinweis: str = ""
    betrag: float | None = None


@dataclass
class PartProcessStepDetail:
    reihenfolge: int
    bezeichnung: str
    veredelungsart: str
    lohnkosten: float
    maschinenkosten: float
    verbrauchskosten: float
    kosten_vor_ausschuss: float
    ausschussquote_pct: float
    ausbeute_pct: float
    vorprodukt_eingang: float
    ausschuss_zuschlag: float
    kosten_nach_ausbeute: float
    mengenfaktor: float


@dataclass
class PartDetail:
    position_id: int | None
    sequence: int
    bezeichnung: str
    teilenummer: str
    menge: float
    price_basis: str
    material_name: str | None
    materialpreis_pro_kg: float | None
    teilegewicht_netto_g: float | None
    schussgewicht_g: float | None
    materialkosten: float | None
    material_ausschussquote_pct: float | None
    materialkosten_inkl_ausschuss: float | None
    material_nominierung: str | None
    mgk_pct: float | None
    material_mgk: float | None
    maschinenkosten: float | None
    fertigungslohn: float | None
    spritzguss_ausgang: float | None
    veredelung_direkt_vor: float | None
    fgk_basis: float | None
    fgk_pct: float | None
    fgk_betrag: float | None
    herstellkosten: float
    zwischensumme: float
    process_steps: list[PartProcessStepDetail] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    legacy: bool = False
    sheet_slug: str = ""


@dataclass
class PurchasedDetail:
    position_id: int | None
    sequence: int
    bezeichnung: str
    artikelnummer: str
    lieferant: str
    menge: float
    einkaufspreis: float
    nominierung: str | None
    mgk_pct: float | None
    kaufteil_mgk: float
    preis_inkl_mgk: float
    zwischensumme: float
    hinweise: list[str] = field(default_factory=list)
    legacy: bool = False


@dataclass
class AssyProcessDetail:
    position_id: int | None
    sequence: int
    bezeichnung: str
    lohnkosten: float | None
    maschinenkosten: float | None
    verbrauchskosten: float | None
    kosten_vor_ausschuss: float
    ausschussquote_pct: float
    ausbeute_pct: float
    vorprodukt_eingang: float
    ausschuss_zuschlag: float
    kosten_nach_ausbeute: float
    fgk_basis: float | None
    fgk_pct: float | None
    fgk_betrag: float | None
    zwischensumme: float
    vorprodukt_komponenten: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)


@dataclass
class UeberleitungLine:
    label: str
    amount: float | None
    basis: str = ""
    highlight: bool = False


@dataclass
class BaugruppeDetailKalkulation:
    program_name: str | None
    customer_name: str | None
    project_name: str | None
    assumptions: list[AssumptionRow]
    parts: list[PartDetail]
    purchased: list[PurchasedDetail]
    processes: list[AssyProcessDetail]
    ueberleitung: list[UeberleitungLine]
    warnings: list[str] = field(default_factory=list)
    live_endpreis: float | None = None
    live_herstellkosten: float | None = None
    live_vvgk: float | None = None
    live_gewinn: float | None = None
    live_skonto: float | None = None
    live_netto: float | None = None
    live_selbstkosten: float | None = None
    jahresstueckzahl: int | None = None
    jahresumsatz: float | None = None
    jahresstueckzahl_hinweis: str = ""
    positions_source: str = "assembly_positions"


def excel_safe_sheet_name(raw: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\\/*?:\[\]]", "", raw).strip() or "Blatt"
    cleaned = cleaned[:31]
    candidate = cleaned
    n = 2
    while candidate in used:
        suffix = f"_{n}"
        candidate = (cleaned[: 31 - len(suffix)] + suffix)[:31]
        n += 1
    used.add(candidate)
    return candidate


def _slug(name: str) -> str:
    text_val = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß]+", "_", name).strip("_")
    return text_val[:24] or "Teil"


def _resolve_hierarchy(db: Session, obj: Baugruppe) -> tuple[str | None, str | None, str | None]:
    project_id = obj.project_id or obj.linked_project_id
    if not project_id:
        return obj.kunde or None, None, obj.projekt or None
    try:
        row = db.execute(
            text(
                """
                SELECT p.name AS project_name, pr.name AS program_name, c.name AS customer_name
                FROM projects p
                LEFT JOIN programs pr ON pr.id = p.program_id
                LEFT JOIN customers c ON c.id = pr.customer_id
                WHERE p.id = :pid
                """
            ),
            {"pid": project_id},
        ).first()
    except Exception:
        return obj.kunde or None, None, obj.projekt or None
    if not row:
        return obj.kunde or None, None, obj.projekt or None
    return (
        (row[2] if row[2] else obj.kunde) or None,
        row[1] or None,
        (row[0] if row[0] else obj.projekt) or None,
    )


def _load_rates(db: Session) -> tuple[CentralMarkupRates | None, list[str]]:
    try:
        return load_central_markup_rates(db), []
    except CentralMarkupRatesError as exc:
        return None, [str(exc)]


def _resolve_jahresstueckzahl(db: Session, obj: Baugruppe) -> tuple[int, str]:
    """Projektvolumen hat Vorrang; sonst gespeicherter Baugruppenwert."""
    stored = int(obj.jahresstueckzahl or 0)
    project_id = obj.project_id or obj.linked_project_id
    if not project_id:
        return stored, "Jahresstückzahl aus Baugruppe (kein Projekt verknüpft)" if stored else (
            "Jahresstückzahl fehlt (kein Projekt / kein Volumen)"
        )
    try:
        avg = average_jahresstueckzahl_for_project(db, int(project_id))
    except Exception:
        return stored, "Jahresstückzahl aus Baugruppe (Projektvolumen nicht lesbar)"
    if avg.has_volumes and avg.jahresstueckzahl is not None:
        return int(avg.jahresstueckzahl), "Jahresstückzahl aus Projektvolumen (Durchschnitt)"
    if stored > 0:
        return stored, "Jahresstückzahl aus Baugruppe (Projekt ohne Volumenjahre)"
    return 0, "Jahresstückzahl 0 – weder Baugruppe noch Projektvolumen"


def _positions_for_export(db: Session, obj: Baugruppe) -> tuple[list[Any], str]:
    positions = [p for p in load_positions(db, obj.id) if getattr(p, "active", True)]
    if positions:
        return positions, "assembly_positions"

    if not getattr(obj, "legacy_mode", False):
        return [], "empty"

    try:
        items = build_legacy_synthetic_items(db, obj.id)
    except Exception:
        return [], "empty"
    if not items:
        return [], "empty"

    synthetic: list[Any] = []
    for index, item in enumerate(items, start=1):
        snap = item.snapshots
        synthetic.append(
            SimpleNamespace(
                id=-(item.legacy_row_id or index),
                sequence=index,
                active=True,
                position_type=item.position_type,
                quantity=float(item.quantity or 1),
                quantity_factor=float(item.quantity_factor or 1),
                price_basis=item.price_basis
                or ("COST" if item.position_type == "PART" else None),
                part_calculation_id=item.part_calculation_id,
                purchased_part_id=item.purchased_part_id,
                finishing_step_id=item.finishing_step_id,
                child_assembly_id=None,
                cost_snapshot=getattr(snap, "cost_snapshot", None) if snap else None,
                price_snapshot=getattr(snap, "price_snapshot", None) if snap else None,
                name_snapshot=(getattr(snap, "name_snapshot", None) or "") if snap else "",
                part_number_snapshot=(getattr(snap, "part_number_snapshot", None) or "")
                if snap
                else "",
                supplier_snapshot=(getattr(snap, "supplier_snapshot", None) or "") if snap else "",
                label=None,
            )
        )
    return synthetic, "legacy_synthetic"


def _empty_part(
    pos: Any,
    *,
    menge: float,
    hk: float,
    zw: float,
    hints: list[str],
    calc: SpritzgussKalkulation | None = None,
    rates: CentralMarkupRates | None = None,
    nominierung: str | None = None,
) -> PartDetail:
    return PartDetail(
        position_id=getattr(pos, "id", None),
        sequence=int(pos.sequence),
        bezeichnung=(calc.teilebezeichnung if calc else None)
        or pos.name_snapshot
        or pos.label
        or "PART",
        teilenummer=(calc.teilenummer if calc else None) or pos.part_number_snapshot or "",
        menge=menge,
        price_basis=pos.price_basis or "COST",
        material_name=None,
        materialpreis_pro_kg=float(calc.materialpreis_pro_kg) if calc else None,
        teilegewicht_netto_g=float(calc.teilegewicht_netto_g) if calc else None,
        schussgewicht_g=float(calc.schussgewicht_g) if calc else None,
        materialkosten=None,
        material_ausschussquote_pct=float(calc.ausschussquote_pct) if calc else None,
        materialkosten_inkl_ausschuss=None,
        material_nominierung=nominierung,
        mgk_pct=None,
        material_mgk=None,
        maschinenkosten=None,
        fertigungslohn=None,
        spritzguss_ausgang=None,
        veredelung_direkt_vor=None,
        fgk_basis=None,
        fgk_pct=rates.fgk_pct if rates else None,
        fgk_betrag=None,
        herstellkosten=hk,
        zwischensumme=zw,
        hinweise=hints,
        legacy=True,
        sheet_slug=_slug(
            (calc.teilebezeichnung if calc else None) or pos.name_snapshot or "PART"
        ),
    )


def _part_detail_from_calc(
    db: Session,
    pos: Any,
    rates: CentralMarkupRates | None,
    ergebnis_line: dict | None,
) -> PartDetail:
    menge = float(pos.quantity or 1)
    hints: list[str] = []
    if pos.price_basis == "SALES_PRICE":
        hints.append(
            "price_basis=SALES_PRICE: Risiko doppelter Zuschläge – Assembly nutzt Verkaufspreis."
        )
    if pos.price_basis == "COST":
        hints.append("Kostenbasis COST: keine erneute SG&A/Gewinn-Belastung in der Baugruppe.")

    hk = float(pos.cost_snapshot or 0)
    if ergebnis_line and ergebnis_line.get("einzelpreis") is not None:
        hk = float(ergebnis_line["einzelpreis"])
    zw = _money(hk * menge)
    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])

    if not pos.part_calculation_id:
        hints.append("Live-Detail nicht verfügbar (fehlende Spritzguss-Kalkulation).")
        return _empty_part(pos, menge=menge, hk=hk, zw=zw, hints=hints)

    calc = db.get(SpritzgussKalkulation, pos.part_calculation_id)
    if not calc:
        hints.append(f"Spritzguss-Kalkulation {pos.part_calculation_id} fehlt.")
        return _empty_part(pos, menge=menge, hk=hk, zw=zw, hints=hints)

    if rates is None:
        hints.append("Zentrale Zuschlagssätze fehlen – Detail mit gespeicherten Sätzen berechnet.")

    nominierung = getattr(calc, "material_nominierung", None)
    mgk_pct: float | None = None
    if rates is not None:
        try:
            mgk_pct = rates.mgk_pct_for_nominierung(
                nominierung, kontext=f"Material {calc.teilebezeichnung}"
            )
        except CentralMarkupRatesError as exc:
            hints.append(str(exc))
            mgk_pct = None
    if mgk_pct is None:
        # Weiterrechnen mit gespeichertem Satz oder 0, damit Prozesskette nicht leer bleibt
        mgk_pct = float(calc.mgk_pct or 0)
        if not nominierung:
            hints.append("Material-Nominierung fehlt – MGK aus gespeichertem Satz / 0 %.")
        else:
            hints.append(
                f"MGK-Satz aus Stammdaten nicht auflösbar – gespeicherter Satz {mgk_pct} % verwendet."
            )

    fgk_pct = float(rates.fgk_pct) if rates else float(calc.fgk_pct or 0)
    vvgk_pct = float(rates.vvgk_pct) if rates else 0.0
    gewinn_pct = float(rates.gewinn_pct) if rates else 0.0
    skonto_pct = float(rates.skonto_pct) if rates else 0.0

    material_name = None
    if getattr(calc, "material_id", None):
        mat = db.get(Material, calc.material_id)
        if mat:
            material_name = mat.bezeichnung

    sg_input = SpritzgussInput(
        teilegewicht_netto_g=calc.teilegewicht_netto_g,
        materialpreis_pro_kg=calc.materialpreis_pro_kg,
        ausschussquote_pct=calc.ausschussquote_pct,
        mgk_pct=mgk_pct,
        material_nominierung=nominierung if nominierung in ("selbstnominiert", "oem_nominiert") else None,  # type: ignore[arg-type]
        zykluszeit_s=calc.zykluszeit_s,
        maschinenstundensatz=calc.maschinenstundensatz,
        kavitaeten=calc.kavitaeten,
        lohnstundensatz=calc.lohnstundensatz,
        fgk_pct=fgk_pct,
        werkzeugkosten_eur=calc.werkzeugkosten_eur or 0,
        werkzeug_abrechnungsart=calc.werkzeug_abrechnungsart or "einmalzahlung",  # type: ignore[arg-type]
        amortisationsvolumen=calc.amortisationsvolumen,
        vvgk_pct=vvgk_pct,
        gewinn_pct=gewinn_pct,
        skonto_pct=skonto_pct,
    )
    sg = berechne_spritzguss(sg_input)

    veredelung_eingaben: list[VeredelungSchrittEingabe] = []
    step_direct: list[tuple[Any, Any, Any]] = []
    for zuordnung in db.scalars(
        select(SpritzgussVeredelungZuordnung)
        .where(SpritzgussVeredelungZuordnung.kalkulation_id == calc.id)
        .order_by(SpritzgussVeredelungZuordnung.reihenfolge)
    ).all():
        row = db.execute(
            text(
                "SELECT bezeichnung, veredelungsart, taktzeit_s, anzahl_mitarbeiter, "
                "lohnstundensatz, maschinenstundensatz, verbrauchskosten_je_stueck, "
                "ausschussquote_pct, reihenfolge FROM veredelungsschritte WHERE id = :id"
            ),
            {"id": zuordnung.veredelungsschritt_id},
        ).first()
        if not row:
            continue
        # Maschinenstundensatz kann NULL sein
        masch_satz = float(row[5] if row[5] is not None else 0)
        vk = berechne_veredelung(
            VeredelungInput(
                taktzeit_s=row[2],
                anzahl_mitarbeiter=row[3],
                lohnstundensatz=row[4],
                maschinenstundensatz=masch_satz,
                verbrauchskosten_je_stueck=row[6],
                ausschussquote_pct=row[7],
                fgk_pct=0,
                reihenfolge=row[8],
            )
        )
        eingabe = VeredelungSchrittEingabe(
            veredelungsschritt_id=zuordnung.veredelungsschritt_id,
            bezeichnung=row[0],
            veredelungsart=row[1],
            reihenfolge=zuordnung.reihenfolge,
            aktiv=zuordnung.aktiv,
            mengenfaktor=zuordnung.mengenfaktor,
            kosten_inkl_ausschuss=vk.kosten_inkl_ausschuss,
            kosten_vor_ausschuss=vk.kosten_vor_ausschuss,
            ausschussquote_pct=float(row[7]),
        )
        veredelung_eingaben.append(eingabe)
        step_direct.append((row, vk, zuordnung))

    if not veredelung_eingaben:
        hints.append("Keine Spritzguss-Veredelungszuordnung – nur Spritzguss-Detail.")

    gesamt = berechne_gesamt(
        sg.to_dict(),
        veredelung_eingaben,
        fgk_pct=fgk_pct,
        vvgk_pct=0,
        gewinn_pct=0,
        skonto_pct=0,
    )
    herstell = float(gesamt.gesamte_herstellkosten)

    process_steps: list[PartProcessStepDetail] = []
    for ergebnis_step in gesamt.veredelung_schritte:
        if not ergebnis_step.aktiv:
            continue
        match = next(
            (
                (row, vk, zu)
                for row, vk, zu in step_direct
                if zu.veredelungsschritt_id == ergebnis_step.veredelungsschritt_id
            ),
            None,
        )
        if match is None:
            continue
        row, vk, zuordnung = match
        quote = float(ergebnis_step.ausschussquote_pct)
        faktor = float(zuordnung.mengenfaktor)
        process_steps.append(
            PartProcessStepDetail(
                reihenfolge=ergebnis_step.reihenfolge,
                bezeichnung=ergebnis_step.bezeichnung,
                veredelungsart=ergebnis_step.veredelungsart,
                lohnkosten=_money(vk.lohnkosten_je_stueck * faktor),
                maschinenkosten=_money(vk.maschinenkosten_je_stueck * faktor),
                verbrauchskosten=_money(vk.verbrauchskosten_je_stueck * faktor),
                kosten_vor_ausschuss=float(ergebnis_step.kosten_vor_ausschuss),
                ausschussquote_pct=quote,
                ausbeute_pct=_money(100.0 - quote),
                vorprodukt_eingang=float(ergebnis_step.vorprodukt_eingang),
                ausschuss_zuschlag=float(ergebnis_step.ausschuss_zuschlag),
                kosten_nach_ausbeute=float(ergebnis_step.kosten_nach_ausbeute),
                mengenfaktor=faktor,
            )
        )

    verd_vor = _money(sum(s.kosten_vor_ausschuss for s in process_steps))
    spritzguss_ausgang = _money(
        float(sg.materialkosten_inkl_ausschuss)
        + float(sg.materialgemeinkosten)
        + float(sg.maschinenkosten)
        + float(sg.fertigungslohn)
    )

    if ergebnis_line and ergebnis_line.get("einzelpreis") is not None:
        herstell = float(ergebnis_line["einzelpreis"])
    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])
    else:
        zw = _money(herstell * menge)

    return PartDetail(
        position_id=getattr(pos, "id", None),
        sequence=int(pos.sequence),
        bezeichnung=calc.teilebezeichnung or pos.name_snapshot or "PART",
        teilenummer=calc.teilenummer or pos.part_number_snapshot or "",
        menge=menge,
        price_basis=pos.price_basis or "COST",
        material_name=material_name,
        materialpreis_pro_kg=float(calc.materialpreis_pro_kg),
        teilegewicht_netto_g=float(calc.teilegewicht_netto_g),
        schussgewicht_g=float(calc.schussgewicht_g or 0),
        materialkosten=float(sg.materialkosten),
        material_ausschussquote_pct=float(calc.ausschussquote_pct),
        materialkosten_inkl_ausschuss=float(sg.materialkosten_inkl_ausschuss),
        material_nominierung=nominierung,
        mgk_pct=mgk_pct,
        material_mgk=float(sg.materialgemeinkosten),
        maschinenkosten=float(sg.maschinenkosten),
        fertigungslohn=float(sg.fertigungslohn),
        spritzguss_ausgang=spritzguss_ausgang,
        veredelung_direkt_vor=verd_vor,
        fgk_basis=float(gesamt.fgk_basis),
        fgk_pct=float(gesamt.applied_fgk_pct),
        fgk_betrag=float(gesamt.fertigungsgemeinkosten),
        herstellkosten=herstell,
        zwischensumme=zw,
        process_steps=process_steps,
        hinweise=hints,
        sheet_slug=_slug(calc.teilebezeichnung or pos.name_snapshot or "PART"),
    )


def _purchased_detail(
    db: Session,
    pos: Any,
    rates: CentralMarkupRates | None,
    ergebnis_line: dict | None,
) -> PurchasedDetail:
    menge = float(pos.quantity or 1)
    hints: list[str] = []
    kt = db.get(Kaufteil, pos.purchased_part_id) if pos.purchased_part_id else None
    if not kt:
        preis = float(pos.price_snapshot or pos.cost_snapshot or 0)
        return PurchasedDetail(
            position_id=getattr(pos, "id", None),
            sequence=int(pos.sequence),
            bezeichnung=pos.name_snapshot or "Kaufteil",
            artikelnummer="",
            lieferant=pos.supplier_snapshot or "",
            menge=menge,
            einkaufspreis=float(pos.cost_snapshot or 0),
            nominierung=None,
            mgk_pct=None,
            kaufteil_mgk=_money(preis - float(pos.cost_snapshot or 0)),
            preis_inkl_mgk=preis,
            zwischensumme=_money(preis * menge),
            hinweise=["Kaufteil-Stammdatensatz fehlt – Snapshot verwendet."],
            legacy=True,
        )

    einkauf = float(kt.preis)
    nominierung = kt.nominierung
    mgk_pct = None
    if rates is None:
        hints.append("Zentrale Zuschlagssätze fehlen.")
    else:
        try:
            mgk_pct = rates.mgk_pct_for_nominierung(
                nominierung, kontext=f"Kaufteil {kt.bezeichnung}"
            )
        except CentralMarkupRatesError as exc:
            hints.append(str(exc))

    if mgk_pct is None:
        inkl = float(pos.price_snapshot or einkauf)
        mgk_betrag = _money(inkl - einkauf)
        if not nominierung:
            hints.append("Kaufteil-Nominierung fehlt – kein zentraler MGK-Satz anwendbar.")
    else:
        inkl = _money(einkauf * (1 + mgk_pct / 100.0))
        mgk_betrag = _money(inkl - einkauf)

    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])
    else:
        zw = _money(inkl * menge)

    return PurchasedDetail(
        position_id=getattr(pos, "id", None),
        sequence=int(pos.sequence),
        bezeichnung=kt.bezeichnung,
        artikelnummer=kt.artikelnummer or "",
        lieferant=kt.lieferant or pos.supplier_snapshot or "",
        menge=menge,
        einkaufspreis=einkauf,
        nominierung=nominierung,
        mgk_pct=mgk_pct,
        kaufteil_mgk=mgk_betrag,
        preis_inkl_mgk=inkl,
        zwischensumme=zw,
        hinweise=hints,
    )


def _yield_for_process(
    pos: Any,
    yield_by_pos: dict[int, dict],
    yield_by_name: dict[str, dict],
) -> dict:
    pid = getattr(pos, "id", None)
    if pid is not None and pid in yield_by_pos:
        return yield_by_pos[pid]
    name = (pos.name_snapshot or pos.label or "").strip().casefold()
    if name and name in yield_by_name:
        return yield_by_name[name]
    return {}


def _ensure_process_yields(
    db: Session,
    ergebnis: dict,
    positions: list[Any],
    rates: CentralMarkupRates | None,
) -> tuple[dict[int, dict], dict[str, dict], float | None, float | None]:
    """Nutzt gespeicherte Yield-Details oder berechnet sie aus Snapshots nach."""
    yield_by_pos = {
        d.get("position_id"): d
        for d in (ergebnis.get("process_yield_details") or [])
        if isinstance(d, dict) and d.get("position_id") is not None
    }
    yield_by_name = {
        str(d.get("name_snapshot") or d.get("label") or "").strip().casefold(): d
        for d in (ergebnis.get("process_yield_details") or [])
        if isinstance(d, dict) and (d.get("name_snapshot") or d.get("label"))
    }
    fgk_basis = _float(ergebnis.get("fgk_basis"))
    fgk_betrag = _float(ergebnis.get("fertigungsgemeinkosten"))

    has_process = any(
        p.position_type == "PROCESS" and getattr(p, "active", True) for p in positions
    )
    if has_process and not yield_by_pos and not yield_by_name and rates is not None:
        calc_inputs: list[PositionCalcInput] = []
        for pos in sorted(positions, key=lambda p: p.sequence):
            if not getattr(pos, "active", True):
                continue
            quote = None
            before = None
            if pos.position_type == "PROCESS" and pos.finishing_step_id:
                row = db.execute(
                    text(
                        "SELECT ausschussquote_pct, taktzeit_s, anzahl_mitarbeiter, "
                        "lohnstundensatz, maschinenstundensatz, verbrauchskosten_je_stueck, "
                        "reihenfolge FROM veredelungsschritte WHERE id = :id"
                    ),
                    {"id": pos.finishing_step_id},
                ).first()
                if row:
                    quote = float(row[0])
                    vk = berechne_veredelung(
                        VeredelungInput(
                            taktzeit_s=row[1],
                            anzahl_mitarbeiter=row[2],
                            lohnstundensatz=row[3],
                            maschinenstundensatz=float(row[4] if row[4] is not None else 0),
                            verbrauchskosten_je_stueck=row[5],
                            ausschussquote_pct=quote,
                            fgk_pct=0,
                            reihenfolge=row[6],
                        )
                    )
                    before = float(vk.kosten_vor_ausschuss) * float(pos.quantity_factor or 1)
            calc_inputs.append(
                PositionCalcInput(
                    position_id=getattr(pos, "id", None),
                    position_type=pos.position_type,
                    sequence=int(pos.sequence),
                    quantity=float(pos.quantity or 1),
                    quantity_factor=float(pos.quantity_factor or 1),
                    price_basis=pos.price_basis,
                    active=True,
                    label=pos.label,
                    name_snapshot=pos.name_snapshot or "",
                    cost_snapshot=pos.cost_snapshot if pos.position_type != "PROCESS" else before,
                    price_snapshot=pos.price_snapshot,
                    cost_before_scrap=before if pos.position_type == "PROCESS" else None,
                    ausschussquote_pct=quote if pos.position_type == "PROCESS" else None,
                )
            )
        try:
            result = calculate_assembly(
                assembly_type="TOP_LEVEL",
                positions=calc_inputs,
                markup_rates=MarkupRates(
                    fgk_pct=rates.fgk_pct,
                    vvgk_pct=rates.vvgk_pct,
                    gewinn_pct=rates.gewinn_pct,
                    skonto_pct=rates.skonto_pct,
                ),
            )
            for d in result.process_yield_details or []:
                payload = {
                    "position_id": d.position_id,
                    "label": d.label,
                    "name_snapshot": d.name_snapshot,
                    "ausschussquote_pct": d.ausschussquote_pct,
                    "vorprodukt_eingang": d.vorprodukt_eingang,
                    "process_kosten_vor_ausschuss": d.process_kosten_vor_ausschuss,
                    "ausschuss_zuschlag": d.ausschuss_zuschlag,
                    "kosten_nach_ausbeute": d.kosten_nach_ausbeute,
                }
                if d.position_id is not None:
                    yield_by_pos[d.position_id] = payload
                if d.name_snapshot:
                    yield_by_name[d.name_snapshot.strip().casefold()] = payload
            if result.fgk_basis is not None:
                fgk_basis = result.fgk_basis
            if result.fertigungsgemeinkosten is not None:
                fgk_betrag = result.fertigungsgemeinkosten
        except Exception:
            pass

    return yield_by_pos, yield_by_name, fgk_basis, fgk_betrag


def _process_detail(
    db: Session,
    pos: Any,
    rates: CentralMarkupRates | None,
    yield_by_pos: dict[int, dict],
    yield_by_name: dict[str, dict],
    ergebnis_line: dict | None,
    assembly_fgk_basis: float | None,
    assembly_fgk: float | None,
    vorprodukt_labels: list[str],
) -> AssyProcessDetail:
    hints: list[str] = []
    yd = _yield_for_process(pos, yield_by_pos, yield_by_name)
    lohn = masch = verb = None
    vor = float(yd.get("process_kosten_vor_ausschuss") or 0)
    quote = float(yd.get("ausschussquote_pct") or 0)
    name = pos.name_snapshot or pos.label or "Prozess"

    if pos.finishing_step_id:
        row = db.execute(
            text(
                "SELECT bezeichnung, taktzeit_s, anzahl_mitarbeiter, lohnstundensatz, "
                "maschinenstundensatz, verbrauchskosten_je_stueck, ausschussquote_pct, "
                "reihenfolge FROM veredelungsschritte WHERE id = :id"
            ),
            {"id": pos.finishing_step_id},
        ).first()
        if row:
            masch_satz = float(row[4] if row[4] is not None else 0)
            vk = berechne_veredelung(
                VeredelungInput(
                    taktzeit_s=row[1],
                    anzahl_mitarbeiter=row[2],
                    lohnstundensatz=row[3],
                    maschinenstundensatz=masch_satz,
                    verbrauchskosten_je_stueck=row[5],
                    ausschussquote_pct=row[6],
                    fgk_pct=0,
                    reihenfolge=row[7],
                )
            )
            faktor = float(pos.quantity_factor or 1)
            lohn = _money(vk.lohnkosten_je_stueck * faktor)
            masch = _money(vk.maschinenkosten_je_stueck * faktor)
            verb = _money(vk.verbrauchskosten_je_stueck * faktor)
            vor = _money(vk.kosten_vor_ausschuss * faktor)
            quote = float(row[6])
            name = row[0]
        else:
            hints.append("Veredelungsschritt nicht gefunden.")

    vorprodukt = float(yd.get("vorprodukt_eingang") or 0)
    if vorprodukt <= 0 and vorprodukt_labels:
        # Fallback: Summe vorheriger Komponenten aus Aufrufkontext (wird gesetzt)
        pass
    nach = float(yd.get("kosten_nach_ausbeute") or 0)
    if nach <= 0 and (vorprodukt > 0 or vor > 0):
        ausbeute = max(0.0, 1.0 - quote / 100.0)
        nach = _money((vorprodukt + vor) / ausbeute) if ausbeute > 0 else _money(vorprodukt + vor)
    zuschlag = float(yd.get("ausschuss_zuschlag") or _money(nach - vorprodukt - vor))
    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])
    else:
        zw = _money(nach - vorprodukt)

    fgk_pct = rates.fgk_pct if rates else None
    fgk_betrag = None
    if rates and assembly_fgk_basis and assembly_fgk_basis > 0 and assembly_fgk is not None and vor:
        fgk_betrag = _money(assembly_fgk * (vor / assembly_fgk_basis))
    elif rates and vor:
        fgk_betrag = _money(vor * rates.fgk_pct / 100.0)

    return AssyProcessDetail(
        position_id=getattr(pos, "id", None),
        sequence=int(pos.sequence),
        bezeichnung=name,
        lohnkosten=lohn,
        maschinenkosten=masch,
        verbrauchskosten=verb,
        kosten_vor_ausschuss=vor,
        ausschussquote_pct=quote,
        ausbeute_pct=_money(100.0 - quote),
        vorprodukt_eingang=vorprodukt,
        ausschuss_zuschlag=zuschlag,
        kosten_nach_ausbeute=nach,
        fgk_basis=vor,
        fgk_pct=fgk_pct,
        fgk_betrag=fgk_betrag,
        zwischensumme=zw,
        vorprodukt_komponenten=list(vorprodukt_labels),
        hinweise=hints
        + [
            "ASSY-Ausschuss belastet alle Vorprodukte gemeinsam: "
            + (", ".join(vorprodukt_labels) if vorprodukt_labels else "alle bis dahin aufgelaufenen Kosten")
            + " plus direkte ASSY-Kosten (Ausbeutekette)."
        ],
    )


def _build_applied_assumptions(
    rates: CentralMarkupRates | None,
    ergebnis: dict,
    rate_warnings: list[str],
) -> list[AssumptionRow]:
    if rates is None:
        return [
            AssumptionRow(
                "Zentrale Zuschlagssätze",
                None,
                "–",
                rate_warnings[0] if rate_warnings else "fehlen",
                None,
            )
        ]
    rows = [
        AssumptionRow(
            "MGK selbstnominiert",
            rates.mgk_kaufteil_selbst_pct,
            "Material inkl. Ausschuss / Kaufteil-Einkaufspreis",
            betrag=None,
        ),
        AssumptionRow(
            "MGK OEM-nominiert",
            rates.mgk_kaufteil_oem_pct,
            "Material inkl. Ausschuss / Kaufteil-Einkaufspreis",
            betrag=None,
        ),
        AssumptionRow(
            "FGK",
            rates.fgk_pct if _float(ergebnis.get("applied_fgk_pct")) is None else _float(ergebnis.get("applied_fgk_pct")),
            "Maschinenkosten + Fertigungslohn + direkte Prozesskosten vor Ausschuss",
            betrag=_float(ergebnis.get("fertigungsgemeinkosten")),
        ),
        AssumptionRow(
            "SG&A / VVGK",
            rates.vvgk_pct if _float(ergebnis.get("applied_vvgk_pct")) is None else _float(ergebnis.get("applied_vvgk_pct")),
            "Herstellkosten",
            betrag=_float(ergebnis.get("vvgk")),
        ),
        AssumptionRow(
            "Profit / Gewinn",
            rates.gewinn_pct
            if _float(ergebnis.get("applied_gewinn_pct")) is None
            else _float(ergebnis.get("applied_gewinn_pct")),
            "Selbstkosten (HK + SG&A)",
            betrag=_float(ergebnis.get("gewinn")),
        ),
        AssumptionRow(
            "Skonto",
            rates.skonto_pct
            if _float(ergebnis.get("applied_skonto_pct")) is None
            else _float(ergebnis.get("applied_skonto_pct")),
            "Nettoverkaufspreis",
            betrag=_float(ergebnis.get("skonto")) if "skonto" in ergebnis else 0.0,
        ),
    ]
    # Wenn Beträge fehlen, aus Sätzen × Basis nachrechnen
    hk = _float(ergebnis.get("herstellkosten"))
    if hk is not None:
        if rows[3].betrag is None and rows[3].satz_prozent is not None:
            rows[3].betrag = _money(hk * rows[3].satz_prozent / 100.0)
        selbst = _float(ergebnis.get("selbstkosten"))
        if selbst is None and rows[3].betrag is not None:
            selbst = _money(hk + rows[3].betrag)
        if rows[4].betrag is None and selbst is not None and rows[4].satz_prozent is not None:
            rows[4].betrag = _money(selbst * rows[4].satz_prozent / 100.0)
        netto = _float(ergebnis.get("nettoverkaufspreis"))
        if netto is None and selbst is not None and rows[4].betrag is not None:
            netto = _money(selbst + rows[4].betrag)
        if rows[5].betrag is None and netto is not None and rows[5].satz_prozent is not None:
            rows[5].betrag = _money(netto * rows[5].satz_prozent / 100.0)
    fgk_b = _float(ergebnis.get("fgk_basis"))
    if rows[2].betrag is None and fgk_b is not None and rows[2].satz_prozent is not None:
        rows[2].betrag = _money(fgk_b * rows[2].satz_prozent / 100.0)
    return rows


def build_baugruppe_detail_kalkulation(db: Session, assembly_id: int) -> BaugruppeDetailKalkulation:
    obj = db.get(Baugruppe, assembly_id)
    if not obj:
        raise ValueError("Baugruppe nicht gefunden")

    ergebnis = parse_json_dict(obj.ergebnis) or {}
    customer_name, program_name, project_name = _resolve_hierarchy(db, obj)
    rates, rate_warnings = _load_rates(db)
    assumptions = _build_applied_assumptions(rates, ergebnis, rate_warnings)

    positions, positions_source = _positions_for_export(db, obj)
    if positions_source == "legacy_synthetic":
        rate_warnings.append(
            "Struktur aus Legacy-Zuordnungen (keine assembly_positions) – Detail live nachgerechnet."
        )

    lines_by_id = {
        p.get("position_id"): p
        for p in (ergebnis.get("positions") or [])
        if isinstance(p, dict) and p.get("position_id") is not None
    }
    # Fallback: Zeilen nach Name matchen (Legacy ohne position_id)
    lines_by_name = {
        str(p.get("name_snapshot") or p.get("bezeichnung") or "").strip().casefold(): p
        for p in (ergebnis.get("positions") or ergebnis.get("einzelteile") or [])
        if isinstance(p, dict)
    }

    yield_by_pos, yield_by_name, fgk_basis, fgk_betrag = _ensure_process_yields(
        db, ergebnis, positions, rates
    )

    parts: list[PartDetail] = []
    purchased: list[PurchasedDetail] = []
    processes: list[AssyProcessDetail] = []
    warnings = list(rate_warnings)
    vorprodukt_labels: list[str] = []

    for pos in sorted(positions, key=lambda p: p.sequence):
        if not getattr(pos, "active", True):
            continue
        line = lines_by_id.get(getattr(pos, "id", None))
        if line is None:
            key = (pos.name_snapshot or "").strip().casefold()
            line = lines_by_name.get(key)

        if pos.position_type == "PART":
            part = _part_detail_from_calc(db, pos, rates, line)
            parts.append(part)
            vorprodukt_labels.append(part.bezeichnung)
        elif pos.position_type == "PURCHASED_PART":
            kauf = _purchased_detail(db, pos, rates, line)
            purchased.append(kauf)
            vorprodukt_labels.append(kauf.bezeichnung)
        elif pos.position_type == "PROCESS":
            # ASSY: alle bisherigen Komponenten sind Vorprodukte
            proc = _process_detail(
                db,
                pos,
                rates,
                yield_by_pos,
                yield_by_name,
                line,
                fgk_basis,
                fgk_betrag,
                list(vorprodukt_labels),
            )
            # Wenn Yield fehlt: Vorprodukt aus Summe bisheriger Zwischensummen
            if proc.vorprodukt_eingang <= 0:
                vor_sum = _money(
                    sum(p.zwischensumme for p in parts)
                    + sum(k.zwischensumme for k in purchased)
                )
                proc.vorprodukt_eingang = vor_sum
                ausbeute = max(0.0, 1.0 - proc.ausschussquote_pct / 100.0)
                if ausbeute > 0:
                    proc.kosten_nach_ausbeute = _money(
                        (vor_sum + proc.kosten_vor_ausschuss) / ausbeute
                    )
                    proc.ausschuss_zuschlag = _money(
                        proc.kosten_nach_ausbeute - vor_sum - proc.kosten_vor_ausschuss
                    )
                    proc.zwischensumme = _money(proc.kosten_nach_ausbeute - vor_sum)
            processes.append(proc)
            vorprodukt_labels.append(proc.bezeichnung)
        elif pos.position_type == "SUBASSEMBLY":
            warnings.append(
                f"Unterbaugruppe '{pos.name_snapshot}' als Sammelposition – Detail siehe Kind-Export."
            )
            vorprodukt_labels.append(pos.name_snapshot or "Unterbaugruppe")

    for p in parts:
        warnings.extend(p.hinweise)
    for p in purchased:
        warnings.extend(p.hinweise)

    jsz, jsz_hinweis = _resolve_jahresstueckzahl(db, obj)
    endpreis = _float(ergebnis.get("endpreis_je_stueck")) or _float(
        ergebnis.get("baugruppenpreis_je_stueck")
    )
    # Immer aus aktuellem Endpreis × JSZ – kein veraltetes ergebnis.jahresumsatz
    jahresumsatz = _money(endpreis * jsz) if endpreis is not None else None

    ueberleitung = _build_ueberleitung(
        ergebnis, parts, purchased, processes, jsz=jsz, endpreis=endpreis, jahresumsatz=jahresumsatz
    )

    return BaugruppeDetailKalkulation(
        program_name=program_name,
        customer_name=customer_name,
        project_name=project_name,
        assumptions=assumptions,
        parts=parts,
        purchased=purchased,
        processes=processes,
        ueberleitung=ueberleitung,
        warnings=list(dict.fromkeys(warnings)),
        live_endpreis=endpreis,
        live_herstellkosten=_float(ergebnis.get("herstellkosten")),
        live_vvgk=_float(ergebnis.get("vvgk")),
        live_gewinn=_float(ergebnis.get("gewinn")),
        live_skonto=_float(ergebnis.get("skonto")) if "skonto" in ergebnis else 0.0,
        live_netto=_float(ergebnis.get("nettoverkaufspreis")),
        live_selbstkosten=_float(ergebnis.get("selbstkosten")),
        jahresstueckzahl=jsz,
        jahresumsatz=jahresumsatz,
        jahresstueckzahl_hinweis=jsz_hinweis,
        positions_source=positions_source,
    )


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_ueberleitung(
    ergebnis: dict,
    parts: list[PartDetail],
    purchased: list[PurchasedDetail],
    processes: list[AssyProcessDetail],
    *,
    jsz: int,
    endpreis: float | None,
    jahresumsatz: float | None,
) -> list[UeberleitungLine]:
    lines: list[UeberleitungLine] = []
    for part in parts:
        lines.append(
            UeberleitungLine(
                f"Einzelteil: {part.bezeichnung}",
                part.zwischensumme,
                f"Menge {part.menge} × HK {part.herstellkosten:.4f} ({part.price_basis})",
            )
        )
        if part.material_mgk is not None:
            lines.append(
                UeberleitungLine(
                    f"  └ Material-MGK {part.bezeichnung} (in HK enthalten)",
                    _money(part.material_mgk * part.menge),
                    f"{part.mgk_pct} % / Nominierung {part.material_nominierung or 'fehlend'}",
                )
            )
        for step in part.process_steps:
            lines.append(
                UeberleitungLine(
                    f"  └ {part.bezeichnung} / {step.bezeichnung} Ausschuss (in HK enthalten)",
                    step.ausschuss_zuschlag,
                    f"{step.ausschussquote_pct} % auf Vorprodukt {step.vorprodukt_eingang:.4f} "
                    f"+ Prozess {step.kosten_vor_ausschuss:.4f}",
                )
            )
        if part.fgk_betrag is not None:
            lines.append(
                UeberleitungLine(
                    f"  └ FGK {part.bezeichnung} (in HK enthalten)",
                    _money(part.fgk_betrag * part.menge),
                    f"{part.fgk_pct} % auf Basis {part.fgk_basis}",
                )
            )

    kauf_einkauf = 0.0
    kauf_mgk = 0.0
    for k in purchased:
        lines.append(
            UeberleitungLine(
                f"Kaufteil: {k.bezeichnung}",
                _money(k.einkaufspreis * k.menge),
                f"Einkauf × Menge {k.menge}",
            )
        )
        lines.append(
            UeberleitungLine(
                f"  └ Kaufteil-MGK {k.bezeichnung}",
                _money(k.kaufteil_mgk * k.menge),
                f"{k.mgk_pct if k.mgk_pct is not None else '–'} % "
                f"({k.nominierung or 'ohne Nominierung'})",
            )
        )
        kauf_einkauf += k.einkaufspreis * k.menge
        kauf_mgk += k.kaufteil_mgk * k.menge
    if purchased:
        lines.append(UeberleitungLine("Kaufteile Summe (Einkauf)", _money(kauf_einkauf), ""))
        lines.append(UeberleitungLine("Kaufteil-MGK Summe", _money(kauf_mgk), ""))

    for proc in processes:
        lines.append(
            UeberleitungLine(
                f"Prozess: {proc.bezeichnung} (direkt vor Ausschuss)",
                proc.kosten_vor_ausschuss,
                "Lohn + Maschine + Verbrauch",
            )
        )
        lines.append(
            UeberleitungLine(
                f"  └ Ausschuss {proc.bezeichnung} auf alle Vorprodukte",
                proc.ausschuss_zuschlag,
                f"{proc.ausschussquote_pct} % auf Vorprodukte {proc.vorprodukt_eingang:.4f} "
                f"[{', '.join(proc.vorprodukt_komponenten) or '–'}] + Prozess "
                f"{proc.kosten_vor_ausschuss:.4f}",
            )
        )

    hk = _float(ergebnis.get("herstellkosten"))
    fgk_b = _float(ergebnis.get("fgk_basis"))
    fgk = _float(ergebnis.get("fertigungsgemeinkosten"))
    vvgk = _float(ergebnis.get("vvgk"))
    selbst = _float(ergebnis.get("selbstkosten"))
    gewinn = _float(ergebnis.get("gewinn"))
    netto = _float(ergebnis.get("nettoverkaufspreis"))
    skonto = _float(ergebnis.get("skonto")) if "skonto" in ergebnis else 0.0

    # Nachrechnen wenn gespeicherte Werte fehlen
    if hk is None:
        hk = _money(
            sum(p.zwischensumme for p in parts)
            + sum(k.zwischensumme for k in purchased)
            + sum(pr.zwischensumme for pr in processes)
            + (fgk or 0)
        )
    if vvgk is None and hk is not None:
        pct = _float(ergebnis.get("applied_vvgk_pct"))
        if pct is not None:
            vvgk = _money(hk * pct / 100.0)
    if selbst is None and hk is not None and vvgk is not None:
        selbst = _money(hk + vvgk)
    if gewinn is None and selbst is not None:
        pct = _float(ergebnis.get("applied_gewinn_pct"))
        if pct is not None:
            gewinn = _money(selbst * pct / 100.0)
    if netto is None and selbst is not None and gewinn is not None:
        netto = _money(selbst + gewinn)
    if endpreis is None and netto is not None and skonto is not None:
        endpreis = _money(netto + skonto)

    lines.append(
        UeberleitungLine(
            "Gesamt-FGK-Basis (Baugruppen-Prozesse)",
            fgk_b,
            "Summe Prozesskosten vor Ausschuss",
        )
    )
    lines.append(
        UeberleitungLine(
            "Gesamt-FGK (Baugruppe)",
            fgk,
            f"{ergebnis.get('applied_fgk_pct', '–')} % auf FGK-Basis",
        )
    )
    lines.append(UeberleitungLine("Herstellkosten", hk, "Positionen inkl. Ausbeutekette + FGK", True))
    lines.append(
        UeberleitungLine(
            "SG&A / VVGK",
            vvgk,
            f"{ergebnis.get('applied_vvgk_pct', '–')} % auf Herstellkosten",
        )
    )
    lines.append(UeberleitungLine("Selbstkosten", selbst, "HK + SG&A"))
    lines.append(
        UeberleitungLine(
            "Profit / Gewinn",
            gewinn,
            f"{ergebnis.get('applied_gewinn_pct', '–')} % auf Selbstkosten",
        )
    )
    lines.append(UeberleitungLine("Nettoverkaufspreis", netto, "Selbstkosten + Profit"))
    lines.append(
        UeberleitungLine(
            "Skonto",
            skonto,
            f"{ergebnis.get('applied_skonto_pct', '–')} % auf Nettoverkaufspreis",
        )
    )
    lines.append(UeberleitungLine("Endpreis je Stück", endpreis, "Netto + Skonto", True))
    lines.append(
        UeberleitungLine(
            "Jahresumsatz",
            jahresumsatz if jahresumsatz is not None else (_money(endpreis * jsz) if endpreis else None),
            f"Endpreis × Jahresstückzahl {jsz}",
            True,
        )
    )
    return lines
