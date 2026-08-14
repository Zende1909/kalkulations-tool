"""Idempotenter Seed für TOP_LEVEL-Zuschlagssätze (vvgk, gewinn, skonto).

Legt fehlende aktive Sätze an. Bestehende GEMEINKOSTEN-/GEWINN-/VERSCHROTTUNG-
Datensätze werden nicht geändert. Nur gegen lokale Entwicklungsdatenbanken
ausführen.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.zuschlagssatz import ASSEMBLY_MARKUP_TYPEN, Zuschlagssatz

TOP_LEVEL_MARKUP_SEED: tuple[tuple[str, str, float], ...] = (
    ("vvgk", "VVGK", 10.0),
    ("gewinn", "Gewinn", 15.0),
    ("skonto", "Skonto", 0.0),
)


def is_local_development_database(database_url: str) -> bool:
    lowered = database_url.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered


def seed_top_level_markup_rates(db: Session) -> list[str]:
    """Legt je technischem Typ höchstens einen aktiven Satz an.

    Returns:
        Liste der durchgeführten Aktionen (insert/skip).
    """
    actions: list[str] = []
    for typ, bezeichnung, satz_prozent in TOP_LEVEL_MARKUP_SEED:
        existing_active = db.scalars(
            select(Zuschlagssatz).where(
                Zuschlagssatz.typ == typ,
                Zuschlagssatz.aktiv.is_(True),
            )
        ).first()
        if existing_active is not None:
            actions.append(f"skip:{typ}")
            continue
        db.add(
            Zuschlagssatz(
                bezeichnung=bezeichnung,
                satz_prozent=satz_prozent,
                typ=typ,
                aktiv=True,
            )
        )
        actions.append(f"insert:{typ}")
    db.commit()
    return actions


def assert_local_development_database(database_url: str) -> None:
    if not is_local_development_database(database_url):
        raise RuntimeError(
            "Seed für TOP_LEVEL-Zuschlagssätze ist nur für lokale "
            "Entwicklungsdatenbanken (localhost/127.0.0.1) erlaubt."
        )
    if not ASSEMBLY_MARKUP_TYPEN:
        raise RuntimeError("ASSEMBLY_MARKUP_TYPEN fehlen")


if __name__ == "__main__":
    from app.config import settings
    from app.database import SessionLocal

    assert_local_development_database(settings.DATABASE_URL)
    session = SessionLocal()
    try:
        result = seed_top_level_markup_rates(session)
        print("seed_top_level_markup_rates:", ", ".join(result))
    finally:
        session.close()
