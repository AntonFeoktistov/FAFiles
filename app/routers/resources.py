from urllib.parse import unquote

from fastapi import APIRouter, Depends, Query, UploadFile, status
from fastapi import File as FastAPIFile

from app import schemas
from app.services import utils
from app.services.storage import StorageService, get_storage_service

from ..schemas import (
    ResourceResponse,
)

router = APIRouter()


@router.get("/resource")
async def get_resource(
    path: str = Query(description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
) -> ResourceResponse:

    resource = storage.get_resource(path)
    if utils.is_resource_folder(resource.full_path):
        return schemas.folder_to_response(resource)
    return schemas.file_to_response(resource)


@router.post("/resource", status_code=status.HTTP_201_CREATED)
async def upload_resources(
    path: str = Query(...),
    files: list[UploadFile] = FastAPIFile(
        ..., description="Несколько файлов (для фронта)"
    ),
    storage: StorageService = Depends(get_storage_service),
):
    decoded_path = unquote(path)
    return await storage.upload_resources(decoded_path, files)


@router.delete("/resource", status_code=204)
async def delete_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
):
    decoded_path = unquote(path)
    await storage.delete_resource(decoded_path)


@router.get("/resource/download", status_code=200)
async def download_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
):
    decoded_path = unquote(path)
    return await storage.download_resource(decoded_path)


@router.post("/resource-swagger", status_code=status.HTTP_201_CREATED)
async def upload_resources_swagger(
    path: str = Query(...),
    file: UploadFile = FastAPIFile(..., description="Один файл (для Swagger)"),
    storage: StorageService = Depends(get_storage_service),
):
    upload_files = [file]
    decoded_path = unquote(path)
    return await storage.upload_resources(decoded_path, upload_files)
