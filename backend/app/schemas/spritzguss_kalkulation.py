from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SpritzgussCalcRequest(BaseModel):
    teilegewicht_netto_g: float = Field(ge=0)
    materialpreis_pro_kg: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    mgk_pct: float = Field(ge=0)
    zykluszeit_s: float = Field(ge=0)
    maschinenstundensatz: float = Field(ge=0)
    kavitaeten: int = Field(ge=1)
    lohnstundensatz: float = Field(ge=0)
    fgk_pct: float = Field(ge=0)
    werkzeugkosten_eur: float = Field(ge=0)
    amortisationsvolumen: float = Field(gt=0)
    vvgk_pct: float = Field(ge=0)
    gewinn_pct: float = Field(ge=0)
    skonto_pct: float = Field(ge=0)


class SpritzgussErgebnisSchema(BaseModel):
    materialgewicht_kg: float
    materialkosten: float
    materialkosten_inkl_ausschuss: float
    materialgemeinkosten: float
    materialkosten_gesamt: float
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    werkzeugkostenanteil: float
    herstellkosten: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    verkaufspreis: float


class SpritzgussCalcResponse(BaseModel):
    ergebnis: SpritzgussErgebnisSchema
    bloecke: dict[str, dict[str, float]]


class SpritzgussKalkulationBase(BaseModel):
    teilebezeichnung: str = Field(min_length=1, max_length=255)
    teilenummer: str = Field(min_length=1, max_length=100)
    kunde: str = ""
    projekt: str = ""
    jahresstueckzahl: int = Field(ge=0, default=0)

    material_id: int | None = None
    schussgewicht_g: float = Field(ge=0, default=0)
    teilegewicht_netto_g: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    materialpreis_pro_kg: float = Field(ge=0)

    maschine_id: int | None = None
    zykluszeit_s: float = Field(ge=0)
    kavitaeten: int = Field(ge=1)
    maschinenstundensatz: float = Field(ge=0)

    lohnkosten_id: int | None = None
    lohnstundensatz: float = Field(ge=0)

    werkzeugkosten_eur: float = Field(ge=0)
    amortisationsvolumen: float = Field(gt=0)

    mgk_pct: float = Field(ge=0, default=0)
    fgk_pct: float = Field(ge=0, default=0)
    vvgk_pct: float = Field(ge=0, default=0)
    gewinn_pct: float = Field(ge=0, default=0)
    skonto_pct: float = Field(ge=0, default=0)

    notizen: str = ""
    aktiv: bool = True


class SpritzgussKalkulationCreate(SpritzgussKalkulationBase):
    pass


class SpritzgussKalkulationUpdate(BaseModel):
    teilebezeichnung: str | None = Field(default=None, min_length=1, max_length=255)
    teilenummer: str | None = Field(default=None, min_length=1, max_length=100)
    kunde: str | None = None
    projekt: str | None = None
    jahresstueckzahl: int | None = Field(default=None, ge=0)

    material_id: int | None = None
    schussgewicht_g: float | None = Field(default=None, ge=0)
    teilegewicht_netto_g: float | None = Field(default=None, ge=0)
    ausschussquote_pct: float | None = Field(default=None, ge=0, lt=100)
    materialpreis_pro_kg: float | None = Field(default=None, ge=0)

    maschine_id: int | None = None
    zykluszeit_s: float | None = Field(default=None, ge=0)
    kavitaeten: int | None = Field(default=None, ge=1)
    maschinenstundensatz: float | None = Field(default=None, ge=0)

    lohnkosten_id: int | None = None
    lohnstundensatz: float | None = Field(default=None, ge=0)

    werkzeugkosten_eur: float | None = Field(default=None, ge=0)
    amortisationsvolumen: float | None = Field(default=None, gt=0)

    mgk_pct: float | None = Field(default=None, ge=0)
    fgk_pct: float | None = Field(default=None, ge=0)
    vvgk_pct: float | None = Field(default=None, ge=0)
    gewinn_pct: float | None = Field(default=None, ge=0)
    skonto_pct: float | None = Field(default=None, ge=0)

    notizen: str | None = None
    aktiv: bool | None = None


class SpritzgussKalkulationRead(SpritzgussKalkulationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ergebnis: dict[str, Any] | None = None
    ergebnis_bloecke: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SpritzgussKalkulationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teilebezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    verkaufspreis: float | None = None
    updated_at: datetime
    aktiv: bool
