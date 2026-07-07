import utils
from httpx import AsyncClient


async def test_get_file_success(
    auth_client: AsyncClient,
    get_root_folder: str,
    make_test_file,
):
    await utils.upload_file(
        auth_client,
        get_root_folder,
        make_test_file,
        name="test1.txt",
        content="Hello World",
    )

    file_path = get_root_folder + "test1.txt"
    await utils.assert_file_exists(
        auth_client,
        file_path,
        expected_name="test1.txt",
        expected_size=len("Hello World"),
    )


async def test_get_folder_success(
    auth_client: AsyncClient,
    get_root_folder: str,
):
    folder_name = "new_folder"
    folder_path = get_root_folder + folder_name + "/"

    await utils.create_folder(auth_client, get_root_folder, name=folder_name)

    await utils.assert_folder_exists(
        auth_client,
        folder_path,
        expected_name=folder_name,
    )
