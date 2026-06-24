from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi import File as FastAPIFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File, Folder

from ..auth import get_current_user
from ..database import get_db
from ..schemas import FileResponse, FolderResponse, SessionData
from ..services import PathService, StorageService

router = APIRouter(prefix="/resource", tags=["resources"])


@router.get("/")
async def get_resource(
    path: str = Query(..., description="Полный путь к ресурсу"),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
):

    folder, file = await PathService.get_resource_by_path(
        path, current_user.user_id, db
    )

    if not folder and not file:
        raise HTTPException(404, "Resource not found")

    if folder:
        path = folder.parent.full_path if folder.parent else ""
        return FolderResponse(path=path, name=folder.name, type="DIRECTORY")

    else:
        path = file.folder.full_path + "/" if file.folder else ""
        return FileResponse(path=path, name=file.name, size=file.size, type="FILE")


@router.post("/create-folder", status_code=201, response_model=FolderResponse)
async def create_folder(
    name: str = Query(..., description="Имя папки"),
    parent_path: str = Query(description="Путь к родительской папке"),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
):

    full_path = f"{parent_path}/{name}/".replace("//", "/")

    existing = await db.execute(
        select(Folder).where(
            Folder.user_id == current_user.user_id, Folder.full_path == full_path
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(409, "Folder already exists")

    parent = None
    if parent_path:
        parent_result = await db.execute(
            select(Folder).where(
                Folder.user_id == current_user.user_id, Folder.full_path == parent_path
            )
        )
        parent = parent_result.scalar_one_or_none()
        if not parent:
            raise HTTPException(404, "Parent folder not found")

    new_folder = Folder(
        user_id=current_user.user_id,
        name=name,
        parent_id=parent.id if parent else None,
        full_path=full_path,
    )

    db.add(new_folder)
    await db.commit()
    await db.refresh(new_folder)

    return FolderResponse(
        path=parent_path + "/" if parent_path else "",
        name=name,
    )


@router.post("/create-file", status_code=201)
async def upload_file(
    path: str = Query(..., description="Путь к папке, в которую загружаем"),
    file: UploadFile = FastAPIFile(...),
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
):

    folder = await PathService.get_resource_by_path(path, current_user.user_id, db)

    file_path = f"{folder.full_path}/{file.filename}"

    exists = await StorageService.file_exists(file_path)
    if exists:
        raise HTTPException(409, f"File {file.filename} already exists")

    await StorageService.upload_file(file_path, file.file)

    new_file = File(
        user_id=current_user.user_id,
        folder_id=folder.id,
        name=file.filename,
        file_path=file_path,
    )
    db.add(new_file)
    await db.commit()
    await db.refresh(new_file)

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
