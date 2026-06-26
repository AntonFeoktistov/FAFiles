import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest_asyncio
from dotenv import load_dotenv
from fastapi import Response
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.auth import create_session, get_current_user, hash_password
from app.database import Base, get_db
from app.main import app
from app.models import User
from app.redis_client import redis_client

load_dotenv(".env.test")

TEST_DATABASE_URL = f"postgresql+asyncpg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
    pool_pre_ping=True,
    pool_recycle=3600,
)
TestingSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="function")
async def event_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop

    await loop.shutdown_asyncgens()
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    loop = asyncio.get_running_loop()

    try:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

        async with TestingSessionLocal() as session:
            yield session
            await session.rollback()
    except Exception as e:
        logging.error(f"Database fixture error: {e}")
        raise


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession):
    await redis_client.connect()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

    if redis_client.client:
        await redis_client.client.flushall()
        await redis_client.client.aclose()


@pytest_asyncio.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> User:
    password_hash = hash_password("testpass123")
    user = User(username="testuser", password_hash=password_hash)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    from app.services.folder_service import FolderService

    await FolderService.create_folder(
        name=f"{user.username}-files", parent_path="", user_id=user.id, db=db_session
    )

    return user


@pytest_asyncio.fixture(scope="function")
async def test_folder(test_user: User, db_session: AsyncSession):
    from app.services.folder_service import FolderService

    folder = await FolderService.create_folder(
        name="documents",
        parent_path=f"{test_user.username}-files/",
        user_id=test_user.id,
        db=db_session,
    )
    return folder


@pytest_asyncio.fixture(scope="function")
async def auth_client(client: AsyncClient, test_user: User):
    response = Response()
    session_data = {
        "user_id": test_user.id,
        "username": test_user.username,
    }
    await create_session(response, session_data)

    cookie_header = response.headers.get("set-cookie", "")
    session_id = None
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith("session_id="):
            session_id = part.split("=")[1]
            break

    if session_id:
        client.cookies.set("session_id", session_id)

    return client


@pytest_asyncio.fixture(scope="function")
async def unauth_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
