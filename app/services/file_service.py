import io
import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from minio import Minio, S3Error
from minio.commonconfig import CopySource
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import File, Folder

load_dotenv()

minio_client = Minio(
    endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000")
    .replace("http://", "")
    .replace("https://", ""),
    access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
    secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
    secure=os.getenv("MINIO_USE_SSL", "false").lower() == "true",
)
BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "user-files")

if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)


class FileService:
    @staticmethod
    async def create_file(
        folder_path: str,
        user_id: int,
        db: AsyncSession,
        file: UploadFile,
    ) -> File:

        full_path = f"{folder_path}{file.filename}"

        folder_query = await db.execute(
            select(Folder).where(
                Folder.user_id == user_id, Folder.full_path == folder_path
            )
        )
        folder = folder_query.scalar_one_or_none()

        if not folder:
            raise HTTPException(404, "Folder not found")

        existing_file = await db.execute(
            select(File).where(
                File.user_id == user_id,
                File.folder_id == folder.id,
                File.name == file.filename,
            )
        )
        if existing_file.scalar_one_or_none():
            raise HTTPException(409, "File already exists")

        upload_result = await FileService._upload_file(file, full_path)

        new_file = File(
            user_id=user_id,
            name=file.filename,
            folder_id=folder.id,
            file_path=full_path,
        )

        db.add(new_file)
        await db.commit()
        await db.refresh(new_file)

        return new_file

    @staticmethod
    async def _upload_file(
        file: UploadFile, path: str, content_type: Optional[str] = None
    ) -> dict:
        try:
            content = await file.read()
            file_size = len(content)

            if not content_type:
                content_type = file.content_type or "application/octet-stream"

            minio_client.put_object(
                bucket_name=BUCKET_NAME,
                object_name=path,
                data=io.BytesIO(content),
                length=file_size,
                content_type=content_type,
            )

            return {
                "path": path,
                "size": file_size,
                "content_type": content_type,
                "filename": path.split("/")[-1],
            }

        except S3Error as e:
            raise HTTPException(status_code=500, detail=f"MinIO upload error: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    @staticmethod
    async def delete_file(file_path: str, user_id: int, db: AsyncSession) -> bool:

        file = await FileService._get_file_by_path(file_path, user_id, db)
        if not file:
            raise HTTPException(404, "File not found")

        try:
            minio_client.remove_object(BUCKET_NAME, file_path)
        except S3Error as e:
            raise HTTPException(500, f"MinIO delete error: {e}")

        await db.delete(file)
        await db.commit()

        return True

    @staticmethod
    async def rename_file(
        from_path: str, to_path: str, user_id: int, db: AsyncSession
    ) -> File:

        file = await FileService._get_file_by_path(from_path, user_id, db)
        if not file:
            raise HTTPException(404, "File not found")

        existing_file = await FileService._get_file_by_path(to_path, user_id, db)
        if existing_file:
            raise HTTPException(409, "File already exists at target path")

        try:
            copy_source = CopySource(BUCKET_NAME, from_path)
            minio_client.copy_object(BUCKET_NAME, to_path, copy_source)
            minio_client.remove_object(BUCKET_NAME, from_path)
        except S3Error as e:
            raise HTTPException(500, f"MinIO operation failed: {e}")

        file.file_path = to_path
        file.name = to_path.split("/")[-1]

        await db.commit()
        await db.refresh(file)

        return file

    @staticmethod
    async def _get_file_by_path(
        file_path: str, user_id: int, db: AsyncSession
    ) -> Optional[File]:

        result = await db.execute(
            select(File).where(File.user_id == user_id, File.file_path == file_path)
        )
        return result.scalar_one_or_none()
