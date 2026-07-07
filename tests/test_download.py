import utils
from fastapi import status
from httpx import AsyncClient


async def test_download_file_success(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):

    content = "Hello World"
    file_name = "test1.txt"

    await utils.upload_file(
        auth_client,
        get_root_folder,
        make_test_file,
        name=file_name,
        content=content,
    )

    file_path = get_root_folder + file_name
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.content == content.encode("utf-8")
    assert response.headers["content-type"] == "application/octet-stream"


async def test_download_file_not_found(
    auth_client: AsyncClient,
    get_root_folder: str,
):
    file_path = get_root_folder + "nonexistent.txt"
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_download_file_unauthorized(
    unauth_client: AsyncClient,
    get_root_folder: str,
):
    file_path = get_root_folder + "test.txt"
    response = await unauth_client.get(
        "/api/resource/download",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_download_folder_success(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    folder_name = "docs"
    folder_path = get_root_folder + folder_name + "/"

    await utils.create_folder(auth_client, get_root_folder, name=folder_name)

    expected_files = {
        "report.pdf": "PDF Content",
        "photo.jpg": "JPEG Content",
        "readme.txt": "README Content",
    }

    for name, content in expected_files.items():
        await utils.upload_file(
            auth_client,
            folder_path,
            make_test_file,
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
    get_root_folder: str,
):
    folder_name = "empty_folder"
    folder_path = get_root_folder + folder_name + "/"

    await utils.create_folder(auth_client, get_root_folder, name=folder_name)

    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "empty" in response.json()["message"].lower()


async def test_download_folder_not_found(
    auth_client: AsyncClient,
    get_root_folder: str,
):
    folder_path = get_root_folder + "nonexistent_folder/"
    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_download_folder_unauthorized(
    unauth_client: AsyncClient,
    get_root_folder: str,
):
    folder_path = get_root_folder + "some_folder/"
    response = await unauth_client.get(
        "/api/resource/download",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_download_folder_wrong_user(
    auth_client: AsyncClient,
    get_root_folder: str,
    get_root_folder_2: str,
    make_test_file,
    auth_client_2: AsyncClient,
):
    folder_name = "docs"

    folder_path_2 = get_root_folder_2 + folder_name + "/"

    await utils.create_folder(auth_client_2, get_root_folder_2, name=folder_name)
    await utils.upload_file(
        auth_client_2,
        folder_path_2,
        make_test_file,
        name="file.txt",
        content="Hello",
    )

    response = await auth_client.get(
        "/api/resource/download",
        params={"path": folder_path_2},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
