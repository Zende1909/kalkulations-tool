from fastapi import APIRouter

from app.api.v1 import (
    auth,
    lohnkosten,
    maschinen,
    materialien,
    spritzguss,
    users,
    zuschlagssaetze,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(materialien.router)
api_router.include_router(maschinen.router)
api_router.include_router(lohnkosten.router)
api_router.include_router(zuschlagssaetze.router)
api_router.include_router(spritzguss.router)
