from pydantic import BaseModel, ConfigDict

from app.config import ResourceType
from app.models import File, Folder
from app.services import utils


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


class ResourceResponse(BaseModel):
    path: str
    name: str
    size: int | None
    type: ResourceType | str


class FolderResponse(BaseModel):
    path: str
    name: str
    type: str = "FOLDER"


class FileResponse(BaseModel):
    path: str
    name: str
    type: str = "FILE"


def folder_to_response(folder: Folder) -> ResourceResponse:
    name, parent_path = utils.get_resource_name_and_parent_path(folder.full_path)
    parent_path = _delete_user_prefix(parent_path)
    return ResourceResponse(
        path=parent_path,
        name=name,
        size=None,
        type=ResourceType.FOLDER,
    )


def file_to_response(file: File) -> ResourceResponse:
    name, parent_path = utils.get_resource_name_and_parent_path(file.full_path)
    parent_path = _delete_user_prefix(parent_path)
    return ResourceResponse(
        path=parent_path,
        name=name,
        size=file.size,
        type=ResourceType.FILE,
    )


def _delete_user_prefix(full_path: str):
    return ("/").join(full_path.split("/")[1:])
