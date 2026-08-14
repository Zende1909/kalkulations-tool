from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.spritzguss_veredelung import VeredelungZuordnungInput, VeredelungZuordnungRead

WerkzeugAbrechnungsart = Literal["amortisation", "einmalzahlung"]


def _require_positive_int_volume(value: Any) -> int:
    if value is None:
        raise ValueError(
            "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein"
        )
    if isinstance(value, bool):
        raise ValueError("amortisationsvolumen muss eine positive ganze Zahl >= 1 sein")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(
                "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein "
                "(Dezimalwerte wie 20000.0001 sind ungültig)"
            )
        as_int = int(value)
    elif isinstance(value, int):
        as_int = value
    elif isinstance(value, str):
        raw = value.strip().replace(" ", "")
        if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
            as_int = int(raw)
        else:
            try:
                as_float = float(raw.replace(",", "."))
            except ValueError as exc:
                raise ValueError(
                    "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein"
                ) from exc
            if not as_float.is_integer():
                raise ValueError(
                    "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein "
                    "(Dezimalwerte wie 20000.0001 sind ungültig)"
                )
            as_int = int(as_float)
    else:
        try:
            as_float = float(value)
            if not as_float.is_integer():
                raise ValueError(
                    "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein "
                    "(Dezimalwerte wie 20000.0001 sind ungültig)"
                )
            as_int = int(as_float)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein"
            ) from exc
    if as_int < 1:
        raise ValueError(
            "amortisationsvolumen muss eine positive ganze Zahl >= 1 sein "
            "(z. B. 1 oder 20000)"
        )
    return as_int


class SpritzgussCalcRequest(BaseModel):
    teilegewicht_netto_g: float = Field(ge=0)
    materialpreis_pro_kg: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    mgk_pct: float = Field(ge=0)
    zykluszeit_s: float = Field(ge=0)
    maschinenstundensatz: float = Field(ge=0)
    kavitaeten: int = Field(ge=1)
    lohnstundensatz: float = Field(ge=0)
    fgk_pct: float = Field(ge=0)
    werkzeugkosten_eur: float = Field(ge=0)
    werkzeug_abrechnungsart: WerkzeugAbrechnungsart = "amortisation"
    amortisationsvolumen: int | None = None
    vvgk_pct: float = Field(ge=0)
    gewinn_pct: float = Field(ge=0)
    skonto_pct: float = Field(ge=0)
    veredelung_zuordnungen: list[VeredelungZuordnungInput] = Field(default_factory=list)

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)

    @model_validator(mode="after")
    def validate_werkzeug_mode(self) -> "SpritzgussCalcRequest":
        if self.werkzeug_abrechnungsart == "amortisation":
            if self.amortisationsvolumen is None or self.amortisationsvolumen < 1:
                raise ValueError(
                    "Bei Amortisation muss amortisationsvolumen eine ganze Zahl >= 1 sein"
                )
        else:
            # Einmalzahlung: Volumen wird ignoriert
            self.amortisationsvolumen = None
        return self


class SpritzgussErgebnisSchema(BaseModel):
    materialgewicht_kg: float
    materialkosten: float
    materialkosten_inkl_ausschuss: float
    materialgemeinkosten: float
    materialkosten_gesamt: float
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    werkzeugkostenanteil: float
    werkzeug_einmalzahlung: float
    herstellkosten: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    verkaufspreis: float
    spritzguss_gesamt: float | None = None
    veredelung_gesamt: float = 0
    endpreis_je_stueck: float | None = None
    veredelung_schritte: list[dict[str, Any]] = Field(default_factory=list)


class SpritzgussCalcResponse(BaseModel):
    ergebnis: SpritzgussErgebnisSchema
    bloecke: dict[str, dict[str, float]]
    veredelung_zuordnungen: list[VeredelungZuordnungRead] = Field(default_factory=list)


class SpritzgussKalkulationBase(BaseModel):
    teilebezeichnung: str = Field(min_length=1, max_length=255)
    teilenummer: str = Field(min_length=1, max_length=100)
    kunde: str = ""
    projekt: str = ""
    jahresstueckzahl: int = Field(ge=0, default=0)

    customer_id: int | None = None
    program_id: int | None = None
    project_id: int | None = None
    calculation_year: int | None = None
    project_volume: float | None = None

    material_id: int | None = None
    schussgewicht_g: float = Field(ge=0, default=0)
    teilegewicht_netto_g: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    materialpreis_pro_kg: float = Field(ge=0)

    maschine_id: int | None = None
    zykluszeit_s: float = Field(ge=0)
    kavitaeten: int = Field(ge=1)
    maschinenstundensatz: float = Field(ge=0)

    lohnkosten_id: int | None = None
    lohnstundensatz: float = Field(ge=0)

    werkzeug_abrechnungsart: WerkzeugAbrechnungsart = "amortisation"
    werkzeugkosten_eur: float = Field(ge=0)
    amortisationsvolumen: int | None = None

    mgk_pct: float = Field(ge=0, default=0)
    fgk_pct: float = Field(ge=0, default=0)
    vvgk_pct: float = Field(ge=0, default=0)
    gewinn_pct: float = Field(ge=0, default=0)
    skonto_pct: float = Field(ge=0, default=0)

    notizen: str = ""
    aktiv: bool = True

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)

    @model_validator(mode="after")
    def validate_werkzeug_mode(self) -> "SpritzgussKalkulationBase":
        if self.werkzeug_abrechnungsart == "amortisation":
            if self.amortisationsvolumen is None or self.amortisationsvolumen < 1:
                raise ValueError(
                    "Bei Amortisation muss amortisationsvolumen eine ganze Zahl >= 1 sein"
                )
        else:
            self.amortisationsvolumen = None
        return self


class SpritzgussKalkulationCreate(SpritzgussKalkulationBase):
    veredelung_zuordnungen: list[VeredelungZuordnungInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_hierarchy_for_new(self) -> "SpritzgussKalkulationCreate":
        missing = [
            name
            for name, val in (
                ("customer_id", self.customer_id),
                ("program_id", self.program_id),
                ("project_id", self.project_id),
            )
            if val is None
        ]
        if missing:
            raise ValueError(
                "Neue Kalkulationen benötigen Kunde, Programm und Projekt "
                f"(fehlend: {', '.join(missing)})."
            )
        return self


class SpritzgussKalkulationUpdate(BaseModel):
    teilebezeichnung: str | None = Field(default=None, min_length=1, max_length=255)
    teilenummer: str | None = Field(default=None, min_length=1, max_length=100)
    kunde: str | None = None
    projekt: str | None = None
    jahresstueckzahl: int | None = Field(default=None, ge=0)

    customer_id: int | None = None
    program_id: int | None = None
    project_id: int | None = None
    calculation_year: int | None = None
    project_volume: float | None = None

    material_id: int | None = None
    schussgewicht_g: float | None = Field(default=None, ge=0)
    teilegewicht_netto_g: float | None = Field(default=None, ge=0)
    ausschussquote_pct: float | None = Field(default=None, ge=0, lt=100)
    materialpreis_pro_kg: float | None = Field(default=None, ge=0)

    maschine_id: int | None = None
    zykluszeit_s: float | None = Field(default=None, ge=0)
    kavitaeten: int | None = Field(default=None, ge=1)
    maschinenstundensatz: float | None = Field(default=None, ge=0)

    lohnkosten_id: int | None = None
    lohnstundensatz: float | None = Field(default=None, ge=0)

    werkzeug_abrechnungsart: WerkzeugAbrechnungsart | None = None
    werkzeugkosten_eur: float | None = Field(default=None, ge=0)
    amortisationsvolumen: int | None = None

    mgk_pct: float | None = Field(default=None, ge=0)
    fgk_pct: float | None = Field(default=None, ge=0)
    vvgk_pct: float | None = Field(default=None, ge=0)
    gewinn_pct: float | None = Field(default=None, ge=0)
    skonto_pct: float | None = Field(default=None, ge=0)

    notizen: str | None = None
    aktiv: bool | None = None
    veredelung_zuordnungen: list[VeredelungZuordnungInput] | None = None

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)


class SpritzgussKalkulationRead(SpritzgussKalkulationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ergebnis: dict[str, Any] | None = None
    ergebnis_bloecke: dict[str, Any] | None = None
    veredelung_zuordnungen: list[VeredelungZuordnungRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SpritzgussKalkulationListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    teilebezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    verkaufspreis: float | None = None
    updated_at: datetime
    aktiv: bool
