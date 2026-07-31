from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import lohnkosten as lohnkosten_crud
from app.database import get_db
from app.models.user import User
from app.schemas.lohnkosten import LohnkostenCreate, LohnkostenRead, LohnkostenUpdate

router = APIRouter(prefix="/lohnkosten", tags=["Lohnkosten"])


@router.get("", response_model=list[LohnkostenRead])
def list_lohnkosten(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return lohnkosten_crud.lohnkosten.get_multi(db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=LohnkostenRead)
def get_lohnkosten(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = lohnkosten_crud.lohnkosten.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lohnkosten nicht gefunden")
    return item


@router.post("", response_model=LohnkostenRead, status_code=status.HTTP_201_CREATED)
def create_lohnkosten(
    item_in: LohnkostenCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    return lohnkosten_crud.lohnkosten.create(db, item_in)


@router.put("/{item_id}", response_model=LohnkostenRead)
def update_lohnkosten(
    item_id: int,
    item_in: LohnkostenUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = lohnkosten_crud.lohnkosten.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lohnkosten nicht gefunden")
    return lohnkosten_crud.lohnkosten.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lohnkosten(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = lohnkosten_crud.lohnkosten.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lohnkosten nicht gefunden")
    lohnkosten_crud.lohnkosten.delete(db, item)
