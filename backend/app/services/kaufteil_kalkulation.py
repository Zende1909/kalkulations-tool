"""Kaufteilkosten: Einkauf + MGK + OEM-Handling + SG&A je Stück."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal

from app.services.central_markup_rates import CentralMarkupRates, CentralMarkupRatesError


class KaufteilKalkulationError(ValueError):
    """Fachlicher Fehler bei der Kaufteilkalkulation."""


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


@dataclass(frozen=True)
class KaufteilKostenDetail:
    nominierung: str
    einkaufspreis_je_stueck: Decimal
    mgk_satz_pct: Decimal
    mgk_je_stueck: Decimal
    oem_handling_satz_pct: Decimal
    oem_handling_je_stueck: Decimal
    sga_basis_je_stueck: Decimal
    sga_satz_pct: Decimal
    sga_quelle: str
    sga_je_stueck: Decimal
    kosten_inkl_overheads_je_stueck: Decimal

    def to_dict(self) -> dict:
        return {k: float(v) if isinstance(v, Decimal) else v for k, v in asdict(self).items()}


def _resolve_sga_satz(
    rates: CentralMarkupRates,
    *,
    sga_override_aktiv: bool,
    sga_satz_manuell: float | None,
    kontext: str,
) -> tuple[Decimal, str]:
    if sga_override_aktiv:
        if sga_satz_manuell is None:
            raise KaufteilKalkulationError(
                f"{kontext}: SG&A-Override aktiv, aber kein manueller Satz hinterlegt."
            )
        satz = _d(sga_satz_manuell)
        if satz < 0:
            raise KaufteilKalkulationError(
                f"{kontext}: manueller SG&A-Satz darf nicht negativ sein."
            )
        return satz, "manuell"
    if rates.vvgk_pct is None:
        raise KaufteilKalkulationError(
            f"{kontext}: kein aktiver zentraler SG&A-Satz (VVGK) hinterlegt."
        )
    return _d(rates.vvgk_pct), "standard"


def berechne_kaufteil_kosten(
    einkaufspreis: float | Decimal,
    nominierung: str | None,
    rates: CentralMarkupRates,
    *,
    sga_override_aktiv: bool = False,
    sga_satz_manuell: float | None = None,
    kontext: str = "Kaufteil",
) -> KaufteilKostenDetail:
    """Berechnet Kaufteilkosten inkl. Overheads je Stück (ohne Mengen, ohne Profit)."""
    if einkaufspreis is None or _d(einkaufspreis) < 0:
        raise KaufteilKalkulationError(f"{kontext}: Einkaufspreis darf nicht negativ sein.")

    if nominierung is None:
        raise KaufteilKalkulationError(
            f"{kontext}: fehlende Kaufteil-Nominierung – bitte selbstnominiert oder OEM-nominiert wählen."
        )

    try:
        mgk_pct = _d(rates.mgk_pct_for_nominierung(nominierung, kontext=kontext))
    except CentralMarkupRatesError as exc:
        raise KaufteilKalkulationError(str(exc)) from exc

    einkauf = _d(einkaufspreis)
    mgk = einkauf * mgk_pct / Decimal("100")

    oem_pct = Decimal("0")
    oem = Decimal("0")
    if nominierung == "oem_nominiert":
        oem_pct = _d(rates.handling_oem_kaufteil_pct or 0)
        oem = einkauf * oem_pct / Decimal("100")
    elif nominierung != "selbstnominiert":
        raise KaufteilKalkulationError(
            f"{kontext}: unbekannte Nominierung '{nominierung}' – "
            "bitte selbstnominiert oder OEM-nominiert wählen."
        )

    sga_basis = einkauf + mgk + oem
    sga_pct, sga_quelle = _resolve_sga_satz(
        rates,
        sga_override_aktiv=sga_override_aktiv,
        sga_satz_manuell=sga_satz_manuell,
        kontext=kontext,
    )
    sga = sga_basis * sga_pct / Decimal("100")
    total = sga_basis + sga

    return KaufteilKostenDetail(
        nominierung=nominierung,
        einkaufspreis_je_stueck=einkauf,
        mgk_satz_pct=mgk_pct,
        mgk_je_stueck=mgk,
        oem_handling_satz_pct=oem_pct,
        oem_handling_je_stueck=oem,
        sga_basis_je_stueck=sga_basis,
        sga_satz_pct=sga_pct,
        sga_quelle=sga_quelle,
        sga_je_stueck=sga,
        kosten_inkl_overheads_je_stueck=total,
    )
