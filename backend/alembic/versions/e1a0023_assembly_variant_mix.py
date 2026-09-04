"""Baugruppenfamilien mit Variantenanteilen.

Revision ID: e1a0023_assembly_variant_mix
Revises: e1a0022_zykluszeit_entnahmeart
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "e1a0023_assembly_variant_mix"
down_revision: Union[str, Sequence[str], None] = "e1a0022_zykluszeit_entnahmeart"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("assembly_families"):
        op.create_table(
            "assembly_families",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("beschreibung", sa.Text(), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="entwurf"),
            sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("ergebnis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        )
        op.create_index("ix_assembly_families_project_id", "assembly_families", ["project_id"])

    if insp.has_table("baugruppen"):
        cols = {c["name"] for c in insp.get_columns("baugruppen")}
        if "family_id" not in cols:
            op.add_column(
                "baugruppen",
                sa.Column("family_id", sa.Integer(), sa.ForeignKey("assembly_families.id", ondelete="SET NULL"), nullable=True),
            )
            op.create_index("ix_baugruppen_family_id", "baugruppen", ["family_id"])
        if "variant_share_pct" not in cols:
            op.add_column("baugruppen", sa.Column("variant_share_pct", sa.Float(), nullable=True))
        # CHECK may already exist on fresh DBs from model; ignore if present
        op.execute(
            sa.text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'chk_baugruppen_variant_share_pct'
                  ) THEN
                    ALTER TABLE baugruppen
                      ADD CONSTRAINT chk_baugruppen_variant_share_pct
                      CHECK (variant_share_pct IS NULL OR (variant_share_pct >= 0 AND variant_share_pct <= 100));
                  END IF;
                END$$;
                """
            )
        )
        op.execute(
            sa.text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_baugruppen_family_teilenummer_active
                ON baugruppen (family_id, lower(teilenummer))
                WHERE family_id IS NOT NULL AND aktiv = true;
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("baugruppen"):
        op.execute(sa.text("DROP INDEX IF EXISTS uq_baugruppen_family_teilenummer_active"))
        op.execute(sa.text("ALTER TABLE baugruppen DROP CONSTRAINT IF EXISTS chk_baugruppen_variant_share_pct"))
        cols = {c["name"] for c in insp.get_columns("baugruppen")}
        if "variant_share_pct" in cols:
            op.drop_column("baugruppen", "variant_share_pct")
        if "family_id" in cols:
            op.drop_index("ix_baugruppen_family_id", table_name="baugruppen")
            op.drop_column("baugruppen", "family_id")
    if insp.has_table("assembly_families"):
        op.drop_index("ix_assembly_families_project_id", table_name="assembly_families")
        op.drop_table("assembly_families")
