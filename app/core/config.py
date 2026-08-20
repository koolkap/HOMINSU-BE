import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, overridable via environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    APP_NAME: str = "Hominsu VR Studio API"
    APP_VERSION: str = "0.1.0"
    # Production-safe default. Set DEBUG=true explicitly for local auto-create/seed behavior.
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- Database (PostgreSQL) ---
    # User/db created via:
    #   CREATE USER hominsu WITH PASSWORD 'hominsu_dev_password';
    #   CREATE DATABASE hominsu OWNER hominsu;
    POSTGRES_USER: str = "hominsu"
    POSTGRES_PASSWORD: str = "hominsu_dev_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "hominsu"
    DATABASE_URL: str = "postgresql+asyncpg://hominsu:hominsu_dev_password@localhost:5432/hominsu"

    # --- Security ---
    SECRET_KEY: str = "change-me-in-production-9f2c1a7e4b8d6f0a3c5e9b1d7f4a2c8e"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # --- CORS ---
    # JSON array (recommended) or comma-separated origins. Example:
    # ["https://hominsu-fe.example.com", "http://localhost:3000"]
    CORS_ORIGINS: str = '["http://localhost:3000"]'

    @property
    def cors_origins(self) -> list[str]:
        """Return normalized browser origins for FastAPI's CORS middleware."""
        raw = self.CORS_ORIGINS.strip()
        if not raw:
            return []

        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("CORS_ORIGINS must be valid JSON or comma-separated origins") from exc
        else:
            parsed = raw.split(",")

        if isinstance(parsed, str):
            parsed = [parsed]
        if not isinstance(parsed, list) or not all(isinstance(origin, str) for origin in parsed):
            raise ValueError("CORS_ORIGINS must be a list of origin strings")

        origins = [origin.strip().rstrip("/") for origin in parsed if origin.strip()]
        return ["*"] if "*" in origins else origins

    # --- SRS Media Server ---
    SRS_HLS_BASE_URL: str = "http://localhost:8080"
    KRW_TO_POINTS_RATE: float = 1.1  # 10,000 KRW -> 11,000 P

    @field_validator("DATABASE_URL")
    @classmethod
    def use_asyncpg_driver(cls, value: str) -> str:
        """Make Railway/Postgres connection URLs compatible with async SQLAlchemy.

        Railway commonly provides DATABASE_URL with the standard
        ``postgresql://`` scheme. This application uses SQLAlchemy's async
        engine, which requires the asyncpg driver in the scheme.
        """
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value[len("postgres://") :]
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value[len("postgresql://") :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
