from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.numbers import parse_de_float


class PositionPricingFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cost_per_piece: float | None = None
    has_cost_per_piece: bool = False
    bottom_price_per_piece: float | None = None
    actual_price_per_piece: float | None = None
    guide_price_per_piece: float | None = None
    project_volume: float = 0
    bottom_price_revenue: float | None = None
    actual_revenue: float | None = None
    cost_total: float | None = None
    margin_bottom_price_per_piece: float | None = None
    margin_actual_price_per_piece: float | None = None
    margin_bottom_price_total: float | None = None
    margin_actual_total: float | None = None
    margin_bottom_price_pct: float | None = None
    margin_actual_price_pct: float | None = None
    margin_bottom_price_total_pct: float | None = None
    margin_actual_total_pct: float | None = None
    price_warnings: list[str] = Field(default_factory=list)
    has_manual_bottom_price: bool = False
    has_manual_actual_price: bool = False


class BusinessCasePartRow(PositionPricingFields):
    id: int
    assignment_type: str = "einzelteil"
    bezeichnung: str
    teilenummer: str
    material_number: str = ""
    kunde: str = ""
    program: str = ""
    projekt: str = ""
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    jahresstueckzahl: int = 0
    gesamtstueckzahl_laufzeit: float = 0
    endpreis_je_stueck: float | None = None
    anzahl_veredelungsschritte: int = 0


class BusinessCaseAssemblyRow(PositionPricingFields):
    id: int
    assignment_type: str = "baugruppe"
    name: str
    teilenummer: str
    material_number: str = ""
    kunde: str = ""
    program: str = ""
    projekt: str = ""
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    jahresstueckzahl: int = 0
    gesamtstueckzahl_laufzeit: float = 0
    baugruppenpreis_je_stueck: float | None = None
    jahresumsatz: float = 0
    umsatzpotenzial_laufzeit: float | None = None
    anzahl_einzelteile: int = 0
    anzahl_kaufteile: int = 0
    anzahl_veredelungsschritte: int = 0


class BusinessCaseInvestmentRow(BaseModel):
    id: int
    bezeichnung: str
    investment_type: str
    payment_type: str
    amount: float
    cost_amount: float = 0
    bottom_price: float | None = None
    revenue_amount: float | None = None
    margin_revenue_minus_cost: float | None = None
    margin_revenue_minus_bottom_price: float | None = None
    margin_bottom_price_minus_cost: float | None = None
    margin_revenue_minus_cost_pct: float | None = None
    margin_revenue_minus_bottom_price_pct: float | None = None
    amount_warnings: list[str] = Field(default_factory=list)
    assignment_type: str | None = None
    assignment_type_label: str = ""
    material_number: str = ""
    part_number: str = ""
    customer_name: str = ""
    program_name: str = ""
    project_name: str = ""
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    amortization_volume: int | None = None
    cost_per_piece: float | None = None
    zuordnung: str = ""
    hinweis: str = ""
    bemerkung: str = ""


class BusinessCaseKpis(BaseModel):
    kunde: str
    programm: str = ""
    projekt: str
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    project_volume_total: float = 0
    cost_total: float | None = None
    bottom_price_revenue_total: float | None = None
    actual_revenue_total: float | None = None
    margin_bottom_price_total: float | None = None
    margin_actual_total: float | None = None
    margin_bottom_price_total_pct: float | None = None
    margin_actual_total_pct: float | None = None
    anzahl_einzelteile: int = 0
    anzahl_baugruppen: int = 0
    anzahl_einzelteile_in_baugruppen_ausgeschlossen: int = 0
    anzahl_investitionen: int = 0
    investitionen_gesamt: float = 0
    amortisationsinvestitionen_gesamt: float = 0
    einmalinvestitionen_gesamt: float = 0
    capex_investitionen_gesamt: float = 0
    entwicklungsinvestitionen_gesamt: float = 0
    amortisationsanteil_je_stueck: float | None = None
    investition_cost_total: float = 0
    investition_bottom_price_total: float = 0
    investition_revenue_total: float = 0
    margin_revenue_minus_cost_total: float | None = None
    margin_revenue_minus_bottom_price_total: float | None = None
    margin_bottom_price_minus_cost_total: float | None = None


class BusinessCaseFilter(BaseModel):
    customer_id: int
    program_id: int
    linked_project_id: int
    customer: str = ""
    program: str = ""
    project: str = ""


class BusinessCaseResponse(BaseModel):
    filter: BusinessCaseFilter
    project: str
    customer: str
    program: str = ""
    customer_id: int
    program_id: int
    linked_project_id: int
    kpis: BusinessCaseKpis
    parts: list[BusinessCasePartRow] = Field(default_factory=list)
    assemblies: list[BusinessCaseAssemblyRow] = Field(default_factory=list)
    investments: list[BusinessCaseInvestmentRow] = Field(default_factory=list)
    investments_capex: list[BusinessCaseInvestmentRow] = Field(default_factory=list)
    investments_entwicklung: list[BusinessCaseInvestmentRow] = Field(default_factory=list)
    investments_other: list[BusinessCaseInvestmentRow] = Field(default_factory=list)
    sales_summary: dict = Field(default_factory=dict)
    investment_summary: dict = Field(default_factory=dict)
    investment_financial_summary: dict = Field(default_factory=dict)
    revenue_summary: dict = Field(default_factory=dict)


class ManualPriceUpsert(BaseModel):
    customer_id: int
    program_id: int
    linked_project_id: int
    assignment_type: str
    object_id: int
    bottom_price_per_piece: float | None = None
    actual_price_per_piece: float | None = None

    @field_validator("bottom_price_per_piece", "actual_price_per_piece", mode="before")
    @classmethod
    def coerce_prices(cls, value):
        if value is None or value == "":
            return None
        parsed = parse_de_float(value, field_label="Preis", allow_none=True)
        if parsed is not None and parsed < 0:
            raise ValueError("Preis darf nicht negativ sein.")
        return parsed

    @field_validator("assignment_type")
    @classmethod
    def check_assignment(cls, value: str) -> str:
        if value not in ("einzelteil", "baugruppe"):
            raise ValueError("Zuordnungstyp muss einzelteil oder baugruppe sein.")
        return value


class ManualPriceRead(BaseModel):
    id: int
    customer_id: int
    program_id: int
    linked_project_id: int
    assignment_type: str
    object_id: int
    bottom_price_per_piece: float | None = None
    actual_price_per_piece: float | None = None
