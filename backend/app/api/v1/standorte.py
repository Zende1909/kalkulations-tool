from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.land import Land
from app.models.user import User
from app.models.werk import Werk
from app.models.werk_zuschlag import WerkZuschlag
from app.schemas.hierarchy_plant import (
    LandCreate,
    LandRead,
    LandUpdate,
    WerkCreate,
    WerkRead,
    WerkUpdate,
    WerkZuschlagCreate,
    WerkZuschlagRead,
    WerkZuschlagUpdate,
)

router = APIRouter(tags=["Standort"])


def _raise_werk_db_error(exc: Exception) -> None:
    """Mappt DB-Fehler auf verständliche API-Antworten (kein undurchsichtiger 500)."""
    if isinstance(exc, IntegrityError):
        raise HTTPException(
            status_code=409, detail="Werk-Code bereits vergeben"
        ) from exc
    if isinstance(exc, ProgrammingError):
        msg = str(getattr(exc, "orig", exc))
        if "arbeitstage_pro_jahr" in msg or "does not exist" in msg or "existiert nicht" in msg:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Datenbankschema veraltet: bitte Migration "
                    "`alembic upgrade head` (e1a0009_werk_operating_params) ausführen."
                ),
            ) from exc
    raise exc


@router.get("/laender", response_model=list[LandRead])
def list_laender(
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return list(db.scalars(select(Land).order_by(Land.code.asc())).all())


@router.post("/laender", response_model=LandRead, status_code=status.HTTP_201_CREATED)
def create_land(
    body: LandCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    if db.scalars(select(Land).where(Land.code == body.code)).first():
        raise HTTPException(status_code=409, detail="Land-Code bereits vergeben")
    obj = Land(**body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/laender/{item_id}", response_model=LandRead)
def update_land(
    item_id: int,
    body: LandUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(Land, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Land nicht gefunden")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/werke", response_model=list[WerkRead])
def list_werke(
    land_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Werk).order_by(Werk.code.asc())
    if land_id is not None:
        stmt = stmt.where(Werk.land_id == land_id)
    return list(db.scalars(stmt).all())


@router.post("/werke", response_model=WerkRead, status_code=status.HTTP_201_CREATED)
def create_werk(
    body: WerkCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    if not db.get(Land, body.land_id):
        raise HTTPException(status_code=422, detail="Land nicht gefunden")
    if db.scalars(select(Werk).where(Werk.code == body.code)).first():
        raise HTTPException(status_code=409, detail="Werk-Code bereits vergeben")
    obj = Werk(**body.model_dump())
    db.add(obj)
    try:
        db.commit()
        db.refresh(obj)
    except (IntegrityError, ProgrammingError) as exc:
        db.rollback()
        _raise_werk_db_error(exc)
    return obj


@router.put("/werke/{item_id}", response_model=WerkRead)
def update_werk(
    item_id: int,
    body: WerkUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(Werk, item_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    updates = body.model_dump(exclude_unset=True)
    if "code" in updates:
        duplicate = db.scalars(
            select(Werk).where(Werk.code == updates["code"], Werk.id != item_id)
        ).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Werk-Code bereits vergeben")
    if "land_id" in updates and updates["land_id"] is not None:
        if not db.get(Land, updates["land_id"]):
            raise HTTPException(status_code=422, detail="Land nicht gefunden")
    for k, v in updates.items():
        setattr(obj, k, v)
    try:
        db.commit()
        db.refresh(obj)
    except (IntegrityError, ProgrammingError) as exc:
        db.rollback()
        _raise_werk_db_error(exc)
    return obj


@router.get("/werke/{werk_id}/zuschlaege", response_model=list[WerkZuschlagRead])
def list_werk_zuschlaege(
    werk_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    if not db.get(Werk, werk_id):
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    return list(
        db.scalars(
            select(WerkZuschlag)
            .where(WerkZuschlag.werk_id == werk_id)
            .order_by(WerkZuschlag.typ.asc())
        ).all()
    )


@router.post(
    "/werke/{werk_id}/zuschlaege",
    response_model=WerkZuschlagRead,
    status_code=status.HTTP_201_CREATED,
)
def create_werk_zuschlag(
    werk_id: int,
    body: WerkZuschlagCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    if not db.get(Werk, werk_id):
        raise HTTPException(status_code=404, detail="Werk nicht gefunden")
    obj = WerkZuschlag(werk_id=werk_id, **body.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/werke/{werk_id}/zuschlaege/{item_id}", response_model=WerkZuschlagRead)
def update_werk_zuschlag(
    werk_id: int,
    item_id: int,
    body: WerkZuschlagUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(WerkZuschlag, item_id)
    if not obj or obj.werk_id != werk_id:
        raise HTTPException(status_code=404, detail="Zuschlag nicht gefunden")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/werke/{werk_id}/zuschlaege/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_werk_zuschlag(
    werk_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(WerkZuschlag, item_id)
    if not obj or obj.werk_id != werk_id:
        raise HTTPException(status_code=404, detail="Zuschlag nicht gefunden")
    db.delete(obj)
    db.commit()
