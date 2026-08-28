"""Berechnungslogik für Baugruppenkalkulationen.

Fachmodell (Bumper-Zusammenbau):
1. Vorprodukt = Σ Einzelteil-Selbstkosten + Σ Kaufteil-Selbstkosten (inkl. MGK)
2. + direkte Montage-/Assemblykosten vor Ausschuss (pro Veredelungsschritt)
3. Ausbeutekette: (Vorprodukt + Direktkosten) / (1 − Ausschussquote/100) je Prozessschritt
4. Gewinn genau einmal auf die Kostenbasis nach Assembly-Ausschuss (kein erneutes SG&A)
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


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


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
    snapshot_preis: float


@dataclass(frozen=True)
class VeredelungEingabe:
    veredelungsschritt_id: int
    bezeichnung: str
    reihenfolge: int
    mengenfaktor: float
    kosten_vor_ausschuss: float
    ausschussquote_pct: float
    snapshot_kosten: float | None = None


@dataclass(frozen=True)
class InvestitionAnzeige:
    id: int
    bezeichnung: str
    investment_type: str
    amount: float
    status: str
    quelle: str

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
    kosten_vor_ausschuss: float
    ausschussquote_pct: float
    mengenfaktor: float
    direktkosten: float
    vorprodukt_eingang: float
    ausschuss_zuschlag: float
    ausbeute_faktor: float
    kosten_nach_ausschuss: float
    kosten_je_stueck: float
    zwischensumme: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BaugruppeErgebnis:
    einzelteile_gesamt: float
    kaufteile_gesamt: float
    veredelung_gesamt: float
    vorprodukt_gesamt: float
    assembly_direkt_gesamt: float
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
            "veredelung_gesamt": self.veredelung_gesamt,
            "vorprodukt_gesamt": self.vorprodukt_gesamt,
            "assembly_direkt_gesamt": self.assembly_direkt_gesamt,
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


def validate_gewinn_pct(gewinn_pct: float | None) -> float:
    if gewinn_pct is None:
        raise BaugruppeMarkupError(
            "Kein aktiver zentraler Gewinnsatz hinterlegt. Bitte Zuschlagssätze pflegen."
        )
    if gewinn_pct < 0:
        raise BaugruppeMarkupError("Gewinnsatz darf nicht negativ sein.")
    return float(gewinn_pct)


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
) -> BaugruppeErgebnis:
    """Berechnet Baugruppen-Endpreis mit Assembly-Ausbeute und einmaligem Gewinn."""
    validate_jahresstueckzahl(jahresstueckzahl)
    gewinn_rate = validate_gewinn_pct(gewinn_pct)
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
        zwischensumme = _money(_d(teil.menge) * _d(teil.snapshot_preis))
        einzelteile_summe += zwischensumme
        einzelteile_ergebnis.append(
            PositionErgebnis(
                id_ref=teil.spritzguss_kalkulation_id,
                bezeichnung=teil.bezeichnung,
                menge=teil.menge,
                einzelpreis=teil.snapshot_preis,
                zwischensumme=float(zwischensumme),
                detail={
                    "teilenummer": teil.teilenummer,
                    "reihenfolge": teil.reihenfolge,
                    "kostenart": "selbstkosten",
                },
            )
        )

    kaufteile_ergebnis: list[PositionErgebnis] = []
    kaufteile_summe = Decimal("0")
    for teil in sorted(kaufteile, key=lambda t: t.reihenfolge):
        validate_menge(teil.menge, label="Kaufteil-Menge")
        validate_preis(teil.snapshot_preis, label="Kaufteil-Selbstkosten")
        zwischensumme = _money(_d(teil.menge) * _d(teil.snapshot_preis))
        kaufteile_summe += zwischensumme
        kaufteile_ergebnis.append(
            PositionErgebnis(
                id_ref=teil.kaufteil_id,
                bezeichnung=teil.bezeichnung,
                menge=teil.menge,
                einzelpreis=teil.snapshot_preis,
                zwischensumme=float(zwischensumme),
                detail={
                    "lieferant": teil.lieferant,
                    "reihenfolge": teil.reihenfolge,
                    "kostenart": "selbstkosten_inkl_mgk",
                },
            )
        )

    vorprodukt = _money(einzelteile_summe + kaufteile_summe)
    running = vorprodukt
    assembly_direct_total = Decimal("0")
    scrap_surcharge_total = Decimal("0")
    veredelungen_ergebnis: list[VeredelungPositionErgebnis] = []

    for schritt in sorted(veredelungen, key=lambda v: v.reihenfolge):
        validate_mengenfaktor(schritt.mengenfaktor)
        validate_preis(schritt.kosten_vor_ausschuss, label="Veredelungskosten")
        vorprodukt_eingang = running
        direct = _money(_d(schritt.kosten_vor_ausschuss) * _d(schritt.mengenfaktor))
        assembly_direct_total += direct
        try:
            running, surcharge, yield_factor = apply_process_yield(
                running,
                direct,
                schritt.ausschussquote_pct,
            )
        except ValueError as exc:
            raise BaugruppeValidationError(str(exc)) from exc
        scrap_surcharge_total += surcharge
        veredelungen_ergebnis.append(
            VeredelungPositionErgebnis(
                veredelungsschritt_id=schritt.veredelungsschritt_id,
                bezeichnung=schritt.bezeichnung,
                reihenfolge=schritt.reihenfolge,
                kosten_vor_ausschuss=schritt.kosten_vor_ausschuss,
                ausschussquote_pct=schritt.ausschussquote_pct,
                mengenfaktor=schritt.mengenfaktor,
                direktkosten=float(direct),
                vorprodukt_eingang=float(_money(vorprodukt_eingang)),
                ausschuss_zuschlag=float(surcharge),
                ausbeute_faktor=float(yield_factor),
                kosten_nach_ausschuss=float(running),
                kosten_je_stueck=schritt.kosten_vor_ausschuss,
                zwischensumme=float(direct),
            )
        )

    kostenbasis_nach_assembly = _money(running)
    gewinn_betrag = _money(kostenbasis_nach_assembly * _d(gewinn_rate) / Decimal("100"))
    endpreis = _money(kostenbasis_nach_assembly + gewinn_betrag)
    jahresumsatz = _money(endpreis * _d(jahresstueckzahl))

    investitionen_liste = investitionen or []
    investitionen_gesamt = sum(i.amount for i in investitionen_liste)

    return BaugruppeErgebnis(
        einzelteile_gesamt=float(einzelteile_summe),
        kaufteile_gesamt=float(kaufteile_summe),
        veredelung_gesamt=float(assembly_direct_total),
        vorprodukt_gesamt=float(vorprodukt),
        assembly_direkt_gesamt=float(assembly_direct_total),
        assembly_ausschuss_zuschlag=float(scrap_surcharge_total),
        kostenbasis_nach_assembly=float(kostenbasis_nach_assembly),
        gewinn_pct=gewinn_rate,
        gewinn_betrag=float(gewinn_betrag),
        baugruppenpreis_je_stueck=float(endpreis),
        jahresstueckzahl=jahresstueckzahl,
        jahresumsatz=float(jahresumsatz),
        einzelteile=einzelteile_ergebnis,
        kaufteile=kaufteile_ergebnis,
        veredelungen=veredelungen_ergebnis,
        investitionen=investitionen_liste,
        investitionen_gesamt=investitionen_gesamt,
    )
