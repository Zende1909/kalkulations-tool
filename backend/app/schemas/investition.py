"""Investitions-Schemas inkl. hierarchischer Zuordnung."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.numbers import parse_de_float
from app.services.investition_assignment_service import ASSIGNMENT_TYPES
from app.services.investition_service import INVESTMENT_TYPES, PAYMENT_TYPES, PLANNING_STATUS_VALUES

AssignmentType = Literal["einzelteil", "kaufteil", "baugruppe", "gesamtprojekt"]


class InvestitionBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=255)
    investment_type: str = Field(default="Werkzeug")
    payment_type: str
    amount: float = Field(ge=0)
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

    @field_validator("amount", mode="before")
    @classmethod
    def coerce_amount(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0.0
        parsed = parse_de_float(value, field_label="Betrag", allow_none=False)
        assert parsed is not None
        return parsed

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
    amount: float | None = Field(default=None, ge=0)
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

    @field_validator("amount", mode="before")
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
    amount: float
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
    amortisationsanteil_je_stueck: float | None = None
    preis_inkl_amortisation_je_stueck: float | None = None
    einmalinvestitionen: list[EinmalinvestitionPosition] = Field(default_factory=list)
    anzahl_investitionen: int = 0
    hat_gespeicherte_kalkulation: bool = False
