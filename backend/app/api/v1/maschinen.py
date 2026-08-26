from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import maschine as maschine_crud
from app.database import get_db
from app.models.maschine import Maschine
from app.models.user import User
from app.models.werk import Werk
from app.schemas.maschine import (
    MaschineCreate,
    MaschineRead,
    MaschineRecalculateRequest,
    MaschineUpdate,
)
from app.services.machine_hourly_rate import (
    MachineRateInput,
    MachineRateValidationError,
    apply_rate_to_maschine,
    berechne_maschinenstundensatz,
)

router = APIRouter(prefix="/maschinen", tags=["Maschinen"])


@router.get("", response_model=list[MaschineRead])
def list_maschinen(
    skip: int = 0,
    limit: int = 500,
    werk_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Maschine).order_by(Maschine.bezeichnung.asc()).offset(skip).limit(limit)
    if werk_id is not None:
        stmt = stmt.where(Maschine.werk_id == werk_id)
    return list(db.scalars(stmt).all())


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


@router.post("", response_model=MaschineRead, status_code=status.HTTP_201_CREATED)
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


@router.post("/{item_id}/recalculate-rate", response_model=MaschineRead)
def recalculate_maschine_rate(
    item_id: int,
    body: MaschineRecalculateRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = db.get(Maschine, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Maschine nicht gefunden")
    fx = body.fx_to_eur if body and body.fx_to_eur else None
    if fx is None and item.werk_id:
        werk = db.get(Werk, item.werk_id)
        if werk:
            fx = float(werk.fx_to_eur)
    fx = fx or 1.0
    required = [
        item.arbeitstage_pro_jahr,
        item.schichten_pro_tag,
        item.stunden_pro_schicht,
        item.oee,
        item.investment,
        item.flaeche_sqm,
        item.space_cost_satz_pro_sqm_jahr,
        item.abschreibungsdauer_jahre,
        item.zinssatz,
        item.versicherungssatz,
        item.instandhaltungssatz,
    ]
    if any(v is None for v in required):
        raise HTTPException(
            status_code=422,
            detail="Maschine hat unvollständige Costing-Parameter für die Neuberechnung",
        )
    try:
        result = berechne_maschinenstundensatz(
            MachineRateInput(
                arbeitstage_pro_jahr=float(item.arbeitstage_pro_jahr),
                schichten_pro_tag=float(item.schichten_pro_tag),
                stunden_pro_schicht=float(item.stunden_pro_schicht),
                oee=float(item.oee),
                investment=float(item.investment),
                flaeche_sqm=float(item.flaeche_sqm),
                space_cost_satz_pro_sqm_jahr=float(item.space_cost_satz_pro_sqm_jahr),
                abschreibungsdauer_jahre=float(item.abschreibungsdauer_jahre),
                zinssatz=float(item.zinssatz or 0),
                versicherungssatz=float(item.versicherungssatz or 0),
                instandhaltungssatz=float(item.instandhaltungssatz or 0),
                stromverbrauch_kwh_h=float(item.stromverbrauch_kwh_h or 0),
                strompreis=float(item.strompreis or 0),
                druckluftverbrauch_m3_h=float(item.druckluftverbrauch_m3_h or 0),
                druckluftpreis=float(item.druckluftpreis or 0),
                kuehlwasserverbrauch_m3_h=float(item.kuehlwasserverbrauch_m3_h or 0),
                kuehlwasserpreis=float(item.kuehlwasserpreis or 0),
                fx_to_eur=float(fx),
                source_currency=item.source_currency or "USD",
            )
        )
    except MachineRateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    apply_rate_to_maschine(item, result)
    item.rate_updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


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
