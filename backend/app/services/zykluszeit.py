"""Zykluszeit-Schätzung für 1K-Thermoplast-Spritzguss.

Ziel ist eine Größenordnung ("wie viele Sekunden?"), keine Prozessauslegung.
Deshalb gibt es genau drei Eingaben:

* Materialgruppe (am Material gepflegt) – liefert alle thermischen Kennwerte
  aus :mod:`app.services.material_thermik`
* äquivalente Wandstärke in mm
* Größenklasse des Teils – liefert die Summe der Nebenzeiten

Kühlzeit nach IKET (``Dosing Guide``, Blatt ``Zykluszeitbestimmung``, sowie
``IKET-Kostenkalkulation-von-Kunststoff-Formteilen-Version-2024.pdf``, S. 83),
Variante "Temperatur in Formteilmitte"::

    t_opt = s² / (a · π²) · ln( 4/π · (T_M − T_W) / (T_E − T_W) )
    t_K   = t_opt · 1,5      (Zuschlag für reale Werkzeugkühlung)
    t_Z   = t_K + Nebenzeiten

Es wird durchgehend ungerundet in ``float`` gerechnet; gerundet wird nur in der
Anzeige beziehungsweise im Export.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.material_thermik import ThermikDefaults, defaults_fuer_gruppe

# Zuschlag auf die theoretische Kühlzeit. Fester Erfahrungswert aus dem
# IKET-Blatt; bewusst nicht mehr pro Kalkulation einstellbar.
KUEHLFAKTOR = 1.5

# Obergrenze gegen offensichtliche Fehleingaben (mm).
MAX_WANDSTAERKE_MM = 50.0

# Nebenzeiten (Schließen, Einspritzen, Öffnen, Entnahme, Handling) als ein
# Summenwert je Größenklasse. Richtwerte: kleine Maschinen erreichen rund 6 s
# Grundzeit, das IKET-Beispiel eines mittleren Teils mit Kernzug und Einlegen
# summiert auf 12,5 s, Großteile mit langen Öffnungswegen liegen darüber.
GROESSENKLASSEN: tuple[tuple[str, str, float], ...] = (
    ("klein", "Klein – Handteil, einfache Entformung", 6.0),
    ("mittel", "Mittel – Standardteil, Roboterentnahme", 10.0),
    ("gross", "Groß – Großteil, Kernzug oder Einlegeteil", 16.0),
)
GROESSENKLASSEN_KEYS: tuple[str, ...] = tuple(key for key, _label, _s in GROESSENKLASSEN)
GROESSENKLASSEN_LABELS: dict[str, str] = {key: label for key, label, _s in GROESSENKLASSEN}
NEBENZEITEN_JE_KLASSE: dict[str, float] = {key: sekunden for key, _label, sekunden in GROESSENKLASSEN}
DEFAULT_GROESSENKLASSE = "mittel"


def normalisiere_groessenklasse(wert: str | None) -> str:
    if wert is None:
        return DEFAULT_GROESSENKLASSE
    key = str(wert).strip().lower()
    return key if key in NEBENZEITEN_JE_KLASSE else DEFAULT_GROESSENKLASSE


def default_nebenzeiten_s(groessenklasse: str | None = None) -> float:
    return NEBENZEITEN_JE_KLASSE[normalisiere_groessenklasse(groessenklasse)]


@dataclass
class ZykluszeitInput:
    """Eingaben des Vorschlags. ``nebenzeiten_gesamt_s=None`` nutzt die Klasse."""

    wandstaerke_mm: float | None
    materialgruppe: str | None
    groessenklasse: str | None = DEFAULT_GROESSENKLASSE
    nebenzeiten_gesamt_s: float | None = None


@dataclass
class ZykluszeitResult:
    berechenbar: bool
    hinweis: str | None = None
    wandstaerke_mm: float | None = None
    materialgruppe: str | None = None
    material_bezeichnung: str | None = None
    groessenklasse: str | None = None
    kuehlfaktor: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeiten_gesamt_s: float | None = None
    gesamtzykluszeit_s: float | None = None

    def as_dict(self) -> dict:
        return {
            "berechenbar": self.berechenbar,
            "hinweis": self.hinweis,
            "wandstaerke_mm": self.wandstaerke_mm,
            "materialgruppe": self.materialgruppe,
            "material_bezeichnung": self.material_bezeichnung,
            "groessenklasse": self.groessenklasse,
            "kuehlfaktor": self.kuehlfaktor,
            "temperaturleitfaehigkeit_m2_s": self.temperaturleitfaehigkeit_m2_s,
            "werkzeugtemperatur_c": self.werkzeugtemperatur_c,
            "schmelzetemperatur_c": self.schmelzetemperatur_c,
            "entformungstemperatur_c": self.entformungstemperatur_c,
            "optimale_kuehlzeit_s": self.optimale_kuehlzeit_s,
            "kuehlzeit_s": self.kuehlzeit_s,
            "nebenzeiten_gesamt_s": self.nebenzeiten_gesamt_s,
            "gesamtzykluszeit_s": self.gesamtzykluszeit_s,
        }


def temperaturleitfaehigkeit(thermik: ThermikDefaults) -> float:
    """α = λ / (ρ · c_p) in m²/s."""
    return thermik.waermeleitfaehigkeit_w_m_k / (
        thermik.schmelzdichte_kg_m3 * thermik.waermekapazitaet_j_kg_k
    )


def optimale_kuehlzeit(*, wandstaerke_mm: float, thermik: ThermikDefaults) -> float:
    """Theoretische Kühlzeit in s (IKET-Variante Formteilmitte, ohne Zuschlag)."""
    alpha = temperaturleitfaehigkeit(thermik)
    wandstaerke_m = wandstaerke_mm / 1000.0
    quotient = (thermik.schmelzetemperatur_c - thermik.werkzeugtemperatur_c) / (
        thermik.entformungstemperatur_c - thermik.werkzeugtemperatur_c
    )
    return (wandstaerke_m**2 / (alpha * math.pi**2)) * math.log((4.0 / math.pi) * quotient)


def _teilergebnis(hinweis: str, inp: ZykluszeitInput, nebenzeiten: float) -> ZykluszeitResult:
    return ZykluszeitResult(
        berechenbar=False,
        hinweis=hinweis,
        wandstaerke_mm=inp.wandstaerke_mm,
        materialgruppe=inp.materialgruppe,
        groessenklasse=normalisiere_groessenklasse(inp.groessenklasse),
        kuehlfaktor=KUEHLFAKTOR,
        nebenzeiten_gesamt_s=nebenzeiten,
    )


def berechne_zykluszeit(inp: ZykluszeitInput) -> ZykluszeitResult:
    """Liefert den Zykluszeitvorschlag oder einen verständlichen Hinweis."""
    klasse = normalisiere_groessenklasse(inp.groessenklasse)
    nebenzeiten = (
        float(inp.nebenzeiten_gesamt_s)
        if inp.nebenzeiten_gesamt_s is not None and math.isfinite(float(inp.nebenzeiten_gesamt_s))
        else default_nebenzeiten_s(klasse)
    )
    if nebenzeiten < 0:
        return _teilergebnis("Die Nebenzeiten dürfen nicht negativ sein.", inp, nebenzeiten)

    thermik = defaults_fuer_gruppe(inp.materialgruppe)
    if thermik is None:
        return _teilergebnis(
            "Für den Zykluszeitvorschlag fehlt die Materialgruppe. Bitte sie in den "
            "Materialstammdaten hinterlegen (z. B. PP, ABS, PA6).",
            inp,
            nebenzeiten,
        )

    if inp.wandstaerke_mm is None:
        return _teilergebnis(
            "Bitte die äquivalente Wandstärke des Teils eintragen.", inp, nebenzeiten
        )
    wandstaerke = float(inp.wandstaerke_mm)
    if not math.isfinite(wandstaerke) or wandstaerke <= 0:
        return _teilergebnis("Die Wandstärke muss größer als 0 mm sein.", inp, nebenzeiten)
    if wandstaerke > MAX_WANDSTAERKE_MM:
        return _teilergebnis(
            f"Die Wandstärke von {wandstaerke:g} mm ist für eine Abschätzung unrealistisch "
            f"(zulässig bis {MAX_WANDSTAERKE_MM:g} mm).",
            inp,
            nebenzeiten,
        )

    # Die Kennwerte stammen aus der internen Gruppentabelle; die folgenden
    # Prüfungen sichern sie gegen fehlerhafte Tabelleneinträge ab.
    if min(
        thermik.schmelzdichte_kg_m3,
        thermik.waermekapazitaet_j_kg_k,
        thermik.waermeleitfaehigkeit_w_m_k,
    ) <= 0 or not (
        thermik.werkzeugtemperatur_c < thermik.entformungstemperatur_c < thermik.schmelzetemperatur_c
    ):
        return _teilergebnis(
            f"Die hinterlegten Kennwerte der Materialgruppe {thermik.gruppe} sind ungültig.",
            inp,
            nebenzeiten,
        )

    t_opt = optimale_kuehlzeit(wandstaerke_mm=wandstaerke, thermik=thermik)
    if not math.isfinite(t_opt) or t_opt <= 0:
        return _teilergebnis(
            f"Für die Materialgruppe {thermik.gruppe} ergibt sich keine positive Kühlzeit.",
            inp,
            nebenzeiten,
        )

    kuehlzeit = t_opt * KUEHLFAKTOR
    return ZykluszeitResult(
        berechenbar=True,
        hinweis=None,
        wandstaerke_mm=wandstaerke,
        materialgruppe=thermik.gruppe,
        material_bezeichnung=thermik.bezeichnung,
        groessenklasse=klasse,
        kuehlfaktor=KUEHLFAKTOR,
        temperaturleitfaehigkeit_m2_s=temperaturleitfaehigkeit(thermik),
        werkzeugtemperatur_c=thermik.werkzeugtemperatur_c,
        schmelzetemperatur_c=thermik.schmelzetemperatur_c,
        entformungstemperatur_c=thermik.entformungstemperatur_c,
        optimale_kuehlzeit_s=t_opt,
        kuehlzeit_s=kuehlzeit,
        nebenzeiten_gesamt_s=nebenzeiten,
        gesamtzykluszeit_s=kuehlzeit + nebenzeiten,
    )
