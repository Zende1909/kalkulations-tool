"""M-7: Material-Nominierung am Spritzguss-Einsatz.

Revision ID: e1a0006_spritzguss_material_nominierung
Revises: e1a0005_central_markups_kaufteil
Create Date: 2026-08-21

Zweck
-----
Schema-Erweiterung (keine Daten-Seeds, keine Umklassifizierung):

- spritzguss_kalkulationen.material_nominierung
  (nullable: selbstnominiert | oem_nominiert)

Bestehende Kalkulationen behalten NULL – Berechnung verlangt dann eine
explizite Nachpflege der Nominierung.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a0006_spritzguss_material_nominierung"
down_revision: Union[str, Sequence[str], None] = "e1a0005_central_markups_kaufteil"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "spritzguss_kalkulationen",
        sa.Column("material_nominierung", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_spritzguss_kalkulationen_material_nominierung",
        "spritzguss_kalkulationen",
        ["material_nominierung"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_spritzguss_kalkulationen_material_nominierung",
        table_name="spritzguss_kalkulationen",
    )
    op.drop_column("spritzguss_kalkulationen", "material_nominierung")
