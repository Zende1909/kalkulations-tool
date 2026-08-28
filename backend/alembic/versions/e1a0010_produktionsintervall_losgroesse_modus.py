"""Werk: Produktionsintervall; Spritzguss: Losgrößenmodus.

Revision ID: e1a0010_produktionsintervall_losgroesse_modus
Revises: e1a0009_werk_operating_params
Create Date: 2026-08-28

Idempotent: Spalten nur hinzufügen, wenn fehlend. Keine DML / keine Seeds.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0010_produktionsintervall_losgroesse_modus"
down_revision: Union[str, Sequence[str], None] = "e1a0009_werk_operating_params"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("werke"):
        existing = {c["name"] for c in insp.get_columns("werke")}
        if "produktionsintervall_arbeitstage" not in existing:
            op.add_column(
                "werke",
                sa.Column("produktionsintervall_arbeitstage", sa.Float(), nullable=True),
            )
    if insp.has_table("spritzguss_kalkulationen"):
        existing = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
        if "losgroesse_modus" not in existing:
            op.add_column(
                "spritzguss_kalkulationen",
                sa.Column("losgroesse_modus", sa.String(length=16), nullable=True),
            )
        if "losgroesse_manuell" not in existing:
            op.add_column(
                "spritzguss_kalkulationen",
                sa.Column("losgroesse_manuell", sa.Integer(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("spritzguss_kalkulationen"):
        existing = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
        if "losgroesse_manuell" in existing:
            op.drop_column("spritzguss_kalkulationen", "losgroesse_manuell")
        if "losgroesse_modus" in existing:
            op.drop_column("spritzguss_kalkulationen", "losgroesse_modus")
    if insp.has_table("werke"):
        existing = {c["name"] for c in insp.get_columns("werke")}
        if "produktionsintervall_arbeitstage" in existing:
            op.drop_column("werke", "produktionsintervall_arbeitstage")
