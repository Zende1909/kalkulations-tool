"""Zykluszeit-Schätzung für frühe Angebotskalkulation (1K-Thermoplast).

Ziel ist eine konservative Größenordnung für die Serienproduktion mit
konventionellen Serien-Stahlwerkzeugen – keine Prozesssimulation.

Eingaben:

* Materialkennwerte aus der bestehenden effektiven Datenquelle
  (:mod:`app.services.material_thermik` über die am Material gepflegte
  Materialgruppe bzw. deren Stammdaten)
* kühlzeitrelevante Wandstärke in mm (Intern: ``wandstaerke_mm``)
* maßgebliche Zuhaltekraft (bevorzugt die erforderliche aus der
  Maschinengrößen-Berechnung, ersatzweise die Maschinen-Zuhaltekraft)
* Schussgewicht und Kavitäten der Kalkulation
* ``entnahmeart`` (``werkzeugfallend`` / ``greifer``)
* ``prozessaufwand`` (``normal`` / ``aufwendig``)

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

Die *automatische* Nebenzeit setzt sich additiv aus vier Komponenten zusammen
(alles pauschale Erfahrungswerte der frühen Angebotskalkulation)::

    t_neben_auto = t_wkz + t_spritz + t_dosier_ueber + t_entnahme + Prozessaufwand

Priorität der Nebenzeit:

1. Manuelle Nebenzeit (``nebenzeiten_gesamt_s`` gesetzt) hat Vorrang und wird
   durch Entnahmeart, Schussgewicht, Kavitäten und ``prozessaufwand`` *nicht*
   verändert.
2. Sonst gilt ``t_neben_auto``.
3. Die Quelle bleibt im Ergebnis als ``manuell``/``automatisch`` erkennbar.

Kühlzeit und Nebenzeitkomponenten werden durchgehend ungerundet in ``float``
gerechnet. Nur die vorgeschlagene Gesamtzykluszeit wird am Ende kaufmännisch
auf eine volle Sekunde gerundet: ``gesamtzykluszeit_s`` ist der Wert, der
angezeigt, exportiert und bei „Übernehmen“ in die Kalkulation geschrieben wird.
Die ungerundete Summe bleibt als ``gesamtzykluszeit_exakt_s`` nachvollziehbar.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

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

# Pauschaler Zuschlag auf die *automatische* Nebenzeit bei aufwendigem Prozess
# (Einlegeteile, mehrere Kernzüge, Ausschrauben). Wird genau einmal addiert.
PROZESSAUFWAND_ZUSCHLAG_S = 5.0

PROZESSAUFWAND_NORMAL = "normal"
PROZESSAUFWAND_AUFWENDIG = "aufwendig"
PROZESSAUFWAND_WERTE: tuple[str, ...] = (PROZESSAUFWAND_NORMAL, PROZESSAUFWAND_AUFWENDIG)
DEFAULT_PROZESSAUFWAND = PROZESSAUFWAND_NORMAL

# --- Entnahmeart -----------------------------------------------------------
# `werkzeugfallend`: Teil fällt nach dem Auswerfen frei aus dem Werkzeug, das
# Werkzeug kann direkt wieder schließen.
# `greifer`: Handlingsystem fährt in das offene Werkzeug ein, entnimmt das Teil
# und fährt aus, bevor das Werkzeug schließen kann.
ENTNAHMEART_WERKZEUGFALLEND = "werkzeugfallend"
ENTNAHMEART_GREIFER = "greifer"
ENTNAHMEART_WERTE: tuple[str, ...] = (ENTNAHMEART_WERKZEUGFALLEND, ENTNAHMEART_GREIFER)
# Bestehende Datensätze ohne Wert verwenden `greifer`.
DEFAULT_ENTNAHMEART = ENTNAHMEART_GREIFER
ENTNAHMEART_LABELS: dict[str, str] = {
    ENTNAHMEART_WERKZEUGFALLEND: "werkzeugfallend – Teil fällt frei aus",
    ENTNAHMEART_GREIFER: "greifer – Handlingsystem entnimmt",
}

# --- Nebenzeitkomponenten (pauschale Erfahrungswerte) ----------------------
# Alle Staffeln sind als ``(obergrenze_t, sekunden)`` aufsteigend definiert und
# werden mit „≤ Obergrenze“ ausgewertet.

# t_wkz: Schließen, Zuhaltung aufbauen, Öffnen und Auswerferhub. Große
# Werkzeuge haben deutlich längere Öffnungswege und niedrigere
# Verfahrgeschwindigkeiten.
WERKZEUGBEWEGUNG_STAFFEL_S: tuple[tuple[float, float], ...] = (
    (100.0, 4.0),
    (300.0, 6.0),
    (800.0, 10.0),
    (1500.0, 14.0),
    (2500.0, 18.0),
)
WERKZEUGBEWEGUNG_UEBER_S = 22.0
WERKZEUGBEWEGUNG_OHNE_ZUHALTEKRAFT_S = 6.0

# t_spritz: Einspritzen und Nachdruck aus dem Schussgewicht.
SPRITZZEIT_GRUNDZEIT_S = 1.5
SPRITZZEIT_JE_GRAMM_S = 0.006
SPRITZZEIT_MIN_S = 1.5
SPRITZZEIT_MAX_S = 30.0
SPRITZZEIT_OHNE_SCHUSSGEWICHT_S = 3.0

# Plastifizierleistung P (kg/h) grob aus der Zuhaltekraft, für den
# Dosierüberhang. Die Plastifizierung läuft parallel zur Kühlung; nur der
# Überhang über die Kühlzeit wird taktbestimmend.
PLASTIFIZIERLEISTUNG_STAFFEL_KG_H: tuple[tuple[float, float], ...] = (
    (100.0, 25.0),
    (300.0, 50.0),
    (800.0, 110.0),
    (1500.0, 200.0),
    (2500.0, 280.0),
)
PLASTIFIZIERLEISTUNG_UEBER_KG_H = 330.0
PLASTIFIZIERLEISTUNG_OHNE_ZUHALTEKRAFT_KG_H = 50.0

# t_entnahme bei `werkzeugfallend`: nur Freifallen und kurzes Nachwarten.
ENTNAHME_WERKZEUGFALLEND_STAFFEL_S: tuple[tuple[float, float], ...] = (
    (300.0, 1.0),
    (1500.0, 1.5),
)
ENTNAHME_WERKZEUGFALLEND_UEBER_S = 2.0
ENTNAHME_WERKZEUGFALLEND_OHNE_ZUHALTEKRAFT_S = 1.0

# t_entnahme bei `greifer`: Der Greifer muss einfahren, greifen, ausfahren und
# freifahren, bevor das Werkzeug schließen darf. Diese Zeit liegt vollständig
# im Takt und skaliert mit dem Öffnungsweg, also mit der Zuhaltekraft.
ENTNAHME_GREIFER_STAFFEL_S: tuple[tuple[float, float], ...] = (
    (300.0, 3.0),
    (800.0, 5.0),
    (1500.0, 7.0),
    (2500.0, 9.0),
)
ENTNAHME_GREIFER_UEBER_S = 11.0
ENTNAHME_GREIFER_OHNE_ZUHALTEKRAFT_S = 5.0
# Mehrere Teile greifen und ablegen dauert länger, skaliert aber nicht linear.
ENTNAHME_GREIFER_JE_WEITERE_KAVITAET_S = 0.2
ENTNAHME_GREIFER_KAVITAETEN_MAX_S = 4.0

# Nicht blockierende Plausibilitätswarnung für große Werkzeuge mit dünn
# angegebener Wandstärke.
GROSSTEIL_WARNUNG_ZUHALTEKRAFT_T = 800.0
GROSSTEIL_WARNUNG_WANDSTAERKE_MM = 3.0
GROSSTEIL_WARNUNG_TEXT = (
    "Große Werkzeug-/Maschinenklasse mit geringer angegebener Wandstärke. "
    "Prüfen, ob lokale Dickstellen an Domen, Rippenkreuzungen oder "
    "Materialanhäufungen die kühlzeitrelevante Wandstärke bestimmen."
)

# Kritischer Dosierengpass: großes Schussgewicht auf einer aus der Zuhaltekraft
# abgeleiteten kleinen Plastifizierklasse. Konservative Angebots-Plausibilität,
# kein Nachweis einer tatsächlichen Maschinenüberlastung – maximale Schussgewichte
# je Maschine liegen nicht vor.
DOSIERZEIT_WARNFAKTOR = 3.0
DOSIERZEIT_WARNGRENZE_S = 60.0

STATUS_GUELTIG = "gueltig"
STATUS_NICHT_PLAUSIBEL = "nicht_plausibel"
STATUS_NICHT_BERECHENBAR = "nicht_berechenbar"
STATUS_WERTE: tuple[str, ...] = (
    STATUS_GUELTIG,
    STATUS_NICHT_PLAUSIBEL,
    STATUS_NICHT_BERECHENBAR,
)

# Informative Werkzeug-/Maschinenklasse. Sie beschreibt die Größenordnung des
# Werkzeugs und wird weiterhin gespeichert und angezeigt, steuert die
# Nebenzeit aber nicht mehr: diese folgt den Komponenten oben.
GROESSENKLASSEN: tuple[tuple[str, str], ...] = (
    ("klein", "Klein – Handteil, einfache Entformung"),
    ("mittel", "Mittel – Standardteil, Roboterentnahme"),
    ("gross", "Groß – Großteil, Kernzug oder Einlegeteil"),
)
GROESSENKLASSEN_KEYS: tuple[str, ...] = tuple(key for key, _label in GROESSENKLASSEN)
GROESSENKLASSEN_LABELS: dict[str, str] = {key: label for key, label in GROESSENKLASSEN}
DEFAULT_GROESSENKLASSE = "mittel"

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


def _zahl_de(wert: float, nachkommastellen: int) -> str:
    """Anzeigezahl ohne interne Variablennamen, deutsches Dezimalformat."""
    vorzeichen = "-" if wert < 0 else ""
    betrag = abs(float(wert))
    if nachkommastellen <= 0:
        ganz = int(math.floor(betrag + 0.5))
        return vorzeichen + f"{ganz:,}".replace(",", ".")
    text = f"{betrag:.{nachkommastellen}f}"
    ganz_s, frac = text.split(".")
    ganz_s = f"{int(ganz_s):,}".replace(",", ".")
    return f"{vorzeichen}{ganz_s},{frac}"


def _positiv_oder_none(wert: float | int | None) -> float | None:
    """Endliche, positive Zahl als ``float`` – sonst ``None``."""
    if wert is None:
        return None
    try:
        parsed = float(wert)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or parsed <= 0:
        return None
    return parsed


def runde_auf_sekunde(wert: float) -> float:
    """Kaufmännisch auf eine volle Sekunde runden (0,5 s wird aufgerundet).

    Angebotszykluszeiten werden in ganzen Sekunden geführt. Bewusst nicht
    ``round()``, das kaufmännisch nicht rundet (``round(0.5) == 0``).
    """
    gerundet = float(math.floor(wert + 0.5))
    # Eine Zykluszeit von 0 s wäre in Kapazität und Kosten nicht verwendbar.
    return max(1.0, gerundet)


def _staffelwert(
    staffel: tuple[tuple[float, float], ...], ueber: float, wert: float
) -> float:
    """Erster Staffelwert mit ``wert <= obergrenze``, sonst ``ueber``."""
    for obergrenze, sekunden in staffel:
        if wert <= obergrenze:
            return sekunden
    return ueber


def massgebliche_zuhaltekraft_t(
    zuhaltekraft_t: float | None, maschinen_zuhaltekraft_t: float | None = None
) -> float | None:
    """Bevorzugt die erforderliche Zuhaltekraft, ersatzweise die der Maschine."""
    return _positiv_oder_none(zuhaltekraft_t) or _positiv_oder_none(
        maschinen_zuhaltekraft_t
    )


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
    massgeblich = _positiv_oder_none(zuhaltekraft_t)
    if massgeblich is None:
        return DEFAULT_GROESSENKLASSE
    return klasse_aus_zuhaltekraft(massgeblich)


def normalisiere_prozessaufwand(wert: str | None) -> str:
    """Fehlende/unbekannte Werte → ``normal`` (Abwärtskompatibilität)."""
    if wert is None or (isinstance(wert, str) and not wert.strip()):
        return DEFAULT_PROZESSAUFWAND
    key = str(wert).strip().lower()
    return key if key in PROZESSAUFWAND_WERTE else DEFAULT_PROZESSAUFWAND


def normalisiere_entnahmeart(wert: str | None) -> str:
    """Fehlende/unbekannte Werte → ``greifer`` (Abwärtskompatibilität)."""
    if wert is None or (isinstance(wert, str) and not wert.strip()):
        return DEFAULT_ENTNAHMEART
    key = str(wert).strip().lower()
    return key if key in ENTNAHMEART_WERTE else DEFAULT_ENTNAHMEART


def normalisiere_kavitaeten(wert: int | float | None) -> int:
    """Mindestens eine Kavität; ungültige Angaben gelten als 1."""
    parsed = _positiv_oder_none(wert)
    if parsed is None:
        return 1
    return max(1, int(parsed))


def materialklasse_fuer_gruppe(gruppe: str | None) -> str:
    if not gruppe:
        return MATERIALKLASSE_UNBEKANNT
    key = str(gruppe).strip().upper()
    if key in TEILKRISTALLINE_GRUPPEN:
        return MATERIALKLASSE_TEILKRISTALLIN
    if key in AMORPHE_GRUPPEN:
        return MATERIALKLASSE_AMORPH
    return MATERIALKLASSE_UNBEKANNT


def werkzeugbewegungszeit_s(zuhaltekraft_t: float | None) -> float:
    """t_wkz: Schließen, Zuhaltung aufbauen, Öffnen, Auswerferhub."""
    massgeblich = _positiv_oder_none(zuhaltekraft_t)
    if massgeblich is None:
        return WERKZEUGBEWEGUNG_OHNE_ZUHALTEKRAFT_S
    return _staffelwert(WERKZEUGBEWEGUNG_STAFFEL_S, WERKZEUGBEWEGUNG_UEBER_S, massgeblich)


def einspritz_nachdruckzeit_s(schussgewicht_g: float | None) -> float:
    """t_spritz aus dem Schussgewicht, begrenzt auf 1,5 s bis 30,0 s."""
    masse = _positiv_oder_none(schussgewicht_g)
    if masse is None:
        return SPRITZZEIT_OHNE_SCHUSSGEWICHT_S
    roh = SPRITZZEIT_GRUNDZEIT_S + SPRITZZEIT_JE_GRAMM_S * masse
    return min(SPRITZZEIT_MAX_S, max(SPRITZZEIT_MIN_S, roh))


def plastifizierleistung_kg_h(zuhaltekraft_t: float | None) -> float:
    """Angesetzte Plastifizierleistung P grob aus der Zuhaltekraft."""
    massgeblich = _positiv_oder_none(zuhaltekraft_t)
    if massgeblich is None:
        return PLASTIFIZIERLEISTUNG_OHNE_ZUHALTEKRAFT_KG_H
    return _staffelwert(
        PLASTIFIZIERLEISTUNG_STAFFEL_KG_H, PLASTIFIZIERLEISTUNG_UEBER_KG_H, massgeblich
    )


def dosierzeit_s(schussmasse_gesamt_g: float, leistung_kg_h: float) -> float:
    """Dosierzeit aus Schussmasse und Plastifizierleistung."""
    if schussmasse_gesamt_g <= 0 or leistung_kg_h <= 0:
        return 0.0
    return (schussmasse_gesamt_g / 1000.0) / leistung_kg_h * 3600.0


def entnahmezeit_s(
    entnahmeart: str | None, zuhaltekraft_t: float | None, kavitaeten: int | None = 1
) -> float:
    """t_entnahme aus Entnahmeart, Zuhaltekraft und Kavitäten."""
    art = normalisiere_entnahmeart(entnahmeart)
    massgeblich = _positiv_oder_none(zuhaltekraft_t)
    if art == ENTNAHMEART_WERKZEUGFALLEND:
        if massgeblich is None:
            return ENTNAHME_WERKZEUGFALLEND_OHNE_ZUHALTEKRAFT_S
        return _staffelwert(
            ENTNAHME_WERKZEUGFALLEND_STAFFEL_S,
            ENTNAHME_WERKZEUGFALLEND_UEBER_S,
            massgeblich,
        )
    basis = (
        ENTNAHME_GREIFER_OHNE_ZUHALTEKRAFT_S
        if massgeblich is None
        else _staffelwert(
            ENTNAHME_GREIFER_STAFFEL_S, ENTNAHME_GREIFER_UEBER_S, massgeblich
        )
    )
    weitere = max(0, normalisiere_kavitaeten(kavitaeten) - 1)
    zuschlag = min(
        ENTNAHME_GREIFER_KAVITAETEN_MAX_S,
        weitere * ENTNAHME_GREIFER_JE_WEITERE_KAVITAET_S,
    )
    return basis + zuschlag


def prozessaufwand_zuschlag_s(prozessaufwand: str | None) -> float:
    if normalisiere_prozessaufwand(prozessaufwand) == PROZESSAUFWAND_AUFWENDIG:
        return PROZESSAUFWAND_ZUSCHLAG_S
    return 0.0


@dataclass
class Nebenzeiten:
    """Aufschlüsselung der *automatischen* Nebenzeit (ungerundet)."""

    werkzeugbewegung_s: float
    einspritz_nachdruck_s: float
    dosierzeit_s: float
    dosier_ueberhang_s: float
    entnahme_s: float
    prozessaufwand_zuschlag_s: float
    plastifizierleistung_kg_h: float
    schussmasse_gesamt_g: float
    gesamt_s: float
    schussgewicht_fallback: bool
    zuhaltekraft_fallback: bool

    def as_dict(self) -> dict:
        return {
            "nebenzeit_werkzeugbewegung_s": self.werkzeugbewegung_s,
            "nebenzeit_einspritz_nachdruck_s": self.einspritz_nachdruck_s,
            "nebenzeit_dosierzeit_s": self.dosierzeit_s,
            "nebenzeit_dosier_ueberhang_s": self.dosier_ueberhang_s,
            "nebenzeit_entnahme_s": self.entnahme_s,
            "nebenzeit_prozessaufwand_zuschlag_s": self.prozessaufwand_zuschlag_s,
            "plastifizierleistung_kg_h": self.plastifizierleistung_kg_h,
            "schussmasse_gesamt_g": self.schussmasse_gesamt_g,
            "nebenzeiten_automatisch_s": self.gesamt_s,
            "schussgewicht_fallback": self.schussgewicht_fallback,
            "zuhaltekraft_fallback": self.zuhaltekraft_fallback,
        }


def automatische_nebenzeiten(
    *,
    zuhaltekraft_t: float | None = None,
    schussgewicht_g: float | None = None,
    kavitaeten: int | None = 1,
    entnahmeart: str | None = None,
    prozessaufwand: str | None = None,
    kuehlzeit_s: float | None = None,
) -> Nebenzeiten:
    """Automatische Nebenzeit als additive Komponenten.

    ``kuehlzeit_s`` ist die Kühlzeit für die Weiterrechnung (inkl. Faktor 1,5).
    Ohne sie kann der Dosierüberhang nicht bestimmt werden und gilt als 0 s.
    """
    massgeblich = _positiv_oder_none(zuhaltekraft_t)
    masse_je_schuss = _positiv_oder_none(schussgewicht_g)
    kav = normalisiere_kavitaeten(kavitaeten)

    t_wkz = werkzeugbewegungszeit_s(massgeblich)
    t_spritz = einspritz_nachdruckzeit_s(masse_je_schuss)
    leistung = plastifizierleistung_kg_h(massgeblich)

    # Die Kavitätenzahl verlängert die Kühlzeit nicht, wirkt aber über die
    # Schussmasse auf die Dosierzeit.
    schussmasse_gesamt = (masse_je_schuss or 0.0) * kav
    t_dosier = dosierzeit_s(schussmasse_gesamt, leistung)
    kuehl = _positiv_oder_none(kuehlzeit_s) or 0.0
    t_dosier_ueber = max(0.0, t_dosier - kuehl)

    t_entnahme = entnahmezeit_s(entnahmeart, massgeblich, kav)
    zuschlag = prozessaufwand_zuschlag_s(prozessaufwand)

    return Nebenzeiten(
        werkzeugbewegung_s=t_wkz,
        einspritz_nachdruck_s=t_spritz,
        dosierzeit_s=t_dosier,
        dosier_ueberhang_s=t_dosier_ueber,
        entnahme_s=t_entnahme,
        prozessaufwand_zuschlag_s=zuschlag,
        plastifizierleistung_kg_h=leistung,
        schussmasse_gesamt_g=schussmasse_gesamt,
        gesamt_s=t_wkz + t_spritz + t_dosier_ueber + t_entnahme + zuschlag,
        schussgewicht_fallback=masse_je_schuss is None,
        zuhaltekraft_fallback=massgeblich is None,
    )


def automatische_nebenzeiten_s(**kwargs) -> float:
    """Summe der automatischen Nebenzeit (Komfortwrapper)."""
    return automatische_nebenzeiten(**kwargs).gesamt_s


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
    maschinen_zuhaltekraft_t: float | None = None
    schussgewicht_g: float | None = None
    kavitaeten: int | None = None
    entnahmeart: str | None = DEFAULT_ENTNAHMEART
    prozessaufwand: str | None = DEFAULT_PROZESSAUFWAND


@dataclass
class ZykluszeitResult:
    berechenbar: bool
    hinweis: str | None = None
    warnungen: list[str] = field(default_factory=list)
    wandstaerke_mm: float | None = None
    materialgruppe: str | None = None
    material_bezeichnung: str | None = None
    materialklasse: str | None = None
    groessenklasse: str | None = None
    groessenklasse_auswahl: str | None = None
    zuhaltekraft_t: float | None = None
    schussgewicht_g: float | None = None
    kavitaeten: int | None = None
    entnahmeart: str | None = None
    prozessaufwand: str | None = None
    kuehlfaktor: float | None = None
    temperaturleitfaehigkeit_m2_s: float | None = None
    werkzeugtemperatur_c: float | None = None
    schmelzetemperatur_c: float | None = None
    entformungstemperatur_c: float | None = None
    # Interner Feldname aus Abwärtskompatibilität; fachlich = theoretische Kühlzeit.
    optimale_kuehlzeit_s: float | None = None
    kuehlzeit_s: float | None = None
    nebenzeit_werkzeugbewegung_s: float | None = None
    nebenzeit_einspritz_nachdruck_s: float | None = None
    nebenzeit_dosierzeit_s: float | None = None
    nebenzeit_dosier_ueberhang_s: float | None = None
    nebenzeit_entnahme_s: float | None = None
    nebenzeit_prozessaufwand_zuschlag_s: float | None = None
    plastifizierleistung_kg_h: float | None = None
    schussmasse_gesamt_g: float | None = None
    nebenzeiten_automatisch_s: float | None = None
    schussgewicht_fallback: bool = False
    zuhaltekraft_fallback: bool = False
    nebenzeiten_gesamt_s: float | None = None
    nebenzeit_quelle: str | None = None
    # Vorschlag in ganzen Sekunden; dieser Wert wird übernommen.
    gesamtzykluszeit_s: float | None = None
    # Ungerundete Summe aus Kühlzeit und Nebenzeit zur Nachvollziehbarkeit.
    gesamtzykluszeit_exakt_s: float | None = None
    # gueltig | nicht_plausibel | nicht_berechenbar
    status: str = STATUS_NICHT_BERECHENBAR
    kann_uebernommen_werden: bool = False
    dosierzeit_warnfaktor: float = DOSIERZEIT_WARNFAKTOR
    dosierzeit_warngrenze_s: float = DOSIERZEIT_WARNGRENZE_S

    def as_dict(self) -> dict:
        return {
            "berechenbar": self.berechenbar,
            "hinweis": self.hinweis,
            "warnungen": list(self.warnungen),
            "wandstaerke_mm": self.wandstaerke_mm,
            "materialgruppe": self.materialgruppe,
            "material_bezeichnung": self.material_bezeichnung,
            "materialklasse": self.materialklasse,
            "groessenklasse": self.groessenklasse,
            "groessenklasse_auswahl": self.groessenklasse_auswahl,
            "zuhaltekraft_t": self.zuhaltekraft_t,
            "schussgewicht_g": self.schussgewicht_g,
            "kavitaeten": self.kavitaeten,
            "entnahmeart": self.entnahmeart,
            "prozessaufwand": self.prozessaufwand,
            "kuehlfaktor": self.kuehlfaktor,
            "temperaturleitfaehigkeit_m2_s": self.temperaturleitfaehigkeit_m2_s,
            "werkzeugtemperatur_c": self.werkzeugtemperatur_c,
            "schmelzetemperatur_c": self.schmelzetemperatur_c,
            "entformungstemperatur_c": self.entformungstemperatur_c,
            "optimale_kuehlzeit_s": self.optimale_kuehlzeit_s,
            "kuehlzeit_s": self.kuehlzeit_s,
            "nebenzeit_werkzeugbewegung_s": self.nebenzeit_werkzeugbewegung_s,
            "nebenzeit_einspritz_nachdruck_s": self.nebenzeit_einspritz_nachdruck_s,
            "nebenzeit_dosierzeit_s": self.nebenzeit_dosierzeit_s,
            "nebenzeit_dosier_ueberhang_s": self.nebenzeit_dosier_ueberhang_s,
            "nebenzeit_entnahme_s": self.nebenzeit_entnahme_s,
            "nebenzeit_prozessaufwand_zuschlag_s": self.nebenzeit_prozessaufwand_zuschlag_s,
            "plastifizierleistung_kg_h": self.plastifizierleistung_kg_h,
            "schussmasse_gesamt_g": self.schussmasse_gesamt_g,
            "nebenzeiten_automatisch_s": self.nebenzeiten_automatisch_s,
            "schussgewicht_fallback": self.schussgewicht_fallback,
            "zuhaltekraft_fallback": self.zuhaltekraft_fallback,
            "nebenzeiten_gesamt_s": self.nebenzeiten_gesamt_s,
            "nebenzeit_quelle": self.nebenzeit_quelle,
            "gesamtzykluszeit_s": self.gesamtzykluszeit_s,
            "gesamtzykluszeit_exakt_s": self.gesamtzykluszeit_exakt_s,
            "status": self.status,
            "kann_uebernommen_werden": self.kann_uebernommen_werden,
            "dosierzeit_warnfaktor": self.dosierzeit_warnfaktor,
            "dosierzeit_warngrenze_s": self.dosierzeit_warngrenze_s,
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


def grossteil_warnung(
    zuhaltekraft_t: float | None, wandstaerke_mm: float | None
) -> str | None:
    """Nicht blockierender Hinweis auf mögliche lokale Dickstellen."""
    kraft = _positiv_oder_none(zuhaltekraft_t)
    dicke = _positiv_oder_none(wandstaerke_mm)
    if kraft is None or dicke is None:
        return None
    if kraft > GROSSTEIL_WARNUNG_ZUHALTEKRAFT_T and dicke < GROSSTEIL_WARNUNG_WANDSTAERKE_MM:
        return GROSSTEIL_WARNUNG_TEXT
    return None


def dosierengpass_ist_kritisch(
    *,
    dosierzeit_s: float | None,
    kuehlzeit_s: float | None,
    schussgewicht_g: float | None,
    plastifizierleistung_kg_h: float | None,
    zuhaltekraft_t: float | None,
    schussgewicht_fallback: bool = False,
    zuhaltekraft_fallback: bool = False,
) -> bool:
    """True bei extremem Dosierengpass relativ zur Kühlzeit und Plastifizierklasse.

    Ohne Schussgewicht oder ohne maßgebliche Zuhaltekraft greifen die bestehenden
    Fallbacks; dann wird kein Schussgewichts-/Dosierengpass gemeldet.
    """
    if schussgewicht_fallback or zuhaltekraft_fallback:
        return False
    if _positiv_oder_none(schussgewicht_g) is None:
        return False
    if _positiv_oder_none(zuhaltekraft_t) is None:
        return False
    if _positiv_oder_none(plastifizierleistung_kg_h) is None:
        return False
    if dosierzeit_s is None or kuehlzeit_s is None:
        return False
    try:
        dosier = float(dosierzeit_s)
        kuehl = float(kuehlzeit_s)
        leistung = float(plastifizierleistung_kg_h)
    except (TypeError, ValueError):
        return False
    if not all(math.isfinite(v) for v in (dosier, kuehl, leistung)):
        return False
    if kuehl <= 0 or leistung <= 0 or dosier <= 0:
        return False
    return dosier > DOSIERZEIT_WARNFAKTOR * kuehl and dosier > DOSIERZEIT_WARNGRENZE_S


def dosierengpass_warnung(
    *,
    dosierzeit_s: float,
    kuehlzeit_s: float,
    schussgewicht_g: float,
    kavitaeten: int,
    zuhaltekraft_t: float,
    plastifizierleistung_kg_h: float,
    dosier_ueberhang_s: float | None = None,
    gesamtzykluszeit_s: float | None = None,
) -> str:
    """Fachliche Meldung ohne interne Variablennamen."""
    zeilen = [
        (
            f"Die berechnete Dosierzeit von {_zahl_de(dosierzeit_s, 1)} s ist für die "
            "aktuell aus der Zuhaltekraft abgeleitete Maschinen-/Plastifizierklasse "
            "ungewöhnlich hoch. Bitte prüfen Sie, ob Schussgewicht, Maße, "
            "Kavitätenzahl und die empfohlene Maschine zusammenpassen. Ohne maximale "
            "Schussgewichte der Maschine kann nur ein Plausibilitätshinweis ausgegeben "
            "werden. Der Vorschlag kann nicht automatisch übernommen werden."
        ),
        f"Schussgewicht: {_zahl_de(schussgewicht_g, 0)} g",
        f"Kavitäten: {kavitaeten}",
        f"Maßgebliche Zuhaltekraft: {_zahl_de(zuhaltekraft_t, 1)} t",
        f"Plastifizierleistung: {_zahl_de(plastifizierleistung_kg_h, 0)} kg/h",
        f"Dosierzeit: {_zahl_de(dosierzeit_s, 1)} s",
        f"Kühlzeit für Weiterrechnung: {_zahl_de(kuehlzeit_s, 2)} s",
    ]
    if dosier_ueberhang_s is not None and math.isfinite(dosier_ueberhang_s):
        zeilen.append(f"Dosierüberhang: {_zahl_de(dosier_ueberhang_s, 1)} s")
    if gesamtzykluszeit_s is not None and math.isfinite(gesamtzykluszeit_s):
        zeilen.append(
            f"Vorgeschlagene Gesamtzeit: {_zahl_de(gesamtzykluszeit_s, 0)} s"
        )
    return " ".join(zeilen[:1]) + " " + " · ".join(zeilen[1:])


@dataclass
class _Kontext:
    """Bereits normalisierte Eingaben für Teil- und Endergebnisse."""

    inp: ZykluszeitInput
    auswahl: str
    klasse: str
    zuhaltekraft_t: float | None
    schussgewicht_g: float | None
    kavitaeten: int
    entnahmeart: str
    prozessaufwand: str
    nebenzeiten: float | None
    nebenzeit_quelle: str
    komponenten: Nebenzeiten
    materialklasse: str | None = None


def _basis_result(ctx: _Kontext) -> ZykluszeitResult:
    return ZykluszeitResult(
        berechenbar=False,
        warnungen=[],
        wandstaerke_mm=ctx.inp.wandstaerke_mm,
        materialgruppe=ctx.inp.materialgruppe,
        materialklasse=ctx.materialklasse,
        groessenklasse=ctx.klasse,
        groessenklasse_auswahl=ctx.auswahl,
        zuhaltekraft_t=ctx.zuhaltekraft_t,
        schussgewicht_g=ctx.schussgewicht_g,
        kavitaeten=ctx.kavitaeten,
        entnahmeart=ctx.entnahmeart,
        prozessaufwand=ctx.prozessaufwand,
        kuehlfaktor=KUEHLFAKTOR,
        nebenzeit_werkzeugbewegung_s=ctx.komponenten.werkzeugbewegung_s,
        nebenzeit_einspritz_nachdruck_s=ctx.komponenten.einspritz_nachdruck_s,
        nebenzeit_dosierzeit_s=ctx.komponenten.dosierzeit_s,
        nebenzeit_dosier_ueberhang_s=ctx.komponenten.dosier_ueberhang_s,
        nebenzeit_entnahme_s=ctx.komponenten.entnahme_s,
        nebenzeit_prozessaufwand_zuschlag_s=ctx.komponenten.prozessaufwand_zuschlag_s,
        plastifizierleistung_kg_h=ctx.komponenten.plastifizierleistung_kg_h,
        schussmasse_gesamt_g=ctx.komponenten.schussmasse_gesamt_g,
        nebenzeiten_automatisch_s=ctx.komponenten.gesamt_s,
        schussgewicht_fallback=ctx.komponenten.schussgewicht_fallback,
        zuhaltekraft_fallback=ctx.komponenten.zuhaltekraft_fallback,
        nebenzeiten_gesamt_s=ctx.nebenzeiten,
        nebenzeit_quelle=ctx.nebenzeit_quelle,
        status=STATUS_NICHT_BERECHENBAR,
        kann_uebernommen_werden=False,
        dosierzeit_warnfaktor=DOSIERZEIT_WARNFAKTOR,
        dosierzeit_warngrenze_s=DOSIERZEIT_WARNGRENZE_S,
    )


def _teilergebnis(hinweis: str, ctx: _Kontext) -> ZykluszeitResult:
    result = _basis_result(ctx)
    result.hinweis = hinweis
    warnung = grossteil_warnung(ctx.zuhaltekraft_t, ctx.inp.wandstaerke_mm)
    if warnung:
        result.warnungen = [warnung]
    return result


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
    zuhaltekraft = massgebliche_zuhaltekraft_t(
        inp.zuhaltekraft_t, inp.maschinen_zuhaltekraft_t
    )
    klasse = effektive_groessenklasse(auswahl, zuhaltekraft)
    prozessaufwand = normalisiere_prozessaufwand(inp.prozessaufwand)
    entnahmeart = normalisiere_entnahmeart(inp.entnahmeart)
    kavitaeten = normalisiere_kavitaeten(inp.kavitaeten)
    schussgewicht = _positiv_oder_none(inp.schussgewicht_g)

    def komponenten_fuer(kuehlzeit_s: float | None) -> Nebenzeiten:
        return automatische_nebenzeiten(
            zuhaltekraft_t=zuhaltekraft,
            schussgewicht_g=schussgewicht,
            kavitaeten=kavitaeten,
            entnahmeart=entnahmeart,
            prozessaufwand=prozessaufwand,
            kuehlzeit_s=kuehlzeit_s,
        )

    manuell = _manuelle_nebenzeiten(inp.nebenzeiten_gesamt_s)
    # Ohne Kühlzeit lässt sich der Dosierüberhang noch nicht bestimmen; für
    # Teilergebnisse (Hinweisfälle) genügen die übrigen Komponenten.
    komponenten = komponenten_fuer(None)
    ctx = _Kontext(
        inp=inp,
        auswahl=auswahl,
        klasse=klasse,
        zuhaltekraft_t=zuhaltekraft,
        schussgewicht_g=schussgewicht,
        kavitaeten=kavitaeten,
        entnahmeart=entnahmeart,
        prozessaufwand=prozessaufwand,
        nebenzeiten=manuell if manuell is not None else komponenten.gesamt_s,
        nebenzeit_quelle=(
            NEBENZEIT_QUELLE_MANUELL if manuell is not None else NEBENZEIT_QUELLE_AUTOMATISCH
        ),
        komponenten=komponenten,
    )

    if manuell is not None and (not math.isfinite(manuell) or manuell < 0):
        ctx.nebenzeiten = manuell if math.isfinite(manuell) else None
        return _teilergebnis("Die Nebenzeit darf nicht negativ sein.", ctx)

    if not math.isfinite(KUEHLFAKTOR) or KUEHLFAKTOR <= 0:
        return _teilergebnis("Der interne Kühlfaktor ist ungültig.", ctx)

    thermik = (
        defaults_fuer_gruppe_db(db, inp.materialgruppe)
        if db is not None
        else defaults_fuer_gruppe(inp.materialgruppe)
    )
    if thermik is None:
        return _teilergebnis(
            "Für den Zykluszeitvorschlag fehlen die Materialkennwerte. Bitte die "
            "Materialgruppe in den Materialstammdaten hinterlegen (z. B. PP, ABS, PA6).",
            ctx,
        )

    ctx.materialklasse = materialklasse_fuer_gruppe(thermik.gruppe)

    if inp.wandstaerke_mm is None:
        return _teilergebnis("Bitte die kühlzeitrelevante Wandstärke des Teils eintragen.", ctx)
    wandstaerke = float(inp.wandstaerke_mm)
    if not math.isfinite(wandstaerke) or wandstaerke <= 0:
        return _teilergebnis("Die kühlzeitrelevante Wandstärke muss größer als 0 mm sein.", ctx)
    if wandstaerke > MAX_WANDSTAERKE_MM:
        return _teilergebnis(
            f"Die Wandstärke von {wandstaerke:g} mm ist für eine Abschätzung unrealistisch "
            f"(zulässig bis {MAX_WANDSTAERKE_MM:g} mm).",
            ctx,
        )

    t_m = float(thermik.schmelzetemperatur_c)
    t_e = float(thermik.entformungstemperatur_c)
    t_w = float(thermik.werkzeugtemperatur_c)
    if not all(math.isfinite(v) for v in (t_m, t_e, t_w)):
        return _teilergebnis(
            f"Die hinterlegten Temperaturen der Materialgruppe {thermik.gruppe} sind ungültig.",
            ctx,
        )
    if not (t_m > t_e):
        return _teilergebnis(
            "Die Schmelzetemperatur muss über der Entformungstemperatur liegen.", ctx
        )
    if not (t_e > t_w):
        return _teilergebnis(
            "Die Entformungstemperatur muss über der Werkzeugtemperatur liegen.", ctx
        )

    dens = float(thermik.schmelzdichte_kg_m3)
    cp = float(thermik.waermekapazitaet_j_kg_k)
    lam = float(thermik.waermeleitfaehigkeit_w_m_k)
    if min(dens, cp, lam) <= 0 or not all(math.isfinite(v) for v in (dens, cp, lam)):
        return _teilergebnis(
            f"Die hinterlegten Kennwerte der Materialgruppe {thermik.gruppe} sind ungültig.",
            ctx,
        )

    alpha = temperaturleitfaehigkeit(thermik)
    if not math.isfinite(alpha) or alpha <= 0:
        return _teilergebnis("Die Temperaturleitfähigkeit muss größer als 0 sein.", ctx)

    # T_E - T_W > 0 ist oben bereits sichergestellt; log_argument vor log() prüfen.
    log_argument = (4.0 / math.pi) * ((t_m - t_w) / (t_e - t_w))
    if not math.isfinite(log_argument) or log_argument <= 1:
        return _teilergebnis(
            "Mit den angegebenen Temperaturen kann keine gültige Kühlzeit berechnet werden.", ctx
        )

    ungueltig = (
        "Die berechnete Zykluszeit ist ungültig. Bitte Eingabewerte und Materialdaten prüfen."
    )
    t_opt = optimale_kuehlzeit(wandstaerke_mm=wandstaerke, thermik=thermik)
    if not math.isfinite(t_opt) or t_opt < 0:
        return _teilergebnis(ungueltig, ctx)

    kuehlzeit = t_opt * KUEHLFAKTOR
    if not math.isfinite(kuehlzeit) or kuehlzeit < 0:
        return _teilergebnis(ungueltig, ctx)

    # Erst jetzt steht die Kühlzeit für den Dosierüberhang bereit.
    komponenten = komponenten_fuer(kuehlzeit)
    ctx.komponenten = komponenten
    nebenzeiten = manuell if manuell is not None else komponenten.gesamt_s
    ctx.nebenzeiten = nebenzeiten
    if not math.isfinite(nebenzeiten) or nebenzeiten < 0:
        return _teilergebnis(ungueltig, ctx)

    gesamt = kuehlzeit + nebenzeiten
    if not math.isfinite(gesamt) or gesamt <= 0:
        return _teilergebnis(ungueltig, ctx)
    gesamt_gerundet = runde_auf_sekunde(gesamt)

    result = _basis_result(ctx)
    result.berechenbar = True
    result.hinweis = _hinweis_materialklasse(ctx.materialklasse or MATERIALKLASSE_UNBEKANNT)
    warnung = grossteil_warnung(zuhaltekraft, wandstaerke)
    result.warnungen = [warnung] if warnung else []
    result.wandstaerke_mm = wandstaerke
    result.materialgruppe = thermik.gruppe
    result.material_bezeichnung = thermik.bezeichnung
    result.temperaturleitfaehigkeit_m2_s = alpha
    result.werkzeugtemperatur_c = t_w
    result.schmelzetemperatur_c = t_m
    result.entformungstemperatur_c = t_e
    result.optimale_kuehlzeit_s = t_opt
    result.kuehlzeit_s = kuehlzeit
    result.gesamtzykluszeit_s = gesamt_gerundet
    result.gesamtzykluszeit_exakt_s = gesamt
    result.status = STATUS_GUELTIG
    result.kann_uebernommen_werden = True
    if dosierengpass_ist_kritisch(
        dosierzeit_s=komponenten.dosierzeit_s,
        kuehlzeit_s=kuehlzeit,
        schussgewicht_g=schussgewicht,
        plastifizierleistung_kg_h=komponenten.plastifizierleistung_kg_h,
        zuhaltekraft_t=zuhaltekraft,
        schussgewicht_fallback=komponenten.schussgewicht_fallback,
        zuhaltekraft_fallback=komponenten.zuhaltekraft_fallback,
    ):
        result.status = STATUS_NICHT_PLAUSIBEL
        result.kann_uebernommen_werden = False
        result.warnungen.append(
            dosierengpass_warnung(
                dosierzeit_s=komponenten.dosierzeit_s,
                kuehlzeit_s=kuehlzeit,
                schussgewicht_g=schussgewicht or 0.0,
                kavitaeten=kavitaeten,
                zuhaltekraft_t=zuhaltekraft or 0.0,
                plastifizierleistung_kg_h=komponenten.plastifizierleistung_kg_h,
                dosier_ueberhang_s=komponenten.dosier_ueberhang_s,
                gesamtzykluszeit_s=gesamt_gerundet,
            )
        )
    return result
