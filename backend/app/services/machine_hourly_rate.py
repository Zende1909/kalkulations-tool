"""Reproduzierbarer Maschinenstundensatz aus Costing-Base-Parametern (Mappe1).

Formeln (Quellwährung, z. B. USD):

    jahresstunden = arbeitstage × schichten × stunden_schicht × oee
    space_h       = fläche × space_satz / jahresstunden
    abschr_h      = investment × (1 / abschreibungsdauer) / jahresstunden
    zinsen_h      = investment × zinssatz / 2 / jahresstunden
    vers_h        = investment × versicherungssatz / jahresstunden
    inst_h        = investment × instandhaltungssatz / jahresstunden
    energie_h     = strom_v×strom_p + druck_v×druck_p + kuehl_v×kuehl_p
    rate          = space_h + abschr_h + zinsen_h + vers_h + inst_h + energie_h

EUR = rate × fx_to_eur. Intern Decimal; Rundung erst bei Anzeige.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


class MachineRateValidationError(ValueError):
    pass


def _d(value: float | int | Decimal | None, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    return Decimal(str(value))


def _qty(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MachineRateInput:
    arbeitstage_pro_jahr: float
    schichten_pro_tag: float
    stunden_pro_schicht: float
    oee: float  # 0..1 (z. B. 0.9)
    investment: float
    flaeche_sqm: float
    space_cost_satz_pro_sqm_jahr: float
    abschreibungsdauer_jahre: float
    zinssatz: float
    versicherungssatz: float
    instandhaltungssatz: float
    stromverbrauch_kwh_h: float
    strompreis: float
    druckluftverbrauch_m3_h: float
    druckluftpreis: float
    kuehlwasserverbrauch_m3_h: float
    kuehlwasserpreis: float
    fx_to_eur: float = 1.0
    source_currency: str = "USD"


@dataclass(frozen=True)
class MachineRateResult:
    jahresstunden: float
    space_costs_pro_stunde: float
    abschreibung_pro_stunde: float
    zinsen_pro_stunde: float
    versicherung_pro_stunde: float
    instandhaltung_pro_stunde: float
    energie_pro_stunde: float
    stundensatz_source: float
    stundensatz_eur: float
    source_currency: str
    fx_to_eur: float
    # Jahreswerte (Quellwährung) zur Nachvollziehbarkeit
    space_costs_jahr: float
    abschreibung_jahr: float
    zinsen_jahr: float
    versicherung_jahr: float
    instandhaltung_jahr: float
    stromkosten_jahr: float
    druckluftkosten_jahr: float
    kuehlwasserkosten_jahr: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def rounded_display(self, digits: int = 2) -> dict[str, float]:
        q = Decimal("1").scaleb(-digits)
        out: dict[str, float] = {}
        for key, value in self.to_dict().items():
            if isinstance(value, (int, float)):
                out[key] = float(
                    Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP)
                )
        return out


def berechne_maschinenstundensatz(data: MachineRateInput) -> MachineRateResult:
    if data.oee <= 0 or data.oee > 1:
        raise MachineRateValidationError("oee muss im Intervall (0, 1] liegen")
    if data.arbeitstage_pro_jahr <= 0:
        raise MachineRateValidationError("arbeitstage_pro_jahr muss > 0 sein")
    if data.schichten_pro_tag <= 0 or data.stunden_pro_schicht <= 0:
        raise MachineRateValidationError("Schichten und Stunden/Schicht müssen > 0 sein")
    if data.abschreibungsdauer_jahre <= 0:
        raise MachineRateValidationError("abschreibungsdauer_jahre muss > 0 sein")
    if data.fx_to_eur <= 0:
        raise MachineRateValidationError("fx_to_eur muss > 0 sein")

    tage = _d(data.arbeitstage_pro_jahr)
    schichten = _d(data.schichten_pro_tag)
    stunden = _d(data.stunden_pro_schicht)
    oee = _d(data.oee)
    inv = _d(data.investment)
    flaeche = _d(data.flaeche_sqm)
    space_satz = _d(data.space_cost_satz_pro_sqm_jahr)
    jahre = _d(data.abschreibungsdauer_jahre)
    zins = _d(data.zinssatz)
    vers = _d(data.versicherungssatz)
    inst = _d(data.instandhaltungssatz)
    fx = _d(data.fx_to_eur)

    jahresstunden = _qty(tage * schichten * stunden * oee)
    if jahresstunden <= 0:
        raise MachineRateValidationError("jahresstunden müssen > 0 sein")

    space_jahr = _qty(flaeche * space_satz)
    space_h = _qty(space_jahr / jahresstunden)

    abschr_jahr = _qty(inv / jahre)
    abschr_h = _qty(abschr_jahr / jahresstunden)

    zinsen_jahr = _qty(inv * zins / Decimal("2"))
    zinsen_h = _qty(zinsen_jahr / jahresstunden)

    vers_jahr = _qty(inv * vers)
    vers_h = _qty(vers_jahr / jahresstunden)

    inst_jahr = _qty(inv * inst)
    inst_h = _qty(inst_jahr / jahresstunden)

    strom_jahr = _qty(
        _d(data.stromverbrauch_kwh_h) * _d(data.strompreis) * jahresstunden
    )
    druck_jahr = _qty(
        _d(data.druckluftverbrauch_m3_h) * _d(data.druckluftpreis) * jahresstunden
    )
    kuehl_jahr = _qty(
        _d(data.kuehlwasserverbrauch_m3_h) * _d(data.kuehlwasserpreis) * jahresstunden
    )
    energie_h = _qty((strom_jahr + druck_jahr + kuehl_jahr) / jahresstunden)

    rate_src = _qty(space_h + abschr_h + zinsen_h + vers_h + inst_h + energie_h)
    rate_eur = _qty(rate_src * fx)

    return MachineRateResult(
        jahresstunden=float(jahresstunden),
        space_costs_pro_stunde=float(space_h),
        abschreibung_pro_stunde=float(abschr_h),
        zinsen_pro_stunde=float(zinsen_h),
        versicherung_pro_stunde=float(vers_h),
        instandhaltung_pro_stunde=float(inst_h),
        energie_pro_stunde=float(energie_h),
        stundensatz_source=float(rate_src),
        stundensatz_eur=float(rate_eur),
        source_currency=data.source_currency,
        fx_to_eur=float(fx),
        space_costs_jahr=float(space_jahr),
        abschreibung_jahr=float(abschr_jahr),
        zinsen_jahr=float(zinsen_jahr),
        versicherung_jahr=float(vers_jahr),
        instandhaltung_jahr=float(inst_jahr),
        stromkosten_jahr=float(strom_jahr),
        druckluftkosten_jahr=float(druck_jahr),
        kuehlwasserkosten_jahr=float(kuehl_jahr),
    )


def apply_rate_to_maschine(maschine: Any, result: MachineRateResult) -> None:
    """Schreibt berechnete Werte auf ein Maschine-ORM-Objekt."""
    maschine.jahresstunden = result.jahresstunden
    maschine.space_costs_pro_stunde = result.space_costs_pro_stunde
    maschine.abschreibung_pro_stunde = result.abschreibung_pro_stunde
    maschine.zinsen_pro_stunde = result.zinsen_pro_stunde
    maschine.versicherung_pro_stunde = result.versicherung_pro_stunde
    maschine.instandhaltung_pro_stunde = result.instandhaltung_pro_stunde
    maschine.energie_pro_stunde = result.energie_pro_stunde
    maschine.stundensatz_source = result.stundensatz_source
    maschine.stundensatz = result.stundensatz_eur
    maschine.source_currency = result.source_currency
