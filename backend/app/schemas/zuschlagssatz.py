from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.zuschlagssatz import ALLOWED_ZUSCHLAGSSATZ_TYPEN

ZuschlagssatzTyp = Literal[
    "GEMEINKOSTEN",
    "GEWINN",
    "VERSCHROTTUNG",
    "mgk_kaufteil_selbst",
    "mgk_kaufteil_oem",
    "fgk",
    "vvgk",
    "gewinn",
    "skonto",
]


def _validate_zuschlagssatz_typ(value: str) -> str:
    if value not in ALLOWED_ZUSCHLAGSSATZ_TYPEN:
        allowed = ", ".join(ALLOWED_ZUSCHLAGSSATZ_TYPEN)
        raise ValueError(f"Ungültiger Zuschlagssatz-Typ '{value}'. Erlaubt: {allowed}")
    return value


class ZuschlagssatzBase(BaseModel):
    bezeichnung: str
    satz_prozent: float = Field(ge=0)
    typ: ZuschlagssatzTyp
    aktiv: bool = True

    @field_validator("typ")
    @classmethod
    def validate_typ(cls, value: str) -> str:
        return _validate_zuschlagssatz_typ(value)


class ZuschlagssatzCreate(ZuschlagssatzBase):
    pass


class ZuschlagssatzUpdate(BaseModel):
    bezeichnung: str | None = None
    satz_prozent: float | None = Field(default=None, ge=0)
    typ: ZuschlagssatzTyp | None = None
    aktiv: bool | None = None

    @field_validator("typ")
    @classmethod
    def validate_typ(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_zuschlagssatz_typ(value)


class ZuschlagssatzRead(ZuschlagssatzBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
