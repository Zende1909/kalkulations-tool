"""Baseline: aktueller Schema-Stand (explizite Alembic-DDL).

Revision ID: e1a0001_baseline
Revises:
Create Date: 2026-08-20

Zweck
-----
Versionierter Ausgangspunkt fuer kuenftige, kontrollierte Schema-Aenderungen.

Inhalt
------
Explizite Alembic-DDL (Tabellen, Indizes, Foreign Keys,
Unique-/Check-Constraints, PostgreSQL-Enum, JSONB).

Kein ORM-Helper fuer Tabellenerzeugung. Keine Seed-Daten:

- keine Zuschlagssaetze (weder GEMEINKOSTEN noch vvgk/gewinn/skonto)
- keine Admin-Benutzer
- keine Daten-Updates (z. B. investitionen.status)

Abgebildete Tabellen (19)
-------------------------
users, materialien, maschinen, lohnkosten, zuschlagssaetze,
customers, programs, program_volumes, projects,
spritzguss_kalkulationen, veredelungsschritte,
spritzguss_veredelung_zuordnungen, kaufteile,
baugruppen, baugruppe_spritzguss_zuordnungen,
baugruppe_kaufteil_zuordnungen, baugruppe_veredelung_zuordnungen,
assembly_positions, investitionen

Besonderheiten
--------------
- PostgreSQL-Enum user_role (admin / kalkulator / viewer)
- JSONB-Spalten ergebnis / ergebnis_bloecke (Spritzguss, Baugruppe)
- CHECK-Constraints und partielle Indizes an assembly_positions / baugruppen

Nutzung
-------
Frische DB:

    cd backend
    alembic upgrade head

Bereits vorhandene DB (Schema bereits vorhanden):

    # 1) Schema manuell gegen Models pruefen
    # 2) Nur nach ausdruecklicher Freigabe:
    alembic stamp e1a0001_baseline

Downgrade
---------
Absichtlich nicht unterstuetzt. Ein DROP ALL waere destruktiv.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e1a0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASELINE_TABLES: tuple[str, ...] = (
    "users",
    "materialien",
    "maschinen",
    "lohnkosten",
    "zuschlagssaetze",
    "customers",
    "programs",
    "program_volumes",
    "projects",
    "spritzguss_kalkulationen",
    "veredelungsschritte",
    "spritzguss_veredelung_zuordnungen",
    "kaufteile",
    "baugruppen",
    "baugruppe_spritzguss_zuordnungen",
    "baugruppe_kaufteil_zuordnungen",
    "baugruppe_veredelung_zuordnungen",
    "assembly_positions",
    "investitionen",
)


def upgrade() -> None:
    """Create current schema with explicit Alembic DDL only (no DML/seeds)."""
    op.create_table('customers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_number', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customers_active'), 'customers', ['active'], unique=False)
    op.create_index(op.f('ix_customers_customer_number'), 'customers', ['customer_number'], unique=True)
    op.create_index(op.f('ix_customers_id'), 'customers', ['id'], unique=False)
    op.create_index(op.f('ix_customers_name'), 'customers', ['name'], unique=False)
    op.create_table('kaufteile',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('artikelnummer', sa.String(length=100), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=False),
    sa.Column('lieferant', sa.String(length=255), nullable=False),
    sa.Column('einheit', sa.String(length=32), nullable=False),
    sa.Column('preis', sa.Float(), nullable=False),
    sa.Column('waehrung', sa.String(length=8), nullable=False),
    sa.Column('gueltig_ab', sa.Date(), nullable=True),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_kaufteile_artikelnummer'), 'kaufteile', ['artikelnummer'], unique=False)
    op.create_index(op.f('ix_kaufteile_id'), 'kaufteile', ['id'], unique=False)
    op.create_table('lohnkosten',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('kosten_pro_stunde', sa.Float(), nullable=False),
    sa.Column('kostenstelle', sa.String(length=50), nullable=False),
    sa.Column('gueltig_ab', sa.Date(), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lohnkosten_id'), 'lohnkosten', ['id'], unique=False)
    op.create_table('maschinen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('maschinen_nr', sa.String(length=50), nullable=False),
    sa.Column('stundensatz', sa.Float(), nullable=False),
    sa.Column('schliesskraft_t', sa.Float(), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_maschinen_id'), 'maschinen', ['id'], unique=False)
    op.create_index(op.f('ix_maschinen_maschinen_nr'), 'maschinen', ['maschinen_nr'], unique=True)
    op.create_table('materialien',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('material_nr', sa.String(length=50), nullable=False),
    sa.Column('preis_pro_kg', sa.Float(), nullable=False),
    sa.Column('dichte', sa.Float(), nullable=False),
    sa.Column('waehrung', sa.String(length=3), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_materialien_id'), 'materialien', ['id'], unique=False)
    op.create_index(op.f('ix_materialien_material_nr'), 'materialien', ['material_nr'], unique=True)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('admin', 'kalkulator', 'viewer', name='user_role'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_table('zuschlagssaetze',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('satz_prozent', sa.Float(), nullable=False),
    sa.Column('typ', sa.String(length=50), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zuschlagssaetze_id'), 'zuschlagssaetze', ['id'], unique=False)
    op.create_table('programs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('program_number', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('vehicle_series', sa.String(length=255), nullable=False),
    sa.Column('sop', sa.Date(), nullable=True),
    sa.Column('eop', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('production_plant', sa.String(length=255), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('customer_id', 'program_number', name='uq_program_customer_number')
    )
    op.create_index(op.f('ix_programs_active'), 'programs', ['active'], unique=False)
    op.create_index(op.f('ix_programs_customer_id'), 'programs', ['customer_id'], unique=False)
    op.create_index(op.f('ix_programs_id'), 'programs', ['id'], unique=False)
    op.create_index(op.f('ix_programs_name'), 'programs', ['name'], unique=False)
    op.create_index(op.f('ix_programs_program_number'), 'programs', ['program_number'], unique=False)
    op.create_index(op.f('ix_programs_status'), 'programs', ['status'], unique=False)
    op.create_table('veredelungsschritte',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('veredelungsart', sa.String(length=64), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=False),
    sa.Column('taktzeit_s', sa.Float(), nullable=False),
    sa.Column('anzahl_mitarbeiter', sa.Integer(), nullable=False),
    sa.Column('lohnkosten_id', sa.Integer(), nullable=True),
    sa.Column('lohnstundensatz', sa.Float(), nullable=False),
    sa.Column('maschinenstundensatz', sa.Float(), nullable=True),
    sa.Column('verbrauchskosten_je_stueck', sa.Float(), nullable=False),
    sa.Column('ausschussquote_pct', sa.Float(), nullable=False),
    sa.Column('fgk_pct', sa.Float(), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['lohnkosten_id'], ['lohnkosten.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_veredelungsschritte_id'), 'veredelungsschritte', ['id'], unique=False)
    op.create_index(op.f('ix_veredelungsschritte_reihenfolge'), 'veredelungsschritte', ['reihenfolge'], unique=False)
    op.create_table('program_volumes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('calendar_year', sa.Integer(), nullable=False),
    sa.Column('vehicle_volume', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('program_id', 'calendar_year', name='uq_program_volume_year')
    )
    op.create_index(op.f('ix_program_volumes_calendar_year'), 'program_volumes', ['calendar_year'], unique=False)
    op.create_index(op.f('ix_program_volumes_id'), 'program_volumes', ['id'], unique=False)
    op.create_index(op.f('ix_program_volumes_program_id'), 'program_volumes', ['program_id'], unique=False)
    op.create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('project_number', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('component_area', sa.String(length=255), nullable=False),
    sa.Column('quantity_per_vehicle', sa.Float(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('program_id', 'project_number', name='uq_project_program_number')
    )
    op.create_index(op.f('ix_projects_active'), 'projects', ['active'], unique=False)
    op.create_index(op.f('ix_projects_id'), 'projects', ['id'], unique=False)
    op.create_index(op.f('ix_projects_name'), 'projects', ['name'], unique=False)
    op.create_index(op.f('ix_projects_program_id'), 'projects', ['program_id'], unique=False)
    op.create_index(op.f('ix_projects_project_number'), 'projects', ['project_number'], unique=False)
    op.create_index(op.f('ix_projects_status'), 'projects', ['status'], unique=False)
    op.create_table('baugruppen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('teilenummer', sa.String(length=100), nullable=False),
    sa.Column('kunde', sa.String(length=255), nullable=False),
    sa.Column('projekt', sa.String(length=255), nullable=False),
    sa.Column('jahresstueckzahl', sa.Integer(), nullable=False),
    sa.Column('beschreibung', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('ergebnis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ergebnis_bloecke', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('linked_project_id', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('assembly_type', sa.String(length=16), nullable=False),
    sa.Column('structure_version', sa.Integer(), nullable=False),
    sa.Column('legacy_mode', sa.Boolean(), nullable=False),
    sa.Column('snapshots_captured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pricing_status', sa.String(length=32), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("assembly_type IN ('TOP_LEVEL', 'SUBASSEMBLY')", name='chk_baugruppen_assembly_type'),
    sa.CheckConstraint("pricing_status IN ('NOT_APPLICABLE', 'CALCULATED', 'STALE')", name='chk_baugruppen_pricing_status'),
    sa.ForeignKeyConstraint(['linked_project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_baugruppen_assembly_type'), 'baugruppen', ['assembly_type'], unique=False)
    op.create_index(op.f('ix_baugruppen_id'), 'baugruppen', ['id'], unique=False)
    op.create_index(op.f('ix_baugruppen_linked_project_id'), 'baugruppen', ['linked_project_id'], unique=False)
    op.create_index(op.f('ix_baugruppen_project_id'), 'baugruppen', ['project_id'], unique=False)
    op.create_index(op.f('ix_baugruppen_teilenummer'), 'baugruppen', ['teilenummer'], unique=False)
    op.create_table('spritzguss_kalkulationen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teilebezeichnung', sa.String(length=255), nullable=False),
    sa.Column('teilenummer', sa.String(length=100), nullable=False),
    sa.Column('kunde', sa.String(length=255), nullable=False),
    sa.Column('projekt', sa.String(length=255), nullable=False),
    sa.Column('jahresstueckzahl', sa.Integer(), nullable=False),
    sa.Column('customer_id', sa.Integer(), nullable=True),
    sa.Column('program_id', sa.Integer(), nullable=True),
    sa.Column('project_id', sa.Integer(), nullable=True),
    sa.Column('calculation_year', sa.Integer(), nullable=True),
    sa.Column('project_volume', sa.Float(), nullable=True),
    sa.Column('material_id', sa.Integer(), nullable=True),
    sa.Column('schussgewicht_g', sa.Float(), nullable=False),
    sa.Column('teilegewicht_netto_g', sa.Float(), nullable=False),
    sa.Column('ausschussquote_pct', sa.Float(), nullable=False),
    sa.Column('materialpreis_pro_kg', sa.Float(), nullable=False),
    sa.Column('maschine_id', sa.Integer(), nullable=True),
    sa.Column('zykluszeit_s', sa.Float(), nullable=False),
    sa.Column('kavitaeten', sa.Integer(), nullable=False),
    sa.Column('maschinenstundensatz', sa.Float(), nullable=False),
    sa.Column('lohnkosten_id', sa.Integer(), nullable=True),
    sa.Column('lohnstundensatz', sa.Float(), nullable=False),
    sa.Column('werkzeug_abrechnungsart', sa.String(length=32), nullable=False),
    sa.Column('werkzeugkosten_eur', sa.Float(), nullable=False),
    sa.Column('amortisationsvolumen', sa.Integer(), nullable=True),
    sa.Column('mgk_pct', sa.Float(), nullable=False),
    sa.Column('fgk_pct', sa.Float(), nullable=False),
    sa.Column('vvgk_pct', sa.Float(), nullable=False),
    sa.Column('gewinn_pct', sa.Float(), nullable=False),
    sa.Column('skonto_pct', sa.Float(), nullable=False),
    sa.Column('ergebnis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('ergebnis_bloecke', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('notizen', sa.Text(), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['lohnkosten_id'], ['lohnkosten.id'], ),
    sa.ForeignKeyConstraint(['maschine_id'], ['maschinen.id'], ),
    sa.ForeignKeyConstraint(['material_id'], ['materialien.id'], ),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_spritzguss_kalkulationen_calculation_year'), 'spritzguss_kalkulationen', ['calculation_year'], unique=False)
    op.create_index(op.f('ix_spritzguss_kalkulationen_customer_id'), 'spritzguss_kalkulationen', ['customer_id'], unique=False)
    op.create_index(op.f('ix_spritzguss_kalkulationen_id'), 'spritzguss_kalkulationen', ['id'], unique=False)
    op.create_index(op.f('ix_spritzguss_kalkulationen_program_id'), 'spritzguss_kalkulationen', ['program_id'], unique=False)
    op.create_index(op.f('ix_spritzguss_kalkulationen_project_id'), 'spritzguss_kalkulationen', ['project_id'], unique=False)
    op.create_index(op.f('ix_spritzguss_kalkulationen_teilenummer'), 'spritzguss_kalkulationen', ['teilenummer'], unique=False)
    op.create_table('assembly_positions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('parent_assembly_id', sa.Integer(), nullable=False),
    sa.Column('position_type', sa.String(length=32), nullable=False),
    sa.Column('sequence', sa.Integer(), nullable=False),
    sa.Column('quantity', sa.Float(), nullable=False),
    sa.Column('quantity_factor', sa.Float(), nullable=False),
    sa.Column('price_basis', sa.String(length=16), nullable=True),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('label', sa.String(length=255), nullable=True),
    sa.Column('part_calculation_id', sa.Integer(), nullable=True),
    sa.Column('purchased_part_id', sa.Integer(), nullable=True),
    sa.Column('child_assembly_id', sa.Integer(), nullable=True),
    sa.Column('finishing_step_id', sa.Integer(), nullable=True),
    sa.Column('cost_snapshot', sa.Float(), nullable=True),
    sa.Column('price_snapshot', sa.Float(), nullable=True),
    sa.Column('name_snapshot', sa.String(length=255), nullable=False),
    sa.Column('part_number_snapshot', sa.String(length=100), nullable=False),
    sa.Column('supplier_snapshot', sa.String(length=255), nullable=False),
    sa.Column('snapshots_captured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("\n            position_type <> 'PART'\n            OR (\n                part_calculation_id IS NOT NULL\n                AND purchased_part_id IS NULL\n                AND child_assembly_id IS NULL\n                AND finishing_step_id IS NULL\n                AND price_basis IS NOT NULL\n            )\n            ", name='chk_ap_part_refs'),
    sa.CheckConstraint("\n            position_type <> 'PROCESS'\n            OR (\n                finishing_step_id IS NOT NULL\n                AND part_calculation_id IS NULL\n                AND purchased_part_id IS NULL\n                AND child_assembly_id IS NULL\n                AND price_basis IS NULL\n            )\n            ", name='chk_ap_process_refs'),
    sa.CheckConstraint("\n            position_type <> 'PURCHASED_PART'\n            OR (\n                purchased_part_id IS NOT NULL\n                AND part_calculation_id IS NULL\n                AND child_assembly_id IS NULL\n                AND finishing_step_id IS NULL\n                AND price_basis IS NULL\n            )\n            ", name='chk_ap_purchased_refs'),
    sa.CheckConstraint("\n            position_type <> 'SUBASSEMBLY'\n            OR (\n                child_assembly_id IS NOT NULL\n                AND part_calculation_id IS NULL\n                AND purchased_part_id IS NULL\n                AND finishing_step_id IS NULL\n                AND price_basis IS NOT NULL\n            )\n            ", name='chk_ap_subassembly_refs'),
    sa.CheckConstraint("position_type IN ('PART', 'PURCHASED_PART', 'SUBASSEMBLY', 'PROCESS')", name='chk_ap_position_type'),
    sa.CheckConstraint("price_basis IS NULL OR price_basis IN ('COST', 'SELF_COST', 'SALES_PRICE')", name='chk_ap_price_basis'),
    sa.CheckConstraint('quantity > 0', name='chk_ap_quantity_positive'),
    sa.CheckConstraint('quantity_factor > 0', name='chk_ap_quantity_factor_positive'),
    sa.CheckConstraint('sequence >= 1', name='chk_ap_sequence_positive'),
    sa.ForeignKeyConstraint(['child_assembly_id'], ['baugruppen.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['finishing_step_id'], ['veredelungsschritte.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['parent_assembly_id'], ['baugruppen.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['part_calculation_id'], ['spritzguss_kalkulationen.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['purchased_part_id'], ['kaufteile.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ap_child_assembly', 'assembly_positions', ['child_assembly_id'], unique=False, postgresql_where=sa.text('child_assembly_id IS NOT NULL'), sqlite_where=sa.text('child_assembly_id IS NOT NULL'))
    op.create_index('idx_ap_parent_assembly', 'assembly_positions', ['parent_assembly_id'], unique=False)
    op.create_index('idx_ap_part_calculation', 'assembly_positions', ['part_calculation_id'], unique=False, postgresql_where=sa.text('part_calculation_id IS NOT NULL'), sqlite_where=sa.text('part_calculation_id IS NOT NULL'))
    op.create_index(op.f('ix_assembly_positions_id'), 'assembly_positions', ['id'], unique=False)
    op.create_index('uq_ap_parent_part', 'assembly_positions', ['parent_assembly_id', 'part_calculation_id'], unique=True, postgresql_where=sa.text("position_type = 'PART'"), sqlite_where=sa.text("position_type = 'PART'"))
    op.create_index('uq_ap_parent_sequence', 'assembly_positions', ['parent_assembly_id', 'sequence'], unique=True)
    op.create_table('baugruppe_kaufteil_zuordnungen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('baugruppe_id', sa.Integer(), nullable=False),
    sa.Column('kaufteil_id', sa.Integer(), nullable=False),
    sa.Column('menge', sa.Float(), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('snapshot_preis', sa.Float(), nullable=False),
    sa.Column('snapshot_bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('snapshot_lieferant', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baugruppe_id'], ['baugruppen.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['kaufteil_id'], ['kaufteile.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('baugruppe_id', 'kaufteil_id', name='uq_baugruppe_kaufteil')
    )
    op.create_index(op.f('ix_baugruppe_kaufteil_zuordnungen_baugruppe_id'), 'baugruppe_kaufteil_zuordnungen', ['baugruppe_id'], unique=False)
    op.create_index(op.f('ix_baugruppe_kaufteil_zuordnungen_id'), 'baugruppe_kaufteil_zuordnungen', ['id'], unique=False)
    op.create_index(op.f('ix_baugruppe_kaufteil_zuordnungen_kaufteil_id'), 'baugruppe_kaufteil_zuordnungen', ['kaufteil_id'], unique=False)
    op.create_table('baugruppe_spritzguss_zuordnungen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('baugruppe_id', sa.Integer(), nullable=False),
    sa.Column('spritzguss_kalkulation_id', sa.Integer(), nullable=False),
    sa.Column('menge', sa.Float(), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('snapshot_preis', sa.Float(), nullable=False),
    sa.Column('snapshot_bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('snapshot_teilenummer', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baugruppe_id'], ['baugruppen.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['spritzguss_kalkulation_id'], ['spritzguss_kalkulationen.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('baugruppe_id', 'spritzguss_kalkulation_id', name='uq_baugruppe_spritzguss')
    )
    op.create_index(op.f('ix_baugruppe_spritzguss_zuordnungen_baugruppe_id'), 'baugruppe_spritzguss_zuordnungen', ['baugruppe_id'], unique=False)
    op.create_index(op.f('ix_baugruppe_spritzguss_zuordnungen_id'), 'baugruppe_spritzguss_zuordnungen', ['id'], unique=False)
    op.create_index(op.f('ix_baugruppe_spritzguss_zuordnungen_spritzguss_kalkulation_id'), 'baugruppe_spritzguss_zuordnungen', ['spritzguss_kalkulation_id'], unique=False)
    op.create_table('baugruppe_veredelung_zuordnungen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('baugruppe_id', sa.Integer(), nullable=False),
    sa.Column('veredelungsschritt_id', sa.Integer(), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('mengenfaktor', sa.Float(), nullable=False),
    sa.Column('snapshot_kosten', sa.Float(), nullable=False),
    sa.Column('snapshot_bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baugruppe_id'], ['baugruppen.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['veredelungsschritt_id'], ['veredelungsschritte.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('baugruppe_id', 'veredelungsschritt_id', name='uq_baugruppe_veredelung')
    )
    op.create_index(op.f('ix_baugruppe_veredelung_zuordnungen_baugruppe_id'), 'baugruppe_veredelung_zuordnungen', ['baugruppe_id'], unique=False)
    op.create_index(op.f('ix_baugruppe_veredelung_zuordnungen_id'), 'baugruppe_veredelung_zuordnungen', ['id'], unique=False)
    op.create_index(op.f('ix_baugruppe_veredelung_zuordnungen_veredelungsschritt_id'), 'baugruppe_veredelung_zuordnungen', ['veredelungsschritt_id'], unique=False)
    op.create_table('investitionen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('investment_type', sa.String(length=64), nullable=False),
    sa.Column('payment_type', sa.String(length=64), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('amortization_volume', sa.Integer(), nullable=True),
    sa.Column('cost_per_piece', sa.Float(), nullable=True),
    sa.Column('project_id', sa.String(length=255), nullable=False),
    sa.Column('customer', sa.String(length=255), nullable=False),
    sa.Column('part_name', sa.String(length=255), nullable=False),
    sa.Column('part_number', sa.String(length=255), nullable=False),
    sa.Column('calculation_id', sa.Integer(), nullable=True),
    sa.Column('baugruppe_id', sa.Integer(), nullable=True),
    sa.Column('supplier', sa.String(length=255), nullable=False),
    sa.Column('order_date', sa.Date(), nullable=True),
    sa.Column('delivery_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('included_in_unit_price', sa.Boolean(), nullable=False),
    sa.Column('archived', sa.Boolean(), nullable=False),
    sa.Column('linked_project_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['baugruppe_id'], ['baugruppen.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['calculation_id'], ['spritzguss_kalkulationen.id'], ),
    sa.ForeignKeyConstraint(['linked_project_id'], ['projects.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investitionen_archived'), 'investitionen', ['archived'], unique=False)
    op.create_index(op.f('ix_investitionen_baugruppe_id'), 'investitionen', ['baugruppe_id'], unique=False)
    op.create_index(op.f('ix_investitionen_calculation_id'), 'investitionen', ['calculation_id'], unique=False)
    op.create_index(op.f('ix_investitionen_customer'), 'investitionen', ['customer'], unique=False)
    op.create_index(op.f('ix_investitionen_id'), 'investitionen', ['id'], unique=False)
    op.create_index(op.f('ix_investitionen_linked_project_id'), 'investitionen', ['linked_project_id'], unique=False)
    op.create_index(op.f('ix_investitionen_name'), 'investitionen', ['name'], unique=False)
    op.create_index(op.f('ix_investitionen_project_id'), 'investitionen', ['project_id'], unique=False)
    op.create_index(op.f('ix_investitionen_status'), 'investitionen', ['status'], unique=False)
    op.create_table('spritzguss_veredelung_zuordnungen',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kalkulation_id', sa.Integer(), nullable=False),
    sa.Column('veredelungsschritt_id', sa.Integer(), nullable=False),
    sa.Column('reihenfolge', sa.Integer(), nullable=False),
    sa.Column('aktiv', sa.Boolean(), nullable=False),
    sa.Column('mengenfaktor', sa.Float(), nullable=False),
    sa.Column('snapshot_bezeichnung', sa.String(length=255), nullable=False),
    sa.Column('snapshot_veredelungsart', sa.String(length=64), nullable=False),
    sa.Column('snapshot_kosten_inkl_ausschuss', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['kalkulation_id'], ['spritzguss_kalkulationen.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['veredelungsschritt_id'], ['veredelungsschritte.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kalkulation_id', 'veredelungsschritt_id', name='uq_spritzguss_veredelung_kalk_schritt')
    )
    op.create_index(op.f('ix_spritzguss_veredelung_zuordnungen_id'), 'spritzguss_veredelung_zuordnungen', ['id'], unique=False)
    op.create_index(op.f('ix_spritzguss_veredelung_zuordnungen_kalkulation_id'), 'spritzguss_veredelung_zuordnungen', ['kalkulation_id'], unique=False)
    op.create_index(op.f('ix_spritzguss_veredelung_zuordnungen_veredelungsschritt_id'), 'spritzguss_veredelung_zuordnungen', ['veredelungsschritt_id'], unique=False)



def downgrade() -> None:
    """Baseline-Downgrade ist absichtlich blockiert (kein DROP ALL)."""
    raise NotImplementedError(
        "Downgrade der Baseline-Revision e1a0001_baseline ist nicht unterstuetzt. "
        "Ein DROP aller Tabellen waere destruktiv. "
        "Fuer lokale Experimente eine frische Datenbank verwenden und "
        "nicht gegen produktive oder bestehende Datenbanken downgraden."
    )
