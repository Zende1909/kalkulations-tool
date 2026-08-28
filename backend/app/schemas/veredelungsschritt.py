from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.numbers import parse_de_float, parse_percent_points

from app.services.veredelung_kalkulation import VEREDELUNGSARTEN

Veredelungsart = Literal[
    "Montage",
    "Ultraschallschweißen",
    "Vibrationsschweißen",
    "Lackieren",
    "Bedrucken",
    "Kaschieren",
    "Clipsen",
    "Schrauben",
    "Sonstige",
]


class VeredelungsschrittBase(BaseModel):
    bezeichnung: str = Field(min_length=1, max_length=255)
    veredelungsart: Veredelungsart
    reihenfolge: int = Field(ge=1)
    beschreibung: str = ""
    taktzeit_s: float = Field(ge=0)
    anzahl_mitarbeiter: int = Field(ge=1)
    lohnkosten_id: int | None = None
    lohnstundensatz: float = Field(ge=0)
    maschinenstundensatz: float | None = None
    verbrauchskosten_je_stueck: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    fgk_pct: float = Field(ge=0)
    aktiv: bool = True

    @field_validator("ausschussquote_pct", mode="before")
    @classmethod
    def coerce_ausschussquote_pct(cls, value: object) -> object:
        if value is None or value == "":
            return 0.0
        parsed = parse_percent_points(value, field_label="Ausschussquote", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("taktzeit_s", "lohnstundensatz", "verbrauchskosten_je_stueck", "fgk_pct", mode="before")
    @classmethod
    def coerce_decimal_fields(cls, value: object, info) -> object:
        if value is None or value == "":
            return 0.0 if info.field_name != "fgk_pct" else 0.0
        label = info.field_name or "Wert"
        parsed = parse_de_float(value, field_label=label, allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("veredelungsart")
    @classmethod
    def validate_art(cls, value: str) -> str:
        if value not in VEREDELUNGSARTEN:
            raise ValueError(
                f"veredelungsart muss eine von {', '.join(VEREDELUNGSARTEN)} sein"
            )
        return value

    @field_validator("maschinenstundensatz", mode="before")
    @classmethod
    def empty_machine_rate_to_none(cls, value: object) -> object:
        if value == "" or value is None:
            return None
        return value

    @model_validator(mode="after")
    def validate_machine_rate(self) -> "VeredelungsschrittBase":
        if self.maschinenstundensatz is not None and self.maschinenstundensatz < 0:
            raise ValueError("maschinenstundensatz muss leer oder nicht negativ sein")
        return self


class VeredelungsschrittCreate(VeredelungsschrittBase):
    pass


class VeredelungsschrittUpdate(BaseModel):
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=255)
    veredelungsart: Veredelungsart | None = None
    reihenfolge: int | None = Field(default=None, ge=1)
    beschreibung: str | None = None
    taktzeit_s: float | None = Field(default=None, ge=0)
    anzahl_mitarbeiter: int | None = Field(default=None, ge=1)
    lohnkosten_id: int | None = None
    lohnstundensatz: float | None = Field(default=None, ge=0)
    maschinenstundensatz: float | None = None
    verbrauchskosten_je_stueck: float | None = Field(default=None, ge=0)
    ausschussquote_pct: float | None = Field(default=None, ge=0, lt=100)
    fgk_pct: float | None = Field(default=None, ge=0)
    aktiv: bool | None = None

    @field_validator("ausschussquote_pct", mode="before")
    @classmethod
    def coerce_ausschussquote_pct_update(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return parse_percent_points(value, field_label="Ausschussquote", allow_none=True)

    @field_validator("maschinenstundensatz", mode="before")
    @classmethod
    def empty_machine_rate_to_none(cls, value: object) -> object:
        if value == "":
            return None
        return value


class VeredelungKostenSchema(BaseModel):
    lohnkosten_je_stueck: float
    maschinenkosten_je_stueck: float
    fertigungsgemeinkosten: float
    kosten_vor_ausschuss: float
    kosten_inkl_ausschuss: float


class VeredelungsschrittRead(VeredelungsschrittBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    lohnkosten_je_stueck: float = 0
    maschinenkosten_je_stueck: float = 0
    fertigungsgemeinkosten: float = 0
    kosten_vor_ausschuss: float = 0
    kosten_inkl_ausschuss: float = 0
