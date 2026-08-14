from app.crud.base import CRUDBase
from app.models.project import Project
from app.schemas.hierarchy import ProjectCreate, ProjectUpdate

project = CRUDBase[Project, ProjectCreate, ProjectUpdate](Project)
