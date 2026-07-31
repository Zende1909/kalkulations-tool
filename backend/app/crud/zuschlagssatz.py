from app.crud.base import CRUDBase
from app.models.zuschlagssatz import Zuschlagssatz
from app.schemas.zuschlagssatz import ZuschlagssatzCreate, ZuschlagssatzUpdate

zuschlagssatz = CRUDBase[Zuschlagssatz, ZuschlagssatzCreate, ZuschlagssatzUpdate](Zuschlagssatz)
