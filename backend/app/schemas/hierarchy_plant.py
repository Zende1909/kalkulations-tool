"""Schemas für Land, Werk und werkbezogene Zuschläge."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.schemas.numbers import parse_de_float as _parse_de_float, parse_percent_points
from app.services.losgroesse_berechnung import DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE

_OPT_FLOAT_LABELS = {
    "arbeitstage_pro_jahr": "Arbeitstage/Jahr",
    "produktionsintervall_arbeitstage": "Produktionsintervall (Arbeitstage)",
    "schichten_pro_tag": "Schichten/Tag",
    "stunden_pro_schicht": "Stunden/Schicht",
    "oee": "OEE",
    "space_cost_satz_pro_sqm_jahr": "Space-Satz",
    "abschreibungsdauer_jahre": "Abschreibungsdauer",
    "zinssatz": "Zinssatz",
    "versicherungssatz": "Versicherungssatz",
    "instandhaltungssatz": "Instandhaltungssatz",
    "strompreis": "Strompreis",
    "druckluftpreis": "Druckluftpreis",
    "kuehlwasserpreis": "Kühlwasserpreis",
}

_OPT_FLOAT_FIELDS = tuple(_OPT_FLOAT_LABELS.keys())

# Kapitalkostensätze am Werk: intern Anteil 0–1 (UI sendet nach /100, z. B. 8 % → 0,08).
_RATE_FRACTION_FIELDS = ("zinssatz", "versicherungssatz", "instandhaltungssatz")
_RATE_FRACTION_LABELS = {
    "zinssatz": "Zinssatz",
    "versicherungssatz": "Versicherungssatz",
    "instandhaltungssatz": "Instandhaltungssatz",
}


class LandBase(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=255)
    aktiv: bool = True


class LandCreate(LandBase):
    pass


class LandUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=16)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    aktiv: bool | None = None


class LandRead(LandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WerkBase(BaseModel):
    land_id: int
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(default="EUR", max_length=8)
    fx_to_eur: float = Field(default=1.0)
    aktiv: bool = True
    # Standortparameter für Maschinenstundensatz (Mappe1 Globals)
    arbeitstage_pro_jahr: float | None = None
    produktionsintervall_arbeitstage: float | None = None
    schichten_pro_tag: float | None = None
    stunden_pro_schicht: float | None = None
    oee: float | None = None
    space_cost_satz_pro_sqm_jahr: float | None = None
    abschreibungsdauer_jahre: float | None = None
    zinssatz: float | None = None
    versicherungssatz: float | None = None
    instandhaltungssatz: float | None = None
    strompreis: float | None = None
    druckluftpreis: float | None = None
    kuehlwasserpreis: float | None = None

    @field_validator("land_id", mode="before")
    @classmethod
    def coerce_land_id(cls, value: Any) -> int:
        if value is None or value == "":
            raise ValueError("Land ist Pflicht")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Land ist ungültig") from exc

    @field_validator("fx_to_eur", mode="before")
    @classmethod
    def coerce_fx_to_eur(cls, value: Any) -> float:
        parsed = _parse_de_float(value, field_label="Wechselkurs → EUR", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("fx_to_eur")
    @classmethod
    def validate_fx_to_eur(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Wechselkurs → EUR muss größer als 0 sein")
        return value

    @field_validator(*_OPT_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _OPT_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return _parse_de_float(value, field_label=label, allow_none=True)

    # Keine strenge Range-Validierung hier: WerkRead erbt WerkBase und muss
    # auch Altdaten außerhalb 0–1 noch ausliefern können (Warnung nur in der UI).


class WerkCreate(WerkBase):
    produktionsintervall_arbeitstage: float | None = Field(
        default=DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE
    )

    @field_validator("produktionsintervall_arbeitstage")
    @classmethod
    def validate_produktionsintervall(cls, value: float | None) -> float | None:
        if value is None:
            return DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE
        if value <= 0:
            raise ValueError(
                "Produktionsintervall muss eine positive Zahl Arbeitstage sein "
                f"(Standard: {DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE})."
            )
        return value

    @field_validator("oee")
    @classmethod
    def validate_oee(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0 or value > 1:
            raise ValueError("OEE muss im Intervall (0, 1] liegen (z. B. 0,9 = 90 %)")
        return value

    @field_validator(*_RATE_FRACTION_FIELDS)
    @classmethod
    def validate_rate_fractions(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is None:
            return None
        label = _RATE_FRACTION_LABELS.get(info.field_name or "", "Kostensatz")
        if value < 0 or value > 1:
            raise ValueError(
                f"{label} muss als Anteil zwischen 0 und 1 liegen "
                f"(UI-Prozent / 100, z. B. 8 % → 0,08). "
                f"Gespeicherte Werte außerhalb dieses Bereichs bitte manuell prüfen "
                f"und korrigieren – keine Automatikkorrektur."
            )
        return value


class WerkUpdate(BaseModel):
    land_id: int | None = None
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    currency: str | None = Field(default=None, max_length=8)
    fx_to_eur: float | None = Field(default=None)
    aktiv: bool | None = None
    arbeitstage_pro_jahr: float | None = None
    produktionsintervall_arbeitstage: float | None = None
    schichten_pro_tag: float | None = None
    stunden_pro_schicht: float | None = None
    oee: float | None = None
    space_cost_satz_pro_sqm_jahr: float | None = None
    abschreibungsdauer_jahre: float | None = None
    zinssatz: float | None = None
    versicherungssatz: float | None = None
    instandhaltungssatz: float | None = None
    strompreis: float | None = None
    druckluftpreis: float | None = None
    kuehlwasserpreis: float | None = None

    @field_validator("land_id", mode="before")
    @classmethod
    def coerce_land_id(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("Land ist ungültig") from exc

    @field_validator("fx_to_eur", mode="before")
    @classmethod
    def coerce_fx_to_eur(cls, value: Any) -> float | None:
        return _parse_de_float(value, field_label="Wechselkurs → EUR", allow_none=True)

    @field_validator("fx_to_eur")
    @classmethod
    def validate_fx_to_eur(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError("Wechselkurs → EUR muss größer als 0 sein")
        return value

    @field_validator(*_OPT_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _OPT_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return _parse_de_float(value, field_label=label, allow_none=True)

    @field_validator("produktionsintervall_arbeitstage")
    @classmethod
    def validate_produktionsintervall_update(cls, value: float | None) -> float | None:
        if value is not None and value <= 0:
            raise ValueError(
                "Produktionsintervall muss eine positive Zahl Arbeitstage sein "
                f"(Standard: {DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE})."
            )
        return value

    @field_validator("oee")
    @classmethod
    def validate_oee(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if value <= 0 or value > 1:
            raise ValueError("OEE muss im Intervall (0, 1] liegen (z. B. 0,9 = 90 %)")
        return value

    @field_validator(*_RATE_FRACTION_FIELDS)
    @classmethod
    def validate_rate_fractions(cls, value: float | None, info: ValidationInfo) -> float | None:
        if value is None:
            return None
        label = _RATE_FRACTION_LABELS.get(info.field_name or "", "Kostensatz")
        if value < 0 or value > 1:
            raise ValueError(
                f"{label} muss als Anteil zwischen 0 und 1 liegen "
                f"(UI-Prozent / 100, z. B. 8 % → 0,08). "
                f"Gespeicherte Werte außerhalb dieses Bereichs bitte manuell prüfen "
                f"und korrigieren – keine Automatikkorrektur."
            )
        return value


class WerkRead(WerkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WerkZuschlagBase(BaseModel):
    typ: str = Field(min_length=1, max_length=64)
    bezeichnung: str = Field(min_length=1, max_length=255)
    satz_prozent: float
    kostenbasis: str = ""
    aktiv: bool = True

    @field_validator("satz_prozent", mode="before")
    @classmethod
    def coerce_satz_prozent(cls, value: object) -> object:
        if value is None or value == "":
            return 0.0
        parsed = parse_percent_points(value, field_label="Satz", allow_none=False)
        assert parsed is not None
        return parsed


class WerkZuschlagCreate(WerkZuschlagBase):
    pass


class WerkZuschlagUpdate(BaseModel):
    typ: str | None = None
    bezeichnung: str | None = None
    satz_prozent: float | None = None
    kostenbasis: str | None = None
    aktiv: bool | None = None

    @field_validator("satz_prozent", mode="before")
    @classmethod
    def coerce_satz_prozent_update(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return parse_percent_points(value, field_label="Satz", allow_none=True)


class WerkZuschlagRead(WerkZuschlagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    werk_id: int
    created_at: datetime
    updated_at: datetime
