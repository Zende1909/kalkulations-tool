from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import zuschlagssatz as zuschlagssatz_crud
from app.database import get_db
from app.models.user import User
from app.schemas.zuschlagssatz import ZuschlagssatzCreate, ZuschlagssatzRead, ZuschlagssatzUpdate

router = APIRouter(prefix="/zuschlagssaetze", tags=["Zuschlagssätze"])


@router.get("/", response_model=list[ZuschlagssatzRead])
def list_zuschlagssaetze(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return zuschlagssatz_crud.zuschlagssatz.get_multi(db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=ZuschlagssatzRead)
def get_zuschlagssatz(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = zuschlagssatz_crud.zuschlagssatz.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zuschlagssatz nicht gefunden")
    return item


@router.post("/", response_model=ZuschlagssatzRead, status_code=status.HTTP_201_CREATED)
def create_zuschlagssatz(
    item_in: ZuschlagssatzCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    return zuschlagssatz_crud.zuschlagssatz.create(db, item_in)


@router.put("/{item_id}", response_model=ZuschlagssatzRead)
def update_zuschlagssatz(
    item_id: int,
    item_in: ZuschlagssatzUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = zuschlagssatz_crud.zuschlagssatz.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zuschlagssatz nicht gefunden")
    return zuschlagssatz_crud.zuschlagssatz.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zuschlagssatz(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = zuschlagssatz_crud.zuschlagssatz.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zuschlagssatz nicht gefunden")
    zuschlagssatz_crud.zuschlagssatz.delete(db, item)
