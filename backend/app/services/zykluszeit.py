"""Zykluszeitvorschlag nach IKET (Kühlzeitkalkulation).

Referenz: ``IKET-Kostenkalkulation - Dosing Guide.xlsx``, Blatt
``Zykluszeitbestimmung`` sowie ``IKET-Kostenkalkulation-von-Kunststoff-
Formteilen-Version-2024.pdf``, Seite 83.

Variante 1 (Entformungstemperatur = mittlere Wandtemperatur)::

    t_K = s² / (a · π²) · ln( 8/π² · (T_M − T_W) / (T_E − T_W) )

Variante 2 (Entformungstemperatur = Temperatur in Formteilmitte)::

    t_K = s² / (a · π²) · ln( 4/π  · (T_M − T_W) / (T_E − T_W) )

Es wird durchgehend ungerundet in ``float`` gerechnet; gerundet wird nur in der
Anzeige beziehungsweise im Export.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

VARIANTE_MITTLERE_WANDTEMPERATUR = 1
VARIANTE_FORMTEILMITTE = 2
UNTERSTUETZTE_VARIANTEN = (VARIANTE_MITTLERE_WANDTEMPERATUR, VARIANTE_FORMTEILMITTE)
DEFAULT_VARIANTE = VARIANTE_FORMTEILMITTE

DEFAULT_KUEHLFAKTOR = 1.5
DEFAULT_KOMPONENTEN = 1

# Nebenzeiten-Defaults exakt aus dem IKET-Blatt "Zykluszeitbestimmung" (B26:B34).
NEBENZEIT_FELDER: tuple[tuple[str, str, float], ...] = (
    ("werkzeug_schliessen_s", "Werkzeug schließen", 2.0),
    ("duese_anlegen_s", "Düsen anlegen", 1.0),
    ("einspritzen_s", "Einspritzen", 2.0),
    ("werkzeug_oeffnen_s", "Werkzeug öffnen", 2.0),
    ("auswerfen_s", "Auswerfen/Entnahme", 2.5),
    ("kernzug_s", "Kernzug/Schieber", 1.0),
    ("ausschrauben_s", "Ausschrauben", 0.0),
    ("einlegen_s", "Einlegen", 2.0),
    ("ausblasen_s", "Ausblasen", 0.0),
)
NEBENZEIT_KEYS: tuple[str, ...] = tuple(key for key, _label, _default in NEBENZEIT_FELDER)
NEBENZEIT_LABELS: dict[str, str] = {key: label for key, label, _default in NEBENZEIT_FELDER}
DEFAULT_NEBENZEITEN: dict[str, float] = {
    key: default for key, _label, default in NEBENZEIT_FELDER
}


def default_nebenzeiten() -> dict[str, float]:
    return dict(DEFAULT_NEBENZEITEN)


@dataclass
class ZykluszeitInput:
    wandstaerke_mm: float | None
    schmelzdichte_kg_m3: float | None
    waermekapazitaet_j_kg_k: float | None
    waermeleitfaehigkeit_w_m_k: float | None
    werkzeugtemperatur_c: float | None
    schmelzetemperatur_c: float | None
    entformungstemperatur_c: float | None
    variante: int = DEFAULT_VARIANTE
    kuehlfaktor: float = DEFAULT_KUEHLFAKTOR
    komponenten: int = DEFAULT_KOMPONENTEN
    nebenzeiten: dict[str, float] = field(default_factory=default_nebenzeiten)


@dataclass
class ZykluszeitResult:
    berechenbar: bool
    hinweis: str | None = None
    variante: int | None = None
    kuehlfaktor: float | None = None
    komponenten: int | None = None
    wandstaerke_mm: float | None = None
    schmelzdichte_kg_m3: float | None = None
    waermekapazitaet_j_kg_k: float | None = None
    waermeleitfaehigkeit_w_m_k: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    vorfaktor_s: float | None = None
    variantenfaktor: float | None = None
    temperaturquotient: float | None = None
    ln_argument: float | None = None
    ln_wert: float | None = None
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeiten: dict[str, float] = field(default_factory=dict)
    nebenzeiten_gesamt_s: float | None = None
    gesamtzykluszeit_s: float | None = None

    def as_dict(self) -> dict:
        return {
            "berechenbar": self.berechenbar,
            "hinweis": self.hinweis,
            "variante": self.variante,
            "kuehlfaktor": self.kuehlfaktor,
            "komponenten": self.komponenten,
            "wandstaerke_mm": self.wandstaerke_mm,
            "schmelzdichte_kg_m3": self.schmelzdichte_kg_m3,
            "waermekapazitaet_j_kg_k": self.waermekapazitaet_j_kg_k,
            "waermeleitfaehigkeit_w_m_k": self.waermeleitfaehigkeit_w_m_k,
            "werkzeugtemperatur_c": self.werkzeugtemperatur_c,
            "schmelzetemperatur_c": self.schmelzetemperatur_c,
            "entformungstemperatur_c": self.entformungstemperatur_c,
            "temperaturleitfaehigkeit_m2_s": self.temperaturleitfaehigkeit_m2_s,
            "vorfaktor_s": self.vorfaktor_s,
            "variantenfaktor": self.variantenfaktor,
            "temperaturquotient": self.temperaturquotient,
            "ln_argument": self.ln_argument,
            "ln_wert": self.ln_wert,
            "optimale_kuehlzeit_s": self.optimale_kuehlzeit_s,
            "kuehlzeit_s": self.kuehlzeit_s,
            "nebenzeiten": dict(self.nebenzeiten),
            "nebenzeiten_gesamt_s": self.nebenzeiten_gesamt_s,
            "gesamtzykluszeit_s": self.gesamtzykluszeit_s,
        }


def _nicht_berechenbar(hinweis: str) -> ZykluszeitResult:
    return ZykluszeitResult(berechenbar=False, hinweis=hinweis)


def temperaturleitfaehigkeit(
    *,
    waermeleitfaehigkeit_w_m_k: float,
    schmelzdichte_kg_m3: float,
    waermekapazitaet_j_kg_k: float,
) -> float:
    """α = λ / (ρ · c_p) in m²/s."""
    return waermeleitfaehigkeit_w_m_k / (schmelzdichte_kg_m3 * waermekapazitaet_j_kg_k)


def variantenfaktor(variante: int) -> float:
    if variante == VARIANTE_MITTLERE_WANDTEMPERATUR:
        return 8.0 / math.pi**2
    return 4.0 / math.pi


def normalisiere_nebenzeiten(werte: dict[str, float] | None) -> dict[str, float]:
    quelle = werte or {}
    return {
        key: float(quelle.get(key) if quelle.get(key) is not None else DEFAULT_NEBENZEITEN[key])
        for key in NEBENZEIT_KEYS
    }


def summe_nebenzeiten(werte: dict[str, float] | None) -> float:
    return float(sum(normalisiere_nebenzeiten(werte).values()))


def _pruefe_eingaben(inp: ZykluszeitInput) -> str | None:
    if inp.komponenten is not None and inp.komponenten > 1:
        return (
            "Automatische Kühlzeitberechnung ist nur für 1-Komponenten-Spritzguss möglich. "
            "Bei Mehrkomponententeilen muss die Kühlzeit über eine Füllstudie ermittelt und "
            "die Zykluszeit manuell eingetragen werden."
        )
    if inp.variante not in UNTERSTUETZTE_VARIANTEN:
        return "Ungültige Berechnungsvariante: nur Variante 1 oder 2 nach IKET sind zulässig."

    fehlend = [
        label
        for label, wert in (
            ("äquivalente Wandstärke", inp.wandstaerke_mm),
            ("Schmelzdichte", inp.schmelzdichte_kg_m3),
            ("spezifische Wärmekapazität", inp.waermekapazitaet_j_kg_k),
            ("Wärmeleitfähigkeit", inp.waermeleitfaehigkeit_w_m_k),
            ("Werkzeugoberflächentemperatur", inp.werkzeugtemperatur_c),
            ("Schmelzetemperatur", inp.schmelzetemperatur_c),
            ("Entformungstemperatur", inp.entformungstemperatur_c),
        )
        if wert is None
    ]
    if fehlend:
        return "Für den Zykluszeitvorschlag fehlen: " + ", ".join(fehlend) + "."

    if not all(
        math.isfinite(float(wert))
        for wert in (
            inp.wandstaerke_mm,
            inp.schmelzdichte_kg_m3,
            inp.waermekapazitaet_j_kg_k,
            inp.waermeleitfaehigkeit_w_m_k,
            inp.werkzeugtemperatur_c,
            inp.schmelzetemperatur_c,
            inp.entformungstemperatur_c,
            inp.kuehlfaktor,
        )
    ):
        return "Ungültige Zahlenwerte für den Zykluszeitvorschlag."

    if float(inp.wandstaerke_mm) <= 0:
        return "Die äquivalente Wandstärke muss größer als 0 mm sein."
    nicht_positiv = [
        label
        for label, wert in (
            ("Schmelzdichte", inp.schmelzdichte_kg_m3),
            ("spezifische Wärmekapazität", inp.waermekapazitaet_j_kg_k),
            ("Wärmeleitfähigkeit", inp.waermeleitfaehigkeit_w_m_k),
        )
        if float(wert) <= 0
    ]
    if nicht_positiv:
        return (
            "Diese Materialkennwerte müssen größer als 0 sein: " + ", ".join(nicht_positiv) + "."
        )
    if float(inp.kuehlfaktor) <= 0:
        return "Der Zuschlagfaktor für die Werkzeugkühlung muss größer als 0 sein."

    t_w = float(inp.werkzeugtemperatur_c)
    t_e = float(inp.entformungstemperatur_c)
    t_m = float(inp.schmelzetemperatur_c)
    if not (t_w < t_e < t_m):
        return (
            "Ungültige Temperaturreihenfolge: es muss Werkzeugoberflächentemperatur "
            f"({t_w:g} °C) < Entformungstemperatur ({t_e:g} °C) < Schmelzetemperatur "
            f"({t_m:g} °C) gelten."
        )

    negative = [
        NEBENZEIT_LABELS[key]
        for key, wert in normalisiere_nebenzeiten(inp.nebenzeiten).items()
        if wert < 0
    ]
    if negative:
        return "Nebenzeiten dürfen nicht negativ sein: " + ", ".join(negative) + "."
    return None


def berechne_zykluszeit(inp: ZykluszeitInput) -> ZykluszeitResult:
    """Berechnet den Zykluszeitvorschlag oder liefert einen verständlichen Hinweis."""
    nebenzeiten = normalisiere_nebenzeiten(inp.nebenzeiten)
    fehler = _pruefe_eingaben(inp)
    if fehler is not None:
        result = _nicht_berechenbar(fehler)
        result.nebenzeiten = nebenzeiten
        result.nebenzeiten_gesamt_s = float(sum(nebenzeiten.values()))
        result.komponenten = inp.komponenten
        result.variante = inp.variante
        result.kuehlfaktor = inp.kuehlfaktor
        result.wandstaerke_mm = inp.wandstaerke_mm
        return result

    alpha = temperaturleitfaehigkeit(
        waermeleitfaehigkeit_w_m_k=float(inp.waermeleitfaehigkeit_w_m_k),
        schmelzdichte_kg_m3=float(inp.schmelzdichte_kg_m3),
        waermekapazitaet_j_kg_k=float(inp.waermekapazitaet_j_kg_k),
    )
    if alpha <= 0:
        return _nicht_berechenbar("Die Temperaturleitfähigkeit muss größer als 0 sein.")

    wandstaerke_m = float(inp.wandstaerke_mm) / 1000.0
    vorfaktor = wandstaerke_m**2 / (alpha * math.pi**2)
    faktor = variantenfaktor(inp.variante)
    quotient = (float(inp.schmelzetemperatur_c) - float(inp.werkzeugtemperatur_c)) / (
        float(inp.entformungstemperatur_c) - float(inp.werkzeugtemperatur_c)
    )
    ln_argument = faktor * quotient
    if ln_argument <= 0:
        return _nicht_berechenbar(
            "Das Logarithmusargument der Kühlzeitformel ist nicht positiv – bitte die "
            "Temperaturen prüfen."
        )

    ln_wert = math.log(ln_argument)
    optimale_kuehlzeit = vorfaktor * ln_wert
    if optimale_kuehlzeit <= 0:
        return _nicht_berechenbar(
            "Die berechnete Kühlzeit ist nicht positiv – die Temperaturdifferenzen sind für "
            "die gewählte Variante zu gering."
        )

    kuehlzeit = optimale_kuehlzeit * float(inp.kuehlfaktor)
    nebenzeiten_gesamt = float(sum(nebenzeiten.values()))

    return ZykluszeitResult(
        berechenbar=True,
        hinweis=None,
        variante=int(inp.variante),
        kuehlfaktor=float(inp.kuehlfaktor),
        komponenten=int(inp.komponenten),
        wandstaerke_mm=float(inp.wandstaerke_mm),
        schmelzdichte_kg_m3=float(inp.schmelzdichte_kg_m3),
        waermekapazitaet_j_kg_k=float(inp.waermekapazitaet_j_kg_k),
        waermeleitfaehigkeit_w_m_k=float(inp.waermeleitfaehigkeit_w_m_k),
        werkzeugtemperatur_c=float(inp.werkzeugtemperatur_c),
        schmelzetemperatur_c=float(inp.schmelzetemperatur_c),
        entformungstemperatur_c=float(inp.entformungstemperatur_c),
        temperaturleitfaehigkeit_m2_s=alpha,
        vorfaktor_s=vorfaktor,
        variantenfaktor=faktor,
        temperaturquotient=quotient,
        ln_argument=ln_argument,
        ln_wert=ln_wert,
        optimale_kuehlzeit_s=optimale_kuehlzeit,
        kuehlzeit_s=kuehlzeit,
        nebenzeiten=nebenzeiten,
        nebenzeiten_gesamt_s=nebenzeiten_gesamt,
        gesamtzykluszeit_s=kuehlzeit + nebenzeiten_gesamt,
    )
