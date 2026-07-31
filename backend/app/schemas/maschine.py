from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaschineBase(BaseModel):
    bezeichnung: str
    maschinen_nr: str
    stundensatz: float
    schliesskraft_t: float
    aktiv: bool = True


class MaschineCreate(MaschineBase):
    pass


class MaschineUpdate(BaseModel):
    bezeichnung: str | None = None
    maschinen_nr: str | None = None
    stundensatz: float | None = None
    schliesskraft_t: float | None = None
    aktiv: bool | None = None


class MaschineRead(MaschineBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
