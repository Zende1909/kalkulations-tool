from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaschineBase(BaseModel):
    bezeichnung: str
    maschinen_nr: str
    stundensatz: float
    schliesskraft_t: float = 0
    aktiv: bool = True
    werk_id: int | None = None
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


class MaschineCreate(MaschineBase):
    pass


class MaschineUpdate(BaseModel):
    bezeichnung: str | None = None
    maschinen_nr: str | None = None
    stundensatz: float | None = None
    schliesskraft_t: float | None = None
    aktiv: bool | None = None
    werk_id: int | None = None
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
