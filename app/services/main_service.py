from typing import List

from fastapi import Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.auth import get_current_user
from app.database import get_db
from app.models import Folder
from app.schemas import ResourceResponse, SessionData
from app.services import minio, utils
from app.services.create_service import CreateService
from app.services.delete_service import DeleteService
from app.services.download_service import DownloadService
from app.services.minio import BUCKET_NAME, minio_client
from app.services.move_service import MoveService
from app.services.repository import StorageRepository


class StorageService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.download = DownloadService(user_id, db)
        self.move = MoveService(user_id, db)
        self.delete = DeleteService(user_id, db)
        self.create = CreateService(user_id, db)
        self.minio_client = minio_client
        self.BUCKET_NAME = BUCKET_NAME

    async def get_resource(self, path):
        path = utils.validate_path(path)
        if utils.is_resource_folder(path):
            resource = await self.repo.get_folder_or_none(path)
        else:
            resource = await self.repo.get_file_or_none(path)
            if not await minio.is_file_exists(path):
                resource = None
        if not resource:
            raise HTTPException(
                status_code=404,
                detail=f"Ресурс {path} не найден",
            )
        return resource

    async def delete_resource(self, path):
        path = utils.validate_path(path)
        if utils.is_resource_folder(path):
            await self.delete.delete_folder(path)
        else:
            await self.delete.delete_file(path)

    async def download_resource(self, path: str) -> StreamingResponse:
        path = utils.validate_path(path)
        if utils.is_resource_folder(path):
            return await self.download.download_folder(path)
        else:
            return await self.download.download_file(path)

    async def move_resource(self, path_from, path_to):
        path_from = utils.validate_path(path_from)
        path_to = utils.validate_path(path_to)
        if utils.is_resource_folder(path_from):
            return await self.move.move_folder(path_from, path_to)
        else:
            return await self.move.move_file(path_from, path_to)

    async def search_resources(self, query):
        query = utils.validate_search_query(query)
        files = await self.repo.get_files_by_query(query)
        folders = await self.repo.get_folders_by_query(query)
        return files + folders

    async def get_folder_resources(self, folder_path):
        folder_path = utils.validate_path(folder_path)
        folder = await self.repo.get_folder_or_none(folder_path)
        if not folder:
            raise HTTPException(
                status_code=404,
                detail=f"Ресурс {folder_path} не найден",
            )
        files = await self.repo.get_files_by_parent(folder)
        folders = await self.repo.get_folders_by_parent(folder)
        return files + folders

    async def create_folder(self, folder_path):
        folder_path = utils.validate_path(folder_path)
        folder_name, parent_path = utils.get_resource_name_and_parent_path(folder_path)
        print(folder_name, parent_path)
        folder = await self.repo.create_folder(folder_name, parent_path)
        return folder

    async def upload_resources(
        self,
        root_path: str,
        files: List[UploadFile],
    ) -> List[ResourceResponse]:
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        root_path = utils.normalize_path(root_path)
        root_folder = await self.repo.get_folder_or_none(root_path)
        if not root_folder:
            raise HTTPException(
                status_code=404,
                detail=f"Родительская папка не найдена: {root_path}",
            )
        entries = await utils.expand_upload_files(files)
        created_folders: dict[str, Folder] = {}
        file_results: list[ResourceResponse] = []
        uploaded_minio_paths: list[str] = []
        try:
            for upload_file in entries:
                relative_path = utils.parse_relative_path(upload_file.filename)
                file_name, parent_rel = utils.get_resource_name_and_parent_path(
                    relative_path
                )
                folder_path = (
                    utils.normalize_path(f"{root_path}{parent_rel}")
                    if parent_rel
                    else root_path
                )
                folder, new_folders = await self.repo.ensure_folder_path(folder_path)
                for new_folder in new_folders:
                    created_folders[new_folder.full_path] = new_folder
                file_path = f"{folder.full_path}{file_name}"
                existing_file = await self.repo.get_file_or_none(file_path)
                if existing_file:
                    raise HTTPException(status_code=409, detail="File already exists")
                file_size = await self.create.upload_file_in_minio_and_get_size(
                    upload_file, file_path
                )
                uploaded_minio_paths.append(file_path)
                file = await self.repo.create_file_in_db(
                    folder.id, file_path, file_size
                )
                file_data = schemas.file_to_response(file)
                file_results.append(file_data)
            await self.db.commit()
        except HTTPException:
            await self.db.rollback()
            await minio.cleanup_minio_objects(uploaded_minio_paths)
            raise
        except Exception as e:
            await self.db.rollback()
            await minio.cleanup_minio_objects(uploaded_minio_paths)
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        folder_results = [
            schemas.folder_to_response(folder)
            for folder in sorted(
                created_folders.values(), key=lambda f: f.full_path.count("/")
            )
        ]
        return folder_results + file_results


async def get_storage_service(
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
) -> StorageService:
    return StorageService(user_id=current_user.user_id, db=db)
