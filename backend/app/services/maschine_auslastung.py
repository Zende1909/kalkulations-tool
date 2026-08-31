"""Maschinenauslastung: Bedarf aus Spritzguss-Prozessen vs. verfügbare Jahresstunden.

Formel (nicht Mittelung von Projektprozenten):
    benötigte Stunden = Σ (Jahresstückzahl × Prozessfaktoren / Nettokapazität)
    Nettokapazität aus Kalkulationsergebnis oder Zykluszeit/Kavitäten/Ausschuss.
    verfügbare Stunden = Maschine.jahresstunden (Werk-Betriebsparameter, Planungsperiode Jahr)
    Auslastung % = benötigte Stunden / verfügbare Stunden × 100
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe, BaugruppeSpritzgussZuordnung
from app.models.customer import Customer
from app.models.maschine import Maschine
from app.models.program import Program, ProgramVolume
from app.models.project import Project
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.werk import Werk
from app.services.machine_hourly_rate import (
    MachineRateValidationError,
    berechne_maschinenstundensatz,
    build_rate_input_from_maschine_and_werk,
)
from app.services.project_volume_service import average_jahresstueckzahl_for_project
from app.services.spritzguss_kalkulation import excel_round_0


@dataclass
class _DemandLine:
    maschine_id: int
    project_id: int
    project_name: str
    source_type: str
    source_label: str
    jahresstueckzahl: float
    required_hours: float
    calendar_year: int | None = None


@dataclass
class _MachineAgg:
    required_hours: float = 0.0
    lines: list[_DemandLine] = field(default_factory=list)
    yearly_hours: dict[int, float] = field(default_factory=dict)


def _parse_json_dict(value: object) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _resolve_nettokapazitaet(calc: SpritzgussKalkulation) -> float | None:
    ergebnis = _parse_json_dict(calc.ergebnis)
    bloecke = _parse_json_dict(calc.ergebnis_bloecke)
    fertigung = bloecke.get("fertigung") if isinstance(bloecke.get("fertigung"), dict) else {}
    for key in ("nettokapazitaet",):
        raw = ergebnis.get(key) or fertigung.get(key)
        if raw is not None:
            val = float(raw)
            if val > 0:
                return val
    zyklus = float(calc.zykluszeit_s or 0)
    kav = int(calc.kavitaeten or 0)
    if zyklus <= 0 or kav <= 0:
        return None
    ausschuss = float(calc.ausschussquote_pct or 0) / 100.0
    if ausschuss >= 1:
        return None
    brutto_exakt = (Decimal("3600") / Decimal(str(zyklus))) * Decimal(str(kav))
    brutto = excel_round_0(brutto_exakt)
    if brutto < 1:
        return None
    netto = float(brutto) * (1.0 - ausschuss)
    return netto if netto > 0 else None


def _hours_from_volume(stueckzahl: float, nettokapazitaet: float | None) -> float | None:
    if nettokapazitaet is None or nettokapazitaet <= 0 or stueckzahl <= 0:
        return None
    return float(stueckzahl) / float(nettokapazitaet)


def _resolve_jahresstueckzahl(db: Session, project_id: int, stored: int | None) -> float:
    if stored is not None and int(stored) > 0:
        return float(stored)
    avg = average_jahresstueckzahl_for_project(db, project_id)
    if avg.jahresstueckzahl is not None and avg.jahresstueckzahl > 0:
        return float(avg.jahresstueckzahl)
    return 0.0


def _resolve_available_hours(maschine: Maschine, werk: Werk | None) -> float | None:
    if maschine.jahresstunden is not None:
        return float(maschine.jahresstunden)
    if werk is None:
        return None
    try:
        rate_input = build_rate_input_from_maschine_and_werk(maschine, werk)
        result = berechne_maschinenstundensatz(rate_input)
        return float(result.jahresstunden)
    except MachineRateValidationError:
        return None


def _validate_hierarchy(
    db: Session,
    *,
    customer_id: int | None,
    program_id: int | None,
    project_ids: list[int],
) -> None:
    if customer_id is not None and customer_id < 1:
        raise HTTPException(status_code=422, detail="Ungültige Kunden-ID")
    if program_id is not None and program_id < 1:
        raise HTTPException(status_code=422, detail="Ungültige Programm-ID")
    if customer_id is not None and db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=422, detail="Kunde nicht gefunden")
    if program_id is not None:
        program = db.get(Program, program_id)
        if program is None:
            raise HTTPException(status_code=422, detail="Programm nicht gefunden")
        if customer_id is not None and program.customer_id != customer_id:
            raise HTTPException(status_code=422, detail="Programm passt nicht zum Kunden")
    for pid in project_ids:
        if pid < 1:
            raise HTTPException(status_code=422, detail="Ungültige Projekt-ID")
        project = db.get(Project, pid)
        if project is None:
            raise HTTPException(status_code=422, detail=f"Projekt {pid} nicht gefunden")
        if program_id is not None and project.program_id != program_id:
            raise HTTPException(status_code=422, detail=f"Projekt {pid} passt nicht zum Programm")
        if customer_id is not None:
            prog = db.get(Program, project.program_id)
            if prog is None or prog.customer_id != customer_id:
                raise HTTPException(status_code=422, detail=f"Projekt {pid} passt nicht zum Kunden")


def _spritzguss_ids_in_baugruppen(db: Session, baugruppe_ids: list[int]) -> set[int]:
    if not baugruppe_ids:
        return set()
    legacy = db.scalars(
        select(BaugruppeSpritzgussZuordnung.spritzguss_kalkulation_id).where(
            BaugruppeSpritzgussZuordnung.baugruppe_id.in_(baugruppe_ids)
        )
    ).all()
    modern = db.scalars(
        select(AssemblyPosition.part_calculation_id).where(
            AssemblyPosition.parent_assembly_id.in_(baugruppe_ids),
            AssemblyPosition.position_type == "PART",
            AssemblyPosition.active.is_(True),
            AssemblyPosition.part_calculation_id.is_not(None),
        )
    ).all()
    return {int(x) for x in legacy if x is not None} | {int(x) for x in modern if x is not None}


def _baugruppen_for_project(db: Session, project_id: int) -> list[Baugruppe]:
    return list(
        db.scalars(
            select(Baugruppe).where(
                Baugruppe.aktiv.is_(True),
                or_(
                    Baugruppe.linked_project_id == project_id,
                    Baugruppe.project_id == project_id,
                ),
            )
        ).all()
    )


def _project_year_volumes(db: Session, project: Project) -> list[tuple[int, float]]:
    rows = db.scalars(
        select(ProgramVolume)
        .where(ProgramVolume.program_id == project.program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    ).all()
    from app.services.hierarchy import calculate_project_volume

    out: list[tuple[int, float]] = []
    for vol in rows:
        pv = calculate_project_volume(vol.vehicle_volume, project.quantity_per_vehicle)
        if pv > 0:
            out.append((int(vol.calendar_year), float(pv)))
    return out


def _add_demand(
    agg: dict[int, _MachineAgg],
    *,
    maschine_id: int,
    project_id: int,
    project_name: str,
    source_type: str,
    source_label: str,
    stueckzahl: float,
    nettokapazitaet: float | None,
    year_volumes: list[tuple[int, float]] | None = None,
    quantity_factor: float = 1.0,
) -> None:
    effective_qty = float(stueckzahl) * float(quantity_factor)
    hours = _hours_from_volume(effective_qty, nettokapazitaet)
    if hours is None:
        return
    bucket = agg.setdefault(maschine_id, _MachineAgg())
    line = _DemandLine(
        maschine_id=maschine_id,
        project_id=project_id,
        project_name=project_name,
        source_type=source_type,
        source_label=source_label,
        jahresstueckzahl=effective_qty,
        required_hours=hours,
    )
    bucket.required_hours += hours
    bucket.lines.append(line)
    if year_volumes and nettokapazitaet:
        for year, vol in year_volumes:
            y_hours = _hours_from_volume(vol * quantity_factor, nettokapazitaet)
            if y_hours is not None:
                bucket.yearly_hours[year] = bucket.yearly_hours.get(year, 0.0) + y_hours


def _collect_project_demand(
    db: Session,
    *,
    project: Project,
    plant_machine_ids: set[int],
    agg: dict[int, _MachineAgg],
) -> None:
    project_id = project.id
    project_name = project.name
    baugruppen = _baugruppen_for_project(db, project_id)
    linked_sg_ids = _spritzguss_ids_in_baugruppen(db, [b.id for b in baugruppen])
    year_volumes = _project_year_volumes(db, project)

    standalone_rows = list(
        db.scalars(
            select(SpritzgussKalkulation).where(
                SpritzgussKalkulation.project_id == project_id,
                SpritzgussKalkulation.aktiv.is_(True),
                SpritzgussKalkulation.maschine_id.is_not(None),
            )
        ).all()
    )
    for calc in standalone_rows:
        if calc.id in linked_sg_ids:
            continue
        if calc.maschine_id not in plant_machine_ids:
            continue
        netto = _resolve_nettokapazitaet(calc)
        qty = _resolve_jahresstueckzahl(db, project_id, calc.jahresstueckzahl)
        _add_demand(
            agg,
            maschine_id=int(calc.maschine_id),
            project_id=project_id,
            project_name=project_name,
            source_type="einzelteil",
            source_label=calc.teilebezeichnung or calc.teilenummer,
            stueckzahl=qty,
            nettokapazitaet=netto,
            year_volumes=year_volumes,
        )

    for bg in baugruppen:
        bg_qty = _resolve_jahresstueckzahl(db, project_id, bg.jahresstueckzahl)
        legacy_links = list(
            db.scalars(
                select(BaugruppeSpritzgussZuordnung).where(
                    BaugruppeSpritzgussZuordnung.baugruppe_id == bg.id
                )
            ).all()
        )
        for link in legacy_links:
            calc = db.get(SpritzgussKalkulation, link.spritzguss_kalkulation_id)
            if calc is None or not calc.aktiv or calc.maschine_id is None:
                continue
            if int(calc.maschine_id) not in plant_machine_ids:
                continue
            netto = _resolve_nettokapazitaet(calc)
            factor = float(link.menge or 1.0)
            _add_demand(
                agg,
                maschine_id=int(calc.maschine_id),
                project_id=project_id,
                project_name=project_name,
                source_type="baugruppe",
                source_label=f"{bg.name} → {calc.teilebezeichnung or calc.teilenummer}",
                stueckzahl=bg_qty,
                nettokapazitaet=netto,
                year_volumes=year_volumes,
                quantity_factor=factor,
            )

        positions = list(
            db.scalars(
                select(AssemblyPosition).where(
                    AssemblyPosition.parent_assembly_id == bg.id,
                    AssemblyPosition.position_type == "PART",
                    AssemblyPosition.active.is_(True),
                    AssemblyPosition.part_calculation_id.is_not(None),
                )
            ).all()
        )
        for pos in positions:
            calc = db.get(SpritzgussKalkulation, pos.part_calculation_id)
            if calc is None or not calc.aktiv or calc.maschine_id is None:
                continue
            if int(calc.maschine_id) not in plant_machine_ids:
                continue
            netto = _resolve_nettokapazitaet(calc)
            factor = float(pos.quantity or 1.0) * float(pos.quantity_factor or 1.0)
            _add_demand(
                agg,
                maschine_id=int(calc.maschine_id),
                project_id=project_id,
                project_name=project_name,
                source_type="baugruppe",
                source_label=f"{bg.name} → {calc.teilebezeichnung or calc.teilenummer}",
                stueckzahl=bg_qty,
                nettokapazitaet=netto,
                year_volumes=year_volumes,
                quantity_factor=factor,
            )


def _ratio_pct(numerator: float, denominator: float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100.0


def build_maschinen_auslastung(
    db: Session,
    *,
    plant_id: int,
    customer_id: int | None = None,
    program_id: int | None = None,
    project_ids: list[int] | None = None,
    nur_aktiv: bool = True,
) -> dict:
    if plant_id < 1:
        raise HTTPException(status_code=422, detail="Ungültige Werk-ID")
    werk = db.get(Werk, plant_id)
    if werk is None:
        raise HTTPException(status_code=422, detail="Werk nicht gefunden")

    pids = list(dict.fromkeys(project_ids or []))
    _validate_hierarchy(db, customer_id=customer_id, program_id=program_id, project_ids=pids)

    stmt = select(Maschine).where(Maschine.werk_id == plant_id).order_by(Maschine.bezeichnung.asc())
    if nur_aktiv:
        stmt = stmt.where(Maschine.aktiv.is_(True))
    machines = list(db.scalars(stmt).all())
    plant_machine_ids = {m.id for m in machines}

    agg: dict[int, _MachineAgg] = {}
    if pids:
        for pid in pids:
            project = db.get(Project, pid)
            if project is None:
                continue
            _collect_project_demand(
                db,
                project=project,
                plant_machine_ids=plant_machine_ids,
                agg=agg,
            )

    rows: list[dict] = []
    util_pcts: list[float] = []
    total_required = 0.0
    total_available = 0.0
    overloaded_count = 0
    max_pct: float | None = None
    max_mid: int | None = None
    max_name: str | None = None
    machines_with_demand = 0

    for maschine in machines:
        bucket = agg.get(maschine.id, _MachineAgg())
        required = float(bucket.required_hours)
        available = _resolve_available_hours(maschine, werk)
        util = _ratio_pct(required, available) if available is not None and available > 0 else None
        rest = (available - required) if available is not None and available > 0 else None
        overload = max(0.0, required - available) if available is not None and available > 0 else None
        is_overloaded = bool(available is not None and available > 0 and required > available)
        if required > 0:
            machines_with_demand += 1
        if is_overloaded:
            overloaded_count += 1
        if util is not None:
            util_pcts.append(util)
            if max_pct is None or util > max_pct:
                max_pct = util
                max_mid = maschine.id
                max_name = maschine.bezeichnung
        if available is not None:
            total_available += available
            total_required += required

        yearly_breakdown: list[dict] = []
        if bucket.yearly_hours:
            for year in sorted(bucket.yearly_hours):
                y_req = bucket.yearly_hours[year]
                yearly_breakdown.append(
                    {
                        "calendar_year": year,
                        "required_hours": round(y_req, 6),
                        "available_hours": available,
                        "utilization_pct": _ratio_pct(y_req, available),
                    }
                )

        rows.append(
            {
                "maschine_id": maschine.id,
                "maschinen_nr": maschine.maschinen_nr,
                "bezeichnung": maschine.bezeichnung,
                "werk_id": maschine.werk_id,
                "werk_name": werk.name,
                "available_hours": available,
                "required_hours": round(required, 6),
                "utilization_pct": round(util, 6) if util is not None else None,
                "rest_capacity_hours": round(rest, 6) if rest is not None else None,
                "overload_hours": round(overload, 6) if overload is not None else None,
                "is_overloaded": is_overloaded,
                "has_demand": required > 0,
                "projects": [
                    {
                        "project_id": line.project_id,
                        "project_name": line.project_name,
                        "source_type": line.source_type,
                        "source_label": line.source_label,
                        "jahresstueckzahl": round(line.jahresstueckzahl, 4),
                        "required_hours": round(line.required_hours, 6),
                    }
                    for line in bucket.lines
                ],
                "yearly_breakdown": yearly_breakdown,
            }
        )

    avg_util = sum(util_pcts) / len(util_pcts) if util_pcts else None
    plant_util = _ratio_pct(total_required, total_available if total_available > 0 else None)

    return {
        "plant_id": plant_id,
        "plant_name": werk.name,
        "customer_id": customer_id,
        "program_id": program_id,
        "project_ids": pids,
        "no_projects_selected": len(pids) == 0,
        "planning_period": {
            "label": "Jahresplanung",
            "basis": "Jahresstückzahl (Durchschnitt Projektmengenprofil) vs. Maschine.jahresstunden (Werk-Betriebsparameter)",
            "available_hours_per_machine_year": _resolve_available_hours(machines[0], werk)
            if len(machines) == 1
            else None,
        },
        "summary": {
            "machine_count": len(machines),
            "machines_with_demand": machines_with_demand,
            "overloaded_count": overloaded_count,
            "average_utilization_pct": round(avg_util, 6) if avg_util is not None else None,
            "plant_utilization_pct": round(plant_util, 6) if plant_util is not None else None,
            "max_utilization_pct": round(max_pct, 6) if max_pct is not None else None,
            "max_utilization_maschine_id": max_mid,
            "max_utilization_maschine_name": max_name,
        },
        "machines": rows,
    }
