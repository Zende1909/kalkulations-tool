from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.schemas.numbers import parse_de_float

_REQUIRED_FLOAT_LABELS = {
    "stundensatz": "Stundensatz",
    "schliesskraft_t": "Schließkraft",
}

_OPTIONAL_FLOAT_LABELS = {
    "arbeitstage_pro_jahr": "Arbeitstage/Jahr",
    "schichten_pro_tag": "Schichten/Tag",
    "stunden_pro_schicht": "Stunden/Schicht",
    "oee": "OEE",
    "investment": "Investment",
    "flaeche_sqm": "Fläche",
    "space_cost_satz_pro_sqm_jahr": "Space-Satz",
    "abschreibungsdauer_jahre": "Abschreibungsdauer",
    "zinssatz": "Zinssatz",
    "versicherungssatz": "Versicherungssatz",
    "instandhaltungssatz": "Instandhaltungssatz",
    "stromverbrauch_kwh_h": "Stromverbrauch",
    "strompreis": "Strompreis",
    "druckluftverbrauch_m3_h": "Druckluftverbrauch",
    "druckluftpreis": "Druckluftpreis",
    "kuehlwasserverbrauch_m3_h": "Kühlwasserverbrauch",
    "kuehlwasserpreis": "Kühlwasserpreis",
    "setup_zeit_min": "Setup-Zeit",
    "setup_mitarbeiter": "Setup-Mitarbeiteranzahl",
}

_REQUIRED_FLOAT_FIELDS = tuple(_REQUIRED_FLOAT_LABELS.keys())
_OPTIONAL_FLOAT_FIELDS = tuple(_OPTIONAL_FLOAT_LABELS.keys())


class MaschineBase(BaseModel):
    bezeichnung: str
    maschinen_nr: str
    stundensatz: float = 0
    schliesskraft_t: float = 0
    aktiv: bool = True
    werk_id: int | None = None
    maschinentyp: str | None = None
    variante: str | None = None
    source_currency: str | None = None
    # Legacy: früher am Maschine-Datensatz; neue Pflege am Werk.
    # Bleiben im Schema für Lesekompatibilität, werden bei Neuberechnung
    # nur noch als Fallback genutzt, wenn Werkwerte fehlen.
    arbeitstage_pro_jahr: float | None = None
    schichten_pro_tag: float | None = None
    stunden_pro_schicht: float | None = None
    oee: float | None = None
    investment: float | None = None
    flaeche_sqm: float | None = None
    space_cost_satz_pro_sqm_jahr: float | None = None
    abschreibungsdauer_jahre: float | None = None
    zinssatz: float | None = None
    versicherungssatz: float | None = None
    instandhaltungssatz: float | None = None
    stromverbrauch_kwh_h: float | None = None
    strompreis: float | None = None
    druckluftverbrauch_m3_h: float | None = None
    druckluftpreis: float | None = None
    kuehlwasserverbrauch_m3_h: float | None = None
    kuehlwasserpreis: float | None = None
    setup_zeit_min: float | None = None
    setup_mitarbeiter: float | None = None

    @field_validator(*_REQUIRED_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_required_floats(cls, value: Any, info: ValidationInfo) -> float:
        label = _REQUIRED_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        parsed = parse_de_float(value, field_label=label, allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator(*_OPTIONAL_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _OPTIONAL_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)


class MaschineCreate(MaschineBase):
    werk_id: int = Field(ge=1)


class MaschineUpdate(BaseModel):
    bezeichnung: str | None = None
    maschinen_nr: str | None = None
    stundensatz: float | None = None
    schliesskraft_t: float | None = None
    aktiv: bool | None = None
    werk_id: int | None = Field(default=None, ge=1)
    maschinentyp: str | None = None
    variante: str | None = None
    source_currency: str | None = None
    arbeitstage_pro_jahr: float | None = None
    schichten_pro_tag: float | None = None
    stunden_pro_schicht: float | None = None
    oee: float | None = None
    investment: float | None = None
    flaeche_sqm: float | None = None
    space_cost_satz_pro_sqm_jahr: float | None = None
    abschreibungsdauer_jahre: float | None = None
    zinssatz: float | None = None
    versicherungssatz: float | None = None
    instandhaltungssatz: float | None = None
    stromverbrauch_kwh_h: float | None = None
    strompreis: float | None = None
    druckluftverbrauch_m3_h: float | None = None
    druckluftpreis: float | None = None
    kuehlwasserverbrauch_m3_h: float | None = None
    kuehlwasserpreis: float | None = None
    setup_zeit_min: float | None = None
    setup_mitarbeiter: float | None = None

    @field_validator("stundensatz", "schliesskraft_t", mode="before")
    @classmethod
    def coerce_optional_required_style(cls, value: Any, info: ValidationInfo) -> float | None:
        if value is None or value == "":
            return None
        label = _REQUIRED_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)

    @field_validator(*_OPTIONAL_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_optional_floats(cls, value: Any, info: ValidationInfo) -> float | None:
        label = _OPTIONAL_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)


class MaschineRead(MaschineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    jahresstunden: float | None = None
    space_costs_pro_stunde: float | None = None
    abschreibung_pro_stunde: float | None = None
    zinsen_pro_stunde: float | None = None
    versicherung_pro_stunde: float | None = None
    instandhaltung_pro_stunde: float | None = None
    energie_pro_stunde: float | None = None
    stundensatz_source: float | None = None
    rate_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class MaschineRecalculateRequest(BaseModel):
    fx_to_eur: float | None = Field(default=None, gt=0)

    @field_validator("fx_to_eur", mode="before")
    @classmethod
    def coerce_fx(cls, value: Any) -> float | None:
        return parse_de_float(value, field_label="Wechselkurs → EUR", allow_none=True)
