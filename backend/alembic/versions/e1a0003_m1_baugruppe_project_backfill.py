"""M-1: baugruppen.project_id aus linked_project_id backfüllen.

Revision ID: e1a0003_m1_baugruppe_project_backfill
Revises: e1a0002_investition_legacy_data
Create Date: 2026-08-20

Zweck
-----
Kontrollierter Daten-Backfill (Phase-A-Schritt M-1):

    project_id = linked_project_id

nur wenn project_id noch NULL ist, linked_project_id gesetzt ist und die
FK auf projects gültig ist.

Keine Anwendungs-Schema-DDL an baugruppen/projects. Kein Freitext-Mapping
(projekt). Keine Änderung an linked_project_id, legacy_mode oder
Legacy-Zuordnungstabellen.

Hinweis: upgrade() erweitert alembic_version.version_num auf VARCHAR(64),
damit die Revisions-ID (länger als 32 Zeichen) speicherbar ist.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a0003_m1_baugruppe_project_backfill"
down_revision: Union[str, Sequence[str], None] = "e1a0002_investition_legacy_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotenter Backfill project_id <- linked_project_id (nur gültige FKs)."""
    # Revision-IDs ab e1a0003 überschreiten das Alembic-Default VARCHAR(32).
    op.execute(
        "ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"
    )
    op.execute(
        """
        UPDATE baugruppen
        SET project_id = linked_project_id
        WHERE project_id IS NULL
          AND linked_project_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM projects
              WHERE projects.id = baugruppen.linked_project_id
          )
        """
    )


def downgrade() -> None:
    """Best-effort Rollback des M-1-Backfills.

    Rollback-Dokumentation
    ----------------------
    Setzt project_id auf NULL zurück, wenn project_id und linked_project_id
    denselben Wert haben (typisches Ergebnis von upgrade()).

    Grenzen:
    - Zeilen, bei denen project_id bereits vor M-1 denselben Wert wie
      linked_project_id hatte, würden ebenfalls geleert.
    - Zeilen, deren project_id nach dem Backfill manuell geändert wurde,
      bleiben unberührt.
    - linked_project_id, legacy_mode und Freitext projekt bleiben unverändert.

    Für produktive Daten: Restore aus Backup bevorzugen.
    """
    op.execute(
        """
        UPDATE baugruppen
        SET project_id = NULL
        WHERE project_id IS NOT NULL
          AND linked_project_id IS NOT NULL
          AND project_id = linked_project_id
        """
    )
