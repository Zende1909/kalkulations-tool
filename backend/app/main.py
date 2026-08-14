from contextlib import asynccontextmanager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_database_connection()
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    """Enthält DB-Namen und Zeilenanzahl – zum Prüfen, ob GET/POST dieselbe DB treffen."""
    with engine.connect() as connection:
        db_name = connection.execute(text("SELECT current_database()")).scalar()
        materialien_count = connection.execute(
            text("SELECT COUNT(*) FROM public.materialien")
        ).scalar()
    return {
        "status": "ok",
        "database": db_name,
        "materialien_count": materialien_count,
        "database_url": engine.url.render_as_string(hide_password=True),
    }
