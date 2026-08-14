"""D-1-Prozessprüfung für Baugruppenstruktur (Phase C – nur Warnings)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.assembly_calculation import CalculationWarning


def _embedded_part_process_ids(db: Session, assembly_id: int) -> dict[int, str]:
    """Veredelungsschritt-IDs aus PART-Prozessketten in derselben Baugruppe."""
    part_ids = [
        row
        for row in db.scalars(
            select(AssemblyPosition.part_calculation_id).where(
                AssemblyPosition.parent_assembly_id == assembly_id,
                AssemblyPosition.position_type == "PART",
                AssemblyPosition.part_calculation_id.is_not(None),
            )
        ).all()
        if row is not None
    ]
    embedded: dict[int, str] = {}
    for part_id in part_ids:
        for zuordnung in db.scalars(
            select(SpritzgussVeredelungZuordnung).where(
                SpritzgussVeredelungZuordnung.kalkulation_id == part_id,
                SpritzgussVeredelungZuordnung.aktiv.is_(True),
            )
        ).all():
            name = zuordnung.snapshot_bezeichnung
            if not name:
                schritt = db.get(Veredelungsschritt, zuordnung.veredelungsschritt_id)
                name = schritt.bezeichnung if schritt else str(zuordnung.veredelungsschritt_id)
            embedded[zuordnung.veredelungsschritt_id] = name
    return embedded


def collect_duplicate_process_warnings(
    db: Session,
    assembly_id: int,
    positions: list[AssemblyPosition],
) -> list[CalculationWarning]:
    """Warnung wenn Prozess in PART-Kette und zusätzlich als PROCESS in derselben Baugruppe."""
    embedded = _embedded_part_process_ids(db, assembly_id)
    if not embedded:
        return []

    warnings: list[CalculationWarning] = []
    seen: set[int] = set()
    for index, pos in enumerate(
        sorted((p for p in positions if p.active), key=lambda p: p.sequence),
        start=1,
    ):
        if pos.position_type != "PROCESS" or not pos.finishing_step_id:
            continue
        step_id = pos.finishing_step_id
        if step_id not in embedded or step_id in seen:
            continue
        seen.add(step_id)
        process_name = pos.name_snapshot or embedded.get(step_id, str(step_id))
        warnings.append(
            CalculationWarning(
                code="DUPLICATE_PROCESS_REVIEW",
                message=(
                    f"Der Prozess '{process_name}' ist bereits in der Einzelteil-Prozesskette "
                    "enthalten und zusätzlich der Baugruppe zugeordnet. Bitte fachlich prüfen."
                ),
                position_id=pos.id,
            )
        )
    return warnings
