from typing import Generic, TypeVar

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: type[ModelType]):
        self.model = model

    def get(self, db: Session, item_id: int) -> ModelType | None:
        return db.get(self.model, item_id)

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> list[ModelType]:
        stmt = (
            select(self.model)
            .order_by(self.model.id.asc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        db_obj = self.model(**obj_in.model_dump())
        db.add(db_obj)
        try:
            # Expliziter Commit – ohne commit() wäre der INSERT nur in der Session sichtbar.
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Datensatz verletzt eine Unique-Constraint "
                    "(z. B. Material-Nr. bereits vergeben). "
                    f"Detail: {exc.orig}"
                ),
            ) from exc
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, db_obj: ModelType, obj_in: UpdateSchemaType) -> ModelType:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        db.add(db_obj)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Aktualisierung verletzt eine Unique-Constraint "
                    f"(Wert bereits vergeben). Detail: {exc.orig}"
                ),
            ) from exc
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, db_obj: ModelType) -> None:
        db.delete(db_obj)
        db.commit()
