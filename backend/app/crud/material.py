from app.crud.base import CRUDBase
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialUpdate

material = CRUDBase[Material, MaterialCreate, MaterialUpdate](Material)
