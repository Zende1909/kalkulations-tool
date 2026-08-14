from app.crud.base import CRUDBase
from app.models.investition import Investition
from app.schemas.investition import InvestitionCreate, InvestitionUpdate

investition = CRUDBase[Investition, InvestitionCreate, InvestitionUpdate](Investition)
