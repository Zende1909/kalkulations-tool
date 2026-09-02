from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.material import Material
from app.models.materialgruppe import Materialgruppe
from app.schemas.materialgruppe import MaterialgruppeCreate, MaterialgruppeUpdate
from app.services.material_thermik import normalisiere_gruppenschluessel


class CRUDMaterialgruppe(CRUDBase[Materialgruppe, MaterialgruppeCreate, MaterialgruppeUpdate]):
    def get_by_gruppe(self, db: Session, gruppe: str | None) -> Materialgruppe | None:
        key = normalisiere_gruppenschluessel(gruppe)
        if key is None:
            return None
        return db.scalar(select(Materialgruppe).where(Materialgruppe.gruppe == key))

    def list_aktiv(self, db: Session, *, skip: int = 0, limit: int = 200) -> list[Materialgruppe]:
        stmt = (
            select(Materialgruppe)
            .where(Materialgruppe.aktiv.is_(True))
            .order_by(Materialgruppe.gruppe.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def count_material_references(self, db: Session, gruppe: str) -> int:
        stmt = select(Material).where(Material.materialgruppe == gruppe)
        return len(list(db.scalars(stmt).all()))

    def rename_gruppe_on_materials(self, db: Session, alt: str, neu: str) -> None:
        if alt == neu:
            return
        for material in db.scalars(select(Material).where(Material.materialgruppe == alt)).all():
            material.materialgruppe = neu
            db.add(material)


materialgruppe = CRUDMaterialgruppe(Materialgruppe)
