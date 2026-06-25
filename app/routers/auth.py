from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.folder_service import FolderService

from ..auth import (
    create_session,
    get_current_user,
    hash_password,
    logout_user,
    verify_password,
)
from ..database import get_db
from ..models import User
from ..schemas import SessionData, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate, response: Response, db: AsyncSession = Depends(get_db)
):
    existing = await db.execute(
        select(User).where((User.username == user_data.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username or email already exists")

    password_hash = hash_password(user_data.password)
    new_user = User(username=user_data.username, password_hash=password_hash)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    root_folder = await FolderService.create_folder(
        name=f"/{new_user.username}-files", parent_path="", user_id=new_user.id, db=db
    )

    session_data = {
        "user_id": new_user.id,
        "username": new_user.username,
    }
    await create_session(response, session_data)

    return UserResponse.model_validate(new_user)


@router.post("/login", response_model=UserResponse)
async def login(
    login_data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session_data = {
        "user_id": user.id,
        "username": user.username,
    }
    await create_session(response, session_data)

    return UserResponse.model_validate(user)


@router.post("/logout")
async def logout(request: Request, response: Response):
    await logout_user(request, response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=SessionData)
async def get_me(current_user: SessionData = Depends(get_current_user)):
    return current_user
