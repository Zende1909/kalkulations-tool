from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ZuschlagssatzBase(BaseModel):
    bezeichnung: str
    satz_prozent: float
    typ: str
    aktiv: bool = True


class ZuschlagssatzCreate(ZuschlagssatzBase):
    pass


class ZuschlagssatzUpdate(BaseModel):
    bezeichnung: str | None = None
    satz_prozent: float | None = None
    typ: str | None = None
    aktiv: bool | None = None


class ZuschlagssatzRead(ZuschlagssatzBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
