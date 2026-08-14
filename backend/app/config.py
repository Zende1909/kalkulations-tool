from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


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

    DATABASE_URL: str = "postgresql+psycopg2://postgres:admin123@localhost:5432/kalkulationstool"
    JWT_SECRET_KEY: str = Field(
        default="change-me-in-production",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    JWT_ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("JWT_ALGORITHM", "ALGORITHM"),
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    COMPANY_NAME: str = "Kalkulations-Tool Automotive"

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
