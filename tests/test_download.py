import utils
from fastapi import status
from httpx import AsyncClient


async def test_download_file_success(
    auth_client: AsyncClient,
    make_test_file,
):

    content = "Hello World"
    file_name = "test1.txt"

    await utils.upload_file(
        auth_client,
        make_test_file,
        name=file_name,
        content=content,
    )

    file_path = file_name
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.content == content.encode("utf-8")
    assert response.headers["content-type"] == "application/octet-stream"


async def test_download_file_not_found(
    auth_client: AsyncClient,
):
    file_path = "nonexistent.txt"
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_download_file_empty_path(
    auth_client: AsyncClient,
):
    file_path = ""
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_download_file_unauthorized(
    unauth_client: AsyncClient,
):
    file_path = "test.txt"
    response = await unauth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_download_folder_success(
    auth_client: AsyncClient,
    make_test_file,
):
    folder_name = "docs"
    folder_path = folder_name + "/"

    await utils.create_folder(auth_client, name=folder_name)

    expected_files = {
        "report.pdf": "PDF Content",
        "photo.jpg": "JPEG Content",
        "readme.txt": "README Content",
    }

    for name, content in expected_files.items():
        await utils.upload_file(
            auth_client,
            make_test_file,
            folder_path,
            name=name,
            content=content,
        )

    await utils.assert_download_folder(
        auth_client,
        folder_path,
        expected_files=expected_files,
        expected_zip_name=folder_name,
    )


async def test_download_empty_folder(
    auth_client: AsyncClient,
):
    folder_name = "empty_folder"
    folder_path = folder_name + "/"

    await utils.create_folder(auth_client, name=folder_name)

    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "empty" in response.json()["message"].lower()


async def test_download_folder_not_found(
    auth_client: AsyncClient,
):
    folder_path = "nonexistent_folder/"
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_download_folder_empty_path(
    auth_client: AsyncClient,
):
    folder_path = ""
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_download_folder_empty_path_2(
    auth_client: AsyncClient,
):
    folder_path = "/"
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_download_folder_unauthorized(
    unauth_client: AsyncClient,
):
    folder_path = "some_folder/"
    response = await unauth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_download_folder_wrong_user(
    auth_client: AsyncClient,
    make_test_file,
    auth_client_2: AsyncClient,
):
    folder_name = "docs"

    folder_path_2 = folder_name + "/"

    await utils.create_folder(auth_client_2, name=folder_name)
    await utils.upload_file(
        auth_client_2,
        make_test_file,
        folder_path_2,
        name="file.txt",
        content="Hello",
    )

    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path_2},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
