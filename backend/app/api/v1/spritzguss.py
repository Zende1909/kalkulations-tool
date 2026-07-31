from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.schemas.spritzguss_kalkulation import (
    SpritzgussCalcRequest,
    SpritzgussCalcResponse,
    SpritzgussErgebnisSchema,
    SpritzgussKalkulationCreate,
    SpritzgussKalkulationListItem,
    SpritzgussKalkulationRead,
    SpritzgussKalkulationUpdate,
)
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    SpritzgussValidationError,
    berechne_spritzguss,
)

router = APIRouter(prefix="/spritzguss", tags=["Spritzguss-Kalkulation"])


def _to_calc_input_from_request(body: SpritzgussCalcRequest) -> SpritzgussInput:
    return SpritzgussInput(**body.model_dump())


def _to_calc_input_from_model(obj: SpritzgussKalkulation) -> SpritzgussInput:
    return SpritzgussInput(
        teilegewicht_netto_g=obj.teilegewicht_netto_g,
        materialpreis_pro_kg=obj.materialpreis_pro_kg,
        ausschussquote_pct=obj.ausschussquote_pct,
        mgk_pct=obj.mgk_pct,
        zykluszeit_s=obj.zykluszeit_s,
        maschinenstundensatz=obj.maschinenstundensatz,
        kavitaeten=obj.kavitaeten,
        lohnstundensatz=obj.lohnstundensatz,
        fgk_pct=obj.fgk_pct,
        werkzeugkosten_eur=obj.werkzeugkosten_eur,
        amortisationsvolumen=obj.amortisationsvolumen,
        vvgk_pct=obj.vvgk_pct,
        gewinn_pct=obj.gewinn_pct,
        skonto_pct=obj.skonto_pct,
    )


def _run_calculation(calc_input: SpritzgussInput) -> SpritzgussCalcResponse:
    try:
        ergebnis = berechne_spritzguss(calc_input)
    except SpritzgussValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return SpritzgussCalcResponse(
        ergebnis=SpritzgussErgebnisSchema(**ergebnis.to_dict()),
        bloecke=ergebnis.as_blocks(),
    )


def _apply_calculation(obj: SpritzgussKalkulation) -> None:
    response = _run_calculation(_to_calc_input_from_model(obj))
    obj.ergebnis = response.ergebnis.model_dump()
    obj.ergebnis_bloecke = response.bloecke


@router.post("/berechnen", response_model=SpritzgussCalcResponse)
def berechnen(
    body: SpritzgussCalcRequest,
    _: User = Depends(require_viewer),
):
    """Berechnet eine Kalkulation ohne Speichern."""
    return _run_calculation(_to_calc_input_from_request(body))


@router.get("", response_model=list[SpritzgussKalkulationListItem])
def list_kalkulationen(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    rows = db.scalars(
        select(SpritzgussKalkulation)
        .order_by(SpritzgussKalkulation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    result: list[SpritzgussKalkulationListItem] = []
    for row in rows:
        verkaufspreis = None
        if isinstance(row.ergebnis, dict):
            verkaufspreis = row.ergebnis.get("verkaufspreis")
        result.append(
            SpritzgussKalkulationListItem(
                id=row.id,
                teilebezeichnung=row.teilebezeichnung,
                teilenummer=row.teilenummer,
                kunde=row.kunde,
                projekt=row.projekt,
                jahresstueckzahl=row.jahresstueckzahl,
                verkaufspreis=verkaufspreis,
                updated_at=row.updated_at,
                aktiv=row.aktiv,
            )
        )
    return result


@router.get("/{item_id}", response_model=SpritzgussKalkulationRead)
def get_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = db.get(SpritzgussKalkulation, item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden")
    return item


@router.post("", response_model=SpritzgussKalkulationRead, status_code=status.HTTP_201_CREATED)
def create_kalkulation(
    body: SpritzgussKalkulationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = SpritzgussKalkulation(**body.model_dump())
    _apply_calculation(obj)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{item_id}", response_model=SpritzgussKalkulationRead)
def update_kalkulation(
    item_id: int,
    body: SpritzgussKalkulationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)

    _apply_calculation(obj)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden")
    db.delete(obj)
    db.commit()
