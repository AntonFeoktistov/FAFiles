from typing import List

from pydantic import BaseModel


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True


class SessionData(BaseModel):
    user_id: int
    username: str


class FolderResponse(BaseModel):
    path: str
    name: str
    type: str = "FOLDER"


class FileResponse(BaseModel):
    path: str
    name: str
    type: str = "FILE"


class FolderDetailResponse(FolderResponse):
    subfolders: List[FolderResponse] = []
    files: List[FileResponse] = []

    class Config:
        from_attributes = True
