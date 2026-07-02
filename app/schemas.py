from typing import List

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str

    model_config = ConfigDict(from_attributes=True)


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


class FileFilterResponse(BaseModel):
    folder_path: str
    name: str


class FolderDetailResponse(FolderResponse):
    subfolders: List[FolderResponse] = []
    files: List[FileResponse] = []
