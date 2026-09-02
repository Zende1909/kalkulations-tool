"""Thermische Kennwerte je Materialgruppe für die Zykluszeit-Schätzung.

Die Stammdaten liegen in der Tabelle ``materialgruppen``. Dieses Modul enthält
Hilfsfunktionen zur Normalisierung von Gruppenschlüsseln und zum Laden der
Kennwerte aus der Datenbank.

Die Konstante ``MATERIALGRUPPEN_DEFAULTS`` dient nur noch als Seed-Quelle für
die Alembic-Migration und Tests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.materialgruppe import Materialgruppe


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

    def as_dict(self) -> dict:
        return asdict(self)


MATERIALGRUPPEN_DEFAULTS: dict[str, ThermikDefaults] = {
    d.gruppe: d
    for d in (
        ThermikDefaults(
            "POM", "Polyoxymethylen", 783.17, 3000.0, 0.27, 40.0, 220.0, 80.0
        ),
        ThermikDefaults(
            "PP", "Polypropylen", 750.0, 2800.0, 0.18, 30.0, 240.0, 90.0
        ),
        ThermikDefaults(
            "PE-HD", "Polyethylen hart", 760.0, 2900.0, 0.25, 30.0, 220.0, 80.0
        ),
        ThermikDefaults(
            "PE-LD", "Polyethylen weich", 740.0, 3000.0, 0.24, 30.0, 200.0, 70.0
        ),
        ThermikDefaults(
            "PA6", "Polyamid 6", 980.0, 2600.0, 0.25, 80.0, 250.0, 130.0
        ),
        ThermikDefaults(
            "PA66", "Polyamid 66", 980.0, 2600.0, 0.25, 80.0, 285.0, 150.0
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
        ),
        ThermikDefaults(
            "SAN", "Styrol-Acrylnitril", 970.0, 2100.0, 0.17, 60.0, 240.0, 90.0
        ),
        ThermikDefaults(
            "PS", "Polystyrol", 970.0, 2100.0, 0.15, 40.0, 220.0, 80.0
        ),
        ThermikDefaults(
            "PC", "Polycarbonat", 1050.0, 2000.0, 0.21, 90.0, 300.0, 130.0
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


def normalisiere_gruppenschluessel(wert: str | None) -> str | None:
    """Bringt eine Nutzereingabe auf einen normalisierten Gruppenschlüssel."""
    if wert is None:
        return None
    key = wert.strip().upper().replace(" ", "").replace("_", "-")
    if not key:
        return None
    return _ALIASE.get(key, key)


def normalisiere_gruppe(wert: str | None) -> str | None:
    """Alias für Abwärtskompatibilität in Tests und Schemas."""
    return normalisiere_gruppenschluessel(wert)


def from_model(row: Materialgruppe) -> ThermikDefaults:
    return ThermikDefaults(
        gruppe=row.gruppe,
        bezeichnung=row.bezeichnung,
        schmelzdichte_kg_m3=row.schmelzdichte_kg_m3,
        waermekapazitaet_j_kg_k=row.waermekapazitaet_j_kg_k,
        waermeleitfaehigkeit_w_m_k=row.waermeleitfaehigkeit_w_m_k,
        werkzeugtemperatur_c=row.werkzeugtemperatur_c,
        schmelzetemperatur_c=row.schmelzetemperatur_c,
        entformungstemperatur_c=row.entformungstemperatur_c,
    )


def defaults_fuer_gruppe_db(db: Session, gruppe: str | None) -> ThermikDefaults | None:
    key = normalisiere_gruppenschluessel(gruppe)
    if key is None:
        return None
    row = db.scalar(
        select(Materialgruppe).where(
            Materialgruppe.gruppe == key,
            Materialgruppe.aktiv.is_(True),
        )
    )
    return from_model(row) if row else None


def alle_defaults_db(db: Session) -> list[ThermikDefaults]:
    rows = db.scalars(select(Materialgruppe).order_by(Materialgruppe.gruppe.asc())).all()
    return [from_model(row) for row in rows]


def defaults_fuer_gruppe(gruppe: str | None) -> ThermikDefaults | None:
    """Fallback für Unit-Tests ohne Datenbank (nur Seed-Tabelle)."""
    key = normalisiere_gruppenschluessel(gruppe)
    return MATERIALGRUPPEN_DEFAULTS.get(key) if key else None


def alle_defaults() -> list[ThermikDefaults]:
    """Fallback für Unit-Tests ohne Datenbank (nur Seed-Tabelle)."""
    return list(MATERIALGRUPPEN_DEFAULTS.values())
