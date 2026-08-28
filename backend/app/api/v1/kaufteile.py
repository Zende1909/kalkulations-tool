from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import kaufteil as kaufteil_crud
from app.database import get_db
from app.models.kaufteil import Kaufteil
from app.models.program import Program
from app.models.project import Project
from app.models.user import User
from app.schemas.baugruppe import KaufteilCreate, KaufteilRead, KaufteilUpdate

router = APIRouter(prefix="/kaufteile", tags=["Kaufteile"])


@router.get("", response_model=list[KaufteilRead])
def list_kaufteile(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    nur_aktiv: bool = Query(False),
    customer_id: int | None = Query(None),
    program_id: int | None = Query(None),
    project_id: int | None = Query(None),
    include_standard: bool = Query(
        True,
        description=(
            "Bei gesetztem project_id zusätzlich Standardkaufteile (project_id IS NULL) liefern"
        ),
    ),
    strict_project: bool = Query(
        False,
        description="Nur Kaufteile mit exakt project_id (ohne Standardkaufteile)",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Listet Kaufteile. Filter Kunde → Programm → Projekt sind optional.

    Ohne Filter bleibt das bisherige Verhalten (volle Liste) erhalten.
    Mit project_id und include_standard (Standard): Projekt-Kaufteile plus Standardkaufteile.
    Mit strict_project=True nur exakte Projektübereinstimmung.
    """
    stmt = select(Kaufteil)
    if nur_aktiv:
        stmt = stmt.where(Kaufteil.aktiv.is_(True))
    if project_id is not None:
        if strict_project or not include_standard:
            stmt = stmt.where(Kaufteil.project_id == project_id)
        else:
            stmt = stmt.where(
                or_(Kaufteil.project_id == project_id, Kaufteil.project_id.is_(None))
            )
    elif program_id is not None:
        stmt = stmt.where(Kaufteil.program_id == program_id)
    elif customer_id is not None:
        # Über Programm-Zuordnung oder direkte customer_id
        stmt = stmt.outerjoin(Program, Kaufteil.program_id == Program.id).where(
            (Kaufteil.customer_id == customer_id) | (Program.customer_id == customer_id)
        )
    stmt = stmt.offset(skip).limit(limit).order_by(Kaufteil.id)
    return list(db.scalars(stmt).unique().all())


@router.get("/{item_id}", response_model=KaufteilRead)
def get_kaufteil(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = kaufteil_crud.kaufteil.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kaufteil nicht gefunden")
    return item


def _apply_project_hierarchy(db: Session, data: dict) -> dict:
    """Leitet Kunde/Programm aus project_id ab; Standardkaufteile ohne project_id."""
    if "project_id" not in data:
        return data
    project_id = data.get("project_id")
    if project_id is None:
        data["customer_id"] = None
        data["program_id"] = None
        return data
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=400, detail="Projekt nicht gefunden")
    data["program_id"] = project.program_id
    program = db.get(Program, project.program_id) if project.program_id else None
    data["customer_id"] = program.customer_id if program else None
    return data


def _validate_hierarchy(db: Session, body: KaufteilCreate | KaufteilUpdate) -> None:
    data = body.model_dump(exclude_unset=True) if isinstance(body, KaufteilUpdate) else body.model_dump()
    project_id = data.get("project_id")
    program_id = data.get("program_id")
    customer_id = data.get("customer_id")

    if project_id is not None:
        project = db.get(Project, project_id)
        if not project:
            raise HTTPException(status_code=400, detail="Projekt nicht gefunden")
        if program_id is not None and project.program_id != program_id:
            raise HTTPException(status_code=400, detail="Projekt gehört nicht zum gewählten Programm")
        program = db.get(Program, project.program_id)
        if customer_id is not None and program and program.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Projekt gehört nicht zum gewählten Kunden")

    if program_id is not None:
        program = db.get(Program, program_id)
        if not program:
            raise HTTPException(status_code=400, detail="Programm nicht gefunden")
        if customer_id is not None and program.customer_id != customer_id:
            raise HTTPException(status_code=400, detail="Programm gehört nicht zum gewählten Kunden")


@router.post("", response_model=KaufteilRead, status_code=status.HTTP_201_CREATED)
def create_kaufteil(
    body: KaufteilCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    payload = _apply_project_hierarchy(db, body.model_dump())
    merged = KaufteilCreate(**payload)
    _validate_hierarchy(db, merged)
    return kaufteil_crud.kaufteil.create(db, merged)


@router.put("/{item_id}", response_model=KaufteilRead)
def update_kaufteil(
    item_id: int,
    body: KaufteilUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = kaufteil_crud.kaufteil.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kaufteil nicht gefunden")
    # Merge for hierarchy check
    merged_dict = {
        "customer_id": item.customer_id,
        "program_id": item.program_id,
        "project_id": item.project_id,
        **body.model_dump(exclude_unset=True),
    }
    if "project_id" in body.model_dump(exclude_unset=True):
        merged_dict = _apply_project_hierarchy(db, merged_dict)
    merged = KaufteilUpdate(**merged_dict)
    _validate_hierarchy(db, merged)
    update_payload = KaufteilUpdate(**{**body.model_dump(exclude_unset=True)})
    if "project_id" in body.model_dump(exclude_unset=True):
        update_payload = KaufteilUpdate(
            **{
                **body.model_dump(exclude_unset=True),
                "customer_id": merged_dict.get("customer_id"),
                "program_id": merged_dict.get("program_id"),
            }
        )
    return kaufteil_crud.kaufteil.update(db, item, update_payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kaufteil(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = kaufteil_crud.kaufteil.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kaufteil nicht gefunden")
    kaufteil_crud.kaufteil.update(
        db,
        item,
        KaufteilUpdate(aktiv=False),
    )
