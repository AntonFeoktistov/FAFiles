import io
import zipfile
from tempfile import SpooledTemporaryFile
from typing import List

from fastapi import HTTPException, UploadFile


def is_resource_folder(path):
    return path.endswith("/")


def normalize_path(path: str) -> str:
    if not path:
        return ""
    while "//" in path:
        path = path.replace("//", "/")
    if path.startswith("/"):
        path = path[1:]
    if not path.endswith("/"):
        path += "/"
    return path


def validate_path(path: str, param_name: str = "path") -> str:

    if not path or not path.strip():
        raise HTTPException(
            status_code=400, detail=f"Параметр '{param_name}' не может быть пустым"
        )
    path = path.strip()
    dangerous_chars = ["..", "\\", ":", "*", "?", '"', "<", ">", "|"]
    for char in dangerous_chars:
        if char in path:
            raise HTTPException(
                status_code=400, detail=f"Недопустимый символ '{char}' в пути"
            )
    if path.startswith("/") or path.startswith("\\"):
        raise HTTPException(status_code=400, detail="Путь не должен начинаться с '/'")
    if len(path) > 1024:
        raise HTTPException(
            status_code=400, detail="Путь слишком длинный (максимум 1024 символа)"
        )
    return path


def normalize_relative_path(filename: str) -> str:
    path = filename.replace("\\", "/").lstrip("./")
    if not path or path.endswith("/"):
        raise ValueError("Invalid file path")
    if ".." in path.split("/"):
        raise ValueError("Invalid file path")
    return path


def get_resource_name_and_parent_path(full_path: str):
    path = full_path.rstrip("/")
    parts = path.split("/")
    name = parts[-1]
    if len(parts) > 1:
        parent = "/".join(parts[:-1]) + "/"
    else:
        parent = ""
    return (name, parent)


def parse_relative_path(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid file path")
    try:
        return normalize_relative_path(filename)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file path")


async def expand_upload_files(files: List[UploadFile]) -> List[UploadFile]:
    if (
        len(files) == 1
        and files[0].filename
        and files[0].filename.lower().endswith(".zip")
    ):
        return await _zip_to_upload_files(files[0])
    return files


def get_content_type(filename: str) -> str:
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
        "ppt": "application/vnd.ms-powerpoint",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "zip": "application/zip",
        "rar": "application/x-rar-compressed",
        "7z": "application/x-7z-compressed",
        "mp4": "video/mp4",
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "json": "application/json",
        "xml": "application/xml",
        "csv": "text/csv",
        "html": "text/html",
        "css": "text/css",
        "js": "application/javascript",
    }
    return types.get(ext, "application/octet-stream")


async def _zip_to_upload_files(zip_file: UploadFile) -> List[UploadFile]:
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
