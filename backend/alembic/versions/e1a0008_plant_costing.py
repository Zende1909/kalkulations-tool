"""Plant costing: Land/Werk, Maschinenparameter, Lohnrollen, Setup-Losgröße.

Revision ID: e1a0008_plant_costing
Revises: e1a0007_veredelung_snapshot_yield
Create Date: 2026-08-26

Nur DDL – keine DML/Seeds. Bestehende Kalkulationen unverändert.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a0008_plant_costing"
down_revision: Union[str, Sequence[str], None] = "e1a0007_veredelung_snapshot_yield"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "laender",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_laender_code", "laender", ["code"], unique=True)
    op.create_index("ix_laender_id", "laender", ["id"])

    op.create_table(
        "werke",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("land_id", sa.Integer(), sa.ForeignKey("laender.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False, server_default="EUR"),
        sa.Column("fx_to_eur", sa.Float(), nullable=False, server_default="1"),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_werke_code", "werke", ["code"], unique=True)
    op.create_index("ix_werke_land_id", "werke", ["land_id"])
    op.create_index("ix_werke_id", "werke", ["id"])

    op.create_table(
        "werk_zuschlaege",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("werk_id", sa.Integer(), sa.ForeignKey("werke.id", ondelete="CASCADE"), nullable=False),
        sa.Column("typ", sa.String(length=64), nullable=False),
        sa.Column("bezeichnung", sa.String(length=255), nullable=False),
        sa.Column("satz_prozent", sa.Float(), nullable=False),
        sa.Column("kostenbasis", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("werk_id", "typ", name="uq_werk_zuschlag_werk_typ"),
    )
    op.create_index("ix_werk_zuschlaege_werk_id", "werk_zuschlaege", ["werk_id"])
    op.create_index("ix_werk_zuschlaege_typ", "werk_zuschlaege", ["typ"])

    # Maschinen-Erweiterungen
    for col, typ in (
        ("werk_id", sa.Integer()),
        ("maschinentyp", sa.String(128)),
        ("variante", sa.String(64)),
        ("source_currency", sa.String(8)),
        ("arbeitstage_pro_jahr", sa.Float()),
        ("schichten_pro_tag", sa.Float()),
        ("stunden_pro_schicht", sa.Float()),
        ("oee", sa.Float()),
        ("investment", sa.Float()),
        ("flaeche_sqm", sa.Float()),
        ("space_cost_satz_pro_sqm_jahr", sa.Float()),
        ("abschreibungsdauer_jahre", sa.Float()),
        ("zinssatz", sa.Float()),
        ("versicherungssatz", sa.Float()),
        ("instandhaltungssatz", sa.Float()),
        ("stromverbrauch_kwh_h", sa.Float()),
        ("strompreis", sa.Float()),
        ("druckluftverbrauch_m3_h", sa.Float()),
        ("druckluftpreis", sa.Float()),
        ("kuehlwasserverbrauch_m3_h", sa.Float()),
        ("kuehlwasserpreis", sa.Float()),
        ("setup_zeit_min", sa.Float()),
        ("setup_mitarbeiter", sa.Float()),
        ("jahresstunden", sa.Float()),
        ("space_costs_pro_stunde", sa.Float()),
        ("abschreibung_pro_stunde", sa.Float()),
        ("zinsen_pro_stunde", sa.Float()),
        ("versicherung_pro_stunde", sa.Float()),
        ("instandhaltung_pro_stunde", sa.Float()),
        ("energie_pro_stunde", sa.Float()),
        ("stundensatz_source", sa.Float()),
        ("rate_updated_at", sa.DateTime(timezone=True)),
    ):
        op.add_column("maschinen", sa.Column(col, typ, nullable=True))
    op.create_foreign_key(
        "fk_maschinen_werk_id", "maschinen", "werke", ["werk_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_maschinen_werk_id", "maschinen", ["werk_id"])

    op.add_column("lohnkosten", sa.Column("werk_id", sa.Integer(), nullable=True))
    op.add_column(
        "lohnkosten",
        sa.Column("rolle", sa.String(32), nullable=False, server_default="sonstig"),
    )
    op.add_column("lohnkosten", sa.Column("source_currency", sa.String(8), nullable=True))
    op.add_column("lohnkosten", sa.Column("source_rate", sa.Float(), nullable=True))
    op.create_foreign_key(
        "fk_lohnkosten_werk_id", "lohnkosten", "werke", ["werk_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_lohnkosten_werk_id", "lohnkosten", ["werk_id"])

    op.add_column("spritzguss_kalkulationen", sa.Column("werk_id", sa.Integer(), nullable=True))
    op.add_column("spritzguss_kalkulationen", sa.Column("losgroesse", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_spritzguss_werk_id",
        "spritzguss_kalkulationen",
        "werke",
        ["werk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_spritzguss_kalkulationen_werk_id", "spritzguss_kalkulationen", ["werk_id"])

    op.add_column("baugruppen", sa.Column("werk_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_baugruppen_werk_id", "baugruppen", "werke", ["werk_id"], ["id"], ondelete="SET NULL"
    )
    op.create_index("ix_baugruppen_werk_id", "baugruppen", ["werk_id"])


def downgrade() -> None:
    op.drop_constraint("fk_baugruppen_werk_id", "baugruppen", type_="foreignkey")
    op.drop_index("ix_baugruppen_werk_id", "baugruppen")
    op.drop_column("baugruppen", "werk_id")

    op.drop_constraint("fk_spritzguss_werk_id", "spritzguss_kalkulationen", type_="foreignkey")
    op.drop_index("ix_spritzguss_kalkulationen_werk_id", "spritzguss_kalkulationen")
    op.drop_column("spritzguss_kalkulationen", "losgroesse")
    op.drop_column("spritzguss_kalkulationen", "werk_id")

    op.drop_constraint("fk_lohnkosten_werk_id", "lohnkosten", type_="foreignkey")
    op.drop_index("ix_lohnkosten_werk_id", "lohnkosten")
    op.drop_column("lohnkosten", "source_rate")
    op.drop_column("lohnkosten", "source_currency")
    op.drop_column("lohnkosten", "rolle")
    op.drop_column("lohnkosten", "werk_id")

    op.drop_constraint("fk_maschinen_werk_id", "maschinen", type_="foreignkey")
    op.drop_index("ix_maschinen_werk_id", "maschinen")
    for col in (
        "rate_updated_at",
        "stundensatz_source",
        "energie_pro_stunde",
        "instandhaltung_pro_stunde",
        "versicherung_pro_stunde",
        "zinsen_pro_stunde",
        "abschreibung_pro_stunde",
        "space_costs_pro_stunde",
        "jahresstunden",
        "setup_mitarbeiter",
        "setup_zeit_min",
        "kuehlwasserpreis",
        "kuehlwasserverbrauch_m3_h",
        "druckluftpreis",
        "druckluftverbrauch_m3_h",
        "strompreis",
        "stromverbrauch_kwh_h",
        "instandhaltungssatz",
        "versicherungssatz",
        "zinssatz",
        "abschreibungsdauer_jahre",
        "space_cost_satz_pro_sqm_jahr",
        "flaeche_sqm",
        "investment",
        "oee",
        "stunden_pro_schicht",
        "schichten_pro_tag",
        "arbeitstage_pro_jahr",
        "source_currency",
        "variante",
        "maschinentyp",
        "werk_id",
    ):
        op.drop_column("maschinen", col)

    op.drop_table("werk_zuschlaege")
    op.drop_table("werke")
    op.drop_table("laender")
