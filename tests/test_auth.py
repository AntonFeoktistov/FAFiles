import pytest
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User


async def test_register_success(client, db_session: AsyncSession):
    response = await client.post(
        "api/auth/sign-up",
        json={"username": "newuser", "password": "newpass"},
    )
    result = await db_session.execute(select(User).where(User.username == "newuser"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["username"] == "newuser"


@pytest.mark.parametrize(
    "username, password",
    [
        ("a", "validpass123"),
        ("a" * 21, "validpass123"),
        ("validuser", "p"),
        ("validuser", "p" * 21),
    ],
)
async def test_register_data_not_valid(
    client,
    db_session,
    username: str,
    password: str,
):
    response = await client.post(
        "/api/auth/sign-up",
        json={"username": username, "password": password},
    )
    result = await db_session.execute(select(User).where(User.username == "newuser"))
    user = result.scalar_one_or_none()
    assert user is None
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Not correct" in response.json()["message"]


async def test_register_duplicate_username(client, test_user, db_session):
    response = await client.post(
        "api/auth/sign-up",
        json={"username": test_user.username, "password": "testpass123"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response.json()["message"]


async def test_login_success(client, test_user):
    response = await client.post(
        "api/auth/sign-in",
        json={"username": test_user.username, "password": "testpass123"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert test_user.username in response.json()["username"]


async def test_login_no_such_user(client):
    response = await client.post(
        "api/auth/sign-in",
        json={"username": "user_not_exists", "password": "random_pass"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "No such user" in response.json()["message"]


async def test_login_not_correct_password(client, test_user):
    response = await client.post(
        "api/auth/sign-in",
        json={"username": test_user.username, "password": "not_correct_password"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not correct password" in response.json()["message"]


async def test_logout_success(auth_client):
    response = await auth_client.post("api/auth/sign-out")
    assert response.status_code == status.HTTP_204_NO_CONTENT


async def test_logout_not_auth(client):
    response = await client.post("api/auth/sign-out")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Not auth" in response.json()["message"]
