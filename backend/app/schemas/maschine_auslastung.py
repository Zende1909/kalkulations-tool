"""Schemas für Maschinenauslastung."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MaschineAuslastungProjectContribution(BaseModel):
    project_id: int
    project_name: str
    source_type: str
    source_label: str
    jahresstueckzahl: float
    run_hours: float = 0
    setup_hours: float = 0
    required_hours: float


class MaschineAuslastungYearRow(BaseModel):
    year: int
    calendar_year: int
    machine_id: int
    maschine_id: int
    machine_name: str
    maschinen_nr: str
    gross_hours: float | None
    oee: float | None
    oee_in_available_hours: bool = True
    available_hours: float | None
    run_hours: float
    setup_hours: float
    required_hours: float
    utilization_pct: float | None
    utilization_percent: float | None
    remaining_hours: float | None
    rest_capacity_hours: float | None
    overload_hours: float | None
    is_overloaded: bool
    overloaded: bool
    has_demand: bool
    project_ids: list[int] = Field(default_factory=list)
    projects: list[MaschineAuslastungProjectContribution] = Field(default_factory=list)


class MaschineAuslastungRow(BaseModel):
    maschine_id: int
    maschinen_nr: str
    bezeichnung: str
    werk_id: int | None
    werk_name: str | None
    gross_hours: float | None = None
    oee: float | None = None
    oee_in_available_hours: bool = True
    available_hours: float | None
    run_hours: float = 0
    setup_hours: float = 0
    required_hours: float
    utilization_pct: float | None
    rest_capacity_hours: float | None
    overload_hours: float | None
    is_overloaded: bool
    has_demand: bool
    years_with_demand: int = 0
    yearly_breakdown: list[MaschineAuslastungYearRow] = Field(default_factory=list)
    projects: list[MaschineAuslastungProjectContribution] = Field(default_factory=list)


class MaschineAuslastungPlanningPeriod(BaseModel):
    label: str
    basis: str
    available_hours_per_machine_year: float | None
    oee_in_available_hours: bool = True


class MaschineAuslastungSummary(BaseModel):
    machine_count: int
    machines_with_demand: int
    overloaded_count: int
    average_utilization_pct: float | None
    plant_utilization_pct: float | None
    max_utilization_pct: float | None
    max_utilization_maschine_id: int | None
    max_utilization_maschine_name: str | None
    max_utilization_year: int | None = None


class MaschineAuslastungResponse(BaseModel):
    plant_id: int
    plant_name: str
    customer_id: int | None
    program_id: int | None
    project_ids: list[int]
    no_projects_selected: bool
    years: list[int]
    planning_period: MaschineAuslastungPlanningPeriod
    summary: MaschineAuslastungSummary
    yearly_rows: list[MaschineAuslastungYearRow] = Field(default_factory=list)
    machines: list[MaschineAuslastungRow]
