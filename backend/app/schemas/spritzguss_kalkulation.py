from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.numbers import parse_percent_points

from app.schemas.maschinen_groesse import MaschinenGroesseFields, MaschinenGroesseResultSchema
from app.schemas.spritzguss_veredelung import VeredelungZuordnungInput, VeredelungZuordnungRead
from app.schemas.zykluszeit import ZykluszeitFields, ZykluszeitResultSchema

WerkzeugAbrechnungsart = Literal["amortisation", "einmalzahlung"]
LosgroesseModus = Literal["automatisch", "manuell"]


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


class SpritzgussCalcRequest(MaschinenGroesseFields, ZykluszeitFields):
    teilegewicht_netto_g: float = Field(ge=0)
    schussgewicht_g: float = Field(gt=0)
    materialpreis_pro_kg: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    mgk_pct: float = Field(ge=0, default=0)  # wird aus Stammdaten überschrieben
    material_nominierung: Literal["selbstnominiert", "oem_nominiert"] | None = None
    zykluszeit_s: float = Field(ge=0)
    maschinenstundensatz: float = Field(ge=0)
    kavitaeten: int = Field(ge=1)
    lohnstundensatz: float = Field(ge=0)
    fgk_pct: float = Field(ge=0, default=0)
    werkzeugkosten_eur: float = Field(ge=0)
    werkzeug_abrechnungsart: WerkzeugAbrechnungsart = "amortisation"
    amortisationsvolumen: int | None = None
    vvgk_pct: float = Field(ge=0, default=0)
    gewinn_pct: float = Field(ge=0, default=0)
    skonto_pct: float = Field(ge=0, default=0)
    veredelung_zuordnungen: list[VeredelungZuordnungInput] = Field(default_factory=list)
    werk_id: int | None = None
    project_id: int | None = None
    losgroesse_modus: LosgroesseModus = "automatisch"
    losgroesse_manuell: int | None = Field(default=None, ge=1)
    losgroesse: int | None = Field(default=None, ge=1)
    setup_zeit_min: float = Field(ge=0, default=0)
    setup_maschinenstundensatz: float = Field(ge=0, default=0)
    setup_lohnstundensatz: float = Field(ge=0, default=0)
    setup_mitarbeiter: float = Field(ge=0, default=0)
    setup_aktiv: bool = False
    material_id: int | None = None

    @field_validator("ausschussquote_pct", mode="before")
    @classmethod
    def coerce_ausschussquote_pct(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0.0
        parsed = parse_percent_points(value, field_label="Ausschussquote", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)

    @field_validator("losgroesse_manuell", mode="before")
    @classmethod
    def validate_losgroesse_manuell(cls, value: Any) -> Any:
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
    materialausschuss_betrag: float | None = None
    materialgemeinkosten: float
    materialkosten_gesamt: float
    mgk_basis: float | None = None
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    fgk_basis: float | None = None
    werkzeugkostenanteil: float
    werkzeug_einmalzahlung: float
    herstellkosten: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    verkaufspreis: float
    applied_mgk_pct: float | None = None
    applied_fgk_pct: float | None = None
    applied_vvgk_pct: float | None = None
    applied_gewinn_pct: float | None = None
    applied_skonto_pct: float | None = None
    material_nominierung: str | None = None
    spritzguss_gesamt: float | None = None
    veredelung_gesamt: float = 0
    endpreis_je_stueck: float | None = None
    veredelung_schritte: list[dict[str, Any]] = Field(default_factory=list)
    setup_maschinenkosten_gesamt: float | None = None
    setup_lohnkosten_gesamt: float | None = None
    setup_kosten_je_teil: float | None = None
    setup_maschinenkosten_je_teil: float | None = None
    setup_lohnkosten_je_teil: float | None = None
    losgroesse: int | None = None
    losgroesse_modus: LosgroesseModus | None = None
    losgroesse_manuell: int | None = None
    losgroesse_automatisch: int | None = None
    losgroesse_aktiv: int | None = None
    losgroesse_jahresbedarf: int | None = None
    produktionsintervall_arbeitstage: float | None = None
    arbeitstage_pro_jahr: float | None = None
    losgroesse_hinweis: str | None = None
    setup_aktiv: bool | None = None
    schussgewicht_g: float | None = None
    teilegewicht_netto_g: float | None = None
    bruttokapazitaet_exakt: float | None = None
    bruttokapazitaet: float | None = None
    nettokapazitaet: float | None = None


class SpritzgussCalcResponse(BaseModel):
    ergebnis: SpritzgussErgebnisSchema
    bloecke: dict[str, dict[str, Any]]
    veredelung_zuordnungen: list[VeredelungZuordnungRead] = Field(default_factory=list)
    maschinen_groesse: MaschinenGroesseResultSchema | None = None
    zykluszeit_vorschlag: ZykluszeitResultSchema | None = None


class SpritzgussKalkulationBase(MaschinenGroesseFields, ZykluszeitFields):
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

    werk_id: int | None = None
    losgroesse: int | None = Field(default=None, ge=1)
    losgroesse_modus: LosgroesseModus | None = "automatisch"
    losgroesse_manuell: int | None = Field(default=None, ge=1)

    material_id: int | None = None
    schussgewicht_g: float = Field(ge=0, default=0)
    teilegewicht_netto_g: float = Field(ge=0)
    ausschussquote_pct: float = Field(ge=0, lt=100)
    materialpreis_pro_kg: float = Field(ge=0)
    material_nominierung: Literal["selbstnominiert", "oem_nominiert"] | None = None

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

    @field_validator("ausschussquote_pct", mode="before")
    @classmethod
    def coerce_ausschussquote_pct(cls, value: Any) -> Any:
        if value is None or value == "":
            return 0.0
        parsed = parse_percent_points(value, field_label="Ausschussquote", allow_none=False)
        assert parsed is not None
        return parsed

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)

    @field_validator("losgroesse_manuell", mode="before")
    @classmethod
    def validate_losgroesse_manuell_base(cls, value: Any) -> Any:
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
    setup_zeit_min: float = Field(ge=0, default=0)
    setup_maschinenstundensatz: float = Field(ge=0, default=0)
    setup_lohnstundensatz: float = Field(ge=0, default=0)
    setup_mitarbeiter: float = Field(ge=0, default=0)
    setup_aktiv: bool = False
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


class SpritzgussKalkulationUpdate(MaschinenGroesseFields, ZykluszeitFields):
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

    werk_id: int | None = None
    losgroesse: int | None = Field(default=None, ge=1)
    losgroesse_modus: LosgroesseModus | None = None
    losgroesse_manuell: int | None = Field(default=None, ge=1)

    material_id: int | None = None
    schussgewicht_g: float | None = Field(default=None, ge=0)
    teilegewicht_netto_g: float | None = Field(default=None, ge=0)
    ausschussquote_pct: float | None = Field(default=None, ge=0, lt=100)
    materialpreis_pro_kg: float | None = Field(default=None, ge=0)
    material_nominierung: Literal["selbstnominiert", "oem_nominiert"] | None = None

    maschine_id: int | None = None
    zykluszeit_s: float | None = Field(default=None, ge=0)
    kavitaeten: int | None = Field(default=None, ge=1)
    maschinenstundensatz: float | None = Field(default=None, ge=0)

    lohnkosten_id: int | None = None
    lohnstundensatz: float | None = Field(default=None, ge=0)

    setup_zeit_min: float | None = Field(default=None, ge=0)
    setup_maschinenstundensatz: float | None = Field(default=None, ge=0)
    setup_lohnstundensatz: float | None = Field(default=None, ge=0)
    setup_mitarbeiter: float | None = Field(default=None, ge=0)
    setup_aktiv: bool | None = None

    werkzeug_abrechnungsart: WerkzeugAbrechnungsart | None = None
    werkzeugkosten_eur: float | None = Field(default=None, ge=0)
    amortisationsvolumen: int | None = None

    mgk_pct: float | None = Field(default=None, ge=0)
    fgk_pct: float | None = Field(default=None, ge=0)
    vvgk_pct: float | None = Field(default=None, ge=0)
    gewinn_pct: float | None = Field(default=None, ge=0)
    skonto_pct: float | None = Field(default=None, ge=0)

    maschinen_groesse_injection_pressure_kg_cm2: float | None = None
    maschinen_groesse_proj_flaeche_netto_mm2: float | None = None
    maschinen_groesse_zuhaltekraft_ohne_sicherheit_t: float | None = None
    maschinen_groesse_sicherheitszuschlag_faktor: float | None = None
    maschinen_groesse_zuhaltekraft_erforderlich_t: float | None = None
    maschinen_groesse_empfohlene_maschine_id: int | None = None
    maschinen_groesse_warnung: str | None = None

    zykluszeit_temperaturleitfaehigkeit_m2_s: float | None = None
    zykluszeit_optimale_kuehlzeit_s: float | None = None
    zykluszeit_kuehlzeit_s: float | None = None
    zykluszeit_nebenzeiten_gesamt_s: float | None = None
    zykluszeit_vorschlag_s: float | None = None
    zykluszeit_hinweis: str | None = None

    notizen: str | None = None
    aktiv: bool | None = None
    veredelung_zuordnungen: list[VeredelungZuordnungInput] | None = None

    @field_validator("ausschussquote_pct", mode="before")
    @classmethod
    def coerce_ausschussquote_pct_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return parse_percent_points(value, field_label="Ausschussquote", allow_none=True)

    @field_validator("amortisationsvolumen", mode="before")
    @classmethod
    def validate_volume_type(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)

    @field_validator("losgroesse_manuell", mode="before")
    @classmethod
    def validate_losgroesse_manuell_update(cls, value: Any) -> Any:
        if value is None or value == "":
            return None
        return _require_positive_int_volume(value)


class SpritzgussKalkulationRead(SpritzgussKalkulationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    setup_zeit_min: float = 0
    setup_maschinenstundensatz: float = 0
    setup_lohnstundensatz: float = 0
    setup_mitarbeiter: float = 0
    setup_aktiv: bool = False
    zykluszeit_temperaturleitfaehigkeit_m2_s: float | None = None
    zykluszeit_optimale_kuehlzeit_s: float | None = None
    zykluszeit_kuehlzeit_s: float | None = None
    zykluszeit_nebenzeiten_gesamt_s: float | None = None
    zykluszeit_vorschlag_s: float | None = None
    zykluszeit_hinweis: str | None = None
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
    project_id: int | None = None
    jahresstueckzahl: int
    verkaufspreis: float | None = None
    selbstkosten: float | None = None
    updated_at: datetime
    aktiv: bool
