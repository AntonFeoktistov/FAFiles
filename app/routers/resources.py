from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi import File as FastAPIFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.file_service import FileService
from app.services.folder_service import FolderService

from ..auth import get_current_user
from ..database import get_db
from ..schemas import FileResponse, FolderDetailResponse, FolderResponse, SessionData

router = APIRouter(prefix="/resource", tags=["resources"])


@router.get("/")
async def get_folder_files(
    folder_path: str = Query(..., description="Полный путь к ресурсу"),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
) -> FolderDetailResponse:

    folder = await FolderService.get_folder_with_children(
        folder_path, current_user.user_id, db
    )

    subfolders = []
    files = []

    for subfolder in folder.subfolders:
        subfolder_data = FolderResponse(path=subfolder.full_path, name=subfolder.name)
        subfolders.append(subfolder_data)

    for file in folder.files:
        file_data = FileResponse(path=file.file_path, name=file.name)
        files.append(file_data)

    return FolderDetailResponse(
        subfolders=subfolders, files=files, path=folder.full_path, name=folder.name
    )


@router.post("/create-folder", status_code=201, response_model=FolderResponse)
async def create_folder(
    name: str = Query(..., description="Имя папки"),
    parent_path: str | None = Query(
        default=None,
        description="Путь к родительской папке (оставьте пустым для корня)",
    ),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
):

    if not parent_path:
        parent_path = f"/{current_user.username}-files/"

    new_folder = await FolderService.create_folder(
        name=name, parent_path=parent_path, user_id=current_user.user_id, db=db
    )

    return FolderResponse(path=parent_path, name=name, type="DIRECTORY")


@router.post("/create-file", status_code=201)
async def upload_file(
    folder_path: str = Query(..., description="Путь к папке, в которую загружаем"),
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
):
    new_file = await FileService.create_file(
        folder_path, current_user.user_id, db, file
    )

    return FileResponse(path=new_file.file_path, name=new_file.name, size=file.size)


# @router.delete("/")
# async def delete_resource(
#     path: str = Query(..., description="Полный путь к ресурсу"),
#     db: AsyncSession = Depends(get_db),
#     current_user: SessionData = Depends(get_current_user),
# ):
#     """Удаление ресурса"""
#     folder, file = await PathService.get_resource_by_path(
#         path, current_user.user_id, db
#     )

#     if not folder and not file:
#         raise HTTPException(404, "Resource not found")

#     if folder:
#         # Удаляем папку и все файлы в ней
#         await MinIOService.delete_folder(folder.full_path)
#         await db.delete(folder)
#     else:
#         # Удаляем файл
#         await MinIOService.delete_file(file.file_path)
#         await db.delete(file)

#     await db.commit()
#     return {"message": "Resource deleted"}


# @router.get("/download")
# async def download_resource(
#     path: str = Query(..., description="Полный путь к ресурсу"),
#     db: AsyncSession = Depends(get_db),
#     current_user: SessionData = Depends(get_current_user),
# ):
#     """Скачивание ресурса (файла или папки в zip)"""
#     folder, file = await PathService.get_resource_by_path(
#         path, current_user.user_id, db
#     )

#     if not folder and not file:
#         raise HTTPException(404, "Resource not found")

#     if folder:
#         # Скачиваем папку как zip
#         return await MinIOService.download_folder_as_zip(folder.full_path)
#     else:
#         # Скачиваем файл
#         return await MinIOService.download_file(file.file_path)


# @router.post("/move")
# async def move_resource(
#     from_path: str = Query(..., description="Старый путь"),
#     to_path: str = Query(..., description="Новый путь"),
#     db: AsyncSession = Depends(get_db),
#     current_user: SessionData = Depends(get_current_user),
# ):
#     """Перемещение или переименование ресурса"""
#     # Получаем исходный ресурс
#     folder, file = await PathService.get_resource_by_path(
#         from_path, current_user.user_id, db
#     )

#     if not folder and not file:
#         raise HTTPException(404, "Resource not found")

#     # Проверяем, не существует ли уже ресурс по новому пути
#     new_folder, new_file = await PathService.get_resource_by_path(
#         to_path, current_user.user_id, db
#     )
#     if new_folder or new_file:
#         raise HTTPException(409, "Resource already exists at target path")

#     # Перемещаем в MinIO
#     if folder:
#         await MinIOService.rename_folder(folder.full_path, to_path)
#         # Обновляем путь в БД
#         # ... обновление full_path у папки и всех вложенных
#     else:
#         await MinIOService.rename_file(file.file_path, to_path)
#         file.file_path = to_path
#         await db.commit()

#     return {"message": "Resource moved"}
