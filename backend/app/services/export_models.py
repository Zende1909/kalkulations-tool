"""Datenmodelle für PDF- und Excel-Exporte."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExportRow:
    label: str
    value: str


@dataclass
class ExportMoneyRow:
    label: str
    amount: float | None
    highlight: bool = False


@dataclass
class ExportTable:
    title: str
    headers: list[str]
    rows: list[list[str]]


@dataclass
class ExportInvestment:
    bezeichnung: str
    typ: str
    betrag: float
    status: str
    hinweis: str


@dataclass
class SpritzgussExportData:
    company_name: str
    calculation_id: int
    teilebezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    created_at: datetime
    updated_at: datetime
    inputs: list[ExportRow]
    kosten: list[ExportMoneyRow]
    veredelung_steps: list[ExportMoneyRow]
    investitionen: list[ExportInvestment]
    werkzeug_hinweis: str | None = None
    endpreis: float | None = None
    has_data: bool = True


@dataclass
class BaugruppeExportData:
    company_name: str
    assembly_id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    created_at: datetime
    updated_at: datetime
    einzelteile: ExportTable
    kaufteile: ExportTable
    veredelung: ExportTable
    investitionen: list[ExportInvestment]
    einzelteile_gesamt: float
    kaufteile_gesamt: float
    veredelung_gesamt: float
    baugruppenpreis_je_stueck: float | None
    jahresumsatz: float
    has_data: bool = True
    export_date: datetime | None = None
    structure_version: int = 1
    status: str = ""
    bom: ExportTable | None = None
    zuschlagssaetze: ExportTable | None = None
    kosten_aufstellung: list[ExportMoneyRow] = field(default_factory=list)
    herstellkosten: float | None = None
    vvgk: float | None = None
    gewinn: float | None = None
    skonto: float | None = None
    nettoverkaufspreis: float | None = None
    gesamtergebnis: float | None = None


@dataclass
class DashboardExportData:
    company_name: str
    filter_project: str | None
    filter_customer: str | None
    generated_at: datetime
    kpis: list[ExportRow]
    recent_calculations: ExportTable
    assemblies: ExportTable
    investments: ExportTable
    price_comparison: ExportTable
    investment_by_project: ExportTable
    revenue_by_project: ExportTable
    price_chart: list[tuple[str, float]] = field(default_factory=list)
    investment_chart: list[tuple[str, float]] = field(default_factory=list)
    revenue_chart: list[tuple[str, float]] = field(default_factory=list)
    has_data: bool = True
    empty_message: str | None = None
    filter_status: str | None = None
    filter_date_from: str | None = None
    filter_date_to: str | None = None
    filter_kalkulationsart: str | None = None
