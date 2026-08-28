"""Berechnungslogik für Baugruppenkalkulationen.

Fachmodell:
1. Einzelteil-Selbstkosten (bereits inkl. ET-MGK/FGK/SG&A) × Menge
2. Kaufteil je Stück: Einkauf + MGK + OEM-Handling + SG&A; dann × Menge
3. Vorprodukt = Einzelteile + Kaufteile
4. Direkte Montagekosten (Lohn + Maschine + Verbrauch) × Prozessfaktor
5. Montage-FGK auf FGK-Basis (Maschine + Lohn + Verbrauch, ohne Kaufteile/Einzelteile)
6. Ausbeutekette je Montageschritt auf kumulierte Kosten (inkl. FGK vor erstem Schritt)
7. Gewinn genau einmal auf Kostenbasis nach Assembly-Ausschuss
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.process_yield import apply_process_yield


class BaugruppeValidationError(ValueError):
    """Ungültige Eingaben für die Baugruppenkalkulation."""


class BaugruppeMarkupError(ValueError):
    """Fehlende zentrale Zuschlagssätze für die Baugruppenkalkulation."""


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _display(value: Decimal) -> float:
    """Nur für API/Anzeige – keine Zwischenrundung in Berechnungen."""
    return float(value.quantize(Decimal("0.0000000001"), rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class EinzelteilEingabe:
    spritzguss_kalkulation_id: int
    bezeichnung: str
    teilenummer: str
    menge: float
    reihenfolge: int
    snapshot_preis: float


@dataclass(frozen=True)
class KaufteilEingabe:
    kaufteil_id: int
    bezeichnung: str
    lieferant: str
    menge: float
    reihenfolge: int
    nominierung: str
    einkaufspreis_je_stueck: float
    mgk_satz_pct: float
    mgk_je_stueck: float
    oem_handling_satz_pct: float
    oem_handling_je_stueck: float
    sga_satz_pct: float
    sga_quelle: str
    sga_je_stueck: float
    kosten_inkl_overheads_je_stueck: float


@dataclass(frozen=True)
class VeredelungEingabe:
    veredelungsschritt_id: int
    bezeichnung: str
    reihenfolge: int
    mengenfaktor: float
    ausschussquote_pct: float
    lohnkosten_je_stueck: float
    maschinenkosten_je_stueck: float
    verbrauchskosten_je_stueck: float
    direktkosten_je_stueck: float


@dataclass(frozen=True)
class InvestitionAnzeige:
    id: int
    bezeichnung: str
    investment_type: str
    amount: float
    status: str
    quelle: str
    cost_amount: float | None = None
    bottom_price: float | None = None
    revenue_amount: float | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class PositionErgebnis:
    id_ref: int
    bezeichnung: str
    menge: float
    einzelpreis: float
    zwischensumme: float
    detail: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VeredelungPositionErgebnis:
    veredelungsschritt_id: int
    bezeichnung: str
    reihenfolge: int
    ausschussquote_pct: float
    mengenfaktor: float
    lohnkosten_je_stueck: float
    maschinenkosten_je_stueck: float
    verbrauchskosten_je_stueck: float
    direktkosten_je_stueck: float
    direktkosten: float
    fgk_basis: float
    vorprodukt_eingang: float
    ausschuss_zuschlag: float
    ausbeute_faktor: float
    kosten_nach_ausschuss: float
    zwischensumme: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BaugruppeErgebnis:
    einzelteile_gesamt: float
    kaufteile_gesamt: float
    kaufteile_einkauf_gesamt: float
    kaufteile_mgk_gesamt: float
    kaufteile_oem_handling_gesamt: float
    kaufteile_sga_gesamt: float
    veredelung_gesamt: float
    vorprodukt_gesamt: float
    assembly_direkt_gesamt: float
    assembly_fgk_basis: float
    assembly_fgk_satz_pct: float
    assembly_fgk_betrag: float
    kostenbasis_vor_ausschuss: float
    assembly_ausschuss_zuschlag: float
    kostenbasis_nach_assembly: float
    gewinn_pct: float
    gewinn_betrag: float
    baugruppenpreis_je_stueck: float
    jahresstueckzahl: int
    jahresumsatz: float
    einzelteile: list[PositionErgebnis]
    kaufteile: list[PositionErgebnis]
    veredelungen: list[VeredelungPositionErgebnis]
    investitionen: list[InvestitionAnzeige]
    investitionen_gesamt: float

    def to_dict(self) -> dict:
        return {
            "einzelteile_gesamt": self.einzelteile_gesamt,
            "kaufteile_gesamt": self.kaufteile_gesamt,
            "kaufteile_einkauf_gesamt": self.kaufteile_einkauf_gesamt,
            "kaufteile_mgk_gesamt": self.kaufteile_mgk_gesamt,
            "kaufteile_oem_handling_gesamt": self.kaufteile_oem_handling_gesamt,
            "kaufteile_sga_gesamt": self.kaufteile_sga_gesamt,
            "veredelung_gesamt": self.veredelung_gesamt,
            "vorprodukt_gesamt": self.vorprodukt_gesamt,
            "assembly_direkt_gesamt": self.assembly_direkt_gesamt,
            "assembly_fgk_basis": self.assembly_fgk_basis,
            "assembly_fgk_satz_pct": self.assembly_fgk_satz_pct,
            "assembly_fgk_betrag": self.assembly_fgk_betrag,
            "kostenbasis_vor_ausschuss": self.kostenbasis_vor_ausschuss,
            "assembly_ausschuss_zuschlag": self.assembly_ausschuss_zuschlag,
            "kostenbasis_nach_assembly": self.kostenbasis_nach_assembly,
            "gewinn_pct": self.gewinn_pct,
            "gewinn_betrag": self.gewinn_betrag,
            "baugruppenpreis_je_stueck": self.baugruppenpreis_je_stueck,
            "jahresstueckzahl": self.jahresstueckzahl,
            "jahresumsatz": self.jahresumsatz,
            "investitionen_gesamt": self.investitionen_gesamt,
            "einzelteile": [p.to_dict() for p in self.einzelteile],
            "kaufteile": [p.to_dict() for p in self.kaufteile],
            "veredelungen": [v.to_dict() for v in self.veredelungen],
            "investitionen": [i.to_dict() for i in self.investitionen],
        }

    def as_zusammenfassung(self) -> dict[str, float | int]:
        return {
            "einzelteile_gesamt": self.einzelteile_gesamt,
            "kaufteile_gesamt": self.kaufteile_gesamt,
            "veredelung_gesamt": self.veredelung_gesamt,
            "vorprodukt_gesamt": self.vorprodukt_gesamt,
            "assembly_direkt_gesamt": self.assembly_direkt_gesamt,
            "assembly_fgk_betrag": self.assembly_fgk_betrag,
            "kostenbasis_vor_ausschuss": self.kostenbasis_vor_ausschuss,
            "assembly_ausschuss_zuschlag": self.assembly_ausschuss_zuschlag,
            "kostenbasis_nach_assembly": self.kostenbasis_nach_assembly,
            "gewinn_pct": self.gewinn_pct,
            "gewinn_betrag": self.gewinn_betrag,
            "baugruppenpreis_je_stueck": self.baugruppenpreis_je_stueck,
            "jahresstueckzahl": self.jahresstueckzahl,
            "jahresumsatz": self.jahresumsatz,
            "investitionen_gesamt": self.investitionen_gesamt,
        }


def validate_menge(menge: float, *, label: str = "Menge") -> None:
    if menge <= 0:
        raise BaugruppeValidationError(f"{label} muss größer als 0 sein")


def validate_mengenfaktor(mengenfaktor: float) -> None:
    if mengenfaktor <= 0:
        raise BaugruppeValidationError("Mengenfaktor muss größer als 0 sein")


def validate_jahresstueckzahl(jahresstueckzahl: int) -> None:
    if jahresstueckzahl < 0:
        raise BaugruppeValidationError("Jahresstückzahl darf nicht negativ sein")


def validate_preis(preis: float, *, label: str = "Preis") -> None:
    if preis < 0:
        raise BaugruppeValidationError(f"{label} darf nicht negativ sein")


def validate_gewinn_pct(gewinn_pct: float | None) -> Decimal:
    if gewinn_pct is None:
        raise BaugruppeMarkupError(
            "Kein aktiver zentraler Gewinnsatz hinterlegt. Bitte Zuschlagssätze pflegen."
        )
    rate = _d(gewinn_pct)
    if rate < 0:
        raise BaugruppeMarkupError("Gewinnsatz darf nicht negativ sein.")
    return rate


def validate_fgk_pct(fgk_pct: float | None) -> Decimal:
    if fgk_pct is None:
        raise BaugruppeMarkupError(
            "Kein aktiver zentraler Montage-FGK-Satz hinterlegt. Bitte Zuschlagssätze pflegen."
        )
    rate = _d(fgk_pct)
    if rate < 0:
        raise BaugruppeMarkupError("Montage-FGK-Satz darf nicht negativ sein.")
    return rate


def _check_duplicates(ids: list[int], *, label: str) -> None:
    seen: set[int] = set()
    for item_id in ids:
        if item_id in seen:
            raise BaugruppeValidationError(f"{label} {item_id} ist doppelt zugeordnet")
        seen.add(item_id)


def berechne_baugruppe(
    einzelteile: list[EinzelteilEingabe],
    kaufteile: list[KaufteilEingabe],
    veredelungen: list[VeredelungEingabe],
    *,
    jahresstueckzahl: int = 0,
    investitionen: list[InvestitionAnzeige] | None = None,
    gewinn_pct: float | None = None,
    fgk_pct: float | None = None,
) -> BaugruppeErgebnis:
    """Berechnet Baugruppen-Endpreis mit Montage-FGK, Assembly-Ausbeute und einmaligem Gewinn."""
    validate_jahresstueckzahl(jahresstueckzahl)
    gewinn_rate = validate_gewinn_pct(gewinn_pct)
    fgk_rate = validate_fgk_pct(fgk_pct)
    _check_duplicates(
        [e.spritzguss_kalkulation_id for e in einzelteile],
        label="Einzelteil",
    )
    _check_duplicates([k.kaufteil_id for k in kaufteile], label="Kaufteil")
    _check_duplicates(
        [v.veredelungsschritt_id for v in veredelungen],
        label="Veredelungsschritt",
    )

    einzelteile_ergebnis: list[PositionErgebnis] = []
    einzelteile_summe = Decimal("0")
    for teil in sorted(einzelteile, key=lambda t: t.reihenfolge):
        validate_menge(teil.menge, label="Einzelteil-Menge")
        validate_preis(teil.snapshot_preis, label="Einzelteil-Selbstkosten")
        unit = _d(teil.snapshot_preis)
        zwischensumme = unit * _d(teil.menge)
        einzelteile_summe += zwischensumme
        einzelteile_ergebnis.append(
            PositionErgebnis(
                id_ref=teil.spritzguss_kalkulation_id,
                bezeichnung=teil.bezeichnung,
                menge=teil.menge,
                einzelpreis=_display(unit),
                zwischensumme=_display(zwischensumme),
                detail={
                    "teilenummer": teil.teilenummer,
                    "reihenfolge": teil.reihenfolge,
                    "kostenart": "selbstkosten",
                },
            )
        )

    kaufteile_ergebnis: list[PositionErgebnis] = []
    kaufteile_summe = Decimal("0")
    kaufteile_einkauf = Decimal("0")
    kaufteile_mgk = Decimal("0")
    kaufteile_oem = Decimal("0")
    kaufteile_sga = Decimal("0")
    for teil in sorted(kaufteile, key=lambda t: t.reihenfolge):
        validate_menge(teil.menge, label="Kaufteil-Menge")
        menge = _d(teil.menge)
        einkauf = _d(teil.einkaufspreis_je_stueck)
        mgk = _d(teil.mgk_je_stueck)
        oem = _d(teil.oem_handling_je_stueck)
        sga = _d(teil.sga_je_stueck)
        unit_total = _d(teil.kosten_inkl_overheads_je_stueck)
        zwischensumme = unit_total * menge
        kaufteile_summe += zwischensumme
        kaufteile_einkauf += einkauf * menge
        kaufteile_mgk += mgk * menge
        kaufteile_oem += oem * menge
        kaufteile_sga += sga * menge
        kaufteile_ergebnis.append(
            PositionErgebnis(
                id_ref=teil.kaufteil_id,
                bezeichnung=teil.bezeichnung,
                menge=teil.menge,
                einzelpreis=_display(unit_total),
                zwischensumme=_display(zwischensumme),
                detail={
                    "lieferant": teil.lieferant,
                    "reihenfolge": teil.reihenfolge,
                    "nominierung": teil.nominierung,
                    "einkaufspreis_je_stueck": _display(einkauf),
                    "mgk_satz_pct": teil.mgk_satz_pct,
                    "mgk_je_stueck": _display(mgk),
                    "oem_handling_satz_pct": teil.oem_handling_satz_pct,
                    "oem_handling_je_stueck": _display(oem),
                    "sga_satz_pct": teil.sga_satz_pct,
                    "sga_quelle": teil.sga_quelle,
                    "sga_basis_je_stueck": _display(einkauf + mgk + oem),
                    "sga_je_stueck": _display(sga),
                    "kosten_inkl_overheads_je_stueck": _display(unit_total),
                },
            )
        )

    vorprodukt = einzelteile_summe + kaufteile_summe
    assembly_direct_total = Decimal("0")
    fgk_basis_total = Decimal("0")
    veredelungen_ergebnis: list[VeredelungPositionErgebnis] = []

    for schritt in sorted(veredelungen, key=lambda v: v.reihenfolge):
        validate_mengenfaktor(schritt.mengenfaktor)
        faktor = _d(schritt.mengenfaktor)
        lohn = _d(schritt.lohnkosten_je_stueck) * faktor
        maschine = _d(schritt.maschinenkosten_je_stueck) * faktor
        verbrauch = _d(schritt.verbrauchskosten_je_stueck) * faktor
        direct = lohn + maschine + verbrauch
        fgk_basis = lohn + maschine + verbrauch
        assembly_direct_total += direct
        fgk_basis_total += fgk_basis

    assembly_fgk = fgk_basis_total * fgk_rate / Decimal("100")
    kostenbasis_vor_ausschuss = vorprodukt + assembly_direct_total + assembly_fgk

    running = vorprodukt + assembly_fgk
    scrap_surcharge_total = Decimal("0")
    for schritt in sorted(veredelungen, key=lambda v: v.reihenfolge):
        validate_mengenfaktor(schritt.mengenfaktor)
        faktor = _d(schritt.mengenfaktor)
        direct = (
            _d(schritt.lohnkosten_je_stueck)
            + _d(schritt.maschinenkosten_je_stueck)
            + _d(schritt.verbrauchskosten_je_stueck)
        ) * faktor
        fgk_basis = (
            _d(schritt.lohnkosten_je_stueck)
            + _d(schritt.maschinenkosten_je_stueck)
            + _d(schritt.verbrauchskosten_je_stueck)
        ) * faktor
        vorprodukt_eingang = running
        try:
            running, surcharge, yield_factor = apply_process_yield(
                running,
                direct,
                schritt.ausschussquote_pct,
                quantize=False,
            )
        except ValueError as exc:
            raise BaugruppeValidationError(str(exc)) from exc
        scrap_surcharge_total += surcharge
        veredelungen_ergebnis.append(
            VeredelungPositionErgebnis(
                veredelungsschritt_id=schritt.veredelungsschritt_id,
                bezeichnung=schritt.bezeichnung,
                reihenfolge=schritt.reihenfolge,
                ausschussquote_pct=schritt.ausschussquote_pct,
                mengenfaktor=schritt.mengenfaktor,
                lohnkosten_je_stueck=schritt.lohnkosten_je_stueck,
                maschinenkosten_je_stueck=schritt.maschinenkosten_je_stueck,
                verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
                direktkosten_je_stueck=schritt.direktkosten_je_stueck,
                direktkosten=_display(direct),
                fgk_basis=_display(fgk_basis),
                vorprodukt_eingang=_display(vorprodukt_eingang),
                ausschuss_zuschlag=_display(surcharge),
                ausbeute_faktor=_display(yield_factor),
                kosten_nach_ausschuss=_display(running),
                zwischensumme=_display(direct),
            )
        )

    if not veredelungen:
        running = kostenbasis_vor_ausschuss

    kostenbasis_nach_assembly = running
    gewinn_betrag = kostenbasis_nach_assembly * gewinn_rate / Decimal("100")
    endpreis = kostenbasis_nach_assembly + gewinn_betrag
    jahresumsatz = endpreis * _d(jahresstueckzahl)

    investitionen_liste = investitionen or []
    investitionen_gesamt = sum(i.amount for i in investitionen_liste)

    return BaugruppeErgebnis(
        einzelteile_gesamt=_display(einzelteile_summe),
        kaufteile_gesamt=_display(kaufteile_summe),
        kaufteile_einkauf_gesamt=_display(kaufteile_einkauf),
        kaufteile_mgk_gesamt=_display(kaufteile_mgk),
        kaufteile_oem_handling_gesamt=_display(kaufteile_oem),
        kaufteile_sga_gesamt=_display(kaufteile_sga),
        veredelung_gesamt=_display(assembly_direct_total),
        vorprodukt_gesamt=_display(vorprodukt),
        assembly_direkt_gesamt=_display(assembly_direct_total),
        assembly_fgk_basis=_display(fgk_basis_total),
        assembly_fgk_satz_pct=float(fgk_rate),
        assembly_fgk_betrag=_display(assembly_fgk),
        kostenbasis_vor_ausschuss=_display(kostenbasis_vor_ausschuss),
        assembly_ausschuss_zuschlag=_display(scrap_surcharge_total),
        kostenbasis_nach_assembly=_display(kostenbasis_nach_assembly),
        gewinn_pct=float(gewinn_rate),
        gewinn_betrag=_display(gewinn_betrag),
        baugruppenpreis_je_stueck=_display(endpreis),
        jahresstueckzahl=jahresstueckzahl,
        jahresumsatz=_display(jahresumsatz),
        einzelteile=einzelteile_ergebnis,
        kaufteile=kaufteile_ergebnis,
        veredelungen=veredelungen_ergebnis,
        investitionen=investitionen_liste,
        investitionen_gesamt=investitionen_gesamt,
    )
