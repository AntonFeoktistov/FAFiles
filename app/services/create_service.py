import io
import logging
from typing import Optional

from fastapi import HTTPException, UploadFile
from minio import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Folder
from app.services import utils
from app.services.minio import BUCKET_NAME, minio_client
from app.services.repository import StorageRepository

logger = logging.getLogger(__name__)


class CreateService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.minio_client = minio_client
        self.BUCKET_NAME = BUCKET_NAME

    async def upload_file_in_minio_and_get_size(
        self,
        file: UploadFile,
        file_path: str,
        content_type: Optional[str] = None,
    ) -> int:
        try:
            content = await file.read()
            file_size = len(content)

            if not content_type:
                content_type = file.content_type or "application/octet-stream"

            self.minio_client.put_object(
                bucket_name=self.BUCKET_NAME,
                object_name=file_path,
                data=io.BytesIO(content),
                length=file_size,
                content_type=content_type,
            )

            return file_size
        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"MinIO upload error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    async def create_folder(self, name: str, parent_path: str) -> Folder:
        parent_path = utils.normalize_path(parent_path) if parent_path else ""
        folder_path = utils.normalize_path(f"{parent_path}{name.strip('/')}/")
        folder, _ = await self.repo.ensure_folder_path(folder_path)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder
