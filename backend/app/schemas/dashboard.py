from datetime import date, datetime

from pydantic import BaseModel, Field


class DashboardKpis(BaseModel):
    anzahl_projekte: int = 0
    anzahl_spritzguss_kalkulationen: int = 0
    anzahl_baugruppen: int = 0
    durchschnitt_endpreis_einzelteil: float | None = None
    durchschnitt_baugruppenpreis: float | None = None
    durchschnitt_preis_pro_stueck: float | None = None
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


class ChartBarItem(BaseModel):
    label: str
    value: float
    typ: str = ""


class AssemblyRow(BaseModel):
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    preis_je_stueck: float | None = None
    jahresstueckzahl: int = 0
    jahresumsatz: float = 0
    status: str = ""
    letzte_kalkulation: datetime | None = None
    cost_structure: list[ChartBarItem] = Field(default_factory=list)


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
    lieferant: str = ""
    bestelldatum: date | None = None
    liefertermin: date | None = None
    amortisationsvolumen: int | None = None
    kostenanteil_pro_teil: float | None = None
    created_at: datetime | None = None


class ProjectAmountItem(BaseModel):
    projekt: str
    betrag: float


class DashboardFilterOptions(BaseModel):
    projekte: list[str] = Field(default_factory=list)
    kunden: list[str] = Field(default_factory=list)
    statusse: list[str] = Field(default_factory=list)
    kalkulationsarten: list[str] = Field(default_factory=list)


class DashboardSummary(BaseModel):
    kpis: DashboardKpis
    recent_calculations: list[RecentCalculationRow] = Field(default_factory=list)
    recent_investments: list[InvestmentRow] = Field(default_factory=list)
    assemblies: list[AssemblyRow] = Field(default_factory=list)
    investments: list[InvestmentRow] = Field(default_factory=list)
    price_comparison: list[ChartBarItem] = Field(default_factory=list)
    cost_structure: list[ChartBarItem] = Field(default_factory=list)
    investment_by_project: list[ProjectAmountItem] = Field(default_factory=list)
    revenue_by_project: list[ProjectAmountItem] = Field(default_factory=list)
    filter_options: DashboardFilterOptions = Field(default_factory=DashboardFilterOptions)
    has_data: bool = True
    empty_message: str | None = None


class AssemblyBomRow(BaseModel):
    position_type: str
    bezeichnung: str
    teilenummer: str = ""
    menge: float = 0
    mengenfaktor: float = 1
    einzelpreis: float | None = None
    zwischensumme: float | None = None


class AssemblyMarkupRow(BaseModel):
    typ: str
    bezeichnung: str
    betrag: float | None = None
    satz_prozent: float | None = None


class AssemblyInvestmentBrief(BaseModel):
    id: int
    bezeichnung: str
    typ: str
    betrag: float
    status: str


class AssemblyOverview(BaseModel):
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    status: str
    structure_version: int = 1
    assembly_type: str = "TOP_LEVEL"
    jahresstueckzahl: int = 0
    letzte_kalkulation: datetime | None = None
    bom: list[AssemblyBomRow] = Field(default_factory=list)
    einzelteilkosten: float = 0
    kaufteilkosten: float = 0
    veredelungskosten: float = 0
    investitionskosten: float = 0
    vvgk: float | None = None
    gewinn: float | None = None
    skonto: float | None = None
    nettoverkaufspreis: float | None = None
    bruttoverkaufspreis: float | None = None
    preis_je_stueck: float | None = None
    herstellkosten: float | None = None
    jahresumsatz: float = 0
    gesamtsumme: float | None = None
    zuschlagssaetze: list[AssemblyMarkupRow] = Field(default_factory=list)
    cost_structure: list[ChartBarItem] = Field(default_factory=list)
    investitionen: list[AssemblyInvestmentBrief] = Field(default_factory=list)
    has_result: bool = False
    generated_at: datetime | None = None
