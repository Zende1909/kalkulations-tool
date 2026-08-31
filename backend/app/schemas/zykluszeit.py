"""Schemas für die Zykluszeit-Schätzung."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.numbers import parse_de_float
from app.services.zykluszeit import (
    DEFAULT_GROESSENKLASSE,
    GROESSENKLASSEN_KEYS,
    KUEHLFAKTOR,
    normalisiere_groessenklasse,
)

_FLOAT_LABELS: dict[str, str] = {
    "zykluszeit_wandstaerke_mm": "Äquivalente Wandstärke",
    "zykluszeit_nebenzeiten_gesamt_s": "Nebenzeiten gesamt",
}


class ZykluszeitFields(BaseModel):
    """Eingabefelder der Zykluszeit-Schätzung (Teil von Create/Update/Calc)."""

    zykluszeit_quelle: str | None = None
    zykluszeit_wandstaerke_mm: float | None = Field(default=None, gt=0)
    zykluszeit_groessenklasse: str | None = None
    zykluszeit_nebenzeiten_gesamt_s: float | None = Field(default=None, ge=0)

    @field_validator(*_FLOAT_LABELS.keys(), mode="before")
    @classmethod
    def coerce_floats(cls, value: Any, info: Any) -> float | None:
        label = _FLOAT_LABELS.get(info.field_name or "", info.field_name or "Wert")
        return parse_de_float(value, field_label=label, allow_none=True)

    @field_validator("zykluszeit_groessenklasse", mode="before")
    @classmethod
    def coerce_groessenklasse(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        klasse = str(value).strip().lower()
        if klasse not in GROESSENKLASSEN_KEYS:
            zulaessig = ", ".join(GROESSENKLASSEN_KEYS)
            raise ValueError(f"Größenklasse muss eine von {zulaessig} sein.")
        return klasse

    @field_validator("zykluszeit_quelle", mode="before")
    @classmethod
    def coerce_quelle(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        quelle = str(value).strip().lower()
        if quelle not in ("manuell", "vorschlag"):
            raise ValueError("Quelle der Zykluszeit muss 'manuell' oder 'vorschlag' sein.")
        return quelle


class ZykluszeitCalcRequest(ZykluszeitFields):
    """Standalone-Request für die Live-Vorschau der Zykluszeit-Schätzung."""

    material_id: int | None = None


class ZykluszeitResultSchema(BaseModel):
    berechenbar: bool
    hinweis: str | None = None
    wandstaerke_mm: float | None = None
    materialgruppe: str | None = None
    material_bezeichnung: str | None = None
    groessenklasse: str | None = None
    kuehlfaktor: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeiten_gesamt_s: float | None = None
    gesamtzykluszeit_s: float | None = None


__all__ = [
    "DEFAULT_GROESSENKLASSE",
    "KUEHLFAKTOR",
    "ZykluszeitCalcRequest",
    "ZykluszeitFields",
    "ZykluszeitResultSchema",
    "normalisiere_groessenklasse",
]
