import utils
from httpx import AsyncClient


async def test_get_file_success(
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
    await utils.assert_file_exists(
        auth_client,
        file_path,
        expected_name="test1.txt",
        expected_size=len("Hello World"),
    )


async def test_get_folder_success(
    auth_client: AsyncClient,
):
    folder_name = "new_folder"
    folder_path = folder_name + "/"

    await utils.create_folder(auth_client, name=folder_name)

    await utils.assert_folder_exists(
        auth_client,
        folder_path,
        expected_name=folder_name,
    )
