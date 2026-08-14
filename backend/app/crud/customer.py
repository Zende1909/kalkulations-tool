from app.crud.base import CRUDBase
from app.models.customer import Customer
from app.schemas.hierarchy import CustomerCreate, CustomerUpdate

customer = CRUDBase[Customer, CustomerCreate, CustomerUpdate](Customer)
