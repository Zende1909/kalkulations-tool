"""Berechnungslogik für Veredelungsschritte."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


class VeredelungValidationError(ValueError):
    """Ungültige Eingaben für einen Veredelungsschritt."""


VEREDELUNGSARTEN = (
    "Montage",
    "Ultraschallschweißen",
    "Vibrationsschweißen",
    "Lackieren",
    "Bedrucken",
    "Kaschieren",
    "Clipsen",
    "Schrauben",
    "Sonstige",
)


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _is_positive_int(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        as_decimal = _d(value)
    except Exception:
        return False
    if as_decimal != as_decimal.to_integral_value():
        return False
    return int(as_decimal) >= 1


@dataclass(frozen=True)
class VeredelungInput:
    taktzeit_s: float
    anzahl_mitarbeiter: int
    lohnstundensatz: float
    maschinenstundensatz: float | None
    verbrauchskosten_je_stueck: float
    ausschussquote_pct: float
    fgk_pct: float
    reihenfolge: int


@dataclass(frozen=True)
class VeredelungKosten:
    lohnkosten_je_stueck: float
    maschinenkosten_je_stueck: float
    fertigungsgemeinkosten: float
    kosten_vor_ausschuss: float
    kosten_inkl_ausschuss: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def validate_veredelung_input(data: VeredelungInput) -> None:
    if data.taktzeit_s < 0:
        raise VeredelungValidationError("taktzeit_s darf nicht negativ sein")
    if data.anzahl_mitarbeiter < 1:
        raise VeredelungValidationError("anzahl_mitarbeiter muss mindestens 1 sein")
    if data.lohnstundensatz < 0:
        raise VeredelungValidationError("lohnstundensatz darf nicht negativ sein")
    if data.maschinenstundensatz is not None and data.maschinenstundensatz < 0:
        raise VeredelungValidationError(
            "maschinenstundensatz muss leer oder nicht negativ sein"
        )
    if data.verbrauchskosten_je_stueck < 0:
        raise VeredelungValidationError("verbrauchskosten_je_stueck darf nicht negativ sein")
    if data.ausschussquote_pct < 0 or data.ausschussquote_pct >= 100:
        raise VeredelungValidationError(
            "ausschussquote_pct muss >= 0 und < 100 sein"
        )
    if data.fgk_pct < 0:
        raise VeredelungValidationError("fgk_pct darf nicht negativ sein")
    if not _is_positive_int(data.reihenfolge):
        raise VeredelungValidationError(
            "reihenfolge muss eine positive ganze Zahl >= 1 sein"
        )


def berechne_veredelung(data: VeredelungInput) -> VeredelungKosten:
    """Berechnet die Kosten eines Veredelungsschritts je Stück."""
    validate_veredelung_input(data)

    taktzeit = _d(data.taktzeit_s)
    mitarbeiter = _d(data.anzahl_mitarbeiter)
    lohnstundensatz = _d(data.lohnstundensatz)
    maschinenstundensatz = _d(data.maschinenstundensatz or 0)
    verbrauch = _d(data.verbrauchskosten_je_stueck)
    ausschuss = _d(data.ausschussquote_pct) / Decimal("100")
    fgk = _d(data.fgk_pct) / Decimal("100")

    # Lohnkosten je Stück = Taktzeit / 3600 × Lohnstundensatz × Anzahl Mitarbeiter
    lohnkosten = _money(taktzeit / Decimal("3600") * lohnstundensatz * mitarbeiter)

    # Maschinenkosten je Stück = Taktzeit / 3600 × Maschinenstundensatz
    maschinenkosten = _money(taktzeit / Decimal("3600") * maschinenstundensatz)

    # Fertigungsgemeinkosten = Lohnkosten × FGK-Satz
    fertigungsgemeinkosten = _money(lohnkosten * fgk)

    # Kosten vor Ausschuss
    kosten_vor = _money(lohnkosten + maschinenkosten + verbrauch + fertigungsgemeinkosten)

    # Kosten einschließlich Ausschuss
    kosten_inkl = _money(kosten_vor / (Decimal("1") - ausschuss))

    return VeredelungKosten(
        lohnkosten_je_stueck=float(lohnkosten),
        maschinenkosten_je_stueck=float(maschinenkosten),
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        kosten_vor_ausschuss=float(kosten_vor),
        kosten_inkl_ausschuss=float(kosten_inkl),
    )
