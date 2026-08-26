"""Schemas für Land, Werk und werkbezogene Zuschläge."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LandBase(BaseModel):
    code: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1, max_length=255)
    aktiv: bool = True


class LandCreate(LandBase):
    pass


class LandUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=16)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    aktiv: bool | None = None


class LandRead(LandBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WerkBase(BaseModel):
    land_id: int
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=255)
    currency: str = Field(default="EUR", max_length=8)
    fx_to_eur: float = Field(gt=0, default=1.0)
    aktiv: bool = True


class WerkCreate(WerkBase):
    pass


class WerkUpdate(BaseModel):
    land_id: int | None = None
    code: str | None = Field(default=None, min_length=1, max_length=32)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    currency: str | None = Field(default=None, max_length=8)
    fx_to_eur: float | None = Field(default=None, gt=0)
    aktiv: bool | None = None


class WerkRead(WerkBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class WerkZuschlagBase(BaseModel):
    typ: str = Field(min_length=1, max_length=64)
    bezeichnung: str = Field(min_length=1, max_length=255)
    satz_prozent: float
    kostenbasis: str = ""
    aktiv: bool = True


class WerkZuschlagCreate(WerkZuschlagBase):
    pass


class WerkZuschlagUpdate(BaseModel):
    typ: str | None = None
    bezeichnung: str | None = None
    satz_prozent: float | None = None
    kostenbasis: str | None = None
    aktiv: bool | None = None


class WerkZuschlagRead(WerkZuschlagBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    werk_id: int
    created_at: datetime
    updated_at: datetime
