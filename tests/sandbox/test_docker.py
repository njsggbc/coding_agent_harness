import pytest
import docker
from harness.sandbox.docker import DockerSandbox
from harness.sandbox.base import ExecResult


@pytest.fixture
def docker_sandbox():
    try:
        client = docker.from_env()
        client.ping()
    except Exception:
        pytest.skip("Docker not available")
    return DockerSandbox(client)


@pytest.mark.asyncio
async def test_create_and_stop_container(docker_sandbox, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    (repo_path / "test.txt").write_text("hello")

    container_id = await docker_sandbox.create(
        image="python:3.11-alpine",
        workdir="/workspace",
        repo_path=str(repo_path),
    )

    assert container_id is not None

    await docker_sandbox.stop(container_id)


@pytest.mark.asyncio
async def test_exec_command(docker_sandbox, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    container_id = await docker_sandbox.create(
        image="python:3.11-alpine",
        workdir="/workspace",
        repo_path=str(repo_path),
    )

    try:
        result = await docker_sandbox.exec(container_id, "echo hello")
        assert result.exit_code == 0
        assert "hello" in result.stdout
    finally:
        await docker_sandbox.stop(container_id)


@pytest.mark.asyncio
async def test_read_write_file(docker_sandbox, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    container_id = await docker_sandbox.create(
        image="python:3.11-alpine",
        workdir="/workspace",
        repo_path=str(repo_path),
    )

    try:
        await docker_sandbox.write_file(container_id, "/workspace/test.py", "print('hello')")
        content = await docker_sandbox.read_file(container_id, "/workspace/test.py")
        assert content == "print('hello')"
    finally:
        await docker_sandbox.stop(container_id)


@pytest.mark.asyncio
async def test_setup_commands(docker_sandbox, tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    container_id = await docker_sandbox.create(
        image="python:3.11-alpine",
        workdir="/workspace",
        repo_path=str(repo_path),
    )

    try:
        await docker_sandbox.setup(container_id, ["pip install --version"])
    finally:
        await docker_sandbox.stop(container_id)