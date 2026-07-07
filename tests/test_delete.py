import utils
from fastapi import status
from httpx import AsyncClient


async def test_delete_file_success(
    auth_client: AsyncClient,
    make_test_file,
):
    await utils.upload_file(
        auth_client,
        make_test_file,
        name="test1.txt",
        content="Hello World",
    )

    file_path = "test1.txt"

    response = await auth_client.delete(
        "/api/resource",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    await utils.assert_file_not_found(auth_client, file_path)


async def test_delete_folder_success(
    auth_client: AsyncClient,
    make_test_file,
):
    folder_name = "new_folder"
    folder_path = folder_name + "/"

    await utils.create_folder(auth_client, name=folder_name)
    await utils.upload_file(
        auth_client,
        make_test_file,
        folder_path=folder_name,
        name="test1.txt",
        content="text",
    )
    file_path = folder_path + "test1.txt"

    response = await auth_client.delete(
        "/api/resource",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_204_NO_CONTENT

    await utils.assert_folder_not_found(auth_client, folder_path)
    await utils.assert_file_not_found(auth_client, file_path)


async def test_delete_file_not_found(
    auth_client: AsyncClient,
):
    file_path = "nonexistent.txt"

    response = await auth_client.delete(
        "/api/resource",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["message"].lower()


async def test_delete_folder_not_found(
    auth_client: AsyncClient,
):
    folder_path = "nonexistent_folder/"

    response = await auth_client.delete(
        "/api/resource",
        params={"path": folder_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["message"].lower()


async def test_delete_file_unauthorized(
    unauth_client: AsyncClient,
):
    file_path = "test.txt"

    response = await unauth_client.delete(
        "/api/resource",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_delete_file_invalid_path(
    auth_client: AsyncClient,
):
    response = await auth_client.delete(
        "/api/resource",
        params={"path": ""},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


async def test_delete_file_wrong_user(
    auth_client: AsyncClient,
    make_test_file,
    auth_client_2: AsyncClient,
):
    await utils.upload_file(
        auth_client_2,
        make_test_file,
        name="test1.txt",
        content="Hello World",
    )
    file_path = "test1.txt"

    response = await auth_client.get(
        "/api/resource",
        params={"path": file_path},
    )
    print(f"GET ответ: {response.status_code}")

    response = await auth_client.delete(
        "/api/resource",
        params={"path": file_path},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
