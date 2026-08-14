from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.permissions import require_viewer
from app.database import get_db
from app.models.user import User
from app.schemas.business_case import BusinessCaseResponse
from app.services.business_case_overview import build_project_business_case

router = APIRouter(prefix="/business-cases", tags=["Business Case"])


@router.get("", response_model=BusinessCaseResponse)
def get_business_case(
    customer: str = Query(..., min_length=1),
    project: str = Query(..., min_length=1),
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
    data = build_project_business_case(
        db,
        customer=customer.strip(),
        project=project.strip(),
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
    )
    return BusinessCaseResponse(**data)
