"""M-6: Zentrale Zuschläge + Kaufteil-Nominierung/Hierarchie.

Revision ID: e1a0005_central_markups_kaufteil
Revises: e1a0004_m5_assembly_positions
Create Date: 2026-08-21

Zweck
-----
Schema-Erweiterung (keine Daten-Seeds, keine Umklassifizierung):

- kaufteile.nominierung (nullable: selbstnominiert | oem_nominiert)
- kaufteile.customer_id / program_id / project_id (nullable FKs)

Zuschlagssatz-Typen werden nur in der Anwendung validiert; bestehende
Stammdatensätze bleiben unverändert. Zentrale Sätze (FGK, MGK Kaufteile,
VVGK, Gewinn, Skonto) müssen manuell oder per Seed-Skript angelegt werden.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a0005_central_markups_kaufteil"
down_revision: Union[str, Sequence[str], None] = "e1a0004_m5_assembly_positions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "kaufteile",
        sa.Column("nominierung", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "kaufteile",
        sa.Column("customer_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "kaufteile",
        sa.Column("program_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "kaufteile",
        sa.Column("project_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_kaufteile_nominierung", "kaufteile", ["nominierung"])
    op.create_index("ix_kaufteile_customer_id", "kaufteile", ["customer_id"])
    op.create_index("ix_kaufteile_program_id", "kaufteile", ["program_id"])
    op.create_index("ix_kaufteile_project_id", "kaufteile", ["project_id"])
    op.create_foreign_key(
        "fk_kaufteile_customer_id_customers",
        "kaufteile",
        "customers",
        ["customer_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_kaufteile_program_id_programs",
        "kaufteile",
        "programs",
        ["program_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_kaufteile_project_id_projects",
        "kaufteile",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_kaufteile_project_id_projects", "kaufteile", type_="foreignkey")
    op.drop_constraint("fk_kaufteile_program_id_programs", "kaufteile", type_="foreignkey")
    op.drop_constraint("fk_kaufteile_customer_id_customers", "kaufteile", type_="foreignkey")
    op.drop_index("ix_kaufteile_project_id", table_name="kaufteile")
    op.drop_index("ix_kaufteile_program_id", table_name="kaufteile")
    op.drop_index("ix_kaufteile_customer_id", table_name="kaufteile")
    op.drop_index("ix_kaufteile_nominierung", table_name="kaufteile")
    op.drop_column("kaufteile", "project_id")
    op.drop_column("kaufteile", "program_id")
    op.drop_column("kaufteile", "customer_id")
    op.drop_column("kaufteile", "nominierung")
