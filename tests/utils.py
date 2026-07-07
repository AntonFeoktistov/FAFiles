from fastapi import status
from httpx import AsyncClient


async def upload_file(
    auth_client: AsyncClient,
    folder_path: str,
    make_test_file,
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
        assert data[0]["name"] == name

    return data


async def upload_file_expect_failure(
    auth_client: AsyncClient,
    folder_path: str,
    make_test_file,
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
    root_path: str,
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
    root_path: str,
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
