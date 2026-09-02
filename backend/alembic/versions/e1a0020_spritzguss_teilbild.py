"""Teilbild für Spritzguss-Kalkulationen."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0020_spritzguss_teilbild"
down_revision: Union[str, Sequence[str], None] = "e1a0019_drop_materialgruppe_quelle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "teilbild_mime" not in columns:
        op.add_column(
            "spritzguss_kalkulationen",
            sa.Column("teilbild_mime", sa.String(length=64), nullable=True),
        )
    if "teilbild_data" not in columns:
        op.add_column(
            "spritzguss_kalkulationen",
            sa.Column("teilbild_data", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "teilbild_data" in columns:
        op.drop_column("spritzguss_kalkulationen", "teilbild_data")
    if "teilbild_mime" in columns:
        op.drop_column("spritzguss_kalkulationen", "teilbild_mime")
