from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent

DEFAULT_JWT_SECRET_KEY = "change-me-in-production"


def _env_files() -> tuple[Path, ...]:
    candidates = (
        BACKEND_DIR / ".env",
        PROJECT_ROOT / ".env",
    )
    return tuple(path for path in candidates if path.is_file())


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"),
    )

    DATABASE_URL: str = "postgresql+psycopg2://postgres:admin123@localhost:5432/kalkulationstool"
    JWT_SECRET_KEY: str = Field(
        default=DEFAULT_JWT_SECRET_KEY,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM"),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    COMPANY_NAME: str = "Kalkulations-Tool Automotive"
    CORS_ALLOW_CREDENTIALS: bool = False

    # Local dev: only create an admin via explicit activation + explicit credentials.
    LOCAL_ADMIN_SEED_ENABLED: bool = False
    LOCAL_ADMIN_EMAIL: str | None = None
    LOCAL_ADMIN_PASSWORD: str | None = None

    # AP2: optional override for startup schema bootstrap (create_all / ensure_*).
    # None = auto from APP_ENV (enabled in development/test, always off in production).
    ALLOW_STARTUP_SCHEMA_BOOTSTRAP: bool | None = None

    @field_validator("APP_ENV", mode="before")
    @classmethod
    def _normalize_app_env(cls, value: str) -> str:
        v = str(value or "").strip().lower()
        if not v:
            return "development"
        if v not in {"development", "production", "test"}:
            raise ValueError("APP_ENV must be development/production/test")
        return v

    @staticmethod
    def is_local_development_database_url(database_url: str) -> bool:
        """Used for safe defaults/guards only; not a security boundary."""
        lowered = database_url.lower()
        return (
            lowered.startswith("sqlite://")
            or "localhost" in lowered
            or "127.0.0.1" in lowered
        )

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def startup_schema_bootstrap_enabled(self) -> bool:
        """Whether lifespan may run create_all / ensure_* / optional admin seed.

        Production always returns False (hard block). For development/test the
        default is True unless ALLOW_STARTUP_SCHEMA_BOOTSTRAP explicitly disables it.
        """
        if self.is_production:
            return False
        if self.ALLOW_STARTUP_SCHEMA_BOOTSTRAP is not None:
            return bool(self.ALLOW_STARTUP_SCHEMA_BOOTSTRAP)
        return self.APP_ENV in {"development", "test"}

    @property
    def is_default_jwt_secret(self) -> bool:
        return self.JWT_SECRET_KEY == DEFAULT_JWT_SECRET_KEY

    def validate_jwt_secret_for_startup(self) -> None:
        """Block production startup with missing/empty/whitespace/default JWT secret."""
        if not self.is_production:
            return

        jwt_secret = (self.JWT_SECRET_KEY or "").strip()
        # Do not leak secret values.
        if not jwt_secret or jwt_secret == DEFAULT_JWT_SECRET_KEY:
            raise RuntimeError(
                "Ungültiger JWT_SECRET_KEY für Produktionsbetrieb. Bitte setze einen eigenen JWT_SECRET_KEY."
            )

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if isinstance(value, str) and value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg2://", 1)
        return value

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
