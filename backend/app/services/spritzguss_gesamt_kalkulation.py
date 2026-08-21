"""Gesamtkalkulation: Spritzguss + Veredelungsschritte.

FGK wird hier genau einmal auf der Basis
Maschinenkosten + Fertigungslohn + direkte Veredelungskosten berechnet
(nicht erneut auf bereits FGK-haltige Spritzguss-Herstellkosten).
SG&A (VVGK) und Profit folgen auf die so ermittelten Herstellkosten.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP


class GesamtValidationError(ValueError):
    """Ungültige Eingaben für die Gesamtkalkulation."""


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def _pct_to_rate(pct: float | Decimal) -> Decimal:
    return _d(pct) / Decimal("100")


@dataclass(frozen=True)
class VeredelungSchrittEingabe:
    veredelungsschritt_id: int
    bezeichnung: str
    veredelungsart: str
    reihenfolge: int
    aktiv: bool
    mengenfaktor: float
    kosten_inkl_ausschuss: float  # direkte Veredelungskosten (ohne FGK)


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
    fgk_basis: float
    werkzeugkostenanteil: float
    veredelung_schritte: list[VeredelungSchrittErgebnis]
    veredelung_gesamt: float
    gesamte_herstellkosten: float
    endpreis_je_stueck: float
    applied_fgk_pct: float
    applied_vvgk_pct: float
    applied_gewinn_pct: float
    applied_skonto_pct: float

    def to_dict(self) -> dict:
        return {
            "spritzguss_herstellkosten": self.spritzguss_herstellkosten,
            "spritzguss_verkaufspreis": self.spritzguss_verkaufspreis,
            "veredelung_gesamt": self.veredelung_gesamt,
            "gesamte_herstellkosten": self.gesamte_herstellkosten,
            "fgk_basis": self.fgk_basis,
            "fertigungsgemeinkosten": self.fertigungsgemeinkosten,
            "vvgk": self.vvgk,
            "selbstkosten": self.selbstkosten,
            "gewinn": self.gewinn,
            "nettoverkaufspreis": self.nettoverkaufspreis,
            "skonto": self.skonto,
            "endpreis_je_stueck": self.endpreis_je_stueck,
            "applied_fgk_pct": self.applied_fgk_pct,
            "applied_vvgk_pct": self.applied_vvgk_pct,
            "applied_gewinn_pct": self.applied_gewinn_pct,
            "applied_skonto_pct": self.applied_skonto_pct,
            "veredelung_schritte": [s.to_dict() for s in self.veredelung_schritte],
        }

    def as_ergebnisuebersicht(self) -> dict[str, float]:
        """Fachliche Kurzübersicht für die Ergebnisanzeige (ohne Investitionsanteil)."""
        return {
            "spritzguss_herstellkosten": self.spritzguss_herstellkosten,
            "veredelung_gesamt": self.veredelung_gesamt,
            "fgk_basis": self.fgk_basis,
            "fertigungsgemeinkosten": self.fertigungsgemeinkosten,
            "gesamte_herstellkosten": self.gesamte_herstellkosten,
            "vvgk": self.vvgk,
            "selbstkosten": self.selbstkosten,
            "gewinn": self.gewinn,
            "nettoverkaufspreis_gesamt": self.nettoverkaufspreis,
            "skonto": self.skonto,
            "endpreis_je_stueck": self.endpreis_je_stueck,
            "fgk_pct": self.applied_fgk_pct,
            "vvgk_pct": self.applied_vvgk_pct,
            "gewinn_pct": self.applied_gewinn_pct,
            "skonto_pct": self.applied_skonto_pct,
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
    *,
    fgk_pct: float,
    vvgk_pct: float = 0,
    gewinn_pct: float = 0,
    skonto_pct: float = 0,
) -> GesamtErgebnis:
    """Kombiniert Spritzguss-Direktkosten mit Veredelung und wendet Zuschläge einmal an.

    Erwartet vom Spritzguss-Ergebnis die Komponenten
    materialkosten_gesamt, maschinenkosten, fertigungslohn (ohne eingebettete
    Veredelungs-FGK). FGK wird neu auf Maschine + Lohn + Veredelung berechnet.
    """
    spritzguss_vp = float(spritzguss_ergebnis.get("verkaufspreis", 0))

    material = _d(spritzguss_ergebnis.get("materialkosten_gesamt", 0))
    maschinenkosten = _d(spritzguss_ergebnis.get("maschinenkosten", 0))
    fertigungslohn = _d(spritzguss_ergebnis.get("fertigungslohn", 0))

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

    # FGK-Basis: Maschine + Lohn + direkte Veredelung (kein Material/Kaufteil/Werkzeug)
    fgk_basis = _money(maschinenkosten + fertigungslohn + veredelung_gesamt)
    fertigungsgemeinkosten = _money(fgk_basis * _pct_to_rate(fgk_pct))

    gesamte_hk = _money(
        material + maschinenkosten + fertigungslohn + veredelung_gesamt + fertigungsgemeinkosten
    )
    # Spritzguss-HK ohne Veredelung, aber mit FGK nur auf Maschine+Lohn (Anzeige)
    spritzguss_hk = _money(
        material
        + maschinenkosten
        + fertigungslohn
        + _money((maschinenkosten + fertigungslohn) * _pct_to_rate(fgk_pct))
    )

    vvgk = _money(gesamte_hk * _pct_to_rate(vvgk_pct))
    selbstkosten = _money(gesamte_hk + vvgk)
    gewinn = _money(selbstkosten * _pct_to_rate(gewinn_pct))
    nettoverkaufspreis = _money(selbstkosten + gewinn)
    skonto = _money(nettoverkaufspreis * _pct_to_rate(skonto_pct))
    endpreis = _money(nettoverkaufspreis + skonto)

    return GesamtErgebnis(
        spritzguss_herstellkosten=float(spritzguss_hk),
        spritzguss_verkaufspreis=spritzguss_vp,
        werkzeug_einmalzahlung=0.0,
        vvgk=float(vvgk),
        selbstkosten=float(selbstkosten),
        gewinn=float(gewinn),
        nettoverkaufspreis=float(nettoverkaufspreis),
        skonto=float(skonto),
        materialkosten_gesamt=float(material),
        maschinenkosten=float(maschinenkosten),
        fertigungslohn=float(fertigungslohn),
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        fgk_basis=float(fgk_basis),
        werkzeugkostenanteil=0.0,
        veredelung_schritte=ergebnis_schritte,
        veredelung_gesamt=float(veredelung_gesamt),
        gesamte_herstellkosten=float(gesamte_hk),
        endpreis_je_stueck=float(endpreis),
        applied_fgk_pct=float(fgk_pct),
        applied_vvgk_pct=float(vvgk_pct),
        applied_gewinn_pct=float(gewinn_pct),
        applied_skonto_pct=float(skonto_pct),
    )
