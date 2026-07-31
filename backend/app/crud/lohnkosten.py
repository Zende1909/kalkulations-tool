from app.crud.base import CRUDBase
from app.models.lohnkosten import Lohnkosten
from app.schemas.lohnkosten import LohnkostenCreate, LohnkostenUpdate

lohnkosten = CRUDBase[Lohnkosten, LohnkostenCreate, LohnkostenUpdate](Lohnkosten)
