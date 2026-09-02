from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.schemas.numbers import parse_de_float
from app.services.material_thermik import normalisiere_gruppenschluessel

_REQUIRED_FLOAT_LABELS = {
    "preis_pro_kg": "Preis pro kg",
    "dichte": "Dichte",
    "injection_pressure_kg_cm2": "Einspritzdruck",
}
_REQUIRED_FLOAT_FIELDS = tuple(_REQUIRED_FLOAT_LABELS.keys())


class MaterialGruppeField(BaseModel):
    """Materialgruppe als Verweis auf einen Eintrag in ``materialgruppen``."""

    materialgruppe: str | None = None

    @field_validator("materialgruppe", mode="before")
    @classmethod
    def coerce_materialgruppe(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        return normalisiere_gruppenschluessel(str(value))


class MaterialBase(MaterialGruppeField):
    bezeichnung: str
    material_nr: str
    preis_pro_kg: float
    dichte: float
    injection_pressure_kg_cm2: float = 500.0
    waehrung: str = "EUR"
    aktiv: bool = True

    @field_validator(*_REQUIRED_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_required_floats(cls, value: Any, info: ValidationInfo) -> float:
        label = _REQUIRED_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        parsed = parse_de_float(value, field_label=label, allow_none=False)
        assert parsed is not None
        return parsed


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(MaterialGruppeField):
    bezeichnung: str | None = None
    material_nr: str | None = None
    preis_pro_kg: float | None = None
    dichte: float | None = None
    injection_pressure_kg_cm2: float | None = None
    waehrung: str | None = None
    aktiv: bool | None = None

    @field_validator(*_REQUIRED_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _REQUIRED_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class MaterialGruppeRead(BaseModel):
    """Nur-Lese-Sicht auf die Kennwerte einer Materialgruppe."""

    gruppe: str
    bezeichnung: str
    schmelzdichte_kg_m3: float
    waermekapazitaet_j_kg_k: float
    waermeleitfaehigkeit_w_m_k: float
    werkzeugtemperatur_c: float
    schmelzetemperatur_c: float
    entformungstemperatur_c: float


__all__ = [
    "MaterialBase",
    "MaterialCreate",
    "MaterialGruppeField",
    "MaterialGruppeRead",
    "MaterialRead",
    "MaterialUpdate",
]
