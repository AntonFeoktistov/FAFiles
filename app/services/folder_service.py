import os
import tempfile
import zipfile
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from minio import S3Error
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.services.file_service import FileService

from ..models import File, Folder
from .file_service import BUCKET_NAME, minio_client


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

        folder = FolderService.get_folder_with_children(folder_path, user_id, db)

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

    @staticmethod
    async def find_files(query: str, user_id: int, db: AsyncSession) -> list[File]:
        files_query = await db.execute(
            select(File).where(File.user_id == user_id, File.name.contains(query))
        )
        files = files_query.scalars().all()
        return files

    @staticmethod
    async def download_folder(folder_path: str, user_id: int, db: AsyncSession):

        folder = await FolderService._get_folder_only(folder_path, user_id, db)
        if not folder:
            raise HTTPException(404, "Folder not found")

        files_query = await db.execute(
            select(File).where(
                File.user_id == user_id, File.file_path.startswith(folder_path)
            )
        )
        all_files = files_query.scalars().all()

        if not all_files:
            raise HTTPException(404, "Folder is empty")

        return await FolderService._download_folder_as_zip(
            folder_path, folder.name, all_files
        )

    @staticmethod
    async def _download_folder_as_zip(
        folder_path: str, folder_name: str, files: list
    ) -> StreamingResponse:

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        tmp_path = tmp.name
        tmp.close()

        try:
            with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for file_obj in files:
                    try:
                        response = minio_client.get_object(
                            BUCKET_NAME, file_obj.file_path
                        )
                        content = response.read()
                        response.close()
                        response.release_conn()

                        arcname = file_obj.file_path[len(folder_path) :]
                        zip_file.writestr(arcname, content)

                    except S3Error as e:
                        print(f"Error: {e}")
                        continue
        except Exception:
            os.unlink(tmp_path)
            raise

        def iter_file():
            try:
                with open(tmp_path, "rb") as f:
                    yield from f
            finally:
                os.unlink(tmp_path)

        encoded_name = quote(folder_name, encoding="utf-8")

        return StreamingResponse(
            iter_file(),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}.zip",
                "Content-Length": str(os.path.getsize(tmp_path)),
            },
        )

    @staticmethod
    def _get_content_type(filename: str) -> str:
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        types = {
            "pdf": "application/pdf",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "txt": "text/plain",
            "doc": "application/msword",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "xls": "application/vnd.ms-excel",
            "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        }
        return types.get(ext, "application/octet-stream")


async def load_all_children(folder: Folder, db: AsyncSession):

    await db.refresh(folder, attribute_names=["subfolders", "files"])

    for subfolder in folder.subfolders:
        await load_all_children(subfolder, db)


def collect_files(folder: Folder, all_files: list):
    all_files.extend(folder.files)
    for subfolder in folder.subfolders:
        collect_files(subfolder, all_files)
