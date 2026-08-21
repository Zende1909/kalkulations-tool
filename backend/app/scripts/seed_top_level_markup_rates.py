"""Idempotenter Seed für zentrale Zuschlagssätze.

Nur explizit per CLI – nie im App-Startup, nie über Alembic.

Aufruf (aus backend/):

    python -m app.scripts.seed_top_level_markup_rates

Legt fehlende aktive Sätze an:

- mgk_kaufteil_selbst = 3 %
- mgk_kaufteil_oem = 5 %
- fgk = 22 %
- vvgk = 10 %
- gewinn = 15 %
- skonto = 0 %

Bestehende GEMEINKOSTEN-/GEWINN-/VERSCHROTTUNG-Datensätze bleiben unverändert.
Bereits aktive Sätze desselben Typs werden nicht überschrieben.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.zuschlagssatz import CENTRAL_MARKUP_TYPEN, Zuschlagssatz

TOP_LEVEL_MARKUP_SEED: tuple[tuple[str, str, float], ...] = (
    ("mgk_kaufteil_selbst", "MGK selbstnominiert (Material & Kaufteile)", 3.0),
    ("mgk_kaufteil_oem", "MGK OEM-nominiert (Material & Kaufteile)", 5.0),
    ("fgk", "FGK", 22.0),
    ("vvgk", "VVGK / SG&A", 10.0),
    ("gewinn", "Gewinn / Profit", 15.0),
    ("skonto", "Skonto", 0.0),
)

# Abwärtskompatibler Alias
ASSEMBLY_MARKUP_SEED = TOP_LEVEL_MARKUP_SEED


def is_local_development_database(database_url: str) -> bool:
    """Nur lokale Dev-/Test-DBs; keine Sicherheitsgrenze für Netzwerkzugriff."""
    return Settings.is_local_development_database_url(database_url)


def seed_top_level_markup_rates(db: Session) -> list[str]:
    """Legt je technischem Typ höchstens einen aktiven Satz an.

    Korrigiert zusätzlich vertauschte MGK-Defaults (selbst=5 / OEM=3 → 3 / 5),
    ohne andere manuell gepflegte Sätze zu überschreiben.
    """
    if set(typ for typ, _, _ in TOP_LEVEL_MARKUP_SEED) != set(CENTRAL_MARKUP_TYPEN):
        raise RuntimeError("TOP_LEVEL_MARKUP_SEED stimmt nicht mit CENTRAL_MARKUP_TYPEN überein.")

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

    # Vertauschte zentrale MGK-Defaults korrigieren (nur exakt 5/3)
    selbst = db.scalars(
        select(Zuschlagssatz).where(
            Zuschlagssatz.typ == "mgk_kaufteil_selbst",
            Zuschlagssatz.aktiv.is_(True),
        )
    ).first()
    oem = db.scalars(
        select(Zuschlagssatz).where(
            Zuschlagssatz.typ == "mgk_kaufteil_oem",
            Zuschlagssatz.aktiv.is_(True),
        )
    ).first()
    if (
        selbst is not None
        and oem is not None
        and float(selbst.satz_prozent) == 5.0
        and float(oem.satz_prozent) == 3.0
    ):
        selbst.satz_prozent = 3.0
        oem.satz_prozent = 5.0
        actions.append("fix:mgk_kaufteil_selbst:5→3")
        actions.append("fix:mgk_kaufteil_oem:3→5")

    db.commit()
    return actions


def assert_local_development_database(database_url: str) -> None:
    if not is_local_development_database(database_url):
        raise RuntimeError(
            "Seed für TOP_LEVEL-Zuschlagssätze ist nur für lokale "
            "Entwicklungsdatenbanken (localhost/127.0.0.1/sqlite) erlaubt."
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: Local-DB-Guard, dann idempotenter Seed."""
    _ = argv
    from app.config import settings

    try:
        assert_local_development_database(settings.DATABASE_URL)
    except RuntimeError as exc:
        print(f"Markup-Seed abgelehnt: {exc}", file=sys.stderr)
        return 1

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        result = seed_top_level_markup_rates(session)
        print("seed_top_level_markup_rates:", ", ".join(result))
        return 0
    except Exception as exc:
        print(f"Markup-Seed fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
