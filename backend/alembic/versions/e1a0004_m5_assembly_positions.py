"""M-5: Legacy-Zuordnungen nach assembly_positions kopieren.

Revision ID: e1a0004_m5_assembly_positions
Revises: e1a0003_m1_baugruppe_project_backfill
Create Date: 2026-08-20

Zweck
-----
Kontrollierte Datenmigration (Phase-A-Schritt M-5):

Kopiert Legacy-Zuordnungen idempotent nach assembly_positions, analog zu
build_legacy_synthetic_items():

- baugruppe_spritzguss_zuordnungen  -> PART (price_basis COST)
- baugruppe_kaufteil_zuordnungen    -> PURCHASED_PART (price_basis NULL)
- baugruppe_veredelung_zuordnungen  -> PROCESS (price_basis NULL)

Nur Baugruppen mit gültigem project_id und ohne bestehende assembly_positions.
Keine SUBASSEMBLY-Zeilen. Legacy-Tabellen unverändert. legacy_mode unverändert
(GET bevorzugt assembly_positions sobald Zeilen existieren).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1a0004_m5_assembly_positions"
down_revision: Union[str, Sequence[str], None] = "e1a0003_m1_baugruppe_project_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Idempotente Kopie Legacy -> assembly_positions (nur berechtigte Baugruppen)."""
    op.execute(
        """
        WITH eligible AS (
            SELECT b.id AS baugruppe_id
            FROM baugruppen b
            WHERE b.project_id IS NOT NULL
              AND EXISTS (
                  SELECT 1 FROM projects p WHERE p.id = b.project_id
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM assembly_positions ap
                  WHERE ap.parent_assembly_id = b.id
              )
        ),
        legacy_rows AS (
            SELECT
                e.baugruppe_id AS parent_assembly_id,
                'PART'::varchar AS position_type,
                z.reihenfolge AS reihenfolge,
                z.id AS legacy_row_id,
                0 AS type_tiebreaker,
                z.menge AS quantity,
                1.0::double precision AS quantity_factor,
                'COST'::varchar AS price_basis,
                z.spritzguss_kalkulation_id AS part_calculation_id,
                NULL::integer AS purchased_part_id,
                NULL::integer AS finishing_step_id,
                NULL::double precision AS cost_snapshot,
                z.snapshot_preis AS price_snapshot,
                z.snapshot_bezeichnung AS name_snapshot,
                z.snapshot_teilenummer AS part_number_snapshot,
                ''::varchar AS supplier_snapshot
            FROM eligible e
            JOIN baugruppe_spritzguss_zuordnungen z
                ON z.baugruppe_id = e.baugruppe_id

            UNION ALL

            SELECT
                e.baugruppe_id,
                'PURCHASED_PART',
                z.reihenfolge,
                z.id,
                1,
                z.menge,
                1.0,
                NULL,
                NULL,
                z.kaufteil_id,
                NULL,
                NULL,
                z.snapshot_preis,
                z.snapshot_bezeichnung,
                '',
                z.snapshot_lieferant
            FROM eligible e
            JOIN baugruppe_kaufteil_zuordnungen z
                ON z.baugruppe_id = e.baugruppe_id

            UNION ALL

            SELECT
                e.baugruppe_id,
                'PROCESS',
                z.reihenfolge,
                z.id,
                2,
                1.0,
                z.mengenfaktor,
                NULL,
                NULL,
                NULL,
                z.veredelungsschritt_id,
                z.snapshot_kosten,
                NULL,
                z.snapshot_bezeichnung,
                '',
                ''
            FROM eligible e
            JOIN baugruppe_veredelung_zuordnungen z
                ON z.baugruppe_id = e.baugruppe_id
        ),
        ordered AS (
            SELECT
                parent_assembly_id,
                position_type,
                quantity,
                quantity_factor,
                price_basis,
                part_calculation_id,
                purchased_part_id,
                finishing_step_id,
                cost_snapshot,
                price_snapshot,
                name_snapshot,
                part_number_snapshot,
                supplier_snapshot,
                ROW_NUMBER() OVER (
                    PARTITION BY parent_assembly_id
                    ORDER BY
                        COALESCE(reihenfolge, 999999),
                        type_tiebreaker,
                        legacy_row_id
                )::integer AS sequence
            FROM legacy_rows
        )
        INSERT INTO assembly_positions (
            parent_assembly_id,
            position_type,
            sequence,
            quantity,
            quantity_factor,
            price_basis,
            active,
            label,
            part_calculation_id,
            purchased_part_id,
            child_assembly_id,
            finishing_step_id,
            cost_snapshot,
            price_snapshot,
            name_snapshot,
            part_number_snapshot,
            supplier_snapshot,
            snapshots_captured_at,
            created_at,
            updated_at
        )
        SELECT
            parent_assembly_id,
            position_type,
            sequence,
            quantity,
            quantity_factor,
            price_basis,
            TRUE,
            NULL,
            part_calculation_id,
            purchased_part_id,
            NULL,
            finishing_step_id,
            cost_snapshot,
            price_snapshot,
            name_snapshot,
            part_number_snapshot,
            supplier_snapshot,
            NULL,
            NOW(),
            NOW()
        FROM ordered
        """
    )


def downgrade() -> None:
    """Best-effort Downgrade – keine pauschale Löschung von Positionen.

    Rollback-Dokumentation
    ----------------------
    upgrade() erzeugt assembly_positions aus Legacy-Zuordnungen. Ein
    automatisches DELETE aller Positionen wäre unsicher, weil:

    - nach M-5 manuell oder per Struktur-API angelegte Positionen nicht
      von migrierten Zeilen unterscheidbar sind;
    - productive Strukturdaten verloren gehen könnten.

    Deshalb führt dieser Downgrade bewusst **keine** DELETE-/UPDATE-
    Operationen auf assembly_positions oder Legacy-Tabellen aus.

    Für kontrollierte Dev-/Smoke-DBs: Restore aus Backup oder gezieltes
    manuelles Löschen nur bekannter Test-IDs.
    Für Produktion: Backup wiederherstellen.
    """
    return
