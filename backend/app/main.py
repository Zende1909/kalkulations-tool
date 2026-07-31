from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Lohnkosten, Maschine, Material, User, Zuschlagssatz  # noqa: F401
from app.scripts.seed_admin import seed_admin_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
