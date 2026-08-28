from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.numbers import parse_de_float


class KaufteilBase(BaseModel):
    artikelnummer: str = Field(min_length=1, max_length=100)
    bezeichnung: str = Field(min_length=1, max_length=255)
    beschreibung: str = ""
    lieferant: str = ""
    einheit: str = "Stück"
    preis: float = Field(ge=0)
    waehrung: str = "EUR"
    gueltig_ab: date | None = None
    aktiv: bool = True
    # selbstnominiert | oem_nominiert | None (Altbestand)
    nominierung: str | None = None
    customer_id: int | None = None
    program_id: int | None = None
    project_id: int | None = None

    @field_validator("preis", mode="before")
    @classmethod
    def coerce_preis(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0.0
        parsed = parse_de_float(value, field_label="Preis", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("nominierung")
    @classmethod
    def validate_nominierung(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        allowed = {"selbstnominiert", "oem_nominiert"}
        if value not in allowed:
            raise ValueError(
                "nominierung muss 'selbstnominiert' oder 'oem_nominiert' sein"
            )
        return value


class KaufteilCreate(KaufteilBase):
    pass


class KaufteilUpdate(BaseModel):
    artikelnummer: str | None = Field(default=None, min_length=1, max_length=100)
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=255)
    beschreibung: str | None = None
    lieferant: str | None = None
    einheit: str | None = None
    preis: float | None = Field(default=None, ge=0)
    waehrung: str | None = None
    gueltig_ab: date | None = None
    aktiv: bool | None = None
    nominierung: str | None = None
    customer_id: int | None = None
    program_id: int | None = None
    project_id: int | None = None

    @field_validator("preis", mode="before")
    @classmethod
    def coerce_preis_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Preis", allow_none=True)

    @field_validator("nominierung")
    @classmethod
    def validate_nominierung_update(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        allowed = {"selbstnominiert", "oem_nominiert"}
        if value not in allowed:
            raise ValueError(
                "nominierung muss 'selbstnominiert' oder 'oem_nominiert' sein"
            )
        return value


class KaufteilRead(KaufteilBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class SpritzgussZuordnungInput(BaseModel):
    spritzguss_kalkulation_id: int
    menge: float = Field(gt=0)
    reihenfolge: int = Field(ge=1, default=1)


class KaufteilZuordnungInput(BaseModel):
    kaufteil_id: int
    menge: float = Field(gt=0)
    reihenfolge: int = Field(ge=1, default=1)
    snapshot_preis: float | None = Field(default=None, ge=0)


class VeredelungZuordnungInput(BaseModel):
    veredelungsschritt_id: int
    reihenfolge: int = Field(ge=1, default=1)
    mengenfaktor: float = Field(gt=0, default=1.0)


class SpritzgussZuordnungRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baugruppe_id: int
    spritzguss_kalkulation_id: int
    menge: float
    reihenfolge: int
    snapshot_preis: float
    snapshot_bezeichnung: str
    snapshot_teilenummer: str
    zwischensumme: float = 0


class KaufteilZuordnungRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baugruppe_id: int
    kaufteil_id: int
    menge: float
    reihenfolge: int
    snapshot_preis: float
    snapshot_bezeichnung: str
    snapshot_lieferant: str
    zwischensumme: float = 0


class VeredelungZuordnungRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    baugruppe_id: int
    veredelungsschritt_id: int
    reihenfolge: int
    mengenfaktor: float
    snapshot_kosten: float
    snapshot_bezeichnung: str
    zwischensumme: float = 0


class InvestitionRead(BaseModel):
    id: int
    bezeichnung: str
    investment_type: str
    amount: float
    status: str
    quelle: str = ""


class BaugruppeErgebnisSchema(BaseModel):
    einzelteile_gesamt: float
    kaufteile_gesamt: float
    veredelung_gesamt: float
    baugruppenpreis_je_stueck: float
    jahresstueckzahl: int
    jahresumsatz: float
    investitionen_gesamt: float = 0
    einzelteile: list[dict] = Field(default_factory=list)
    kaufteile: list[dict] = Field(default_factory=list)
    veredelungen: list[dict] = Field(default_factory=list)
    investitionen: list[dict] = Field(default_factory=list)


class BaugruppeCalcRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    jahresstueckzahl: int = Field(ge=0, default=0)
    werk_id: int | None = None
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput] = Field(default_factory=list)
    kaufteil_zuordnungen: list[KaufteilZuordnungInput] = Field(default_factory=list)
    veredelung_zuordnungen: list[VeredelungZuordnungInput] = Field(default_factory=list)


class BaugruppeCalcResponse(BaseModel):
    ergebnis: BaugruppeErgebnisSchema
    bloecke: dict[str, dict]


class BaugruppeBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    teilenummer: str = ""
    kunde: str = ""
    projekt: str = ""
    project_id: int | None = None
    werk_id: int | None = None
    jahresstueckzahl: int = Field(ge=0, default=0)
    beschreibung: str = ""
    status: str = "entwurf"
    aktiv: bool = True


class BaugruppeCreate(BaugruppeBase):
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput] = Field(default_factory=list)
    kaufteil_zuordnungen: list[KaufteilZuordnungInput] = Field(default_factory=list)
    veredelung_zuordnungen: list[VeredelungZuordnungInput] = Field(default_factory=list)


class BaugruppeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    teilenummer: str | None = None
    kunde: str | None = None
    projekt: str | None = None
    project_id: int | None = None
    clear_project_link: bool | None = None
    werk_id: int | None = None
    jahresstueckzahl: int | None = Field(default=None, ge=0)
    beschreibung: str | None = None
    status: str | None = None
    aktiv: bool | None = None
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput] | None = None
    kaufteil_zuordnungen: list[KaufteilZuordnungInput] | None = None
    veredelung_zuordnungen: list[VeredelungZuordnungInput] | None = None


class BaugruppeListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    project_id: int | None = None
    jahresstueckzahl: int
    status: str
    baugruppenpreis_je_stueck: float | None = None
    updated_at: datetime
    aktiv: bool


class BaugruppeRead(BaugruppeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int | None = None
    program_id: int | None = None
    ergebnis: dict | None = None
    ergebnis_bloecke: dict | None = None
    created_at: datetime
    updated_at: datetime
    spritzguss_zuordnungen: list[SpritzgussZuordnungRead] = Field(default_factory=list)
    kaufteil_zuordnungen: list[KaufteilZuordnungRead] = Field(default_factory=list)
    veredelung_zuordnungen: list[VeredelungZuordnungRead] = Field(default_factory=list)
    investitionen: list[InvestitionRead] = Field(default_factory=list)

    @field_validator("jahresstueckzahl", mode="before")
    @classmethod
    def coerce_jahresstueckzahl(cls, value: object) -> int:
        if value is None:
            return 0
        return int(value)
