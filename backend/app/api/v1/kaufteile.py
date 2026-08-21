from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
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
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Listet Kaufteile. Filter Kunde → Programm → Projekt sind optional.

    Ohne Filter bleibt das bisherige Verhalten (volle Liste) erhalten.
    """
    stmt = select(Kaufteil)
    if nur_aktiv:
        stmt = stmt.where(Kaufteil.aktiv.is_(True))
    if project_id is not None:
        stmt = stmt.where(Kaufteil.project_id == project_id)
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
    _validate_hierarchy(db, body)
    return kaufteil_crud.kaufteil.create(db, body)


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
    merged = KaufteilUpdate(
        **{
            **{
                "customer_id": item.customer_id,
                "program_id": item.program_id,
                "project_id": item.project_id,
            },
            **body.model_dump(exclude_unset=True),
        }
    )
    _validate_hierarchy(db, merged)
    return kaufteil_crud.kaufteil.update(db, item, body)


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
