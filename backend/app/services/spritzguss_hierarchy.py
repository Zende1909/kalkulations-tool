"""Auflösung der Kunde → Programm → Projekt Hierarchie für Kalkulationen."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.models.program import Program, ProgramVolume
from app.models.project import Project
from app.services.hierarchy import calculate_project_volume, validate_calendar_year


def resolve_hierarchy_for_spritzguss(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    project_id: int,
    calculation_year: int | None = None,
) -> dict:
    if customer_id < 1 or program_id < 1 or project_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ungültige Hierarchie-IDs.",
        )

    customer = db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kunde nicht gefunden")

    program = db.get(Program, program_id)
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")
    if program.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programm gehört nicht zum ausgewählten Kunden.",
        )

    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden")
    if project.program_id != program_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt gehört nicht zum ausgewählten Programm.",
        )

    result: dict = {
        "customer_id": customer_id,
        "program_id": program_id,
        "project_id": project_id,
        "kunde": customer.name,
        "projekt": project.name,
    }

    if calculation_year is not None:
        try:
            validate_calendar_year(calculation_year)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        volume_row = db.scalar(
            select(ProgramVolume).where(
                ProgramVolume.program_id == program_id,
                ProgramVolume.calendar_year == calculation_year,
            )
        )
        if volume_row:
            project_volume = calculate_project_volume(volume_row.vehicle_volume, project.quantity_per_vehicle)
            jahresstueckzahl = int(round(project_volume))
            if jahresstueckzahl < 0:
                jahresstueckzahl = 0
            result["calculation_year"] = calculation_year
            result["project_volume"] = project_volume
            result["jahresstueckzahl"] = jahresstueckzahl

    return result
