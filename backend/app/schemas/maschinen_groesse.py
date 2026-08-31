"""Pydantic-Schemas für Maschinengröße / Zuhaltekraft."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MaschinenGroesseModus = Literal["masse", "flaeche"]


class MaschinenGroesseFields(BaseModel):
    maschinen_groesse_modus: MaschinenGroesseModus | None = None
    maschinen_groesse_breite_mm: float | None = Field(default=None, ge=0)
    maschinen_groesse_laenge_mm: float | None = Field(default=None, ge=0)
    maschinen_groesse_oeffnungen_pct: float | None = Field(default=None, ge=0, le=100)
    maschinen_groesse_proj_flaeche_mm2: float | None = Field(default=None, ge=0)
    maschinen_groesse_schwindung_pct: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_modus_fields(self) -> "MaschinenGroesseFields":
        if self.maschinen_groesse_modus is None:
            return self
        if self.maschinen_groesse_schwindung_pct is None:
            raise ValueError("Schwindung ist für die Maschinengrößenberechnung erforderlich.")
        if self.maschinen_groesse_modus == "masse":
            missing = [
                name
                for name, val in (
                    ("Breite", self.maschinen_groesse_breite_mm),
                    ("Länge", self.maschinen_groesse_laenge_mm),
                    ("Öffnungen", self.maschinen_groesse_oeffnungen_pct),
                )
                if val is None
            ]
            if missing:
                raise ValueError(
                    "Im Modus Maße sind Breite, Länge und Öffnungen erforderlich."
                )
        else:
            if self.maschinen_groesse_proj_flaeche_mm2 is None:
                raise ValueError(
                    "Im Modus Projizierte Fläche ist die Fläche erforderlich."
                )
        return self


class MaschinenGroesseCalcRequest(MaschinenGroesseFields):
    material_id: int | None = None
    kavitaeten: int = Field(ge=1, default=1)
    werk_id: int | None = None


class MaschinenGroesseResultSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    modus: MaschinenGroesseModus
    injection_pressure_kg_cm2: float
    kavitaeten: int
    breite_mm: float | None = None
    laenge_mm: float | None = None
    oeffnungen_pct: float | None = None
    proj_flaeche_mm2: float | None = None
    schwindung_pct: float | None = None
    proj_flaeche_netto_mm2: float | None = None
    zuhaltekraft_ohne_sicherheit_t: float
    sicherheitszuschlag_faktor: float
    zuhaltekraft_erforderlich_t: float
    empfohlene_maschine_id: int | None = None
    empfohlene_maschine_name: str | None = None
    empfohlene_maschine_schliesskraft_t: float | None = None
    warnung: str | None = None
