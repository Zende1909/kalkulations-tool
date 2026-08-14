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
    InvestitionSummary,
    InvestitionUpdate,
)
from app.services.investition_service import (
    EINMALZAHLUNG_HINWEIS,
    validate_investition_input,
    zuordnung_label,
)

router = APIRouter(prefix="/investitionen", tags=["Investitionen"])

SORT_FIELDS = {
    "amount": Investition.amount,
    "status": Investition.status,
    "delivery_date": Investition.delivery_date,
    "order_date": Investition.order_date,
    "created_at": Investition.created_at,
    "updated_at": Investition.updated_at,
}


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
        name=row.name,
        investment_type=row.investment_type,
        payment_type=row.payment_type,
        amount=float(row.amount),
        amortization_volume=row.amortization_volume,
        cost_per_piece=row.cost_per_piece,
        project=row.project_id or "",
        customer=row.customer or "",
        part_name=row.part_name or "",
        part_number=row.part_number or "",
        calculation_id=row.calculation_id,
        baugruppe_id=row.baugruppe_id,
        supplier=row.supplier or "",
        order_date=row.order_date,
        delivery_date=row.delivery_date,
        status=row.status,
        description=row.description or "",
        included_in_unit_price=bool(row.included_in_unit_price),
        archived=bool(row.archived),
        zuordnung=zuordnung_label(
            calculation_id=row.calculation_id,
            baugruppe_id=row.baugruppe_id,
            part_number=row.part_number,
            part_name=row.part_name,
            project_id=row.project_id,
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Einzelteil-Kalkulation nicht gefunden")
    if baugruppe_id is not None and not db.get(Baugruppe, baugruppe_id):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Baugruppe nicht gefunden")


def _build_payload(body: InvestitionCreate | InvestitionUpdate, existing: Investition | None = None) -> dict:
    if isinstance(body, InvestitionCreate):
        data = body.model_dump()
    else:
        data = body.model_dump(exclude_unset=True)
        if existing is not None:
            merged = {
                "name": existing.name,
                "investment_type": existing.investment_type,
                "payment_type": existing.payment_type,
                "amount": existing.amount,
                "amortization_volume": existing.amortization_volume,
                "status": existing.status,
                "calculation_id": existing.calculation_id,
                "included_in_unit_price": existing.included_in_unit_price,
            }
            merged.update(data)
            data = merged

    computed = validate_investition_input(
        name=data["name"],
        investment_type=data["investment_type"],
        payment_type=data["payment_type"],
        amount=float(data["amount"]),
        amortization_volume=data.get("amortization_volume"),
        status_value=data["status"],
        calculation_id=data.get("calculation_id"),
        included_in_unit_price=data.get("included_in_unit_price"),
    )
    db_payload = {
        "name": data["name"].strip(),
        "investment_type": data["investment_type"],
        "payment_type": data["payment_type"],
        "amount": float(data["amount"]),
        "project_id": data.get("project", "") or "",
        "customer": data.get("customer", "") or "",
        "part_name": data.get("part_name", "") or "",
        "part_number": data.get("part_number", "") or "",
        "calculation_id": data.get("calculation_id"),
        "baugruppe_id": data.get("baugruppe_id"),
        "supplier": data.get("supplier", "") or "",
        "order_date": data.get("order_date"),
        "delivery_date": data.get("delivery_date"),
        "status": data["status"],
        "description": data.get("description", "") or "",
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
    investment_type: str | None,
    payment_type: str | None,
    status_filter: str | None,
    search: str | None,
    include_archived: bool,
):
    if not include_archived:
        stmt = stmt.where(Investition.archived.is_(False))
    if project:
        stmt = stmt.where(Investition.project_id == project)
    if customer:
        stmt = stmt.where(Investition.customer == customer)
    if investment_type:
        stmt = stmt.where(Investition.investment_type == investment_type)
    if payment_type:
        stmt = stmt.where(Investition.payment_type == payment_type)
    if status_filter:
        stmt = stmt.where(Investition.status == status_filter)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Investition.name.ilike(term),
                Investition.description.ilike(term),
                Investition.part_name.ilike(term),
                Investition.part_number.ilike(term),
                Investition.supplier.ilike(term),
                Investition.project_id.ilike(term),
                Investition.customer.ilike(term),
            )
        )
    return stmt


@router.get("/summary", response_model=InvestitionSummary)
def get_investition_summary(
    project: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    investment_type: str | None = Query(default=None),
    payment_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Investition)
    stmt = _apply_filters(
        stmt,
        project=project,
        customer=customer,
        investment_type=investment_type,
        payment_type=payment_type,
        status_filter=status_filter,
        search=search,
        include_archived=False,
    )
    rows = list(db.scalars(stmt).all())
    einmal = [r for r in rows if r.payment_type == "Einmalzahlung"]
    amort = [r for r in rows if r.payment_type == "Amortisation"]
    return InvestitionSummary(
        gesamtinvestitionen=round(sum(float(r.amount) for r in rows), 2),
        anzahl_investitionen=len(rows),
        summe_einmalzahlungen=round(sum(float(r.amount) for r in einmal), 2),
        summe_amortisiert=round(sum(float(r.amount) for r in amort), 2),
        in_planung=sum(1 for r in rows if r.status == "In Planung"),
        bestellt=sum(1 for r in rows if r.status == "Bestellt"),
        abgeschlossen=sum(1 for r in rows if r.status == "Abgeschlossen"),
    )


@router.get("", response_model=list[InvestitionRead])
def list_investitionen(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    project: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    investment_type: str | None = Query(default=None),
    payment_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="updated_at"),
    sort_dir: str = Query(default="desc"),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    sort_col = SORT_FIELDS.get(sort_by, Investition.updated_at)
    stmt = select(Investition)
    stmt = _apply_filters(
        stmt,
        project=project,
        customer=customer,
        investment_type=investment_type,
        payment_type=payment_type,
        status_filter=status_filter,
        search=search,
        include_archived=include_archived,
    )
    if sort_dir.lower() == "asc":
        stmt = stmt.order_by(sort_col.asc())
    else:
        stmt = stmt.order_by(sort_col.desc())
    stmt = stmt.offset(skip).limit(limit)
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
