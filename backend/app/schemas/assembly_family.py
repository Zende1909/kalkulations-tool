"""Schemas für Baugruppenfamilien und Variantenmix."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.numbers import parse_de_float

MixStatus = Literal["complete", "incomplete", "overflow", "empty"]


class AssemblyFamilyCreate(BaseModel):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    beschreibung: str = ""
    status: str = "entwurf"
    aktiv: bool = True


class AssemblyFamilyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    beschreibung: str | None = None
    status: str | None = None
    aktiv: bool | None = None


class AssemblyFamilyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    name: str
    beschreibung: str
    status: str
    aktiv: bool
    ergebnis: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssemblyVariantCreate(BaseModel):
    teilenummer: str = Field(min_length=1, max_length=100)
    bezeichnung: str = Field(min_length=1, max_length=255)
    anteil_prozent: float = Field(ge=0, le=100)
    beschreibung: str = ""
    aktiv: bool = True
    werk_id: int | None = None

    @field_validator("anteil_prozent", mode="before")
    @classmethod
    def coerce_anteil(cls, value: Any) -> Any:
        if value is None or value == "":
            raise ValueError("Variantenanteil ist erforderlich.")
        parsed = parse_de_float(value, field_label="Variantenanteil", allow_none=False)
        assert parsed is not None
        return parsed


class AssemblyVariantUpdate(BaseModel):
    teilenummer: str | None = Field(default=None, min_length=1, max_length=100)
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=255)
    anteil_prozent: float | None = Field(default=None, ge=0, le=100)
    beschreibung: str | None = None
    aktiv: bool | None = None
    werk_id: int | None = None

    @field_validator("anteil_prozent", mode="before")
    @classmethod
    def coerce_anteil_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Variantenanteil", allow_none=True)


class AssemblyVariantComponentRead(BaseModel):
    component_type: str
    component_id: int
    bezeichnung: str
    teilenummer: str = ""
    menge_je_variante: float
    effektive_jahresmenge: float


class AssemblyVariantSummary(BaseModel):
    id: int
    teilenummer: str
    bezeichnung: str
    anteil_prozent: float
    aktiv: bool
    jahresmenge: int
    komponenten_anzahl: int
    kosten_je_stueck: float
    gewichteter_kostenbeitrag: float | None = None
    komponenten: list[AssemblyVariantComponentRead] = Field(default_factory=list)


class AggregatedComponentRead(BaseModel):
    component_type: str
    component_id: int
    bezeichnung: str
    teilenummer: str = ""
    effektive_jahresmenge: float
    losgroesse: int | None = None
    anzahl_lose: int | None = None


class AssemblyFamilyMixRead(BaseModel):
    family_id: int
    name: str
    project_id: int
    status: str
    aktiv: bool
    project_jahresstueckzahl: int
    mix_status: MixStatus
    mix_message: str
    mix_is_complete: bool
    can_compute_full: bool
    active_share_sum_pct: float
    missing_pct: float
    overflow_pct: float
    variants: list[AssemblyVariantSummary]
    aggregated_components: list[AggregatedComponentRead]
    gewichtete_kosten_pro_projektstueck: float | None = None
