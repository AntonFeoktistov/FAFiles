from fastapi import status
from httpx import AsyncClient
from utils import assert_file_exists


async def test_upload_single_file(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    file = make_test_file("test1.txt", "Hello World")
    response = await auth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()[0]["name"] == "test1.txt"

    file_path = get_root_folder + "test1.txt"
    await assert_file_exists(
        auth_client,
        file_path,
        expected_name="test1.txt",
        expected_size=len("Hello World"),
    )


async def test_upload_multiple_files(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    files_data = [
        make_test_file("test1.txt", "Hello World"),
        make_test_file("test2.txt", "Hello World2"),
    ]

    files = [("files", file) for file in files_data]

    response = await auth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files=files,
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert len(data) == 2
    assert data[0]["name"] == "test1.txt"
    assert data[1]["name"] == "test2.txt"

    for file_name, file_content in files_data:
        file_path = get_root_folder + file_name
        await assert_file_exists(
            auth_client,
            file_path,
            expected_name=file_name,
            expected_size=len(file_content),
        )


async def test_upload_file_already_exists(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    file = make_test_file("test1.txt", "Hello World")

    response = await auth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_201_CREATED

    response = await auth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in response.json()["message"].lower()


async def test_upload_file_invalid_folder(
    auth_client: AsyncClient,
    make_test_file,
):
    file = make_test_file("test.txt", "Hello")
    response = await auth_client.post(
        "/api/resource",
        params={"path": "nonexistent-folder/"},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "не найдена" in response.json()["message"]


async def test_upload_empty_file(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    file = make_test_file("empty.txt", "")
    response = await auth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data[0]["name"] == "empty.txt"
    assert data[0]["size"] == 0


async def test_upload_file_unauthorized(
    unauth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    file = make_test_file("test.txt", "Hello")
    response = await unauth_client.post(
        "/api/resource",
        params={"path": get_root_folder},
        files={"files": file},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
