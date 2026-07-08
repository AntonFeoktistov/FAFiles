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

        await self._move_in_minio(path_from, path_to)

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

        path_from = utils.normalize_path(path_from)
        path_to = utils.normalize_path(path_to)

        folder = await self._validate_folder_exists(path_from)
        await self._validate_target_not_exists(path_to)
        updated_folders = await self._update_folder_paths(folder, path_from, path_to)
        await self._move_files_and_update_paths(path_from, path_to, updated_folders)

        await self.db.commit()
        await self.db.refresh(folder)

        return folder

    async def _validate_folder_exists(self, path: str) -> Folder:
        folder = await self.repo.get_folder_or_none(path)
        if not folder:
            raise HTTPException(404, f"Folder '{path}' not found")
        return folder

    async def _validate_target_not_exists(self, path: str) -> None:
        folder_to = await self.repo.get_folder_or_none(path)
        if folder_to:
            raise HTTPException(409, f"Folder on '{path}' already exists")

    async def _move_in_minio(self, from_path: str, to_path: str) -> None:
        try:
            copy_source = CopySource(self.BUCKET_NAME, from_path)
            self.minio_client.copy_object(self.BUCKET_NAME, to_path, copy_source)
            self.minio_client.remove_object(self.BUCKET_NAME, from_path)
        except S3Error as e:
            raise HTTPException(500, f"MinIO error: {e}")

    async def _update_folder_paths(
        self,
        folder: Folder,
        path_from: str,
        path_to: str,
    ) -> dict[str, Folder]:
        old_full = folder.full_path
        new_full = old_full.replace(path_from, path_to, 1)
        folder.full_path = new_full
        folder.name, _ = utils.get_resource_name_and_parent_path(new_full)
        folder.parent_id = None

        updated_folders: dict[str, Folder] = {new_full: folder}

        _, parent_path = utils.get_resource_name_and_parent_path(new_full)
        if parent_path:
            parent_folder = await self.repo.get_folder_or_none(parent_path)
            if parent_folder:
                updated_folders[parent_path] = parent_folder

        descendant_folders = await self.repo.get_folders_by_prefix(path_from)
        for subfolder in descendant_folders:
            old_subpath = subfolder.full_path
            new_subpath = old_subpath.replace(path_from, path_to, 1)
            subfolder.full_path = new_subpath
            subfolder.name, _ = utils.get_resource_name_and_parent_path(new_subpath)
            updated_folders[new_subpath] = subfolder

        self._set_parent_ids(updated_folders)

        return updated_folders

    def _set_parent_ids(self, folders: dict[str, Folder]) -> None:
        for f in folders.values():
            _, parent_path = utils.get_resource_name_and_parent_path(f.full_path)
            if parent_path in folders:
                f.parent_id = folders[parent_path].id

    async def _move_files_and_update_paths(
        self,
        path_from: str,
        path_to: str,
        updated_folders: dict[str, Folder],
    ) -> None:
        files = await self.repo.get_files_by_prefix(path_from)

        for file_obj in files:
            old_path = file_obj.full_path
            new_path = old_path.replace(path_from, path_to, 1)

            await self._move_in_minio(old_path, new_path)

            file_obj.full_path = new_path
            file_obj.name, _ = utils.get_resource_name_and_parent_path(new_path)

            _, parent_path = utils.get_resource_name_and_parent_path(new_path)
            if parent_path in updated_folders:
                file_obj.folder_id = updated_folders[parent_path].id
