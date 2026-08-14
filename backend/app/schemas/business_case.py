from pydantic import BaseModel, Field


class LifetimeYearRow(BaseModel):
    calendar_year: int
    vehicle_volume: int = 0
    quantity_per_vehicle: float = 0
    project_volume: float = 0
    teilepreis_je_stueck: float | None = None
    baugruppenpreis_je_stueck: float | None = None
    jahresumsatz: float = 0


class BusinessCasePartRow(BaseModel):
    id: int
    bezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    gesamtstueckzahl_laufzeit: float = 0
    endpreis_je_stueck: float | None = None
    jahresumsatz: float = 0
    umsatzpotenzial_laufzeit: float = 0
    lifetime_years: list[LifetimeYearRow] = Field(default_factory=list)
    anzahl_veredelungsschritte: int = 0


class BusinessCaseAssemblyRow(BaseModel):
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    gesamtstueckzahl_laufzeit: float = 0
    baugruppenpreis_je_stueck: float | None = None
    jahresumsatz: float = 0
    umsatzpotenzial_laufzeit: float = 0
    lifetime_years: list[LifetimeYearRow] = Field(default_factory=list)
    anzahl_einzelteile: int = 0
    anzahl_kaufteile: int = 0
    anzahl_veredelungsschritte: int = 0


class BusinessCaseInvestmentRow(BaseModel):
    id: int
    bezeichnung: str
    investment_type: str
    payment_type: str
    amount: float
    amortization_volume: int | None = None
    cost_per_piece: float | None = None
    zuordnung: str = ""
    hinweis: str = ""
    bemerkung: str = ""


class BusinessCaseKpis(BaseModel):
    kunde: str
    projekt: str
    jahresstueckzahl_gesamt: int = 0
    gesamtstueckzahl_laufzeit: float = 0
    umsatzpotenzial_laufzeit: float = 0
    umsatzpotenzial_einzelteile: float = 0
    umsatzpotenzial_baugruppen: float = 0
    anzahl_einzelteile: int = 0
    anzahl_baugruppen: int = 0
    anzahl_investitionen: int = 0
    investitionen_gesamt: float = 0
    amortisationsinvestitionen_gesamt: float = 0
    einmalinvestitionen_gesamt: float = 0
    amortisationsanteil_je_stueck: float | None = None
    teilepreis_je_stueck: float | None = None
    baugruppenpreis_je_stueck: float | None = None


class BusinessCaseResponse(BaseModel):
    project: str
    customer: str
    kpis: BusinessCaseKpis
    parts: list[BusinessCasePartRow] = Field(default_factory=list)
    assemblies: list[BusinessCaseAssemblyRow] = Field(default_factory=list)
    investments: list[BusinessCaseInvestmentRow] = Field(default_factory=list)
    investment_summary: dict = Field(default_factory=dict)
    revenue_summary: dict = Field(default_factory=dict)
    lifetime_volume_profile: list[LifetimeYearRow] = Field(default_factory=list)
