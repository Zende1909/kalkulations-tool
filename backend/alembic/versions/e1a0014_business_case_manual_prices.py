"""Business Case: manuelle Stückpreise je Projektposition.

Revision ID: e1a0014_business_case_manual_prices
Revises: e1a0013_investition_cost_bottom_revenue
Create Date: 2026-08-28
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0014_business_case_manual_prices"
down_revision: Union[str, Sequence[str], None] = "e1a0013_investition_cost_bottom_revenue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("business_case_manual_prices"):
        return
    op.create_table(
        "business_case_manual_prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("linked_project_id", sa.Integer(), nullable=False),
        sa.Column("assignment_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.Integer(), nullable=False),
        sa.Column("bottom_price_per_piece", sa.Float(), nullable=True),
        sa.Column("actual_price_per_piece", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["linked_project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "customer_id",
            "program_id",
            "linked_project_id",
            "assignment_type",
            "object_id",
            name="uq_bc_manual_price_scope",
        ),
    )
    op.create_index("ix_bc_manual_prices_customer_id", "business_case_manual_prices", ["customer_id"])
    op.create_index("ix_bc_manual_prices_program_id", "business_case_manual_prices", ["program_id"])
    op.create_index("ix_bc_manual_prices_linked_project_id", "business_case_manual_prices", ["linked_project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("business_case_manual_prices"):
        op.drop_table("business_case_manual_prices")
