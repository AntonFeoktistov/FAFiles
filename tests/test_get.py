from fastapi import status
from httpx import AsyncClient

from app.services import utils


async def assert_get_file(auth_client: AsyncClient, file_path):
    response = await auth_client.post(
        "/api/resource",
        params={"path": file_path},
    )
    name, folder_path = utils.get_resource_name_and_parent_path(file_path)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data[0]["name"] == name
    assert data[0]["path"] == folder_path
    assert data[0]["size"] is not None
    assert data[0]["type"] == "FILE"
