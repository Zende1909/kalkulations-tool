"""Berechnetes Projektmengenprofil über die Projektlaufzeit."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.program import ProgramVolume
from app.models.project import Project
from app.services.hierarchy import calculate_project_volume


def build_project_volume_profile(db: Session, project_id: int) -> dict:
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden")

    volumes = db.scalars(
        select(ProgramVolume)
        .where(ProgramVolume.program_id == project.program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    ).all()

    rows: list[dict] = []
    total = 0.0
    for volume in volumes:
        project_volume = calculate_project_volume(volume.vehicle_volume, project.quantity_per_vehicle)
        total += project_volume
        rows.append(
            {
                "calendar_year": volume.calendar_year,
                "vehicle_volume": volume.vehicle_volume,
                "quantity_per_vehicle": project.quantity_per_vehicle,
                "project_volume": project_volume,
            }
        )

    return {
        "project_id": project.id,
        "program_id": project.program_id,
        "quantity_per_vehicle": project.quantity_per_vehicle,
        "total_project_volume": round(total, 2),
        "rows": rows,
    }
