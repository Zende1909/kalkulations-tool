"""Zuschlagskalkulation für Spritzguss-Einzelteile (reine Berechnungslogik)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


class SpritzgussValidationError(ValueError):
    """Ungültige Eingaben für die Spritzguss-Kalkulation."""


Money = Decimal


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
    mgk_pct: float
    zykluszeit_s: float
    maschinenstundensatz: float
    kavitaeten: int
    lohnstundensatz: float
    fgk_pct: float
    werkzeugkosten_eur: float
    amortisationsvolumen: float
    vvgk_pct: float
    gewinn_pct: float
    skonto_pct: float


@dataclass(frozen=True)
class SpritzgussErgebnis:
    # 1–5 Material
    materialgewicht_kg: float
    materialkosten: float
    materialkosten_inkl_ausschuss: float
    materialgemeinkosten: float
    materialkosten_gesamt: float
    # 6–8 Fertigung
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    # 9 Werkzeug
    werkzeugkostenanteil: float
    # 10–16
    herstellkosten: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    verkaufspreis: float

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    def as_blocks(self) -> dict[str, dict[str, float]]:
        return {
            "material": {
                "materialgewicht_kg": self.materialgewicht_kg,
                "materialkosten": self.materialkosten,
                "materialkosten_inkl_ausschuss": self.materialkosten_inkl_ausschuss,
                "materialgemeinkosten": self.materialgemeinkosten,
                "materialkosten_gesamt": self.materialkosten_gesamt,
            },
            "fertigung": {
                "maschinenkosten": self.maschinenkosten,
                "fertigungslohn": self.fertigungslohn,
                "fertigungsgemeinkosten": self.fertigungsgemeinkosten,
            },
            "werkzeug": {
                "werkzeugkostenanteil": self.werkzeugkostenanteil,
            },
            "gemeinkosten": {
                "herstellkosten": self.herstellkosten,
                "vvgk": self.vvgk,
                "selbstkosten": self.selbstkosten,
                "gewinn": self.gewinn,
            },
            "verkaufspreis": {
                "nettoverkaufspreis": self.nettoverkaufspreis,
                "skonto": self.skonto,
                "verkaufspreis": self.verkaufspreis,
            },
        }


def validate_spritzguss_input(data: SpritzgussInput) -> None:
    numeric_fields = {
        "teilegewicht_netto_g": data.teilegewicht_netto_g,
        "materialpreis_pro_kg": data.materialpreis_pro_kg,
        "ausschussquote_pct": data.ausschussquote_pct,
        "mgk_pct": data.mgk_pct,
        "zykluszeit_s": data.zykluszeit_s,
        "maschinenstundensatz": data.maschinenstundensatz,
        "lohnstundensatz": data.lohnstundensatz,
        "fgk_pct": data.fgk_pct,
        "werkzeugkosten_eur": data.werkzeugkosten_eur,
        "amortisationsvolumen": data.amortisationsvolumen,
        "vvgk_pct": data.vvgk_pct,
        "gewinn_pct": data.gewinn_pct,
        "skonto_pct": data.skonto_pct,
    }
    for name, value in numeric_fields.items():
        if value < 0:
            raise SpritzgussValidationError(f"{name} darf nicht negativ sein")

    if data.ausschussquote_pct >= 100:
        raise SpritzgussValidationError("ausschussquote_pct muss kleiner als 100 % sein")

    if data.kavitaeten < 1:
        raise SpritzgussValidationError("kavitaeten muss mindestens 1 sein")

    if data.amortisationsvolumen <= 0:
        raise SpritzgussValidationError("amortisationsvolumen muss größer als 0 sein")


def berechne_spritzguss(data: SpritzgussInput) -> SpritzgussErgebnis:
    """Führt die Zuschlagskalkulation in 16 Stufen durch."""
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
    werkzeugkosten = _d(data.werkzeugkosten_eur)
    amortisation = _d(data.amortisationsvolumen)
    vvgk_rate = _pct_to_rate(_d(data.vvgk_pct))
    gewinn_rate = _pct_to_rate(_d(data.gewinn_pct))
    skonto_rate = _pct_to_rate(_d(data.skonto_pct))

    # 1 Materialgewicht je Gutteil (kg)
    materialgewicht_kg = _qty(teilegewicht_g / Decimal("1000"))

    # 2 Materialkosten
    materialkosten = _money(materialgewicht_kg * materialpreis)

    # 3 Materialkosten inkl. Ausschuss
    materialkosten_inkl_ausschuss = _money(materialkosten / (Decimal("1") - ausschuss))

    # 4 Materialgemeinkosten
    materialgemeinkosten = _money(materialkosten_inkl_ausschuss * mgk)

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

    # 8 Fertigungsgemeinkosten
    fertigungsgemeinkosten = _money(fertigungslohn * fgk)

    # 9 Werkzeugkostenanteil
    werkzeugkostenanteil = _money(werkzeugkosten / amortisation)

    # 10 Herstellkosten
    herstellkosten = _money(
        materialkosten_gesamt
        + maschinenkosten
        + fertigungslohn
        + fertigungsgemeinkosten
        + werkzeugkostenanteil
    )

    # 11 VVGK
    vvgk = _money(herstellkosten * vvgk_rate)

    # 12 Selbstkosten
    selbstkosten = _money(herstellkosten + vvgk)

    # 13 Gewinn
    gewinn = _money(selbstkosten * gewinn_rate)

    # 14 Nettoverkaufspreis
    nettoverkaufspreis = _money(selbstkosten + gewinn)

    # 15 Skonto
    skonto = _money(nettoverkaufspreis * skonto_rate)

    # 16 Verkaufspreis
    verkaufspreis = _money(nettoverkaufspreis + skonto)

    return SpritzgussErgebnis(
        materialgewicht_kg=float(materialgewicht_kg),
        materialkosten=float(materialkosten),
        materialkosten_inkl_ausschuss=float(materialkosten_inkl_ausschuss),
        materialgemeinkosten=float(materialgemeinkosten),
        materialkosten_gesamt=float(materialkosten_gesamt),
        maschinenkosten=float(maschinenkosten),
        fertigungslohn=float(fertigungslohn),
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        werkzeugkostenanteil=float(werkzeugkostenanteil),
        herstellkosten=float(herstellkosten),
        vvgk=float(vvgk),
        selbstkosten=float(selbstkosten),
        gewinn=float(gewinn),
        nettoverkaufspreis=float(nettoverkaufspreis),
        skonto=float(skonto),
        verkaufspreis=float(verkaufspreis),
    )
