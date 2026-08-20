"""Investitions-Legacy-Daten: name-Backfill und Status offen → In Planung.

Revision ID: e1a0002_investition_legacy_data
Revises: e1a0001_baseline
Create Date: 2026-08-20

Zweck
-----
Überführt die bisherige Startup-DML aus ensure_investition_schema() in eine
kontrollierte, versionierte Alembic-Datenmigration:

1. name aus part_name bzw. description befüllen, wenn name leer/NULL ist
   (Fallback: 'Investition')
2. status 'offen' → 'In Planung'

Betrifft ausschließlich Zeilen in investitionen, die die WHERE-Bedingungen
erfüllen. Keine Schema-DDL, keine Seeds.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a0002_investition_legacy_data"
down_revision: Union[str, Sequence[str], None] = "e1a0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotente Datenmigration für Legacy-Investitionszeilen."""
    op.execute(
        """
        UPDATE investitionen
        SET name = COALESCE(
            NULLIF(name, ''),
            NULLIF(part_name, ''),
            NULLIF(description, ''),
            'Investition'
        )
        WHERE name IS NULL OR name = ''
        """
    )
    op.execute(
        """
        UPDATE investitionen
        SET status = 'In Planung'
        WHERE status = 'offen'
        """
    )


def downgrade() -> None:
    """Best-effort Rollback der Investitions-Datenmigration.

    Rollback-Dokumentation
    ----------------------
    Name (best-effort):
        Setzt name auf '' zurück, wenn der aktuelle name dem Backfill-Ergebnis
        aus upgrade() entspricht (part_name, sonst description, sonst
        'Investition'). Manuell gesetzte Namen, die zufällig identisch zu
        part_name/description/'Investition' sind, können mit betroffen sein.

    Status (bewusst eingeschränkt):
        Ein pauschales Zurücksetzen aller Zeilen mit status='In Planung' auf
        'offen' wäre unsicher, weil legitime 'In Planung'-Datensätze nicht von
        migrierten Zeilen unterscheidbar sind. Deshalb wird der Status hier
        NICHT automatisch zurückgesetzt.

        Für produktive Daten: Restore aus Backup bevorzugen.
        Für kontrollierte Dev-/Smoke-DBs ggf. manuell:
            UPDATE investitionen SET status = 'offen'
            WHERE id IN (... bekannte, zuvor 'offen'-IDs ...);
    """
    op.execute(
        """
        UPDATE investitionen
        SET name = ''
        WHERE name = COALESCE(
            NULLIF(part_name, ''),
            NULLIF(description, ''),
            'Investition'
        )
        """
    )
