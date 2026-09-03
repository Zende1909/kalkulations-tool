"""Zykluszeit-Schätzung für frühe Angebotskalkulation (1K-Thermoplast).

Ziel ist eine konservative Größenordnung für die Serienproduktion mit
konventionellen Serien-Stahlwerkzeugen – keine Prozesssimulation.

Eingaben:

* Materialkennwerte aus der bestehenden effektiven Datenquelle
  (:mod:`app.services.material_thermik` über die am Material gepflegte
  Materialgruppe bzw. deren Stammdaten)
* kühlzeitrelevante Wandstärke in mm (Intern: ``wandstaerke_mm``)
* Größenklasse des Teils bzw. ``auto`` aus Zuhaltekraft
* ``prozessaufwand`` (``normal`` / ``aufwendig``) – beeinflusst nur die
  *automatische* Nebenzeit

Kühlzeit nach IKET (``Dosing Guide``, Blatt ``Zykluszeitbestimmung``, sowie
``IKET-Kostenkalkulation-von-Kunststoff-Formteilen-Version-2024.pdf``, S. 83),
Variante 2 „Temperatur in Formteilmitte“. Fachlich primär für teilkristalline
Thermoplaste; für amorphe Materialien wird sie hier bewusst als vereinfachte
Näherung der Angebotskalkulation verwendet::

    t_opt = s² / (a · π²) · ln( 4/π · (T_M − T_W) / (T_E − T_W) )
    t_K   = t_opt · 1,5
    t_Z   = t_K + Nebenzeiten

Der Faktor 1,5 ist ein konservativer Kalkulationsfaktor für reale
Werkzeugtemperierung und geometrische Abweichungen – kein Benutzerfeld.

Priorität der Nebenzeit:

1. Manuelle Nebenzeit (``nebenzeiten_gesamt_s`` gesetzt) hat Vorrang und wird
   durch ``prozessaufwand`` *nicht* verändert.
2. Sonst automatische Nebenzeit aus Zuhaltekraft/Größenklasse; bei
   ``aufwendig`` pauschal +5 s (nur einmal, nur im automatischen Fallback).

Es wird durchgehend ungerundet in ``float`` gerechnet; gerundet wird nur in der
Anzeige beziehungsweise im Export.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services.material_thermik import (
    ThermikDefaults,
    defaults_fuer_gruppe,
    defaults_fuer_gruppe_db,
)

# Zuschlag auf die theoretische Kühlzeit. Konservativer Kalkulationsfaktor für
# reale Werkzeugtemperierung und geometrische Abweichungen in der frühen
# Angebotskalkulation mit Serien-Stahlwerkzeugen; bewusst kein Benutzerfeld.
KUEHLFAKTOR = 1.5

# Obergrenze gegen offensichtliche Fehleingaben (mm).
MAX_WANDSTAERKE_MM = 50.0

# Pauschaler Zuschlag auf die *automatische* Nebenzeit bei aufwendigem Prozess.
PROZESSAUFWAND_ZUSCHLAG_S = 5.0

PROZESSAUFWAND_NORMAL = "normal"
PROZESSAUFWAND_AUFWENDIG = "aufwendig"
PROZESSAUFWAND_WERTE: tuple[str, ...] = (PROZESSAUFWAND_NORMAL, PROZESSAUFWAND_AUFWENDIG)
DEFAULT_PROZESSAUFWAND = PROZESSAUFWAND_NORMAL

# Nebenzeiten (Schließen, Einspritzen, Öffnen, Entnahme, Handling) als ein
# Summenwert je Größenklasse – pauschale Erfahrungswerte für die frühe
# Angebotskalkulation. Parallel ablaufende Vorgänge werden nicht separat angesetzt.
GROESSENKLASSEN: tuple[tuple[str, str, float], ...] = (
    ("klein", "Klein – Handteil, einfache Entformung", 6.0),
    ("mittel", "Mittel – Standardteil, Roboterentnahme", 10.0),
    ("gross", "Groß – Großteil, Kernzug oder Einlegeteil", 16.0),
)
GROESSENKLASSEN_KEYS: tuple[str, ...] = tuple(key for key, _label, _s in GROESSENKLASSEN)
GROESSENKLASSEN_LABELS: dict[str, str] = {key: label for key, label, _s in GROESSENKLASSEN}
NEBENZEITEN_JE_KLASSE: dict[str, float] = {key: sekunden for key, _label, sekunden in GROESSENKLASSEN}
DEFAULT_GROESSENKLASSE = "mittel"

# Kavitätenzahl und Teilefläche wirken über die Zuhaltekraft: ein größeres
# Werkzeug braucht längere Öffnungs-, Auswerfer- und Einspritzwege.
GROESSENKLASSE_AUTO = "auto"
AUTO_SCHWELLEN_T: tuple[tuple[float, str], ...] = ((100.0, "klein"), (300.0, "mittel"))
AUSWAHLWERTE: tuple[str, ...] = (GROESSENKLASSE_AUTO, *GROESSENKLASSEN_KEYS)

# Bekannte Polymerklassen der Seed-/Stammdaten (ohne neue Benutzereingabe).
# Variante 2 ist IKET-seitig primär für teilkristalline Thermoplaste.
TEILKRISTALLINE_GRUPPEN: frozenset[str] = frozenset(
    {"POM", "PP", "PE-HD", "PE-LD", "PA6", "PA66", "PBT"}
)
AMORPHE_GRUPPEN: frozenset[str] = frozenset({"ABS", "SAN", "PS", "PC", "PMMA"})

MATERIALKLASSE_TEILKRISTALLIN = "teilkristallin"
MATERIALKLASSE_AMORPH = "amorph"
MATERIALKLASSE_UNBEKANNT = "unbekannt"

NEBENZEIT_QUELLE_MANUELL = "manuell"
NEBENZEIT_QUELLE_AUTOMATISCH = "automatisch"


def klasse_aus_zuhaltekraft(zuhaltekraft_t: float) -> str:
    for grenze, klasse in AUTO_SCHWELLEN_T:
        if zuhaltekraft_t <= grenze:
            return klasse
    return "gross"


def normalisiere_groessenklasse(wert: str | None) -> str:
    """Auswahlwert normalisieren; unbekannte Werte gelten als ``auto``."""
    if wert is None:
        return GROESSENKLASSE_AUTO
    key = str(wert).strip().lower()
    return key if key in AUSWAHLWERTE else GROESSENKLASSE_AUTO


def effektive_groessenklasse(wert: str | None, zuhaltekraft_t: float | None) -> str:
    """Löst ``auto`` gegen die Zuhaltekraft auf; ohne sie gilt der Default."""
    klasse = normalisiere_groessenklasse(wert)
    if klasse != GROESSENKLASSE_AUTO:
        return klasse
    if zuhaltekraft_t is None or not math.isfinite(float(zuhaltekraft_t)) or zuhaltekraft_t <= 0:
        return DEFAULT_GROESSENKLASSE
    return klasse_aus_zuhaltekraft(float(zuhaltekraft_t))


def normalisiere_prozessaufwand(wert: str | None) -> str:
    """Fehlende/unbekannte Werte → ``normal`` (Abwärtskompatibilität)."""
    if wert is None or (isinstance(wert, str) and not wert.strip()):
        return DEFAULT_PROZESSAUFWAND
    key = str(wert).strip().lower()
    return key if key in PROZESSAUFWAND_WERTE else DEFAULT_PROZESSAUFWAND


def materialklasse_fuer_gruppe(gruppe: str | None) -> str:
    if not gruppe:
        return MATERIALKLASSE_UNBEKANNT
    key = str(gruppe).strip().upper()
    if key in TEILKRISTALLINE_GRUPPEN:
        return MATERIALKLASSE_TEILKRISTALLIN
    if key in AMORPHE_GRUPPEN:
        return MATERIALKLASSE_AMORPH
    return MATERIALKLASSE_UNBEKANNT


def automatische_nebenzeiten_s(
    *,
    groessenklasse: str | None = None,
    zuhaltekraft_t: float | None = None,
    prozessaufwand: str | None = None,
) -> float:
    """Automatische Nebenzeit aus Größenklasse/Zuhaltekraft und Prozessaufwand."""
    basis = NEBENZEITEN_JE_KLASSE[effektive_groessenklasse(groessenklasse, zuhaltekraft_t)]
    if normalisiere_prozessaufwand(prozessaufwand) == PROZESSAUFWAND_AUFWENDIG:
        return basis + PROZESSAUFWAND_ZUSCHLAG_S
    return basis


def default_nebenzeiten_s(
    groessenklasse: str | None = None,
    zuhaltekraft_t: float | None = None,
    prozessaufwand: str | None = None,
) -> float:
    """Abwärtskompatibler Alias für die automatische Nebenzeit."""
    return automatische_nebenzeiten_s(
        groessenklasse=groessenklasse,
        zuhaltekraft_t=zuhaltekraft_t,
        prozessaufwand=prozessaufwand,
    )


def _manuelle_nebenzeiten(wert: float | None) -> float | None:
    """Liefert die manuelle Nebenzeit oder None, wenn der automatische Fallback gilt."""
    if wert is None:
        return None
    try:
        parsed = float(wert)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


@dataclass
class ZykluszeitInput:
    """Eingaben des Vorschlags.

    ``nebenzeiten_gesamt_s=None`` nutzt die automatische Nebenzeit.
    ``wandstaerke_mm`` ist die kühlzeitrelevante Wandstärke (mm).
    """

    wandstaerke_mm: float | None
    materialgruppe: str | None
    groessenklasse: str | None = GROESSENKLASSE_AUTO
    nebenzeiten_gesamt_s: float | None = None
    zuhaltekraft_t: float | None = None
    prozessaufwand: str | None = DEFAULT_PROZESSAUFWAND


@dataclass
class ZykluszeitResult:
    berechenbar: bool
    hinweis: str | None = None
    wandstaerke_mm: float | None = None
    materialgruppe: str | None = None
    material_bezeichnung: str | None = None
    materialklasse: str | None = None
    groessenklasse: str | None = None
    groessenklasse_auswahl: str | None = None
    zuhaltekraft_t: float | None = None
    prozessaufwand: str | None = None
    kuehlfaktor: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    # Interner Feldname aus Abwärtskompatibilität; fachlich = theoretische Kühlzeit.
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeiten_gesamt_s: float | None = None
    nebenzeit_quelle: str | None = None
    gesamtzykluszeit_s: float | None = None

    def as_dict(self) -> dict:
        return {
            "berechenbar": self.berechenbar,
            "hinweis": self.hinweis,
            "wandstaerke_mm": self.wandstaerke_mm,
            "materialgruppe": self.materialgruppe,
            "material_bezeichnung": self.material_bezeichnung,
            "materialklasse": self.materialklasse,
            "groessenklasse": self.groessenklasse,
            "groessenklasse_auswahl": self.groessenklasse_auswahl,
            "zuhaltekraft_t": self.zuhaltekraft_t,
            "prozessaufwand": self.prozessaufwand,
            "kuehlfaktor": self.kuehlfaktor,
            "temperaturleitfaehigkeit_m2_s": self.temperaturleitfaehigkeit_m2_s,
            "werkzeugtemperatur_c": self.werkzeugtemperatur_c,
            "schmelzetemperatur_c": self.schmelzetemperatur_c,
            "entformungstemperatur_c": self.entformungstemperatur_c,
            "optimale_kuehlzeit_s": self.optimale_kuehlzeit_s,
            "kuehlzeit_s": self.kuehlzeit_s,
            "nebenzeiten_gesamt_s": self.nebenzeiten_gesamt_s,
            "nebenzeit_quelle": self.nebenzeit_quelle,
            "gesamtzykluszeit_s": self.gesamtzykluszeit_s,
        }


def temperaturleitfaehigkeit(thermik: ThermikDefaults) -> float:
    """α = λ / (ρ · c_p) in m²/s."""
    return thermik.waermeleitfaehigkeit_w_m_k / (
        thermik.schmelzdichte_kg_m3 * thermik.waermekapazitaet_j_kg_k
    )


def _hinweis_materialklasse(materialklasse: str) -> str | None:
    if materialklasse == MATERIALKLASSE_AMORPH:
        return (
            "IKET-Variante 2 ist fachlich primär für teilkristalline Thermoplaste. "
            "Für amorphe Materialien wird der Vorschlag als vereinfachte Näherung "
            "der Angebotskalkulation angezeigt; die manuelle Zykluszeit bleibt nutzbar."
        )
    if materialklasse == MATERIALKLASSE_UNBEKANNT:
        return (
            "Die Materialklasse (amorph/teilkristallin) ist unbekannt. Der automatische "
            "Vorschlag basiert auf IKET-Variante 2 als vereinfachte Näherung; die manuelle "
            "Zykluszeit bleibt nutzbar."
        )
    return None


def _teilergebnis(
    hinweis: str,
    inp: ZykluszeitInput,
    *,
    nebenzeiten: float | None,
    nebenzeit_quelle: str | None,
    prozessaufwand: str,
    materialklasse: str | None = None,
) -> ZykluszeitResult:
    return ZykluszeitResult(
        berechenbar=False,
        hinweis=hinweis,
        wandstaerke_mm=inp.wandstaerke_mm,
        materialgruppe=inp.materialgruppe,
        materialklasse=materialklasse,
        groessenklasse=effektive_groessenklasse(inp.groessenklasse, inp.zuhaltekraft_t),
        groessenklasse_auswahl=normalisiere_groessenklasse(inp.groessenklasse),
        zuhaltekraft_t=inp.zuhaltekraft_t,
        prozessaufwand=prozessaufwand,
        kuehlfaktor=KUEHLFAKTOR,
        nebenzeiten_gesamt_s=nebenzeiten,
        nebenzeit_quelle=nebenzeit_quelle,
    )


def optimale_kuehlzeit(*, wandstaerke_mm: float, thermik: ThermikDefaults) -> float:
    """Theoretische Kühlzeit in s (IKET-Variante 2 Formteilmitte, ohne Zuschlag).

    Interner Name ``optimale_kuehlzeit`` bleibt aus Abwärtskompatibilität;
    fachlich handelt es sich um die theoretische Kühlzeit (keine Optimierung).
    """
    alpha = temperaturleitfaehigkeit(thermik)
    wandstaerke_m = wandstaerke_mm / 1000.0
    quotient = (thermik.schmelzetemperatur_c - thermik.werkzeugtemperatur_c) / (
        thermik.entformungstemperatur_c - thermik.werkzeugtemperatur_c
    )
    log_argument = (4.0 / math.pi) * quotient
    return (wandstaerke_m**2 / (alpha * math.pi**2)) * math.log(log_argument)


def berechne_zykluszeit(inp: ZykluszeitInput, db: Session | None = None) -> ZykluszeitResult:
    """Liefert den Zykluszeitvorschlag oder einen verständlichen Hinweis."""
    auswahl = normalisiere_groessenklasse(inp.groessenklasse)
    klasse = effektive_groessenklasse(auswahl, inp.zuhaltekraft_t)
    prozessaufwand = normalisiere_prozessaufwand(inp.prozessaufwand)

    manuell = _manuelle_nebenzeiten(inp.nebenzeiten_gesamt_s)
    if manuell is not None:
        nebenzeiten = manuell
        nebenzeit_quelle = NEBENZEIT_QUELLE_MANUELL
    else:
        nebenzeiten = automatische_nebenzeiten_s(
            groessenklasse=auswahl,
            zuhaltekraft_t=inp.zuhaltekraft_t,
            prozessaufwand=prozessaufwand,
        )
        nebenzeit_quelle = NEBENZEIT_QUELLE_AUTOMATISCH

    if not math.isfinite(nebenzeiten) or nebenzeiten < 0:
        return _teilergebnis(
            "Die Nebenzeit darf nicht negativ sein.",
            inp,
            nebenzeiten=nebenzeiten if math.isfinite(nebenzeiten) else None,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
        )

    if not math.isfinite(KUEHLFAKTOR) or KUEHLFAKTOR <= 0:
        return _teilergebnis(
            "Der interne Kühlfaktor ist ungültig.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
        )

    thermik = (
        defaults_fuer_gruppe_db(db, inp.materialgruppe)
        if db is not None
        else defaults_fuer_gruppe(inp.materialgruppe)
    )
    if thermik is None:
        return _teilergebnis(
            "Für den Zykluszeitvorschlag fehlen die Materialkennwerte. Bitte die "
            "Materialgruppe in den Materialstammdaten hinterlegen (z. B. PP, ABS, PA6).",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
        )

    materialklasse = materialklasse_fuer_gruppe(thermik.gruppe)

    if inp.wandstaerke_mm is None:
        return _teilergebnis(
            "Bitte die kühlzeitrelevante Wandstärke des Teils eintragen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )
    wandstaerke = float(inp.wandstaerke_mm)
    if not math.isfinite(wandstaerke) or wandstaerke <= 0:
        return _teilergebnis(
            "Die kühlzeitrelevante Wandstärke muss größer als 0 mm sein.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )
    if wandstaerke > MAX_WANDSTAERKE_MM:
        return _teilergebnis(
            f"Die Wandstärke von {wandstaerke:g} mm ist für eine Abschätzung unrealistisch "
            f"(zulässig bis {MAX_WANDSTAERKE_MM:g} mm).",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    t_m = float(thermik.schmelzetemperatur_c)
    t_e = float(thermik.entformungstemperatur_c)
    t_w = float(thermik.werkzeugtemperatur_c)
    if not all(math.isfinite(v) for v in (t_m, t_e, t_w)):
        return _teilergebnis(
            f"Die hinterlegten Temperaturen der Materialgruppe {thermik.gruppe} sind ungültig.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )
    if not (t_m > t_e):
        return _teilergebnis(
            "Die Schmelzetemperatur muss über der Entformungstemperatur liegen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )
    if not (t_e > t_w):
        return _teilergebnis(
            "Die Entformungstemperatur muss über der Werkzeugtemperatur liegen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    dens = float(thermik.schmelzdichte_kg_m3)
    cp = float(thermik.waermekapazitaet_j_kg_k)
    lam = float(thermik.waermeleitfaehigkeit_w_m_k)
    if min(dens, cp, lam) <= 0 or not all(math.isfinite(v) for v in (dens, cp, lam)):
        return _teilergebnis(
            f"Die hinterlegten Kennwerte der Materialgruppe {thermik.gruppe} sind ungültig.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    alpha = temperaturleitfaehigkeit(thermik)
    if not math.isfinite(alpha) or alpha <= 0:
        return _teilergebnis(
            "Die Temperaturleitfähigkeit muss größer als 0 sein.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    # T_E - T_W > 0 ist oben bereits sichergestellt; log_argument vor log() prüfen.
    log_argument = (4.0 / math.pi) * ((t_m - t_w) / (t_e - t_w))
    if not math.isfinite(log_argument) or log_argument <= 1:
        return _teilergebnis(
            "Mit den angegebenen Temperaturen kann keine gültige Kühlzeit berechnet werden.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    t_opt = optimale_kuehlzeit(wandstaerke_mm=wandstaerke, thermik=thermik)
    if not math.isfinite(t_opt) or t_opt < 0:
        return _teilergebnis(
            "Die berechnete Zykluszeit ist ungültig. Bitte Eingabewerte und Materialdaten prüfen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    kuehlzeit = t_opt * KUEHLFAKTOR
    if not math.isfinite(kuehlzeit) or kuehlzeit < 0:
        return _teilergebnis(
            "Die berechnete Zykluszeit ist ungültig. Bitte Eingabewerte und Materialdaten prüfen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    gesamt = kuehlzeit + nebenzeiten
    if not math.isfinite(gesamt) or gesamt <= 0:
        return _teilergebnis(
            "Die berechnete Zykluszeit ist ungültig. Bitte Eingabewerte und Materialdaten prüfen.",
            inp,
            nebenzeiten=nebenzeiten,
            nebenzeit_quelle=nebenzeit_quelle,
            prozessaufwand=prozessaufwand,
            materialklasse=materialklasse,
        )

    hinweis = _hinweis_materialklasse(materialklasse)
    return ZykluszeitResult(
        berechenbar=True,
        hinweis=hinweis,
        wandstaerke_mm=wandstaerke,
        materialgruppe=thermik.gruppe,
        material_bezeichnung=thermik.bezeichnung,
        materialklasse=materialklasse,
        groessenklasse=klasse,
        groessenklasse_auswahl=auswahl,
        zuhaltekraft_t=inp.zuhaltekraft_t,
        prozessaufwand=prozessaufwand,
        kuehlfaktor=KUEHLFAKTOR,
        temperaturleitfaehigkeit_m2_s=alpha,
        werkzeugtemperatur_c=t_w,
        schmelzetemperatur_c=t_m,
        entformungstemperatur_c=t_e,
        optimale_kuehlzeit_s=t_opt,
        kuehlzeit_s=kuehlzeit,
        nebenzeiten_gesamt_s=nebenzeiten,
        nebenzeit_quelle=nebenzeit_quelle,
        gesamtzykluszeit_s=gesamt,
    )
