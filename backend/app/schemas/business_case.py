from pydantic import BaseModel, Field


class BusinessCasePartRow(BaseModel):
    id: int
    bezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    endpreis_je_stueck: float | None = None
    jahresumsatz: float = 0
    anzahl_veredelungsschritte: int = 0


class BusinessCaseAssemblyRow(BaseModel):
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    baugruppenpreis_je_stueck: float | None = None
    jahresumsatz: float = 0
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
