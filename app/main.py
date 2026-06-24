from contextlib import asynccontextmanager

from fastapi import FastAPI

from .database import Base, engine
from .redis_client import redis_client
from .routers import auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await redis_client.connect()
    print("✅ PostgreSQL и Redis готовы")
    yield
    await redis_client.close()
    print("👋 Завершение работы")


app = FastAPI(
    title="FastAPI Auth",
    description="Аутентификация через сессии с Redis",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
