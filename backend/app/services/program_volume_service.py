"""Programmstückzahlen: SOP/EOP-Jahreszeitraum und Bulk-Speicherung."""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.program import Program, ProgramVolume
from app.services.hierarchy import validate_calendar_year, validate_vehicle_volume


def calendar_years_from_sop_eop(sop: date | None, eop: date | None) -> list[int]:
    if sop is None or eop is None:
        return []
    start = sop.year
    end = eop.year
    if start > end:
        return []
    return list(range(start, end + 1))


def _load_saved_volumes(db: Session, program_id: int) -> dict[int, ProgramVolume]:
    rows = db.scalars(
        select(ProgramVolume)
        .where(ProgramVolume.program_id == program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    ).all()
    return {row.calendar_year: row for row in rows}


def build_program_volume_profile(db: Session, program_id: int) -> dict:
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")

    saved = _load_saved_volumes(db, program_id)
    sop_years = set(calendar_years_from_sop_eop(program.sop, program.eop))
    all_years = sorted(set(saved.keys()) | sop_years)

    rows = []
    for year in all_years:
        volume = saved.get(year)
        rows.append(
            {
                "id": volume.id if volume else None,
                "calendar_year": year,
                "vehicle_volume": volume.vehicle_volume if volume else 0,
                "in_sop_eop_range": year in sop_years,
            }
        )

    return {
        "program_id": program_id,
        "sop": program.sop,
        "eop": program.eop,
        "sop_eop_years": sorted(sop_years),
        "rows": rows,
    }


def generate_years_from_sop_eop(db: Session, program_id: int) -> list[int]:
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")

    years = calendar_years_from_sop_eop(program.sop, program.eop)
    if not years:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="SOP und EOP müssen gesetzt sein, um Jahreszeilen zu erzeugen.",
        )

    saved = _load_saved_volumes(db, program_id)
    for year in years:
        if year not in saved:
            db.add(ProgramVolume(program_id=program_id, calendar_year=year, vehicle_volume=0))

    db.flush()
    return years


def years_with_data_outside_sop_eop(
    db: Session,
    program_id: int,
    *,
    sop: date | None,
    eop: date | None,
) -> list[int]:
    saved = _load_saved_volumes(db, program_id)
    new_range = set(calendar_years_from_sop_eop(sop, eop))
    return sorted(
        year
        for year, row in saved.items()
        if year not in new_range and row.vehicle_volume > 0
    )


def bulk_save_program_volumes(
    db: Session,
    program_id: int,
    items: list[dict],
) -> list[ProgramVolume]:
    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")

    if not items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mindestens eine Jahresmenge muss übergeben werden.",
        )

    years_in_payload: list[int] = []
    for item in items:
        years_in_payload.append(validate_calendar_year(int(item["calendar_year"])))

    if len(years_in_payload) != len(set(years_in_payload)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Doppelte Kalenderjahre sind nicht erlaubt.",
        )

    saved = _load_saved_volumes(db, program_id)
    for item in items:
        year = validate_calendar_year(int(item["calendar_year"]))
        vehicle_volume = validate_vehicle_volume(int(item["vehicle_volume"]))
        if year in saved:
            saved[year].vehicle_volume = vehicle_volume
        else:
            row = ProgramVolume(program_id=program_id, calendar_year=year, vehicle_volume=vehicle_volume)
            db.add(row)
            saved[year] = row

    db.flush()
    return list(
        db.scalars(
            select(ProgramVolume)
            .where(ProgramVolume.program_id == program_id)
            .order_by(ProgramVolume.calendar_year.asc())
        ).all()
    )


def delete_program_volume_for_year(db: Session, program_id: int, calendar_year: int) -> None:
    row = db.scalar(
        select(ProgramVolume).where(
            ProgramVolume.program_id == program_id,
            ProgramVolume.calendar_year == calendar_year,
        )
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Keine Stückzahl für Kalenderjahr {calendar_year} gefunden.",
        )
    db.delete(row)
