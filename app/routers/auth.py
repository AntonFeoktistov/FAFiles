from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.folder_service import FolderService

from ..auth import (
    create_session,
    get_current_user,
    hash_password,
    logout_user,
    validate_register_data,
    verify_password,
)
from ..database import get_db
from ..models import User
from ..schemas import SessionData, UserCreate, UserLogin, UserResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/sign-up", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    user_data: UserCreate, response: Response, db: AsyncSession = Depends(get_db)
):
    is_data_correct = await validate_register_data(user_data)
    if not is_data_correct:
        raise HTTPException(
            status_code=400, detail="Not correct register data (2 < length < 20)"
        )

    existing = await db.execute(
        select(User).where((User.username == user_data.username))
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    password_hash = hash_password(user_data.password)
    new_user = User(username=user_data.username, password_hash=password_hash)

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    root_folder = await FolderService.create_folder(
        name=f"/{new_user.username}-files", parent_path="", user_id=new_user.id, db=db
    )

    session_data = SessionData(user_id=new_user.id, username=new_user.username)
    await create_session(response, session_data)

    return UserResponse(username=new_user.username)


@router.post("/sign-in", response_model=UserResponse)
async def login(
    login_data: UserLogin, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="No such user")
    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Not correct password")

    session_data = SessionData(user_id=user.id, username=login_data.username)
    await create_session(response, session_data)

    return UserResponse(username=user.username)


@router.post("/sign-out", status_code=204)
async def logout(
    request: Request,
    response: Response,
    current_user: SessionData = Depends(get_current_user),
):

    await logout_user(request, response)
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: SessionData = Depends(get_current_user)):
    return UserResponse(username=current_user.username)
