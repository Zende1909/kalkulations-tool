from app.crud.base import CRUDBase
from app.models.kaufteil import Kaufteil
from app.schemas.baugruppe import KaufteilCreate, KaufteilUpdate

kaufteil = CRUDBase[Kaufteil, KaufteilCreate, KaufteilUpdate](Kaufteil)
