"""Investitionen: Kosten, Bottom Price und Erlös als getrennte Einmalbeträge.

Revision ID: e1a0013_investition_cost_bottom_revenue
Revises: e1a0012_investition_assignment_hierarchy
Create Date: 2026-08-28

Legacy: amount wird nach cost_amount übernommen; bottom_price/revenue_amount bleiben NULL.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0013_investition_cost_bottom_revenue"
down_revision: Union[str, Sequence[str], None] = "e1a0012_investition_assignment_hierarchy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("investitionen"):
        return
    existing = {c["name"] for c in insp.get_columns("investitionen")}

    if "cost_amount" not in existing:
        op.add_column(
            "investitionen",
            sa.Column("cost_amount", sa.Float(), nullable=False, server_default="0"),
        )
    if "bottom_price" not in existing:
        op.add_column("investitionen", sa.Column("bottom_price", sa.Float(), nullable=True))
    if "revenue_amount" not in existing:
        op.add_column("investitionen", sa.Column("revenue_amount", sa.Float(), nullable=True))

    op.execute(
        """
        UPDATE investitionen
        SET cost_amount = amount
        WHERE cost_amount IS NULL OR cost_amount = 0
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("investitionen"):
        return
    existing = {c["name"] for c in insp.get_columns("investitionen")}
    for col in ("revenue_amount", "bottom_price", "cost_amount"):
        if col in existing:
            op.drop_column("investitionen", col)
