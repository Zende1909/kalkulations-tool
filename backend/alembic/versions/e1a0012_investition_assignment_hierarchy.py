"""Investitionen: Hierarchie-IDs, Zuordnungstyp und Kaufteil-FK.

Revision ID: e1a0012_investition_assignment_hierarchy
Revises: e1a0011_kaufteil_sga_override
Create Date: 2026-08-28

Additiv: customer_id, program_id, assignment_type, kaufteil_id.
Backfill assignment_type und linked_project_id aus bestehenden Daten (idempotent).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0012_investition_assignment_hierarchy"
down_revision: Union[str, Sequence[str], None] = "e1a0011_kaufteil_sga_override"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("investitionen"):
        return
    existing = {c["name"] for c in insp.get_columns("investitionen")}

    if "customer_id" not in existing:
        op.add_column(
            "investitionen",
            sa.Column("customer_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_investitionen_customer_id",
            "investitionen",
            "customers",
            ["customer_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_investitionen_customer_id", "investitionen", ["customer_id"])

    if "program_id" not in existing:
        op.add_column(
            "investitionen",
            sa.Column("program_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_investitionen_program_id",
            "investitionen",
            "programs",
            ["program_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_investitionen_program_id", "investitionen", ["program_id"])

    if "assignment_type" not in existing:
        op.add_column(
            "investitionen",
            sa.Column("assignment_type", sa.String(length=32), nullable=True),
        )
        op.create_index("ix_investitionen_assignment_type", "investitionen", ["assignment_type"])

    if "kaufteil_id" not in existing:
        op.add_column(
            "investitionen",
            sa.Column("kaufteil_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_investitionen_kaufteil_id",
            "investitionen",
            "kaufteile",
            ["kaufteil_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_investitionen_kaufteil_id", "investitionen", ["kaufteil_id"])

    # assignment_type aus Legacy-FKs ableiten
    op.execute(
        """
        UPDATE investitionen
        SET assignment_type = 'einzelteil'
        WHERE assignment_type IS NULL AND calculation_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE investitionen
        SET assignment_type = 'baugruppe'
        WHERE assignment_type IS NULL AND baugruppe_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE investitionen
        SET assignment_type = 'kaufteil'
        WHERE assignment_type IS NULL AND kaufteil_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE investitionen
        SET assignment_type = 'gesamtprojekt'
        WHERE assignment_type IS NULL
        """
    )

    # linked_project_id aus eindeutigem Projektnamen
    op.execute(
        """
        UPDATE investitionen i
        SET linked_project_id = (
            SELECT p.id FROM projects p
            WHERE p.name = i.project_id
            LIMIT 1
        )
        WHERE i.linked_project_id IS NULL
          AND i.project_id IS NOT NULL AND i.project_id <> ''
          AND (
            SELECT COUNT(*) FROM projects p WHERE p.name = i.project_id
          ) = 1
        """
    )

    # Hierarchie-IDs aus verknüpftem Projekt
    op.execute(
        """
        UPDATE investitionen i
        SET program_id = p.program_id,
            customer_id = pr.customer_id
        FROM projects p
        JOIN programs pr ON pr.id = p.program_id
        WHERE i.linked_project_id = p.id
          AND (i.program_id IS NULL OR i.customer_id IS NULL)
        """
    )

    # part_number aus verknüpften Objekten, falls leer
    op.execute(
        """
        UPDATE investitionen i
        SET part_number = sg.teilenummer,
            part_name = COALESCE(NULLIF(i.part_name, ''), sg.teilebezeichnung)
        FROM spritzguss_kalkulationen sg
        WHERE i.calculation_id = sg.id
          AND (i.part_number IS NULL OR i.part_number = '')
          AND sg.teilenummer IS NOT NULL AND sg.teilenummer <> ''
        """
    )
    op.execute(
        """
        UPDATE investitionen i
        SET part_number = bg.teilenummer,
            part_name = COALESCE(NULLIF(i.part_name, ''), bg.name)
        FROM baugruppen bg
        WHERE i.baugruppe_id = bg.id
          AND (i.part_number IS NULL OR i.part_number = '')
          AND bg.teilenummer IS NOT NULL AND bg.teilenummer <> ''
        """
    )
    op.execute(
        """
        UPDATE investitionen i
        SET part_number = kt.artikelnummer,
            part_name = COALESCE(NULLIF(i.part_name, ''), kt.bezeichnung)
        FROM kaufteile kt
        WHERE i.kaufteil_id = kt.id
          AND (i.part_number IS NULL OR i.part_number = '')
          AND kt.artikelnummer IS NOT NULL AND kt.artikelnummer <> ''
        """
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("investitionen"):
        return
    existing = {c["name"] for c in insp.get_columns("investitionen")}
    for col, fk, idx in (
        ("kaufteil_id", "fk_investitionen_kaufteil_id", "ix_investitionen_kaufteil_id"),
        ("program_id", "fk_investitionen_program_id", "ix_investitionen_program_id"),
        ("customer_id", "fk_investitionen_customer_id", "ix_investitionen_customer_id"),
    ):
        if col in existing:
            op.drop_index(idx, table_name="investitionen")
            op.drop_constraint(fk, "investitionen", type_="foreignkey")
            op.drop_column("investitionen", col)
    if "assignment_type" in existing:
        op.drop_index("ix_investitionen_assignment_type", table_name="investitionen")
        op.drop_column("investitionen", "assignment_type")
