from fastapi import APIRouter

from app.api.v1 import (
    assembly_families,
    assembly_structure,
    auth,
    baugruppen,
    business_cases,
    customers,
    dashboard,
    investitionen,
    kaufteile,
    lohnkosten,
    maschinen,
    materialgruppen,
    materialien,
    program_volumes,
    programs,
    projects,
    reports,
    spritzguss,
    standorte,
    users,
    veredelung,
    zuschlagssaetze,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(materialgruppen.router)
api_router.include_router(materialien.router)
api_router.include_router(maschinen.router)
api_router.include_router(lohnkosten.router)
api_router.include_router(zuschlagssaetze.router)
api_router.include_router(standorte.router)
api_router.include_router(spritzguss.router)
api_router.include_router(veredelung.router)
api_router.include_router(kaufteile.router)
api_router.include_router(baugruppen.router)
api_router.include_router(assembly_families.router)
api_router.include_router(assembly_structure.router)
api_router.include_router(business_cases.router)
api_router.include_router(customers.router)
api_router.include_router(programs.router)
api_router.include_router(program_volumes.router)
api_router.include_router(projects.router)
api_router.include_router(dashboard.router)
api_router.include_router(investitionen.router)
api_router.include_router(reports.router)
