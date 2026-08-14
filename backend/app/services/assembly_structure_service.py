"""Service für Baugruppen-Struktur-API (Phase B – ohne Kalkulationslogik)."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import (
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
)
from app.models.kaufteil import Kaufteil
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.assembly_structure import (
    AssemblyPositionCreateRequest,
    AssemblyPositionInput,
    AssemblyPositionPatchRequest,
    AssemblyPositionRead,
    AssemblyStructureRead,
    AssemblyStructureReplaceRequest,
    ChildAssemblyPreview,
    PositionSnapshotRead,
    PositionsSource,
)

MAX_CHILD_PREVIEW_DEPTH = 1

_TYPE_TIEBREAKER = {
    "PART": 0,
    "PURCHASED_PART": 1,
    "PROCESS": 2,
}

_DEFAULT_PART_PRICE_BASIS = "COST"
_DEFAULT_SUBASSEMBLY_PRICE_BASIS = "COST"


class AssemblyStructureError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class _LegacySyntheticItem:
    position_type: str
    legacy_source: str
    reihenfolge: int
    legacy_row_id: int
    quantity: float
    quantity_factor: float
    part_calculation_id: int | None = None
    purchased_part_id: int | None = None
    finishing_step_id: int | None = None
    price_basis: str | None = None
    snapshots: PositionSnapshotRead | None = None


def effective_project_id(baugruppe: Baugruppe) -> int | None:
    return baugruppe.project_id or baugruppe.linked_project_id


def get_baugruppe_or_raise(db: Session, baugruppe_id: int) -> Baugruppe:
    obj = db.get(Baugruppe, baugruppe_id)
    if not obj:
        raise AssemblyStructureError("Baugruppe nicht gefunden", status_code=404)
    return obj


def load_positions(db: Session, parent_id: int) -> list[AssemblyPosition]:
    return list(
        db.scalars(
            select(AssemblyPosition)
            .where(AssemblyPosition.parent_assembly_id == parent_id)
            .order_by(AssemblyPosition.sequence)
        ).all()
    )


def _position_snapshots_from_orm(pos: AssemblyPosition) -> PositionSnapshotRead:
    return PositionSnapshotRead(
        cost_snapshot=pos.cost_snapshot,
        price_snapshot=pos.price_snapshot,
        name_snapshot=pos.name_snapshot or "",
        part_number_snapshot=pos.part_number_snapshot or "",
        supplier_snapshot=pos.supplier_snapshot or "",
        snapshots_captured_at=pos.snapshots_captured_at,
    )


def _position_to_read(
    pos: AssemblyPosition,
    *,
    child_assembly: ChildAssemblyPreview | None = None,
) -> AssemblyPositionRead:
    return AssemblyPositionRead(
        id=pos.id,
        position_type=pos.position_type,  # type: ignore[arg-type]
        sequence=pos.sequence,
        quantity=pos.quantity,
        quantity_factor=pos.quantity_factor,
        price_basis=pos.price_basis,  # type: ignore[arg-type]
        active=pos.active,
        label=pos.label,
        part_calculation_id=pos.part_calculation_id,
        purchased_part_id=pos.purchased_part_id,
        child_assembly_id=pos.child_assembly_id,
        finishing_step_id=pos.finishing_step_id,
        snapshots=_position_snapshots_from_orm(pos),
        child_assembly=child_assembly,
    )


def _synthetic_to_read(item: _LegacySyntheticItem, sequence: int) -> AssemblyPositionRead:
    return AssemblyPositionRead(
        id=None,
        position_type=item.position_type,  # type: ignore[arg-type]
        sequence=sequence,
        quantity=item.quantity,
        quantity_factor=item.quantity_factor,
        price_basis=item.price_basis,  # type: ignore[arg-type]
        active=True,
        label=None,
        part_calculation_id=item.part_calculation_id,
        purchased_part_id=item.purchased_part_id,
        child_assembly_id=None,
        finishing_step_id=item.finishing_step_id,
        snapshots=item.snapshots or PositionSnapshotRead(),
        legacy_source=item.legacy_source,  # type: ignore[arg-type]
    )


def build_legacy_synthetic_items(db: Session, baugruppe_id: int) -> list[_LegacySyntheticItem]:
    items: list[_LegacySyntheticItem] = []

    for row in db.scalars(
        select(BaugruppeSpritzgussZuordnung)
        .where(BaugruppeSpritzgussZuordnung.baugruppe_id == baugruppe_id)
        .order_by(BaugruppeSpritzgussZuordnung.reihenfolge, BaugruppeSpritzgussZuordnung.id)
    ).all():
        items.append(
            _LegacySyntheticItem(
                position_type="PART",
                legacy_source="spritzguss",
                reihenfolge=row.reihenfolge,
                legacy_row_id=row.id,
                quantity=row.menge,
                quantity_factor=1.0,
                part_calculation_id=row.spritzguss_kalkulation_id,
                price_basis=_DEFAULT_PART_PRICE_BASIS,
                snapshots=PositionSnapshotRead(
                    price_snapshot=row.snapshot_preis,
                    name_snapshot=row.snapshot_bezeichnung,
                    part_number_snapshot=row.snapshot_teilenummer,
                ),
            )
        )

    for row in db.scalars(
        select(BaugruppeKaufteilZuordnung)
        .where(BaugruppeKaufteilZuordnung.baugruppe_id == baugruppe_id)
        .order_by(BaugruppeKaufteilZuordnung.reihenfolge, BaugruppeKaufteilZuordnung.id)
    ).all():
        items.append(
            _LegacySyntheticItem(
                position_type="PURCHASED_PART",
                legacy_source="kaufteil",
                reihenfolge=row.reihenfolge,
                legacy_row_id=row.id,
                quantity=row.menge,
                quantity_factor=1.0,
                purchased_part_id=row.kaufteil_id,
                price_basis=None,
                snapshots=PositionSnapshotRead(
                    price_snapshot=row.snapshot_preis,
                    name_snapshot=row.snapshot_bezeichnung,
                    supplier_snapshot=row.snapshot_lieferant,
                ),
            )
        )

    for row in db.scalars(
        select(BaugruppeVeredelungZuordnung)
        .where(BaugruppeVeredelungZuordnung.baugruppe_id == baugruppe_id)
        .order_by(BaugruppeVeredelungZuordnung.reihenfolge, BaugruppeVeredelungZuordnung.id)
    ).all():
        items.append(
            _LegacySyntheticItem(
                position_type="PROCESS",
                legacy_source="veredelung",
                reihenfolge=row.reihenfolge,
                legacy_row_id=row.id,
                quantity=1.0,
                quantity_factor=row.mengenfaktor,
                finishing_step_id=row.veredelungsschritt_id,
                price_basis=None,
                snapshots=PositionSnapshotRead(
                    cost_snapshot=row.snapshot_kosten,
                    name_snapshot=row.snapshot_bezeichnung,
                ),
            )
        )

    items.sort(
        key=lambda item: (
            item.reihenfolge if item.reihenfolge is not None else 999_999,
            _TYPE_TIEBREAKER[item.position_type],
            item.legacy_row_id,
        )
    )
    return items


def build_legacy_synthetic_positions(
    db: Session, baugruppe_id: int
) -> list[AssemblyPositionRead]:
    items = build_legacy_synthetic_items(db, baugruppe_id)
    return [_synthetic_to_read(item, index) for index, item in enumerate(items, start=1)]


def build_child_preview(
    db: Session,
    child_id: int,
    *,
    depth: int,
    max_depth: int = MAX_CHILD_PREVIEW_DEPTH,
) -> ChildAssemblyPreview | None:
    child = db.get(Baugruppe, child_id)
    if not child:
        return None

    db_positions = load_positions(db, child_id)
    if db_positions:
        positions_source: PositionsSource = "assembly_positions"
        position_reads = []
        for pos in db_positions:
            nested = None
            if pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id and depth < max_depth:
                nested = build_child_preview(
                    db,
                    pos.child_assembly_id,
                    depth=depth + 1,
                    max_depth=max_depth,
                )
            position_reads.append(_position_to_read(pos, child_assembly=nested))
    elif child.legacy_mode:
        position_reads = build_legacy_synthetic_positions(db, child_id)
        positions_source = "legacy_synthetic" if position_reads else "empty"
    else:
        positions_source = "empty"
        position_reads = []

    return ChildAssemblyPreview(
        id=child.id,
        name=child.name,
        teilenummer=child.teilenummer,
        assembly_type=child.assembly_type,  # type: ignore[arg-type]
        structure_version=child.structure_version,
        legacy_mode=child.legacy_mode,
        positions=position_reads,
        positions_source=positions_source,
    )


def get_structure(db: Session, baugruppe_id: int) -> AssemblyStructureRead:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    db_positions = load_positions(db, baugruppe_id)

    if db_positions:
        positions_source: PositionsSource = "assembly_positions"
        position_reads: list[AssemblyPositionRead] = []
        for pos in db_positions:
            child_preview = None
            if pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id:
                child_preview = build_child_preview(db, pos.child_assembly_id, depth=0)
            position_reads.append(_position_to_read(pos, child_assembly=child_preview))
    elif baugruppe.legacy_mode:
        position_reads = build_legacy_synthetic_positions(db, baugruppe_id)
        if position_reads:
            positions_source = "legacy_synthetic"
        else:
            positions_source = "empty"
            position_reads = []
    else:
        positions_source = "empty"
        position_reads = []

    return AssemblyStructureRead(
        id=baugruppe.id,
        name=baugruppe.name,
        teilenummer=baugruppe.teilenummer,
        kunde=baugruppe.kunde,
        projekt=baugruppe.projekt,
        beschreibung=baugruppe.beschreibung,
        status=baugruppe.status,
        aktiv=baugruppe.aktiv,
        project_id=baugruppe.project_id,
        linked_project_id=baugruppe.linked_project_id,
        assembly_type=baugruppe.assembly_type,  # type: ignore[arg-type]
        structure_version=baugruppe.structure_version,
        legacy_mode=baugruppe.legacy_mode,
        pricing_status=baugruppe.pricing_status,
        positions_source=positions_source,
        positions=position_reads,
    )


def validate_position_refs(position: AssemblyPositionInput, index: int) -> None:
    prefix = f"Position #{index}"

    if position.position_type == "PART":
        if not position.part_calculation_id:
            raise AssemblyStructureError(f"{prefix}: PART benötigt part_calculation_id")
        if position.price_basis is None:
            raise AssemblyStructureError(f"{prefix}: PART benötigt price_basis")
        forbidden = [
            ("purchased_part_id", position.purchased_part_id),
            ("child_assembly_id", position.child_assembly_id),
            ("finishing_step_id", position.finishing_step_id),
        ]
        for name, value in forbidden:
            if value is not None:
                raise AssemblyStructureError(f"{prefix}: PART darf {name} nicht setzen")
    elif position.position_type == "PURCHASED_PART":
        if not position.purchased_part_id:
            raise AssemblyStructureError(f"{prefix}: PURCHASED_PART benötigt purchased_part_id")
        if position.price_basis is not None:
            raise AssemblyStructureError(f"{prefix}: PURCHASED_PART darf kein price_basis setzen")
        forbidden = [
            ("part_calculation_id", position.part_calculation_id),
            ("child_assembly_id", position.child_assembly_id),
            ("finishing_step_id", position.finishing_step_id),
        ]
        for name, value in forbidden:
            if value is not None:
                raise AssemblyStructureError(f"{prefix}: PURCHASED_PART darf {name} nicht setzen")
    elif position.position_type == "SUBASSEMBLY":
        if not position.child_assembly_id:
            raise AssemblyStructureError(f"{prefix}: SUBASSEMBLY benötigt child_assembly_id")
        if position.price_basis is None:
            raise AssemblyStructureError(f"{prefix}: SUBASSEMBLY benötigt price_basis")
        forbidden = [
            ("part_calculation_id", position.part_calculation_id),
            ("purchased_part_id", position.purchased_part_id),
            ("finishing_step_id", position.finishing_step_id),
        ]
        for name, value in forbidden:
            if value is not None:
                raise AssemblyStructureError(f"{prefix}: SUBASSEMBLY darf {name} nicht setzen")
    elif position.position_type == "PROCESS":
        if not position.finishing_step_id:
            raise AssemblyStructureError(f"{prefix}: PROCESS benötigt finishing_step_id")
        if position.price_basis is not None:
            raise AssemblyStructureError(f"{prefix}: PROCESS darf kein price_basis setzen")
        forbidden = [
            ("part_calculation_id", position.part_calculation_id),
            ("purchased_part_id", position.purchased_part_id),
            ("child_assembly_id", position.child_assembly_id),
        ]
        for name, value in forbidden:
            if value is not None:
                raise AssemblyStructureError(f"{prefix}: PROCESS darf {name} nicht setzen")


def validate_sequences(positions: list[AssemblyPositionInput]) -> None:
    seen: set[int] = set()
    for position in positions:
        if position.sequence in seen:
            raise AssemblyStructureError(
                f"Doppelte sequence {position.sequence} innerhalb der Baugruppe"
            )
        seen.add(position.sequence)


def validate_referenced_entities_exist(db: Session, positions: list[AssemblyPositionInput]) -> None:
    for index, position in enumerate(positions, start=1):
        prefix = f"Position #{index}"
        if position.part_calculation_id is not None:
            if not db.get(SpritzgussKalkulation, position.part_calculation_id):
                raise AssemblyStructureError(
                    f"{prefix}: Spritzguss-Kalkulation {position.part_calculation_id} nicht gefunden",
                    status_code=404,
                )
        if position.purchased_part_id is not None:
            kt = db.get(Kaufteil, position.purchased_part_id)
            if not kt:
                raise AssemblyStructureError(
                    f"{prefix}: Kaufteil {position.purchased_part_id} nicht gefunden",
                    status_code=404,
                )
        if position.finishing_step_id is not None:
            if not db.get(Veredelungsschritt, position.finishing_step_id):
                raise AssemblyStructureError(
                    f"{prefix}: Veredelungsschritt {position.finishing_step_id} nicht gefunden",
                    status_code=404,
                )


def validate_project_scope(
    db: Session, baugruppe: Baugruppe, positions: list[AssemblyPositionInput]
) -> None:
    project_id = effective_project_id(baugruppe)
    if project_id is None:
        raise AssemblyStructureError("Projekt-Zuordnung fehlt")

    for index, position in enumerate(positions, start=1):
        prefix = f"Position #{index}"
        if position.part_calculation_id is not None:
            kalk = db.get(SpritzgussKalkulation, position.part_calculation_id)
            if kalk and kalk.project_id is not None and kalk.project_id != project_id:
                raise AssemblyStructureError(
                    f"{prefix}: Spritzguss-Kalkulation gehört nicht zum Projekt der Baugruppe"
                )
        if position.child_assembly_id is not None:
            child = db.get(Baugruppe, position.child_assembly_id)
            if child:
                child_project = effective_project_id(child)
                if child_project is not None and child_project != project_id:
                    raise AssemblyStructureError(
                        f"{prefix}: Unterbaugruppe gehört nicht zum Projekt der Baugruppe"
                    )


def validate_subassembly_rules(
    db: Session,
    baugruppe: Baugruppe,
    positions: list[AssemblyPositionInput],
) -> None:
    for index, position in enumerate(positions, start=1):
        if position.position_type != "SUBASSEMBLY" or not position.child_assembly_id:
            continue
        prefix = f"Position #{index}"
        if position.child_assembly_id == baugruppe.id:
            raise AssemblyStructureError(f"{prefix}: Baugruppe darf nicht auf sich selbst verweisen")
        child = db.get(Baugruppe, position.child_assembly_id)
        if not child:
            raise AssemblyStructureError(
                f"{prefix}: Unterbaugruppe {position.child_assembly_id} nicht gefunden",
                status_code=404,
            )
        if child.assembly_type != "SUBASSEMBLY":
            raise AssemblyStructureError(
                f"{prefix}: Nur SUBASSEMBLY darf als Unterbaugruppe verwendet werden"
            )


def _load_subassembly_children(db: Session, assembly_id: int) -> list[int]:
    return [
        child_id
        for child_id in db.scalars(
            select(AssemblyPosition.child_assembly_id).where(
                AssemblyPosition.parent_assembly_id == assembly_id,
                AssemblyPosition.position_type == "SUBASSEMBLY",
                AssemblyPosition.child_assembly_id.is_not(None),
            )
        ).all()
        if child_id is not None
    ]


def detect_cycle(
    db: Session,
    root_id: int,
    positions: list[AssemblyPositionInput],
) -> None:
    child_ids = [
        p.child_assembly_id
        for p in positions
        if p.position_type == "SUBASSEMBLY" and p.child_assembly_id is not None
    ]
    for child_id in child_ids:
        if child_id == root_id:
            raise AssemblyStructureError("Zyklus in der Baugruppenstruktur: Selbstreferenz")
        visited: set[int] = {child_id}
        queue: deque[int] = deque([child_id])
        while queue:
            current = queue.popleft()
            for next_child in _load_subassembly_children(db, current):
                if next_child == root_id:
                    raise AssemblyStructureError(
                        "Zyklus in der Baugruppenstruktur über mehrere Ebenen"
                    )
                if next_child not in visited:
                    visited.add(next_child)
                    queue.append(next_child)


def _parse_ergebnis(raw: Any) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _endpreis_aus_spritzguss(kalk: SpritzgussKalkulation) -> float | None:
    ergebnis = _parse_ergebnis(kalk.ergebnis)
    if ergebnis:
        preis = ergebnis.get("endpreis_je_stueck")
        if preis is None:
            preis = ergebnis.get("verkaufspreis")
        if preis is not None:
            return float(preis)
    return None


def capture_snapshots_if_possible(db: Session, position: AssemblyPositionInput) -> dict[str, Any]:
    now = datetime.now(UTC)
    result: dict[str, Any] = {
        "name_snapshot": "",
        "part_number_snapshot": "",
        "supplier_snapshot": "",
        "cost_snapshot": None,
        "price_snapshot": None,
        "snapshots_captured_at": now,
    }

    if position.position_type == "PART" and position.part_calculation_id:
        kalk = db.get(SpritzgussKalkulation, position.part_calculation_id)
        if kalk:
            result["name_snapshot"] = kalk.teilebezeichnung
            result["part_number_snapshot"] = kalk.teilenummer
            result["price_snapshot"] = _endpreis_aus_spritzguss(kalk)
    elif position.position_type == "PURCHASED_PART" and position.purchased_part_id:
        kt = db.get(Kaufteil, position.purchased_part_id)
        if kt:
            result["name_snapshot"] = kt.bezeichnung
            result["supplier_snapshot"] = kt.lieferant
            result["price_snapshot"] = kt.preis
    elif position.position_type == "PROCESS" and position.finishing_step_id:
        schritt = db.get(Veredelungsschritt, position.finishing_step_id)
        if schritt:
            result["name_snapshot"] = schritt.bezeichnung
    elif position.position_type == "SUBASSEMBLY" and position.child_assembly_id:
        child = db.get(Baugruppe, position.child_assembly_id)
        if child:
            result["name_snapshot"] = child.name
            result["part_number_snapshot"] = child.teilenummer

    return result


def _input_to_orm(
    db: Session,
    parent_id: int,
    position: AssemblyPositionInput,
) -> AssemblyPosition:
    snapshots = capture_snapshots_if_possible(db, position)
    return AssemblyPosition(
        parent_assembly_id=parent_id,
        position_type=position.position_type,
        sequence=position.sequence,
        quantity=position.quantity,
        quantity_factor=position.quantity_factor,
        price_basis=position.price_basis,
        active=position.active,
        label=position.label,
        part_calculation_id=position.part_calculation_id,
        purchased_part_id=position.purchased_part_id,
        child_assembly_id=position.child_assembly_id,
        finishing_step_id=position.finishing_step_id,
        **snapshots,
    )


def _apply_header_updates(
    baugruppe: Baugruppe,
    *,
    project_id: int | None,
    assembly_type: str | None,
) -> None:
    if project_id is not None:
        baugruppe.project_id = project_id
    if assembly_type is not None:
        baugruppe.assembly_type = assembly_type


def _validate_all(
    db: Session,
    baugruppe: Baugruppe,
    positions: list[AssemblyPositionInput],
) -> None:
    validate_sequences(positions)
    for index, position in enumerate(positions, start=1):
        validate_position_refs(position, index)
    validate_referenced_entities_exist(db, positions)
    validate_project_scope(db, baugruppe, positions)
    validate_subassembly_rules(db, baugruppe, positions)
    detect_cycle(db, baugruppe.id, positions)


def _handle_integrity_error(exc: IntegrityError) -> AssemblyStructureError:
    message = str(exc.orig).lower() if exc.orig else str(exc).lower()
    if "uq_ap_parent_sequence" in message or "sequence" in message:
        return AssemblyStructureError("Doppelte sequence innerhalb der Baugruppe", status_code=409)
    if "uq_ap_parent_part" in message or "part_calculation_id" in message:
        return AssemblyStructureError(
            "Einzelteil ist in dieser Baugruppe bereits als PART vorhanden",
            status_code=409,
        )
    return AssemblyStructureError("Struktur konnte nicht gespeichert werden", status_code=409)


def replace_structure(
    db: Session,
    baugruppe_id: int,
    request: AssemblyStructureReplaceRequest,
) -> AssemblyStructureRead:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    if request.structure_version != baugruppe.structure_version:
        raise AssemblyStructureError(
            f"Veraltete structure_version (erwartet {baugruppe.structure_version})",
            status_code=409,
        )

    _apply_header_updates(
        baugruppe,
        project_id=request.project_id,
        assembly_type=request.assembly_type,
    )
    _validate_all(db, baugruppe, request.positions)

    try:
        db.execute(
            delete(AssemblyPosition).where(AssemblyPosition.parent_assembly_id == baugruppe_id)
        )
        for position in request.positions:
            db.add(_input_to_orm(db, baugruppe_id, position))
        baugruppe.structure_version += 1
        baugruppe.legacy_mode = False
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _handle_integrity_error(exc) from exc

    db.refresh(baugruppe)
    return get_structure(db, baugruppe_id)


def add_position(
    db: Session,
    baugruppe_id: int,
    payload: AssemblyPositionCreateRequest,
) -> AssemblyPositionRead:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    if effective_project_id(baugruppe) is None:
        raise AssemblyStructureError("Projekt-Zuordnung fehlt")

    _validate_all(db, baugruppe, [payload])

    try:
        pos = _input_to_orm(db, baugruppe_id, payload)
        db.add(pos)
        baugruppe.structure_version += 1
        baugruppe.legacy_mode = False
        db.commit()
        db.refresh(pos)
    except IntegrityError as exc:
        db.rollback()
        raise _handle_integrity_error(exc) from exc

    child_preview = None
    if pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id:
        child_preview = build_child_preview(db, pos.child_assembly_id, depth=0)
    return _position_to_read(pos, child_assembly=child_preview)


def patch_position(
    db: Session,
    baugruppe_id: int,
    position_id: int,
    payload: AssemblyPositionPatchRequest,
) -> AssemblyPositionRead:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    pos = db.get(AssemblyPosition, position_id)
    if not pos or pos.parent_assembly_id != baugruppe_id:
        raise AssemblyStructureError("Position nicht gefunden", status_code=404)

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return _position_to_read(pos)

    if "sequence" in updates and updates["sequence"] != pos.sequence:
        conflict = db.scalar(
            select(AssemblyPosition.id).where(
                AssemblyPosition.parent_assembly_id == baugruppe_id,
                AssemblyPosition.sequence == updates["sequence"],
                AssemblyPosition.id != position_id,
            )
        )
        if conflict:
            raise AssemblyStructureError(
                f"Doppelte sequence {updates['sequence']} innerhalb der Baugruppe"
            )

    for field, value in updates.items():
        setattr(pos, field, value)

    try:
        baugruppe.structure_version += 1
        db.commit()
        db.refresh(pos)
    except IntegrityError as exc:
        db.rollback()
        raise _handle_integrity_error(exc) from exc

    child_preview = None
    if pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id:
        child_preview = build_child_preview(db, pos.child_assembly_id, depth=0)
    return _position_to_read(pos, child_assembly=child_preview)


def delete_position(db: Session, baugruppe_id: int, position_id: int) -> None:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    pos = db.get(AssemblyPosition, position_id)
    if not pos or pos.parent_assembly_id != baugruppe_id:
        raise AssemblyStructureError("Position nicht gefunden", status_code=404)

    db.delete(pos)
    baugruppe.structure_version += 1
    db.commit()
