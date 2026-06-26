from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.file_service import FileService

from ..models import File, Folder


class FolderService:
    @staticmethod
    async def create_folder(
        name: str, parent_path: str, user_id: int, db: AsyncSession
    ) -> Folder:
        full_path = f"{parent_path}{name}/".replace("//", "/")
        print(parent_path)
        existing = await db.execute(
            select(Folder).where(
                Folder.user_id == user_id, Folder.full_path == full_path
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(409, "Folder already exists")

        parent = None
        if parent_path:
            parent_result = await db.execute(
                select(Folder).where(
                    Folder.user_id == user_id, Folder.full_path == parent_path
                )
            )
            parent = parent_result.scalar_one_or_none()
            if not parent:
                raise HTTPException(404, "Parent folder not found")

        new_folder = Folder(
            user_id=user_id,
            name=name,
            parent_id=parent.id if parent else None,
            full_path=full_path,
        )

        db.add(new_folder)
        await db.commit()
        await db.refresh(new_folder)

        return new_folder

    @staticmethod
    async def delete_folder(folder_path: str, user_id: int, db: AsyncSession) -> bool:

        folder = FolderService._get_folder_with_children(folder_path, user_id, db)

        await load_all_children(folder, db)

        all_files = []
        collect_files(folder, all_files)

        for file_obj in all_files:
            await FileService.delete_file(file_obj.file_path, user_id, db)

        await db.delete(folder)
        await db.commit()

        return True

    @staticmethod
    async def rename_folder(
        from_path: str, to_path: str, user_id: int, db: AsyncSession
    ) -> bool:

        folder = await FolderService._get_folder_only(from_path, user_id, db)

        try:
            await FolderService._get_folder_only(to_path, user_id, db)
            raise HTTPException(409, "Folder already exists")
        except HTTPException:
            pass

        await load_all_children(folder, db)

        all_files = []
        collect_files(folder, all_files)

        for file in all_files:
            from_path_file = from_path + file.name
            to_path_file = to_path + file.name
            await FileService.rename_file(from_path_file, to_path_file, user_id, db)

        from_prefix_db = from_path if from_path.endswith("/") else from_path + "/"

        await db.execute(
            update(Folder)
            .where(
                Folder.user_id == user_id,
                Folder.full_path.startswith(from_prefix_db),
                Folder.full_path != from_path,
            )
            .values(full_path=func.replace(Folder.full_path, from_path, to_path))
        )

        await db.execute(
            update(File)
            .where(File.user_id == user_id, File.file_path.startswith(from_prefix_db))
            .values(file_path=func.replace(File.file_path, from_path, to_path))
        )

        folder.full_path = to_path
        folder.name = to_path.rstrip("/").split("/")[-1]

        await db.commit()
        await db.refresh(folder)

        return True

    @staticmethod
    async def _get_folder_only(
        folder_path: str, user_id: int, db: AsyncSession
    ) -> Folder:

        folder_query = await db.execute(
            select(Folder).where(
                Folder.user_id == user_id, Folder.full_path == folder_path
            )
        )
        folder = folder_query.scalar_one_or_none()

        if not folder:
            raise HTTPException(404, "Folder not found")

        return folder

    @staticmethod
    async def _get_folder_with_children(
        folder_path: str, user_id: int, db: AsyncSession
    ) -> Folder:

        folder_query = await db.execute(
            select(Folder)
            .where(Folder.user_id == user_id, Folder.full_path == folder_path)
            .options(selectinload(Folder.subfolders), selectinload(Folder.files))
        )
        folder = folder_query.scalar_one_or_none()

        if not folder:
            raise HTTPException(404, "Folder not found")

        return folder

    @staticmethod
    async def find_files(query: str, user_id: int, db: AsyncSession) -> list[File]:
        files_query = await db.execute(
            select(File).where(File.user_id == user_id, File.name.contains(query))
        )
        files = files_query.scalars().all()
        return files


async def load_all_children(folder: Folder, db: AsyncSession):

    await db.refresh(folder, attribute_names=["subfolders", "files"])

    for subfolder in folder.subfolders:
        await load_all_children(subfolder, db)


def collect_files(folder: Folder, all_files: list):
    all_files.extend(folder.files)
    for subfolder in folder.subfolders:
        collect_files(subfolder, all_files)
