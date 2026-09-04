"""Smoke-Tests für Alembic-Bootstrap (ohne Produktions-/Arbeits-DB)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND_DIR = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
BASELINE_REVISION = "e1a0001_baseline"
BASELINE_FILE = BACKEND_DIR / "alembic" / "versions" / "e1a0001_baseline_current_schema.py"

EXPECTED_BASELINE_TABLES = {
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
}

# Tabellen aus späteren Revisionen (ab e1a0008_plant_costing)
EXPECTED_POST_BASELINE_TABLES = {
    "laender",
    "werke",
    "werk_zuschlaege",
}

EXPECTED_CURRENT_ORM_TABLES = EXPECTED_BASELINE_TABLES | EXPECTED_POST_BASELINE_TABLES | {
    "assembly_families",
    "business_case_manual_prices",
    "materialgruppen",
}


def _alembic_config() -> Config:
    assert ALEMBIC_INI.is_file(), f"alembic.ini fehlt: {ALEMBIC_INI}"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def _load_baseline_module():
    spec = importlib.util.spec_from_file_location(
        "e1a0001_baseline_current_schema",
        BASELINE_FILE,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_alembic_config_file_exists_and_loads():
    cfg = _alembic_config()
    assert cfg.get_main_option("script_location")
    url = cfg.get_main_option("sqlalchemy.url") or ""
    assert "admin123" not in url
    assert "kalkulation_secret" not in url
    assert "ci_password" not in url


def test_alembic_database_url_comes_from_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://ci_user:ci_password@127.0.0.1:5432/ci_db",
    )
    from app.config import Settings

    fresh = Settings()
    assert fresh.DATABASE_URL.startswith("postgresql+psycopg2://")
    assert "127.0.0.1" in fresh.DATABASE_URL
    assert "ci_db" in fresh.DATABASE_URL

    import app.config as config_mod

    monkeypatch.setattr(config_mod, "settings", fresh)

    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    from app.alembic_helpers import get_database_url, target_metadata

    url = get_database_url()
    assert url == fresh.DATABASE_URL
    assert EXPECTED_BASELINE_TABLES.issubset(set(target_metadata.tables.keys()))


def test_baseline_revision_is_discoverable():
    cfg = _alembic_config()
    scripts = ScriptDirectory.from_config(cfg)
    rev = scripts.get_revision(BASELINE_REVISION)
    assert rev is not None
    assert rev.down_revision is None
    assert BASELINE_REVISION in {r.revision for r in scripts.walk_revisions()}


def test_alembic_head_is_plant_costing_revision():
    cfg = _alembic_config()
    scripts = ScriptDirectory.from_config(cfg)
    assert scripts.get_heads() == ["e1a0023_assembly_variant_mix"]
    rev = scripts.get_revision("e1a0023_assembly_variant_mix")
    assert rev is not None
    assert rev.down_revision == "e1a0022_zykluszeit_entnahmeart"
    rev22 = scripts.get_revision("e1a0022_zykluszeit_entnahmeart")
    assert rev22 is not None
    assert rev22.down_revision == "e1a0021_zykluszeit_prozessaufwand"
    rev21 = scripts.get_revision("e1a0021_zykluszeit_prozessaufwand")
    assert rev21 is not None
    assert rev21.down_revision == "e1a0020_spritzguss_teilbild"
    rev20 = scripts.get_revision("e1a0020_spritzguss_teilbild")
    assert rev20 is not None
    assert rev20.down_revision == "e1a0019_drop_materialgruppe_quelle"
    rev19 = scripts.get_revision("e1a0019_drop_materialgruppe_quelle")
    assert rev19 is not None
    assert rev19.down_revision == "e1a0018_materialgruppen_stammdaten"
    rev18 = scripts.get_revision("e1a0018_materialgruppen_stammdaten")
    assert rev18 is not None
    assert rev18.down_revision == "e1a0017_simplify_cycle_time"
    rev17 = scripts.get_revision("e1a0017_simplify_cycle_time")
    assert rev17 is not None
    assert rev17.down_revision == "e1a0016_cycle_time_suggestion"
    rev16 = scripts.get_revision("e1a0016_cycle_time_suggestion")
    assert rev16 is not None
    assert rev16.down_revision == "e1a0015_injection_machine_sizing"
    rev15 = scripts.get_revision("e1a0015_injection_machine_sizing")
    assert rev15 is not None
    assert rev15.down_revision == "e1a0014_business_case_manual_prices"
    rev14 = scripts.get_revision("e1a0014_business_case_manual_prices")
    assert rev14 is not None
    assert rev14.down_revision == "e1a0013_investition_cost_bottom_revenue"
    rev13 = scripts.get_revision("e1a0013_investition_cost_bottom_revenue")
    assert rev13 is not None
    assert rev13.down_revision == "e1a0012_investition_assignment_hierarchy"
    rev12 = scripts.get_revision("e1a0012_investition_assignment_hierarchy")
    assert rev12 is not None
    assert rev12.down_revision == "e1a0011_kaufteil_sga_override"
    rev11 = scripts.get_revision("e1a0011_kaufteil_sga_override")
    assert rev11 is not None
    assert rev11.down_revision == "e1a0010_produktionsintervall_losgroesse_modus"
    rev10 = scripts.get_revision("e1a0010_produktionsintervall_losgroesse_modus")
    assert rev10 is not None
    assert rev10.down_revision == "e1a0009_werk_operating_params"
    e8 = scripts.get_revision("e1a0008_plant_costing")
    assert e8 is not None
    assert e8.down_revision == "e1a0007_veredelung_snapshot_yield"
    e7 = scripts.get_revision("e1a0007_veredelung_snapshot_yield")
    assert e7 is not None
    assert e7.down_revision == "e1a0006_spritzguss_material_nominierung"
    e5 = scripts.get_revision("e1a0005_central_markups_kaufteil")
    assert e5 is not None
    assert e5.down_revision == "e1a0004_m5_assembly_positions"


def test_baseline_contains_no_dml_or_seeds():
    source = BASELINE_FILE.read_text(encoding="utf-8")
    upper = source.upper()
    assert "INSERT INTO" not in upper
    assert "UPDATE " not in upper
    assert "DELETE FROM" not in upper
    assert "create_all" not in source
    assert "Base.metadata" not in source
    assert "vvgk" not in source or "nicht" in source.lower()
    assert "GEMEINKOSTEN" in source  # dokumentiert als nicht geseedet
    assert "NotImplementedError" in source
    assert source.count("op.create_table") == 19
    module = _load_baseline_module()
    assert tuple(module.BASELINE_TABLES) == tuple(sorted(EXPECTED_BASELINE_TABLES)) or set(
        module.BASELINE_TABLES
    ) == EXPECTED_BASELINE_TABLES


def test_baseline_table_list_matches_orm_metadata():
    from app.database import Base
    from app import models as _models  # noqa: F401

    assert set(Base.metadata.tables.keys()) == EXPECTED_CURRENT_ORM_TABLES
    module = _load_baseline_module()
    assert set(module.BASELINE_TABLES) == EXPECTED_BASELINE_TABLES


def test_baseline_downgrade_is_blocked():
    module = _load_baseline_module()
    with pytest.raises(NotImplementedError):
        module.downgrade()


def test_alembic_ini_does_not_embed_real_database_secrets():
    text = ALEMBIC_INI.read_text(encoding="utf-8")
    for forbidden in ("admin123", "kalkulation_secret", "JWT_SECRET", "LOCAL_ADMIN_PASSWORD"):
        assert forbidden not in text
