"""Zuschlagskalkulation für Spritzguss-Einzelteile (reine Berechnungslogik).

Kostenbasen
-----------
- Material-MGK: auf **Materialkosten inklusive materialbezogenem Ausschuss**
  (``materialkosten / (1 − Ausschussquote)``). Direktkosten ohne Ausschuss
  sind nur Zwischenschritt. Satz aus Stammdaten laut Nominierung
  (selbstnominiert / OEM-nominiert).
- FGK: ausschließlich Maschinenkosten + Fertigungslohn
  (nicht Material, nicht Material-MGK, nicht Werkzeug).
- SG&A (VVGK): auf Herstellkosten (Material inkl. MGK + Maschine + Lohn + FGK;
  Werkzeug-/Investitionsanteil bleibt 0 im Teilepreis).
- Profit: auf Selbstkosten (HK + SG&A).
- Skonto: auf Nettoverkaufspreis.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

WerkzeugAbrechnungsart = Literal["amortisation", "einmalzahlung"]
MaterialNominierung = Literal["selbstnominiert", "oem_nominiert"]


class SpritzgussValidationError(ValueError):
    """Ungültige Eingaben für die Spritzguss-Kalkulation."""


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _pct_to_rate(percent: Decimal) -> Decimal:
    return percent / Decimal("100")


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _qty(value: Decimal, places: str = "0.0001") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SpritzgussInput:
    teilegewicht_netto_g: float
    materialpreis_pro_kg: float
    ausschussquote_pct: float
    zykluszeit_s: float
    maschinenstundensatz: float
    kavitaeten: int
    lohnstundensatz: float
    fgk_pct: float
    werkzeugkosten_eur: float
    werkzeug_abrechnungsart: WerkzeugAbrechnungsart = "amortisation"
    amortisationsvolumen: int | None = None
    vvgk_pct: float = 0
    gewinn_pct: float = 0
    skonto_pct: float = 0
    # Material-MGK-Satz in % (zentral gesetzt laut material_nominierung)
    mgk_pct: float = 0
    material_nominierung: MaterialNominierung | None = None


@dataclass(frozen=True)
class SpritzgussErgebnis:
    materialgewicht_kg: float
    materialkosten: float
    materialkosten_inkl_ausschuss: float
    materialgemeinkosten: float
    materialkosten_gesamt: float
    mgk_basis: float
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    fgk_basis: float
    werkzeugkostenanteil: float
    werkzeug_einmalzahlung: float
    herstellkosten: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    verkaufspreis: float
    applied_mgk_pct: float
    applied_fgk_pct: float
    applied_vvgk_pct: float
    applied_gewinn_pct: float
    applied_skonto_pct: float
    material_nominierung: str | None

    def to_dict(self) -> dict[str, float | str | None]:
        return asdict(self)

    def as_blocks(self) -> dict[str, dict[str, float | str | None]]:
        return {
            "material": {
                "materialgewicht_kg": self.materialgewicht_kg,
                "materialkosten": self.materialkosten,
                "materialkosten_inkl_ausschuss": self.materialkosten_inkl_ausschuss,
                "mgk_basis": self.mgk_basis,
                "materialgemeinkosten": self.materialgemeinkosten,
                "mgk_pct": self.applied_mgk_pct,
                "material_nominierung": self.material_nominierung,
                "materialkosten_gesamt": self.materialkosten_gesamt,
            },
            "fertigung": {
                "maschinenkosten": self.maschinenkosten,
                "fertigungslohn": self.fertigungslohn,
                "fertigungsgemeinkosten": self.fertigungsgemeinkosten,
                "fgk_basis": self.fgk_basis,
                "fgk_pct": self.applied_fgk_pct,
            },
            "werkzeug": {
                "werkzeugkostenanteil": self.werkzeugkostenanteil,
                "werkzeug_einmalzahlung": self.werkzeug_einmalzahlung,
            },
            "gemeinkosten": {
                "herstellkosten": self.herstellkosten,
                "vvgk": self.vvgk,
                "vvgk_pct": self.applied_vvgk_pct,
                "vvgk_basis": self.herstellkosten,
                "selbstkosten": self.selbstkosten,
                "gewinn": self.gewinn,
                "gewinn_pct": self.applied_gewinn_pct,
                "gewinn_basis": self.selbstkosten,
            },
            "verkaufspreis": {
                "nettoverkaufspreis": self.nettoverkaufspreis,
                "skonto": self.skonto,
                "skonto_pct": self.applied_skonto_pct,
                "verkaufspreis": self.verkaufspreis,
            },
        }


def validate_spritzguss_input(data: SpritzgussInput) -> None:
    numeric_fields = {
        "teilegewicht_netto_g": data.teilegewicht_netto_g,
        "materialpreis_pro_kg": data.materialpreis_pro_kg,
        "ausschussquote_pct": data.ausschussquote_pct,
        "zykluszeit_s": data.zykluszeit_s,
        "maschinenstundensatz": data.maschinenstundensatz,
        "lohnstundensatz": data.lohnstundensatz,
        "fgk_pct": data.fgk_pct,
        "werkzeugkosten_eur": data.werkzeugkosten_eur,
        "vvgk_pct": data.vvgk_pct,
        "gewinn_pct": data.gewinn_pct,
        "skonto_pct": data.skonto_pct,
        "mgk_pct": data.mgk_pct,
    }
    for name, value in numeric_fields.items():
        if value < 0:
            raise SpritzgussValidationError(f"{name} darf nicht negativ sein")

    if data.ausschussquote_pct >= 100:
        raise SpritzgussValidationError("ausschussquote_pct muss kleiner als 100 % sein")

    if data.kavitaeten < 1:
        raise SpritzgussValidationError("kavitaeten muss mindestens 1 sein")

    if data.material_nominierung is not None and data.material_nominierung not in (
        "selbstnominiert",
        "oem_nominiert",
    ):
        raise SpritzgussValidationError(
            "material_nominierung muss 'selbstnominiert' oder 'oem_nominiert' sein"
        )


def berechne_spritzguss(data: SpritzgussInput) -> SpritzgussErgebnis:
    """Führt die Zuschlagskalkulation durch (Material-MGK + FGK auf Maschine+Lohn)."""
    validate_spritzguss_input(data)

    teilegewicht_g = _d(data.teilegewicht_netto_g)
    materialpreis = _d(data.materialpreis_pro_kg)
    ausschuss = _pct_to_rate(_d(data.ausschussquote_pct))
    mgk = _pct_to_rate(_d(data.mgk_pct))
    zykluszeit = _d(data.zykluszeit_s)
    maschinenstundensatz = _d(data.maschinenstundensatz)
    kavitaeten = _d(data.kavitaeten)
    lohnstundensatz = _d(data.lohnstundensatz)
    fgk = _pct_to_rate(_d(data.fgk_pct))
    vvgk_rate = _pct_to_rate(_d(data.vvgk_pct))
    gewinn_rate = _pct_to_rate(_d(data.gewinn_pct))
    skonto_rate = _pct_to_rate(_d(data.skonto_pct))

    # 1 Materialgewicht je Gutteil (kg)
    materialgewicht_kg = _qty(teilegewicht_g / Decimal("1000"))

    # 2 Materialkosten (direkt, ohne Ausschuss)
    materialkosten = _money(materialgewicht_kg * materialpreis)

    # 3 Materialkosten inkl. Ausschuss (= MGK-Basis)
    materialkosten_inkl_ausschuss = _money(materialkosten / (Decimal("1") - ausschuss))
    mgk_basis = materialkosten_inkl_ausschuss

    # 4 Materialgemeinkosten auf Basis inkl. Ausschuss
    materialgemeinkosten = _money(mgk_basis * mgk)

    # 5 Materialkosten gesamt
    materialkosten_gesamt = _money(materialkosten_inkl_ausschuss + materialgemeinkosten)

    # 6 Maschinenkosten je Teil
    maschinenkosten = _money(
        zykluszeit / Decimal("3600") * maschinenstundensatz / kavitaeten
    )

    # 7 Fertigungslohn je Teil
    fertigungslohn = _money(
        zykluszeit / Decimal("3600") * lohnstundensatz / kavitaeten
    )

    # 8 Fertigungsgemeinkosten – Basis: Maschinenkosten + Fertigungslohn
    fgk_basis = _money(maschinenkosten + fertigungslohn)
    fertigungsgemeinkosten = _money(fgk_basis * fgk)

    # 9 Werkzeug – nicht im Teilepreis
    werkzeugkostenanteil = _money(Decimal("0"))
    werkzeug_einmalzahlung = _money(Decimal("0"))

    # 10 Herstellkosten
    herstellkosten = _money(
        materialkosten_gesamt
        + maschinenkosten
        + fertigungslohn
        + fertigungsgemeinkosten
        + werkzeugkostenanteil
    )

    vvgk = _money(herstellkosten * vvgk_rate)
    selbstkosten = _money(herstellkosten + vvgk)
    gewinn = _money(selbstkosten * gewinn_rate)
    nettoverkaufspreis = _money(selbstkosten + gewinn)
    skonto = _money(nettoverkaufspreis * skonto_rate)
    verkaufspreis = _money(nettoverkaufspreis + skonto)

    return SpritzgussErgebnis(
        materialgewicht_kg=float(materialgewicht_kg),
        materialkosten=float(materialkosten),
        materialkosten_inkl_ausschuss=float(materialkosten_inkl_ausschuss),
        materialgemeinkosten=float(materialgemeinkosten),
        materialkosten_gesamt=float(materialkosten_gesamt),
        mgk_basis=float(mgk_basis),
        maschinenkosten=float(maschinenkosten),
        fertigungslohn=float(fertigungslohn),
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        fgk_basis=float(fgk_basis),
        werkzeugkostenanteil=float(werkzeugkostenanteil),
        werkzeug_einmalzahlung=float(werkzeug_einmalzahlung),
        herstellkosten=float(herstellkosten),
        vvgk=float(vvgk),
        selbstkosten=float(selbstkosten),
        gewinn=float(gewinn),
        nettoverkaufspreis=float(nettoverkaufspreis),
        skonto=float(skonto),
        verkaufspreis=float(verkaufspreis),
        applied_mgk_pct=float(data.mgk_pct),
        applied_fgk_pct=float(data.fgk_pct),
        applied_vvgk_pct=float(data.vvgk_pct),
        applied_gewinn_pct=float(data.gewinn_pct),
        applied_skonto_pct=float(data.skonto_pct),
        material_nominierung=data.material_nominierung,
    )
