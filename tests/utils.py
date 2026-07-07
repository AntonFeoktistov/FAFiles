from fastapi import status
from httpx import AsyncClient


async def assert_file_exists(
    auth_client: AsyncClient,
    file_path: str,
    expected_name: str = None,
    expected_size: int = None,
):
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
