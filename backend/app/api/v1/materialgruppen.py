from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import materialgruppe as materialgruppe_crud
from app.database import get_db
from app.models.materialgruppe import Materialgruppe
from app.models.user import User
from app.schemas.materialgruppe import (
    MaterialgruppeCreate,
    MaterialgruppeRead,
    MaterialgruppeUpdate,
)

router = APIRouter(prefix="/materialgruppen", tags=["Materialgruppen"])


@router.get("", response_model=list[MaterialgruppeRead])
def list_materialgruppen(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    nur_aktiv: bool = Query(False),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Materialgruppe).order_by(Materialgruppe.gruppe.asc()).offset(skip).limit(limit)
    if nur_aktiv:
        stmt = stmt.where(Materialgruppe.aktiv.is_(True))
    return list(db.scalars(stmt).all())


@router.get("/{item_id}", response_model=MaterialgruppeRead)
def get_materialgruppe(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = materialgruppe_crud.materialgruppe.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materialgruppe nicht gefunden",
        )
    return item


@router.post("", response_model=MaterialgruppeRead, status_code=status.HTTP_201_CREATED)
def create_materialgruppe(
    item_in: MaterialgruppeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    if materialgruppe_crud.materialgruppe.get_by_gruppe(db, item_in.gruppe):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Materialgruppe '{item_in.gruppe}' existiert bereits.",
        )
    return materialgruppe_crud.materialgruppe.create(db, item_in)


@router.put("/{item_id}", response_model=MaterialgruppeRead)
def update_materialgruppe(
    item_id: int,
    item_in: MaterialgruppeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = materialgruppe_crud.materialgruppe.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materialgruppe nicht gefunden",
        )

    update_data = item_in.model_dump(exclude_unset=True)
    neue_gruppe = update_data.get("gruppe")
    if neue_gruppe and neue_gruppe != item.gruppe:
        existing = materialgruppe_crud.materialgruppe.get_by_gruppe(db, neue_gruppe)
        if existing and existing.id != item.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Materialgruppe '{neue_gruppe}' existiert bereits.",
            )
        materialgruppe_crud.materialgruppe.rename_gruppe_on_materials(db, item.gruppe, neue_gruppe)

    merged = {
        "gruppe": item.gruppe,
        "bezeichnung": item.bezeichnung,
        "schmelzdichte_kg_m3": item.schmelzdichte_kg_m3,
        "waermekapazitaet_j_kg_k": item.waermekapazitaet_j_kg_k,
        "waermeleitfaehigkeit_w_m_k": item.waermeleitfaehigkeit_w_m_k,
        "werkzeugtemperatur_c": item.werkzeugtemperatur_c,
        "schmelzetemperatur_c": item.schmelzetemperatur_c,
        "entformungstemperatur_c": item.entformungstemperatur_c,
        **update_data,
    }
    werkzeug = merged["werkzeugtemperatur_c"]
    entformung = merged["entformungstemperatur_c"]
    schmelze = merged["schmelzetemperatur_c"]
    if not (werkzeug < entformung < schmelze):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Temperaturen müssen der Reihenfolge Werkzeug < Entformung < Schmelze folgen.",
        )

    return materialgruppe_crud.materialgruppe.update(db, item, item_in)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_materialgruppe(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = materialgruppe_crud.materialgruppe.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Materialgruppe nicht gefunden",
        )
    refs = materialgruppe_crud.materialgruppe.count_material_references(db, item.gruppe)
    if refs > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Materialgruppe '{item.gruppe}' wird noch von {refs} Material(en) "
                "verwendet und kann nicht gelöscht werden."
            ),
        )
    materialgruppe_crud.materialgruppe.delete(db, item)
