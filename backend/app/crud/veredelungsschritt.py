from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.veredelungsschritt import VeredelungsschrittCreate, VeredelungsschrittUpdate


class CRUDVeredelungsschritt(
    CRUDBase[Veredelungsschritt, VeredelungsschrittCreate, VeredelungsschrittUpdate]
):
    def get_multi(
        self, db: Session, skip: int = 0, limit: int = 100
    ) -> list[Veredelungsschritt]:
        stmt = (
            select(self.model)
            .order_by(self.model.reihenfolge.asc(), self.model.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())


veredelungsschritt = CRUDVeredelungsschritt(Veredelungsschritt)
