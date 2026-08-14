"""Struktur-API für mehrstufige Baugruppen (Phase B)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.user import User
from app.schemas.assembly_calculation import (
    AssemblyRecalculateRequest,
    AssemblyRecalculateResponse,
)
from app.schemas.assembly_structure import (
    AssemblyPositionCreateRequest,
    AssemblyPositionPatchRequest,
    AssemblyPositionRead,
    AssemblyStructureRead,
    AssemblyStructureReplaceRequest,
)
from app.services.assembly_recalculation_service import (
    AssemblyRecalculationError,
    recalculate_assembly_tree,
)
from app.services.assembly_structure_service import (
    AssemblyStructureError,
    add_position,
    delete_position,
    get_structure,
    patch_position,
    replace_structure,
)

router = APIRouter(prefix="/baugruppen", tags=["Baugruppen-Struktur"])


def _raise_from_service(exc: AssemblyStructureError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _raise_from_recalc(exc: AssemblyRecalculationError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{baugruppe_id}/recalculate", response_model=AssemblyRecalculateResponse)
def recalculate_structure(
    baugruppe_id: int,
    payload: AssemblyRecalculateRequest | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyRecalculateResponse:
    request = payload or AssemblyRecalculateRequest()
    try:
        return recalculate_assembly_tree(db, baugruppe_id, request)
    except AssemblyRecalculationError as exc:
        _raise_from_recalc(exc)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
    raise RuntimeError("unreachable")


@router.get("/{baugruppe_id}/structure", response_model=AssemblyStructureRead)
def read_structure(
    baugruppe_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> AssemblyStructureRead:
    try:
        return get_structure(db, baugruppe_id)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
    raise RuntimeError("unreachable")


@router.put("/{baugruppe_id}/structure", response_model=AssemblyStructureRead)
def write_structure(
    baugruppe_id: int,
    payload: AssemblyStructureReplaceRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyStructureRead:
    try:
        return replace_structure(db, baugruppe_id, payload)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Struktur konnte nicht gespeichert werden",
        ) from exc
    raise RuntimeError("unreachable")


@router.post(
    "/{baugruppe_id}/positions",
    response_model=AssemblyPositionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_position(
    baugruppe_id: int,
    payload: AssemblyPositionCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyPositionRead:
    try:
        return add_position(db, baugruppe_id, payload)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Position konnte nicht gespeichert werden",
        ) from exc
    raise RuntimeError("unreachable")


@router.patch(
    "/{baugruppe_id}/positions/{position_id}",
    response_model=AssemblyPositionRead,
)
def update_position(
    baugruppe_id: int,
    position_id: int,
    payload: AssemblyPositionPatchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyPositionRead:
    try:
        return patch_position(db, baugruppe_id, position_id, payload)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Position konnte nicht gespeichert werden",
        ) from exc
    raise RuntimeError("unreachable")


@router.delete(
    "/{baugruppe_id}/positions/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_position(
    baugruppe_id: int,
    position_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> None:
    try:
        delete_position(db, baugruppe_id, position_id)
    except AssemblyStructureError as exc:
        _raise_from_service(exc)
