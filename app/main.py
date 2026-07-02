from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import HTTPException, RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.exceptions import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)
from app.routers import resources

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

app.include_router(auth.router, prefix="/api")
app.include_router(resources.router, prefix="/api")

app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
