from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from app.schemas.numbers import parse_de_float
from app.services.material_thermik import (
    MATERIALGRUPPEN_DEFAULTS,
    THERMIK_FELDER,
    defaults_fuer_gruppe,
    normalisiere_gruppe,
)

_REQUIRED_FLOAT_LABELS = {
    "preis_pro_kg": "Preis pro kg",
    "dichte": "Dichte",
    "injection_pressure_kg_cm2": "Einspritzdruck",
}
_REQUIRED_FLOAT_FIELDS = tuple(_REQUIRED_FLOAT_LABELS.keys())

_THERMIK_FLOAT_LABELS = {
    "schmelzdichte_kg_m3": "Schmelzdichte",
    "waermekapazitaet_j_kg_k": "spezifische Wärmekapazität",
    "waermeleitfaehigkeit_w_m_k": "Wärmeleitfähigkeit",
    "werkzeugtemperatur_c": "Werkzeugoberflächentemperatur",
    "schmelzetemperatur_c": "Schmelzetemperatur",
    "entformungstemperatur_c": "Entformungstemperatur",
}
_THERMIK_FLOAT_FIELDS = tuple(_THERMIK_FLOAT_LABELS.keys())

_POSITIVE_THERMIK_FIELDS = (
    "schmelzdichte_kg_m3",
    "waermekapazitaet_j_kg_k",
    "waermeleitfaehigkeit_w_m_k",
)


def _validate_positive_thermik(model: BaseModel) -> None:
    for name in _POSITIVE_THERMIK_FIELDS:
        wert = getattr(model, name, None)
        if wert is not None and wert <= 0:
            raise ValueError(f"{_THERMIK_FLOAT_LABELS[name]} muss größer als 0 sein.")


class MaterialThermikFields(BaseModel):
    materialgruppe: str | None = None
    schmelzdichte_kg_m3: float | None = None
    waermekapazitaet_j_kg_k: float | None = None
    waermeleitfaehigkeit_w_m_k: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None

    @field_validator(*_THERMIK_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_thermik_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _THERMIK_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)

    @field_validator("materialgruppe", mode="before")
    @classmethod
    def coerce_materialgruppe(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        normalisiert = normalisiere_gruppe(str(value))
        if normalisiert is None:
            bekannt = ", ".join(sorted(MATERIALGRUPPEN_DEFAULTS))
            raise ValueError(f"Unbekannte Materialgruppe '{value}'. Bekannt sind: {bekannt}.")
        return normalisiert


class MaterialBase(MaterialThermikFields):
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
    @model_validator(mode="after")
    def apply_materialgruppe_defaults(self) -> "MaterialCreate":
        """Nicht gepflegte Thermikfelder aus den Gruppen-Richtwerten vorbelegen."""
        defaults = defaults_fuer_gruppe(self.materialgruppe)
        if defaults is not None:
            for name, wert in defaults.thermik_felder().items():
                if getattr(self, name) is None:
                    setattr(self, name, wert)
        _validate_positive_thermik(self)
        return self


class MaterialUpdate(MaterialThermikFields):
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

    @model_validator(mode="after")
    def check_thermik(self) -> "MaterialUpdate":
        _validate_positive_thermik(self)
        return self


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class MaterialThermikDefaultRead(BaseModel):
    gruppe: str
    bezeichnung: str
    schmelzdichte_kg_m3: float
    waermekapazitaet_j_kg_k: float
    waermeleitfaehigkeit_w_m_k: float
    werkzeugtemperatur_c: float
    schmelzetemperatur_c: float
    entformungstemperatur_c: float
    quelle: str


__all__ = [
    "MaterialBase",
    "MaterialCreate",
    "MaterialRead",
    "MaterialThermikDefaultRead",
    "MaterialThermikFields",
    "MaterialUpdate",
    "THERMIK_FELDER",
]
