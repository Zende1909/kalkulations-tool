from fastapi import APIRouter

from app.api.v1 import (
    auth,
    baugruppen,
    dashboard,
    investitionen,
    kaufteile,
    lohnkosten,
    maschinen,
    materialien,
    reports,
    spritzguss,
    users,
    veredelung,
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
api_router.include_router(veredelung.router)
api_router.include_router(kaufteile.router)
api_router.include_router(baugruppen.router)
api_router.include_router(dashboard.router)
api_router.include_router(investitionen.router)
api_router.include_router(reports.router)
