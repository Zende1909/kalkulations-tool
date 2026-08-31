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
from app.schemas.maschine_auslastung import MaschineAuslastungResponse
from app.services.maschine_auslastung import build_maschinen_auslastung
from app.services.machine_hourly_rate import (
    MachineRateValidationError,
    apply_rate_to_maschine,
    berechne_maschinenstundensatz,
    build_rate_input_from_maschine_and_werk,
)

router = APIRouter(prefix="/maschinen", tags=["Maschinen"])

# Standortparameter gehören ans Werk – Clients dürfen sie nicht mehr setzen.
_WERK_OWNED_MACHINE_FIELDS = (
    "arbeitstage_pro_jahr",
    "schichten_pro_tag",
    "stunden_pro_schicht",
    "oee",
    "space_cost_satz_pro_sqm_jahr",
    "abschreibungsdauer_jahre",
    "zinssatz",
    "versicherungssatz",
    "instandhaltungssatz",
    "strompreis",
    "druckluftpreis",
    "kuehlwasserpreis",
)


def _require_werk(db: Session, werk_id: int) -> Werk:
    werk = db.get(Werk, werk_id)
    if not werk:
        raise HTTPException(status_code=422, detail="Werk nicht gefunden")
    return werk


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


@router.get("/auslastung", response_model=MaschineAuslastungResponse)
def get_maschinen_auslastung(
    plant_id: int = Query(..., ge=1, description="Werk-ID"),
    customer_id: int | None = Query(default=None, ge=1),
    program_id: int | None = Query(default=None, ge=1),
    project_ids: list[int] = Query(default=[], alias="project_ids"),
    nur_aktiv: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Maschinenauslastung je Werk, filterbar über Kunde → Programm → Projekte."""
    return build_maschinen_auslastung(
        db,
        plant_id=plant_id,
        customer_id=customer_id,
        program_id=program_id,
        project_ids=project_ids,
        nur_aktiv=nur_aktiv,
    )


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
    werk = _require_werk(db, item_in.werk_id)
    data = item_in.model_dump()
    for key in _WERK_OWNED_MACHINE_FIELDS:
        data[key] = None
    data["stundensatz"] = 0.0
    data["source_currency"] = data.get("source_currency") or werk.currency
    created = maschine_crud.maschine.create(db, MaschineCreate.model_validate(data))
    try:
        rate_input = build_rate_input_from_maschine_and_werk(created, werk)
        result = berechne_maschinenstundensatz(rate_input)
        apply_rate_to_maschine(created, result)
        created.rate_updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(created)
    except MachineRateValidationError:
        # Unvollständige Parameter: Stundensatz bleibt 0 bis Neu berechnen
        pass
    return created


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
    updates = item_in.model_dump(exclude_unset=True)
    for key in _WERK_OWNED_MACHINE_FIELDS:
        updates.pop(key, None)
    updates.pop("stundensatz", None)
    if "werk_id" in updates:
        if updates["werk_id"] is None:
            raise HTTPException(status_code=422, detail="werk_id ist Pflicht")
        werk = _require_werk(db, int(updates["werk_id"]))
        if not updates.get("source_currency"):
            updates["source_currency"] = werk.currency
    return maschine_crud.maschine.update(
        db, item, MaschineUpdate.model_validate(updates)
    )


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
    if not item.werk_id:
        raise HTTPException(
            status_code=422,
            detail="Maschine ohne Werk – bitte Werk zuordnen und Betriebsparameter am Werk pflegen",
        )
    werk = _require_werk(db, item.werk_id)
    fx = body.fx_to_eur if body and body.fx_to_eur else None
    try:
        rate_input = build_rate_input_from_maschine_and_werk(item, werk, fx_to_eur=fx)
        result = berechne_maschinenstundensatz(rate_input)
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
