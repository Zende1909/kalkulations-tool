"""Schemas für die Zykluszeit-Schätzung."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.numbers import parse_de_float
from app.services.zykluszeit import (
    AUSWAHLWERTE,
    DEFAULT_ENTNAHMEART,
    DEFAULT_GROESSENKLASSE,
    DEFAULT_PROZESSAUFWAND,
    ENTNAHMEART_WERTE,
    GROESSENKLASSE_AUTO,
    KUEHLFAKTOR,
    PROZESSAUFWAND_WERTE,
    normalisiere_entnahmeart,
    normalisiere_groessenklasse,
    normalisiere_prozessaufwand,
)

_FLOAT_LABELS: dict[str, str] = {
    "zykluszeit_wandstaerke_mm": "kühlzeitrelevante Wandstärke",
    "zykluszeit_nebenzeiten_gesamt_s": "Nebenzeiten gesamt",
}


class ZykluszeitFields(BaseModel):
    """Eingabefelder der Zykluszeit-Schätzung (Teil von Create/Update/Calc)."""

    zykluszeit_quelle: str | None = None
    zykluszeit_wandstaerke_mm: float | None = Field(default=None, gt=0)
    zykluszeit_groessenklasse: str | None = None
    zykluszeit_prozessaufwand: str | None = None
    zykluszeit_entnahmeart: str | None = None
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
        if klasse not in AUSWAHLWERTE:
            zulaessig = ", ".join(AUSWAHLWERTE)
            raise ValueError(f"Größenklasse muss eine von {zulaessig} sein.")
        return klasse

    @field_validator("zykluszeit_prozessaufwand", mode="before")
    @classmethod
    def coerce_prozessaufwand(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        key = str(value).strip().lower()
        if key not in PROZESSAUFWAND_WERTE:
            zulaessig = ", ".join(PROZESSAUFWAND_WERTE)
            raise ValueError(f"Prozessaufwand muss eine von {zulaessig} sein.")
        return key

    @field_validator("zykluszeit_entnahmeart", mode="before")
    @classmethod
    def coerce_entnahmeart(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        key = str(value).strip().lower()
        if key not in ENTNAHMEART_WERTE:
            zulaessig = ", ".join(ENTNAHMEART_WERTE)
            raise ValueError(f"Entnahmeart muss eine von {zulaessig} sein.")
        return key

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
    # Aus der Maschinengrößen-Berechnung des Formulars; enthält die Kavitäten.
    zuhaltekraft_t: float | None = Field(default=None, ge=0)
    # Ersatzweise Zuhaltekraft der gewählten Maschine.
    maschinen_zuhaltekraft_t: float | None = Field(default=None, ge=0)
    # Für Einspritzzeit, Dosierüberhang und Greiferzuschlag.
    schussgewicht_g: float | None = Field(default=None, ge=0)
    kavitaeten: int | None = Field(default=None, ge=1)

    @field_validator("schussgewicht_g", "zuhaltekraft_t", "maschinen_zuhaltekraft_t", mode="before")
    @classmethod
    def coerce_mengen(cls, value: Any, info: Any) -> float | None:
        return parse_de_float(value, field_label=info.field_name or "Wert", allow_none=True)


class ZykluszeitResultSchema(BaseModel):
    berechenbar: bool
    hinweis: str | None = None
    warnungen: list[str] = Field(default_factory=list)
    wandstaerke_mm: float | None = None
    materialgruppe: str | None = None
    material_bezeichnung: str | None = None
    materialklasse: str | None = None
    groessenklasse: str | None = None
    groessenklasse_auswahl: str | None = None
    zuhaltekraft_t: float | None = None
    schussgewicht_g: float | None = None
    kavitaeten: int | None = None
    entnahmeart: str | None = None
    prozessaufwand: str | None = None
    kuehlfaktor: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeit_werkzeugbewegung_s: float | None = None
    nebenzeit_einspritz_nachdruck_s: float | None = None
    nebenzeit_dosierzeit_s: float | None = None
    nebenzeit_dosier_ueberhang_s: float | None = None
    nebenzeit_entnahme_s: float | None = None
    nebenzeit_prozessaufwand_zuschlag_s: float | None = None
    plastifizierleistung_kg_h: float | None = None
    schussmasse_gesamt_g: float | None = None
    nebenzeiten_automatisch_s: float | None = None
    schussgewicht_fallback: bool = False
    zuhaltekraft_fallback: bool = False
    nebenzeiten_gesamt_s: float | None = None
    nebenzeit_quelle: str | None = None
    gesamtzykluszeit_s: float | None = None
    gesamtzykluszeit_exakt_s: float | None = None
    status: str | None = None
    kann_uebernommen_werden: bool = False
    dosierzeit_warnfaktor: float | None = None
    dosierzeit_warngrenze_s: float | None = None


__all__ = [
    "DEFAULT_ENTNAHMEART",
    "DEFAULT_GROESSENKLASSE",
    "DEFAULT_PROZESSAUFWAND",
    "GROESSENKLASSE_AUTO",
    "KUEHLFAKTOR",
    "ZykluszeitCalcRequest",
    "ZykluszeitFields",
    "ZykluszeitResultSchema",
    "normalisiere_entnahmeart",
    "normalisiere_groessenklasse",
    "normalisiere_prozessaufwand",
]
