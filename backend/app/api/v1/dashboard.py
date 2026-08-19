from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_viewer
from app.database import get_db
from app.models.baugruppe import Baugruppe
from app.models.investition import Investition
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.schemas.dashboard import AssemblyOverview, DashboardSummary
from app.services.dashboard import (
    BaugruppeRecord,
    InvestitionRecord,
    SpritzgussRecord,
    build_dashboard_summary,
    parse_json_dict,
)
from app.services.dashboard_assembly import build_assembly_overview

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _load_spritzguss_records(db: Session) -> list[SpritzgussRecord]:
    rows = db.scalars(select(SpritzgussKalkulation)).all()
    return [
        SpritzgussRecord(
            id=row.id,
            teilebezeichnung=row.teilebezeichnung,
            teilenummer=row.teilenummer,
            kunde=row.kunde,
            projekt=row.projekt,
            jahresstueckzahl=row.jahresstueckzahl,
            aktiv=row.aktiv,
            ergebnis=parse_json_dict(row.ergebnis),
            created_at=row.created_at,
            updated_at=row.updated_at,
            status="aktiv" if row.aktiv else "inaktiv",
        )
        for row in rows
    ]


def _load_baugruppe_records(db: Session) -> list[BaugruppeRecord]:
    rows = db.scalars(select(Baugruppe)).all()
    return [
        BaugruppeRecord(
            id=row.id,
            name=row.name,
            teilenummer=row.teilenummer,
            kunde=row.kunde,
            projekt=row.projekt,
            jahresstueckzahl=row.jahresstueckzahl,
            aktiv=row.aktiv,
            ergebnis=parse_json_dict(row.ergebnis),
            created_at=row.created_at,
            updated_at=row.updated_at,
            status=row.status or "entwurf",
        )
        for row in rows
    ]


def _load_investition_records(db: Session) -> list[InvestitionRecord]:
    sg_map = {
        row.id: row
        for row in db.scalars(select(SpritzgussKalkulation)).all()
    }
    bg_map = {row.id: row for row in db.scalars(select(Baugruppe)).all()}
    rows = db.scalars(select(Investition).where(Investition.archived.is_(False))).all()
    result: list[InvestitionRecord] = []
    for row in rows:
        kunde = row.customer or ""
        projekt = row.project_id or ""
        if not kunde and row.calculation_id and row.calculation_id in sg_map:
            sg = sg_map[row.calculation_id]
            kunde = sg.kunde
            projekt = sg.projekt or projekt
        elif row.baugruppe_id and row.baugruppe_id in bg_map:
            bg = bg_map[row.baugruppe_id]
            kunde = bg.kunde
            projekt = bg.projekt or projekt
        result.append(
            InvestitionRecord(
                id=row.id,
                project_id=row.project_id or "",
                calculation_id=row.calculation_id,
                baugruppe_id=row.baugruppe_id,
                part_name=row.part_name,
                description=row.description,
                amount=float(row.amount),
                investment_type=row.investment_type,
                payment_type=row.payment_type,
                status=row.status,
                kunde=kunde,
                projekt=projekt,
                supplier=row.supplier or "",
                order_date=row.order_date,
                delivery_date=row.delivery_date,
                amortization_volume=row.amortization_volume,
                cost_per_piece=row.cost_per_piece,
                created_at=row.created_at,
                name=row.name or "",
            )
        )
    return result


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    project: str | None = Query(default=None, description="Filter nach Projekt"),
    customer: str | None = Query(default=None, description="Filter nach Kunde"),
    status: str | None = Query(default=None, description="Filter nach Status"),
    date_from: date | None = Query(default=None, description="Zeitraum von"),
    date_to: date | None = Query(default=None, description="Zeitraum bis"),
    kalkulationsart: str | None = Query(default=None, description="Spritzguss oder Baugruppe"),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Management-Übersicht mit KPIs, Tabellen und Diagrammdaten."""
    summary = build_dashboard_summary(
        _load_spritzguss_records(db),
        _load_baugruppe_records(db),
        _load_investition_records(db),
        project=project or None,
        customer=customer or None,
        status=status or None,
        date_from=date_from,
        date_to=date_to,
        kalkulationsart=kalkulationsart or None,
    )
    return DashboardSummary(**summary)


@router.get("/assemblies/{assembly_id}", response_model=AssemblyOverview)
def get_assembly_overview(
    assembly_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Read-only Baugruppendetail für Dashboard und Export-Vorschau."""
    return AssemblyOverview(**build_assembly_overview(db, assembly_id))
