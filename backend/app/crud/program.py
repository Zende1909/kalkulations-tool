from app.crud.base import CRUDBase
from app.models.program import Program, ProgramVolume
from app.schemas.hierarchy import ProgramCreate, ProgramUpdate, ProgramVolumeCreate, ProgramVolumeUpdate

program = CRUDBase[Program, ProgramCreate, ProgramUpdate](Program)
program_volume = CRUDBase[ProgramVolume, ProgramVolumeCreate, ProgramVolumeUpdate](ProgramVolume)
