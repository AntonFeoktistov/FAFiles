from enum import Enum
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- PostgreSQL ---
    POSTGRES_DB: str = "fastapi_db"
    POSTGRES_USER: str = "fastapi_user"
    POSTGRES_PASSWORD: str = "fastapi_pass"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Auth & Session ---
    SECRET_KEY: str = "your-super-secret-key"
    SESSION_TTL: int = 86400

    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET_NAME: str

    MINIO_ROOT_USER: Optional[str] = None
    MINIO_ROOT_PASSWORD: Optional[str] = None

    MINIO_USE_SSL: bool = False

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()


class ResourceType(str, Enum):
    FOLDER = "DIRECTORY"
    FILE = "FILE"
