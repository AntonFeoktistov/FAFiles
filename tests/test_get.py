import pytest

pytestmark = pytest.mark.asyncio(loop_scope="function")


@pytest.mark.asyncio
async def test_get_folder_files(auth_client, test_user):

    response = await auth_client.get(
        "/resource/",
        params={
            "folder_path": f"{test_user.username}-files/",
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert "subfolders" in data
    assert "files" in data

    if data["subfolders"]:
        subfolder = data["subfolders"][0]
        assert "name" in subfolder
        assert "full_path" in subfolder

    if data["files"]:
        file = data["files"][0]
        assert "name" in file
        assert "file_path" in file


@pytest.mark.asyncio
async def test_get_folder_files_incorrect_path(auth_client, test_user):
    response = await auth_client.get(
        "/resource/",
        params={
            "folder_path": "error_path/",
        },
    )

    assert response.status_code == 404
    data = response.json()

    assert "detail" in data
