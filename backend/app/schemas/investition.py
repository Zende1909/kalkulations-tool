"""Investitions-Schemas inkl. hierarchischer Zuordnung und Finanzbeträge."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.numbers import parse_de_float
from app.services.investition_assignment_service import ASSIGNMENT_TYPES
from app.services.investition_service import INVESTMENT_TYPES, PAYMENT_TYPES, PLANNING_STATUS_VALUES

AssignmentType = Literal["einzelteil", "kaufteil", "baugruppe", "gesamtprojekt"]


def _parse_money(value: Any, label: str, *, allow_none: bool) -> Any:
    if value is None or value == "":
        return None if allow_none else 0.0
    return parse_de_float(value, field_label=label, allow_none=allow_none)


class InvestitionBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    investment_type: str = Field(default="Werkzeug")
    payment_type: str
    cost_amount: float = Field(default=0, ge=0)
    bottom_price: float | None = Field(default=None, ge=0)
    revenue_amount: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, ge=0, deprecated=True)
    amortization_volume: int | None = Field(default=None, ge=1)
    project: str = Field(default="", max_length=255)
    customer: str = Field(default="", max_length=255)
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    assignment_type: AssignmentType | None = None
    part_name: str = Field(default="", max_length=255)
    part_number: str = Field(default="", max_length=255)
    calculation_id: int | None = None
    baugruppe_id: int | None = None
    kaufteil_id: int | None = None
    planning_status: str | None = Field(default=None, alias="status")
    description: str = ""
    included_in_unit_price: bool | None = None

    @field_validator("cost_amount", mode="before")
    @classmethod
    def coerce_cost_amount(cls, value: Any) -> Any:
        return _parse_money(value, "Kosten", allow_none=False)

    @field_validator("bottom_price", "revenue_amount", mode="before")
    @classmethod
    def coerce_optional_amounts(cls, value: Any) -> Any:
        return _parse_money(value, "Betrag", allow_none=True)

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_legacy_amount(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Betrag", allow_none=True)

    @model_validator(mode="after")
    def resolve_legacy_amount(self) -> "InvestitionBase":
        if self.amount is not None and self.cost_amount == 0:
            object.__setattr__(self, "cost_amount", self.amount)
        return self

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

    @field_validator("planning_status")
    @classmethod
    def check_planning_status(cls, value: str | None) -> str | None:
        if value and value not in PLANNING_STATUS_VALUES:
            raise ValueError(f"Ungültiger Planungsstatus: {value}")
        return value

    @field_validator("assignment_type")
    @classmethod
    def check_assignment_type(cls, value: str | None) -> str | None:
        if value is not None and value not in ASSIGNMENT_TYPES:
            raise ValueError(f"Ungültiger Zuordnungstyp: {value}")
        return value


class InvestitionCreate(InvestitionBase):
    @model_validator(mode="after")
    def require_hierarchy_or_legacy_project(self) -> "InvestitionCreate":
        has_hierarchy = (
            self.customer_id is not None
            and self.program_id is not None
            and self.linked_project_id is not None
        )
        if not has_hierarchy and not (self.project or "").strip():
            raise ValueError("Projekt oder Hierarchie (Kunde/Programm/Projekt-ID) ist erforderlich.")
        if has_hierarchy and not self.assignment_type:
            raise ValueError("Zuordnungstyp ist erforderlich.")
        return self


class InvestitionUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    investment_type: str | None = None
    payment_type: str | None = None
    cost_amount: float | None = Field(default=None, ge=0)
    bottom_price: float | None = Field(default=None, ge=0)
    revenue_amount: float | None = Field(default=None, ge=0)
    amount: float | None = Field(default=None, ge=0, deprecated=True)
    amortization_volume: int | None = Field(default=None, ge=1)
    project: str | None = Field(default=None, max_length=255)
    customer: str | None = None
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    assignment_type: AssignmentType | None = None
    part_name: str | None = None
    part_number: str | None = None
    calculation_id: int | None = None
    baugruppe_id: int | None = None
    kaufteil_id: int | None = None
    planning_status: str | None = Field(default=None, alias="status")
    description: str | None = None
    included_in_unit_price: bool | None = None
    archived: bool | None = None

    @field_validator("cost_amount", "bottom_price", "revenue_amount", "amount", mode="before")
    @classmethod
    def coerce_amount_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Betrag", allow_none=True)

    @field_validator("assignment_type")
    @classmethod
    def check_assignment_type_update(cls, value: str | None) -> str | None:
        if value is not None and value not in ASSIGNMENT_TYPES:
            raise ValueError(f"Ungültiger Zuordnungstyp: {value}")
        return value


class InvestitionTargetRead(BaseModel):
    object_id: int
    assignment_type: str
    label: str
    material_number: str
    part_name: str
    status: str | None = None
    part_price: float | None = None
    supplier: str | None = None
    nominierung: str | None = None
    customer_name: str | None = None
    program_name: str | None = None
    project_name: str | None = None


class InvestitionRead(BaseModel):
    id: int
    name: str
    investment_type: str
    payment_type: str
    cost_amount: float
    bottom_price: float | None = None
    revenue_amount: float | None = None
    amount: float
    margin_revenue_minus_cost: float | None = None
    margin_revenue_minus_bottom_price: float | None = None
    margin_bottom_price_minus_cost: float | None = None
    amount_warnings: list[str] = Field(default_factory=list)
    amortization_volume: int | None
    cost_per_piece: float | None
    project: str
    customer: str
    customer_id: int | None = None
    program_id: int | None = None
    linked_project_id: int | None = None
    assignment_type: str | None = None
    assignment_type_label: str = ""
    part_number: str = ""
    part_name: str = ""
    calculation_id: int | None
    baugruppe_id: int | None
    kaufteil_id: int | None = None
    description: str
    included_in_unit_price: bool
    archived: bool
    zuordnung: str = ""
    payment_hint: str = ""
    created_at: datetime
    updated_at: datetime


class EinmalinvestitionPosition(BaseModel):
    id: int
    name: str
    amount: float
    cost_amount: float = 0
    bottom_price: float | None = None
    revenue_amount: float | None = None
    hinweis: str


class BusinessCaseSummary(BaseModel):
    filter: dict
    teilepreis_je_stueck: float | None = None
    baugruppenpreis_je_stueck: float | None = None
    jahresstueckzahl: int | None = None
    jahresumsatz: float | None = None
    investitionen_gesamt: float = 0
    amortisationsinvestitionen_gesamt: float = 0
    einmalinvestitionen_gesamt: float = 0
    investition_cost_total: float = 0
    investition_bottom_price_total: float = 0
    investition_revenue_total: float = 0
    margin_revenue_minus_cost_total: float | None = None
    margin_revenue_minus_bottom_price_total: float | None = None
    margin_bottom_price_minus_cost_total: float | None = None
    amortisationsanteil_je_stueck: float | None = None
    preis_inkl_amortisation_je_stueck: float | None = None
    einmalinvestitionen: list[EinmalinvestitionPosition] = Field(default_factory=list)
    anzahl_investitionen: int = 0
    hat_gespeicherte_kalkulation: bool = False
