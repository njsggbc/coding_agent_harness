### Task 4: Sandbox Layer

**Files:**
- Create: `harness/sandbox/base.py`
- Create: `harness/sandbox/guard.py`
- Create: `harness/sandbox/docker.py`
- Test: `tests/sandbox/test_guard.py`
- Test: `tests/sandbox/test_docker.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `ExecResult` dataclass: `exit_code: int`, `stdout: str`, `stderr: str`
  - `Sandbox` ABC with methods: `async create(image: str, workdir: str, repo_path: str) -> str`, `async exec(container_id: str, command: str, workdir: Optional[str]) -> ExecResult`, `async read_file(container_id: str, path: str) -> str`, `async write_file(container_id: str, path: str, content: str)`, `async setup(container_id: str, commands: list[str])`, `async stop(container_id: str)`
  - `DockerSandbox(Sandbox)` class
  - `CommandGuard(blocked_patterns: list[str])` class with `check(tool_name: str, args: dict) -> bool`

- [ ] **Step 1: Write base.py (no test needed, just ABC)**

```python
# harness/sandbox/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class Sandbox(ABC):
    @abstractmethod
    async def create(self, image: str, workdir: str, repo_path: str) -> str:
        ...

    @abstractmethod
    async def exec(self, container_id: str, command: str, workdir: Optional[str] = None) -> ExecResult:
        ...

    @abstractmethod
    async def read_file(self, container_id: str, path: str) -> str:
        ...

    @abstractmethod
    async def write_file(self, container_id: str, path: str, content: str):
        ...

    @abstractmethod
    async def setup(self, container_id: str, commands: list[str]):
        ...

    @abstractmethod
    async def stop(self, container_id: str):
        ...
```

- [ ] **Step 2: Write failing guard test**

```python
# tests/sandbox/test_guard.py
import pytest
from harness.sandbox.guard import CommandGuard, GuardBlockedError


def test_guard_allows_safe_command():
    guard = CommandGuard(blocked_patterns=["rm -rf /", "shutdown"])

    guard.check("run_shell", {"command": "ls -la"})
    guard.check("run_shell", {"command": "pytest tests/"})


def test_guard_blocks_dangerous_command():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    with pytest.raises(GuardBlockedError, match="Command blocked"):
        guard.check("run_shell", {"command": "rm -rf /"})


def test_guard_blocks_dangerous_command_in_subcommand():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    with pytest.raises(GuardBlockedError):
        guard.check("run_shell", {"command": "sudo rm -rf / --no-preserve-root"})


def test_guard_ignores_non_shell_tools():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    guard.check("read_file", {"path": "/etc/passwd"})
    guard.check("write_file", {"path": "/tmp/test", "content": "rm -rf /"})


def test_guard_with_empty_blocked_list():
    guard = CommandGuard(blocked_patterns=[])

    guard.check("run_shell", {"command": "rm -rf /"})
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/sandbox/test_guard.py -v
```

Expected: FAIL

- [ ] **Step 4: Write guard.py**

```python
# harness/sandbox/guard.py
class GuardBlockedError(Exception):
    pass


class CommandGuard:
    def __init__(self, blocked_patterns: list[str]):
        self.blocked_patterns = blocked_patterns

    def check(self, tool_name: str, args: dict) -> bool:
        if tool_name == "run_shell":
            command = args.get("command", "")
            for pattern in self.blocked_patterns:
                if pattern in command:
                    raise GuardBlockedError(
                        f"Command blocked: '{command}' matches pattern '{pattern}'"
                    )
        return True
```

- [ ] **Step 5: Run guard test to verify it passes**

```bash
pytest tests/sandbox/test_guard.py -v
```

Expected: PASS

- [ ] **Step 6: Write failing Docker test**

```python
# tests/sandbox/test_docker.py
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
```

- [ ] **Step 7: Run test to verify it fails**

```bash
pytest tests/sandbox/test_docker.py -v
```

Expected: FAIL with import errors

- [ ] **Step 8: Write docker.py**

```python
# harness/sandbox/docker.py
import asyncio
from typing import Optional
import docker
from docker.models.containers import Container
from harness.sandbox.base import Sandbox, ExecResult


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
        kwargs = {"cmd": ["sh", "-c", command]}
        if workdir:
            kwargs["workdir"] = workdir

        result = await self._run_async(container.exec_run, **kwargs)
        return ExecResult(
            exit_code=result.exit_code,
            stdout=result.output.decode("utf-8", errors="replace") if result.output else "",
            stderr="",
        )

    async def read_file(self, container_id: str, path: str) -> str:
        result = await self.exec(container_id, f"cat '{path}'")
        if result.exit_code != 0:
            raise FileNotFoundError(f"Cannot read {path}: {result.stdout}")
        return result.stdout

    async def write_file(self, container_id: str, path: str, content: str):
        escaped = content.replace("'", "'\\''")
        result = await self.exec(container_id, f"cat > '{path}' << 'EOF'\n{escaped}\nEOF")
        if result.exit_code != 0:
            raise RuntimeError(f"Cannot write {path}: {result.stdout}")

    async def setup(self, container_id: str, commands: list[str]):
        for cmd in commands:
            await self.exec(container_id, cmd)

    async def stop(self, container_id: str):
        try:
            container = self.client.containers.get(container_id)
            await self._run_async(container.stop, timeout=5)
        except docker.errors.NotFound:
            pass
```

- [ ] **Step 9: Run Docker test to verify it passes**

```bash
pytest tests/sandbox/test_docker.py -v
```

Expected: PASS (or SKIP if Docker not available)

- [ ] **Step 10: Commit**

```bash
git add harness/sandbox/ tests/sandbox/
git commit -m "feat: add sandbox layer with Docker, Guard, and abstract interface"
```

---

