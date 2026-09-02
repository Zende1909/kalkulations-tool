from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import material as material_crud
from app.crud import materialgruppe as materialgruppe_crud
from app.database import get_db
from app.models.user import User
from app.schemas.material import (
    MaterialCreate,
    MaterialGruppeRead,
    MaterialRead,
    MaterialUpdate,
)
from app.services.material_thermik import alle_defaults_db

router = APIRouter(prefix="/materialien", tags=["Materialien"])


def _validate_materialgruppe(db: Session, gruppe: str | None) -> str | None:
    if gruppe is None:
        return None
    row = materialgruppe_crud.materialgruppe.get_by_gruppe(db, gruppe)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unbekannte Materialgruppe '{gruppe}'. Bitte in den Stammdaten anlegen.",
        )
    if not row.aktiv:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Materialgruppe '{gruppe}' ist deaktiviert.",
        )
    return row.gruppe


@router.get("", response_model=list[MaterialRead])
def list_materialien(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return material_crud.material.get_multi(db, skip=skip, limit=limit)


@router.get("/materialgruppen", response_model=list[MaterialGruppeRead])
def list_materialgruppen(
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Auswählbare Materialgruppen samt Kennwerten (Abwärtskompatibilität)."""
    return [d.as_dict() for d in alle_defaults_db(db)]


@router.get("/{item_id}", response_model=MaterialRead)
def get_material(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = material_crud.material.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material nicht gefunden")
    return item


@router.post("", response_model=MaterialRead, status_code=status.HTTP_201_CREATED)
def create_material(
    item_in: MaterialCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    gruppe = _validate_materialgruppe(db, item_in.materialgruppe)
    payload = item_in.model_copy(update={"materialgruppe": gruppe})
    return material_crud.material.create(db, payload)


@router.put("/{item_id}", response_model=MaterialRead)
def update_material(
    item_id: int,
    item_in: MaterialUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = material_crud.material.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material nicht gefunden")
    update_data = item_in.model_dump(exclude_unset=True)
    if "materialgruppe" in update_data:
        update_data["materialgruppe"] = _validate_materialgruppe(db, update_data["materialgruppe"])
    payload = MaterialUpdate(**update_data)
    return material_crud.material.update(db, item, payload)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_material(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = material_crud.material.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material nicht gefunden")
    material_crud.material.delete(db, item)
