"""AP3: Docker Compose starts alembic before uvicorn; production JWT/APP_ENV."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = ROOT / "docker-compose.yml"
COMPOSE_DEV = ROOT / "docker-compose.dev.yml"
ENTRYPOINT = ROOT / "backend" / "docker-entrypoint.sh"
DOCKERFILE = ROOT / "backend" / "Dockerfile"


def _compose_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env.update(extra)
    return env


def test_entrypoint_runs_alembic_before_exec():
    source = ENTRYPOINT.read_text(encoding="utf-8")
    assert "set -eu" in source or "set -e" in source
    assert "alembic upgrade head" in source
    assert 'exec "$@"' in source
    assert "seed_admin" not in source.lower()
    assert "seed_top_level" not in source.lower()
    # alembic must appear before exec
    assert source.index("alembic upgrade head") < source.index("exec")


def test_dockerfile_uses_entrypoint():
    source = DOCKERFILE.read_text(encoding="utf-8")
    assert 'ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint.sh"]' in source
    assert "CMD" in source and "uvicorn" in source


def test_compose_yaml_production_guards():
    source = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "APP_ENV: production" in source
    assert "@db:5432" in source
    assert "JWT_SECRET_KEY: ${JWT_SECRET_KEY:?" in source
    assert "change-me-in-production" not in source
    assert "service_healthy" in source
    assert "seed_admin" not in source
    assert "seed_top_level" not in source
    assert "--reload" not in source


def test_compose_dev_overlay_preserves_reload():
    source = COMPOSE_DEV.read_text(encoding="utf-8")
    assert "APP_ENV: development" in source
    assert "--reload" in source
    assert "./backend:/app" in source


@pytest.mark.skipif(
    subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0,
    reason="docker compose not available",
)
def test_docker_compose_config_resolves_production():
    env = _compose_env(JWT_SECRET_KEY="compose-test-secret-not-default-42")
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert re.search(r"APP_ENV:\s*production", out)
    assert "@db:5432/" in out or "@db:5432" in out
    assert "change-me-in-production" not in out
    assert "compose-test-secret-not-default-42" in out
    assert "seed_admin" not in out
    assert "seed_top_level" not in out


@pytest.mark.skipif(
    subprocess.run(["docker", "compose", "version"], capture_output=True).returncode != 0,
    reason="docker compose not available",
)
def test_docker_compose_dev_config_sets_development():
    env = _compose_env(JWT_SECRET_KEY="compose-test-secret-not-default-42")
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            str(COMPOSE_FILE),
            "-f",
            str(COMPOSE_DEV),
            "config",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert re.search(r"APP_ENV:\s*development", result.stdout)
    assert "--reload" in result.stdout
