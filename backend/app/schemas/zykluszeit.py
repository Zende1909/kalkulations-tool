"""Schemas für den Zykluszeitvorschlag nach IKET."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.numbers import parse_de_float
from app.services.zykluszeit import (
    DEFAULT_KOMPONENTEN,
    DEFAULT_KUEHLFAKTOR,
    DEFAULT_NEBENZEITEN,
    DEFAULT_VARIANTE,
    NEBENZEIT_KEYS,
    UNTERSTUETZTE_VARIANTEN,
)

# Modellspalte je Nebenzeit-Schlüssel des Services.
NEBENZEIT_MODEL_FIELDS: dict[str, str] = {
    key: f"zykluszeit_nz_{key}" for key in NEBENZEIT_KEYS
}
# Feldname im Schema je Nebenzeit-Schlüssel.
NEBENZEIT_SCHEMA_FIELDS: dict[str, str] = dict(NEBENZEIT_MODEL_FIELDS)

_ZYKLUSZEIT_FLOAT_LABELS: dict[str, str] = {
    "zykluszeit_wandstaerke_mm": "Äquivalente Wandstärke",
    "zykluszeit_kuehlfaktor": "Zuschlagfaktor Werkzeugkühlung",
    "zykluszeit_nz_werkzeug_schliessen_s": "Werkzeug schließen",
    "zykluszeit_nz_duese_anlegen_s": "Düsen anlegen",
    "zykluszeit_nz_einspritzen_s": "Einspritzen",
    "zykluszeit_nz_werkzeug_oeffnen_s": "Werkzeug öffnen",
    "zykluszeit_nz_auswerfen_s": "Auswerfen/Entnahme",
    "zykluszeit_nz_kernzug_s": "Kernzug/Schieber",
    "zykluszeit_nz_ausschrauben_s": "Ausschrauben",
    "zykluszeit_nz_einlegen_s": "Einlegen",
    "zykluszeit_nz_ausblasen_s": "Ausblasen",
}
_ZYKLUSZEIT_FLOAT_FIELDS = tuple(_ZYKLUSZEIT_FLOAT_LABELS.keys())


class ZykluszeitFields(BaseModel):
    """Eingabefelder des Zykluszeitvorschlags (Teil von Create/Update/Calc)."""

    zykluszeit_quelle: str | None = None
    zykluszeit_wandstaerke_mm: float | None = Field(default=None, gt=0)
    zykluszeit_variante: int | None = None
    zykluszeit_kuehlfaktor: float | None = Field(default=None, gt=0)
    zykluszeit_komponenten: int | None = Field(default=None, ge=1)
    zykluszeit_nz_werkzeug_schliessen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_duese_anlegen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_einspritzen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_werkzeug_oeffnen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_auswerfen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_kernzug_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_ausschrauben_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_einlegen_s: float | None = Field(default=None, ge=0)
    zykluszeit_nz_ausblasen_s: float | None = Field(default=None, ge=0)

    @field_validator(*_ZYKLUSZEIT_FLOAT_FIELDS, mode="before")
    @classmethod
    def coerce_zykluszeit_floats(cls, value: Any, info: Any) -> float | None:
        label = _ZYKLUSZEIT_FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)

    @field_validator("zykluszeit_variante", mode="before")
    @classmethod
    def coerce_variante(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        variante = int(value)
        if variante not in UNTERSTUETZTE_VARIANTEN:
            zulaessig = ", ".join(str(v) for v in UNTERSTUETZTE_VARIANTEN)
            raise ValueError(f"Berechnungsvariante muss eine von {zulaessig} sein.")
        return variante

    @field_validator("zykluszeit_quelle", mode="before")
    @classmethod
    def coerce_quelle(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        quelle = str(value).strip().lower()
        if quelle not in ("manuell", "vorschlag"):
            raise ValueError("Quelle der Zykluszeit muss 'manuell' oder 'vorschlag' sein.")
        return quelle

    def nebenzeiten_dict(self) -> dict[str, float]:
        return {
            key: (
                getattr(self, model_field)
                if getattr(self, model_field) is not None
                else DEFAULT_NEBENZEITEN[key]
            )
            for key, model_field in NEBENZEIT_SCHEMA_FIELDS.items()
        }


class ZykluszeitCalcRequest(ZykluszeitFields):
    """Standalone-Request für die Live-Vorschau des Zykluszeitvorschlags."""

    material_id: int | None = None


class ZykluszeitResultSchema(BaseModel):
    berechenbar: bool
    hinweis: str | None = None
    variante: int | None = None
    kuehlfaktor: float | None = None
    komponenten: int | None = None
    wandstaerke_mm: float | None = None
    schmelzdichte_kg_m3: float | None = None
    waermekapazitaet_j_kg_k: float | None = None
    waermeleitfaehigkeit_w_m_k: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    vorfaktor_s: float | None = None
    variantenfaktor: float | None = None
    temperaturquotient: float | None = None
    ln_argument: float | None = None
    ln_wert: float | None = None
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeiten: dict[str, float] = Field(default_factory=dict)
    nebenzeiten_gesamt_s: float | None = None
    gesamtzykluszeit_s: float | None = None


__all__ = [
    "DEFAULT_KOMPONENTEN",
    "DEFAULT_KUEHLFAKTOR",
    "DEFAULT_VARIANTE",
    "NEBENZEIT_MODEL_FIELDS",
    "ZykluszeitCalcRequest",
    "ZykluszeitFields",
    "ZykluszeitResultSchema",
]
