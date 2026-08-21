"""Detaillierte Baugruppen-Kalkulationsdaten für Excel-/PDF-Export.

Liest gespeicherte Assembly-Ergebnisse und rechnet PART-/Kaufteil-/Prozess-
Details live nach (ohne DB-Mutation), damit der Export fachlich nachrechenbar ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe
from app.models.kaufteil import Kaufteil
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.services.assembly_structure_service import load_positions
from app.services.central_markup_rates import (
    CentralMarkupRates,
    CentralMarkupRatesError,
    load_central_markup_rates,
)
from app.services.dashboard import parse_json_dict
from app.services.spritzguss_gesamt_kalkulation import (
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _pct(value: float | None) -> float | None:
    return None if value is None else float(value)


@dataclass
class AssumptionRow:
    bezeichnung: str
    satz_prozent: float | None
    kostenbasis: str
    hinweis: str = ""


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
    materialkosten: float | None
    material_ausschussquote_pct: float | None
    materialkosten_inkl_ausschuss: float | None
    material_nominierung: str | None
    mgk_pct: float | None
    material_mgk: float | None
    maschinenkosten: float | None
    fertigungslohn: float | None
    veredelung_direkt_vor: float | None
    fgk_basis: float | None
    fgk_pct: float | None
    fgk_betrag: float | None
    herstellkosten: float
    zwischensumme: float
    process_steps: list[PartProcessStepDetail] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    legacy: bool = False


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
    jahresstueckzahl: int | None = None
    jahresumsatz: float | None = None


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


def _part_detail_from_calc(
    db: Session,
    pos: AssemblyPosition,
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

    if not pos.part_calculation_id or rates is None:
        hints.append("Live-Detail nicht verfügbar (fehlende Kalkulation oder Zuschlagssätze).")
        return PartDetail(
            position_id=pos.id,
            sequence=pos.sequence,
            bezeichnung=pos.name_snapshot or pos.label or "PART",
            teilenummer=pos.part_number_snapshot or "",
            menge=menge,
            price_basis=pos.price_basis or "COST",
            materialkosten=None,
            material_ausschussquote_pct=None,
            materialkosten_inkl_ausschuss=None,
            material_nominierung=None,
            mgk_pct=None,
            material_mgk=None,
            maschinenkosten=None,
            fertigungslohn=None,
            veredelung_direkt_vor=None,
            fgk_basis=None,
            fgk_pct=None,
            fgk_betrag=None,
            herstellkosten=hk,
            zwischensumme=zw,
            hinweise=hints,
            legacy=True,
        )

    calc = db.get(SpritzgussKalkulation, pos.part_calculation_id)
    if not calc:
        hints.append(f"Spritzguss-Kalkulation {pos.part_calculation_id} fehlt.")
        return PartDetail(
            position_id=pos.id,
            sequence=pos.sequence,
            bezeichnung=pos.name_snapshot or "PART",
            teilenummer=pos.part_number_snapshot or "",
            menge=menge,
            price_basis=pos.price_basis or "COST",
            materialkosten=None,
            material_ausschussquote_pct=None,
            materialkosten_inkl_ausschuss=None,
            material_nominierung=None,
            mgk_pct=None,
            material_mgk=None,
            maschinenkosten=None,
            fertigungslohn=None,
            veredelung_direkt_vor=None,
            fgk_basis=None,
            fgk_pct=None,
            fgk_betrag=None,
            herstellkosten=hk,
            zwischensumme=zw,
            hinweise=hints,
            legacy=True,
        )

    nominierung = getattr(calc, "material_nominierung", None)
    try:
        mgk_pct = rates.mgk_pct_for_nominierung(
            nominierung, kontext=f"Material {calc.teilebezeichnung}"
        )
    except CentralMarkupRatesError as exc:
        hints.append(str(exc))
        mgk_pct = None

    if mgk_pct is None:
        return PartDetail(
            position_id=pos.id,
            sequence=pos.sequence,
            bezeichnung=calc.teilebezeichnung or pos.name_snapshot or "PART",
            teilenummer=calc.teilenummer or pos.part_number_snapshot or "",
            menge=menge,
            price_basis=pos.price_basis or "COST",
            materialkosten=None,
            material_ausschussquote_pct=float(calc.ausschussquote_pct),
            materialkosten_inkl_ausschuss=None,
            material_nominierung=nominierung,
            mgk_pct=None,
            material_mgk=None,
            maschinenkosten=None,
            fertigungslohn=None,
            veredelung_direkt_vor=None,
            fgk_basis=None,
            fgk_pct=rates.fgk_pct,
            fgk_betrag=None,
            herstellkosten=hk,
            zwischensumme=zw,
            hinweise=hints,
        )

    sg_input = SpritzgussInput(
        teilegewicht_netto_g=calc.teilegewicht_netto_g,
        materialpreis_pro_kg=calc.materialpreis_pro_kg,
        ausschussquote_pct=calc.ausschussquote_pct,
        mgk_pct=mgk_pct,
        material_nominierung=nominierung,  # type: ignore[arg-type]
        zykluszeit_s=calc.zykluszeit_s,
        maschinenstundensatz=calc.maschinenstundensatz,
        kavitaeten=calc.kavitaeten,
        lohnstundensatz=calc.lohnstundensatz,
        fgk_pct=rates.fgk_pct,
        werkzeugkosten_eur=calc.werkzeugkosten_eur or 0,
        werkzeug_abrechnungsart=calc.werkzeug_abrechnungsart or "einmalzahlung",  # type: ignore[arg-type]
        amortisationsvolumen=calc.amortisationsvolumen,
        vvgk_pct=rates.vvgk_pct,
        gewinn_pct=rates.gewinn_pct,
        skonto_pct=rates.skonto_pct,
    )
    sg = berechne_spritzguss(sg_input)

    veredelung_eingaben: list[VeredelungSchrittEingabe] = []
    step_direct: list[tuple[Any, Any]] = []
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
        vk = berechne_veredelung(
            VeredelungInput(
                taktzeit_s=row[2],
                anzahl_mitarbeiter=row[3],
                lohnstundensatz=row[4],
                maschinenstundensatz=row[5],
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

    gesamt = berechne_gesamt(
        sg.to_dict(),
        veredelung_eingaben,
        fgk_pct=rates.fgk_pct,
        vvgk_pct=0,
        gewinn_pct=0,
        skonto_pct=0,
    )
    # Für Assembly COST-Basis: Herstellkosten ohne Top-Level-Verkaufszuschläge
    herstell = float(gesamt.gesamte_herstellkosten)

    process_steps: list[PartProcessStepDetail] = []
    for ergebnis_step in gesamt.veredelung_schritte:
        if not ergebnis_step.aktiv:
            continue
        # Direkte Lohn/Maschine/Verbrauch aus Eingabe-Match
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
    # Assembly-Ergebnis hat Vorrang für Stückpreis/Zwischensumme (COST-Basis),
    # Live-Detail liefert die Aufschlüsselung.
    if ergebnis_line and ergebnis_line.get("einzelpreis") is not None:
        herstell = float(ergebnis_line["einzelpreis"])
    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])
    else:
        zw = _money(herstell * menge)
    return PartDetail(
        position_id=pos.id,
        sequence=pos.sequence,
        bezeichnung=calc.teilebezeichnung or pos.name_snapshot or "PART",
        teilenummer=calc.teilenummer or pos.part_number_snapshot or "",
        menge=menge,
        price_basis=pos.price_basis or "COST",
        materialkosten=float(sg.materialkosten),
        material_ausschussquote_pct=float(calc.ausschussquote_pct),
        materialkosten_inkl_ausschuss=float(sg.materialkosten_inkl_ausschuss),
        material_nominierung=nominierung,
        mgk_pct=mgk_pct,
        material_mgk=float(sg.materialgemeinkosten),
        maschinenkosten=float(sg.maschinenkosten),
        fertigungslohn=float(sg.fertigungslohn),
        veredelung_direkt_vor=verd_vor,
        fgk_basis=float(gesamt.fgk_basis),
        fgk_pct=float(gesamt.applied_fgk_pct),
        fgk_betrag=float(gesamt.fertigungsgemeinkosten),
        herstellkosten=herstell,
        zwischensumme=zw,
        process_steps=process_steps,
        hinweise=hints,
    )


def _purchased_detail(
    db: Session,
    pos: AssemblyPosition,
    rates: CentralMarkupRates | None,
    ergebnis_line: dict | None,
) -> PurchasedDetail:
    menge = float(pos.quantity or 1)
    hints: list[str] = []
    kt = db.get(Kaufteil, pos.purchased_part_id) if pos.purchased_part_id else None
    if not kt:
        preis = float(pos.price_snapshot or pos.cost_snapshot or 0)
        return PurchasedDetail(
            position_id=pos.id,
            sequence=pos.sequence,
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
            mgk_pct = rates.mgk_pct_for_nominierung(nominierung, kontext=f"Kaufteil {kt.bezeichnung}")
        except CentralMarkupRatesError as exc:
            hints.append(str(exc))

    if mgk_pct is None:
        inkl = float(pos.price_snapshot or einkauf)
        mgk_betrag = _money(inkl - einkauf)
    else:
        inkl = _money(einkauf * (1 + mgk_pct / 100.0))
        mgk_betrag = _money(inkl - einkauf)

    if ergebnis_line and ergebnis_line.get("zwischensumme") is not None:
        zw = float(ergebnis_line["zwischensumme"])
    else:
        zw = _money(inkl * menge)

    return PurchasedDetail(
        position_id=pos.id,
        sequence=pos.sequence,
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


def _process_detail(
    db: Session,
    pos: AssemblyPosition,
    rates: CentralMarkupRates | None,
    yield_by_pos: dict[int, dict],
    ergebnis_line: dict | None,
    assembly_fgk_basis: float | None,
    assembly_fgk: float | None,
) -> AssyProcessDetail:
    hints: list[str] = []
    yd = yield_by_pos.get(pos.id or -1, {})
    lohn = masch = verb = None
    vor = float(yd.get("process_kosten_vor_ausschuss") or 0)
    quote = float(yd.get("ausschussquote_pct") or 0)
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
            vk = berechne_veredelung(
                VeredelungInput(
                    taktzeit_s=row[1],
                    anzahl_mitarbeiter=row[2],
                    lohnstundensatz=row[3],
                    maschinenstundensatz=row[4],
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
            name = pos.name_snapshot or "Prozess"
            hints.append("Veredelungsschritt nicht gefunden.")
    else:
        name = pos.name_snapshot or pos.label or "Prozess"

    vorprodukt = float(yd.get("vorprodukt_eingang") or 0)
    nach = float(yd.get("kosten_nach_ausbeute") or (vorprodukt + vor))
    zuschlag = float(yd.get("ausschuss_zuschlag") or _money(nach - vorprodukt - vor))
    zw = float(ergebnis_line["zwischensumme"]) if ergebnis_line and ergebnis_line.get("zwischensumme") is not None else _money(nach - vorprodukt)

    fgk_pct = rates.fgk_pct if rates else None
    # FGK auf diesen Prozessanteil proportional zur Assembly-FGK-Basis
    fgk_betrag = None
    if rates and assembly_fgk_basis and assembly_fgk_basis > 0 and assembly_fgk is not None:
        fgk_betrag = _money(assembly_fgk * (vor / assembly_fgk_basis))

    return AssyProcessDetail(
        position_id=pos.id,
        sequence=pos.sequence,
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
        hinweise=hints
        + [
            "ASSY-/Prozess-Ausschuss belastet Vorproduktkosten + direkte Prozesskosten gemeinsam "
            "(Ausbeutekette)."
        ],
    )


def build_baugruppe_detail_kalkulation(db: Session, assembly_id: int) -> BaugruppeDetailKalkulation:
    obj = db.get(Baugruppe, assembly_id)
    if not obj:
        raise ValueError("Baugruppe nicht gefunden")

    ergebnis = parse_json_dict(obj.ergebnis) or {}
    customer_name, program_name, project_name = _resolve_hierarchy(db, obj)
    rates, rate_warnings = _load_rates(db)

    assumptions: list[AssumptionRow] = []
    if rates:
        assumptions = [
            AssumptionRow(
                "MGK selbstnominiert",
                rates.mgk_kaufteil_selbst_pct,
                "Material inkl. Ausschuss / Kaufteil-Einkaufspreis",
            ),
            AssumptionRow(
                "MGK OEM-nominiert",
                rates.mgk_kaufteil_oem_pct,
                "Material inkl. Ausschuss / Kaufteil-Einkaufspreis",
            ),
            AssumptionRow(
                "FGK",
                rates.fgk_pct,
                "Maschinenkosten + Fertigungslohn + direkte Prozesskosten vor Ausschuss",
            ),
            AssumptionRow("SG&A / VVGK", rates.vvgk_pct, "Herstellkosten"),
            AssumptionRow("Profit / Gewinn", rates.gewinn_pct, "Herstellkosten + SG&A (Selbstkosten)"),
            AssumptionRow("Skonto", rates.skonto_pct, "Nettoverkaufspreis"),
        ]
    else:
        assumptions.append(
            AssumptionRow("Zentrale Zuschlagssätze", None, "–", rate_warnings[0] if rate_warnings else "fehlen")
        )

    positions = load_positions(db, assembly_id)
    lines_by_id = {
        p.get("position_id"): p
        for p in (ergebnis.get("positions") or [])
        if isinstance(p, dict) and p.get("position_id") is not None
    }
    yield_by_pos = {
        d.get("position_id"): d
        for d in (ergebnis.get("process_yield_details") or [])
        if isinstance(d, dict) and d.get("position_id") is not None
    }

    parts: list[PartDetail] = []
    purchased: list[PurchasedDetail] = []
    processes: list[AssyProcessDetail] = []
    warnings = list(rate_warnings)

    fgk_basis = _float(ergebnis.get("fgk_basis"))
    fgk_betrag = _float(ergebnis.get("fertigungsgemeinkosten"))

    for pos in sorted(positions, key=lambda p: p.sequence):
        if not pos.active:
            continue
        line = lines_by_id.get(pos.id)
        if pos.position_type == "PART":
            parts.append(_part_detail_from_calc(db, pos, rates, line))
        elif pos.position_type == "PURCHASED_PART":
            purchased.append(_purchased_detail(db, pos, rates, line))
        elif pos.position_type == "PROCESS":
            processes.append(
                _process_detail(db, pos, rates, yield_by_pos, line, fgk_basis, fgk_betrag)
            )
        elif pos.position_type == "SUBASSEMBLY":
            warnings.append(
                f"Unterbaugruppe '{pos.name_snapshot}' als Sammelposition – Detail siehe Kind-Export."
            )

    for p in parts:
        warnings.extend(p.hinweise)
    for p in purchased:
        warnings.extend(p.hinweise)

    ueberleitung = _build_ueberleitung(ergebnis, parts, purchased, processes, obj)
    endpreis = _float(ergebnis.get("endpreis_je_stueck"))
    jsz = int(obj.jahresstueckzahl or 0)
    jahresumsatz = _money(endpreis * jsz) if endpreis is not None else None

    return BaugruppeDetailKalkulation(
        program_name=program_name,
        customer_name=customer_name,
        project_name=project_name,
        assumptions=assumptions,
        parts=parts,
        purchased=purchased,
        processes=processes,
        ueberleitung=ueberleitung,
        warnings=warnings,
        live_endpreis=endpreis,
        live_herstellkosten=_float(ergebnis.get("herstellkosten")),
        live_vvgk=_float(ergebnis.get("vvgk")),
        live_gewinn=_float(ergebnis.get("gewinn")),
        live_skonto=_float(ergebnis.get("skonto")),
        live_netto=_float(ergebnis.get("nettoverkaufspreis")),
        jahresstueckzahl=jsz,
        jahresumsatz=jahresumsatz,
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
    obj: Baugruppe,
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
        for step in part.process_steps:
            lines.append(
                UeberleitungLine(
                    f"  └ {part.bezeichnung} / {step.bezeichnung} Ausschuss",
                    step.ausschuss_zuschlag,
                    f"Quote {step.ausschussquote_pct} % auf Vorprodukt {step.vorprodukt_eingang:.4f} + Prozess {step.kosten_vor_ausschuss:.4f}",
                )
            )
            if part.fgk_betrag is not None and step == part.process_steps[-1]:
                pass
        if part.material_mgk is not None:
            lines.append(
                UeberleitungLine(
                    f"  └ Material-MGK {part.bezeichnung}",
                    _money(part.material_mgk * part.menge),
                    f"{part.mgk_pct} % auf Material inkl. Ausschuss",
                )
            )
        if part.fgk_betrag is not None:
            lines.append(
                UeberleitungLine(
                    f"  └ FGK {part.bezeichnung}",
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
                f"{k.mgk_pct if k.mgk_pct is not None else '–'} % ({k.nominierung or 'ohne Nominierung'})",
            )
        )
        kauf_einkauf += k.einkaufspreis * k.menge
        kauf_mgk += k.kaufteil_mgk * k.menge
    if purchased:
        lines.append(
            UeberleitungLine(
                "Kaufteile Summe (Einkauf)",
                _money(kauf_einkauf),
                "Summe Einkaufspreise × Menge",
            )
        )
        lines.append(
            UeberleitungLine("Kaufteil-MGK Summe", _money(kauf_mgk), "Summe MGK × Menge"),
        )

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
                f"  └ Ausschuss {proc.bezeichnung}",
                proc.ausschuss_zuschlag,
                f"{proc.ausschussquote_pct} % auf Vorprodukte {proc.vorprodukt_eingang:.4f} + Prozess "
                f"{proc.kosten_vor_ausschuss:.4f} (Ausbeute {proc.ausbeute_pct} %)",
            )
        )

    hk = _float(ergebnis.get("herstellkosten"))
    fgk_b = _float(ergebnis.get("fgk_basis"))
    fgk = _float(ergebnis.get("fertigungsgemeinkosten"))
    vvgk = _float(ergebnis.get("vvgk"))
    selbst = _float(ergebnis.get("selbstkosten"))
    gewinn = _float(ergebnis.get("gewinn"))
    netto = _float(ergebnis.get("nettoverkaufspreis"))
    skonto = _float(ergebnis.get("skonto"))
    endpreis = _float(ergebnis.get("endpreis_je_stueck"))

    lines.append(UeberleitungLine("Gesamt-FGK-Basis (Baugruppen-Prozesse)", fgk_b, "Summe Prozesskosten vor Ausschuss"))
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
    jsz = int(obj.jahresstueckzahl or 0)
    if endpreis is not None:
        lines.append(
            UeberleitungLine(
                "Jahresumsatz",
                _money(endpreis * jsz),
                f"Endpreis × Jahresstückzahl {jsz}",
                True,
            )
        )
    return lines
