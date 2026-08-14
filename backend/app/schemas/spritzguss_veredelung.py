from pydantic import BaseModel, ConfigDict, Field


class VeredelungZuordnungInput(BaseModel):
    veredelungsschritt_id: int
    reihenfolge: int = Field(ge=1)
    aktiv: bool = True
    mengenfaktor: float = Field(ge=0, default=1.0)


class VeredelungZuordnungUpdate(BaseModel):
    reihenfolge: int | None = Field(default=None, ge=1)
    aktiv: bool | None = None
    mengenfaktor: float | None = Field(default=None, ge=0)


class VeredelungZuordnungRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kalkulation_id: int
    veredelungsschritt_id: int
    reihenfolge: int
    aktiv: bool
    mengenfaktor: float
    snapshot_bezeichnung: str
    snapshot_veredelungsart: str
    snapshot_kosten_inkl_ausschuss: float
    kosten_gesamt: float = 0


class VeredelungReihenfolgeItem(BaseModel):
    id: int
    reihenfolge: int = Field(ge=1)


class VeredelungReihenfolgeUpdate(BaseModel):
    zuordnungen: list[VeredelungReihenfolgeItem]
