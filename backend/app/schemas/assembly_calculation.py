"""Schemas für Baugruppen-Kalkulation (Phase C)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CalculationWarning(BaseModel):
    code: str
    message: str
    position_id: int | None = None
    assembly_id: int | None = None


class PositionCalculationLineRead(BaseModel):
    position_id: int | None = None
    position_type: str
    sequence: int
    label: str | None = None
    name_snapshot: str = ""
    einzelpreis: float
    quantity: float
    quantity_factor: float
    zwischensumme: float


class AssemblyCalculationResultRead(BaseModel):
    herstellkosten: float
    vvgk: float | None = None
    selbstkosten: float | None = None
    gewinn: float | None = None
    nettoverkaufspreis: float | None = None
    skonto: float | None = None
    endpreis_je_stueck: float | None = None
    markup_applied: bool = False


class AssemblyRecalculateRequest(BaseModel):
    refresh_snapshots: bool = True
    include_descendants: bool = True
    validate_only: bool = False


class AssemblyRecalculateResponse(BaseModel):
    assembly_id: int
    assembly_type: str
    structure_version: int
    pricing_status: str
    snapshots_captured_at: datetime | None = None
    calculation: AssemblyCalculationResultRead
    positions: list[PositionCalculationLineRead] = Field(default_factory=list)
    warnings: list[CalculationWarning] = Field(default_factory=list)
    recalculated_assembly_ids: list[int] = Field(default_factory=list)
