"""Pydantic-Schemas für die Baugruppen-Struktur-API (Phase B)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.assembly_calculation import AssemblyCalculationResultRead, CalculationWarning

PositionType = Literal["PART", "PURCHASED_PART", "SUBASSEMBLY", "PROCESS"]
PriceBasis = Literal["COST", "SELF_COST", "SALES_PRICE"]
AssemblyType = Literal["TOP_LEVEL", "SUBASSEMBLY"]
PositionsSource = Literal["assembly_positions", "legacy_synthetic", "empty"]
LegacySource = Literal["spritzguss", "kaufteil", "veredelung"]


class PositionSnapshotRead(BaseModel):
    cost_snapshot: float | None = None
    price_snapshot: float | None = None
    name_snapshot: str = ""
    part_number_snapshot: str = ""
    supplier_snapshot: str = ""
    snapshots_captured_at: datetime | None = None


class ChildAssemblyPreview(BaseModel):
    id: int
    name: str
    teilenummer: str
    assembly_type: AssemblyType
    structure_version: int
    legacy_mode: bool
    positions: list[AssemblyPositionRead] = Field(default_factory=list)
    positions_source: PositionsSource


class AssemblyPositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    position_type: PositionType
    sequence: int
    quantity: float
    quantity_factor: float
    price_basis: PriceBasis | None = None
    active: bool = True
    label: str | None = None
    part_calculation_id: int | None = None
    purchased_part_id: int | None = None
    child_assembly_id: int | None = None
    finishing_step_id: int | None = None
    snapshots: PositionSnapshotRead
    legacy_source: LegacySource | None = None
    child_assembly: ChildAssemblyPreview | None = None
    snapshot_stale: bool = False


class AssemblyStructureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    beschreibung: str
    status: str
    aktiv: bool
    project_id: int | None = None
    linked_project_id: int | None = None
    assembly_type: AssemblyType
    structure_version: int
    legacy_mode: bool
    pricing_status: str
    positions_source: PositionsSource
    positions: list[AssemblyPositionRead] = Field(default_factory=list)
    calculation: AssemblyCalculationResultRead | None = None
    warnings: list[CalculationWarning] = Field(default_factory=list)
    snapshot_stale: bool = False
    effective_pricing_status: str | None = None


class AssemblyPositionInput(BaseModel):
    position_type: PositionType
    sequence: int = Field(ge=1)
    quantity: float = Field(gt=0, default=1.0)
    quantity_factor: float = Field(gt=0, default=1.0)
    price_basis: PriceBasis | None = None
    active: bool = True
    label: str | None = None
    part_calculation_id: int | None = None
    purchased_part_id: int | None = None
    child_assembly_id: int | None = None
    finishing_step_id: int | None = None


class AssemblyStructureReplaceRequest(BaseModel):
    structure_version: int = Field(ge=1)
    project_id: int | None = None
    assembly_type: AssemblyType | None = None
    positions: list[AssemblyPositionInput] = Field(default_factory=list)
    recalculate: bool = False


class AssemblyPositionCreateRequest(AssemblyPositionInput):
    pass


class AssemblyPositionPatchRequest(BaseModel):
    sequence: int | None = Field(default=None, ge=1)
    quantity: float | None = Field(default=None, gt=0)
    quantity_factor: float | None = Field(default=None, gt=0)
    price_basis: PriceBasis | None = None
    active: bool | None = None
    label: str | None = None


# Forward references auflösen
ChildAssemblyPreview.model_rebuild()
AssemblyPositionRead.model_rebuild()
