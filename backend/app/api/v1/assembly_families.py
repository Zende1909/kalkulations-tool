"""API für Baugruppenfamilien und Variantenmix."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.assembly_family import AssemblyFamily
from app.models.baugruppe import Baugruppe
from app.models.customer import Customer
from app.models.program import Program
from app.models.project import Project
from app.models.user import User
from app.schemas.assembly_family import (
    AssemblyFamilyCreate,
    AssemblyFamilyMixRead,
    AssemblyFamilyRead,
    AssemblyFamilyUpdate,
    AssemblyVariantCreate,
    AssemblyVariantUpdate,
)
from app.services.assembly_variant_mix import (
    assert_unique_teilenummer,
    build_family_mix_result,
    project_jahresstueckzahl,
    validate_share_pct,
    variant_jahresmenge,
)

router = APIRouter(prefix="/assembly-families", tags=["assembly-families"])


class AssemblyVariantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    family_id: int | None
    teilenummer: str
    name: str
    beschreibung: str
    anteil_prozent: float
    jahresstueckzahl: int
    aktiv: bool
    status: str
    project_id: int | None
    werk_id: int | None


def _variant_to_read(v: Baugruppe) -> AssemblyVariantRead:
    return AssemblyVariantRead(
        id=v.id,
        family_id=v.family_id,
        teilenummer=v.teilenummer,
        name=v.name,
        beschreibung=v.beschreibung or "",
        anteil_prozent=float(v.variant_share_pct or 0),
        jahresstueckzahl=int(v.jahresstueckzahl or 0),
        aktiv=bool(v.aktiv),
        status=v.status,
        project_id=v.project_id,
        werk_id=v.werk_id,
    )


def _family_or_404(db: Session, family_id: int) -> AssemblyFamily:
    obj = db.get(AssemblyFamily, family_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Baugruppenfamilie nicht gefunden.")
    return obj


def _variant_or_404(db: Session, family_id: int, variant_id: int) -> Baugruppe:
    obj = db.get(Baugruppe, variant_id)
    if obj is None or obj.family_id != family_id:
        raise HTTPException(status_code=404, detail="Variante nicht gefunden.")
    return obj


def _refresh_family_ergebnis(db: Session, family: AssemblyFamily) -> dict:
    result = build_family_mix_result(db, int(family.id))
    family.ergebnis = result
    db.add(family)
    return result


def _apply_variant_jahresmenge(db: Session, family: AssemblyFamily, variant: Baugruppe) -> None:
    project_qty = project_jahresstueckzahl(db, int(family.project_id))
    share = float(variant.variant_share_pct or 0) if variant.aktiv else 0.0
    variant.jahresstueckzahl = variant_jahresmenge(project_qty, share)
    variant.project_id = family.project_id
    variant.linked_project_id = family.project_id


def _project_labels(db: Session, project_id: int) -> tuple[str, str]:
    project = db.get(Project, project_id)
    if project is None:
        return "", ""
    program = db.get(Program, project.program_id)
    customer_name = ""
    if program is not None:
        customer = db.get(Customer, program.customer_id)
        customer_name = customer.name if customer else ""
    return customer_name, project.name


@router.get("", response_model=list[AssemblyFamilyRead])
def list_families(
    project_id: int | None = Query(default=None),
    aktiv: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> list[AssemblyFamily]:
    stmt = select(AssemblyFamily).order_by(AssemblyFamily.name, AssemblyFamily.id)
    if project_id is not None:
        stmt = stmt.where(AssemblyFamily.project_id == project_id)
    if aktiv is not None:
        stmt = stmt.where(AssemblyFamily.aktiv.is_(aktiv))
    return list(db.scalars(stmt).all())


@router.post("", response_model=AssemblyFamilyRead, status_code=status.HTTP_201_CREATED)
def create_family(
    body: AssemblyFamilyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyFamily:
    project = db.get(Project, body.project_id)
    if project is None:
        raise HTTPException(status_code=400, detail="Projekt nicht gefunden.")
    obj = AssemblyFamily(
        project_id=body.project_id,
        name=body.name.strip(),
        beschreibung=body.beschreibung or "",
        status=body.status or "entwurf",
        aktiv=body.aktiv,
    )
    db.add(obj)
    db.flush()
    _refresh_family_ergebnis(db, obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{family_id}", response_model=AssemblyFamilyRead)
def get_family(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> AssemblyFamily:
    return _family_or_404(db, family_id)


@router.put("/{family_id}", response_model=AssemblyFamilyRead)
def update_family(
    family_id: int,
    body: AssemblyFamilyUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyFamily:
    obj = _family_or_404(db, family_id)
    data = body.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        data["name"] = str(data["name"]).strip()
    for key, value in data.items():
        setattr(obj, key, value)
    _refresh_family_ergebnis(db, obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{family_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_family(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> None:
    obj = _family_or_404(db, family_id)
    variants = list(db.scalars(select(Baugruppe).where(Baugruppe.family_id == family_id)).all())
    for v in variants:
        v.family_id = None
        v.variant_share_pct = None
        db.add(v)
    db.delete(obj)
    db.commit()


@router.get("/{family_id}/mix", response_model=AssemblyFamilyMixRead)
def get_family_mix(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
) -> dict:
    _family_or_404(db, family_id)
    return build_family_mix_result(db, family_id)


@router.post("/{family_id}/recalculate", response_model=AssemblyFamilyMixRead)
def recalculate_family(
    family_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> dict:
    family = _family_or_404(db, family_id)
    variants = list(db.scalars(select(Baugruppe).where(Baugruppe.family_id == family_id)).all())
    for v in variants:
        _apply_variant_jahresmenge(db, family, v)
        db.add(v)
    result = _refresh_family_ergebnis(db, family)
    db.commit()
    return result


@router.post(
    "/{family_id}/variants",
    response_model=AssemblyVariantRead,
    status_code=status.HTTP_201_CREATED,
)
def create_variant(
    family_id: int,
    body: AssemblyVariantCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyVariantRead:
    family = _family_or_404(db, family_id)
    try:
        share = validate_share_pct(body.anteil_prozent)
        assert_unique_teilenummer(db, family_id, body.teilenummer)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    kunde, projekt = _project_labels(db, int(family.project_id))
    variant = Baugruppe(
        name=body.bezeichnung.strip(),
        teilenummer=body.teilenummer.strip(),
        beschreibung=body.beschreibung or "",
        status="entwurf",
        aktiv=body.aktiv,
        project_id=family.project_id,
        linked_project_id=family.project_id,
        kunde=kunde,
        projekt=projekt,
        werk_id=body.werk_id,
        family_id=family.id,
        variant_share_pct=share,
        assembly_type="TOP_LEVEL",
        legacy_mode=True,
    )
    _apply_variant_jahresmenge(db, family, variant)
    db.add(variant)
    db.flush()
    _refresh_family_ergebnis(db, family)
    db.commit()
    db.refresh(variant)
    return _variant_to_read(variant)


@router.put("/{family_id}/variants/{variant_id}", response_model=AssemblyVariantRead)
def update_variant(
    family_id: int,
    variant_id: int,
    body: AssemblyVariantUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> AssemblyVariantRead:
    family = _family_or_404(db, family_id)
    variant = _variant_or_404(db, family_id, variant_id)
    data = body.model_dump(exclude_unset=True)
    try:
        if "anteil_prozent" in data and data["anteil_prozent"] is not None:
            data["variant_share_pct"] = validate_share_pct(data.pop("anteil_prozent"))
        elif "anteil_prozent" in data:
            data.pop("anteil_prozent")
        if "bezeichnung" in data and data["bezeichnung"] is not None:
            data["name"] = str(data.pop("bezeichnung")).strip()
        if "teilenummer" in data and data["teilenummer"] is not None:
            tn = str(data["teilenummer"]).strip()
            assert_unique_teilenummer(db, family_id, tn, exclude_variant_id=variant.id)
            data["teilenummer"] = tn
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for key, value in data.items():
        if key in {"name", "teilenummer", "beschreibung", "aktiv", "werk_id", "variant_share_pct"}:
            setattr(variant, key, value)
    _apply_variant_jahresmenge(db, family, variant)
    db.add(variant)
    _refresh_family_ergebnis(db, family)
    db.commit()
    db.refresh(variant)
    return _variant_to_read(variant)


@router.delete("/{family_id}/variants/{variant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_variant(
    family_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
) -> None:
    family = _family_or_404(db, family_id)
    variant = _variant_or_404(db, family_id, variant_id)
    db.delete(variant)
    db.flush()
    _refresh_family_ergebnis(db, family)
    db.commit()
