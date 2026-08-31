"""Material-Einspritzdruck und Maschinengröße an Spritzguss-Kalkulation.

Revision ID: e1a0015_injection_machine_sizing
Revises: e1a0014_business_case_manual_prices
Create Date: 2026-08-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0015_injection_machine_sizing"
down_revision: Union[str, Sequence[str], None] = "e1a0014_business_case_manual_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    _add_column_if_missing(
        "materialien",
        sa.Column(
            "injection_pressure_kg_cm2",
            sa.Float(),
            nullable=False,
            server_default="500",
        ),
    )
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("materialien"):
        op.execute(
            sa.text(
                "UPDATE materialien SET injection_pressure_kg_cm2 = 500 "
                "WHERE injection_pressure_kg_cm2 IS NULL"
            )
        )

    sizing_columns = [
        sa.Column("maschinen_groesse_modus", sa.String(length=16), nullable=True),
        sa.Column("maschinen_groesse_breite_mm", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_laenge_mm", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_oeffnungen_pct", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_proj_flaeche_mm2", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_schwindung_pct", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_injection_pressure_kg_cm2", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_proj_flaeche_netto_mm2", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_zuhaltekraft_ohne_sicherheit_t", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_sicherheitszuschlag_faktor", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_zuhaltekraft_erforderlich_t", sa.Float(), nullable=True),
        sa.Column("maschinen_groesse_empfohlene_maschine_id", sa.Integer(), nullable=True),
        sa.Column("maschinen_groesse_warnung", sa.String(length=512), nullable=True),
    ]
    for column in sizing_columns:
        _add_column_if_missing("spritzguss_kalkulationen", column)

    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("spritzguss_kalkulationen"):
        fks = {fk["name"] for fk in insp.get_foreign_keys("spritzguss_kalkulationen")}
        if "fk_sg_maschinen_groesse_empfohlene_maschine" not in fks:
            op.create_foreign_key(
                "fk_sg_maschinen_groesse_empfohlene_maschine",
                "spritzguss_kalkulationen",
                "maschinen",
                ["maschinen_groesse_empfohlene_maschine_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("spritzguss_kalkulationen"):
        fks = {fk["name"] for fk in insp.get_foreign_keys("spritzguss_kalkulationen")}
        if "fk_sg_maschinen_groesse_empfohlene_maschine" in fks:
            op.drop_constraint(
                "fk_sg_maschinen_groesse_empfohlene_maschine",
                "spritzguss_kalkulationen",
                type_="foreignkey",
            )
        for name in (
            "maschinen_groesse_warnung",
            "maschinen_groesse_empfohlene_maschine_id",
            "maschinen_groesse_zuhaltekraft_erforderlich_t",
            "maschinen_groesse_sicherheitszuschlag_faktor",
            "maschinen_groesse_zuhaltekraft_ohne_sicherheit_t",
            "maschinen_groesse_proj_flaeche_netto_mm2",
            "maschinen_groesse_injection_pressure_kg_cm2",
            "maschinen_groesse_schwindung_pct",
            "maschinen_groesse_proj_flaeche_mm2",
            "maschinen_groesse_oeffnungen_pct",
            "maschinen_groesse_laenge_mm",
            "maschinen_groesse_breite_mm",
            "maschinen_groesse_modus",
        ):
            cols = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
            if name in cols:
                op.drop_column("spritzguss_kalkulationen", name)
    if insp.has_table("materialien"):
        cols = {c["name"] for c in insp.get_columns("materialien")}
        if "injection_pressure_kg_cm2" in cols:
            op.drop_column("materialien", "injection_pressure_kg_cm2")
