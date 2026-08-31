from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import program as program_crud
from app.crud import project as project_crud
from app.database import get_db
from app.models.program import Program, ProgramVolume
from app.models.project import Project
from app.models.user import User
from app.schemas.hierarchy import (
    ProjectAverageJahresstueckzahlRead,
    ProjectCreate,
    ProjectRead,
    ProjectUpdate,
    ProjectVolumeCalculation,
    ProjectVolumeProfileRead,
)
from app.services.hierarchy import calculate_project_volume, validate_calendar_year
from app.services.project_volume_service import (
    average_jahresstueckzahl_for_project,
    build_project_volume_profile,
)

router = APIRouter(prefix="/projects", tags=["Projekte"])


def _get_project_or_404(db: Session, project_id: int) -> Project:
    if project_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Projekt-ID")
    item = project_crud.project.get(db, project_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projekt nicht gefunden")
    return item


def _get_program_or_404(db: Session, program_id: int) -> None:
    if program_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Programm-ID")
    item = program_crud.program.get(db, program_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    program_id: int | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Project)
    if program_id is not None:
        if program_id < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Programm-ID")
        stmt = stmt.where(Project.program_id == program_id)
    if customer_id is not None:
        if customer_id < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Kunden-ID")
        stmt = stmt.join(Program, Program.id == Project.program_id).where(
            Program.customer_id == customer_id
        )
    if active is not None:
        stmt = stmt.where(Project.active.is_(active))
    if status is not None:
        from app.models.project import PROJECT_STATUSES

        if status not in PROJECT_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ungültiger Projektstatus",
            )
        stmt = stmt.where(Project.status == status)
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Project.name.ilike(term), Project.project_number.ilike(term))
        )
    stmt = stmt.order_by(Project.name.asc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{item_id}", response_model=ProjectRead)
def get_project(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return _get_project_or_404(db, item_id)


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    item_in: ProjectCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_program_or_404(db, item_in.program_id)
    return project_crud.project.create(db, item_in)


@router.put("/{item_id}", response_model=ProjectRead)
def update_project(
    item_id: int,
    item_in: ProjectUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_project_or_404(db, item_id)
    if item_in.program_id is not None:
        _get_program_or_404(db, item_in.program_id)
    return project_crud.project.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_project(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_project_or_404(db, item_id)
    project_crud.project.update(db, item, ProjectUpdate(active=False))


@router.get("/{project_id}/volume-profile", response_model=ProjectVolumeProfileRead)
def get_project_volume_profile(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_project_or_404(db, project_id)
    return build_project_volume_profile(db, project_id)


@router.get(
    "/{project_id}/average-jahresstueckzahl",
    response_model=ProjectAverageJahresstueckzahlRead,
)
def get_average_jahresstueckzahl(
    project_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Durchschnitt der Projektstückzahlen über alle hinterlegten Jahre, aufgerundet (ceil)."""
    _get_project_or_404(db, project_id)
    result = average_jahresstueckzahl_for_project(db, project_id)
    return ProjectAverageJahresstueckzahlRead(**result.to_dict())


@router.get("/{project_id}/calculated-volume", response_model=ProjectVolumeCalculation)
def get_calculated_volume(
    project_id: int,
    calendar_year: int = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    try:
        validate_calendar_year(calendar_year)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    project = _get_project_or_404(db, project_id)
    volume_row = db.scalar(
        select(ProgramVolume).where(
            ProgramVolume.program_id == project.program_id,
            ProgramVolume.calendar_year == calendar_year,
        )
    )
    if not volume_row:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Keine Fahrzeugstückzahl für Kalenderjahr {calendar_year} hinterlegt.",
        )

    return ProjectVolumeCalculation(
        project_id=project.id,
        program_id=project.program_id,
        calendar_year=calendar_year,
        vehicle_volume=volume_row.vehicle_volume,
        quantity_per_vehicle=project.quantity_per_vehicle,
        project_volume=calculate_project_volume(
            volume_row.vehicle_volume,
            project.quantity_per_vehicle,
        ),
    )
