from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.business_case_manual_price import BusinessCaseManualPrice
from app.models.user import User
from app.schemas.business_case import (
    BusinessCaseResponse,
    ManualPriceRead,
    ManualPriceUpsert,
)
from app.services.business_case_overview import build_project_business_case

router = APIRouter(prefix="/business-cases", tags=["Business Case"])


@router.get("", response_model=BusinessCaseResponse)
def get_business_case(
    customer_id: int = Query(..., ge=1),
    program_id: int = Query(..., ge=1),
    linked_project_id: int = Query(..., ge=1),
    calculation_id: int | None = Query(default=None),
    baugruppe_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    if calculation_id is not None and baugruppe_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Einzelteil und Baugruppe können nicht gleichzeitig gefiltert werden.",
        )
    try:
        data = build_project_business_case(
            db,
            customer_id=customer_id,
            program_id=program_id,
            linked_project_id=linked_project_id,
            calculation_id=calculation_id,
            baugruppe_id=baugruppe_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return BusinessCaseResponse(**data)


@router.put("/manual-prices", response_model=ManualPriceRead)
def upsert_manual_price(
    body: ManualPriceUpsert,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    try:
        build_project_business_case(
            db,
            customer_id=body.customer_id,
            program_id=body.program_id,
            linked_project_id=body.linked_project_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    row = db.scalar(
        select(BusinessCaseManualPrice).where(
            BusinessCaseManualPrice.customer_id == body.customer_id,
            BusinessCaseManualPrice.program_id == body.program_id,
            BusinessCaseManualPrice.linked_project_id == body.linked_project_id,
            BusinessCaseManualPrice.assignment_type == body.assignment_type,
            BusinessCaseManualPrice.object_id == body.object_id,
        )
    )
    if row is None:
        row = BusinessCaseManualPrice(
            customer_id=body.customer_id,
            program_id=body.program_id,
            linked_project_id=body.linked_project_id,
            assignment_type=body.assignment_type,
            object_id=body.object_id,
        )
        db.add(row)
    row.bottom_price_per_piece = body.bottom_price_per_piece
    row.actual_price_per_piece = body.actual_price_per_piece
    db.commit()
    db.refresh(row)
    return ManualPriceRead(
        id=row.id,
        customer_id=row.customer_id,
        program_id=row.program_id,
        linked_project_id=row.linked_project_id,
        assignment_type=row.assignment_type,
        object_id=row.object_id,
        bottom_price_per_piece=row.bottom_price_per_piece,
        actual_price_per_piece=row.actual_price_per_piece,
    )
