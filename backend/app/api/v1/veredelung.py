from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import veredelungsschritt as veredelung_crud
from app.database import get_db
from app.models.user import User
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.veredelungsschritt import (
    VeredelungsschrittCreate,
    VeredelungsschrittRead,
    VeredelungsschrittUpdate,
)
from app.services.veredelung_kalkulation import (
    VeredelungInput,
    VeredelungValidationError,
    berechne_veredelung,
)

router = APIRouter(prefix="/veredelung", tags=["Veredelung"])


def _to_input(obj: Veredelungsschritt | VeredelungsschrittCreate | VeredelungsschrittUpdate | dict) -> VeredelungInput:
    if isinstance(obj, dict):
        data = obj
    elif hasattr(obj, "model_dump"):
        data = obj.model_dump()
    else:
        data = {
            "taktzeit_s": obj.taktzeit_s,
            "anzahl_mitarbeiter": obj.anzahl_mitarbeiter,
            "lohnstundensatz": obj.lohnstundensatz,
            "maschinenstundensatz": obj.maschinenstundensatz,
            "verbrauchskosten_je_stueck": obj.verbrauchskosten_je_stueck,
            "ausschussquote_pct": obj.ausschussquote_pct,
            "fgk_pct": obj.fgk_pct,
            "reihenfolge": obj.reihenfolge,
        }
    return VeredelungInput(
        taktzeit_s=float(data["taktzeit_s"]),
        anzahl_mitarbeiter=int(data["anzahl_mitarbeiter"]),
        lohnstundensatz=float(data["lohnstundensatz"]),
        maschinenstundensatz=(
            None
            if data.get("maschinenstundensatz") is None
            else float(data["maschinenstundensatz"])
        ),
        verbrauchskosten_je_stueck=float(data["verbrauchskosten_je_stueck"]),
        ausschussquote_pct=float(data["ausschussquote_pct"]),
        fgk_pct=float(data["fgk_pct"]),
        reihenfolge=int(data["reihenfolge"]),
    )


def _with_kosten(obj: Veredelungsschritt) -> VeredelungsschrittRead:
    try:
        kosten = berechne_veredelung(_to_input(obj))
    except VeredelungValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    base = VeredelungsschrittRead.model_validate(obj)
    return base.model_copy(update=kosten.to_dict())


@router.get("", response_model=list[VeredelungsschrittRead])
def list_veredelungsschritte(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    rows = veredelung_crud.veredelungsschritt.get_multi(db, skip=skip, limit=limit)
    return [_with_kosten(row) for row in rows]


@router.get("/{item_id}", response_model=VeredelungsschrittRead)
def get_veredelungsschritt(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = veredelung_crud.veredelungsschritt.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veredelungsschritt nicht gefunden",
        )
    return _with_kosten(item)


@router.post("", response_model=VeredelungsschrittRead, status_code=status.HTTP_201_CREATED)
def create_veredelungsschritt(
    item_in: VeredelungsschrittCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    try:
        berechne_veredelung(_to_input(item_in))
    except VeredelungValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    item = veredelung_crud.veredelungsschritt.create(db, item_in)
    return _with_kosten(item)


@router.put("/{item_id}", response_model=VeredelungsschrittRead)
def update_veredelungsschritt(
    item_id: int,
    item_in: VeredelungsschrittUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = veredelung_crud.veredelungsschritt.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veredelungsschritt nicht gefunden",
        )
    updates = item_in.model_dump(exclude_unset=True)
    merged = {
        "taktzeit_s": updates.get("taktzeit_s", item.taktzeit_s),
        "anzahl_mitarbeiter": updates.get("anzahl_mitarbeiter", item.anzahl_mitarbeiter),
        "lohnstundensatz": updates.get("lohnstundensatz", item.lohnstundensatz),
        "maschinenstundensatz": updates.get(
            "maschinenstundensatz", item.maschinenstundensatz
        ),
        "verbrauchskosten_je_stueck": updates.get(
            "verbrauchskosten_je_stueck", item.verbrauchskosten_je_stueck
        ),
        "ausschussquote_pct": updates.get("ausschussquote_pct", item.ausschussquote_pct),
        "fgk_pct": updates.get("fgk_pct", item.fgk_pct),
        "reihenfolge": updates.get("reihenfolge", item.reihenfolge),
    }
    try:
        berechne_veredelung(_to_input(merged))
    except VeredelungValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    updated = veredelung_crud.veredelungsschritt.update(db, item, item_in)
    return _with_kosten(updated)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_veredelungsschritt(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = veredelung_crud.veredelungsschritt.get(db, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Veredelungsschritt nicht gefunden",
        )
    veredelung_crud.veredelungsschritt.delete(db, item)
