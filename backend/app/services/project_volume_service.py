"""Berechnetes Projektmengenprofil über die Projektlaufzeit."""

from __future__ import annotations

import math
from dataclasses import dataclass

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


@dataclass(frozen=True)
class AverageJahresstueckzahl:
    """Durchschnittliche Jahresstückzahl aus dem Projektmengenprofil."""

    project_id: int
    year_count: int
    sum_project_volume: float
    average_raw: float | None
    jahresstueckzahl: int | None
    has_volumes: bool

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "year_count": self.year_count,
            "sum_project_volume": round(self.sum_project_volume, 2),
            "average_raw": None if self.average_raw is None else round(self.average_raw, 4),
            "jahresstueckzahl": self.jahresstueckzahl,
            "has_volumes": self.has_volumes,
        }


def average_jahresstueckzahl_for_project(db: Session, project_id: int) -> AverageJahresstueckzahl:
    """ceil(Summe Projektstückzahlen / Anzahl Jahre) – ohne erfundene Defaults.

    Quelle je Jahr: ProgramVolume.vehicle_volume × Project.quantity_per_vehicle
    (wie im volume-profile).
    """
    profile = build_project_volume_profile(db, project_id)
    rows = profile["rows"]
    if not rows:
        return AverageJahresstueckzahl(
            project_id=project_id,
            year_count=0,
            sum_project_volume=0.0,
            average_raw=None,
            jahresstueckzahl=None,
            has_volumes=False,
        )
    total = float(sum(float(r["project_volume"]) for r in rows))
    count = len(rows)
    average = total / count
    return AverageJahresstueckzahl(
        project_id=project_id,
        year_count=count,
        sum_project_volume=total,
        average_raw=average,
        jahresstueckzahl=int(math.ceil(average)),
        has_volumes=True,
    )
