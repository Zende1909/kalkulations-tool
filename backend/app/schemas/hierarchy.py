from datetime import date, datetime

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.program import PROGRAM_STATUSES
from app.models.project import PROJECT_STATUSES
from app.schemas.numbers import parse_de_float
from app.services.hierarchy import (
    validate_calendar_year,
    validate_component_area,
    validate_quantity_per_vehicle,
    validate_vehicle_volume,
)

ComponentArea = Literal["Interior", "Exterior"]


class CustomerBase(BaseModel):
    customer_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    notes: str = ""
    active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    customer_number: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    active: bool | None = None


class CustomerRead(CustomerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProgramBase(BaseModel):
    customer_id: int
    program_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    vehicle_series: str = ""
    sop: date | None = None
    eop: date | None = None
    status: str = "Anfrage"
    production_plant: str = ""
    notes: str = ""
    active: bool = True

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PROGRAM_STATUSES:
            raise ValueError(f"Ungültiger Programmstatus: {value}")
        return value


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    customer_id: int | None = None
    program_number: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    vehicle_series: str | None = None
    sop: date | None = None
    eop: date | None = None
    status: str | None = None
    production_plant: str | None = None
    notes: str | None = None
    active: bool | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in PROGRAM_STATUSES:
            raise ValueError(f"Ungültiger Programmstatus: {value}")
        return value


class ProgramRead(ProgramBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProgramVolumeBase(BaseModel):
    program_id: int
    calendar_year: int
    vehicle_volume: int = 0

    @field_validator("calendar_year")
    @classmethod
    def check_year(cls, value: int) -> int:
        return validate_calendar_year(value)

    @field_validator("vehicle_volume")
    @classmethod
    def check_volume(cls, value: int) -> int:
        return validate_vehicle_volume(value)


class ProgramVolumeCreate(ProgramVolumeBase):
    pass


class ProgramVolumeUpdate(BaseModel):
    program_id: int | None = None
    calendar_year: int | None = None
    vehicle_volume: int | None = None

    @field_validator("calendar_year")
    @classmethod
    def check_year(cls, value: int | None) -> int | None:
        if value is not None:
            return validate_calendar_year(value)
        return value

    @field_validator("vehicle_volume")
    @classmethod
    def check_volume(cls, value: int | None) -> int | None:
        if value is not None:
            return validate_vehicle_volume(value)
        return value


class ProgramVolumeRead(ProgramVolumeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProjectBase(BaseModel):
    program_id: int
    project_number: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    component_area: ComponentArea
    quantity_per_vehicle: float = 1.0
    status: str = "Anfrage"
    notes: str = ""
    active: bool = True

    @field_validator("component_area")
    @classmethod
    def check_component_area(cls, value: str) -> str:
        return validate_component_area(value, strict=True)  # type: ignore[return-value]

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in PROJECT_STATUSES:
            raise ValueError(f"Ungültiger Projektstatus: {value}")
        return value

    @field_validator("quantity_per_vehicle", mode="before")
    @classmethod
    def coerce_quantity_per_vehicle(cls, value: Any) -> Any:
        if value is None or value == "":
            return 1.0
        parsed = parse_de_float(value, field_label="Anzahl pro Fahrzeug", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("quantity_per_vehicle")
    @classmethod
    def check_quantity(cls, value: float) -> float:
        return validate_quantity_per_vehicle(value)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    program_id: int | None = None
    project_number: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    component_area: ComponentArea | None = None
    quantity_per_vehicle: float | None = None
    status: str | None = None
    notes: str | None = None
    active: bool | None = None

    @field_validator("component_area")
    @classmethod
    def check_component_area(cls, value: str | None) -> str | None:
        if value is not None:
            return validate_component_area(value, strict=True)  # type: ignore[return-value]
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str | None) -> str | None:
        if value is not None and value not in PROJECT_STATUSES:
            raise ValueError(f"Ungültiger Projektstatus: {value}")
        return value

    @field_validator("quantity_per_vehicle", mode="before")
    @classmethod
    def coerce_quantity_per_vehicle_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_de_float(value, field_label="Anzahl pro Fahrzeug", allow_none=True)

    @field_validator("quantity_per_vehicle")
    @classmethod
    def check_quantity(cls, value: float | None) -> float | None:
        if value is not None:
            return validate_quantity_per_vehicle(value)
        return value


class ProjectRead(ProjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ProjectVolumeCalculation(BaseModel):
    project_id: int
    program_id: int
    calendar_year: int
    vehicle_volume: int
    quantity_per_vehicle: float
    project_volume: float


class ProgramVolumeProfileRow(BaseModel):
    id: int | None = None
    calendar_year: int
    vehicle_volume: int = 0
    in_sop_eop_range: bool = True


class ProgramVolumeProfileRead(BaseModel):
    program_id: int
    sop: date | None = None
    eop: date | None = None
    sop_eop_years: list[int] = Field(default_factory=list)
    rows: list[ProgramVolumeProfileRow] = Field(default_factory=list)


class ProgramVolumeBulkItem(BaseModel):
    calendar_year: int
    vehicle_volume: int = 0

    @field_validator("calendar_year")
    @classmethod
    def check_year(cls, value: int) -> int:
        return validate_calendar_year(value)

    @field_validator("vehicle_volume")
    @classmethod
    def check_volume(cls, value: int) -> int:
        return validate_vehicle_volume(value)


class ProgramVolumeBulkSave(BaseModel):
    volumes: list[ProgramVolumeBulkItem] = Field(min_length=1)


class SopEopChangeWarning(BaseModel):
    years_with_data_outside_new_range: list[int] = Field(default_factory=list)
    message: str = ""


class ProjectVolumeProfileRow(BaseModel):
    calendar_year: int
    vehicle_volume: int
    quantity_per_vehicle: float
    project_volume: float


class ProjectVolumeProfileRead(BaseModel):
    project_id: int
    program_id: int
    quantity_per_vehicle: float
    total_project_volume: float = 0
    rows: list[ProjectVolumeProfileRow] = Field(default_factory=list)


class ProjectAverageJahresstueckzahlRead(BaseModel):
    """Durchschnittliche Jahresstückzahl: ceil(Summe / Anzahl Jahre)."""

    project_id: int
    year_count: int
    sum_project_volume: float
    average_raw: float | None = None
    jahresstueckzahl: int | None = None
    has_volumes: bool
