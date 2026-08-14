from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import customer as customer_crud
from app.crud import program as program_crud
from app.database import get_db
from app.models.program import Program, ProgramVolume
from app.models.user import User
from app.models.project import Project
from app.schemas.hierarchy import (
    ProgramCreate,
    ProgramRead,
    ProgramUpdate,
    ProgramVolumeRead,
    ProjectRead,
)

router = APIRouter(prefix="/programs", tags=["Programme"])


def _get_program_or_404(db: Session, program_id: int) -> Program:
    if program_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Programm-ID")
    item = program_crud.program.get(db, program_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")
    return item


def _get_customer_or_404(db: Session, customer_id: int):
    if customer_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Kunden-ID")
    item = customer_crud.customer.get(db, customer_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kunde nicht gefunden")
    return item


@router.get("", response_model=list[ProgramRead])
def list_programs(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    customer_id: int | None = Query(default=None),
    search: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Program)
    if customer_id is not None:
        if customer_id < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Kunden-ID")
        stmt = stmt.where(Program.customer_id == customer_id)
    if active is not None:
        stmt = stmt.where(Program.active.is_(active))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Program.name.ilike(term), Program.program_number.ilike(term))
        )
    stmt = stmt.order_by(Program.name.asc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{item_id}", response_model=ProgramRead)
def get_program(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return _get_program_or_404(db, item_id)


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
def create_program(
    item_in: ProgramCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_customer_or_404(db, item_in.customer_id)
    return program_crud.program.create(db, item_in)


@router.put("/{item_id}", response_model=ProgramRead)
def update_program(
    item_id: int,
    item_in: ProgramUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_program_or_404(db, item_id)
    if item_in.customer_id is not None:
        _get_customer_or_404(db, item_in.customer_id)
    return program_crud.program.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_program(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_program_or_404(db, item_id)
    program_crud.program.update(db, item, ProgramUpdate(active=False))


@router.get("/{program_id}/projects", response_model=list[ProjectRead])
def list_program_projects(
    program_id: int,
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_program_or_404(db, program_id)
    stmt = select(Project).where(Project.program_id == program_id)
    if active is not None:
        stmt = stmt.where(Project.active.is_(active))
    stmt = stmt.order_by(Project.name.asc())
    return list(db.scalars(stmt).all())


@router.get("/{program_id}/volumes", response_model=list[ProgramVolumeRead])
def list_program_volumes(
    program_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_program_or_404(db, program_id)
    stmt = (
        select(ProgramVolume)
        .where(ProgramVolume.program_id == program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    )
    return list(db.scalars(stmt).all())


@router.get("/{program_id}/available-years", response_model=list[int])
def list_available_years(
    program_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_program_or_404(db, program_id)
    stmt = (
        select(ProgramVolume.calendar_year)
        .where(ProgramVolume.program_id == program_id)
        .order_by(ProgramVolume.calendar_year.asc())
    )
    return list(db.scalars(stmt).all())
