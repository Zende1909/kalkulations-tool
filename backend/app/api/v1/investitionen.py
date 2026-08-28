from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.crud.investition import investition as investition_crud
from app.database import get_db
from app.models.baugruppe import Baugruppe
from app.models.customer import Customer
from app.models.investition import Investition
from app.models.kaufteil import Kaufteil
from app.models.program import Program
from app.models.project import Project
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.schemas.investition import (
    InvestitionCreate,
    InvestitionRead,
    InvestitionTargetRead,
    InvestitionUpdate,
)
from app.services.investition_assignment_service import (
    ASSIGNMENT_TYPE_LABELS,
    infer_assignment_type,
    list_investment_targets,
    validate_assignment_payload,
)
from app.services.investition_service import EINMALZAHLUNG_HINWEIS, validate_investition_input, zuordnung_label

router = APIRouter(prefix="/investitionen", tags=["Investitionen"])


def _load_link_maps(
    db: Session,
) -> tuple[
    dict[int, SpritzgussKalkulation],
    dict[int, Baugruppe],
    dict[int, Kaufteil],
    dict[int, Customer],
    dict[int, Program],
    dict[int, Project],
]:
    sg_map = {row.id: row for row in db.scalars(select(SpritzgussKalkulation)).all()}
    bg_map = {row.id: row for row in db.scalars(select(Baugruppe)).all()}
    kt_map = {row.id: row for row in db.scalars(select(Kaufteil)).all()}
    customer_map = {row.id: row for row in db.scalars(select(Customer)).all()}
    program_map = {row.id: row for row in db.scalars(select(Program)).all()}
    project_map = {row.id: row for row in db.scalars(select(Project)).all()}
    return sg_map, bg_map, kt_map, customer_map, program_map, project_map


def _to_read(
    row: Investition,
    sg_map: dict[int, SpritzgussKalkulation],
    bg_map: dict[int, Baugruppe],
    kt_map: dict[int, Kaufteil],
    customer_map: dict[int, Customer],
    program_map: dict[int, Program],
    project_map: dict[int, Project],
) -> InvestitionRead:
    calc = sg_map.get(row.calculation_id) if row.calculation_id else None
    bg = bg_map.get(row.baugruppe_id) if row.baugruppe_id else None
    kt = kt_map.get(row.kaufteil_id) if row.kaufteil_id else None
    customer = customer_map.get(row.customer_id) if row.customer_id else None
    program = program_map.get(row.program_id) if row.program_id else None
    project = project_map.get(row.linked_project_id) if row.linked_project_id else None
    atype = infer_assignment_type(
        assignment_type=row.assignment_type,
        calculation_id=row.calculation_id,
        baugruppe_id=row.baugruppe_id,
        kaufteil_id=row.kaufteil_id,
    )
    return InvestitionRead(
        id=row.id,
        name=row.name or row.description or row.part_name,
        investment_type=row.investment_type,
        payment_type=row.payment_type,
        amount=float(row.amount),
        amortization_volume=row.amortization_volume,
        cost_per_piece=row.cost_per_piece,
        project=project.name if project else (row.project_id or ""),
        customer=customer.name if customer else (row.customer or ""),
        customer_id=row.customer_id,
        program_id=row.program_id,
        linked_project_id=row.linked_project_id,
        assignment_type=atype,
        assignment_type_label=ASSIGNMENT_TYPE_LABELS.get(atype or "", ""),
        part_number=row.part_number or "",
        part_name=row.part_name or "",
        calculation_id=row.calculation_id,
        baugruppe_id=row.baugruppe_id,
        kaufteil_id=row.kaufteil_id,
        description=row.description or "",
        included_in_unit_price=bool(row.included_in_unit_price),
        archived=bool(row.archived),
        zuordnung=zuordnung_label(
            calculation_id=row.calculation_id,
            baugruppe_id=row.baugruppe_id,
            kaufteil_id=row.kaufteil_id,
            assignment_type=atype,
            part_number=row.part_number or "",
            part_name=row.part_name or "",
            project_id=row.project_id or "",
            calc_teilenummer=calc.teilenummer if calc else None,
            calc_bezeichnung=calc.teilebezeichnung if calc else None,
            bg_name=bg.name if bg else None,
            bg_teilenummer=bg.teilenummer if bg else None,
            kt_bezeichnung=kt.bezeichnung if kt else None,
            kt_artikelnummer=kt.artikelnummer if kt else None,
            customer_name=customer.name if customer else row.customer or None,
            program_name=program.name if program else None,
            project_name=project.name if project else row.project_id or None,
        ),
        payment_hint=EINMALZAHLUNG_HINWEIS if row.payment_type == "Einmalzahlung" else "",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _validate_exclusive_links(
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None,
) -> None:
    ids = [x for x in (calculation_id, baugruppe_id, kaufteil_id) if x is not None]
    if len(ids) > 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investition kann nur einem Zielobjekt zugeordnet werden.",
        )


def _build_payload(
    body: InvestitionCreate | InvestitionUpdate,
    db: Session,
    existing: Investition | None = None,
) -> dict:
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
                "customer_id": existing.customer_id,
                "program_id": existing.program_id,
                "linked_project_id": existing.linked_project_id,
                "assignment_type": existing.assignment_type,
                "calculation_id": existing.calculation_id,
                "baugruppe_id": existing.baugruppe_id,
                "kaufteil_id": existing.kaufteil_id,
                "included_in_unit_price": existing.included_in_unit_price,
                "status": existing.status,
            }
            merged.update(data)
            data = merged

    has_hierarchy = (
        data.get("customer_id") is not None
        and data.get("program_id") is not None
        and data.get("linked_project_id") is not None
    )
    assignment_fields = validate_assignment_payload(
        db,
        customer_id=data.get("customer_id"),
        program_id=data.get("program_id"),
        linked_project_id=data.get("linked_project_id"),
        assignment_type=data.get("assignment_type"),
        calculation_id=data.get("calculation_id"),
        baugruppe_id=data.get("baugruppe_id"),
        kaufteil_id=data.get("kaufteil_id"),
        require_hierarchy=has_hierarchy,
    )
    if assignment_fields:
        data.update(assignment_fields)

    project_name = data.get("project") or assignment_fields.get("project_id") or ""
    if not str(project_name).strip() and data.get("linked_project_id"):
        project = db.get(Project, data["linked_project_id"])
        if project:
            project_name = project.name

    computed = validate_investition_input(
        name=data["name"],
        investment_type=data["investment_type"],
        payment_type=data["payment_type"],
        amount=float(data["amount"]),
        amortization_volume=data.get("amortization_volume"),
        project=str(project_name),
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
        "project_id": str(project_name).strip(),
        "customer": data.get("customer", "") or "",
        "part_name": data.get("part_name", "") or "",
        "part_number": data.get("part_number", "") or "",
        "calculation_id": data.get("calculation_id"),
        "baugruppe_id": data.get("baugruppe_id"),
        "kaufteil_id": data.get("kaufteil_id"),
        "customer_id": data.get("customer_id"),
        "program_id": data.get("program_id"),
        "linked_project_id": data.get("linked_project_id"),
        "assignment_type": data.get("assignment_type"),
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
    linked_project_id: int | None,
    customer: str | None,
    customer_id: int | None,
    program_id: int | None,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None,
    assignment_type: str | None,
    investment_type: str | None,
    payment_type: str | None,
    scope: str | None = None,
    search: str | None,
    include_archived: bool,
):
    if not include_archived:
        stmt = stmt.where(Investition.archived.is_(False))
    if linked_project_id is not None:
        stmt = stmt.where(Investition.linked_project_id == linked_project_id)
    elif project:
        stmt = stmt.where(Investition.project_id == project)
    if customer_id is not None:
        stmt = stmt.where(Investition.customer_id == customer_id)
    elif customer:
        stmt = stmt.where(Investition.customer == customer)
    if program_id is not None:
        stmt = stmt.where(Investition.program_id == program_id)
    if assignment_type:
        if assignment_type == "gesamtprojekt":
            stmt = stmt.where(
                or_(
                    Investition.assignment_type == "gesamtprojekt",
                    Investition.assignment_type.is_(None),
                ),
                Investition.calculation_id.is_(None),
                Investition.baugruppe_id.is_(None),
                Investition.kaufteil_id.is_(None),
            )
        else:
            stmt = stmt.where(Investition.assignment_type == assignment_type)
    if calculation_id is not None:
        stmt = stmt.where(Investition.calculation_id == calculation_id)
    elif baugruppe_id is not None:
        stmt = stmt.where(Investition.baugruppe_id == baugruppe_id)
    elif kaufteil_id is not None:
        stmt = stmt.where(Investition.kaufteil_id == kaufteil_id)
    elif scope == "gesamtprojekt":
        stmt = stmt.where(
            Investition.calculation_id.is_(None),
            Investition.baugruppe_id.is_(None),
            Investition.kaufteil_id.is_(None),
        )
    elif scope == "einzelteil":
        stmt = stmt.where(Investition.calculation_id.is_not(None))
    elif scope == "baugruppe":
        stmt = stmt.where(Investition.baugruppe_id.is_not(None))
    elif scope == "kaufteil":
        stmt = stmt.where(Investition.kaufteil_id.is_not(None))
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


@router.get("/targets", response_model=list[InvestitionTargetRead])
def list_investition_targets(
    customer_id: int = Query(...),
    program_id: int = Query(...),
    project_id: int = Query(...),
    assignment_type: str = Query(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    targets = list_investment_targets(
        db,
        customer_id=customer_id,
        program_id=program_id,
        project_id=project_id,
        assignment_type=assignment_type,
    )
    return [InvestitionTargetRead.model_validate(t, from_attributes=True) for t in targets]


@router.get("", response_model=list[InvestitionRead])
def list_investitionen(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=1000),
    project: str | None = Query(default=None),
    linked_project_id: int | None = Query(default=None),
    customer: str | None = Query(default=None),
    customer_id: int | None = Query(default=None),
    program_id: int | None = Query(default=None),
    calculation_id: int | None = Query(default=None),
    baugruppe_id: int | None = Query(default=None),
    kaufteil_id: int | None = Query(default=None),
    assignment_type: str | None = Query(default=None),
    investment_type: str | None = Query(default=None),
    payment_type: str | None = Query(default=None),
    scope: str | None = Query(default=None),
    search: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    if linked_project_id is None and (not project or not project.strip()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt (Name oder linked_project_id) ist erforderlich, um Investitionen zu laden.",
        )
    stmt = select(Investition)
    stmt = _apply_filters(
        stmt,
        project=project,
        linked_project_id=linked_project_id,
        customer=customer,
        customer_id=customer_id,
        program_id=program_id,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        kaufteil_id=kaufteil_id,
        assignment_type=assignment_type,
        scope=scope,
        investment_type=investment_type,
        payment_type=payment_type,
        search=search,
        include_archived=include_archived,
    )
    stmt = stmt.order_by(Investition.updated_at.desc()).offset(skip).limit(limit)
    rows = list(db.scalars(stmt).all())
    maps = _load_link_maps(db)
    return [_to_read(row, *maps) for row in rows]


@router.get("/{item_id}", response_model=InvestitionRead)
def get_investition(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    row = investition_crud.get(db, item_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Investition nicht gefunden")
    maps = _load_link_maps(db)
    return _to_read(row, *maps)


@router.post("", response_model=InvestitionRead, status_code=status.HTTP_201_CREATED)
def create_investition(
    body: InvestitionCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    _validate_exclusive_links(body.calculation_id, body.baugruppe_id, body.kaufteil_id)
    payload = _build_payload(body, db)
    db_obj = Investition(**payload)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    maps = _load_link_maps(db)
    return _to_read(db_obj, *maps)


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
    merged_calc = body.calculation_id if "calculation_id" in body.model_dump(exclude_unset=True) else row.calculation_id
    merged_bg = body.baugruppe_id if "baugruppe_id" in body.model_dump(exclude_unset=True) else row.baugruppe_id
    merged_kt = body.kaufteil_id if "kaufteil_id" in body.model_dump(exclude_unset=True) else row.kaufteil_id
    _validate_exclusive_links(merged_calc, merged_bg, merged_kt)
    payload = _build_payload(body, db, existing=row)
    for field, value in payload.items():
        setattr(row, field, value)
    db.add(row)
    db.commit()
    db.refresh(row)
    maps = _load_link_maps(db)
    return _to_read(row, *maps)


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
