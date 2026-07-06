import io
import logging
import zipfile
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from minio import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import utils
from app.services.minio import BUCKET_NAME, minio_client
from app.services.repository import StorageRepository

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.minio_client = minio_client
        self.BUCKET_NAME = BUCKET_NAME

    async def download_file(self, file_path: str) -> StreamingResponse:
        try:
            response = self.minio_client.get_object(self.BUCKET_NAME, file_path)

            file_name, _ = utils.get_resource_name_and_parent_path(file_path)
            encoded_filename = quote(file_name, encoding="utf-8")

            return StreamingResponse(
                response,
                media_type="application/octet-stream",
                headers={
                    "Content-Disposition": f'attachment; filename="{encoded_filename}"',
                    "Content-Length": str(response.headers.get("Content-Length", 0)),
                },
            )
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise HTTPException(404, "File not found in storage")
            raise HTTPException(500, f"MinIO error: {e}")

    async def download_folder(self, folder_path: str) -> StreamingResponse:
        all_files = await self.repo.get_files_by_prefix(folder_path)
        if not all_files:
            raise HTTPException(404, "Folder is empty")

        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for file_obj in all_files:
                try:
                    response = self.minio_client.get_object(
                        self.BUCKET_NAME, file_obj.full_path
                    )
                    content = response.read()
                    response.close()
                    response.release_conn()
                    arcname = file_obj.full_path.replace(folder_path, "", 1)
                    zip_file.writestr(arcname, content)

                except S3Error as e:
                    if e.code == "NoSuchKey":
                        continue
                    raise HTTPException(500, f"MinIO error: {e}")

        zip_buffer.seek(0)
        folder_name, _ = utils.get_resource_name_and_parent_path(folder_path)
        encoded_name = quote(folder_name, encoding="utf-8")

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{encoded_name}.zip"',
                "Content-Length": str(zip_buffer.getbuffer().nbytes),
            },
        )
