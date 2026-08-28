"""Kaufteil: optionale SG&A-Override-Felder.

Revision ID: e1a0011_kaufteil_sga_override
Revises: e1a0010_produktionsintervall_losgroesse_modus
Create Date: 2026-08-28

Idempotent: Spalten nur hinzufügen, wenn fehlend. Keine DML.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0011_kaufteil_sga_override"
down_revision: Union[str, Sequence[str], None] = "e1a0010_produktionsintervall_losgroesse_modus"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("kaufteile"):
        return
    existing = {c["name"] for c in insp.get_columns("kaufteile")}
    if "sga_override_aktiv" not in existing:
        op.add_column(
            "kaufteile",
            sa.Column("sga_override_aktiv", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "sga_satz_manuell" not in existing:
        op.add_column(
            "kaufteile",
            sa.Column("sga_satz_manuell", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("kaufteile"):
        return
    existing = {c["name"] for c in insp.get_columns("kaufteile")}
    if "sga_satz_manuell" in existing:
        op.drop_column("kaufteile", "sga_satz_manuell")
    if "sga_override_aktiv" in existing:
        op.drop_column("kaufteile", "sga_override_aktiv")
