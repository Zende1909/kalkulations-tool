"""Gesamtkalkulation: Spritzguss + Veredelungsschritte."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


class GesamtValidationError(ValueError):
    """Ungültige Eingaben für die Gesamtkalkulation."""


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class VeredelungSchrittEingabe:
    veredelungsschritt_id: int
    bezeichnung: str
    veredelungsart: str
    reihenfolge: int
    aktiv: bool
    mengenfaktor: float
    kosten_inkl_ausschuss: float


@dataclass(frozen=True)
class VeredelungSchrittErgebnis:
    veredelungsschritt_id: int
    bezeichnung: str
    veredelungsart: str
    reihenfolge: int
    aktiv: bool
    mengenfaktor: float
    kosten_inkl_ausschuss: float
    kosten_gesamt: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class GesamtErgebnis:
    spritzguss_herstellkosten: float
    spritzguss_verkaufspreis: float
    werkzeug_einmalzahlung: float
    vvgk: float
    selbstkosten: float
    gewinn: float
    nettoverkaufspreis: float
    skonto: float
    materialkosten_gesamt: float
    maschinenkosten: float
    fertigungslohn: float
    fertigungsgemeinkosten: float
    werkzeugkostenanteil: float
    veredelung_schritte: list[VeredelungSchrittErgebnis]
    veredelung_gesamt: float
    gesamte_herstellkosten: float
    endpreis_je_stueck: float

    def to_dict(self) -> dict:
        return {
            "spritzguss_herstellkosten": self.spritzguss_herstellkosten,
            "spritzguss_verkaufspreis": self.spritzguss_verkaufspreis,
            "veredelung_gesamt": self.veredelung_gesamt,
            "gesamte_herstellkosten": self.gesamte_herstellkosten,
            "endpreis_je_stueck": self.endpreis_je_stueck,
            "veredelung_schritte": [s.to_dict() for s in self.veredelung_schritte],
        }

    def as_ergebnisuebersicht(self) -> dict[str, float]:
        """Fachliche Kurzübersicht für die Ergebnisanzeige (ohne Einzelposten)."""
        return {
            "spritzguss_herstellkosten": self.spritzguss_herstellkosten,
            "veredelung_gesamt": self.veredelung_gesamt,
            "gesamte_herstellkosten": self.gesamte_herstellkosten,
            "vvgk": self.vvgk,
            "selbstkosten": self.selbstkosten,
            "gewinn": self.gewinn,
            "nettoverkaufspreis_gesamt": self.nettoverkaufspreis,
            "skonto": self.skonto,
            "endpreis_je_stueck": self.endpreis_je_stueck,
        }

    def as_veredelung_block(self) -> dict[str, float]:
        block: dict[str, float] = {"veredelung_gesamt": self.veredelung_gesamt}
        for schritt in sorted(self.veredelung_schritte, key=lambda s: s.reihenfolge):
            if schritt.aktiv:
                block[f"schritt_{schritt.reihenfolge}"] = schritt.kosten_gesamt
        return block


def validate_veredelung_zuordnung(
    reihenfolge: int,
    mengenfaktor: float,
) -> None:
    if reihenfolge < 1:
        raise GesamtValidationError("reihenfolge muss eine positive ganze Zahl >= 1 sein")
    if mengenfaktor < 0:
        raise GesamtValidationError("mengenfaktor darf nicht negativ sein")


def berechne_veredelung_schritt(
    schritt: VeredelungSchrittEingabe,
) -> VeredelungSchrittErgebnis:
    validate_veredelung_zuordnung(schritt.reihenfolge, schritt.mengenfaktor)
    unit = _money(_d(schritt.kosten_inkl_ausschuss))
    faktor = _d(schritt.mengenfaktor)
    kosten_gesamt = _money(unit * faktor) if schritt.aktiv else _money(Decimal("0"))
    return VeredelungSchrittErgebnis(
        veredelungsschritt_id=schritt.veredelungsschritt_id,
        bezeichnung=schritt.bezeichnung,
        veredelungsart=schritt.veredelungsart,
        reihenfolge=schritt.reihenfolge,
        aktiv=schritt.aktiv,
        mengenfaktor=float(faktor),
        kosten_inkl_ausschuss=float(unit),
        kosten_gesamt=float(kosten_gesamt),
    )


def berechne_gesamt(
    spritzguss_ergebnis: dict,
    veredelung_schritte: list[VeredelungSchrittEingabe],
) -> GesamtErgebnis:
    """Kombiniert Spritzguss-Ergebnis mit Veredelungsschritten."""
    spritzguss_vp = float(spritzguss_ergebnis["verkaufspreis"])
    werkzeug_einmal = float(spritzguss_ergebnis.get("werkzeug_einmalzahlung", 0))

    sorted_steps = sorted(veredelung_schritte, key=lambda s: s.reihenfolge)
    ergebnis_schritte: list[VeredelungSchrittErgebnis] = []
    veredelung_summe = Decimal("0")

    seen_ids: set[int] = set()
    for schritt in sorted_steps:
        if schritt.veredelungsschritt_id in seen_ids:
            raise GesamtValidationError(
                f"Veredelungsschritt {schritt.veredelungsschritt_id} ist doppelt zugeordnet"
            )
        seen_ids.add(schritt.veredelungsschritt_id)
        ergebnis = berechne_veredelung_schritt(schritt)
        ergebnis_schritte.append(ergebnis)
        if ergebnis.aktiv:
            veredelung_summe += _d(ergebnis.kosten_gesamt)

    veredelung_gesamt = _money(veredelung_summe)
    spritzguss_hk = float(spritzguss_ergebnis["herstellkosten"])
    gesamte_hk = _money(_d(spritzguss_hk) + veredelung_gesamt)
    # Variante A (aktuell): Veredelung wird auf den fertigen Spritzguss-Verkaufspreis addiert.
    endpreis = _money(_d(spritzguss_vp) + veredelung_gesamt)

    return GesamtErgebnis(
        spritzguss_herstellkosten=spritzguss_hk,
        spritzguss_verkaufspreis=spritzguss_vp,
        werkzeug_einmalzahlung=werkzeug_einmal,
        vvgk=float(spritzguss_ergebnis.get("vvgk", 0)),
        selbstkosten=float(spritzguss_ergebnis.get("selbstkosten", 0)),
        gewinn=float(spritzguss_ergebnis.get("gewinn", 0)),
        nettoverkaufspreis=float(spritzguss_ergebnis.get("nettoverkaufspreis", 0)),
        skonto=float(spritzguss_ergebnis.get("skonto", 0)),
        materialkosten_gesamt=float(spritzguss_ergebnis.get("materialkosten_gesamt", 0)),
        maschinenkosten=float(spritzguss_ergebnis.get("maschinenkosten", 0)),
        fertigungslohn=float(spritzguss_ergebnis.get("fertigungslohn", 0)),
        fertigungsgemeinkosten=float(spritzguss_ergebnis.get("fertigungsgemeinkosten", 0)),
        werkzeugkostenanteil=float(spritzguss_ergebnis.get("werkzeugkostenanteil", 0)),
        veredelung_schritte=ergebnis_schritte,
        veredelung_gesamt=float(veredelung_gesamt),
        gesamte_herstellkosten=float(gesamte_hk),
        endpreis_je_stueck=float(endpreis),
    )
