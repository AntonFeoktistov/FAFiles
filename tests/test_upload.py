from httpx import AsyncClient

from tests import utils


async def test_upload_single_file(
    auth_client: AsyncClient,
    make_test_file,
):
    name, content, folder = "test1.txt", "Hello World", ""
    await utils.upload_file(auth_client, make_test_file, name=name, content=content)
    file_path = folder + name
    await utils.assert_file_exists(
        auth_client,
        file_path,
        expected_name=name,
        expected_size=len(content),
    )


async def test_upload_file_already_exists(
    auth_client: AsyncClient,
    make_test_file,
):
    name = "test1.txt"

    await utils.upload_file(auth_client, make_test_file, name=name)

    await utils.upload_file_expect_failure(
        auth_client,
        make_test_file,
        name=name,
        expected_status=409,
        expected_message="already exists",
    )


async def test_upload_file_invalid_folder(
    auth_client: AsyncClient,
    make_test_file,
):
    await utils.upload_file_expect_failure(
        auth_client,
        make_test_file,
        "nonexistent-folder/",
        expected_status=404,
        expected_message="не найдена",
    )


async def test_upload_file_unauthorized(
    unauth_client: AsyncClient,
    make_test_file,
):
    await utils.upload_file_expect_failure(
        unauth_client,
        make_test_file,
        expected_status=401,
    )
