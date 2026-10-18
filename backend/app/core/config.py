import os
from pydantic_settings import BaseSettings

def _get_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        return "sqlite+aiosqlite:///./lumos.db"
    # Neon / Render often give postgres:// — SQLAlchemy async needs postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

class Settings(BaseSettings):
    PROJECT_NAME: str = "Lumos"
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "lumos-super-secret-key-change-in-production-2024")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    DATABASE_URL: str = _get_database_url()

    class Config:
        env_file = ".env"

settings = Settings()
