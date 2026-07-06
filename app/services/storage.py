import io
import zipfile
from tempfile import SpooledTemporaryFile
from typing import List, Optional

from fastapi import Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from minio import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app import schemas
from app.auth import get_current_user
from app.config import ResourceType
from app.database import get_db
from app.models import File, Folder
from app.schemas import ResourceResponse, SessionData
from app.services import minio, utils
from app.services.download_service import DownloadService
from app.services.minio import BUCKET_NAME, minio_client
from app.services.repository import StorageRepository


class StorageService:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db
        self.repo = StorageRepository(user_id, db)
        self.download = DownloadService(user_id, db)
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
                status_code=400,
                detail=f"Родительская папка не найдена: {root_path}",
            )
        entries = await self._expand_upload_files(files)
        created_folders: dict[str, Folder] = {}
        file_results: list[ResourceResponse] = []
        uploaded_minio_paths: list[str] = []
        try:
            for upload_file in entries:
                relative_path = self._parse_relative_path(upload_file.filename)
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
                file_size = await self._upload_file_and_get_size(upload_file, file_path)
                uploaded_minio_paths.append(file_path)
                self.db.add(
                    File(
                        user_id=self.user_id,
                        name=file_name,
                        folder_id=folder.id,
                        full_path=file_path,
                        size=file_size,
                    )
                )
                file_results.append(
                    ResourceResponse(
                        path=folder.full_path,
                        name=file_name,
                        size=file_size,
                        type=ResourceType.FILE,
                    )
                )
            await self.db.commit()
        except HTTPException:
            await self.db.rollback()
            self._cleanup_minio_objects(uploaded_minio_paths)
            raise
        except Exception as e:
            await self.db.rollback()
            self._cleanup_minio_objects(uploaded_minio_paths)
            raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
        folder_results = [
            schemas.folder_to_response(folder)
            for folder in sorted(
                created_folders.values(), key=lambda f: f.full_path.count("/")
            )
        ]
        return folder_results + file_results

    async def delete_resource(self, path):
        path = utils.validate_path(path)
        if utils.is_resource_folder(path):
            await self._delete_folder(path)
        else:
            await self._delete_file(path)

    async def download_resource(self, path: str) -> StreamingResponse:
        path = utils.validate_path(path)
        if utils.is_resource_folder(path):
            return await self.download.download_folder(path)
        else:
            return await self.download.download_file(path)

    async def create_folder(self, name: str, parent_path: str) -> Folder:
        parent_path = utils.normalize_path(parent_path) if parent_path else ""
        folder_path = utils.normalize_path(f"{parent_path}{name.strip('/')}/")
        folder, _ = await self.repo.ensure_folder_path(folder_path)
        await self.db.commit()
        await self.db.refresh(folder)
        return folder

    async def _delete_file(self, file_path: str) -> None:
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

    async def _delete_folder(self, folder_path: str) -> None:
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

        await self.db.delete(folder)
        await self.db.commit()

    async def _upload_file_and_get_size(
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

    def _parse_relative_path(self, filename: str | None) -> str:
        if not filename:
            raise HTTPException(status_code=400, detail="Invalid file path")
        try:
            return utils.normalize_relative_path(filename)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid file path")

    async def _expand_upload_files(self, files: List[UploadFile]) -> List[UploadFile]:
        if (
            len(files) == 1
            and files[0].filename
            and files[0].filename.lower().endswith(".zip")
        ):
            return await self._zip_to_upload_files(files[0])
        return files

    async def _zip_to_upload_files(self, zip_file: UploadFile) -> List[UploadFile]:
        content = await zip_file.read()
        zip_buffer = io.BytesIO(content)
        entries: list[UploadFile] = []

        with zipfile.ZipFile(zip_buffer, "r") as zf:
            for file_info in zf.filelist:
                if file_info.is_dir():
                    continue
                file_content = zf.read(file_info.filename)
                temp = SpooledTemporaryFile()
                temp.write(file_content)
                temp.seek(0)
                entries.append(UploadFile(filename=file_info.filename, file=temp))

        if not entries:
            raise HTTPException(status_code=400, detail="ZIP archive is empty")
        return entries

    def _cleanup_minio_objects(self, object_paths: list[str]) -> None:
        for object_path in object_paths:
            try:
                self.minio_client.remove_object(self.BUCKET_NAME, object_path)
            except S3Error:
                pass


async def get_storage_service(
    db: AsyncSession = Depends(get_db),
    current_user: SessionData = Depends(get_current_user),
) -> StorageService:
    return StorageService(user_id=current_user.user_id, db=db)
