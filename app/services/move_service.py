import logging

from fastapi import HTTPException
from minio import S3Error
from minio.commonconfig import CopySource
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File, Folder
from app.services import utils
from app.services.create_service import CreateService
from app.services.delete_service import DeleteService
from app.services.minio import BUCKET_NAME, minio_client
from app.services.repository import StorageRepository

logger = logging.getLogger(__name__)


class MoveService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.delete = DeleteService(user_id, db)
        self.create = CreateService(user_id, db)
        self.minio_client = minio_client
        self.BUCKET_NAME = BUCKET_NAME

    async def move_file(self, path_from: str, path_to: str) -> File:
        file = await self.repo.get_file_or_none(path_from)
        if not file:
            raise HTTPException(404, "File not found")

        file_to = await self.repo.get_file_or_none(path_to)
        if file_to:
            raise HTTPException(409, f"File on {path_to} already exists")

        try:
            copy_source = CopySource(self.BUCKET_NAME, path_from)
            self.minio_client.copy_object(self.BUCKET_NAME, path_to, copy_source)
            self.minio_client.remove_object(self.BUCKET_NAME, path_from)
        except S3Error as e:
            raise HTTPException(500, f"MinIO error: {e}")

        file_name, folder_path = utils.get_resource_name_and_parent_path(path_to)
        folder = await self.repo.get_folder_or_none(folder_path)
        if not folder:
            raise HTTPException(404, f"Folder '{folder_path}' not found")

        file.full_path = path_to
        file.name = file_name
        file.folder_id = folder.id
        await self.db.commit()
        await self.db.refresh(file)

        return file

    async def move_folder(self, path_from: str, path_to: str) -> Folder:
        folder = await self.repo.get_folder_or_none(path_from)
        if not folder:
            raise HTTPException(404, "Folder not found")

        folder_to = await self.repo.get_folder_or_none(path_to)
        if folder_to:
            raise HTTPException(409, f"Folder on {path_to} already exists")

        files = await self.repo.get_files_by_prefix(path_from)

        for file_obj in files:
            new_file_path = file_obj.full_path.replace(path_from, path_to, 1)

            try:
                copy_source = CopySource(self.BUCKET_NAME, file_obj.full_path)
                self.minio_client.copy_object(
                    self.BUCKET_NAME, new_file_path, copy_source
                )
                self.minio_client.remove_object(self.BUCKET_NAME, file_obj.full_path)
            except S3Error as e:
                raise HTTPException(500, f"MinIO error: {e}")

            file_obj.full_path = new_file_path
            file_obj.name, _ = utils.get_resource_name_and_parent_path(new_file_path)

        folder.full_path = path_to
        folder.name, _ = utils.get_resource_name_and_parent_path(path_to)

        await self.db.commit()
        await self.db.refresh(folder)

        return folder
