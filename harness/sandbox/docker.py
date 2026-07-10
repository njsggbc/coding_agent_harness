import asyncio
import base64
import logging
import shlex
from typing import Optional
import docker
from harness.sandbox.base import Sandbox, ExecResult

logger = logging.getLogger(__name__)


class DockerSandbox(Sandbox):
    def __init__(self, client: docker.DockerClient):
        self.client = client

    async def _run_async(self, func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    async def create(self, image: str, workdir: str, repo_path: str) -> str:
        container = await self._run_async(
            self.client.containers.run,
            image=image,
            command="tail -f /dev/null",
            volumes={repo_path: {"bind": workdir, "mode": "rw"}},
            working_dir=workdir,
            detach=True,
            remove=True,
        )
        return container.id

    async def exec(self, container_id: str, command: str, workdir: Optional[str] = None) -> ExecResult:
        container = self.client.containers.get(container_id)
        kwargs = {"cmd": ["sh", "-c", command], "demux": True}
        if workdir:
            kwargs["workdir"] = workdir

        result = await self._run_async(container.exec_run, **kwargs)
        exit_code, (stdout, stderr) = result
        return ExecResult(
            exit_code=exit_code,
            stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
            stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
        )

    async def read_file(self, container_id: str, path: str) -> str:
        result = await self.exec(container_id, f"cat {shlex.quote(path)}")
        if result.exit_code != 0:
            raise FileNotFoundError(f"Cannot read {path}: {result.stdout or result.stderr}")
        return result.stdout

    async def write_file(self, container_id: str, path: str, content: str):
        encoded = base64.b64encode(content.encode()).decode()
        result = await self.exec(
            container_id, f"echo {shlex.quote(encoded)} | base64 -d > {shlex.quote(path)}"
        )
        if result.exit_code != 0:
            raise RuntimeError(f"Cannot write {path}: {result.stdout or result.stderr}")

    async def setup(self, container_id: str, commands: list[str]):
        for cmd in commands:
            result = await self.exec(container_id, cmd)
            if result.exit_code != 0:
                logger.warning(
                    "Setup command failed (continuing): %s\nstdout: %s\nstderr: %s",
                    cmd, result.stdout, result.stderr,
                )

    async def stop(self, container_id: str):
        try:
            container = self.client.containers.get(container_id)
            await self._run_async(container.stop, timeout=5)
        except docker.errors.NotFound:
            pass