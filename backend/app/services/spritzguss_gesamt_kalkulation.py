"""Gesamtkalkulation: Spritzguss + Veredelungsschritte.

Ausschussmodell
---------------
- Materialausschuss: lokal in der Spritzguss-Kalkulation.
- Veredelungsausschuss (z. B. Kaschieren): Ausbeutekette
  ``(Vorprodukt + Prozess_vor) / (1 − q)`` – einmal pro Schritt,
  inkl. Kosten bereits hergestellter Vorprodukte.
- FGK genau einmal auf Maschine + Lohn + direkte Veredelungskosten *vor*
  Ausschuss (keine Doppelanwendung desselben Ausschusses auf die FGK-Basis).
- SG&A (VVGK) und Profit folgen auf die so ermittelten Herstellkosten.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.services.process_yield import apply_process_yield


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
    kosten_inkl_ausschuss: float  # Eigenkosten inkl. Prozessausschuss (Anzeige)
    # Für Ausbeutekette; wenn gesetzt, wird kaskadiert.
    kosten_vor_ausschuss: float | None = None
    ausschussquote_pct: float = 0.0


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
    kosten_vor_ausschuss: float = 0.0
    ausschussquote_pct: float = 0.0
    vorprodukt_eingang: float = 0.0
    ausschuss_zuschlag: float = 0.0
    kosten_nach_ausbeute: float = 0.0

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
    materialkosten_vor_ausschuss: float | None = None
    material_ausschussquote_pct: float | None = None
    applied_mgk_pct: float | None = None
    material_nominierung: str | None = None

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
            "materialkosten_gesamt": self.materialkosten_gesamt,
            "materialkosten_vor_ausschuss": self.materialkosten_vor_ausschuss,
            "material_ausschussquote_pct": self.material_ausschussquote_pct,
            "applied_mgk_pct": self.applied_mgk_pct,
            "material_nominierung": self.material_nominierung,
            "maschinenkosten": self.maschinenkosten,
            "fertigungslohn": self.fertigungslohn,
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
    vor = (
        float(_money(_d(schritt.kosten_vor_ausschuss) * faktor))
        if schritt.kosten_vor_ausschuss is not None and schritt.aktiv
        else float(kosten_gesamt)
    )
    return VeredelungSchrittErgebnis(
        veredelungsschritt_id=schritt.veredelungsschritt_id,
        bezeichnung=schritt.bezeichnung,
        veredelungsart=schritt.veredelungsart,
        reihenfolge=schritt.reihenfolge,
        aktiv=schritt.aktiv,
        mengenfaktor=float(faktor),
        kosten_inkl_ausschuss=float(unit),
        kosten_gesamt=float(kosten_gesamt),
        kosten_vor_ausschuss=vor if schritt.aktiv else 0.0,
        ausschussquote_pct=schritt.ausschussquote_pct if schritt.aktiv else 0.0,
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
    """Kombiniert Spritzguss-Direktkosten mit Veredelung und wendet Zuschläge einmal an."""
    spritzguss_vp = float(spritzguss_ergebnis.get("verkaufspreis", 0))

    material = _d(spritzguss_ergebnis.get("materialkosten_gesamt", 0))
    maschinenkosten = _d(spritzguss_ergebnis.get("maschinenkosten", 0))
    fertigungslohn = _d(spritzguss_ergebnis.get("fertigungslohn", 0))

    sorted_steps = sorted(veredelung_schritte, key=lambda s: s.reihenfolge)
    ergebnis_schritte: list[VeredelungSchrittErgebnis] = []
    process_direct_sum = Decimal("0")
    # Laufende Fertigungskosten vor FGK (Material inkl. Materialausschuss + Maschine + Lohn)
    running = _money(material + maschinenkosten + fertigungslohn)

    seen_ids: set[int] = set()
    for schritt in sorted_steps:
        if schritt.veredelungsschritt_id in seen_ids:
            raise GesamtValidationError(
                f"Veredelungsschritt {schritt.veredelungsschritt_id} ist doppelt zugeordnet"
            )
        seen_ids.add(schritt.veredelungsschritt_id)

        if not schritt.aktiv:
            ergebnis_schritte.append(berechne_veredelung_schritt(schritt))
            continue

        faktor = _d(schritt.mengenfaktor)
        vorprodukt_eingang = float(running)

        if schritt.kosten_vor_ausschuss is not None:
            vor = _money(_d(schritt.kosten_vor_ausschuss) * faktor)
            try:
                output, surcharge, _yf = apply_process_yield(
                    running, vor, schritt.ausschussquote_pct
                )
            except ValueError as exc:
                raise GesamtValidationError(str(exc)) from exc
            process_direct_sum += vor
            beitrag = _money(output - running)
            running = output
            unit_inkl = _money(_d(schritt.kosten_inkl_ausschuss))
            ergebnis_schritte.append(
                VeredelungSchrittErgebnis(
                    veredelungsschritt_id=schritt.veredelungsschritt_id,
                    bezeichnung=schritt.bezeichnung,
                    veredelungsart=schritt.veredelungsart,
                    reihenfolge=schritt.reihenfolge,
                    aktiv=True,
                    mengenfaktor=float(faktor),
                    kosten_inkl_ausschuss=float(unit_inkl),
                    kosten_gesamt=float(beitrag),
                    kosten_vor_ausschuss=float(vor),
                    ausschussquote_pct=schritt.ausschussquote_pct,
                    vorprodukt_eingang=vorprodukt_eingang,
                    ausschuss_zuschlag=float(surcharge),
                    kosten_nach_ausbeute=float(output),
                )
            )
        else:
            # Legacy: nur Eigenkosten inkl. Ausschuss addieren (keine Vorprodukt-Kaskade)
            unit = _money(_d(schritt.kosten_inkl_ausschuss))
            kosten_gesamt = _money(unit * faktor)
            process_direct_sum += kosten_gesamt
            running = _money(running + kosten_gesamt)
            ergebnis_schritte.append(
                VeredelungSchrittErgebnis(
                    veredelungsschritt_id=schritt.veredelungsschritt_id,
                    bezeichnung=schritt.bezeichnung,
                    veredelungsart=schritt.veredelungsart,
                    reihenfolge=schritt.reihenfolge,
                    aktiv=True,
                    mengenfaktor=float(faktor),
                    kosten_inkl_ausschuss=float(unit),
                    kosten_gesamt=float(kosten_gesamt),
                    kosten_vor_ausschuss=float(kosten_gesamt),
                    ausschussquote_pct=0.0,
                    vorprodukt_eingang=vorprodukt_eingang,
                    ausschuss_zuschlag=0.0,
                    kosten_nach_ausbeute=float(running),
                )
            )

    veredelung_gesamt = _money(running - material - maschinenkosten - fertigungslohn)

    # FGK-Basis: Maschine + Lohn + direkte Veredelung *vor* Ausschuss
    fgk_basis = _money(maschinenkosten + fertigungslohn + process_direct_sum)
    fertigungsgemeinkosten = _money(fgk_basis * _pct_to_rate(fgk_pct))

    gesamte_hk = _money(running + fertigungsgemeinkosten)
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

    mat_vor = spritzguss_ergebnis.get("materialkosten")
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
        materialkosten_vor_ausschuss=float(mat_vor) if mat_vor is not None else None,
        material_ausschussquote_pct=(
            float(spritzguss_ergebnis["ausschussquote_pct"])
            if spritzguss_ergebnis.get("ausschussquote_pct") is not None
            else None
        ),
        applied_mgk_pct=(
            float(spritzguss_ergebnis["applied_mgk_pct"])
            if spritzguss_ergebnis.get("applied_mgk_pct") is not None
            else None
        ),
        material_nominierung=spritzguss_ergebnis.get("material_nominierung"),
    )
