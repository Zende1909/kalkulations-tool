from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import maschine as maschine_crud
from app.database import get_db
from app.models.user import User
from app.schemas.maschine import MaschineCreate, MaschineRead, MaschineUpdate

router = APIRouter(prefix="/maschinen", tags=["Maschinen"])


@router.get("/", response_model=list[MaschineRead])
def list_maschinen(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return maschine_crud.maschine.get_multi(db, skip=skip, limit=limit)


@router.get("/{item_id}", response_model=MaschineRead)
def get_maschine(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = maschine_crud.maschine.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden")
    return item


@router.post("/", response_model=MaschineRead, status_code=status.HTTP_201_CREATED)
def create_maschine(
    item_in: MaschineCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    return maschine_crud.maschine.create(db, item_in)


@router.put("/{item_id}", response_model=MaschineRead)
def update_maschine(
    item_id: int,
    item_in: MaschineUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = maschine_crud.maschine.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden")
    return maschine_crud.maschine.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_maschine(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = maschine_crud.maschine.get(db, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Maschine nicht gefunden")
    maschine_crud.maschine.delete(db, item)
