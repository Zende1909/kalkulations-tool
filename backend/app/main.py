from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine, verify_database_connection
from app.models import (  # noqa: F401
    AssemblyPosition,
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
    Customer,
    Investition,
    Kaufteil,
    Lohnkosten,
    Maschine,
    Material,
    Program,
    ProgramVolume,
    Project,
    SpritzgussKalkulation,
    SpritzgussVeredelungZuordnung,
    User,
    Veredelungsschritt,
    Zuschlagssatz,
)
from app.scripts.seed_admin import seed_admin_user
from app.db_upgrade import (
    ensure_assembly_structure_schema,
    ensure_investition_schema,
    ensure_spritzguss_hierarchy_schema,
    ensure_spritzguss_schema,
)
from app.startup import verify_database_at_alembic_head

logger = logging.getLogger(__name__)


def _run_dev_schema_bootstrap() -> None:
    """Controlled create_all + ensure_* + optional admin seed (never production)."""
    logger.info(
        "Startup-Schema-Bootstrap aktiv (APP_ENV=%s, ALLOW_STARTUP_SCHEMA_BOOTSTRAP=%s)",
        settings.APP_ENV,
        settings.ALLOW_STARTUP_SCHEMA_BOOTSTRAP,
    )
    Base.metadata.create_all(bind=engine)
    ensure_spritzguss_schema(engine)
    ensure_spritzguss_hierarchy_schema(engine)
    ensure_investition_schema(engine)
    ensure_assembly_structure_schema(engine)
    db = SessionLocal()
    try:
        seed_admin_user(db)
    finally:
        db.close()


def _run_production_startup_checks() -> None:
    """JWT already validated; verify DB connectivity done; Alembic head read-only."""
    logger.info(
        "Produktions-Startup: keine Schemaänderungen, keine Seeds, "
        "keine Datenmutation – nur Alembic-Head-Prüfung"
    )
    verify_database_at_alembic_head(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast before any DB interaction; prevents unsafe production startup.
    settings.validate_jwt_secret_for_startup()
    verify_database_connection()
    if settings.startup_schema_bootstrap_enabled:
        _run_dev_schema_bootstrap()
    else:
        _run_production_startup_checks()
    yield


app = FastAPI(
    title="Kalkulations-Tool API",
    description="API für Kunststoffmodul-Kalkulation in der Automotive-Zulieferindustrie",
    version="0.1.0",
    lifespan=lifespan,
)

_cors_origins = list(
    dict.fromkeys(
        [
            *settings.cors_origins_list,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
)

_cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
# Headers used by the frontend (see `frontend/src/api/client.ts` + auth flow).
_cors_headers = [
    "Authorization",
    "Content-Type",
    "Accept",
    "Cache-Control",
    "Pragma",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=_cors_methods,
    allow_headers=_cors_headers,
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    """
    Unauthentifizierter Technik-Healthcheck für Monitoring.

    Keine internen Daten wie DB-Host/User/URL ausgeben (Security Hardening).
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1")).scalar()
        return {"status": "ok", "service": "backend", "database": "connected"}
    except Exception:
        return {"status": "unavailable", "service": "backend", "database": "unavailable"}
