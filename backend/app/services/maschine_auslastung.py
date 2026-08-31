"""Maschinenauslastung: Laufzeit + Rüstzeit vs. verfügbare Jahresstunden.

OEE: `Maschine.jahresstunden` wird aus Werk-Parametern als
    arbeitstage × schichten × stunden × OEE berechnet (siehe machine_hourly_rate).
    OEE ist damit in den verfügbaren Stunden enthalten und wird nicht auf den Bedarf angewendet.

Bedarf je Jahr (keine Mittelung von Projektprozenten):
    Laufzeit = Jahresstückzahl × Mengenfaktor / Nettokapazität
    Anzahl Lose = ceil(Jahresstückzahl × Mengenfaktor / Losgröße)
    Rüstzeit = Anzahl Lose × (setup_zeit_min / 60)   [nur Maschinen-Rüstzeit, nicht in Nettokapazität]
    Gesamtbedarf = Laufzeit + Rüstzeit
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from decimal import Decimal

from fastapi import HTTPException
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
from app.services.spritzguss_kalkulation import excel_round_0

UTILIZATION_YEARS = list(range(2026, 2041))


@dataclass(frozen=True)
class _MachineCapacity:
    gross_hours: float | None
    oee: float | None
    available_hours: float | None
    oee_in_available_hours: bool


@dataclass
class _YearBucket:
    run_hours: float = 0.0
    setup_hours: float = 0.0
    project_ids: set[int] = field(default_factory=set)


@dataclass
class _DemandLine:
    project_id: int
    project_name: str
    source_type: str
    source_label: str
    calendar_year: int
    jahresstueckzahl: float
    run_hours: float
    setup_hours: float

    @property
    def required_hours(self) -> float:
        return self.run_hours + self.setup_hours


@dataclass
class _MachineAgg:
    yearly: dict[int, _YearBucket] = field(default_factory=dict)
    lines: list[_DemandLine] = field(default_factory=list)

    def year_bucket(self, year: int) -> _YearBucket:
        return self.yearly.setdefault(year, _YearBucket())


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


def _pick_werk_or_machine(werk: Werk | None, maschine: Maschine, attr: str) -> float | None:
    if werk is not None:
        val = getattr(werk, attr, None)
        if val is not None:
            return float(val)
    val = getattr(maschine, attr, None)
    return float(val) if val is not None else None


def _resolve_machine_capacity(maschine: Maschine, werk: Werk | None) -> _MachineCapacity:
    """Verfügbare Stunden = Brutto × OEE; jahresstunden enthält OEE bereits."""
    oee = _pick_werk_or_machine(werk, maschine, "oee")
    available: float | None = None
    gross: float | None = None

    if maschine.jahresstunden is not None:
        available = float(maschine.jahresstunden)
        if oee is not None and oee > 0:
            gross = available / oee
    elif werk is not None:
        try:
            rate_input = build_rate_input_from_maschine_and_werk(maschine, werk)
            result = berechne_maschinenstundensatz(rate_input)
            available = float(result.jahresstunden)
            oee = float(rate_input.oee)
            tage = float(rate_input.arbeitstage_pro_jahr)
            schichten = float(rate_input.schichten_pro_tag)
            stunden = float(rate_input.stunden_pro_schicht)
            gross = tage * schichten * stunden
        except MachineRateValidationError:
            pass

    if gross is None and available is not None and oee is not None and oee > 0:
        gross = available / oee

    return _MachineCapacity(
        gross_hours=gross,
        oee=oee,
        available_hours=available,
        oee_in_available_hours=True,
    )


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


def _setup_aktiv(calc: SpritzgussKalkulation, maschine: Maschine) -> bool:
    ergebnis = _parse_json_dict(calc.ergebnis)
    bloecke = _parse_json_dict(calc.ergebnis_bloecke)
    fertigung = bloecke.get("fertigung") if isinstance(bloecke.get("fertigung"), dict) else {}
    if fertigung.get("setup_aktiv") is False or ergebnis.get("setup_aktiv") is False:
        return False
    setup_min = float(getattr(maschine, "setup_zeit_min", None) or 0)
    los = calc.losgroesse
    return setup_min > 0 and los is not None and int(los) >= 1


def _run_hours(volume: float, nettokapazitaet: float | None) -> float:
    if nettokapazitaet is None or nettokapazitaet <= 0 or volume <= 0:
        return 0.0
    return float(volume) / float(nettokapazitaet)


def _setup_hours(volume: float, losgroesse: int | None, setup_zeit_min: float | None) -> float:
    if volume <= 0 or losgroesse is None or int(losgroesse) < 1:
        return 0.0
    setup_min = float(setup_zeit_min or 0)
    if setup_min <= 0:
        return 0.0
    lots = math.ceil(float(volume) / float(losgroesse))
    return lots * (setup_min / 60.0)


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


def _project_year_volume_map(db: Session, project: Project) -> dict[int, float]:
    from app.services.hierarchy import calculate_project_volume

    rows = db.scalars(
        select(ProgramVolume)
        .where(ProgramVolume.program_id == project.program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    ).all()
    out: dict[int, float] = {}
    for vol in rows:
        year = int(vol.calendar_year)
        if year not in UTILIZATION_YEARS:
            continue
        pv = calculate_project_volume(vol.vehicle_volume, project.quantity_per_vehicle)
        if pv > 0:
            out[year] = float(pv)
    return out


def _add_yearly_demand(
    agg: dict[int, _MachineAgg],
    *,
    maschine: Maschine,
    calc: SpritzgussKalkulation,
    project_id: int,
    project_name: str,
    source_type: str,
    source_label: str,
    year_volumes: dict[int, float],
    quantity_factor: float,
    nettokapazitaet: float | None,
) -> None:
    setup_min = float(maschine.setup_zeit_min or 0) if _setup_aktiv(calc, maschine) else 0.0
    los = int(calc.losgroesse) if calc.losgroesse is not None else None
    bucket_root = agg.setdefault(maschine.id, _MachineAgg())

    for year in UTILIZATION_YEARS:
        raw_vol = year_volumes.get(year, 0.0)
        volume = raw_vol * float(quantity_factor)
        run = _run_hours(volume, nettokapazitaet)
        setup = _setup_hours(volume, los, setup_min) if setup_min > 0 else 0.0
        if run <= 0 and setup <= 0:
            continue
        yb = bucket_root.year_bucket(year)
        yb.run_hours += run
        yb.setup_hours += setup
        yb.project_ids.add(project_id)
        bucket_root.lines.append(
            _DemandLine(
                project_id=project_id,
                project_name=project_name,
                source_type=source_type,
                source_label=source_label,
                calendar_year=year,
                jahresstueckzahl=volume,
                run_hours=run,
                setup_hours=setup,
            )
        )


def _process_calc_link(
    db: Session,
    agg: dict[int, _MachineAgg],
    *,
    calc: SpritzgussKalkulation,
    maschine: Maschine,
    project: Project,
    source_type: str,
    source_label: str,
    year_volumes: dict[int, float],
    quantity_factor: float,
    plant_machine_ids: set[int],
) -> None:
    if calc.maschine_id is None or int(calc.maschine_id) not in plant_machine_ids:
        return
    if not calc.aktiv:
        return
    netto = _resolve_nettokapazitaet(calc)
    _add_yearly_demand(
        agg,
        maschine=maschine,
        calc=calc,
        project_id=project.id,
        project_name=project.name,
        source_type=source_type,
        source_label=source_label,
        year_volumes=year_volumes,
        quantity_factor=quantity_factor,
        nettokapazitaet=netto,
    )


def _collect_project_demand(
    db: Session,
    *,
    project: Project,
    plant_machines: dict[int, Maschine],
    agg: dict[int, _MachineAgg],
) -> None:
    plant_machine_ids = set(plant_machines.keys())
    baugruppen = _baugruppen_for_project(db, project.id)
    linked_sg_ids = _spritzguss_ids_in_baugruppen(db, [b.id for b in baugruppen])
    year_volumes = _project_year_volume_map(db, project)

    standalone_rows = list(
        db.scalars(
            select(SpritzgussKalkulation).where(
                SpritzgussKalkulation.project_id == project.id,
                SpritzgussKalkulation.aktiv.is_(True),
                SpritzgussKalkulation.maschine_id.is_not(None),
            )
        ).all()
    )
    for calc in standalone_rows:
        if calc.id in linked_sg_ids:
            continue
        maschine = plant_machines.get(int(calc.maschine_id or 0))
        if maschine is None:
            continue
        _process_calc_link(
            db,
            agg,
            calc=calc,
            maschine=maschine,
            project=project,
            source_type="einzelteil",
            source_label=calc.teilebezeichnung or calc.teilenummer,
            year_volumes=year_volumes,
            quantity_factor=1.0,
            plant_machine_ids=plant_machine_ids,
        )

    for bg in baugruppen:
        bg_year_volumes = year_volumes
        legacy_links = list(
            db.scalars(
                select(BaugruppeSpritzgussZuordnung).where(
                    BaugruppeSpritzgussZuordnung.baugruppe_id == bg.id
                )
            ).all()
        )
        for link in legacy_links:
            calc = db.get(SpritzgussKalkulation, link.spritzguss_kalkulation_id)
            if calc is None:
                continue
            maschine = plant_machines.get(int(calc.maschine_id or 0))
            if maschine is None:
                continue
            _process_calc_link(
                db,
                agg,
                calc=calc,
                maschine=maschine,
                project=project,
                source_type="baugruppe",
                source_label=f"{bg.name} → {calc.teilebezeichnung or calc.teilenummer}",
                year_volumes=bg_year_volumes,
                quantity_factor=float(link.menge or 1.0),
                plant_machine_ids=plant_machine_ids,
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
            if calc is None:
                continue
            maschine = plant_machines.get(int(calc.maschine_id or 0))
            if maschine is None:
                continue
            factor = float(pos.quantity or 1.0) * float(pos.quantity_factor or 1.0)
            _process_calc_link(
                db,
                agg,
                calc=calc,
                maschine=maschine,
                project=project,
                source_type="baugruppe",
                source_label=f"{bg.name} → {calc.teilebezeichnung or calc.teilenummer}",
                year_volumes=bg_year_volumes,
                quantity_factor=factor,
                plant_machine_ids=plant_machine_ids,
            )


def _ratio_pct(numerator: float, denominator: float | None) -> float | None:
    if denominator is None or denominator <= 0:
        return None
    return numerator / denominator * 100.0


def _year_row_dict(
    *,
    year: int,
    maschine: Maschine,
    capacity: _MachineCapacity,
    bucket: _YearBucket,
    lines: list[_DemandLine],
) -> dict:
    required = bucket.run_hours + bucket.setup_hours
    available = capacity.available_hours
    util = _ratio_pct(required, available) if available is not None and available > 0 else None
    remaining = (available - required) if available is not None and available > 0 else None
    overloaded = bool(available is not None and available > 0 and required > available)
    year_lines = [ln for ln in lines if ln.calendar_year == year]
    return {
        "year": year,
        "calendar_year": year,
        "machine_id": maschine.id,
        "maschine_id": maschine.id,
        "machine_name": maschine.bezeichnung,
        "maschinen_nr": maschine.maschinen_nr,
        "gross_hours": round(capacity.gross_hours, 6) if capacity.gross_hours is not None else None,
        "oee": round(capacity.oee, 6) if capacity.oee is not None else None,
        "oee_in_available_hours": capacity.oee_in_available_hours,
        "available_hours": round(available, 6) if available is not None else None,
        "run_hours": round(bucket.run_hours, 6),
        "setup_hours": round(bucket.setup_hours, 6),
        "required_hours": round(required, 6),
        "utilization_pct": round(util, 6) if util is not None else None,
        "utilization_percent": round(util, 6) if util is not None else None,
        "remaining_hours": round(remaining, 6) if remaining is not None else None,
        "rest_capacity_hours": round(remaining, 6) if remaining is not None else None,
        "overload_hours": round(max(0.0, required - available), 6)
        if available is not None and available > 0 and required > available
        else None,
        "is_overloaded": overloaded,
        "overloaded": overloaded,
        "has_demand": required > 0,
        "project_ids": sorted(bucket.project_ids),
        "projects": [
            {
                "project_id": ln.project_id,
                "project_name": ln.project_name,
                "source_type": ln.source_type,
                "source_label": ln.source_label,
                "jahresstueckzahl": round(ln.jahresstueckzahl, 4),
                "run_hours": round(ln.run_hours, 6),
                "setup_hours": round(ln.setup_hours, 6),
                "required_hours": round(ln.required_hours, 6),
            }
            for ln in year_lines
        ],
    }


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
    plant_machines = {m.id: m for m in machines}

    agg: dict[int, _MachineAgg] = {}
    if pids:
        for pid in pids:
            project = db.get(Project, pid)
            if project is None:
                continue
            _collect_project_demand(
                db,
                project=project,
                plant_machines=plant_machines,
                agg=agg,
            )

    yearly_rows: list[dict] = []
    machine_rows: list[dict] = []
    capacities: dict[int, _MachineCapacity] = {
        m.id: _resolve_machine_capacity(m, werk) for m in machines
    }

    for maschine in machines:
        capacity = capacities[maschine.id]
        bucket_agg = agg.get(maschine.id, _MachineAgg())
        machine_yearly: list[dict] = []

        for year in UTILIZATION_YEARS:
            yb = bucket_agg.yearly.get(year, _YearBucket())
            row = _year_row_dict(
                year=year,
                maschine=maschine,
                capacity=capacity,
                bucket=yb,
                lines=bucket_agg.lines,
            )
            machine_yearly.append(row)
            yearly_rows.append(row)

        total_required = sum(r["required_hours"] for r in machine_yearly)
        total_run = sum(r["run_hours"] for r in machine_yearly)
        total_setup = sum(r["setup_hours"] for r in machine_yearly)
        available = capacity.available_hours
        years_with_demand = sum(1 for r in machine_yearly if r["has_demand"])

        machine_rows.append(
            {
                "maschine_id": maschine.id,
                "maschinen_nr": maschine.maschinen_nr,
                "bezeichnung": maschine.bezeichnung,
                "werk_id": maschine.werk_id,
                "werk_name": werk.name,
                "gross_hours": capacity.gross_hours,
                "oee": capacity.oee,
                "oee_in_available_hours": capacity.oee_in_available_hours,
                "available_hours": available,
                "run_hours": round(total_run, 6),
                "setup_hours": round(total_setup, 6),
                "required_hours": round(total_required, 6),
                "utilization_pct": None,
                "rest_capacity_hours": None,
                "overload_hours": None,
                "is_overloaded": False,
                "has_demand": total_required > 0,
                "years_with_demand": years_with_demand,
                "yearly_breakdown": machine_yearly,
                "projects": [],
            }
        )

    return {
        "plant_id": plant_id,
        "plant_name": werk.name,
        "customer_id": customer_id,
        "program_id": program_id,
        "project_ids": pids,
        "no_projects_selected": len(pids) == 0,
        "years": UTILIZATION_YEARS,
        "planning_period": {
            "label": "Jahresauslastung 2026–2040",
            "basis": (
                "Pro Jahresstückzahl aus Projektmengenprofil; verfügbare Stunden = Brutto × OEE "
                "(OEE bereits in Maschine.jahresstunden); Bedarf = Laufzeit + Rüstzeit"
            ),
            "available_hours_per_machine_year": capacities[machines[0].id].available_hours
            if len(machines) == 1
            else None,
            "oee_in_available_hours": True,
        },
        "summary": _build_summary(yearly_rows, len(machines)),
        "yearly_rows": yearly_rows,
        "machines": machine_rows,
    }


def _build_summary(yearly_rows: list[dict], machine_count: int) -> dict:
    util_pcts = [
        float(r["utilization_pct"])
        for r in yearly_rows
        if r.get("utilization_pct") is not None and r.get("has_demand")
    ]
    overloaded = sum(1 for r in yearly_rows if r.get("is_overloaded"))
    machines_with_demand = len({r["machine_id"] for r in yearly_rows if r.get("has_demand")})
    max_pct: float | None = None
    max_mid: int | None = None
    max_name: str | None = None
    max_year: int | None = None
    for r in yearly_rows:
        u = r.get("utilization_pct")
        if u is None:
            continue
        if max_pct is None or float(u) > max_pct:
            max_pct = float(u)
            max_mid = int(r["machine_id"])
            max_name = str(r["machine_name"])
            max_year = int(r["year"])

    total_req = sum(float(r["required_hours"]) for r in yearly_rows)
    total_avail = sum(
        float(r["available_hours"])
        for r in yearly_rows
        if r.get("available_hours") is not None and float(r["available_hours"]) > 0
    )
    plant_util = _ratio_pct(total_req, total_avail if total_avail > 0 else None)

    return {
        "machine_count": machine_count,
        "machines_with_demand": machines_with_demand,
        "overloaded_count": overloaded,
        "average_utilization_pct": round(sum(util_pcts) / len(util_pcts), 6) if util_pcts else None,
        "plant_utilization_pct": round(plant_util, 6) if plant_util is not None else None,
        "max_utilization_pct": round(max_pct, 6) if max_pct is not None else None,
        "max_utilization_maschine_id": max_mid,
        "max_utilization_maschine_name": max_name,
        "max_utilization_year": max_year,
    }


def build_maschinen_auslastung_summary_for_year(
    result: dict,
    *,
    calendar_year: int,
) -> dict:
    """Hilfsfunktion für KPI-Aggregation zu einem Kalenderjahr (Frontend/Tests)."""
    rows = [r for r in result.get("yearly_rows", []) if int(r["year"]) == calendar_year]
    return _build_summary(rows, int(result.get("summary", {}).get("machine_count", 0)))
