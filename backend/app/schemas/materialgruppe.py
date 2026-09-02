from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.schemas.numbers import parse_de_float
from app.services.material_thermik import normalisiere_gruppenschluessel

_FLOAT_LABELS: dict[str, str] = {
    "schmelzdichte_kg_m3": "Schmelzdichte",
    "waermekapazitaet_j_kg_k": "Wärmekapazität",
    "waermeleitfaehigkeit_w_m_k": "Wärmeleitfähigkeit",
    "werkzeugtemperatur_c": "Werkzeugtemperatur",
    "schmelzetemperatur_c": "Schmelzetemperatur",
    "entformungstemperatur_c": "Entformungstemperatur",
}
_THERMAL_FLOAT_FIELDS = tuple(_FLOAT_LABELS.keys())


class MaterialgruppeBase(BaseModel):
    gruppe: str
    bezeichnung: str
    schmelzdichte_kg_m3: float
    waermekapazitaet_j_kg_k: float
    waermeleitfaehigkeit_w_m_k: float
    werkzeugtemperatur_c: float
    schmelzetemperatur_c: float
    entformungstemperatur_c: float
    aktiv: bool = True

    @field_validator("gruppe", mode="before")
    @classmethod
    def coerce_gruppe(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError("Gruppenschlüssel ist erforderlich.")
        normalisiert = normalisiere_gruppenschluessel(str(value))
        if normalisiert is None:
            raise ValueError("Gruppenschlüssel ist ungültig.")
        return normalisiert

    @field_validator(*_THERMAL_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_floats(cls, value: Any, info: ValidationInfo) -> float:
        label = _FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        parsed = parse_de_float(value, field_label=label, allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("schmelzdichte_kg_m3", "waermekapazitaet_j_kg_k", "waermeleitfaehigkeit_w_m_k")
    @classmethod
    def positive_thermal(cls, value: float, info: ValidationInfo) -> float:
        label = _FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        if value <= 0:
            raise ValueError(f"{label} muss größer als 0 sein.")
        return value

    @field_validator("entformungstemperatur_c")
    @classmethod
    def temperature_order(cls, entformung: float, info: ValidationInfo) -> float:
        data = info.data
        werkzeug = data.get("werkzeugtemperatur_c")
        schmelze = data.get("schmelzetemperatur_c")
        if werkzeug is not None and not (werkzeug < entformung):
            raise ValueError("Entformungstemperatur muss über der Werkzeugtemperatur liegen.")
        if schmelze is not None and not (entformung < schmelze):
            raise ValueError("Entformungstemperatur muss unter der Schmelzetemperatur liegen.")
        return entformung


class MaterialgruppeCreate(MaterialgruppeBase):
    pass


class MaterialgruppeUpdate(BaseModel):
    gruppe: str | None = None
    bezeichnung: str | None = None
    schmelzdichte_kg_m3: float | None = None
    waermekapazitaet_j_kg_k: float | None = None
    waermeleitfaehigkeit_w_m_k: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    aktiv: bool | None = None

    @field_validator("gruppe", mode="before")
    @classmethod
    def coerce_gruppe(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        normalisiert = normalisiere_gruppenschluessel(str(value))
        if normalisiert is None:
            raise ValueError("Gruppenschlüssel ist ungültig.")
        return normalisiert

    @field_validator(*_THERMAL_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)


class MaterialgruppeRead(MaterialgruppeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
