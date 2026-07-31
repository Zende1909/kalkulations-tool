from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MaterialBase(BaseModel):
    bezeichnung: str
    material_nr: str
    preis_pro_kg: float
    dichte: float
    waehrung: str = "EUR"
    aktiv: bool = True


class MaterialCreate(MaterialBase):
    pass


class MaterialUpdate(BaseModel):
    bezeichnung: str | None = None
    material_nr: str | None = None
    preis_pro_kg: float | None = None
    dichte: float | None = None
    waehrung: str | None = None
    aktiv: bool | None = None


class MaterialRead(MaterialBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
