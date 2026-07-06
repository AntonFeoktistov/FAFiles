import os

from dotenv import load_dotenv
from minio import Minio, S3Error

load_dotenv()


def _make_minio_client():
    minio_client = Minio(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000")
        .replace("http://", "")
        .replace("https://", ""),
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=os.getenv("MINIO_USE_SSL", "false").lower() == "true",
    )
    return minio_client


BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "user-files")
minio_client = _make_minio_client()

if not minio_client.bucket_exists(BUCKET_NAME):
    minio_client.make_bucket(BUCKET_NAME)


async def is_file_exists(file_path: str) -> bool:
    try:
        minio_client.stat_object(BUCKET_NAME, file_path)
        return True
    except S3Error as e:
        if e.code == "NoSuchKey":
            return False
        raise


async def cleanup_minio_objects(object_paths: list[str]) -> None:
    for object_path in object_paths:
        try:
            minio_client.remove_object(BUCKET_NAME, object_path)
        except S3Error:
            pass
