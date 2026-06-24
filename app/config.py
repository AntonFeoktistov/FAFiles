from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    POSTGRES_DB: str = "fastapi_db"
    POSTGRES_USER: str = "fastapi_user"
    POSTGRES_PASSWORD: str = "fastapi_pass"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"

    REDIS_URL: str = "redis://localhost:6379/0"

    SECRET_KEY: str = "your-super-secret-key"
    SESSION_TTL: int = 86400

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()


settings = get_settings()
