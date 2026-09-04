"""Projektbezogene Baugruppenanteile: Familien-Abhängigkeit fachlich lösen.

Revision ID: e1a0024_project_assembly_shares
Revises: e1a0023_assembly_variant_mix

- Stellt sicher, dass Baugruppen mit family_id eine project_id vom Familienprojekt haben
- family_id / assembly_families bleiben als Legacy bestehen (kein Drop)
- variant_share_pct bleibt der gespeicherte „Anteil am Projekt (%)“
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0024_project_assembly_shares"
down_revision: Union[str, Sequence[str], None] = "e1a0023_assembly_variant_mix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("baugruppen") or not insp.has_table("assembly_families"):
        return

    # project_id / linked_project_id aus der Familie nachziehen (verlustfrei)
    op.execute(
        sa.text(
            """
            UPDATE baugruppen AS b
            SET
              project_id = COALESCE(b.project_id, f.project_id),
              linked_project_id = COALESCE(b.linked_project_id, b.project_id, f.project_id)
            FROM assembly_families AS f
            WHERE b.family_id = f.id
              AND (
                b.project_id IS NULL
                OR b.linked_project_id IS NULL
              )
            """
        )
    )


def downgrade() -> None:
    # Daten-Backfill ist idempotent; kein Rollback der project_id-Werte
    pass
