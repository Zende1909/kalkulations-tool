"""AP3: CI runs alembic upgrade head before pytest against migrated schema."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BACKEND_DIR = ROOT / "backend"


def _workflow_source() -> str:
    assert CI_WORKFLOW.is_file(), f"missing {CI_WORKFLOW}"
    return CI_WORKFLOW.read_text(encoding="utf-8")


def test_ci_workflow_triggers_include_phase_e_db_safety():
    source = _workflow_source()
    assert "phase-e-db-safety" in source
    assert "phase-e-ci" in source
    assert "main" in source


def test_ci_workflow_env_and_postgres_health():
    source = _workflow_source()
    assert "APP_ENV: test" in source
    assert 'ALLOW_STARTUP_SCHEMA_BOOTSTRAP: "false"' in source
    assert "DATABASE_URL: postgresql+psycopg2://ci_user:ci_password@127.0.0.1:5432/ci_db" in source
    assert "JWT_SECRET_KEY: ci-test-jwt-secret" in source
    assert 'LOCAL_ADMIN_SEED_ENABLED: "false"' in source
    assert "pg_isready" in source
    assert "--health-cmd" in source or "health-cmd" in source


def test_ci_workflow_runs_alembic_before_pytest():
    source = _workflow_source()
    assert "alembic upgrade head" in source
    assert "python -m pytest" in source
    assert source.index("alembic upgrade head") < source.index("python -m pytest")
    # Migration failures must be a dedicated step (non-zero exit stops the job).
    assert "Apply Alembic migrations" in source
    assert "npm run build" in source
    assert source.index("python -m pytest") < source.index("npm run build")


def test_ci_workflow_has_no_automatic_seeds():
    source = _workflow_source()
    assert "seed_admin" not in source
    assert "seed_top_level" not in source


def test_ci_workflow_yaml_parses():
    pytest.importorskip("yaml")
    import yaml

    data = yaml.safe_load(_workflow_source())
    assert data["name"] == "CI"
    assert "backend-and-frontend" in data["jobs"]
    job = data["jobs"]["backend-and-frontend"]
    assert job["env"]["APP_ENV"] == "test"
    assert job["env"]["ALLOW_STARTUP_SCHEMA_BOOTSTRAP"] == "false"
    assert "ci_db" in job["env"]["DATABASE_URL"]
    step_names = [s.get("name") for s in job["steps"] if isinstance(s, dict)]
    assert "Apply Alembic migrations" in step_names
    assert "Run backend tests" in step_names
    assert "Build frontend" in step_names
    mig_idx = step_names.index("Apply Alembic migrations")
    test_idx = step_names.index("Run backend tests")
    assert mig_idx < test_idx


def test_alembic_head_is_e1a0009_for_ci_expectation():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["e1a0012_investition_assignment_hierarchy"]
