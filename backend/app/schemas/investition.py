from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.investition_service import INVESTMENT_TYPES, PAYMENT_TYPES, STATUS_VALUES


class InvestitionBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    investment_type: str = Field(default="Werkzeug")
    payment_type: str = Field(default="Einmalzahlung")
    amount: float = Field(ge=0)
    amortization_volume: int | None = Field(default=None, ge=1)
    project: str = Field(default="", max_length=255)
    customer: str = Field(default="", max_length=255)
    part_name: str = Field(default="", max_length=255)
    part_number: str = Field(default="", max_length=255)
    calculation_id: int | None = None
    baugruppe_id: int | None = None
    supplier: str = Field(default="", max_length=255)
    order_date: date | None = None
    delivery_date: date | None = None
    status: str = Field(default="In Planung")
    description: str = ""
    included_in_unit_price: bool | None = None

    @field_validator("investment_type")
    @classmethod
    def check_type(cls, value: str) -> str:
        if value not in INVESTMENT_TYPES:
            raise ValueError(f"Ungültige Investitionsart: {value}")
        return value

    @field_validator("payment_type")
    @classmethod
    def check_payment(cls, value: str) -> str:
        if value not in PAYMENT_TYPES:
            raise ValueError(f"Ungültige Zahlungsart: {value}")
        return value

    @field_validator("status")
    @classmethod
    def check_status(cls, value: str) -> str:
        if value not in STATUS_VALUES:
            raise ValueError(f"Ungültiger Status: {value}")
        return value


class InvestitionCreate(InvestitionBase):
    pass


class InvestitionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    investment_type: str | None = None
    payment_type: str | None = None
    amount: float | None = Field(default=None, ge=0)
    amortization_volume: int | None = Field(default=None, ge=1)
    project: str | None = Field(default=None, max_length=255)
    customer: str | None = None
    part_name: str | None = None
    part_number: str | None = None
    calculation_id: int | None = None
    baugruppe_id: int | None = None
    supplier: str | None = None
    order_date: date | None = None
    delivery_date: date | None = None
    status: str | None = None
    description: str | None = None
    included_in_unit_price: bool | None = None
    archived: bool | None = None


class InvestitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    investment_type: str
    payment_type: str
    amount: float
    amortization_volume: int | None
    cost_per_piece: float | None
    project: str
    customer: str
    part_name: str
    part_number: str
    calculation_id: int | None
    baugruppe_id: int | None
    supplier: str
    order_date: date | None
    delivery_date: date | None
    status: str
    description: str
    included_in_unit_price: bool
    archived: bool
    zuordnung: str = ""
    payment_hint: str = ""
    created_at: datetime
    updated_at: datetime


class InvestitionSummary(BaseModel):
    gesamtinvestitionen: float
    anzahl_investitionen: int
    summe_einmalzahlungen: float
    summe_amortisiert: float
    in_planung: int
    bestellt: int
    abgeschlossen: int
