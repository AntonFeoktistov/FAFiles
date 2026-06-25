from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import Folder


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
    async def get_folder_with_children(
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
