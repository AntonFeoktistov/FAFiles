import logging

from fastapi import HTTPException
from minio import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import minio, utils
from app.services.minio import BUCKET_NAME, minio_client
from app.services.repository import StorageRepository

logger = logging.getLogger(__name__)


class DeleteService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.minio_client = minio_client
        self.BUCKET_NAME = BUCKET_NAME

    async def delete_file(self, file_path: str) -> None:
        file = await self.repo.get_file_or_none(file_path)
        file_in_minio = await minio.is_file_exists(file_path)
        if not file or not file_in_minio:
            raise HTTPException(404, "File not found")
        try:
            self.minio_client.remove_object(self.BUCKET_NAME, file_path)
        except S3Error as e:
            raise HTTPException(500, f"MinIO error: {e}")

        await self.db.delete(file)
        await self.db.commit()

    async def delete_folder(self, folder_path: str) -> None:
        folder_path = utils.normalize_path(folder_path)
        folder = await self.repo.get_folder_or_none(folder_path)
        if not folder:
            raise HTTPException(404, f"Folder '{folder_path}' not found")

        files = await self.repo.get_files_by_prefix(folder_path)
        for file_obj in files:
            try:
                self.minio_client.remove_object(self.BUCKET_NAME, file_obj.full_path)
            except S3Error as e:
                if e.code != "NoSuchKey":
                    raise HTTPException(500, f"MinIO error: {e}")
            await self.db.delete(file_obj)

        descendants = await self.repo.get_folders_by_prefix(folder_path)
        for subfolder in descendants:
            await self.db.delete(subfolder)
        await self.db.delete(folder)
        await self.db.commit()
