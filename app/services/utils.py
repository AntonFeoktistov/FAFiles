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
