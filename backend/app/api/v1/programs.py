from fastapi import APIRouter, Depends, HTTPException, Query, status
from datetime import date
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
    ProgramVolumeBulkSave,
    ProgramVolumeProfileRead,
    ProgramVolumeRead,
    ProjectRead,
    SopEopChangeWarning,
)
from app.services.program_volume_service import (
    bulk_save_program_volumes,
    build_program_volume_profile,
    delete_program_volume_for_year,
    generate_years_from_sop_eop,
    years_with_data_outside_sop_eop,
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
    confirm_sop_eop_shrink: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_program_or_404(db, item_id)
    if item_in.customer_id is not None:
        _get_customer_or_404(db, item_in.customer_id)

    new_sop = item_in.sop if item_in.sop is not None else item.sop
    new_eop = item_in.eop if item_in.eop is not None else item.eop
    sop_changed = item_in.sop is not None and item_in.sop != item.sop
    eop_changed = item_in.eop is not None and item_in.eop != item.eop

    if (sop_changed or eop_changed) and not confirm_sop_eop_shrink:
        outside = years_with_data_outside_sop_eop(db, item_id, sop=new_sop, eop=new_eop)
        if outside:
            years_str = ", ".join(str(y) for y in outside)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "sop_eop_shrink",
                    "years_with_data_outside_new_range": outside,
                    "message": (
                        f"Für folgende Kalenderjahre sind bereits Fahrzeugstückzahlen hinterlegt, "
                        f"die außerhalb des neuen SOP/EOP-Zeitraums liegen: {years_str}. "
                        "Bitte bestätigen Sie die Änderung oder passen Sie die Mengen an."
                    ),
                },
            )

    updated = program_crud.program.update(db, item, item_in)
    if sop_changed or eop_changed:
        generate_years_from_sop_eop(db, item_id)
        db.commit()
        db.refresh(updated)
    return updated


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


@router.get("/{program_id}/volume-profile", response_model=ProgramVolumeProfileRead)
def get_program_volume_profile(
    program_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_program_or_404(db, program_id)
    return build_program_volume_profile(db, program_id)


@router.post("/{program_id}/volume-profile/generate-years", response_model=ProgramVolumeProfileRead)
def post_generate_program_years(
    program_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_program_or_404(db, program_id)
    generate_years_from_sop_eop(db, program_id)
    db.commit()
    return build_program_volume_profile(db, program_id)


@router.put("/{program_id}/volumes/bulk", response_model=list[ProgramVolumeRead])
def put_bulk_program_volumes(
    program_id: int,
    body: ProgramVolumeBulkSave,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_program_or_404(db, program_id)
    rows = bulk_save_program_volumes(
        db,
        program_id,
        [item.model_dump() for item in body.volumes],
    )
    db.commit()
    return rows


@router.get("/{program_id}/sop-eop-change-preview", response_model=SopEopChangeWarning)
def preview_sop_eop_change(
    program_id: int,
    sop: date | None = Query(default=None),
    eop: date | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_program_or_404(db, program_id)
    outside = years_with_data_outside_sop_eop(db, program_id, sop=sop, eop=eop)
    message = ""
    if outside:
        years_str = ", ".join(str(y) for y in outside)
        message = (
            f"Für folgende Kalenderjahre sind Fahrzeugstückzahlen hinterlegt, "
            f"die außerhalb des neuen Zeitraums liegen: {years_str}."
        )
    return SopEopChangeWarning(years_with_data_outside_new_range=outside, message=message)


@router.delete("/{program_id}/volumes/{calendar_year}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program_year_volume(
    program_id: int,
    calendar_year: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _get_program_or_404(db, program_id)
    delete_program_volume_for_year(db, program_id, calendar_year)
    db.commit()
