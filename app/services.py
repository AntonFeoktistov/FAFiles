import io
import os
from typing import Optional, Tuple

from dotenv import load_dotenv
from fastapi import HTTPException, UploadFile
from minio import Minio, S3Error
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import File, Folder

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


class StorageService:
    @staticmethod
    async def upload_file(
        file: UploadFile, path: str, content_type: str = None
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
    async def rename_file(old_path: str, new_path: str) -> bool:
        try:
            minio_client.copy_object(
                BUCKET_NAME, new_path, f"/{BUCKET_NAME}/{old_path}"
            )
            minio_client.remove_object(BUCKET_NAME, old_path)
            return True
        except Exception as e:
            print(f"MinIO rename error: {e}")
            return False

    @staticmethod
    async def delete_file(path: str) -> bool:
        try:
            minio_client.remove_object(BUCKET_NAME, path)
            return True
        except Exception as e:
            print(f"MinIO delete error: {e}")
            return False

    @staticmethod
    async def file_exists(path: str) -> bool:
        try:
            minio_client.stat_object(BUCKET_NAME, path)
            return True
        except Exception:
            return False


class BusinessLogicService:
    @staticmethod
    async def update_folder_structure(session: AsyncSession, folder_id: int):

        async def traverse(f: Folder):
            f.full_path = f.calculate_full_path(f.user.username)

            for sub in f.subfolders:
                await traverse(sub)

            for file_obj in f.files:
                file_obj.file_path = file_obj.full_path_in_storage

        result = await session.execute(select(Folder).where(Folder.id == folder_id))
        folder = result.scalar_one_or_none()

        if not folder:
            raise ValueError("Folder not found")

        await session.scalars(select(Folder).where(Folder.parent_id == folder.id))
        await traverse(folder)

    @staticmethod
    async def safe_rename_file_in_db(session: AsyncSession, file_id: int) -> bool:

        result = await session.execute(select(File).where(File.id == file_id))
        file_obj = result.scalar_one_or_none()
        if not file_obj:
            return False

        old_path = file_obj.file_path
        new_path = file_obj.full_path_in_storage

        if old_path and old_path != new_path:
            success = await StorageService.rename_file(old_path, new_path)
            if not success:
                return False

            file_obj.file_path = new_path
            return True

        elif not old_path:
            file_obj.file_path = new_path
            return True

        return True

    @staticmethod
    async def delete_folder_with_cleanup(session: AsyncSession, folder_id: int) -> bool:
        result = await session.execute(
            select(Folder)
            .where(Folder.id == folder_id)
            .options(
                selectinload(Folder.files),
                selectinload(Folder.subfolders).selectinload(Folder.files),
            )
        )
        folder = result.scalars().first()

        if not folder:
            return False

        files_to_delete = []

        def collect_files(f: Folder):
            for fl in f.files:
                files_to_delete.append(fl.file_path)
            for sub in f.subfolders:
                collect_files(sub)

        collect_files(folder)

        try:
            for path in files_to_delete:
                if path:
                    await StorageService.delete_file(path)

            session.delete(folder)
            return True
        except Exception as e:
            print(f"Cleanup failed: {e}")
            return False


class PathService:
    @staticmethod
    async def get_resource_by_path(
        path: str, user_id: int, session: AsyncSession
    ) -> Tuple[Optional[Folder], Optional[File]]:
        """
        Найти ресурс (папку или файл) по пути.
        Возвращает (folder, file) — один из них будет None.
        """
        path = path.strip("/")
        is_folder = path.endswith("/")
        is_file = not is_folder
        if is_folder:
            path = path.rstrip("/")

        parts = path.split("/")
        folder_name = parts[-1] if is_folder else None
        file_name = parts[-1] if is_file else None
        parent_path = "/".join(parts[:-1])

        parent_folder = (
            await PathService._get_folder_by_path(parent_path, user_id, session)
            if parent_path
            else None
        )

        if is_folder:
            result = await session.execute(
                select(Folder).where(
                    Folder.user_id == user_id,
                    Folder.name == folder_name,
                    Folder.parent_id == (parent_folder.id if parent_folder else None),
                )
            )
            folder = result.scalar_one_or_none()
            return folder, None
        elif is_file:
            result = await session.execute(
                select(File).where(
                    File.user_id == user_id,
                    File.name == file_name,
                    File.folder_id == (parent_folder.id if parent_folder else None),
                )
            )
            file = result.scalar_one_or_none()
            return None, file

    @staticmethod
    async def _get_folder_by_path(
        path: str, user_id: int, session: AsyncSession
    ) -> Optional[Folder]:
        if not path:
            return None

        parts = path.split("/")
        current_parent = None

        for name in parts:
            result = await session.execute(
                select(Folder).where(
                    Folder.user_id == user_id,
                    Folder.name == name,
                    Folder.parent_id == (current_parent.id if current_parent else None),
                )
            )
            folder = result.scalar_one_or_none()
            if not folder:
                return None
            current_parent = folder

        return current_parent
