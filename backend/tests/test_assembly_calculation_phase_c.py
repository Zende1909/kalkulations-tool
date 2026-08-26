"""Phase-C-Tests: rekursive Baugruppen-Kalkulation."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe
from app.schemas.assembly_calculation import AssemblyRecalculateRequest
from app.services.assembly_calculation import (
    AssemblyCalculationError,
    MarkupRates,
    PositionCalcInput,
    calculate_assembly,
    calculate_position_line,
)
from app.services.assembly_process_validation import collect_duplicate_process_warnings
from app.services.assembly_recalculation_service import (
    AssemblyRecalculationError,
    recalculate_assembly_tree,
)
from app.services.assembly_structure_service import get_structure, replace_structure
from app.schemas.assembly_structure import AssemblyPositionInput, AssemblyStructureReplaceRequest


def _create_phase_c_schema(engine) -> None:
    statements = [
        "CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, program_id INTEGER, name VARCHAR(255) DEFAULT '', active BOOLEAN DEFAULT 1)",
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
            project_id INTEGER,
            werk_id INTEGER,
            losgroesse INTEGER,
            schussgewicht_g FLOAT NOT NULL DEFAULT 0,
            teilegewicht_netto_g FLOAT NOT NULL DEFAULT 100,
            ausschussquote_pct FLOAT NOT NULL DEFAULT 10,
            materialpreis_pro_kg FLOAT NOT NULL DEFAULT 10,
            material_nominierung VARCHAR(32),
            zykluszeit_s FLOAT NOT NULL DEFAULT 36,
            kavitaeten INTEGER NOT NULL DEFAULT 2,
            maschinenstundensatz FLOAT NOT NULL DEFAULT 100,
            lohnstundensatz FLOAT NOT NULL DEFAULT 50,
            werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'amortisation',
            werkzeugkosten_eur FLOAT NOT NULL DEFAULT 10000,
            amortisationsvolumen INTEGER DEFAULT 10000,
            mgk_pct FLOAT NOT NULL DEFAULT 5,
            fgk_pct FLOAT NOT NULL DEFAULT 20,
            vvgk_pct FLOAT NOT NULL DEFAULT 10,
            gewinn_pct FLOAT NOT NULL DEFAULT 10,
            skonto_pct FLOAT NOT NULL DEFAULT 2,
            ergebnis TEXT,
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS spritzguss_veredelung_zuordnungen (
            id INTEGER PRIMARY KEY,
            kalkulation_id INTEGER NOT NULL,
            veredelungsschritt_id INTEGER NOT NULL,
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            mengenfaktor FLOAT NOT NULL DEFAULT 1,
            snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            snapshot_veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
            snapshot_kosten_inkl_ausschuss FLOAT NOT NULL DEFAULT 0,
            snapshot_kosten_vor_ausschuss FLOAT,
            snapshot_ausschussquote_pct FLOAT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            nominierung VARCHAR(32),
            customer_id INTEGER,
            program_id INTEGER,
            project_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS veredelungsschritte (
            id INTEGER PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            veredelungsart VARCHAR(64) NOT NULL DEFAULT 'Montage',
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            beschreibung TEXT NOT NULL DEFAULT '',
            taktzeit_s FLOAT NOT NULL DEFAULT 60,
            anzahl_mitarbeiter INTEGER NOT NULL DEFAULT 1,
            lohnkosten_id INTEGER,
            lohnstundensatz FLOAT NOT NULL DEFAULT 50,
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
        CREATE TABLE IF NOT EXISTS zuschlagssaetze (
            id INTEGER PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            satz_prozent FLOAT NOT NULL DEFAULT 0,
            typ VARCHAR(50) NOT NULL DEFAULT '',
            aktiv BOOLEAN NOT NULL DEFAULT 1,
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
    _create_phase_c_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def _seed_project(db, project_id: int = 100) -> None:
    db.execute(text("INSERT INTO projects (id) VALUES (:id)"), {"id": project_id})
    db.commit()


def _top(db, project_id: int = 100) -> Baugruppe:
    bg = Baugruppe(name="TSV", teilenummer="TSV-1", project_id=project_id, legacy_mode=False)
    db.add(bg)
    db.commit()
    db.refresh(bg)
    return bg


def _sub(db, project_id: int = 100, name: str = "Armauflage") -> Baugruppe:
    bg = Baugruppe(
        name=name,
        teilenummer="AA-1",
        assembly_type="SUBASSEMBLY",
        project_id=project_id,
        legacy_mode=False,
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    return bg


def _put(db, bg_id: int, positions: list[AssemblyPositionInput]) -> None:
    replace_structure(
        db,
        bg_id,
        AssemblyStructureReplaceRequest(structure_version=1, positions=positions),
    )


def _part_pos(**kwargs) -> AssemblyPositionInput:
    base = dict(
        position_type="PART",
        sequence=1,
        quantity=1.0,
        part_calculation_id=501,
        price_basis="COST",
    )
    base.update(kwargs)
    return AssemblyPositionInput(**base)


def test_part_cost_uses_cost_snapshot_only():
    pos = PositionCalcInput(
        position_id=1,
        position_type="PART",
        sequence=1,
        quantity=2,
        quantity_factor=1,
        price_basis="COST",
        active=True,
        label=None,
        name_snapshot="Teil",
        cost_snapshot=4.2,
        price_snapshot=12.5,
    )
    line, warnings = calculate_position_line(pos, position_index=1)
    assert line.zwischensumme == pytest.approx(8.4)
    assert line.einzelpreis == pytest.approx(4.2)
    assert warnings == []


def test_part_cost_missing_snapshot_raises():
    pos = PositionCalcInput(
        position_id=1,
        position_type="PART",
        sequence=1,
        quantity=1,
        quantity_factor=1,
        price_basis="COST",
        active=True,
        label=None,
        name_snapshot="Teil",
        cost_snapshot=None,
        price_snapshot=12.5,
    )
    with pytest.raises(AssemblyCalculationError):
        calculate_position_line(pos, position_index=1)


def test_part_self_cost_raises():
    pos = PositionCalcInput(
        position_id=1,
        position_type="PART",
        sequence=1,
        quantity=1,
        quantity_factor=1,
        price_basis="SELF_COST",
        active=True,
        label=None,
        name_snapshot="Teil",
        cost_snapshot=4.2,
        price_snapshot=12.5,
    )
    with pytest.raises(AssemblyCalculationError, match="SELF_COST"):
        calculate_position_line(pos, position_index=1)


def test_part_sales_price_emits_warning():
    pos = PositionCalcInput(
        position_id=1,
        position_type="PART",
        sequence=1,
        quantity=1,
        quantity_factor=1,
        price_basis="SALES_PRICE",
        active=True,
        label=None,
        name_snapshot="Teil",
        cost_snapshot=4.2,
        price_snapshot=12.5,
    )
    line, warnings = calculate_position_line(pos, position_index=1)
    assert line.zwischensumme == pytest.approx(12.5)
    assert any(w.code == "DOUBLE_MARKUP_RISK" for w in warnings)


def test_purchased_part_calculation():
    pos = PositionCalcInput(
        position_id=2,
        position_type="PURCHASED_PART",
        sequence=2,
        quantity=4,
        quantity_factor=1,
        price_basis=None,
        active=True,
        label=None,
        name_snapshot="Clip",
        cost_snapshot=None,
        price_snapshot=0.25,
    )
    line, _ = calculate_position_line(pos, position_index=1)
    assert line.zwischensumme == pytest.approx(1.0)


def test_process_calculation():
    pos = PositionCalcInput(
        position_id=3,
        position_type="PROCESS",
        sequence=3,
        quantity=1,
        quantity_factor=1.5,
        price_basis=None,
        active=True,
        label=None,
        name_snapshot="Montage",
        cost_snapshot=3.0,
        price_snapshot=None,
    )
    line, _ = calculate_position_line(pos, position_index=1)
    assert line.zwischensumme == pytest.approx(4.5)


def test_subassembly_only_cost_and_hk():
    result = calculate_assembly(
        assembly_type="SUBASSEMBLY",
        positions=[
            PositionCalcInput(
                position_id=1,
                position_type="PART",
                sequence=1,
                quantity=1,
                quantity_factor=1,
                price_basis="COST",
                active=True,
                label=None,
                name_snapshot="Teil",
                cost_snapshot=4.2,
                price_snapshot=None,
            )
        ],
    )
    assert result.herstellkosten == pytest.approx(4.2)
    assert result.markup_applied is False
    assert result.endpreis_je_stueck is None


def test_top_level_with_markups(db):
    result = calculate_assembly(
        assembly_type="TOP_LEVEL",
        positions=[
            PositionCalcInput(
                position_id=1,
                position_type="PART",
                sequence=1,
                quantity=1,
                quantity_factor=1,
                price_basis="COST",
                active=True,
                label=None,
                name_snapshot="Teil",
                cost_snapshot=100.0,
                price_snapshot=150.0,
            )
        ],
        markup_rates=MarkupRates(vvgk_pct=10, gewinn_pct=10, skonto_pct=2, fgk_pct=22),
    )
    assert result.herstellkosten == pytest.approx(100.0)
    assert result.vvgk == pytest.approx(10.0)
    assert result.selbstkosten == pytest.approx(110.0)
    assert result.markup_applied is True
    assert result.endpreis_je_stueck is not None


def test_inactive_position_skipped():
    result = calculate_assembly(
        assembly_type="TOP_LEVEL",
        positions=[
            PositionCalcInput(
                position_id=1,
                position_type="PART",
                sequence=1,
                quantity=1,
                quantity_factor=1,
                price_basis="COST",
                active=False,
                label=None,
                name_snapshot="Teil",
                cost_snapshot=100.0,
                price_snapshot=None,
            ),
            PositionCalcInput(
                position_id=2,
                position_type="PART",
                sequence=2,
                quantity=1,
                quantity_factor=1,
                price_basis="COST",
                active=True,
                label=None,
                name_snapshot="Teil2",
                cost_snapshot=50.0,
                price_snapshot=None,
            ),
        ],
        markup_rates=MarkupRates(vvgk_pct=0, gewinn_pct=0, skonto_pct=0, fgk_pct=0),
    )
    assert result.herstellkosten == pytest.approx(50.0)
    assert len(result.position_lines) == 1


def test_duplicate_process_warning_not_blocking(db):
    _seed_project(db)
    top = _top(db)
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id, material_nominierung) "
            "VALUES (501, 'Träger', 'T-1', 100, 'selbstnominiert')"
        )
    )
    db.execute(
        text(
            "INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart, taktzeit_s) "
            "VALUES (33, 'Schäumen', 'Sonstige', 60)"
        )
    )
    db.execute(
        text(
            "INSERT INTO spritzguss_veredelung_zuordnungen "
            "(id, kalkulation_id, veredelungsschritt_id, reihenfolge, snapshot_bezeichnung, snapshot_kosten_inkl_ausschuss) "
            "VALUES (1, 501, 33, 1, 'Schäumen', 1.5)"
        )
    )
    db.commit()

    db.add(
        AssemblyPosition(
            parent_assembly_id=top.id,
            position_type="PART",
            sequence=1,
            part_calculation_id=501,
            price_basis="COST",
            cost_snapshot=4.2,
            quantity=1,
        )
    )
    db.add(
        AssemblyPosition(
            parent_assembly_id=top.id,
            position_type="PROCESS",
            sequence=2,
            finishing_step_id=33,
            cost_snapshot=1.5,
            quantity=1,
            quantity_factor=1,
            name_snapshot="Schäumen",
        )
    )
    db.commit()

    positions = db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == top.id).all()
    warnings = collect_duplicate_process_warnings(db, top.id, positions)
    assert len(warnings) == 1
    assert warnings[0].code == "DUPLICATE_PROCESS_REVIEW"


def _seed_markups(
    db,
    *,
    vvgk_pct: float = 0.0,
    gewinn_pct: float = 0.0,
    skonto_pct: float = 0.0,
    fgk_pct: float = 22.0,
    mgk_selbst_pct: float = 3.0,
    mgk_oem_pct: float = 5.0,
) -> None:
    db.execute(text("DELETE FROM zuschlagssaetze"))
    db.execute(
        text(
            "INSERT INTO zuschlagssaetze (id, bezeichnung, satz_prozent, typ, aktiv) VALUES "
            "(1, 'VVGK', :vvgk, 'vvgk', 1), "
            "(2, 'Gewinn', :gewinn, 'gewinn', 1), "
            "(3, 'Skonto', :skonto, 'skonto', 1), "
            "(4, 'FGK', :fgk, 'fgk', 1), "
            "(5, 'MGK selbst', :mgk_s, 'mgk_kaufteil_selbst', 1), "
            "(6, 'MGK OEM', :mgk_o, 'mgk_kaufteil_oem', 1)"
        ),
        {
            "vvgk": vvgk_pct,
            "gewinn": gewinn_pct,
            "skonto": skonto_pct,
            "fgk": fgk_pct,
            "mgk_s": mgk_selbst_pct,
            "mgk_o": mgk_oem_pct,
        },
    )
    db.commit()


def _seed_references(db) -> None:
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id, material_nominierung) "
            "VALUES (501, 'Träger', 'T-1', 100, 'selbstnominiert')"
        )
    )
    db.execute(
        text(
            "INSERT INTO kaufteile (id, artikelnummer, bezeichnung, preis, nominierung) "
            "VALUES (301, 'K-1', 'Lautsprecher', 8.0, 'selbstnominiert')"
        )
    )
    db.execute(
        text(
            "INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart, taktzeit_s) "
            "VALUES (401, 'Endmontage', 'Montage', 60)"
        )
    )
    db.commit()


def test_recalculate_with_existing_snapshots(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _seed_markups(db, vvgk_pct=10, gewinn_pct=10, skonto_pct=2)

    _put(
        db,
        top.id,
        [
            AssemblyPositionInput(
                position_type="PART",
                sequence=1,
                quantity=1,
                part_calculation_id=501,
                price_basis="COST",
            ),
            AssemblyPositionInput(
                position_type="PURCHASED_PART",
                sequence=2,
                quantity=2,
                purchased_part_id=301,
            ),
            AssemblyPositionInput(
                position_type="PROCESS",
                sequence=3,
                quantity=1,
                quantity_factor=1,
                finishing_step_id=401,
            ),
        ],
    )
    positions = db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == top.id).all()
    for pos in positions:
        if pos.position_type == "PART":
            pos.cost_snapshot = 4.2
            pos.price_snapshot = 12.0
        elif pos.position_type == "PURCHASED_PART":
            pos.price_snapshot = 8.0
        elif pos.position_type == "PROCESS":
            pos.cost_snapshot = 3.0
        pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()

    result = recalculate_assembly_tree(
        db,
        top.id,
        AssemblyRecalculateRequest(refresh_snapshots=False, include_descendants=False),
    )
    assert result.calculation.herstellkosten == pytest.approx(4.2 + 16.0 + 3.0 + 0.66)
    assert result.pricing_status == "CALCULATED"
    assert result.recalculated_assembly_ids == [top.id]


def test_recalculate_missing_snapshot_422(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos()])
    with pytest.raises(AssemblyRecalculationError) as exc:
        recalculate_assembly_tree(
            db,
            top.id,
            AssemblyRecalculateRequest(refresh_snapshots=False),
        )
    assert exc.value.status_code == 422


def test_recalculate_self_cost_422(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos(price_basis="SELF_COST")])
    pos = db.query(AssemblyPosition).one()
    pos.cost_snapshot = 4.2
    pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()
    with pytest.raises(AssemblyRecalculationError, match="SELF_COST"):
        recalculate_assembly_tree(
            db,
            top.id,
            AssemblyRecalculateRequest(refresh_snapshots=False),
        )


def test_subassembly_wrong_price_basis_422(db):
    _seed_project(db)
    top = _top(db)
    sub = _sub(db)
    db.add(
        AssemblyPosition(
            parent_assembly_id=top.id,
            position_type="SUBASSEMBLY",
            sequence=1,
            quantity=1,
            child_assembly_id=sub.id,
            price_basis="SALES_PRICE",
        )
    )
    top.legacy_mode = False
    db.commit()

    with pytest.raises(AssemblyRecalculationError) as exc:
        recalculate_assembly_tree(
            db,
            top.id,
            AssemblyRecalculateRequest(refresh_snapshots=False),
        )
    assert exc.value.status_code == 422
    assert "COST" in str(exc.value) or "price_basis" in str(exc.value).lower()


def test_nested_subassembly_recalc(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    sub = _sub(db)
    _put(
        db,
        sub.id,
        [
            AssemblyPositionInput(
                position_type="PART",
                sequence=1,
                quantity=1,
                part_calculation_id=501,
                price_basis="COST",
            )
        ],
    )
    pos = db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == sub.id).one()
    pos.cost_snapshot = 16.5
    pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()

    _put(
        db,
        top.id,
        [
            AssemblyPositionInput(
                position_type="SUBASSEMBLY",
                sequence=1,
                quantity=1,
                child_assembly_id=sub.id,
                price_basis="COST",
            ),
            AssemblyPositionInput(
                position_type="PART",
                sequence=2,
                quantity=1,
                part_calculation_id=501,
                price_basis="COST",
            ),
        ],
    )
    for pos in db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == top.id).all():
        if pos.position_type == "PART":
            pos.cost_snapshot = 4.2
            pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()

    _seed_markups(db, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)

    result = recalculate_assembly_tree(
        db,
        top.id,
        AssemblyRecalculateRequest(refresh_snapshots=False, include_descendants=True),
    )
    assert result.calculation.herstellkosten == pytest.approx(16.5 + 4.2)
    assert sub.id in result.recalculated_assembly_ids


def test_get_does_not_persist_stale(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos()])
    pos = db.query(AssemblyPosition).one()
    pos.cost_snapshot = 4.2
    pos.snapshots_captured_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    db.execute(
        text("UPDATE spritzguss_kalkulationen SET updated_at = :ts WHERE id = 501"),
        {"ts": datetime.now(UTC).isoformat()},
    )
    db.commit()

    before_status = db.get(Baugruppe, top.id).pricing_status
    structure = get_structure(db, top.id)
    after_status = db.get(Baugruppe, top.id).pricing_status
    assert before_status == after_status
    assert structure.snapshot_stale is True
    assert structure.effective_pricing_status == "STALE"


def test_duplicate_process_recalc_returns_warning(db):
    _seed_project(db)
    top = _top(db)
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id, material_nominierung) "
            "VALUES (501, 'Träger', 'T-1', 100, 'selbstnominiert')"
        )
    )
    db.execute(
        text(
            "INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart, taktzeit_s) "
            "VALUES (33, 'Schäumen', 'Sonstige', 60)"
        )
    )
    db.execute(
        text(
            "INSERT INTO spritzguss_veredelung_zuordnungen "
            "(id, kalkulation_id, veredelungsschritt_id, reihenfolge, snapshot_bezeichnung, snapshot_kosten_inkl_ausschuss) "
            "VALUES (1, 501, 33, 1, 'Schäumen', 1.5)"
        )
    )
    _seed_markups(db, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)

    _put(
        db,
        top.id,
        [
            _part_pos(sequence=1),
            AssemblyPositionInput(
                position_type="PROCESS",
                sequence=2,
                quantity=1,
                quantity_factor=1,
                finishing_step_id=33,
            ),
        ],
    )
    for pos in db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == top.id).all():
        if pos.position_type == "PART":
            pos.cost_snapshot = 4.2
        elif pos.position_type == "PROCESS":
            pos.cost_snapshot = 1.5
        pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()

    result = recalculate_assembly_tree(
        db,
        top.id,
        AssemblyRecalculateRequest(refresh_snapshots=False),
    )
    assert any(w.code == "DUPLICATE_PROCESS_REVIEW" for w in result.warnings)
    assert result.calculation.herstellkosten == pytest.approx(6.03)


def test_recalculate_missing_markup_rates_422(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos()])
    pos = db.query(AssemblyPosition).one()
    pos.cost_snapshot = 4.2
    pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()
    db.execute(
        text(
            "INSERT INTO zuschlagssaetze (id, bezeichnung, satz_prozent, typ, aktiv) "
            "VALUES (1, 'VVGK', 10, 'vvgk', 1)"
        )
    )
    db.commit()

    with pytest.raises(AssemblyRecalculationError) as exc:
        recalculate_assembly_tree(
            db,
            top.id,
            AssemblyRecalculateRequest(refresh_snapshots=False),
        )
    assert exc.value.status_code == 422
    message = str(exc.value)
    assert "Fehlende aktive Zuschlagssätze" in message
    assert "gewinn" in message or "fgk" in message


def test_recalculate_zero_percent_markups_are_present(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos()])
    pos = db.query(AssemblyPosition).one()
    pos.cost_snapshot = 4.2
    pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()
    _seed_markups(db, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)

    result = recalculate_assembly_tree(
        db,
        top.id,
        AssemblyRecalculateRequest(refresh_snapshots=False),
    )
    assert result.calculation.herstellkosten == pytest.approx(4.2)
    assert result.calculation.vvgk == pytest.approx(0.0)
    assert result.calculation.gewinn == pytest.approx(0.0)
    assert result.calculation.skonto == pytest.approx(0.0)
    assert result.calculation.markup_applied is True
    assert not any(w.code == "MISSING_MARKUP_RATE" for w in result.warnings)


def test_missing_markup_rates_raise_in_pure_calculation():
    with pytest.raises(AssemblyCalculationError, match="Fehlende Zuschlagssätze"):
        calculate_assembly(
            assembly_type="TOP_LEVEL",
            positions=[
                PositionCalcInput(
                    position_id=1,
                    position_type="PART",
                    sequence=1,
                    quantity=1,
                    quantity_factor=1,
                    price_basis="COST",
                    active=True,
                    label=None,
                    name_snapshot="Teil",
                    cost_snapshot=4.2,
                    price_snapshot=None,
                )
            ],
            markup_rates=MarkupRates(),
        )


def test_recalculate_no_structure_400(db):
    _seed_project(db)
    top = _top(db)
    with pytest.raises(AssemblyRecalculationError) as exc:
        recalculate_assembly_tree(db, top.id, AssemblyRecalculateRequest())
    assert exc.value.status_code == 400


def test_legacy_api_unchanged_import():
    from app.api.v1.baugruppen import _baugruppe_to_read, berechne_baugruppe

    assert callable(_baugruppe_to_read)
    assert callable(berechne_baugruppe)


def test_db_upgrade_unchanged_for_phase_c():
    import inspect

    from app.db_upgrade import ensure_assembly_structure_schema

    source = inspect.getsource(ensure_assembly_structure_schema)
    assert "self_cost_snapshot" not in source
