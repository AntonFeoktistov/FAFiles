from typing import Union
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi import File as FastAPIFile

from app import schemas
from app.services import utils
from app.services.main_service import StorageService, get_storage_service

from ..schemas import (
    ResourceResponse,
)

router = APIRouter()


@router.get("/resource")
async def get_resource(
    path: str = Query("", description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
) -> ResourceResponse:
    path = utils.decode_path(path, storage.user_id)
    resource = await storage.get_resource(path)
    if utils.is_resource_folder(resource.full_path):
        return schemas.folder_to_response(resource)
    return schemas.file_to_response(resource)


@router.post("/resource", status_code=status.HTTP_201_CREATED)
async def upload_resources(
    path: str = "",
    files: Union[UploadFile, list[UploadFile]] = FastAPIFile(
        ..., description="Файлы для загрузки"
    ),
    storage: StorageService = Depends(get_storage_service),
):
    path = utils.decode_path(path, storage.user_id)
    if isinstance(files, UploadFile):
        files = [files]
    return await storage.upload_resources(path, files)


@router.delete("/resource", status_code=204)
async def delete_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
):
    path = utils.decode_path(path, storage.user_id)
    await storage.delete_resource(path)


@router.get("/resource/download", status_code=200)
async def download_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
):
    path = utils.decode_path(path, storage.user_id)
    return await storage.download_resource(path)


@router.post("/resource/move", status_code=status.HTTP_201_CREATED)
async def move_resource(
    from_path: str = Query("", alias="from", description="Откуда перемещение"),
    to_path: str = Query("", alias="to", description="Куда перемещение"),
    storage: StorageService = Depends(get_storage_service),
):
    path_from = utils.decode_path(from_path, storage.user_id)
    path_to = utils.decode_path(to_path, storage.user_id)
    resource = await storage.move_resource(path_from, path_to)
    if utils.is_resource_folder(resource.full_path):
        return schemas.folder_to_response(resource)
    else:
        return schemas.file_to_response(resource)


@router.get("/resource/search")
async def search_resources(
    query: str = Query("", description="Запрос для поиска (частичное совпадение)"),
    storage: StorageService = Depends(get_storage_service),
) -> list[ResourceResponse]:

    query = unquote(query)
    resources = await storage.search_resources(query)
    response = []
    for resource in resources:
        if utils.is_resource_folder(resource.full_path):
            response.append(schemas.folder_to_response(resource))
        else:
            response.append(schemas.file_to_response(resource))
    return response


@router.get("/directory")
async def get_directory(
    path: str = Query("", description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
) -> list[ResourceResponse]:

    path = utils.decode_path(path, storage.user_id)
    folder_resources = await storage.get_folder_resources(path)
    response = []
    for resource in folder_resources:
        if utils.is_resource_folder(resource.full_path):
            response.append(schemas.folder_to_response(resource))
        else:
            response.append(schemas.file_to_response(resource))
    return response


@router.post("/directory", status_code=status.HTTP_201_CREATED)
async def create_directory(
    path: str = "",
    storage: StorageService = Depends(get_storage_service),
):
    path = utils.decode_path(path, storage.user_id) + "/"
    folder = await storage.create_folder(path)
    return schemas.folder_to_response(folder)


# only for testing
@router.post("/resource-swagger", status_code=status.HTTP_201_CREATED)
async def upload_resources_swagger(
    path: str = "",
    file: UploadFile = FastAPIFile(..., description="Один файл (для Swagger)"),
    storage: StorageService = Depends(get_storage_service),
):
    upload_files = [file]
    path = utils.decode_path(path, storage.user_id)
    return await storage.upload_resources(path, upload_files)
