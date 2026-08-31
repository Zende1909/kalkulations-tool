from typing import Any

from dataclasses import replace

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import BaugruppeSpritzgussZuordnung
from app.models.investition import Investition
from app.models.material import Material
from app.models.maschine import Maschine
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.user import User
from app.models.veredelungsschritt import Veredelungsschritt
from app.models.werk import Werk
from app.schemas.maschinen_groesse import (
    MaschinenGroesseCalcRequest,
    MaschinenGroesseFields,
    MaschinenGroesseResultSchema,
)
from app.schemas.spritzguss_kalkulation import (
    SpritzgussCalcRequest,
    SpritzgussCalcResponse,
    SpritzgussErgebnisSchema,
    SpritzgussKalkulationCreate,
    SpritzgussKalkulationListItem,
    SpritzgussKalkulationRead,
    SpritzgussKalkulationUpdate,
)
from app.schemas.spritzguss_veredelung import (
    VeredelungReihenfolgeUpdate,
    VeredelungZuordnungInput,
    VeredelungZuordnungRead,
    VeredelungZuordnungUpdate,
)
from app.schemas.zykluszeit import (
    ZykluszeitCalcRequest,
    ZykluszeitFields,
    ZykluszeitResultSchema,
)
from app.services.central_markup_rates import (
    CentralMarkupRatesError,
    load_central_markup_rates,
)
from app.services.losgroesse_berechnung import (
    LosgroesseKontext,
    LosgroesseValidationError,
    losgroesse_metadata_dict,
    resolve_losgroesse,
)
from app.services.maschinen_groesse import (
    MaschinenGroesseInput,
    MaschinenGroesseResult,
    MaschinenGroesseValidationError,
    berechne_maschinen_groesse_mit_auswahl,
    validate_injection_pressure,
)
from app.services.spritzguss_gesamt_kalkulation import (
    GesamtValidationError,
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    SpritzgussValidationError,
    berechne_spritzguss,
)
from app.services.spritzguss_hierarchy import resolve_hierarchy_for_spritzguss
from app.services.zykluszeit import (
    ZykluszeitInput,
    ZykluszeitResult,
    berechne_zykluszeit,
)
from app.services.veredelung_kalkulation import berechne_veredelung
from app.services.veredelung_kalkulation import VeredelungInput as VeredelungCalcInput

router = APIRouter(prefix="/spritzguss", tags=["Spritzguss-Kalkulation"])


def _material_injection_pressure(db: Session, material_id: int | None) -> float:
    if material_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Material ist für die Maschinengrößenberechnung erforderlich.",
        )
    material = db.get(Material, material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Material nicht gefunden.",
        )
    try:
        return validate_injection_pressure(
            material.injection_pressure_kg_cm2,
            kontext=f"Material {material.material_nr}",
        )
    except MaschinenGroesseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _maschinen_groesse_input_from_fields(
    *,
    modus: str | None,
    breite_mm: float | None,
    laenge_mm: float | None,
    oeffnungen_pct: float | None,
    proj_flaeche_mm2: float | None,
    injection_pressure_kg_cm2: float,
    kavitaeten: int,
) -> MaschinenGroesseInput | None:
    if modus is None:
        return None
    return MaschinenGroesseInput(
        modus=modus,  # type: ignore[arg-type]
        breite_mm=breite_mm,
        laenge_mm=laenge_mm,
        oeffnungen_pct=oeffnungen_pct,
        proj_flaeche_mm2=proj_flaeche_mm2,
        injection_pressure_kg_cm2=injection_pressure_kg_cm2,
        kavitaeten=kavitaeten,
    )


def _apply_maschinen_groesse_result(obj: SpritzgussKalkulation, result: MaschinenGroesseResult) -> None:
    obj.maschinen_groesse_injection_pressure_kg_cm2 = result.injection_pressure_kg_cm2
    obj.maschinen_groesse_proj_flaeche_netto_mm2 = result.proj_flaeche_netto_mm2
    obj.maschinen_groesse_zuhaltekraft_ohne_sicherheit_t = result.zuhaltekraft_ohne_sicherheit_t
    obj.maschinen_groesse_sicherheitszuschlag_faktor = result.sicherheitszuschlag_faktor
    obj.maschinen_groesse_zuhaltekraft_erforderlich_t = result.zuhaltekraft_erforderlich_t
    obj.maschinen_groesse_empfohlene_maschine_id = result.empfohlene_maschine_id
    obj.maschinen_groesse_warnung = result.warnung


def _run_maschinen_groesse_for_model(
    db: Session,
    obj: SpritzgussKalkulation,
) -> MaschinenGroesseResult | None:
    if obj.maschinen_groesse_modus is None:
        obj.maschinen_groesse_injection_pressure_kg_cm2 = None
        obj.maschinen_groesse_proj_flaeche_netto_mm2 = None
        obj.maschinen_groesse_zuhaltekraft_ohne_sicherheit_t = None
        obj.maschinen_groesse_sicherheitszuschlag_faktor = None
        obj.maschinen_groesse_zuhaltekraft_erforderlich_t = None
        obj.maschinen_groesse_empfohlene_maschine_id = None
        obj.maschinen_groesse_warnung = None
        return None
    pressure = _material_injection_pressure(db, obj.material_id)
    sizing_input = _maschinen_groesse_input_from_fields(
        modus=obj.maschinen_groesse_modus,
        breite_mm=obj.maschinen_groesse_breite_mm,
        laenge_mm=obj.maschinen_groesse_laenge_mm,
        oeffnungen_pct=obj.maschinen_groesse_oeffnungen_pct,
        proj_flaeche_mm2=obj.maschinen_groesse_proj_flaeche_mm2,
        injection_pressure_kg_cm2=pressure,
        kavitaeten=obj.kavitaeten,
    )
    if sizing_input is None:
        return None
    try:
        result = berechne_maschinen_groesse_mit_auswahl(
            db,
            sizing_input,
            werk_id=obj.werk_id,
        )
    except MaschinenGroesseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    _apply_maschinen_groesse_result(obj, result)
    return result


def _run_maschinen_groesse_for_request(
    db: Session,
    body: MaschinenGroesseCalcRequest | SpritzgussCalcRequest,
    *,
    werk_id: int | None,
) -> MaschinenGroesseResult | None:
    if body.maschinen_groesse_modus is None:
        return None
    pressure = _material_injection_pressure(db, body.material_id)
    sizing_input = _maschinen_groesse_input_from_fields(
        modus=body.maschinen_groesse_modus,
        breite_mm=body.maschinen_groesse_breite_mm,
        laenge_mm=body.maschinen_groesse_laenge_mm,
        oeffnungen_pct=body.maschinen_groesse_oeffnungen_pct,
        proj_flaeche_mm2=body.maschinen_groesse_proj_flaeche_mm2,
        injection_pressure_kg_cm2=pressure,
        kavitaeten=body.kavitaeten,
    )
    if sizing_input is None:
        return None
    try:
        return berechne_maschinen_groesse_mit_auswahl(
            db,
            sizing_input,
            werk_id=werk_id,
        )
    except MaschinenGroesseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


def _maschinen_groesse_schema(result: MaschinenGroesseResult | None) -> MaschinenGroesseResultSchema | None:
    if result is None:
        return None
    return MaschinenGroesseResultSchema(**result.as_dict())


# Rein berechnete Spalten. `zykluszeit_nebenzeiten_gesamt_s` gehört bewusst
# nicht dazu: dort steht die optionale Übersteuerung des Klassen-Richtwerts.
_ZYKLUSZEIT_RESULT_ATTRS = (
    "zykluszeit_kuehlzeit_s",
    "zykluszeit_vorschlag_s",
    "zykluszeit_hinweis",
)


def _materialgruppe(db: Session, material_id: int | None) -> str | None:
    if material_id is None:
        return None
    material = db.get(Material, material_id)
    return getattr(material, "materialgruppe", None) if material is not None else None


def _apply_zykluszeit_result(obj: SpritzgussKalkulation, result: ZykluszeitResult) -> None:
    obj.zykluszeit_kuehlzeit_s = result.kuehlzeit_s
    obj.zykluszeit_vorschlag_s = result.gesamtzykluszeit_s
    obj.zykluszeit_hinweis = result.hinweis


def _run_zykluszeit_for_model(
    db: Session, obj: SpritzgussKalkulation
) -> ZykluszeitResult | None:
    """Zykluszeit-Schätzung am Datensatz aktualisieren.

    Der Vorschlag ist rein informativ: er blockiert das Speichern nie und
    überschreibt ``zykluszeit_s`` nicht. Ohne gepflegte Wandstärke gilt der
    Bereich als ungenutzt und die berechneten Spalten werden geleert.
    """
    if obj.zykluszeit_wandstaerke_mm is None:
        for attr in _ZYKLUSZEIT_RESULT_ATTRS:
            setattr(obj, attr, None)
        return None
    result = berechne_zykluszeit(
        ZykluszeitInput(
            wandstaerke_mm=obj.zykluszeit_wandstaerke_mm,
            materialgruppe=_materialgruppe(db, obj.material_id),
            groessenklasse=obj.zykluszeit_groessenklasse,
            nebenzeiten_gesamt_s=obj.zykluszeit_nebenzeiten_gesamt_s,
        )
    )
    _apply_zykluszeit_result(obj, result)
    return result


def _run_zykluszeit_for_request(
    db: Session, body: ZykluszeitCalcRequest | SpritzgussCalcRequest
) -> ZykluszeitResult:
    return berechne_zykluszeit(
        ZykluszeitInput(
            wandstaerke_mm=body.zykluszeit_wandstaerke_mm,
            materialgruppe=_materialgruppe(db, body.material_id),
            groessenklasse=body.zykluszeit_groessenklasse,
            nebenzeiten_gesamt_s=body.zykluszeit_nebenzeiten_gesamt_s,
        )
    )


def _zykluszeit_schema(result: ZykluszeitResult | None) -> ZykluszeitResultSchema | None:
    if result is None:
        return None
    return ZykluszeitResultSchema(**result.as_dict())


def _apply_central_rates(
    db: Session, calc_input: SpritzgussInput, *, werk_id: int | None = None
) -> SpritzgussInput:
    """Setzt Zuschlagssätze aus Stammdaten; MGK nur als Satz, Anwendung in der Engine.

    Der zentrale MGK-Satz ersetzt einen etwaigen Client-``mgk_pct``. Die betragsmäßige
    MGK wird ausschließlich in ``berechne_spritzguss`` einmal auf
    ``materialkosten_inkl_ausschuss`` berechnet – nicht erneut auf
    ``materialkosten_gesamt``.
    """
    try:
        rates = load_central_markup_rates(db, werk_id=werk_id)
        mgk_pct = rates.mgk_pct_for_nominierung(
            calc_input.material_nominierung,
            kontext="Spritzguss-Materialeinsatz",
        )
    except CentralMarkupRatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SpritzgussInput(
        teilegewicht_netto_g=calc_input.teilegewicht_netto_g,
        schussgewicht_g=calc_input.schussgewicht_g,
        materialpreis_pro_kg=calc_input.materialpreis_pro_kg,
        ausschussquote_pct=calc_input.ausschussquote_pct,
        mgk_pct=mgk_pct,
        material_nominierung=calc_input.material_nominierung,
        zykluszeit_s=calc_input.zykluszeit_s,
        maschinenstundensatz=calc_input.maschinenstundensatz,
        kavitaeten=calc_input.kavitaeten,
        lohnstundensatz=calc_input.lohnstundensatz,
        fgk_pct=rates.fgk_pct,
        werkzeugkosten_eur=calc_input.werkzeugkosten_eur,
        werkzeug_abrechnungsart=calc_input.werkzeug_abrechnungsart,
        amortisationsvolumen=calc_input.amortisationsvolumen,
        vvgk_pct=rates.vvgk_pct,
        gewinn_pct=rates.gewinn_pct,
        skonto_pct=rates.skonto_pct,
        setup_zeit_min=calc_input.setup_zeit_min,
        setup_maschinenstundensatz=calc_input.setup_maschinenstundensatz,
        setup_lohnstundensatz=calc_input.setup_lohnstundensatz,
        setup_mitarbeiter=calc_input.setup_mitarbeiter,
        losgroesse=calc_input.losgroesse,
        setup_aktiv=calc_input.setup_aktiv,
    )


def _apply_hierarchy_payload(db: Session, payload: dict) -> dict:
    """Setzt kunde/projekt aus zentraler Hierarchie, wenn IDs gesetzt sind."""
    cid = payload.get("customer_id")
    pid = payload.get("program_id")
    prid = payload.get("project_id")
    year = payload.get("calculation_year")
    if cid is None and pid is None and prid is None:
        return payload
    if None in (cid, pid, prid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kunde, Programm und Projekt müssen gemeinsam angegeben werden.",
        )
    resolved = resolve_hierarchy_for_spritzguss(
        db,
        customer_id=int(cid),
        program_id=int(pid),
        project_id=int(prid),
        calculation_year=int(year) if year is not None else None,
    )
    payload.update(resolved)
    return payload


def _normalize_veredelung_zuordnungen(
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]] | None,
) -> list[VeredelungZuordnungInput]:
    """Wandelt Dict- oder Pydantic-Eingaben in Validierte Zuordnungen um."""
    if not zuordnungen:
        return []

    normalized: list[VeredelungZuordnungInput] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(zuordnungen, start=1):
        if isinstance(item, VeredelungZuordnungInput):
            zuordnung = item
        elif isinstance(item, dict):
            raw_id = item.get("veredelungsschritt_id")
            if raw_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: veredelungsschritt_id fehlt",
                )
            reihenfolge = item.get("reihenfolge", item.get("sequence"))
            if reihenfolge is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: reihenfolge fehlt",
                )
            payload = {
                "veredelungsschritt_id": raw_id,
                "reihenfolge": reihenfolge,
                "aktiv": item.get("aktiv", True),
                "mengenfaktor": item.get("mengenfaktor", item.get("quantity_factor", 1.0)),
            }
            try:
                zuordnung = VeredelungZuordnungInput.model_validate(payload)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: {exc.errors()[0]['msg']}",
                ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Veredelungszuordnung #{index}: ungültiges Format",
            )

        if zuordnung.veredelungsschritt_id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Veredelungsschritt {zuordnung.veredelungsschritt_id} "
                    "ist doppelt zugeordnet"
                ),
            )
        seen_ids.add(zuordnung.veredelungsschritt_id)
        normalized.append(zuordnung)

    return normalized


def _prepare_calc_input_with_losgroesse(
    db: Session,
    calc_input: SpritzgussInput,
    *,
    project_id: int | None,
    werk_id: int | None,
    losgroesse_modus: str | None,
    losgroesse_manuell: int | None,
    losgroesse_gespeichert: int | None,
) -> tuple[SpritzgussInput, LosgroesseKontext]:
    setup_aktiv = bool(calc_input.setup_aktiv) or float(calc_input.setup_zeit_min or 0) > 0
    gespeichert = (
        losgroesse_gespeichert
        if losgroesse_gespeichert is not None
        else calc_input.losgroesse
    )
    effective_modus = losgroesse_modus
    effective_manuell = losgroesse_manuell
    # Legacy: explizite Losgröße ohne Projekt → manuell (kein erzwungenes Auto)
    if (
        effective_modus in (None, "automatisch")
        and project_id is None
        and gespeichert is not None
        and effective_manuell is None
    ):
        effective_modus = "manuell"
        effective_manuell = int(gespeichert)
    try:
        ctx = resolve_losgroesse(
            db,
            modus=effective_modus,
            losgroesse_manuell=effective_manuell,
            losgroesse_gespeichert=gespeichert,
            project_id=project_id,
            werk_id=werk_id,
            setup_aktiv=setup_aktiv,
        )
    except LosgroesseValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return replace(calc_input, losgroesse=ctx.losgroesse_aktiv), ctx


def _to_calc_input_from_request(body: SpritzgussCalcRequest) -> SpritzgussInput:
    data = body.model_dump(
        exclude={
            "veredelung_zuordnungen",
            "werk_id",
            "project_id",
            "material_id",
            "losgroesse_modus",
            "losgroesse_manuell",
            "losgroesse",
            *MaschinenGroesseFields.model_fields.keys(),
            *ZykluszeitFields.model_fields.keys(),
        },
    )
    return SpritzgussInput(**data)


def _to_calc_input_from_model(obj: SpritzgussKalkulation) -> SpritzgussInput:
    art = getattr(obj, "werkzeug_abrechnungsart", None) or "amortisation"
    volumen = obj.amortisationsvolumen
    if art == "amortisation" and volumen is not None:
        volumen = int(volumen)
    elif art != "amortisation":
        volumen = None

    return SpritzgussInput(
        teilegewicht_netto_g=obj.teilegewicht_netto_g,
        schussgewicht_g=float(getattr(obj, "schussgewicht_g", 0) or 0),
        materialpreis_pro_kg=obj.materialpreis_pro_kg,
        ausschussquote_pct=obj.ausschussquote_pct,
        mgk_pct=obj.mgk_pct,
        material_nominierung=getattr(obj, "material_nominierung", None),  # type: ignore[arg-type]
        zykluszeit_s=obj.zykluszeit_s,
        maschinenstundensatz=obj.maschinenstundensatz,
        kavitaeten=obj.kavitaeten,
        lohnstundensatz=obj.lohnstundensatz,
        fgk_pct=obj.fgk_pct,
        werkzeugkosten_eur=obj.werkzeugkosten_eur,
        werkzeug_abrechnungsart=art,  # type: ignore[arg-type]
        amortisationsvolumen=volumen,
        vvgk_pct=obj.vvgk_pct,
        gewinn_pct=obj.gewinn_pct,
        skonto_pct=obj.skonto_pct,
        losgroesse=getattr(obj, "losgroesse", None),
        setup_zeit_min=float((obj.ergebnis or {}).get("setup_zeit_min", 0) or 0)
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_maschinenstundensatz=float(
            (obj.ergebnis or {}).get("setup_maschinenstundensatz", 0) or 0
        )
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_lohnstundensatz=float(
            (obj.ergebnis or {}).get("setup_lohnstundensatz", 0) or 0
        )
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_mitarbeiter=float((obj.ergebnis or {}).get("setup_mitarbeiter", 0) or 0)
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_aktiv=bool((obj.ergebnis or {}).get("setup_aktiv", False))
        if isinstance(obj.ergebnis, dict)
        else False,
    )


def _live_kosten_fuer_veredelungsschritt(schritt: Veredelungsschritt) -> float:
    kosten = berechne_veredelung(
        VeredelungCalcInput(
            taktzeit_s=schritt.taktzeit_s,
            anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
            lohnstundensatz=schritt.lohnstundensatz,
            maschinenstundensatz=schritt.maschinenstundensatz,
            verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
            ausschussquote_pct=schritt.ausschussquote_pct,
            fgk_pct=0,
            reihenfolge=schritt.reihenfolge,
        )
    )
    return kosten.kosten_inkl_ausschuss


def _live_veredelung_kosten(schritt: Veredelungsschritt):
    return berechne_veredelung(
        VeredelungCalcInput(
            taktzeit_s=schritt.taktzeit_s,
            anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
            lohnstundensatz=schritt.lohnstundensatz,
            maschinenstundensatz=schritt.maschinenstundensatz,
            verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
            ausschussquote_pct=schritt.ausschussquote_pct,
            fgk_pct=0,
            reihenfolge=schritt.reihenfolge,
        )
    )


def _resolve_veredelung_eingaben(
    db: Session,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
    *,
    use_snapshots: bool,
    kalkulation_id: int | None = None,
) -> list[VeredelungSchrittEingabe]:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    if not zuordnungen:
        return []

    snapshot_map: dict[int, SpritzgussVeredelungZuordnung] = {}
    if use_snapshots and kalkulation_id is not None:
        rows = db.scalars(
            select(SpritzgussVeredelungZuordnung).where(
                SpritzgussVeredelungZuordnung.kalkulation_id == kalkulation_id
            )
        ).all()
        snapshot_map = {row.veredelungsschritt_id: row for row in rows}

    eingaben: list[VeredelungSchrittEingabe] = []
    for zuordnung in zuordnungen:
        schritt = db.get(Veredelungsschritt, zuordnung.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {zuordnung.veredelungsschritt_id} nicht gefunden",
            )
        if not use_snapshots and not schritt.aktiv:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Veredelungsschritt '{schritt.bezeichnung}' ist inaktiv",
            )

        snapshot = snapshot_map.get(zuordnung.veredelungsschritt_id)
        live = _live_veredelung_kosten(schritt)
        if use_snapshots and snapshot is not None:
            kosten = snapshot.snapshot_kosten_inkl_ausschuss
            bezeichnung = snapshot.snapshot_bezeichnung
            art = snapshot.snapshot_veredelungsart
            # Ausbeutekette: Snapshot-Vor-Kosten/Quote (wie beim Speichern geschrieben).
            # Legacy-Zeilen ohne Vor-Snapshot → Live, damit Speichern = Berechnen.
            snap_vor = getattr(snapshot, "snapshot_kosten_vor_ausschuss", None)
            snap_q = getattr(snapshot, "snapshot_ausschussquote_pct", None)
            if snap_vor is not None and snap_q is not None:
                kosten_vor = float(snap_vor)
                ausschuss_q = float(snap_q)
            else:
                kosten_vor = live.kosten_vor_ausschuss
                ausschuss_q = float(schritt.ausschussquote_pct)
        else:
            kosten = live.kosten_inkl_ausschuss
            kosten_vor = live.kosten_vor_ausschuss
            ausschuss_q = float(schritt.ausschussquote_pct)
            bezeichnung = schritt.bezeichnung
            art = schritt.veredelungsart

        eingaben.append(
            VeredelungSchrittEingabe(
                veredelungsschritt_id=zuordnung.veredelungsschritt_id,
                bezeichnung=bezeichnung,
                veredelungsart=art,
                reihenfolge=zuordnung.reihenfolge,
                aktiv=zuordnung.aktiv,
                mengenfaktor=zuordnung.mengenfaktor,
                kosten_inkl_ausschuss=kosten,
                kosten_vor_ausschuss=kosten_vor,
                ausschussquote_pct=ausschuss_q,
            )
        )
    return eingaben


def _zuordnung_read(
    row: SpritzgussVeredelungZuordnung,
    *,
    kosten_gesamt: float | None = None,
) -> VeredelungZuordnungRead:
    if kosten_gesamt is None:
        kosten_gesamt = (
            row.snapshot_kosten_inkl_ausschuss * row.mengenfaktor if row.aktiv else 0.0
        )
    return VeredelungZuordnungRead(
        id=row.id,
        kalkulation_id=row.kalkulation_id,
        veredelungsschritt_id=row.veredelungsschritt_id,
        reihenfolge=row.reihenfolge,
        aktiv=row.aktiv,
        mengenfaktor=row.mengenfaktor,
        snapshot_bezeichnung=row.snapshot_bezeichnung,
        snapshot_veredelungsart=row.snapshot_veredelungsart,
        snapshot_kosten_inkl_ausschuss=row.snapshot_kosten_inkl_ausschuss,
        kosten_gesamt=kosten_gesamt,
    )


def _schema_mismatch_http(exc: ProgrammingError) -> HTTPException:
    """Übersetzt fehlende Snapshot-Spalten in eine handlungsfähige API-Antwort."""
    detail = (
        "Datenbankschema ist veraltet (fehlende Veredelungs-Snapshot-Spalten). "
        "Bitte `alembic upgrade head` ausführen "
        "(Revision e1a0007_veredelung_snapshot_yield)."
    )
    msg = str(getattr(exc, "orig", None) or exc)
    if "snapshot_kosten_vor_ausschuss" in msg or "snapshot_ausschussquote_pct" in msg:
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Datenbankschema passt nicht zum API-Code (UndefinedColumn). "
            "Bitte `alembic upgrade head` ausführen."
        ),
    )


def _load_zuordnungen(db: Session, kalkulation_id: int) -> list[SpritzgussVeredelungZuordnung]:
    try:
        return list(
            db.scalars(
                select(SpritzgussVeredelungZuordnung)
                .where(SpritzgussVeredelungZuordnung.kalkulation_id == kalkulation_id)
                .order_by(
                    SpritzgussVeredelungZuordnung.reihenfolge.asc(),
                    SpritzgussVeredelungZuordnung.id.asc(),
                )
            ).all()
        )
    except ProgrammingError as exc:
        raise _schema_mismatch_http(exc) from exc


def _sync_veredelung_zuordnungen(
    db: Session,
    obj: SpritzgussKalkulation,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
) -> list[SpritzgussVeredelungZuordnung]:
    """Ersetzt Zuordnungen und speichert Kosten-Snapshots."""
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    for existing in _load_zuordnungen(db, obj.id):
        db.delete(existing)
    db.flush()

    created: list[SpritzgussVeredelungZuordnung] = []
    for zuordnung in zuordnungen:
        schritt = db.get(Veredelungsschritt, zuordnung.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {zuordnung.veredelungsschritt_id} nicht gefunden",
            )
        live = _live_veredelung_kosten(schritt)
        row = SpritzgussVeredelungZuordnung(
            kalkulation_id=obj.id,
            veredelungsschritt_id=zuordnung.veredelungsschritt_id,
            reihenfolge=zuordnung.reihenfolge,
            aktiv=zuordnung.aktiv,
            mengenfaktor=zuordnung.mengenfaktor,
            snapshot_bezeichnung=schritt.bezeichnung,
            snapshot_veredelungsart=schritt.veredelungsart,
            snapshot_kosten_inkl_ausschuss=live.kosten_inkl_ausschuss,
            snapshot_kosten_vor_ausschuss=live.kosten_vor_ausschuss,
            snapshot_ausschussquote_pct=float(schritt.ausschussquote_pct),
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def _build_calc_response(
    db: Session,
    calc_input: SpritzgussInput,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
    *,
    use_snapshots: bool = False,
    kalkulation_id: int | None = None,
    saved_rows: list[SpritzgussVeredelungZuordnung] | None = None,
    werk_id: int | None = None,
    project_id: int | None = None,
    losgroesse_modus: str | None = None,
    losgroesse_manuell: int | None = None,
    losgroesse_gespeichert: int | None = None,
    maschinen_groesse: MaschinenGroesseResult | None = None,
    zykluszeit_vorschlag: ZykluszeitResult | None = None,
) -> SpritzgussCalcResponse:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    calc_input, losgroesse_ctx = _prepare_calc_input_with_losgroesse(
        db,
        calc_input,
        project_id=project_id,
        werk_id=werk_id,
        losgroesse_modus=losgroesse_modus,
        losgroesse_manuell=losgroesse_manuell,
        losgroesse_gespeichert=losgroesse_gespeichert,
    )
    calc_input = _apply_central_rates(db, calc_input, werk_id=werk_id)
    try:
        spritzguss = berechne_spritzguss(calc_input)
    except SpritzgussValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    spritzguss_dict = spritzguss.to_dict()
    bloecke = spritzguss.as_blocks()

    try:
        veredelung_eingaben = _resolve_veredelung_eingaben(
            db,
            zuordnungen,
            use_snapshots=use_snapshots,
            kalkulation_id=kalkulation_id,
        )
        gesamt = berechne_gesamt(
            spritzguss_dict,
            veredelung_eingaben,
            fgk_pct=calc_input.fgk_pct,
            vvgk_pct=calc_input.vvgk_pct,
            gewinn_pct=calc_input.gewinn_pct,
            skonto_pct=calc_input.skonto_pct,
        )
    except GesamtValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    ergebnis_dict = {
        **spritzguss_dict,
        **gesamt.to_dict(),
        # Gleiche Kostenbasis wie Endpreis: Gesamt-HK inkl. einer FGK
        "herstellkosten": gesamt.gesamte_herstellkosten,
        # Endpreis inkl. Veredelung und zentraler Zuschläge (nicht Spritzguss-VP allein)
        "verkaufspreis": gesamt.endpreis_je_stueck,
        # Material-Stack nur aus der Engine (MGK genau einmal auf inkl. Ausschuss).
        # Gesamt übernimmt materialkosten_gesamt unverändert – kein zweiter MGK-Satz.
        "materialkosten": spritzguss.materialkosten,
        "materialkosten_inkl_ausschuss": spritzguss.materialkosten_inkl_ausschuss,
        "materialausschuss_betrag": spritzguss.materialausschuss_betrag,
        "mgk_basis": spritzguss.mgk_basis,
        "materialgemeinkosten": spritzguss.materialgemeinkosten,
        "materialkosten_gesamt": spritzguss.materialkosten_gesamt,
        "applied_mgk_pct": spritzguss.applied_mgk_pct,
    }
    ergebnis_dict.update(losgroesse_metadata_dict(losgroesse_ctx))
    ergebnis_dict["losgroesse"] = losgroesse_ctx.losgroesse_aktiv

    # FGK genau einmal und konsistent anzeigen (Basis inkl. Veredelung)
    bloecke["fertigung"] = {
        **bloecke.get("fertigung", {}),
        "bruttokapazitaet_exakt": gesamt.bruttokapazitaet_exakt,
        "bruttokapazitaet": gesamt.bruttokapazitaet,
        "nettokapazitaet": gesamt.nettokapazitaet,
        "maschinenkosten": gesamt.maschinenkosten,
        "fertigungslohn": gesamt.fertigungslohn,
        "setup_maschinenkosten_je_teil": gesamt.setup_maschinenkosten_je_teil,
        "setup_lohnkosten_je_teil": gesamt.setup_lohnkosten_je_teil,
        "setup_kosten_je_teil": gesamt.setup_kosten_je_teil,
        "fgk_basis": gesamt.fgk_basis,
        "fertigungsgemeinkosten": gesamt.fertigungsgemeinkosten,
        "fgk_pct": gesamt.applied_fgk_pct,
        "losgroesse": losgroesse_ctx.losgroesse_aktiv,
        "losgroesse_modus": losgroesse_ctx.modus,
        "losgroesse_automatisch": losgroesse_ctx.losgroesse_automatisch,
        "losgroesse_aktiv": losgroesse_ctx.losgroesse_aktiv,
    }

    # FGK nur im Fertigungsblock (nicht nochmals unter Gemeinkosten) –
    # vermeidet den Eindruck einer zweiten Addition.
    bloecke["gemeinkosten"] = {
        "herstellkosten": gesamt.gesamte_herstellkosten,
        "vvgk": gesamt.vvgk,
        "vvgk_pct": gesamt.applied_vvgk_pct,
        "vvgk_basis": gesamt.gesamte_herstellkosten,
        "selbstkosten": gesamt.selbstkosten,
        "gewinn": gesamt.gewinn,
        "gewinn_pct": gesamt.applied_gewinn_pct,
        "gewinn_basis": gesamt.selbstkosten,
    }
    bloecke["verkaufspreis"] = {
        "nettoverkaufspreis": gesamt.nettoverkaufspreis,
        "skonto": gesamt.skonto,
        "skonto_pct": gesamt.applied_skonto_pct,
        "verkaufspreis": gesamt.endpreis_je_stueck,
    }
    bloecke["zusammenfassung"] = gesamt.as_ergebnisuebersicht()
    if gesamt.veredelung_gesamt > 0 or gesamt.veredelung_schritte:
        bloecke["veredelung"] = gesamt.as_veredelung_block()

    zuordnung_reads: list[VeredelungZuordnungRead] = []
    if saved_rows is not None:
        kosten_map = {
            s.veredelungsschritt_id: s.kosten_gesamt for s in gesamt.veredelung_schritte
        }
        zuordnung_reads = [
            _zuordnung_read(row, kosten_gesamt=kosten_map.get(row.veredelungsschritt_id, 0))
            for row in saved_rows
        ]
    elif zuordnungen:
        kosten_map = {
            s.veredelungsschritt_id: s.kosten_gesamt for s in gesamt.veredelung_schritte
        }
        for z in sorted(zuordnungen, key=lambda x: x.reihenfolge):
            schritt = next(s for s in gesamt.veredelung_schritte if s.veredelungsschritt_id == z.veredelungsschritt_id)
            zuordnung_reads.append(
                VeredelungZuordnungRead(
                    id=0,
                    kalkulation_id=kalkulation_id or 0,
                    veredelungsschritt_id=z.veredelungsschritt_id,
                    reihenfolge=z.reihenfolge,
                    aktiv=z.aktiv,
                    mengenfaktor=z.mengenfaktor,
                    snapshot_bezeichnung=schritt.bezeichnung,
                    snapshot_veredelungsart=schritt.veredelungsart,
                    snapshot_kosten_inkl_ausschuss=schritt.kosten_inkl_ausschuss,
                    kosten_gesamt=kosten_map.get(z.veredelungsschritt_id, 0),
                )
            )

    if maschinen_groesse is not None:
        ergebnis_dict["maschinen_groesse"] = maschinen_groesse.as_dict()
        bloecke["maschinen_groesse"] = maschinen_groesse.as_dict()

    if zykluszeit_vorschlag is not None:
        ergebnis_dict["zykluszeit_vorschlag"] = zykluszeit_vorschlag.as_dict()
        bloecke["zykluszeit_vorschlag"] = zykluszeit_vorschlag.as_dict()

    return SpritzgussCalcResponse(
        ergebnis=SpritzgussErgebnisSchema(**ergebnis_dict),
        bloecke=bloecke,
        veredelung_zuordnungen=zuordnung_reads,
        maschinen_groesse=_maschinen_groesse_schema(maschinen_groesse),
        zykluszeit_vorschlag=_zykluszeit_schema(zykluszeit_vorschlag),
    )


def _apply_calculation(
    db: Session,
    obj: SpritzgussKalkulation,
    zuordnungen: list[VeredelungZuordnungInput] | None = None,
    *,
    use_snapshots: bool = False,
) -> SpritzgussCalcResponse:
    if zuordnungen is None:
        rows = _load_zuordnungen(db, obj.id)
        zuordnungen = [
            VeredelungZuordnungInput(
                veredelungsschritt_id=row.veredelungsschritt_id,
                reihenfolge=row.reihenfolge,
                aktiv=row.aktiv,
                mengenfaktor=row.mengenfaktor,
            )
            for row in rows
        ]
        use_snapshots = True

    sizing = _run_maschinen_groesse_for_model(db, obj)
    zykluszeit = _run_zykluszeit_for_model(db, obj)
    response = _build_calc_response(
        db,
        _to_calc_input_from_model(obj),
        zuordnungen,
        use_snapshots=use_snapshots,
        kalkulation_id=obj.id,
        saved_rows=_load_zuordnungen(db, obj.id) if obj.id else None,
        werk_id=getattr(obj, "werk_id", None),
        project_id=getattr(obj, "project_id", None),
        losgroesse_modus=getattr(obj, "losgroesse_modus", None),
        losgroesse_manuell=getattr(obj, "losgroesse_manuell", None),
        losgroesse_gespeichert=getattr(obj, "losgroesse", None),
        maschinen_groesse=sizing,
        zykluszeit_vorschlag=zykluszeit,
    )
    # Angewandte zentrale Sätze am Datensatz spiegeln (Export/Transparenz)
    ergebnis = response.ergebnis
    if ergebnis.applied_mgk_pct is not None:
        obj.mgk_pct = float(ergebnis.applied_mgk_pct)
    if ergebnis.applied_fgk_pct is not None:
        obj.fgk_pct = float(ergebnis.applied_fgk_pct)
    if ergebnis.applied_vvgk_pct is not None:
        obj.vvgk_pct = float(ergebnis.applied_vvgk_pct)
    if ergebnis.applied_gewinn_pct is not None:
        obj.gewinn_pct = float(ergebnis.applied_gewinn_pct)
    if ergebnis.applied_skonto_pct is not None:
        obj.skonto_pct = float(ergebnis.applied_skonto_pct)
    if ergebnis.material_nominierung is not None:
        obj.material_nominierung = ergebnis.material_nominierung
    obj.losgroesse = ergebnis.losgroesse_aktiv or ergebnis.losgroesse
    if ergebnis.losgroesse_modus is not None:
        obj.losgroesse_modus = ergebnis.losgroesse_modus
    obj.losgroesse_manuell = (
        ergebnis.losgroesse_manuell
        if ergebnis.losgroesse_modus == "manuell"
        else None
    )
    previous = obj.ergebnis if isinstance(obj.ergebnis, dict) else {}
    dumped = ergebnis.model_dump()
    # Setup-Eingabeparameter beibehalten / aus calc_input spiegeln
    calc_in = _to_calc_input_from_model(obj)
    for key in (
        "setup_zeit_min",
        "setup_maschinenstundensatz",
        "setup_lohnstundensatz",
        "setup_mitarbeiter",
        "setup_aktiv",
    ):
        dumped[key] = getattr(calc_in, key, previous.get(key, 0 if key != "setup_aktiv" else False))
    # Maschinenrate-Snapshot (falls Maschine verknüpft)
    rate_snap = previous.get("maschinen_rate_snapshot")
    if obj.maschine_id:
        maschine = db.get(Maschine, obj.maschine_id)
        if maschine is not None:
            rate_snap = {
                "maschine_id": maschine.id,
                "maschinen_nr": maschine.maschinen_nr,
                "source_currency": maschine.source_currency,
                "stundensatz_source": maschine.stundensatz_source,
                "stundensatz_eur": maschine.stundensatz,
                "jahresstunden": maschine.jahresstunden,
                "komponenten_usd": {
                    "space": maschine.space_costs_pro_stunde,
                    "abschreibung": maschine.abschreibung_pro_stunde,
                    "zinsen": maschine.zinsen_pro_stunde,
                    "versicherung": maschine.versicherung_pro_stunde,
                    "instandhaltung": maschine.instandhaltung_pro_stunde,
                    "energie": maschine.energie_pro_stunde,
                },
                "fx_to_eur": None,
                "werk_id": maschine.werk_id,
            }
            if maschine.werk_id:
                werk = db.get(Werk, maschine.werk_id)
                if werk:
                    rate_snap["fx_to_eur"] = float(werk.fx_to_eur)
                    rate_snap["currency"] = werk.currency
                    rate_snap["werk_code"] = werk.code
    if rate_snap:
        dumped["maschinen_rate_snapshot"] = rate_snap
    if response.maschinen_groesse is not None:
        dumped["maschinen_groesse"] = response.maschinen_groesse.model_dump()
    if response.zykluszeit_vorschlag is not None:
        dumped["zykluszeit_vorschlag"] = response.zykluszeit_vorschlag.model_dump()
    dumped["zykluszeit_quelle"] = getattr(obj, "zykluszeit_quelle", None) or "manuell"
    if getattr(obj, "werk_id", None):
        werk = db.get(Werk, obj.werk_id)
        if werk:
            dumped["werk_snapshot"] = {
                "werk_id": werk.id,
                "code": werk.code,
                "name": werk.name,
                "currency": werk.currency,
                "fx_to_eur": float(werk.fx_to_eur),
            }
    obj.ergebnis = dumped
    obj.ergebnis_bloecke = response.bloecke
    return response


def _kalkulation_to_read(db: Session, obj: SpritzgussKalkulation) -> SpritzgussKalkulationRead:
    rows = _load_zuordnungen(db, obj.id)
    kosten_map: dict[int, float] = {}
    if isinstance(obj.ergebnis, dict):
        for schritt in obj.ergebnis.get("veredelung_schritte", []) or []:
            if isinstance(schritt, dict):
                kosten_map[schritt.get("veredelungsschritt_id", 0)] = schritt.get(
                    "kosten_gesamt", 0
                )
    zuordnungen = [
        _zuordnung_read(row, kosten_gesamt=kosten_map.get(row.veredelungsschritt_id))
        for row in rows
    ]
    base = SpritzgussKalkulationRead.model_validate(obj)
    erg = obj.ergebnis if isinstance(obj.ergebnis, dict) else {}
    return base.model_copy(
        update={
            "veredelung_zuordnungen": zuordnungen,
            "setup_zeit_min": float(erg.get("setup_zeit_min", 0) or 0),
            "setup_maschinenstundensatz": float(
                erg.get("setup_maschinenstundensatz", 0) or 0
            ),
            "setup_lohnstundensatz": float(erg.get("setup_lohnstundensatz", 0) or 0),
            "setup_mitarbeiter": float(erg.get("setup_mitarbeiter", 0) or 0),
            "setup_aktiv": bool(erg.get("setup_aktiv", False)),
        }
    )


def _run_calculation(
    db: Session,
    calc_input: SpritzgussInput,
    zuordnungen: list[VeredelungZuordnungInput],
    *,
    werk_id: int | None = None,
    project_id: int | None = None,
    losgroesse_modus: str | None = None,
    losgroesse_manuell: int | None = None,
    losgroesse_gespeichert: int | None = None,
    maschinen_groesse: MaschinenGroesseResult | None = None,
    zykluszeit_vorschlag: ZykluszeitResult | None = None,
) -> SpritzgussCalcResponse:
    return _build_calc_response(
        db,
        calc_input,
        zuordnungen,
        use_snapshots=False,
        werk_id=werk_id,
        project_id=project_id,
        losgroesse_modus=losgroesse_modus,
        losgroesse_manuell=losgroesse_manuell,
        losgroesse_gespeichert=losgroesse_gespeichert,
        maschinen_groesse=maschinen_groesse,
        zykluszeit_vorschlag=zykluszeit_vorschlag,
    )


def _sync_werkzeug_investition(db: Session, obj: SpritzgussKalkulation) -> None:
    """Legt/aktualisiert/löscht die zugehörige Werkzeug-Einmalzahlung."""
    existing = db.scalars(
        select(Investition).where(
            Investition.calculation_id == obj.id,
            Investition.investment_type == "Werkzeug",
            Investition.payment_type == "Einmalzahlung",
        )
    ).first()

    art = getattr(obj, "werkzeug_abrechnungsart", "amortisation")
    if art != "einmalzahlung" or obj.werkzeugkosten_eur <= 0:
        if existing:
            db.delete(existing)
        return

    description = (
        f"Werkzeug-Einmalzahlung für {obj.teilenummer} – {obj.teilebezeichnung}"
    )
    if existing:
        existing.project_id = obj.projekt or ""
        existing.customer = obj.kunde or ""
        existing.part_name = obj.teilebezeichnung
        existing.part_number = obj.teilenummer or ""
        existing.name = f"Werkzeug {obj.teilenummer}".strip() or "Werkzeug-Einmalzahlung"
        existing.description = description
        existing.amount = obj.werkzeugkosten_eur
        existing.status = "In Planung"
        existing.included_in_unit_price = False
        existing.amortization_volume = None
        existing.cost_per_piece = None
    else:
        db.add(
            Investition(
                project_id=obj.projekt or "",
                customer=obj.kunde or "",
                calculation_id=obj.id,
                part_name=obj.teilebezeichnung,
                part_number=obj.teilenummer or "",
                name=f"Werkzeug {obj.teilenummer}".strip() or "Werkzeug-Einmalzahlung",
                description=description,
                amount=obj.werkzeugkosten_eur,
                investment_type="Werkzeug",
                payment_type="Einmalzahlung",
                status="In Planung",
                included_in_unit_price=False,
            )
        )


@router.post("/maschinen-groesse/berechnen", response_model=MaschinenGroesseResultSchema)
def berechne_maschinen_groesse_endpoint(
    body: MaschinenGroesseCalcRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Berechnet Maschinengröße / Zuhaltekraft ohne vollständige Kalkulation."""
    sizing = _run_maschinen_groesse_for_request(db, body, werk_id=body.werk_id)
    if sizing is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maschinengrößen-Modus ist erforderlich.",
        )
    schema = _maschinen_groesse_schema(sizing)
    assert schema is not None
    return schema


@router.post("/zykluszeit/berechnen", response_model=ZykluszeitResultSchema)
def berechne_zykluszeit_endpoint(
    body: ZykluszeitCalcRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Zykluszeitvorschlag nach IKET ohne vollständige Kalkulation.

    Liefert auch bei unvollständigen oder unzulässigen Eingaben HTTP 200 mit
    ``berechenbar=false`` und einem verständlichen Hinweis.
    """
    schema = _zykluszeit_schema(_run_zykluszeit_for_request(db, body))
    assert schema is not None
    return schema


@router.post("/berechnen", response_model=SpritzgussCalcResponse)
def berechnen(
    body: SpritzgussCalcRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Berechnet eine Kalkulation ohne Speichern."""
    sizing = _run_maschinen_groesse_for_request(db, body, werk_id=body.werk_id)
    zykluszeit = (
        _run_zykluszeit_for_request(db, body)
        if body.zykluszeit_wandstaerke_mm is not None
        else None
    )
    calc_input = _to_calc_input_from_request(body)
    return _run_calculation(
        db,
        calc_input,
        body.veredelung_zuordnungen,
        werk_id=body.werk_id,
        project_id=body.project_id,
        losgroesse_modus=body.losgroesse_modus,
        losgroesse_manuell=body.losgroesse_manuell,
        losgroesse_gespeichert=body.losgroesse,
        maschinen_groesse=sizing,
        zykluszeit_vorschlag=zykluszeit,
    )


@router.get("", response_model=list[SpritzgussKalkulationListItem])
def list_kalkulationen(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    nur_aktiv: bool = Query(False),
    project_id: int | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(SpritzgussKalkulation).order_by(SpritzgussKalkulation.updated_at.desc())
    if nur_aktiv:
        stmt = stmt.where(SpritzgussKalkulation.aktiv.is_(True))
    if project_id is not None:
        stmt = stmt.where(SpritzgussKalkulation.project_id == project_id)
    rows = db.scalars(stmt.offset(skip).limit(limit)).all()
    from app.services.spritzguss_cost_snapshot import (
        selbstkosten_aus_ergebnis,
        verkaufspreis_aus_ergebnis,
    )

    result: list[SpritzgussKalkulationListItem] = []
    for row in rows:
        ergebnis = row.ergebnis if isinstance(row.ergebnis, dict) else None
        result.append(
            SpritzgussKalkulationListItem(
                id=row.id,
                teilebezeichnung=row.teilebezeichnung,
                teilenummer=row.teilenummer,
                kunde=row.kunde,
                projekt=row.projekt,
                project_id=getattr(row, "project_id", None),
                jahresstueckzahl=row.jahresstueckzahl,
                verkaufspreis=verkaufspreis_aus_ergebnis(ergebnis),
                selbstkosten=selbstkosten_aus_ergebnis(ergebnis),
                updated_at=row.updated_at,
                aktiv=row.aktiv,
            )
        )
    return result


@router.get("/{item_id}", response_model=SpritzgussKalkulationRead)
def get_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = db.get(SpritzgussKalkulation, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    return _kalkulation_to_read(db, item)


@router.get("/{item_id}/veredelung", response_model=list[VeredelungZuordnungRead])
def list_veredelung_zuordnungen(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = db.get(SpritzgussKalkulation, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    return _kalkulation_to_read(db, item).veredelung_zuordnungen


@router.post(
    "/{item_id}/veredelung",
    response_model=VeredelungZuordnungRead,
    status_code=status.HTTP_201_CREATED,
)
def add_veredelung_zuordnung(
    item_id: int,
    body: VeredelungZuordnungInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    existing = db.scalars(
        select(SpritzgussVeredelungZuordnung).where(
            SpritzgussVeredelungZuordnung.kalkulation_id == item_id,
            SpritzgussVeredelungZuordnung.veredelungsschritt_id
            == body.veredelungsschritt_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veredelungsschritt ist dieser Kalkulation bereits zugeordnet",
        )
    schritt = db.get(Veredelungsschritt, body.veredelungsschritt_id)
    if not schritt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Veredelungsschritt nicht gefunden"
        )
    live = _live_veredelung_kosten(schritt)
    row = SpritzgussVeredelungZuordnung(
        kalkulation_id=item_id,
        veredelungsschritt_id=body.veredelungsschritt_id,
        reihenfolge=body.reihenfolge,
        aktiv=body.aktiv,
        mengenfaktor=body.mengenfaktor,
        snapshot_bezeichnung=schritt.bezeichnung,
        snapshot_veredelungsart=schritt.veredelungsart,
        snapshot_kosten_inkl_ausschuss=live.kosten_inkl_ausschuss,
        snapshot_kosten_vor_ausschuss=live.kosten_vor_ausschuss,
        snapshot_ausschussquote_pct=float(schritt.ausschussquote_pct),
    )
    db.add(row)
    db.flush()
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    db.refresh(row)
    gesamt_kosten = row.snapshot_kosten_inkl_ausschuss * row.mengenfaktor if row.aktiv else 0
    return _zuordnung_read(row, kosten_gesamt=gesamt_kosten)


@router.put("/{item_id}/veredelung/reihenfolge", response_model=list[VeredelungZuordnungRead])
def update_veredelung_reihenfolge(
    item_id: int,
    body: VeredelungReihenfolgeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    rows = {row.id: row for row in _load_zuordnungen(db, item_id)}
    for item in body.zuordnungen:
        row = rows.get(item.id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Zuordnung {item.id} nicht gefunden",
            )
        row.reihenfolge = item.reihenfolge
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    return _kalkulation_to_read(db, obj).veredelung_zuordnungen


@router.put("/{item_id}/veredelung/{zuordnung_id}", response_model=VeredelungZuordnungRead)
def update_veredelung_zuordnung(
    item_id: int,
    zuordnung_id: int,
    body: VeredelungZuordnungUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    row = db.get(SpritzgussVeredelungZuordnung, zuordnung_id)
    if not row or row.kalkulation_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden"
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    db.refresh(row)
    return _zuordnung_read(row)


@router.delete("/{item_id}/veredelung/{zuordnung_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_veredelung_zuordnung(
    item_id: int,
    zuordnung_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    row = db.get(SpritzgussVeredelungZuordnung, zuordnung_id)
    if not row or row.kalkulation_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden"
        )
    db.delete(row)
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()


SETUP_ERGEBNIS_KEYS = (
    "setup_zeit_min",
    "setup_maschinenstundensatz",
    "setup_lohnstundensatz",
    "setup_mitarbeiter",
    "setup_aktiv",
)


def _merge_setup_into_ergebnis(obj: SpritzgussKalkulation, setup: dict[str, Any]) -> None:
    current = dict(obj.ergebnis) if isinstance(obj.ergebnis, dict) else {}
    for key in SETUP_ERGEBNIS_KEYS:
        if key in setup and setup[key] is not None:
            current[key] = setup[key]
    obj.ergebnis = current


@router.post("", response_model=SpritzgussKalkulationRead, status_code=status.HTTP_201_CREATED)
def create_kalkulation(
    body: SpritzgussKalkulationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    zuordnungen = body.veredelung_zuordnungen
    payload = body.model_dump(exclude={"veredelung_zuordnungen", *SETUP_ERGEBNIS_KEYS})
    payload = _apply_hierarchy_payload(db, payload)
    if payload.get("werkzeug_abrechnungsart") == "einmalzahlung":
        payload["amortisationsvolumen"] = None
    obj = SpritzgussKalkulation(**payload)
    db.add(obj)
    db.flush()
    _merge_setup_into_ergebnis(
        obj,
        {k: getattr(body, k) for k in SETUP_ERGEBNIS_KEYS},
    )
    _sync_veredelung_zuordnungen(db, obj, zuordnungen)
    _apply_calculation(db, obj, zuordnungen, use_snapshots=True)
    db.commit()
    db.refresh(obj)
    # Werkzeug-Investitionen werden separat im Modul Investitionen / Business Case gepflegt.
    # _sync_werkzeug_investition(db, obj)
    db.commit()
    db.refresh(obj)
    return _kalkulation_to_read(db, obj)


@router.put("/{item_id}", response_model=SpritzgussKalkulationRead)
def update_kalkulation(
    item_id: int,
    body: SpritzgussKalkulationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )

    updates = body.model_dump(exclude_unset=True)
    zuordnungen = updates.pop("veredelung_zuordnungen", None)
    setup_updates = {k: updates.pop(k) for k in list(SETUP_ERGEBNIS_KEYS) if k in updates}
    if setup_updates:
        _merge_setup_into_ergebnis(obj, setup_updates)
    hierarchy_keys = {"customer_id", "program_id", "project_id", "calculation_year"}
    if hierarchy_keys.intersection(updates):
        merged = {
            "customer_id": updates.get("customer_id", obj.customer_id),
            "program_id": updates.get("program_id", obj.program_id),
            "project_id": updates.get("project_id", obj.project_id),
            "calculation_year": updates.get("calculation_year", obj.calculation_year),
        }
        merged = _apply_hierarchy_payload(db, merged)
        updates.update(merged)
    for field, value in updates.items():
        setattr(obj, field, value)

    art = getattr(obj, "werkzeug_abrechnungsart", "amortisation")
    if art == "einmalzahlung":
        obj.amortisationsvolumen = None
    elif obj.amortisationsvolumen is not None:
        obj.amortisationsvolumen = int(obj.amortisationsvolumen)

    if zuordnungen is not None:
        zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
        _sync_veredelung_zuordnungen(db, obj, zuordnungen)

    _apply_calculation(
        db,
        obj,
        zuordnungen if zuordnungen is not None else None,
        use_snapshots=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # Werkzeug-Investitionen werden separat im Modul Investitionen / Business Case gepflegt.
    # _sync_werkzeug_investition(db, obj)
    db.commit()
    db.refresh(obj)
    return _kalkulation_to_read(db, obj)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    """Löscht eine Spritzguss-Kalkulation inkl. abhängiger Veredelungs-/Investitionsdaten.

    Referenzen in Baugruppen (Legacy-Zuordnung oder Assembly-PART) blockieren das
    Löschen bewusst (FK NO ACTION / RESTRICT) – dann HTTP 409 mit Hinweis.
    """
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )

    blockers: list[str] = []

    assembly_count = db.scalar(
        select(func.count())
        .select_from(AssemblyPosition)
        .where(AssemblyPosition.part_calculation_id == item_id)
    )
    if assembly_count:
        blockers.append(
            f"{assembly_count} Baugruppen-Position(en) (assembly_positions)"
        )

    legacy_count = db.scalar(
        select(func.count())
        .select_from(BaugruppeSpritzgussZuordnung)
        .where(BaugruppeSpritzgussZuordnung.spritzguss_kalkulation_id == item_id)
    )
    if legacy_count:
        blockers.append(
            f"{legacy_count} Legacy-Baugruppen-Zuordnung(en)"
        )

    if blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Kalkulation kann nicht gelöscht werden, weil sie noch in Baugruppen "
                "verwendet wird (aktiv oder archiviert): "
                + "; ".join(blockers)
                + ". Bitte zuerst die Verknüpfungen in den betreffenden Baugruppen entfernen "
                "oder die Baugruppe endgültig löschen."
            ),
        )

    # Abhängigkeiten, die mit der Kalkulation entfallen dürfen
    for verd in db.scalars(
        select(SpritzgussVeredelungZuordnung).where(
            SpritzgussVeredelungZuordnung.kalkulation_id == item_id
        )
    ).all():
        db.delete(verd)
    for inv in db.scalars(
        select(Investition).where(Investition.calculation_id == item_id)
    ).all():
        db.delete(inv)

    db.delete(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Kalkulation kann nicht gelöscht werden, weil noch abhängige "
                "Datensätze darauf verweisen. Bitte Verknüpfungen in Baugruppen "
                "prüfen und entfernen."
            ),
        ) from exc
