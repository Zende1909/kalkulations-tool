"""Phase-B-Tests: Struktur-API (Service-Ebene)."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import (
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
)
from app.schemas.assembly_structure import (
    AssemblyPositionCreateRequest,
    AssemblyPositionInput,
    AssemblyPositionPatchRequest,
    AssemblyStructureReplaceRequest,
)
from app.services.assembly_structure_service import (
    AssemblyStructureError,
    add_position,
    build_legacy_synthetic_positions,
    delete_position,
    get_structure,
    patch_position,
    replace_structure,
)


def _create_phase_b_schema(engine) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            program_id INTEGER,
            project_number VARCHAR(64) NOT NULL DEFAULT '',
            name VARCHAR(255) NOT NULL DEFAULT '',
            component_area VARCHAR(255) NOT NULL DEFAULT '',
            quantity_per_vehicle FLOAT NOT NULL DEFAULT 1,
            status VARCHAR(32) NOT NULL DEFAULT 'Anfrage',
            notes TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppen (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL DEFAULT '',
            teilenummer VARCHAR(100) NOT NULL DEFAULT '',
            kunde VARCHAR(255) NOT NULL DEFAULT '',
            projekt VARCHAR(255) NOT NULL DEFAULT '',
            jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
            beschreibung TEXT NOT NULL DEFAULT '',
            status VARCHAR(32) NOT NULL DEFAULT 'entwurf',
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            linked_project_id INTEGER,
            project_id INTEGER REFERENCES projects(id),
            werk_id INTEGER,
            assembly_type VARCHAR(16) NOT NULL DEFAULT 'TOP_LEVEL',
            structure_version INTEGER NOT NULL DEFAULT 1,
            legacy_mode BOOLEAN NOT NULL DEFAULT 1,
            pricing_status VARCHAR(32) NOT NULL DEFAULT 'NOT_APPLICABLE',
            family_id INTEGER,
            variant_share_pct FLOAT,
            ergebnis TEXT,
            ergebnis_bloecke TEXT,
            snapshots_captured_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS spritzguss_kalkulationen (
            id INTEGER PRIMARY KEY,
            teilebezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            teilenummer VARCHAR(100) NOT NULL DEFAULT '',
            kunde VARCHAR(255) NOT NULL DEFAULT '',
            projekt VARCHAR(255) NOT NULL DEFAULT '',
            jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
            customer_id INTEGER,
            program_id INTEGER,
            project_id INTEGER REFERENCES projects(id),
            calculation_year INTEGER,
            project_volume FLOAT,
            werk_id INTEGER,
            losgroesse INTEGER, losgroesse_modus VARCHAR(16), losgroesse_manuell INTEGER,
            material_id INTEGER,
            schussgewicht_g FLOAT NOT NULL DEFAULT 0,
            teilegewicht_netto_g FLOAT NOT NULL DEFAULT 1,
            ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
            materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
            maschine_id INTEGER,
            zykluszeit_s FLOAT NOT NULL DEFAULT 1,
            kavitaeten INTEGER NOT NULL DEFAULT 1,
            maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
            lohnkosten_id INTEGER,
            lohnstundensatz FLOAT NOT NULL DEFAULT 0,
            werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'amortisation',
            werkzeugkosten_eur FLOAT NOT NULL DEFAULT 0,
            amortisationsvolumen INTEGER,
            mgk_pct FLOAT NOT NULL DEFAULT 0,
            fgk_pct FLOAT NOT NULL DEFAULT 0,
            vvgk_pct FLOAT NOT NULL DEFAULT 0,
            gewinn_pct FLOAT NOT NULL DEFAULT 0,
            skonto_pct FLOAT NOT NULL DEFAULT 0,
            ergebnis TEXT,
            ergebnis_bloecke TEXT,
            notizen TEXT NOT NULL DEFAULT '',
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            maschinen_groesse_modus VARCHAR(16),
            maschinen_groesse_breite_mm FLOAT,
            maschinen_groesse_laenge_mm FLOAT,
            maschinen_groesse_oeffnungen_pct FLOAT,
            maschinen_groesse_proj_flaeche_mm2 FLOAT,
            maschinen_groesse_schwindung_pct FLOAT,
            maschinen_groesse_injection_pressure_kg_cm2 FLOAT,
            maschinen_groesse_proj_flaeche_netto_mm2 FLOAT,
            maschinen_groesse_zuhaltekraft_ohne_sicherheit_t FLOAT,
            maschinen_groesse_sicherheitszuschlag_faktor FLOAT,
            maschinen_groesse_zuhaltekraft_erforderlich_t FLOAT,
            maschinen_groesse_empfohlene_maschine_id INTEGER,
            maschinen_groesse_warnung VARCHAR(512),
            zykluszeit_quelle VARCHAR(16),
            zykluszeit_wandstaerke_mm FLOAT,
            zykluszeit_groessenklasse VARCHAR(16),
                    zykluszeit_prozessaufwand VARCHAR(16),
                    zykluszeit_entnahmeart VARCHAR(16),
            zykluszeit_kuehlzeit_s FLOAT,
            zykluszeit_nebenzeiten_gesamt_s FLOAT,
            zykluszeit_vorschlag_s FLOAT,
            zykluszeit_hinweis VARCHAR(512),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ,
                    teilbild_mime VARCHAR(64),
                    teilbild_data TEXT
                )
        """,
        """
        CREATE TABLE IF NOT EXISTS kaufteile (
            id INTEGER PRIMARY KEY,
            artikelnummer VARCHAR(100) NOT NULL DEFAULT '',
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            beschreibung TEXT NOT NULL DEFAULT '',
            lieferant VARCHAR(255) NOT NULL DEFAULT '',
            einheit VARCHAR(32) NOT NULL DEFAULT 'Stück',
            preis FLOAT NOT NULL DEFAULT 0,
            waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
            gueltig_ab DATE,
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            project_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS veredelungsschritte (
            id INTEGER PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            beschreibung TEXT NOT NULL DEFAULT '',
            taktzeit_s FLOAT NOT NULL DEFAULT 0,
            anzahl_mitarbeiter INTEGER NOT NULL DEFAULT 1,
            lohnkosten_id INTEGER,
            lohnstundensatz FLOAT NOT NULL DEFAULT 0,
            maschinenstundensatz FLOAT,
            verbrauchskosten_je_stueck FLOAT NOT NULL DEFAULT 0,
            ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
            fgk_pct FLOAT NOT NULL DEFAULT 0,
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS investitionen (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL DEFAULT '',
            investment_type VARCHAR(64) NOT NULL DEFAULT 'Werkzeug',
            payment_type VARCHAR(64) NOT NULL DEFAULT 'Einmalzahlung',
            amount FLOAT NOT NULL DEFAULT 0,
            cost_amount FLOAT NOT NULL DEFAULT 0,
            bottom_price FLOAT,
            revenue_amount FLOAT,
            amortization_volume INTEGER,
            cost_per_piece FLOAT,
            project_id VARCHAR(255) NOT NULL DEFAULT '',
            customer VARCHAR(255) NOT NULL DEFAULT '',
            part_name VARCHAR(255) NOT NULL DEFAULT '',
            part_number VARCHAR(255) NOT NULL DEFAULT '',
            calculation_id INTEGER,
            baugruppe_id INTEGER,
            supplier VARCHAR(255) NOT NULL DEFAULT '',
            order_date DATE,
            delivery_date DATE,
            status VARCHAR(64) NOT NULL DEFAULT 'In Planung',
            description TEXT NOT NULL DEFAULT '',
            included_in_unit_price BOOLEAN NOT NULL DEFAULT 0,
            archived BOOLEAN NOT NULL DEFAULT 0,
            linked_project_id INTEGER,
            customer_id INTEGER,
            program_id INTEGER,
            assignment_type VARCHAR(32),
            kaufteil_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppe_spritzguss_zuordnungen (
            id INTEGER PRIMARY KEY,
            baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id),
            spritzguss_kalkulation_id INTEGER NOT NULL,
            menge FLOAT NOT NULL DEFAULT 1,
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            snapshot_preis FLOAT NOT NULL DEFAULT 0,
            snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            snapshot_teilenummer VARCHAR(100) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppe_kaufteil_zuordnungen (
            id INTEGER PRIMARY KEY,
            baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id),
            kaufteil_id INTEGER NOT NULL,
            menge FLOAT NOT NULL DEFAULT 1,
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            snapshot_preis FLOAT NOT NULL DEFAULT 0,
            snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            snapshot_lieferant VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppe_veredelung_zuordnungen (
            id INTEGER PRIMARY KEY,
            baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id),
            veredelungsschritt_id INTEGER NOT NULL,
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            mengenfaktor FLOAT NOT NULL DEFAULT 1,
            snapshot_kosten FLOAT NOT NULL DEFAULT 0,
            snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    AssemblyPosition.__table__.create(engine, checkfirst=True)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    _create_phase_b_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def _seed_project(db, project_id: int = 100) -> int:
    db.execute(text("INSERT INTO projects (id) VALUES (:id)"), {"id": project_id})
    db.commit()
    return project_id


def _seed_top_level(db, *, project_id: int | None = 100, linked_project_id: int | None = None) -> Baugruppe:
    bg = Baugruppe(
        name="Türseitenverkleidung",
        teilenummer="TSV-001",
        project_id=project_id,
        linked_project_id=linked_project_id,
        legacy_mode=True,
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    return bg


def _seed_subassembly(db, *, project_id: int = 100, name: str = "Armauflage") -> Baugruppe:
    bg = Baugruppe(
        name=name,
        teilenummer="AA-001",
        assembly_type="SUBASSEMBLY",
        project_id=project_id,
        legacy_mode=True,
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    return bg


def _seed_part(db, *, project_id: int = 100, part_id: int = 501) -> int:
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen "
            "(id, teilebezeichnung, teilenummer, project_id, ergebnis) "
            "VALUES (:id, :name, :tn, :pid, :erg)"
        ),
        {
            "id": part_id,
            "name": "Grundträger",
            "tn": "GT-001",
            "pid": project_id,
            "erg": json.dumps({"endpreis_je_stueck": 4.2}),
        },
    )
    db.commit()
    return part_id


def _seed_kaufteil(db, kaufteil_id: int = 301, project_id: int = 100) -> int:
    db.execute(
        text(
            "INSERT INTO kaufteile (id, artikelnummer, bezeichnung, lieferant, preis, project_id) "
            "VALUES (:id, 'K-1', 'Clip', 'Lieferant A', 0.25, :pid)"
        ),
        {"id": kaufteil_id, "pid": project_id},
    )
    db.commit()
    return kaufteil_id


def _seed_process(db, process_id: int = 401) -> int:
    db.execute(
        text(
            "INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) "
            "VALUES (:id, 'Endmontage', 'MONTAGE')"
        ),
        {"id": process_id},
    )
    db.commit()
    return process_id


def _put_request(version: int, positions: list[AssemblyPositionInput], **kwargs) -> AssemblyStructureReplaceRequest:
    return AssemblyStructureReplaceRequest(structure_version=version, positions=positions, **kwargs)


def test_get_structure_empty_new_assembly(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    result = get_structure(db, bg.id)
    assert result.positions_source == "empty"
    assert result.positions == []
    assert result.legacy_mode is True


def test_get_structure_legacy_synthetic_mixed_order(db):
    _seed_project(db)
    bg = _seed_top_level(db, project_id=None, linked_project_id=100)
    _seed_part(db)
    _seed_kaufteil(db)
    _seed_process(db)

    db.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=bg.id,
            spritzguss_kalkulation_id=501,
            menge=2,
            reihenfolge=3,
            snapshot_preis=4.2,
            snapshot_bezeichnung="Grundträger",
            snapshot_teilenummer="GT-001",
        )
    )
    db.add(
        BaugruppeKaufteilZuordnung(
            baugruppe_id=bg.id,
            kaufteil_id=301,
            menge=4,
            reihenfolge=1,
            snapshot_preis=0.25,
            snapshot_bezeichnung="Clip",
            snapshot_lieferant="Lieferant A",
        )
    )
    db.add(
        BaugruppeVeredelungZuordnung(
            baugruppe_id=bg.id,
            veredelungsschritt_id=401,
            reihenfolge=2,
            mengenfaktor=1.5,
            snapshot_kosten=3.0,
            snapshot_bezeichnung="Endmontage",
        )
    )
    db.commit()

    result = get_structure(db, bg.id)
    assert result.positions_source == "legacy_synthetic"
    assert [p.sequence for p in result.positions] == [1, 2, 3]
    assert result.positions[0].position_type == "PURCHASED_PART"
    assert result.positions[1].position_type == "PROCESS"
    assert result.positions[2].position_type == "PART"
    assert result.positions[0].legacy_source == "kaufteil"
    assert all(p.id is None for p in result.positions)


def test_put_valid_part_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_part(db)

    result = replace_structure(
        db,
        bg.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="PART",
                    sequence=1,
                    quantity=1,
                    part_calculation_id=501,
                    price_basis="COST",
                )
            ],
        ),
    )
    assert len(result.positions) == 1
    assert result.positions[0].position_type == "PART"
    assert result.legacy_mode is False
    assert result.structure_version == 2
    assert result.positions_source == "assembly_positions"


def test_put_valid_purchased_part_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_kaufteil(db)

    result = replace_structure(
        db,
        bg.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="PURCHASED_PART",
                    sequence=1,
                    quantity=2,
                    purchased_part_id=301,
                )
            ],
        ),
    )
    assert result.positions[0].position_type == "PURCHASED_PART"
    assert result.positions[0].price_basis is None


def test_put_valid_subassembly_position(db):
    _seed_project(db)
    top = _seed_top_level(db)
    sub = _seed_subassembly(db)

    result = replace_structure(
        db,
        top.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="SUBASSEMBLY",
                    sequence=1,
                    quantity=1,
                    child_assembly_id=sub.id,
                    price_basis="COST",
                    label="Armauflage links",
                )
            ],
        ),
    )
    assert result.positions[0].position_type == "SUBASSEMBLY"
    assert result.positions[0].child_assembly is not None
    assert result.positions[0].child_assembly.id == sub.id


def test_put_valid_process_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)

    result = replace_structure(
        db,
        bg.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="PROCESS",
                    sequence=1,
                    quantity=1,
                    quantity_factor=1.5,
                    finishing_step_id=401,
                )
            ],
        ),
    )
    assert result.positions[0].position_type == "PROCESS"
    assert result.positions[0].quantity_factor == 1.5


def test_post_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)

    pos = add_position(
        db,
        bg.id,
        AssemblyPositionCreateRequest(
            position_type="PROCESS",
            sequence=1,
            quantity=1,
            finishing_step_id=401,
        ),
    )
    assert pos.id is not None
    assert pos.position_type == "PROCESS"
    db.refresh(bg)
    assert bg.structure_version == 2
    assert bg.legacy_mode is False


def test_patch_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)
    created = add_position(
        db,
        bg.id,
        AssemblyPositionCreateRequest(
            position_type="PROCESS",
            sequence=1,
            quantity=1,
            finishing_step_id=401,
        ),
    )
    updated = patch_position(
        db,
        bg.id,
        created.id,
        AssemblyPositionPatchRequest(sequence=5, quantity=2, label="Montage 1"),
    )
    assert updated.sequence == 5
    assert updated.quantity == 2
    assert updated.label == "Montage 1"


def test_delete_position(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)
    created = add_position(
        db,
        bg.id,
        AssemblyPositionCreateRequest(
            position_type="PROCESS",
            sequence=1,
            quantity=1,
            finishing_step_id=401,
        ),
    )
    delete_position(db, bg.id, created.id)
    assert db.query(AssemblyPosition).count() == 0

    with pytest.raises(AssemblyStructureError) as exc:
        delete_position(db, bg.id, 9999)
    assert exc.value.status_code == 404


def test_reject_duplicate_sequence(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db, process_id=401)
    _seed_process(db, process_id=402)

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            bg.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="PROCESS",
                        sequence=1,
                        quantity=1,
                        finishing_step_id=401,
                    ),
                    AssemblyPositionInput(
                        position_type="PROCESS",
                        sequence=1,
                        quantity=1,
                        finishing_step_id=402,
                    ),
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_invalid_ref_combination(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_part(db)

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            bg.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="PART",
                        sequence=1,
                        quantity=1,
                        part_calculation_id=501,
                        price_basis="COST",
                        finishing_step_id=401,
                    )
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_top_level_as_child(db):
    _seed_project(db)
    top = _seed_top_level(db)
    other_top = Baugruppe(name="Anderes TOP", teilenummer="TOP-2", project_id=100)
    db.add(other_top)
    db.commit()

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            top.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="SUBASSEMBLY",
                        sequence=1,
                        quantity=1,
                        child_assembly_id=other_top.id,
                        price_basis="COST",
                    )
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_self_reference(db):
    _seed_project(db)
    top = _seed_top_level(db)

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            top.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="SUBASSEMBLY",
                        sequence=1,
                        quantity=1,
                        child_assembly_id=top.id,
                        price_basis="COST",
                    )
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_multi_level_cycle(db):
    _seed_project(db)
    a = _seed_top_level(db)
    b = _seed_subassembly(db, name="B")
    c = _seed_subassembly(db, name="C")

    db.add(
        AssemblyPosition(
            parent_assembly_id=b.id,
            position_type="SUBASSEMBLY",
            sequence=1,
            child_assembly_id=c.id,
            price_basis="COST",
        )
    )
    db.add(
        AssemblyPosition(
            parent_assembly_id=c.id,
            position_type="SUBASSEMBLY",
            sequence=1,
            child_assembly_id=a.id,
            price_basis="COST",
        )
    )
    db.commit()

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            a.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="SUBASSEMBLY",
                        sequence=1,
                        quantity=1,
                        child_assembly_id=b.id,
                        price_basis="COST",
                    )
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_wrong_project_id(db):
    _seed_project(db, 100)
    db.execute(text("INSERT INTO projects (id) VALUES (200)"))
    db.commit()
    bg = _seed_top_level(db, project_id=100)
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id) "
            "VALUES (777, 'Fremdteil', 'F-1', 200)"
        )
    )
    db.commit()

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            bg.id,
            _put_request(
                1,
                [
                    AssemblyPositionInput(
                        position_type="PART",
                        sequence=1,
                        quantity=1,
                        part_calculation_id=777,
                        price_basis="COST",
                    )
                ],
            ),
        )
    assert exc.value.status_code == 400


def test_reject_stale_structure_version(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)

    with pytest.raises(AssemblyStructureError) as exc:
        replace_structure(
            db,
            bg.id,
            _put_request(
                99,
                [
                    AssemblyPositionInput(
                        position_type="PROCESS",
                        sequence=1,
                        quantity=1,
                        finishing_step_id=401,
                    )
                ],
            ),
        )
    assert exc.value.status_code == 409


def test_allow_duplicate_child_assembly_id(db):
    _seed_project(db)
    top = _seed_top_level(db)
    sub = _seed_subassembly(db)

    result = replace_structure(
        db,
        top.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="SUBASSEMBLY",
                    sequence=1,
                    quantity=1,
                    child_assembly_id=sub.id,
                    price_basis="COST",
                    label="links",
                ),
                AssemblyPositionInput(
                    position_type="SUBASSEMBLY",
                    sequence=2,
                    quantity=1,
                    child_assembly_id=sub.id,
                    price_basis="COST",
                    label="rechts",
                ),
            ],
        ),
    )
    assert len(result.positions) == 2
    assert result.positions[0].child_assembly_id == result.positions[1].child_assembly_id


def test_allow_duplicate_finishing_step_id(db):
    _seed_project(db)
    bg = _seed_top_level(db)
    _seed_process(db)

    result = replace_structure(
        db,
        bg.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="PROCESS",
                    sequence=1,
                    quantity=1,
                    finishing_step_id=401,
                    label="Schweißen Tür",
                ),
                AssemblyPositionInput(
                    position_type="PROCESS",
                    sequence=2,
                    quantity=1,
                    finishing_step_id=401,
                    label="Schweißen Armauflage",
                ),
            ],
        ),
    )
    assert len(result.positions) == 2
    assert result.positions[0].finishing_step_id == result.positions[1].finishing_step_id


def test_legacy_tables_unchanged_after_structure_write(db):
    _seed_project(db)
    bg = _seed_top_level(db, project_id=None, linked_project_id=100)
    _seed_part(db)
    _seed_kaufteil(db)
    _seed_process(db)

    db.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=bg.id,
            spritzguss_kalkulation_id=501,
            menge=1,
            reihenfolge=1,
        )
    )
    db.add(
        BaugruppeKaufteilZuordnung(
            baugruppe_id=bg.id,
            kaufteil_id=301,
            menge=1,
            reihenfolge=1,
        )
    )
    db.add(
        BaugruppeVeredelungZuordnung(
            baugruppe_id=bg.id,
            veredelungsschritt_id=401,
            reihenfolge=1,
        )
    )
    db.commit()

    counts_before = (
        db.query(BaugruppeSpritzgussZuordnung).count(),
        db.query(BaugruppeKaufteilZuordnung).count(),
        db.query(BaugruppeVeredelungZuordnung).count(),
    )

    replace_structure(
        db,
        bg.id,
        _put_request(
            1,
            [
                AssemblyPositionInput(
                    position_type="PROCESS",
                    sequence=1,
                    quantity=1,
                    finishing_step_id=401,
                )
            ],
        ),
    )

    counts_after = (
        db.query(BaugruppeSpritzgussZuordnung).count(),
        db.query(BaugruppeKaufteilZuordnung).count(),
        db.query(BaugruppeVeredelungZuordnung).count(),
    )
    assert counts_before == counts_after


def test_legacy_baugruppe_still_loadable_via_legacy_helper(db):
    from app.api.v1.baugruppen import _baugruppe_to_read

    _seed_project(db)
    bg = _seed_top_level(db, project_id=None, linked_project_id=100)
    _seed_part(db)
    db.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=bg.id,
            spritzguss_kalkulation_id=501,
            menge=1,
            reihenfolge=1,
            snapshot_preis=4.2,
            snapshot_bezeichnung="Grundträger",
            snapshot_teilenummer="GT-001",
        )
    )
    db.commit()

    read = _baugruppe_to_read(db, bg)
    assert len(read.spritzguss_zuordnungen) == 1
    assert read.spritzguss_zuordnungen[0].spritzguss_kalkulation_id == 501


def test_legacy_synthetic_tiebreaker_same_reihenfolge(db):
    _seed_project(db)
    bg = _seed_top_level(db, project_id=None, linked_project_id=100)
    _seed_part(db)
    _seed_kaufteil(db)
    _seed_process(db)

    db.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=bg.id,
            spritzguss_kalkulation_id=501,
            menge=1,
            reihenfolge=1,
        )
    )
    db.add(
        BaugruppeKaufteilZuordnung(
            baugruppe_id=bg.id,
            kaufteil_id=301,
            menge=1,
            reihenfolge=1,
        )
    )
    db.add(
        BaugruppeVeredelungZuordnung(
            baugruppe_id=bg.id,
            veredelungsschritt_id=401,
            reihenfolge=1,
        )
    )
    db.commit()

    positions = build_legacy_synthetic_positions(db, bg.id)
    assert [p.position_type for p in positions] == ["PART", "PURCHASED_PART", "PROCESS"]
