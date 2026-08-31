"""Thermische Materialgruppen-Richtwerte für die Kühlzeitberechnung (IKET).

Herkunft der Werte:

``POM``
    Vollständig aus der Referenz ``IKET-Kostenkalkulation - Dosing Guide.xlsx``,
    Blatt ``Zykluszeitbestimmung`` (Delrin 500P NC010, DuPont).

Übrige Gruppen
    Übliche Verarbeitungs-Richtwerte für Thermoplaste. Sie dienen ausschließlich
    als Vorbelegung und müssen gegen das Materialdatenblatt geprüft werden;
    deshalb ist jede Gruppe mit ``quelle`` gekennzeichnet.

Die Schmelzdichte ist bewusst getrennt von der Feststoffdichte des Materials
(``Material.dichte``) geführt, weil die IKET-Kühlzeitformel mit der Dichte der
Schmelze rechnet.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

QUELLE_IKET = "iket"
QUELLE_RICHTWERT = "richtwert"


@dataclass(frozen=True)
class ThermikDefaults:
    gruppe: str
    bezeichnung: str
    schmelzdichte_kg_m3: float
    waermekapazitaet_j_kg_k: float
    waermeleitfaehigkeit_w_m_k: float
    werkzeugtemperatur_c: float
    schmelzetemperatur_c: float
    entformungstemperatur_c: float
    quelle: str

    def as_dict(self) -> dict:
        return asdict(self)

    def thermik_felder(self) -> dict[str, float]:
        return {
            "schmelzdichte_kg_m3": self.schmelzdichte_kg_m3,
            "waermekapazitaet_j_kg_k": self.waermekapazitaet_j_kg_k,
            "waermeleitfaehigkeit_w_m_k": self.waermeleitfaehigkeit_w_m_k,
            "werkzeugtemperatur_c": self.werkzeugtemperatur_c,
            "schmelzetemperatur_c": self.schmelzetemperatur_c,
            "entformungstemperatur_c": self.entformungstemperatur_c,
        }


MATERIALGRUPPEN_DEFAULTS: dict[str, ThermikDefaults] = {
    d.gruppe: d
    for d in (
        ThermikDefaults(
            "POM", "Polyoxymethylen", 783.17, 3000.0, 0.27, 40.0, 220.0, 80.0, QUELLE_IKET
        ),
        ThermikDefaults(
            "PP", "Polypropylen", 750.0, 2800.0, 0.18, 30.0, 240.0, 90.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PE-HD", "Polyethylen hart", 760.0, 2900.0, 0.25, 30.0, 220.0, 80.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PA6", "Polyamid 6", 980.0, 2600.0, 0.25, 80.0, 250.0, 130.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PA66", "Polyamid 66", 980.0, 2600.0, 0.25, 80.0, 285.0, 150.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "ABS",
            "Acrylnitril-Butadien-Styrol",
            940.0,
            2300.0,
            0.18,
            60.0,
            240.0,
            90.0,
            QUELLE_RICHTWERT,
        ),
        ThermikDefaults(
            "SAN", "Styrol-Acrylnitril", 970.0, 2100.0, 0.17, 60.0, 240.0, 90.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PS", "Polystyrol", 970.0, 2100.0, 0.15, 40.0, 220.0, 80.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PC", "Polycarbonat", 1050.0, 2000.0, 0.21, 90.0, 300.0, 130.0, QUELLE_RICHTWERT
        ),
        ThermikDefaults(
            "PMMA", "Polymethylmethacrylat", 1080.0, 2100.0, 0.19, 70.0, 250.0, 100.0,
            QUELLE_RICHTWERT,
        ),
        ThermikDefaults(
            "PBT", "Polybutylenterephthalat", 1120.0, 2300.0, 0.22, 80.0, 250.0, 130.0,
            QUELLE_RICHTWERT,
        ),
    )
}

THERMIK_FELDER = (
    "schmelzdichte_kg_m3",
    "waermekapazitaet_j_kg_k",
    "waermeleitfaehigkeit_w_m_k",
    "werkzeugtemperatur_c",
    "schmelzetemperatur_c",
    "entformungstemperatur_c",
)


def normalisiere_gruppe(wert: str | None) -> str | None:
    """Bringt eine Nutzereingabe auf einen bekannten Gruppenschlüssel."""
    if wert is None:
        return None
    key = wert.strip().upper().replace(" ", "").replace("_", "-")
    if not key:
        return None
    if key in MATERIALGRUPPEN_DEFAULTS:
        return key
    aliase = {"PEHD": "PE-HD", "HDPE": "PE-HD", "PA-6": "PA6", "PA-66": "PA66", "POMC": "POM"}
    return aliase.get(key)


def defaults_fuer_gruppe(gruppe: str | None) -> ThermikDefaults | None:
    key = normalisiere_gruppe(gruppe)
    return MATERIALGRUPPEN_DEFAULTS.get(key) if key else None


def alle_defaults() -> list[ThermikDefaults]:
    return list(MATERIALGRUPPEN_DEFAULTS.values())
