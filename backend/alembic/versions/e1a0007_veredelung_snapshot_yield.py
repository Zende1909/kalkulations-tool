"""Veredelungs-Snapshot: Vor-Ausschuss-Kosten und Quote für Ausbeutekette.

Revision ID: e1a0007_veredelung_snapshot_yield
Revises: e1a0006_spritzguss_material_nominierung
Create Date: 2026-08-21

Zweck
-----
Beim Speichern einer Spritzguss-Kalkulation müssen Veredelungs-Snapshots dieselben
Ausbeute-Eingaben tragen wie „Berechnen“ (live). Sonst fällt der Save-Pfad auf die
Legacy-Addition ohne Vorprodukt-Kaskade und der Endpreis weicht ab.

- spritzguss_veredelung_zuordnungen.snapshot_kosten_vor_ausschuss (nullable)
- spritzguss_veredelung_zuordnungen.snapshot_ausschussquote_pct (nullable)
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a0007_veredelung_snapshot_yield"
down_revision: Union[str, Sequence[str], None] = "e1a0006_spritzguss_material_nominierung"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "spritzguss_veredelung_zuordnungen",
        sa.Column("snapshot_kosten_vor_ausschuss", sa.Float(), nullable=True),
    )
    op.add_column(
        "spritzguss_veredelung_zuordnungen",
        sa.Column("snapshot_ausschussquote_pct", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("spritzguss_veredelung_zuordnungen", "snapshot_ausschussquote_pct")
    op.drop_column("spritzguss_veredelung_zuordnungen", "snapshot_kosten_vor_ausschuss")
