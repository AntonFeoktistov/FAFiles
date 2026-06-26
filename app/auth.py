import hashlib
import json
import secrets
import uuid

from fastapi import HTTPException, Request, Response

from .config import settings
from .redis_client import redis_client
from .schemas import UserResponse


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    hash_value = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{hash_value}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, hash_value = password_hash.split(":")
        expected_hash = hashlib.sha256((salt + password).encode()).hexdigest()
        return expected_hash == hash_value
    except (ValueError, AttributeError):
        return False


async def create_session(response: Response, user_data: dict) -> str:
    session_id = str(uuid.uuid4())
    session_key = f"session:{session_id}"

    await redis_client.set_session(session_key, user_data, settings.SESSION_TTL)

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=settings.SESSION_TTL,
        path="/",
    )

    return session_id


async def get_session_data(session_id: str) -> dict | None:
    session_key = f"session:{session_id}"
    data = await redis_client.get(session_key)
    if data:
        return json.loads(data) if isinstance(data, str) else data
    return None


async def delete_session(session_id: str):
    session_key = f"session:{session_id}"
    await redis_client.delete(session_key)


async def refresh_session_ttl(session_id: str):
    session_key = f"session:{session_id}"
    await redis_client.expire(session_key, settings.SESSION_TTL)


async def get_current_user(request: Request) -> UserResponse:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_data = await get_session_data(session_id)
    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    await refresh_session_ttl(session_id)

    return UserResponse(
        user_id=session_data["user_id"],
        username=session_data["username"],
    )


async def logout_user(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id:
        await delete_session(session_id)
    response.delete_cookie("session_id", path="/")
