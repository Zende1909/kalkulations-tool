from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud import customer as customer_crud
from app.database import get_db
from app.models.customer import Customer
from app.models.user import User
from app.models.program import Program
from app.schemas.hierarchy import CustomerCreate, CustomerRead, CustomerUpdate, ProgramRead

router = APIRouter(prefix="/customers", tags=["Kunden"])


def _get_customer_or_404(db: Session, customer_id: int) -> Customer:
    if customer_id < 1:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ungültige Kunden-ID")
    item = customer_crud.customer.get(db, customer_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Kunde nicht gefunden")
    return item


@router.get("", response_model=list[CustomerRead])
def list_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    search: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Customer)
    if active is not None:
        stmt = stmt.where(Customer.active.is_(active))
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(Customer.name.ilike(term), Customer.customer_number.ilike(term))
        )
    stmt = stmt.order_by(Customer.name.asc()).offset(skip).limit(limit)
    return list(db.scalars(stmt).all())


@router.get("/{item_id}", response_model=CustomerRead)
def get_customer(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return _get_customer_or_404(db, item_id)


@router.post("", response_model=CustomerRead, status_code=status.HTTP_201_CREATED)
def create_customer(
    item_in: CustomerCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    return customer_crud.customer.create(db, item_in)


@router.put("/{item_id}", response_model=CustomerRead)
def update_customer(
    item_id: int,
    item_in: CustomerUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_customer_or_404(db, item_id)
    return customer_crud.customer.update(db, item, item_in)


@router.get("/{customer_id}/programs", response_model=list[ProgramRead])
def list_customer_programs(
    customer_id: int,
    active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    _get_customer_or_404(db, customer_id)
    stmt = select(Program).where(Program.customer_id == customer_id)
    if active is not None:
        stmt = stmt.where(Program.active.is_(active))
    stmt = stmt.order_by(Program.name.asc())
    return list(db.scalars(stmt).all())


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_customer(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    item = _get_customer_or_404(db, item_id)
    customer_crud.customer.update(db, item, CustomerUpdate(active=False))
