import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

# Eine gemeinsame Engine für alle Requests (POST und GET).
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    isolation_level="READ COMMITTED",
)

# expire_on_commit=False: Objekte nach commit() bleiben für die Response nutzbar.
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


class Base(DeclarativeBase):
    pass


def verify_database_connection() -> None:
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT current_database(), current_user")
            ).fetchone()
            logger.info(
                "Datenbankverbindung OK: database=%s user=%s url=%s",
                row[0],
                row[1],
                engine.url.render_as_string(hide_password=True),
            )
    except UnicodeDecodeError as exc:
        raise RuntimeError(
            "Datenbankverbindung fehlgeschlagen. Prüfen Sie DATABASE_URL in der .env "
            "(Datei im Projektroot oder unter backend/.env). Auf Windows kann ein "
            "falscher Benutzer/Passwort/DB-Name diesen Encoding-Fehler auslösen."
        ) from exc
    except OperationalError as exc:
        raise RuntimeError(
            f"Datenbankverbindung fehlgeschlagen: {exc.orig}"
        ) from exc


def get_db():
    """Gemeinsame Session-Factory für alle Endpunkte (POST und GET)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
