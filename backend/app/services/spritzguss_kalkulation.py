"""Zuschlagskalkulation für Spritzguss-Einzelteile (reine Berechnungslogik).

Kostenbasen
-----------
- Materialverbrauch / direkte Materialkosten: **Schussgewicht (Brutto)** je Gutteil
  (``schussgewicht_g / 1000 × Materialpreis``). Das Netto-Teilegewicht ist nur
  Informationswert und geht nicht in die Materialkosten ein.
- Material-Ausschuss (Prozessausschuss): genau einmal auf die Schussgewichts-
  Materialkosten: ``materialkosten / (1 − Ausschussquote)``. Das Schussgewicht
  enthält typischerweise bereits Anguss-/Bruttomaterial; der Ausschusszuschlag
  deckt zusätzlich Ausschussteile ab – keine zweite Anguss-Umrechnung aus dem
  Nettogewicht.
- Material-MGK: auf **Materialkosten inklusive Prozessausschuss**
  (``mgk_basis``) – genau einmal; nie auf ``materialkosten_gesamt``.
- Direkte Fertigungskosten (Maschine / Lohn) je Gutteil über **Nettokapazität**
  (Excel ``Beispielkalkulation`` / Costing-Logik)::

      Bruttokapazität_exakt = 3600 / Zykluszeit_s × Kavitäten
      Bruttokapazität = ROUND(Bruttokapazität_exakt, 0)   # Excel ROUND
      Nettokapazität = Bruttokapazität × (1 − Ausschussquote)
      Maschinenkosten = Maschinenstundensatz / Nettokapazität
      Fertigungslohn = Lohnstundensatz / Nettokapazität

  Setup-Kosten werden über die Losgröße umgelegt und **nicht** zusätzlich mit
  dem Spritzguss-Ausschuss belastet.
- FGK: Maschinenkosten + Fertigungslohn + Setup je Teil
  (nicht Material, nicht Material-MGK, nicht Werkzeug).
- SG&A (VVGK): auf Herstellkosten (Material inkl. MGK + Maschine + Lohn + Setup + FGK;
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


def excel_round_0(value: Decimal) -> Decimal:
    """Excel ``ROUND(x, 0)`` (kaufmännisch, HALF_UP)."""
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SpritzgussInput:
    teilegewicht_netto_g: float
    schussgewicht_g: float
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
    # Setup (optional; aktiv wenn setup_zeit_min > 0)
    setup_zeit_min: float = 0
    setup_maschinenstundensatz: float = 0
    setup_lohnstundensatz: float = 0
    setup_mitarbeiter: float = 0
    losgroesse: int | None = None
    setup_aktiv: bool = False


@dataclass(frozen=True)
class SpritzgussErgebnis:
    materialgewicht_kg: float
    materialkosten: float
    materialkosten_inkl_ausschuss: float
    materialausschuss_betrag: float
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
    schussgewicht_g: float
    teilegewicht_netto_g: float
    setup_maschinenkosten_gesamt: float = 0.0
    setup_lohnkosten_gesamt: float = 0.0
    setup_kosten_je_teil: float = 0.0
    setup_maschinenkosten_je_teil: float = 0.0
    setup_lohnkosten_je_teil: float = 0.0
    losgroesse: int | None = None
    setup_aktiv: bool = False
    # Kapazität (Stück/h) – Brutto wie Excel ROUND(...,0), Netto nach Ausschuss
    bruttokapazitaet_exakt: float = 0.0
    bruttokapazitaet: float = 0.0
    nettokapazitaet: float = 0.0

    def to_dict(self) -> dict[str, float | str | None]:
        return asdict(self)

    def as_blocks(self) -> dict[str, dict[str, float | str | None]]:
        return {
            "material": {
                "schussgewicht_g": self.schussgewicht_g,
                "teilegewicht_netto_g": self.teilegewicht_netto_g,
                "materialgewicht_kg": self.materialgewicht_kg,
                "materialkosten": self.materialkosten,
                "materialkosten_inkl_ausschuss": self.materialkosten_inkl_ausschuss,
                "materialausschuss_betrag": self.materialausschuss_betrag,
                "mgk_basis": self.mgk_basis,
                "materialgemeinkosten": self.materialgemeinkosten,
                "mgk_pct": self.applied_mgk_pct,
                "material_nominierung": self.material_nominierung,
                "materialkosten_gesamt": self.materialkosten_gesamt,
            },
            "fertigung": {
                "bruttokapazitaet_exakt": self.bruttokapazitaet_exakt,
                "bruttokapazitaet": self.bruttokapazitaet,
                "nettokapazitaet": self.nettokapazitaet,
                "maschinenkosten": self.maschinenkosten,
                "fertigungslohn": self.fertigungslohn,
                "setup_maschinenkosten_je_teil": self.setup_maschinenkosten_je_teil,
                "setup_lohnkosten_je_teil": self.setup_lohnkosten_je_teil,
                "setup_kosten_je_teil": self.setup_kosten_je_teil,
                "losgroesse": self.losgroesse,
                "setup_aktiv": self.setup_aktiv,
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
        "schussgewicht_g": data.schussgewicht_g,
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

    if data.schussgewicht_g <= 0:
        raise SpritzgussValidationError(
            "schussgewicht_g muss größer als 0 sein – "
            "Materialkosten basieren auf dem Schussgewicht (Brutto), "
            "nicht auf dem Netto-Teilegewicht. Bitte Schussgewicht erfassen."
        )

    if data.ausschussquote_pct >= 100:
        raise SpritzgussValidationError("ausschussquote_pct muss kleiner als 100 % sein")

    if data.zykluszeit_s <= 0:
        raise SpritzgussValidationError("zykluszeit_s muss größer als 0 sein")

    if data.kavitaeten < 1:
        raise SpritzgussValidationError("kavitaeten muss mindestens 1 sein")

    if data.material_nominierung is not None and data.material_nominierung not in (
        "selbstnominiert",
        "oem_nominiert",
    ):
        raise SpritzgussValidationError(
            "material_nominierung muss 'selbstnominiert' oder 'oem_nominiert' sein"
        )

    setup_aktiv = bool(data.setup_aktiv) or float(data.setup_zeit_min or 0) > 0
    if setup_aktiv:
        if data.losgroesse is None or int(data.losgroesse) < 1:
            raise SpritzgussValidationError(
                "losgroesse muss >= 1 sein, wenn Setup aktiv ist"
            )
        if data.setup_zeit_min < 0 or data.setup_mitarbeiter < 0:
            raise SpritzgussValidationError("Setup-Parameter dürfen nicht negativ sein")


def berechne_spritzguss(data: SpritzgussInput) -> SpritzgussErgebnis:
    """Führt die Zuschlagskalkulation durch (Material-MGK + FGK auf Maschine+Lohn+Setup)."""
    validate_spritzguss_input(data)

    schussgewicht_g = _d(data.schussgewicht_g)
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

    materialgewicht_kg = _qty(schussgewicht_g / Decimal("1000"))
    materialkosten = _money(materialgewicht_kg * materialpreis)
    # Ausschuss genau einmal auf die direkten Materialkosten (nicht auf MGK).
    materialkosten_inkl_ausschuss = _money(materialkosten / (Decimal("1") - ausschuss))
    materialausschuss_betrag = _money(materialkosten_inkl_ausschuss - materialkosten)
    # MGK genau einmal auf Material inkl. Ausschuss – nie auf materialkosten_gesamt.
    mgk_basis = materialkosten_inkl_ausschuss
    materialgemeinkosten = _money(mgk_basis * mgk)
    materialkosten_gesamt = _money(materialkosten_inkl_ausschuss + materialgemeinkosten)

    # Kapazität analog Excel: ROUND((3600/Zyklus)*Kavitäten, 0), dann Netto mit Ausschuss
    brutto_exakt = (Decimal("3600") / zykluszeit) * kavitaeten
    brutto = excel_round_0(brutto_exakt)
    if brutto < 1:
        raise SpritzgussValidationError(
            "Bruttokapazität ist nach Excel-Rundung < 1 Stück/h – "
            "Zykluszeit oder Kavitäten prüfen"
        )
    netto = brutto * (Decimal("1") - ausschuss)
    if netto <= 0:
        raise SpritzgussValidationError("Nettokapazität muss größer als 0 sein")

    maschinenkosten = _money(maschinenstundensatz / netto)
    fertigungslohn = _money(lohnstundensatz / netto)

    setup_aktiv = bool(data.setup_aktiv) or float(data.setup_zeit_min or 0) > 0
    setup_maschinen_gesamt = Decimal("0")
    setup_lohn_gesamt = Decimal("0")
    setup_maschine_teil = Decimal("0")
    setup_lohn_teil = Decimal("0")
    setup_je_teil = Decimal("0")
    if setup_aktiv:
        # Setup über Losgröße – ohne zusätzlichen Spritzguss-Ausschuss (Excel-Logik).
        # Maschinen- und Lohnanteil gemeinsam berechnen; Detailanteile nur für Anzeige.
        stunden = _d(data.setup_zeit_min) / Decimal("60")
        los = _d(int(data.losgroesse or 1))
        setup_stundensatz = _d(data.setup_maschinenstundensatz) + (
            _d(data.setup_lohnstundensatz) * _d(data.setup_mitarbeiter)
        )
        setup_je_teil = (setup_stundensatz * stunden) / los
        setup_maschinen_gesamt = _money(
            stunden * _d(data.setup_maschinenstundensatz)
        )
        setup_lohn_gesamt = _money(
            stunden * _d(data.setup_lohnstundensatz) * _d(data.setup_mitarbeiter)
        )
        setup_maschine_teil = _money(
            stunden * _d(data.setup_maschinenstundensatz) / los
        )
        setup_lohn_teil = _money(
            stunden * _d(data.setup_lohnstundensatz) * _d(data.setup_mitarbeiter) / los
        )

    # FGK-Basis: Maschine + Lohn + Setup (je Teil), ohne Material
    fgk_basis = _money(maschinenkosten + fertigungslohn + setup_je_teil)
    fertigungsgemeinkosten = _money(fgk_basis * fgk)

    werkzeugkostenanteil = _money(Decimal("0"))
    werkzeug_einmalzahlung = _money(Decimal("0"))

    herstellkosten = _money(
        materialkosten_gesamt
        + maschinenkosten
        + fertigungslohn
        + setup_je_teil
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
        materialausschuss_betrag=float(materialausschuss_betrag),
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
        schussgewicht_g=float(data.schussgewicht_g),
        teilegewicht_netto_g=float(data.teilegewicht_netto_g),
        setup_maschinenkosten_gesamt=float(setup_maschinen_gesamt),
        setup_lohnkosten_gesamt=float(setup_lohn_gesamt),
        setup_kosten_je_teil=float(setup_je_teil),
        setup_maschinenkosten_je_teil=float(setup_maschine_teil),
        setup_lohnkosten_je_teil=float(setup_lohn_teil),
        losgroesse=int(data.losgroesse) if data.losgroesse is not None else None,
        setup_aktiv=setup_aktiv,
        bruttokapazitaet_exakt=float(brutto_exakt),
        bruttokapazitaet=float(brutto),
        nettokapazitaet=float(netto),
    )
