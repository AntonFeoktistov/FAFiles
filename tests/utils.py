import zipfile
from io import BytesIO

from fastapi import status
from httpx import AsyncClient


async def upload_file(
    auth_client: AsyncClient,
    make_test_file,
    folder_path: str = "",
    name: str = "test.txt",
    content: str = "Hello World",
    expected_status: int = 201,
) -> dict:

    file = make_test_file(name, content)
    response = await auth_client.post(
        "/api/resource",
        params={"path": folder_path},
        files={"files": file},
    )

    assert response.status_code == expected_status
    data = response.json()

    if expected_status == 201:
        if isinstance(data, list):
            assert data[0]["name"] == name
        else:
            assert data["name"] == name

    return data


async def upload_file_expect_failure(
    auth_client: AsyncClient,
    make_test_file,
    folder_path: str = "",
    name: str = "test.txt",
    content: str = "Hello World",
    expected_status: int = 409,
    expected_message: str = None,
) -> dict:
    file = make_test_file(name, content)
    response = await auth_client.post(
        "/api/resource",
        params={"path": folder_path},
        files={"files": file},
    )

    assert response.status_code == expected_status
    data = response.json()

    if expected_message:
        assert expected_message in data.get("message", "")

    return data


async def create_folder(
    auth_client: AsyncClient,
    root_path: str = "",
    name: str = "new_folder",
    expected_status: int = 201,
) -> dict:
    folder_path = root_path + name
    response = await auth_client.post(
        "/api/directory",
        params={"path": folder_path},
    )

    assert response.status_code == expected_status
    data = response.json()

    if expected_status == 201:
        print(data["name"], name)
        assert data["name"] == name

    return data


async def create_folder_expect_failure(
    auth_client: AsyncClient,
    root_path: str = "",
    name: str = "new_folder",
    expected_status: int = 409,
    expected_message: str = None,
) -> dict:
    folder_path = root_path + name
    response = await auth_client.post(
        "/api/directory",
        params={"path": folder_path},
    )

    assert response.status_code == expected_status
    data = response.json()

    if expected_message:
        assert expected_message in data.get("message", "")

    return data


async def assert_file_exists(
    auth_client: AsyncClient,
    file_path: str,
    expected_name: str = None,
    expected_size: int = None,
) -> dict:
    response = await auth_client.get(
        "/api/resource",
        params={"path": file_path},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    if isinstance(data, list):
        assert len(data) == 1
        item = data[0]
    else:
        item = data

    assert item["type"] == "FILE"

    if expected_name:
        assert item["name"] == expected_name

    if expected_size is not None:
        assert item["size"] == expected_size

    return item


async def assert_file_not_found(
    auth_client: AsyncClient,
    file_path: str,
) -> dict:
    response = await auth_client.get(
        "/api/resource",
        params={"path": file_path},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    return response.json()


async def assert_folder_exists(
    auth_client: AsyncClient,
    folder_path: str,
    expected_name: str = None,
) -> dict:
    response = await auth_client.get(
        "/api/resource",
        params={"path": folder_path},
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["type"] == "DIRECTORY"
    if expected_name:
        assert data["name"] == expected_name

    return data


async def assert_folder_not_found(
    auth_client: AsyncClient,
    folder_path: str,
) -> dict:
    response = await auth_client.get(
        "/api/resource",
        params={"path": folder_path},
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    return response.json()


async def assert_download_file(
    auth_client: AsyncClient,
    file_path: str,
    expected_name: str,
    expected_content: str | bytes,
) -> None:
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )

    assert response.status_code == status.HTTP_200_OK

    if isinstance(expected_content, str):
        expected_content = expected_content.encode("utf-8")

    assert response.content == expected_content
    assert (
        f'attachment; filename="{expected_name}"'
        in response.headers["content-disposition"]
    )
    assert response.headers["content-type"] == "application/octet-stream"


async def assert_download_folder(
    auth_client: AsyncClient,
    folder_path: str,
    expected_files: dict[str, str | bytes],
    expected_zip_name: str = None,
) -> None:
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/zip"

    if expected_zip_name:
        assert (
            f'attachment; filename="{expected_zip_name}.zip"'
            in response.headers["content-disposition"]
        )

    zip_content = BytesIO(response.content)

    with zipfile.ZipFile(zip_content, "r") as zip_file:
        zip_names = zip_file.namelist()

        for name, content in expected_files.items():
            assert name in zip_names, f"File '{name}' not found in ZIP"
            if isinstance(content, str):
                assert zip_file.read(name).decode("utf-8") == content
            else:
                assert zip_file.read(name) == content
