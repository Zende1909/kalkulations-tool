"""Zentrale Zuschlagssätze aus Stammdaten.

Kostenbasen (fachlich verbindlich)
----------------------------------
- MGK selbstnominiert / OEM-nominiert (Typen ``mgk_kaufteil_selbst`` /
  ``mgk_kaufteil_oem`` – gelten für Materialeinsatz und Kaufteile):
  * Spritzguss-Material: Materialkosten **inklusive** materialbezogenem
    Ausschuss
  * Kaufteile: ausschließlich Einkaufspreis
- FGK:
  Maschinenkosten + Fertigungslohn + direkte Veredelungskosten
  (ohne Material, Material-MGK, Kaufteile, Kaufteil-MGK, Werkzeug).
  Pro Kostenbestandteil genau einmal.
- SG&A / VVGK:
  vollständige Herstellkosten (Material inkl. MGK, Fertigung inkl. FGK,
  Veredelung direkt, Kaufteile inkl. MGK, Werkzeug-/Investition falls vorhanden).
- Profit / Gewinn:
  Herstellkosten + SG&A (Selbstkosten).
- Skonto:
  weiterhin auf Nettoverkaufspreis, Satz aus Stammdaten (typ ``skonto``).

Fehlende oder inaktive Pflichtsätze führen zu einem klaren Fehler –
kein stilles Rechnen mit 0 %.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.zuschlagssatz import CENTRAL_MARKUP_TYPEN, Zuschlagssatz

# Technische Typ-Keys (lowercase), pflegbar nur in Stammdaten → Zuschlagssätze.
# Historische Keys „mgk_kaufteil_*“ gelten fachlich für Material und Kaufteile.
TYP_MGK_SELBST = "mgk_kaufteil_selbst"
TYP_MGK_OEM = "mgk_kaufteil_oem"
TYP_FGK = "fgk"
TYP_VVGK = "vvgk"
TYP_GEWINN = "gewinn"
TYP_SKONTO = "skonto"

NOMINIERUNG_SELBST = "selbstnominiert"
NOMINIERUNG_OEM = "oem_nominiert"
NOMINIERUNGEN = (NOMINIERUNG_SELBST, NOMINIERUNG_OEM)

# Abwärtskompatible Aliase
TYP_MGK_KAUFTEIL_SELBST = TYP_MGK_SELBST
TYP_MGK_KAUFTEIL_OEM = TYP_MGK_OEM
KAUFTEIL_NOMINIERUNG_SELBST = NOMINIERUNG_SELBST
KAUFTEIL_NOMINIERUNG_OEM = NOMINIERUNG_OEM
KAUFTEIL_NOMINIERUNGEN = NOMINIERUNGEN


class CentralMarkupRatesError(ValueError):
    """Fehlende oder ungültige zentrale Zuschlagssätze."""


@dataclass(frozen=True)
class CentralMarkupRates:
    """Aktive zentrale Zuschlagssätze in Prozent."""

    mgk_kaufteil_selbst_pct: float
    mgk_kaufteil_oem_pct: float
    fgk_pct: float
    vvgk_pct: float  # SG&A / Overhead
    gewinn_pct: float
    skonto_pct: float
    handling_oem_kaufteil_pct: float = 0.0

    @property
    def mgk_selbst_pct(self) -> float:
        return self.mgk_kaufteil_selbst_pct

    @property
    def mgk_oem_pct(self) -> float:
        return self.mgk_kaufteil_oem_pct

    def mgk_pct_for_nominierung(
        self,
        nominierung: str | None,
        *,
        kontext: str = "Datensatz",
    ) -> float:
        if nominierung == NOMINIERUNG_SELBST:
            return self.mgk_kaufteil_selbst_pct
        if nominierung == NOMINIERUNG_OEM:
            return self.mgk_kaufteil_oem_pct
        raise CentralMarkupRatesError(
            f"{kontext} ohne gültige Nominierung (selbstnominiert / OEM-nominiert). "
            "Bitte Klassifizierung nachpflegen – ohne Auswahl wird kein MGK-Satz angewendet."
        )


_REQUIRED: tuple[tuple[str, str], ...] = (
    (TYP_MGK_SELBST, "mgk_kaufteil_selbst_pct"),
    (TYP_MGK_OEM, "mgk_kaufteil_oem_pct"),
    (TYP_FGK, "fgk_pct"),
    (TYP_VVGK, "vvgk_pct"),
    (TYP_GEWINN, "gewinn_pct"),
    (TYP_SKONTO, "skonto_pct"),
)

TYP_HANDLING_OEM = "handling_oem_kaufteil"


def load_central_markup_rates(
    db: Session, *, werk_id: int | None = None
) -> CentralMarkupRates:
    """Lädt aktive zentrale Sätze; optionale Werk-Overrides für FGK/SG&A/Profit/Skonto/Handling."""
    if set(typ for typ, _ in _REQUIRED) != set(CENTRAL_MARKUP_TYPEN):
        raise RuntimeError("CENTRAL_MARKUP_TYPEN und Loader sind inkonsistent.")

    found: dict[str, float] = {}
    for row in db.scalars(select(Zuschlagssatz).where(Zuschlagssatz.aktiv.is_(True))).all():
        key = (row.typ or "").strip()
        if key in found:
            continue
        if key in dict(_REQUIRED):
            found[key] = float(row.satz_prozent)

    missing_labels = [typ for typ, _ in _REQUIRED if typ not in found]
    if missing_labels:
        raise CentralMarkupRatesError(
            "Fehlende aktive Zuschlagssätze in Stammdaten: "
            + ", ".join(missing_labels)
            + ". Bitte unter Stammdaten → Zuschlagssätze anlegen und aktivieren."
        )

    handling = 0.0
    if werk_id is not None:
        from app.models.werk_zuschlag import WerkZuschlag

        for row in db.scalars(
            select(WerkZuschlag).where(
                WerkZuschlag.werk_id == werk_id,
                WerkZuschlag.aktiv.is_(True),
            )
        ).all():
            key = (row.typ or "").strip()
            if key in found and key in {
                TYP_FGK,
                TYP_VVGK,
                TYP_GEWINN,
                TYP_SKONTO,
            }:
                found[key] = float(row.satz_prozent)
            if key == TYP_HANDLING_OEM:
                handling = float(row.satz_prozent)

    return CentralMarkupRates(
        mgk_kaufteil_selbst_pct=found[TYP_MGK_SELBST],
        mgk_kaufteil_oem_pct=found[TYP_MGK_OEM],
        fgk_pct=found[TYP_FGK],
        vvgk_pct=found[TYP_VVGK],
        gewinn_pct=found[TYP_GEWINN],
        skonto_pct=found[TYP_SKONTO],
        handling_oem_kaufteil_pct=handling,
    )
