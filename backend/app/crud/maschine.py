from app.crud.base import CRUDBase
from app.models.maschine import Maschine
from app.schemas.maschine import MaschineCreate, MaschineUpdate

maschine = CRUDBase[Maschine, MaschineCreate, MaschineUpdate](Maschine)
