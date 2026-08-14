from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud.investition import investition as investition_crud
from app.database import get_db
from app.models.baugruppe import Baugruppe
from app.models.investition import Investition
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.schemas.investition import (
    InvestitionCreate,
    InvestitionRead,
    InvestitionUpdate,
)
from app.services.investition_service import EINMALZAHLUNG_HINWEIS, validate_investition_input, zuordnung_label

router = APIRouter(prefix="/investitionen", tags=["Investitionen"])


def _load_link_maps(db: Session) -> tuple[dict[int, SpritzgussKalkulation], dict[int, Baugruppe]]:
    sg_map = {row.id: row for row in db.scalars(select(SpritzgussKalkulation)).all()}
    bg_map = {row.id: row for row in db.scalars(select(Baugruppe)).all()}
    return sg_map, bg_map


def _to_read(
    row: Investition,
    sg_map: dict[int, SpritzgussKalkulation],
    bg_map: dict[int, Baugruppe],
) -> InvestitionRead:
    calc = sg_map.get(row.calculation_id) if row.calculation_id else None
    bg = bg_map.get(row.baugruppe_id) if row.baugruppe_id else None
    return InvestitionRead(
        id=row.id,
        name=row.name or row.description or row.part_name,
        investment_type=row.investment_type,
        payment_type=row.payment_type,
        amount=float(row.amount),
        amortization_volume=row.amortization_volume,
        cost_per_piece=row.cost_per_piece,
        project=row.project_id or "",
        customer=row.customer or "",
        calculation_id=row.calculation_id,
        baugruppe_id=row.baugruppe_id,
        description=row.description or "",
        included_in_unit_price=bool(row.included_in_unit_price),
        archived=bool(row.archived),
        zuordnung=zuordnung_label(
            calculation_id=row.calculation_id,
            baugruppe_id=row.baugruppe_id,
            part_number=row.part_number or "",
            part_name=row.part_name or "",
            project_id=row.project_id or "",
            calc_teilenummer=calc.teilenummer if calc else None,
            calc_bezeichnung=calc.teilebezeichnung if calc else None,
            bg_name=bg.name if bg else None,
            bg_teilenummer=bg.teilenummer if bg else None,
        ),
        payment_hint=EINMALZAHLUNG_HINWEIS if row.payment_type == "Einmalzahlung" else "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _validate_links(db: Session, calculation_id: int | None, baugruppe_id: int | None) -> None:
    if calculation_id is not None and not db.get(SpritzgussKalkulation, calculation_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Einzelteil-Kalkulation nicht gefunden",
        )
    if baugruppe_id is not None and not db.get(Baugruppe, baugruppe_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Baugruppe nicht gefunden",
        )


def _build_payload(body: InvestitionCreate | InvestitionUpdate, existing: Investition | None = None) -> dict:
    if isinstance(body, InvestitionCreate):
        data = body.model_dump(by_alias=True)
    else:
        data = body.model_dump(exclude_unset=True, by_alias=True)
        if existing is not None:
            merged = {
                "name": existing.name,
                "investment_type": existing.investment_type,
                "payment_type": existing.payment_type,
                "amount": existing.amount,
                "amortization_volume": existing.amortization_volume,
                "project": existing.project_id,
                "customer": existing.customer,
                "calculation_id": existing.calculation_id,
                "baugruppe_id": existing.baugruppe_id,
                "included_in_unit_price": existing.included_in_unit_price,
                "status": existing.status,
            }
            merged.update(data)
            data = merged

    computed = validate_investition_input(
        name=data["name"],
        investment_type=data["investment_type"],
        payment_type=data["payment_type"],
        amount=float(data["amount"]),
        amortization_volume=data.get("amortization_volume"),
        project=data.get("project", ""),
        calculation_id=data.get("calculation_id"),
        baugruppe_id=data.get("baugruppe_id"),
        included_in_unit_price=data.get("included_in_unit_price"),
        planning_status=data.get("status"),
    )
    db_payload = {
        "name": data["name"].strip(),
        "investment_type": data["investment_type"],
        "payment_type": data["payment_type"],
        "amount": float(data["amount"]),
        "project_id": data.get("project", "").strip(),
        "customer": data.get("customer", "") or "",
        "part_name": data.get("part_name", "") or "",
        "part_number": data.get("part_number", "") or "",
        "calculation_id": data.get("calculation_id"),
        "baugruppe_id": data.get("baugruppe_id"),
        "description": data.get("description", "") or "",
        "status": computed.pop("status"),
        **computed,
    }
    if isinstance(body, InvestitionUpdate) and body.archived is not None:
        db_payload["archived"] = body.archived
    return db_payload


def _apply_filters(
    stmt,
    *,
    project: str | None,
    customer: str | None,
    calculation_id: int | None,
    baugruppe_id: int | None,
    investment_type: str | None,
    payment_type: str | None,
    scope: str | None = None,
    search: str | None,
    include_archived: bool,
):
    if not include_archived:
        stmt = stmt.where(Investition.archived.is_(False))
    if project:
        stmt = stmt.where(Investition.project_id == project)
    if customer:
        stmt = stmt.where(Investition.customer == customer)
    if calculation_id is not None:
        stmt = stmt.where(Investition.calculation_id == calculation_id)
    elif baugruppe_id is not None:
        stmt = stmt.where(Investition.baugruppe_id == baugruppe_id)
    elif scope == "gesamtprojekt":
        stmt = stmt.where(
            Investition.calculation_id.is_(None),
            Investition.baugruppe_id.is_(None),
        )
    elif scope == "einzelteil":
        stmt = stmt.where(Investition.calculation_id.is_not(None))
    elif scope == "baugruppe":
        stmt = stmt.where(Investition.baugruppe_id.is_not(None))
    if investment_type:
        stmt = stmt.where(Investition.investment_type == investment_type)
    if payment_type:
        stmt = stmt.where(Investition.payment_type == payment_type)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Investition.name.ilike(term),
                Investition.description.ilike(term),
                Investition.part_name.ilike(term),
                Investition.part_number.ilike(term),
                Investition.project_id.ilike(term),
                Investition.customer.ilike(term),
            )
        )
    return stmt


@router.get("", response_model=list[InvestitionRead])
def list_investitionen(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    project: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    calculation_id: int | None = Query(default=None),
    baugruppe_id: int | None = Query(default=None),
    investment_type: str | None = Query(default=None),
    payment_type: str | None = Query(default=None),
    scope: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    if not project or not project.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt ist erforderlich, um Investitionen zu laden.",
        )
    stmt = select(Investition)
    stmt = _apply_filters(
        stmt,
        project=project,
        customer=customer,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        scope=scope,
        investment_type=investment_type,
        payment_type=payment_type,
        search=search,
        include_archived=include_archived,
    )
    stmt = stmt.order_by(Investition.updated_at.desc()).offset(skip).limit(limit)
    rows = list(db.scalars(stmt).all())
    sg_map, bg_map = _load_link_maps(db)
    return [_to_read(row, sg_map, bg_map) for row in rows]


@router.get("/{item_id}", response_model=InvestitionRead)
def get_investition(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    row = investition_crud.get(db, item_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investition nicht gefunden")
    sg_map, bg_map = _load_link_maps(db)
    return _to_read(row, sg_map, bg_map)


@router.post("", response_model=InvestitionRead, status_code=status.HTTP_201_CREATED)
def create_investition(
    body: InvestitionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    if body.calculation_id is not None and body.baugruppe_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investition kann nur einem Einzelteil oder einer Baugruppe zugeordnet werden.",
        )
    _validate_links(db, body.calculation_id, body.baugruppe_id)
    payload = _build_payload(body)
    db_obj = Investition(**payload)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    sg_map, bg_map = _load_link_maps(db)
    return _to_read(db_obj, sg_map, bg_map)


@router.put("/{item_id}", response_model=InvestitionRead)
def update_investition(
    item_id: int,
    body: InvestitionUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    row = investition_crud.get(db, item_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investition nicht gefunden")
    calc_id = body.calculation_id if body.calculation_id is not None else row.calculation_id
    bg_id = body.baugruppe_id if body.baugruppe_id is not None else row.baugruppe_id
    if calc_id is not None and bg_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investition kann nur einem Einzelteil oder einer Baugruppe zugeordnet werden.",
        )
    _validate_links(db, calc_id, bg_id)
    payload = _build_payload(body, existing=row)
    for field, value in payload.items():
        setattr(row, field, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    sg_map, bg_map = _load_link_maps(db)
    return _to_read(row, sg_map, bg_map)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_investition(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    row = investition_crud.get(db, item_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investition nicht gefunden")
    row.archived = True
    db.add(row)
    db.commit()
