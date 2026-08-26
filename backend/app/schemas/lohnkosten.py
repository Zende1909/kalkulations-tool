from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


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


class LohnkostenRead(LohnkostenBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
