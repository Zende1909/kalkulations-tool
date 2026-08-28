from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.permissions import require_viewer
from app.database import get_db
from app.models.user import User
from app.services.business_case_export import build_business_case_export, render_business_case_excel
from app.services.export_builders import (
    baugruppe_export_filename,
    build_baugruppe_export,
    build_dashboard_export,
    build_spritzguss_export,
    dashboard_export_filename,
    spritzguss_export_filename,
)
from app.services.export_excel import (
    render_baugruppe_excel,
    render_dashboard_excel,
    render_spritzguss_excel,
)
from app.services.export_pdf import (
    render_baugruppe_pdf,
    render_business_case_pdf,
    render_dashboard_pdf,
    render_spritzguss_pdf,
)

router = APIRouter(prefix="/reports", tags=["Reports"])


def _file_response(content: bytes, filename: str, media_type: str) -> Response:
    encoded = quote(filename)
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded}",
        },
    )


@router.get("/spritzguss/{calculation_id}.pdf")
def export_spritzguss_pdf(
    calculation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_spritzguss_export(db, calculation_id)
    pdf = render_spritzguss_pdf(data)
    return _file_response(pdf, spritzguss_export_filename(data, "pdf"), "application/pdf")


@router.get("/spritzguss/{calculation_id}.xlsx")
def export_spritzguss_xlsx(
    calculation_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_spritzguss_export(db, calculation_id)
    xlsx = render_spritzguss_excel(data)
    return _file_response(
        xlsx,
        spritzguss_export_filename(data, "xlsx"),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/baugruppen/{assembly_id}.pdf")
def export_baugruppe_pdf(
    assembly_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_baugruppe_export(db, assembly_id)
    pdf = render_baugruppe_pdf(data)
    return _file_response(pdf, baugruppe_export_filename(data, "pdf"), "application/pdf")


@router.get("/baugruppen/{assembly_id}.xlsx")
def export_baugruppe_xlsx(
    assembly_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_baugruppe_export(db, assembly_id)
    xlsx = render_baugruppe_excel(data)
    return _file_response(
        xlsx,
        baugruppe_export_filename(data, "xlsx"),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/dashboard.pdf")
def export_dashboard_pdf(
    project: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    kalkulationsart: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_dashboard_export(
        db,
        project=project or None,
        customer=customer or None,
        status=status or None,
        date_from=date_from,
        date_to=date_to,
        kalkulationsart=kalkulationsart or None,
    )
    pdf = render_dashboard_pdf(data)
    return _file_response(pdf, dashboard_export_filename(data, "pdf"), "application/pdf")


@router.get("/dashboard.xlsx")
def export_dashboard_xlsx(
    project: str | None = Query(default=None),
    customer: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    kalkulationsart: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_dashboard_export(
        db,
        project=project or None,
        customer=customer or None,
        status=status or None,
        date_from=date_from,
        date_to=date_to,
        kalkulationsart=kalkulationsart or None,
    )
    xlsx = render_dashboard_excel(data)
    return _file_response(
        xlsx,
        dashboard_export_filename(data, "xlsx"),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/business-case.xlsx")
def export_business_case_xlsx(
    customer_id: int = Query(..., ge=1),
    program_id: int = Query(..., ge=1),
    linked_project_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_business_case_export(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    xlsx = render_business_case_excel(data)
    safe_name = data.project.replace(" ", "_")
    return _file_response(
        xlsx,
        f"business_case_{safe_name}.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/business-case.pdf")
def export_business_case_pdf(
    customer_id: int = Query(..., ge=1),
    program_id: int = Query(..., ge=1),
    linked_project_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    data = build_business_case_export(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    pdf = render_business_case_pdf(data)
    safe_name = data.project.replace(" ", "_")
    return _file_response(
        pdf,
        f"business_case_{safe_name}.pdf",
        "application/pdf",
    )
