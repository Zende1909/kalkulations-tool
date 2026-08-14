from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import kaufteil as kaufteil_crud
from app.database import get_db
from app.models.user import User
from app.schemas.baugruppe import KaufteilCreate, KaufteilRead, KaufteilUpdate

router = APIRouter(prefix="/kaufteile", tags=["Kaufteile"])


@router.get("", response_model=list[KaufteilRead])
def list_kaufteile(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    nur_aktiv: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    items = kaufteil_crud.kaufteil.get_multi(db, skip=skip, limit=limit)
    if nur_aktiv:
        return [item for item in items if item.aktiv]
    return items


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


@router.post("", response_model=KaufteilRead, status_code=status.HTTP_201_CREATED)
def create_kaufteil(
    body: KaufteilCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
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
