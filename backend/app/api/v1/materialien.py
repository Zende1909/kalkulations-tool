from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import material as material_crud
from app.database import get_db
from app.models.user import User
from app.schemas.material import MaterialCreate, MaterialRead, MaterialUpdate

router = APIRouter(prefix="/materialien", tags=["Materialien"])


@router.get("", response_model=list[MaterialRead])
def list_materialien(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return material_crud.material.get_multi(db, skip=skip, limit=limit)


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
    return material_crud.material.create(db, item_in)


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
    return material_crud.material.update(db, item, item_in)


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
