"""Berechnungslogik für Baugruppenkalkulationen."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


class BaugruppeValidationError(ValueError):
    """Ungültige Eingaben für die Baugruppenkalkulation."""


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
    snapshot_kosten: float


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
    kosten_je_stueck: float
    mengenfaktor: float
    zwischensumme: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BaugruppeErgebnis:
    einzelteile_gesamt: float
    kaufteile_gesamt: float
    veredelung_gesamt: float
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
) -> BaugruppeErgebnis:
    """Berechnet Baugruppenpreis ohne zusätzliche VVGK/Gewinn-Zuschläge."""
    validate_jahresstueckzahl(jahresstueckzahl)
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
        validate_preis(teil.snapshot_preis, label="Einzelteil-Preis")
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
                },
            )
        )

    kaufteile_ergebnis: list[PositionErgebnis] = []
    kaufteile_summe = Decimal("0")
    for teil in sorted(kaufteile, key=lambda t: t.reihenfolge):
        validate_menge(teil.menge, label="Kaufteil-Menge")
        validate_preis(teil.snapshot_preis, label="Kaufteil-Preis")
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
                },
            )
        )

    veredelungen_ergebnis: list[VeredelungPositionErgebnis] = []
    veredelung_summe = Decimal("0")
    for schritt in sorted(veredelungen, key=lambda v: v.reihenfolge):
        validate_mengenfaktor(schritt.mengenfaktor)
        validate_preis(schritt.snapshot_kosten, label="Veredelungskosten")
        zwischensumme = _money(_d(schritt.snapshot_kosten) * _d(schritt.mengenfaktor))
        veredelung_summe += zwischensumme
        veredelungen_ergebnis.append(
            VeredelungPositionErgebnis(
                veredelungsschritt_id=schritt.veredelungsschritt_id,
                bezeichnung=schritt.bezeichnung,
                reihenfolge=schritt.reihenfolge,
                kosten_je_stueck=schritt.snapshot_kosten,
                mengenfaktor=schritt.mengenfaktor,
                zwischensumme=float(zwischensumme),
            )
        )

    baugruppenpreis = _money(einzelteile_summe + kaufteile_summe + veredelung_summe)
    jahresumsatz = _money(baugruppenpreis * _d(jahresstueckzahl))

    investitionen_liste = investitionen or []
    investitionen_gesamt = sum(i.amount for i in investitionen_liste)

    return BaugruppeErgebnis(
        einzelteile_gesamt=float(einzelteile_summe),
        kaufteile_gesamt=float(kaufteile_summe),
        veredelung_gesamt=float(veredelung_summe),
        baugruppenpreis_je_stueck=float(baugruppenpreis),
        jahresstueckzahl=jahresstueckzahl,
        jahresumsatz=float(jahresumsatz),
        einzelteile=einzelteile_ergebnis,
        kaufteile=kaufteile_ergebnis,
        veredelungen=veredelungen_ergebnis,
        investitionen=investitionen_liste,
        investitionen_gesamt=investitionen_gesamt,
    )
