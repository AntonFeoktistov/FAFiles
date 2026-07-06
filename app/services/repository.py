from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import File, Folder
from app.services import utils


class StorageRepository:
    def __init__(self, user_id: int, db: AsyncSession):
        self.user_id = user_id
        self.db = db

    async def create_folder(self, name: str, parent_path: str) -> Folder:
        name = name.strip("/")
        parent_path = utils.normalize_path(parent_path) if parent_path else ""

        folder_path = f"{parent_path}{name}/"
        folder_path = utils.normalize_path(folder_path)

        existing = await self.get_folder_or_none(folder_path)
        if existing:
            raise HTTPException(409, "Folder already exists")

        parent = None
        if parent_path:
            parent_result = await self.db.execute(
                select(Folder).where(
                    Folder.user_id == self.user_id,
                    Folder.full_path == parent_path,
                )
            )
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise HTTPException(
                    404, f"Родительская папка не найдена: {parent_path}"
                )

        new_folder = Folder(
            user_id=self.user_id,
            name=name,
            parent_id=parent.id if parent else None,
            full_path=folder_path,
        )

        self.db.add(new_folder)
        await self.db.flush()
        return new_folder

    async def ensure_folder_path(self, path: str) -> tuple[Folder, list[Folder]]:
        path = utils.normalize_path(path)
        folder = await self.get_folder_or_none(path)
        if folder:
            return folder, []
        name, parent_path = utils.get_resource_name_and_parent_path(path)
        created: list[Folder] = []
        if parent_path:
            _, parent_created = await self.ensure_folder_path(parent_path)
            created.extend(parent_created)
        folder = await self.create_folder(name, parent_path)
        created.append(folder)
        return folder, created

    async def get_or_create_folder_by_path(self, path: str) -> Folder:
        folder, _ = await self.ensure_folder_path(path)
        return folder

    async def get_file_or_none(self, file_path: str) -> Optional[File]:
        query = await self.db.execute(
            select(File).where(
                File.user_id == self.user_id,
                File.full_path == file_path,
            )
        )
        return query.scalar_one_or_none()

    async def get_folder_or_none(self, folder_path: str) -> Optional[Folder]:
        folder_path = utils.normalize_path(folder_path)

        folder_query = await self.db.execute(
            select(Folder).where(
                Folder.user_id == self.user_id,
                Folder.full_path == folder_path,
            )
        )
        return folder_query.scalar_one_or_none()

    async def get_files_by_prefix(self, prefix: str) -> list[File]:
        query = await self.db.execute(
            select(File).where(
                File.user_id == self.user_id, File.full_path.startswith(prefix)
            )
        )
        return query.scalars().all()

    async def get_folder_or_none(self, folder_path: str) -> Optional[Folder]:
        folder_path = utils.normalize_path(folder_path)

        folder_query = await self.db.execute(
            select(Folder).where(
                Folder.user_id == self.user_id,
                Folder.full_path == folder_path,
            )
        )
        return folder_query.scalar_one_or_none()

    async def get_files_by_query(self, query: str) -> list:
        query = await self.db.execute(
            select(File).where(File.user_id == self.user_id, File.name.contains(query))
        )
        return query.scalars().all()

    async def get_folders_by_query(self, query: str) -> list:
        query = await self.db.execute(
            select(Folder).where(
                Folder.user_id == self.user_id, Folder.name.contains(query)
            )
        )
        return query.scalars().all()

    async def create_file_in_db(
        self, folder_id: int, full_path: str, file_size: int
    ) -> File:
        file_name, _ = utils.get_resource_name_and_parent_path(full_path)
        file = File(
            user_id=self.user_id,
            name=file_name,
            folder_id=folder_id,
            full_path=full_path,
            size=file_size,
        )
        self.db.add(file)
        await self.db.commit()
        await self.db.refresh(file)
        return file
