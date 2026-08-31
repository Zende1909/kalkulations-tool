"""Maschinengröße / Zuhaltekraft nach Excel ``p1-1`` ab ``AC27``.

Maßeingabe::

    Projizierte Fläche netto = Breite × Länge × (1 - Öffnungen/100)
    Zuhaltekraft (t) = netto / 100 × Injection Pressure (kg/cm²) × Kavitäten / 1000

Flächeneingabe::

    Projizierte Fläche netto = eingegebene projizierte Fläche
    Zuhaltekraft (t) = netto / 100 × Injection Pressure (kg/cm²) × Kavitäten / 1000

Sicherheitszuschlag: erforderliche Zuhaltekraft = ohne Sicherheit × 1,20.

Keine Zwischenrundung in der Berechnungskette.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.maschine import Maschine

MaschinenGroesseModus = Literal["masse", "flaeche"]

SAFETY_FACTOR = 1.2
DEFAULT_INJECTION_PRESSURE_KG_CM2 = 500.0

_EXCLUDED_MASCHINENTYP = ("montage", "veredelung", "assembly", "finish", "finishing")


class MaschinenGroesseValidationError(ValueError):
    """Ungültige Eingaben für die Maschinengrößenberechnung."""


@dataclass(frozen=True)
class MaschinenGroesseInput:
    modus: MaschinenGroesseModus
    injection_pressure_kg_cm2: float
    kavitaeten: int
    breite_mm: float | None = None
    laenge_mm: float | None = None
    oeffnungen_pct: float | None = None
    proj_flaeche_mm2: float | None = None


@dataclass(frozen=True)
class MaschinenGroesseResult:
    modus: MaschinenGroesseModus
    injection_pressure_kg_cm2: float
    kavitaeten: int
    breite_mm: float | None
    laenge_mm: float | None
    oeffnungen_pct: float | None
    proj_flaeche_mm2: float | None
    proj_flaeche_netto_mm2: float | None
    zuhaltekraft_ohne_sicherheit_t: float
    sicherheitszuschlag_faktor: float
    zuhaltekraft_erforderlich_t: float
    empfohlene_maschine_id: int | None
    empfohlene_maschine_name: str | None
    empfohlene_maschine_schliesskraft_t: float | None
    warnung: str | None

    def as_dict(self) -> dict:
        return {
            "modus": self.modus,
            "injection_pressure_kg_cm2": self.injection_pressure_kg_cm2,
            "kavitaeten": self.kavitaeten,
            "breite_mm": self.breite_mm,
            "laenge_mm": self.laenge_mm,
            "oeffnungen_pct": self.oeffnungen_pct,
            "proj_flaeche_mm2": self.proj_flaeche_mm2,
            "proj_flaeche_netto_mm2": self.proj_flaeche_netto_mm2,
            "zuhaltekraft_ohne_sicherheit_t": self.zuhaltekraft_ohne_sicherheit_t,
            "sicherheitszuschlag_faktor": self.sicherheitszuschlag_faktor,
            "zuhaltekraft_erforderlich_t": self.zuhaltekraft_erforderlich_t,
            "empfohlene_maschine_id": self.empfohlene_maschine_id,
            "empfohlene_maschine_name": self.empfohlene_maschine_name,
            "empfohlene_maschine_schliesskraft_t": self.empfohlene_maschine_schliesskraft_t,
            "warnung": self.warnung,
        }


def validate_injection_pressure(value: float | None, *, kontext: str = "Material") -> float:
    if value is None:
        raise MaschinenGroesseValidationError(
            f"{kontext}: Einspritzdruck (injection_pressure_kg_cm2) fehlt."
        )
    if value <= 0:
        raise MaschinenGroesseValidationError(
            f"{kontext}: Einspritzdruck muss größer als 0 kg/cm² sein."
        )
    return float(value)


def is_spritzguss_maschine(maschine: Maschine) -> bool:
    typ = (maschine.maschinentyp or "").strip().lower()
    return not any(token in typ for token in _EXCLUDED_MASCHINENTYP)


def proj_flaeche_netto_masse(
    *,
    breite_mm: float,
    laenge_mm: float,
    oeffnungen_pct: float,
) -> float:
    return breite_mm * laenge_mm * (1 - oeffnungen_pct / 100)


def zuhaltekraft_aus_masse(
    *,
    breite_mm: float,
    laenge_mm: float,
    oeffnungen_pct: float,
    injection_pressure_kg_cm2: float,
    kavitaeten: int,
) -> tuple[float, float]:
    """Returns (proj_flaeche_netto_mm2, zuhaltekraft_ohne_sicherheit_t)."""
    netto = proj_flaeche_netto_masse(
        breite_mm=breite_mm,
        laenge_mm=laenge_mm,
        oeffnungen_pct=oeffnungen_pct,
    )
    ohne = netto / 100 * injection_pressure_kg_cm2 * kavitaeten / 1000
    return netto, ohne


def zuhaltekraft_aus_flaeche(
    *,
    proj_flaeche_mm2: float,
    injection_pressure_kg_cm2: float,
    kavitaeten: int,
) -> tuple[float, float]:
    """Returns (proj_flaeche_netto_mm2, zuhaltekraft_ohne_sicherheit_t)."""
    netto = proj_flaeche_mm2
    ohne = netto / 100 * injection_pressure_kg_cm2 * kavitaeten / 1000
    return netto, ohne


def _validate_pct(name: str, value: float | None, *, max_inclusive: float = 100) -> float:
    if value is None:
        raise MaschinenGroesseValidationError(f"{name} fehlt.")
    if value < 0 or value > max_inclusive:
        raise MaschinenGroesseValidationError(
            f"{name} muss zwischen 0 und {max_inclusive} % liegen."
        )
    return float(value)


def _validate_positive(name: str, value: float | None) -> float:
    if value is None or value <= 0:
        raise MaschinenGroesseValidationError(f"{name} muss größer als 0 sein.")
    return float(value)


def berechne_maschinen_groesse(inp: MaschinenGroesseInput) -> MaschinenGroesseResult:
    pressure = validate_injection_pressure(inp.injection_pressure_kg_cm2)
    if inp.kavitaeten < 1:
        raise MaschinenGroesseValidationError("Kavitäten müssen mindestens 1 sein.")

    proj_netto: float | None

    if inp.modus == "masse":
        breite = _validate_positive("Breite", inp.breite_mm)
        laenge = _validate_positive("Länge", inp.laenge_mm)
        oeffnungen = _validate_pct("Öffnungen", inp.oeffnungen_pct)
        proj_netto, ohne = zuhaltekraft_aus_masse(
            breite_mm=breite,
            laenge_mm=laenge,
            oeffnungen_pct=oeffnungen,
            injection_pressure_kg_cm2=pressure,
            kavitaeten=inp.kavitaeten,
        )
        breite_mm, laenge_mm, oeffnungen_pct = breite, laenge, oeffnungen
        proj_flaeche_mm2 = None
    else:
        flaeche = _validate_positive("Projizierte Fläche", inp.proj_flaeche_mm2)
        proj_netto, ohne = zuhaltekraft_aus_flaeche(
            proj_flaeche_mm2=flaeche,
            injection_pressure_kg_cm2=pressure,
            kavitaeten=inp.kavitaeten,
        )
        breite_mm = laenge_mm = oeffnungen_pct = None
        proj_flaeche_mm2 = flaeche

    erforderlich = ohne * SAFETY_FACTOR
    return MaschinenGroesseResult(
        modus=inp.modus,
        injection_pressure_kg_cm2=pressure,
        kavitaeten=inp.kavitaeten,
        breite_mm=breite_mm,
        laenge_mm=laenge_mm,
        oeffnungen_pct=oeffnungen_pct,
        proj_flaeche_mm2=proj_flaeche_mm2,
        proj_flaeche_netto_mm2=proj_netto,
        zuhaltekraft_ohne_sicherheit_t=ohne,
        sicherheitszuschlag_faktor=SAFETY_FACTOR,
        zuhaltekraft_erforderlich_t=erforderlich,
        empfohlene_maschine_id=None,
        empfohlene_maschine_name=None,
        empfohlene_maschine_schliesskraft_t=None,
        warnung=None,
    )


def waehle_kleinste_maschine(
    db: Session,
    *,
    werk_id: int,
    erforderliche_zuhaltekraft_t: float,
) -> tuple[Maschine | None, str | None]:
    stmt = (
        select(Maschine)
        .where(
            Maschine.werk_id == werk_id,
            Maschine.aktiv.is_(True),
            Maschine.schliesskraft_t >= erforderliche_zuhaltekraft_t,
            Maschine.schliesskraft_t > 0,
        )
        .order_by(Maschine.schliesskraft_t.asc(), Maschine.bezeichnung.asc())
    )
    candidates = [m for m in db.scalars(stmt).all() if is_spritzguss_maschine(m)]
    if not candidates:
        return None, "Keine passende Maschine"
    return candidates[0], None


def berechne_maschinen_groesse_mit_auswahl(
    db: Session,
    inp: MaschinenGroesseInput,
    *,
    werk_id: int | None,
) -> MaschinenGroesseResult:
    base = berechne_maschinen_groesse(inp)
    if werk_id is None:
        return MaschinenGroesseResult(
            **{
                **base.as_dict(),
                "empfohlene_maschine_id": None,
                "empfohlene_maschine_name": None,
                "empfohlene_maschine_schliesskraft_t": None,
                "warnung": "Bitte Werk wählen, um eine Maschine vorzuschlagen.",
            }
        )

    maschine, warnung = waehle_kleinste_maschine(
        db,
        werk_id=werk_id,
        erforderliche_zuhaltekraft_t=base.zuhaltekraft_erforderlich_t,
    )
    if maschine is None:
        return MaschinenGroesseResult(
            **{
                **base.as_dict(),
                "empfohlene_maschine_id": None,
                "empfohlene_maschine_name": None,
                "empfohlene_maschine_schliesskraft_t": None,
                "warnung": warnung,
            }
        )
    return MaschinenGroesseResult(
        **{
            **base.as_dict(),
            "empfohlene_maschine_id": maschine.id,
            "empfohlene_maschine_name": f"{maschine.bezeichnung} ({maschine.maschinen_nr})",
            "empfohlene_maschine_schliesskraft_t": float(maschine.schliesskraft_t),
            "warnung": None,
        }
    )
