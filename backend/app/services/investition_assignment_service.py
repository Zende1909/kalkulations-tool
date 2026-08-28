"""Hierarchie- und Objektzuordnung für Investitionen.

IDs und Beziehungen (Stammdaten):
- Kunde: customers.id
- Programm: programs.id (programs.customer_id → customers.id)
- Projekt: projects.id (projects.program_id → programs.id)
- Einzelteil: spritzguss_kalkulationen.id, Materialnummer in teilenummer
- Kaufteil: kaufteile.id, Materialnummer in artikelnummer
- Baugruppe: baugruppen.id, Teilenummer in teilenummer

Bestehende Investitionen ohne assignment_type werden beim Lesen aus calculation_id /
baugruppe_id / kaufteil_id abgeleitet (Legacy-Kompatibilität).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.baugruppe import Baugruppe
from app.models.customer import Customer
from app.models.kaufteil import Kaufteil
from app.models.program import Program
from app.models.project import Project
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.services.dashboard import preis_aus_baugruppe
from app.services.spritzguss_cost_snapshot import selbstkosten_aus_ergebnis

ASSIGNMENT_TYPES = ("einzelteil", "kaufteil", "baugruppe", "gesamtprojekt")

ASSIGNMENT_TYPE_LABELS = {
    "einzelteil": "Einzelteil",
    "kaufteil": "Kaufteil",
    "baugruppe": "Baugruppe",
    "gesamtprojekt": "Gesamtprojekt",
}


@dataclass(frozen=True)
class HierarchyContext:
    customer_id: int
    program_id: int
    project_id: int
    customer_name: str
    program_name: str
    project_name: str


@dataclass(frozen=True)
class InvestitionTarget:
    object_id: int
    assignment_type: str
    label: str
    material_number: str
    part_name: str
    status: str | None = None
    part_price: float | None = None
    supplier: str | None = None
    nominierung: str | None = None
    customer_name: str | None = None
    program_name: str | None = None
    project_name: str | None = None


def infer_assignment_type(
    *,
    assignment_type: str | None,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None,
) -> str | None:
    if assignment_type in ASSIGNMENT_TYPES:
        return assignment_type
    if calculation_id is not None:
        return "einzelteil"
    if kaufteil_id is not None:
        return "kaufteil"
    if baugruppe_id is not None:
        return "baugruppe"
    return "gesamtprojekt"


def load_hierarchy_context(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    project_id: int,
) -> HierarchyContext:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt nicht gefunden.",
        )
    if project.program_id != program_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programm passt nicht zum ausgewählten Projekt.",
        )
    program = db.get(Program, program_id)
    if program is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programm nicht gefunden.",
        )
    if program.customer_id != customer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kunde passt nicht zum ausgewählten Programm.",
        )
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kunde nicht gefunden.",
        )
    if not customer.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kunde ist nicht aktiv.",
        )
    return HierarchyContext(
        customer_id=customer.id,
        program_id=program.id,
        project_id=project.id,
        customer_name=customer.name,
        program_name=program.name,
        project_name=project.name,
    )


def _baugruppe_project_match(baugruppe: Baugruppe, project_id: int) -> bool:
    effective = baugruppe.project_id or baugruppe.linked_project_id
    return effective == project_id


def list_investment_targets(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    project_id: int,
    assignment_type: str,
) -> list[InvestitionTarget]:
    if assignment_type not in ASSIGNMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültiger Zuordnungstyp: {assignment_type}",
        )
    ctx = load_hierarchy_context(
        db,
        customer_id=customer_id,
        program_id=program_id,
        project_id=project_id,
    )
    if assignment_type == "gesamtprojekt":
        return []

    if assignment_type == "einzelteil":
        rows = db.scalars(
            select(SpritzgussKalkulation)
            .where(
                SpritzgussKalkulation.project_id == ctx.project_id,
                SpritzgussKalkulation.aktiv.is_(True),
                SpritzgussKalkulation.teilenummer != "",
            )
            .order_by(SpritzgussKalkulation.teilenummer)
        ).all()
        result: list[InvestitionTarget] = []
        for row in rows:
            if row.customer_id is not None and row.customer_id != ctx.customer_id:
                continue
            if row.program_id is not None and row.program_id != ctx.program_id:
                continue
            ergebnis = row.ergebnis if isinstance(row.ergebnis, dict) else None
            result.append(
                InvestitionTarget(
                    object_id=row.id,
                    assignment_type="einzelteil",
                    label=f"{row.teilenummer} – {row.teilebezeichnung}",
                    material_number=row.teilenummer,
                    part_name=row.teilebezeichnung,
                    status="aktiv" if row.aktiv else "inaktiv",
                    part_price=selbstkosten_aus_ergebnis(ergebnis),
                )
            )
        return result

    if assignment_type == "kaufteil":
        rows = db.scalars(
            select(Kaufteil)
            .where(
                Kaufteil.project_id == ctx.project_id,
                Kaufteil.aktiv.is_(True),
                Kaufteil.artikelnummer != "",
            )
            .order_by(Kaufteil.artikelnummer)
        ).all()
        result = []
        for row in rows:
            if row.customer_id is not None and row.customer_id != ctx.customer_id:
                continue
            if row.program_id is not None and row.program_id != ctx.program_id:
                continue
            result.append(
                InvestitionTarget(
                    object_id=row.id,
                    assignment_type="kaufteil",
                    label=f"{row.artikelnummer} – {row.bezeichnung}",
                    material_number=row.artikelnummer,
                    part_name=row.bezeichnung,
                    status="aktiv" if row.aktiv else "inaktiv",
                    part_price=float(row.preis),
                    supplier=row.lieferant or None,
                    nominierung=row.nominierung,
                )
            )
        return result

    rows = db.scalars(
        select(Baugruppe)
        .where(
            or_(
                Baugruppe.project_id == ctx.project_id,
                Baugruppe.linked_project_id == ctx.project_id,
            ),
            Baugruppe.aktiv.is_(True),
        )
        .order_by(Baugruppe.teilenummer, Baugruppe.name)
    ).all()
    result = []
    for row in rows:
        if not _baugruppe_project_match(row, ctx.project_id):
            continue
        ergebnis = row.ergebnis if isinstance(row.ergebnis, dict) else None
        result.append(
            InvestitionTarget(
                object_id=row.id,
                assignment_type="baugruppe",
                label=f"{row.teilenummer} – {row.name}" if row.teilenummer else row.name,
                material_number=row.teilenummer or "",
                part_name=row.name,
                status=row.status,
                part_price=preis_aus_baugruppe(ergebnis),
                customer_name=row.kunde or ctx.customer_name,
                program_name=ctx.program_name,
                project_name=row.projekt or ctx.project_name,
            )
        )
    return result


def _resolve_object_fields(
    db: Session,
    *,
    assignment_type: str,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None,
    project_id: int,
) -> dict[str, Any]:
    if assignment_type == "einzelteil":
        if calculation_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Einzelteil-ID ist erforderlich.",
            )
        calc = db.get(SpritzgussKalkulation, calculation_id)
        if calc is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Einzelteil-Kalkulation nicht gefunden.",
            )
        if calc.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Einzelteil gehört nicht zum ausgewählten Projekt.",
            )
        if not (calc.teilenummer or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Einzelteil hat keine gültige Materialnummer.",
            )
        return {
            "calculation_id": calc.id,
            "baugruppe_id": None,
            "kaufteil_id": None,
            "part_number": calc.teilenummer.strip(),
            "part_name": calc.teilebezeichnung,
        }

    if assignment_type == "kaufteil":
        if kaufteil_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kaufteil-ID ist erforderlich.",
            )
        kt = db.get(Kaufteil, kaufteil_id)
        if kt is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kaufteil nicht gefunden.",
            )
        if kt.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kaufteil gehört nicht zum ausgewählten Projekt.",
            )
        if not (kt.artikelnummer or "").strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kaufteil hat keine gültige Materialnummer.",
            )
        return {
            "calculation_id": None,
            "baugruppe_id": None,
            "kaufteil_id": kt.id,
            "part_number": kt.artikelnummer.strip(),
            "part_name": kt.bezeichnung,
        }

    if assignment_type == "baugruppe":
        if baugruppe_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Baugruppen-ID ist erforderlich.",
            )
        bg = db.get(Baugruppe, baugruppe_id)
        if bg is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Baugruppe nicht gefunden.",
            )
        if not _baugruppe_project_match(bg, project_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Baugruppe gehört nicht zum ausgewählten Projekt.",
            )
        return {
            "calculation_id": None,
            "baugruppe_id": bg.id,
            "kaufteil_id": None,
            "part_number": (bg.teilenummer or "").strip(),
            "part_name": bg.name,
        }

    if calculation_id is not None or baugruppe_id is not None or kaufteil_id is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Gesamtprojekt-Investition darf kein Zielobjekt haben.",
        )
    return {
        "calculation_id": None,
        "baugruppe_id": None,
        "kaufteil_id": None,
        "part_number": "",
        "part_name": "",
    }


def validate_assignment_payload(
    db: Session,
    *,
    customer_id: int | None,
    program_id: int | None,
    linked_project_id: int | None,
    assignment_type: str | None,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
    kaufteil_id: int | None = None,
    require_hierarchy: bool = True,
) -> dict[str, Any]:
    """Validiert Hierarchie und Objektzuordnung; liefert DB-Felder für Persistenz."""
    if require_hierarchy:
        if customer_id is None or program_id is None or linked_project_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Kunde, Programm und Projekt sind für die Zuordnung erforderlich.",
            )
        if not assignment_type:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Zuordnungstyp ist erforderlich.",
            )

    resolved_type = infer_assignment_type(
        assignment_type=assignment_type,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        kaufteil_id=kaufteil_id,
    )
    if require_hierarchy and resolved_type not in ASSIGNMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültiger Zuordnungstyp: {assignment_type}",
        )

    if not require_hierarchy or linked_project_id is None:
        return {}

    ctx = load_hierarchy_context(
        db,
        customer_id=customer_id,  # type: ignore[arg-type]
        program_id=program_id,  # type: ignore[arg-type]
        project_id=linked_project_id,
    )
    object_fields = _resolve_object_fields(
        db,
        assignment_type=resolved_type or "gesamtprojekt",
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        kaufteil_id=kaufteil_id,
        project_id=ctx.project_id,
    )
    return {
        "customer_id": ctx.customer_id,
        "program_id": ctx.program_id,
        "linked_project_id": ctx.project_id,
        "assignment_type": resolved_type,
        "project_id": ctx.project_name,
        "customer": ctx.customer_name,
        **object_fields,
    }


def resolve_part_price_for_assignment(
    db: Session,
    *,
    assignment_type: str | None,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None,
) -> float | None:
    """Preisfeld je Objekttyp für Materialnummer-Matching (Auswertung).

    - Einzelteil: Selbstkosten/Herstellkosten aus gespeichertem Ergebnis
    - Kaufteil: Einkaufspreis (preis)
    - Baugruppe: baugruppenpreis_je_stueck aus gespeichertem Ergebnis
    """
    atype = infer_assignment_type(
        assignment_type=assignment_type,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        kaufteil_id=kaufteil_id,
    )
    if atype == "einzelteil" and calculation_id is not None:
        calc = db.get(SpritzgussKalkulation, calculation_id)
        if calc and isinstance(calc.ergebnis, dict):
            return selbstkosten_aus_ergebnis(calc.ergebnis)
    if atype == "kaufteil" and kaufteil_id is not None:
        kt = db.get(Kaufteil, kaufteil_id)
        if kt:
            return float(kt.preis)
    if atype == "baugruppe" and baugruppe_id is not None:
        bg = db.get(Baugruppe, baugruppe_id)
        if bg and isinstance(bg.ergebnis, dict):
            return preis_aus_baugruppe(bg.ergebnis)
    return None
