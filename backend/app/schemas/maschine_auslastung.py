"""Schemas für Maschinenauslastung."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MaschineAuslastungProjectContribution(BaseModel):
    project_id: int
    project_name: str
    source_type: str
    source_label: str
    jahresstueckzahl: float
    required_hours: float


class MaschineAuslastungYearRow(BaseModel):
    calendar_year: int
    required_hours: float
    available_hours: float | None
    utilization_pct: float | None


class MaschineAuslastungRow(BaseModel):
    maschine_id: int
    maschinen_nr: str
    bezeichnung: str
    werk_id: int | None
    werk_name: str | None
    available_hours: float | None
    required_hours: float
    utilization_pct: float | None
    rest_capacity_hours: float | None
    overload_hours: float | None
    is_overloaded: bool
    has_demand: bool
    projects: list[MaschineAuslastungProjectContribution] = Field(default_factory=list)
    yearly_breakdown: list[MaschineAuslastungYearRow] = Field(default_factory=list)


class MaschineAuslastungPlanningPeriod(BaseModel):
    label: str
    basis: str
    available_hours_per_machine_year: float | None


class MaschineAuslastungSummary(BaseModel):
    machine_count: int
    machines_with_demand: int
    overloaded_count: int
    average_utilization_pct: float | None
    plant_utilization_pct: float | None
    max_utilization_pct: float | None
    max_utilization_maschine_id: int | None
    max_utilization_maschine_name: str | None


class MaschineAuslastungResponse(BaseModel):
    plant_id: int
    plant_name: str
    customer_id: int | None
    program_id: int | None
    project_ids: list[int]
    no_projects_selected: bool
    planning_period: MaschineAuslastungPlanningPeriod
    summary: MaschineAuslastungSummary
    machines: list[MaschineAuslastungRow]
