from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.numbers import parse_de_float

class LohnkostenBase(BaseModel):
    bezeichnung: str
    kosten_pro_stunde: float
    kostenstelle: str = ""
    gueltig_ab: date
    aktiv: bool = True
    werk_id: int | None = None
    rolle: str = Field(default="sonstig")
    source_currency: str | None = None
    source_rate: float | None = None

    @field_validator("kosten_pro_stunde", mode="before")
    @classmethod
    def coerce_kosten_pro_stunde(cls, value: Any) -> Any:
        parsed = parse_de_float(value, field_label="Kosten pro Stunde", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("source_rate", mode="before")
    @classmethod
    def coerce_source_rate(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Originalsatz", allow_none=True)


class LohnkostenCreate(LohnkostenBase):
    pass


class LohnkostenUpdate(BaseModel):
    bezeichnung: str | None = None
    kosten_pro_stunde: float | None = None
    kostenstelle: str | None = None
    gueltig_ab: date | None = None
    aktiv: bool | None = None
    werk_id: int | None = None
    rolle: str | None = None
    source_currency: str | None = None
    source_rate: float | None = None

    @field_validator("kosten_pro_stunde", mode="before")
    @classmethod
    def coerce_kosten_pro_stunde_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Kosten pro Stunde", allow_none=True)

    @field_validator("source_rate", mode="before")
    @classmethod
    def coerce_source_rate_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Originalsatz", allow_none=True)


class LohnkostenRead(LohnkostenBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
