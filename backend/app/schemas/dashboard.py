from datetime import datetime

from pydantic import BaseModel, Field


class DashboardKpis(BaseModel):
    anzahl_projekte: int = 0
    anzahl_spritzguss_kalkulationen: int = 0
    anzahl_baugruppen: int = 0
    durchschnitt_endpreis_einzelteil: float | None = None
    durchschnitt_baugruppenpreis: float | None = None
    investitionen_gesamt: float = 0
    jahresstueckzahl: int = 0
    umsatzpotenzial_jahr: float = 0


class RecentCalculationRow(BaseModel):
    id: int
    kalkulationsart: str
    bezeichnung: str
    nummer: str
    kunde: str
    projekt: str
    endpreis_je_stueck: float | None = None
    created_at: datetime
    updated_at: datetime


class AssemblyRow(BaseModel):
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    preis_je_stueck: float | None = None
    jahresstueckzahl: int = 0
    jahresumsatz: float = 0


class InvestmentRow(BaseModel):
    id: int
    bezeichnung: str
    typ: str
    betrag: float
    projekt: str
    kunde: str = ""
    status: str
    im_stueckpreis: bool = False
    hinweis: str = ""


class ChartBarItem(BaseModel):
    label: str
    value: float
    typ: str = ""


class ProjectAmountItem(BaseModel):
    projekt: str
    betrag: float


class DashboardFilterOptions(BaseModel):
    projekte: list[str] = Field(default_factory=list)
    kunden: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    kpis: DashboardKpis
    recent_calculations: list[RecentCalculationRow] = Field(default_factory=list)
    assemblies: list[AssemblyRow] = Field(default_factory=list)
    investments: list[InvestmentRow] = Field(default_factory=list)
    price_comparison: list[ChartBarItem] = Field(default_factory=list)
    investment_by_project: list[ProjectAmountItem] = Field(default_factory=list)
    revenue_by_project: list[ProjectAmountItem] = Field(default_factory=list)
    filter_options: DashboardFilterOptions = Field(default_factory=DashboardFilterOptions)
