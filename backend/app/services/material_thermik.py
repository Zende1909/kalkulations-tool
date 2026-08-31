"""Thermische Kennwerte je Materialgruppe für die Zykluszeit-Schätzung.

Diese Werte werden bewusst *nicht* je Material gepflegt: für eine Abschätzung
der Zykluszeit genügt die Materialgruppe. Am Material wird deshalb nur noch die
Gruppe hinterlegt, alles Weitere kommt aus dieser Tabelle.

Der POM-Satz stammt direkt aus ``IKET-Kostenkalkulation - Dosing Guide.xlsx``
(Blatt ``Zykluszeitbestimmung``), die übrigen Sätze sind gängige Richtwerte aus
der Verarbeitungsliteratur (Menges/Mohren) und als solche gekennzeichnet. Alle
Sätze ergeben eine Temperaturleitfähigkeit im üblichen Band von rund
0,07 bis 0,12 mm²/s.
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
            "PE-LD", "Polyethylen weich", 740.0, 3000.0, 0.24, 30.0, 200.0, 70.0, QUELLE_RICHTWERT
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
            "PMMA",
            "Polymethylmethacrylat",
            1080.0,
            2100.0,
            0.19,
            70.0,
            250.0,
            100.0,
            QUELLE_RICHTWERT,
        ),
        ThermikDefaults(
            "PBT",
            "Polybutylenterephthalat",
            1120.0,
            2300.0,
            0.22,
            80.0,
            250.0,
            130.0,
            QUELLE_RICHTWERT,
        ),
    )
}

_ALIASE = {
    "PEHD": "PE-HD",
    "HDPE": "PE-HD",
    "PELD": "PE-LD",
    "LDPE": "PE-LD",
    "PA-6": "PA6",
    "PA-66": "PA66",
    "POMC": "POM",
}


def normalisiere_gruppe(wert: str | None) -> str | None:
    """Bringt eine Nutzereingabe auf einen bekannten Gruppenschlüssel."""
    if wert is None:
        return None
    key = wert.strip().upper().replace(" ", "").replace("_", "-")
    if not key:
        return None
    if key in MATERIALGRUPPEN_DEFAULTS:
        return key
    return _ALIASE.get(key)


def defaults_fuer_gruppe(gruppe: str | None) -> ThermikDefaults | None:
    key = normalisiere_gruppe(gruppe)
    return MATERIALGRUPPEN_DEFAULTS.get(key) if key else None


def alle_defaults() -> list[ThermikDefaults]:
    return list(MATERIALGRUPPEN_DEFAULTS.values())
