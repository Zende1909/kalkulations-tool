from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import program as program_crud
from app.database import get_db
from app.models.program import ProgramVolume
from app.models.user import User
from app.schemas.hierarchy import ProgramVolumeCreate, ProgramVolumeRead, ProgramVolumeUpdate

router = APIRouter(prefix="/program-volumes", tags=["Programmstückzahlen"])


def _get_volume_or_404(db: Session, item_id: int) -> ProgramVolume:
    if item_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige ID")
    item = program_crud.program_volume.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programmstückzahl nicht gefunden")
    return item


def _get_program_or_404(db: Session, program_id: int) -> None:
    if program_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Programm-ID")
    item = program_crud.program.get(db, program_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Programm nicht gefunden")


@router.get("", response_model=list[ProgramVolumeRead])
def list_program_volumes(
    program_id: int | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(ProgramVolume)
    if program_id is not None:
        if program_id < 1:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Programm-ID")
        stmt = stmt.where(ProgramVolume.program_id == program_id)
    stmt = stmt.order_by(ProgramVolume.calendar_year.asc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{item_id}", response_model=ProgramVolumeRead)
def get_program_volume(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return _get_volume_or_404(db, item_id)


@router.post("", response_model=ProgramVolumeRead, status_code=status.HTTP_201_CREATED)
def create_program_volume(
    item_in: ProgramVolumeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_program_or_404(db, item_in.program_id)
    return program_crud.program_volume.create(db, item_in)


@router.put("/{item_id}", response_model=ProgramVolumeRead)
def update_program_volume(
    item_id: int,
    item_in: ProgramVolumeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_volume_or_404(db, item_id)
    if item_in.program_id is not None:
        _get_program_or_404(db, item_in.program_id)
    return program_crud.program_volume.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program_volume(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_volume_or_404(db, item_id)
    program_crud.program_volume.delete(db, item)
