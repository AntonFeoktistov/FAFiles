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


@router.post("/resource-swagger", status_code=status.HTTP_201_CREATED)
async def upload_resources_swagger(
    path: str = Query(...),
    file: UploadFile = FastAPIFile(..., description="Один файл (для Swagger)"),
    storage: StorageService = Depends(get_storage_service),
):
    upload_files = [file]
    decoded_path = unquote(path)
    return await storage.upload_resources(decoded_path, upload_files)


@router.delete("/resource", status_code=204)
async def delete_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    storage: StorageService = Depends(get_storage_service),
):
    decoded_path = unquote(path)
    print(decoded_path)
    await storage.delete_resource(decoded_path)


# @router.get("/")
# async def get_folder_files(
#     folder_path: str = Query(..., description="Полный путь к ресурсу"),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ) -> FolderDetailResponse:

#     folder = await FolderService.get_folder_with_children(
#         folder_path, current_user.user_id, db
#     )

#     subfolders = []
#     files = []

#     for subfolder in folder.subfolders:
#         subfolder_data = FolderResponse(path=subfolder.full_path, name=subfolder.name)
#         subfolders.append(subfolder_data)

#     for file in folder.files:
#         file_data = FileResponse(path=file.full_path, name=file.name)
#         files.append(file_data)

#     return FolderDetailResponse(
#         subfolders=subfolders, files=files, path=folder.full_path, name=folder.name
#     )


# @router.post("/create-folder", status_code=201, response_model=FolderResponse)
# async def create_folder(
#     name: str = Query(..., description="Имя папки"),
#     parent_path: str | None = Query(
#         default=None,
#         description="Путь к родительской папке (оставьте пустым для корня)",
#     ),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ):

#     if not parent_path:
#         parent_path = f"/{current_user.username}-files/"

#     new_folder = await FolderService.create_folder(
#         name=name, parent_path=parent_path, user_id=current_user.user_id, db=db
#     )

#     return FolderResponse(path=parent_path, name=name, type="DIRECTORY")


# @router.post("/create-file", status_code=201)
# async def upload_file(
#     folder_path: str = Query(..., description="Путь к папке, в которую загружаем"),
#     file: UploadFile = FastAPIFile(...),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ):
#     new_file = await FileService.create_file(
#         folder_path, current_user.user_id, db, file
#     )

#     return FileResponse(path=new_file.full_path, name=new_file.name, size=file.size)


# @router.post("/rename")
# async def rename_resource(
#     from_path: str = Query(..., description="Старый путь"),
#     to_path: str = Query(..., description="Новый путь"),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ):
#     is_folder = from_path.endswith("/")

#     if is_folder:
#         await FolderService.rename_folder(from_path, to_path, current_user.user_id, db)
#     if not is_folder:
#         await FileService.rename_file(from_path, to_path, current_user.user_id, db)

#     return {"message": "Resource moved"}


# @router.get("/search")
# async def find_files(
#     query: str = Query(..., min_length=2, description="Строка для поиска"),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ) -> list[FileFilterResponse]:

#     all_files = await FolderService.find_files(query, current_user.user_id, db)
#     files = []
#     for file in all_files:
#         folder_path = "/".join(file.full_path.split("/")[:-1]) + "/"
#         file_data = FileFilterResponse(folder_path=folder_path, name=file.name)
#         files.append(file_data)

#     return files


# @router.get("/download")
# async def download_file(
#     path: str = Query(..., description="Путь к файлу"),
#     db: AsyncSession = Depends(get_db),
#     current_user: UserResponse = Depends(get_current_user),
# ):
#     is_folder = path.endswith("/")

#     if is_folder:
#         response = await FolderService.download_folder(path, current_user.user_id, db)

#     if not is_folder:
#         response = await FileService.download_file(path, current_user.user_id, db)
#     return response
