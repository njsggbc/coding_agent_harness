# Coding Agent Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI tool that drives an OpenAI-powered agent to autonomously fix bugs in code repositories within Docker sandboxes.

**Architecture:** Core + Plugin architecture. CLI layer invokes TaskManager, which orchestrates AgentLoop. AgentLoop drives the tool-calling cycle via Adapter, executing tools inside a Docker Sandbox. Observer emits events for streaming/logging. Storage persists task state to SQLite + files.

**Tech Stack:** Python 3.11+, asyncio, openai, docker-py, click, pyyaml, gitpython, pytest, pytest-asyncio

## Global Constraints

- Python 3.11+ required
- Zero non-essential dependencies (sqlite3 from stdlib, no ORM)
- All async I/O uses asyncio
- Docker must be installed and running for sandbox tasks
- `data/` directory default at project root, overridable via config.yaml or CLI
- `tasks/` directory for YAML task definitions
- `reports/` directory for generated reports
- TDD: write failing test first, then implementation
- Frequent commits per task

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `harness/__init__.py`
- Create: `harness/core/__init__.py`
- Create: `harness/adapters/__init__.py`
- Create: `harness/tools/__init__.py`
- Create: `harness/sandbox/__init__.py`
- Create: `harness/storage/__init__.py`
- Create: `harness/observer/__init__.py`
- Create: `harness/report/__init__.py`
- Create: `harness/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tasks/.gitkeep`
- Create: `reports/.gitkeep`
- Create: `data/.gitkeep`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: project structure, `pyproject.toml` with all dependencies, `config.yaml` template

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "harness"
version = "0.1.0"
description = "Coding Agent Harness - Bug-fixing agent orchestration framework"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.0.0",
    "docker>=7.0.0",
    "click>=8.1.0",
    "pyyaml>=6.0",
    "gitpython>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[project.scripts]
harness = "harness.cli.main:cli"
```

- [ ] **Step 2: Create config.yaml**

```yaml
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "${OPENAI_API_KEY}"

logging:
  level: "INFO"
  file: "harness.log"
```

- [ ] **Step 3: Create conftest.py**

```python
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_config_yaml():
    return """
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "test-key"

logging:
  level: "INFO"
  file: "harness.log"
"""
```

- [ ] **Step 4: Create all __init__.py files (empty)**

- [ ] **Step 5: Create .gitignore**

```
__pycache__/
*.pyc
data/
.env
*.egg-info/
dist/
build/
```

- [ ] **Step 6: Create .gitkeep files for tasks/, reports/, data/**

- [ ] **Step 7: Install dependencies and verify**

```bash
pip install -e ".[dev]"
```

Expected: all packages install without error

- [ ] **Step 8: Run a smoke test**

```python
# tests/test_scaffolding.py
def test_imports():
    import harness
    from harness.core import task
    from harness.adapters import base
    from harness.tools import registry
    from harness.sandbox import base as sandbox_base
    from harness.storage import db
    from harness.observer import base as observer_base
    from harness.report import generator
    from harness.cli import main
```

```bash
pytest tests/test_scaffolding.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure and dependencies"
```

---

### Task 2: Task Model

**Files:**
- Create: `harness/core/task.py`
- Test: `tests/core/test_task.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `TaskConfig` dataclass
  - `EnvironmentConfig` dataclass
  - `AgentConfig` dataclass
  - `SandboxConfig` dataclass
  - `VerificationConfig` dataclass
  - `TaskStatus` enum: `PENDING = "pending"`, `RUNNING = "running"`, `DONE = "done"`, `FAILED = "failed"`, `CANCELLED = "cancelled"`
  - `load_task_config(path: str) -> TaskConfig` function
  - `TaskConfig.from_yaml(path: str) -> TaskConfig` classmethod

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_task.py
import pytest
import yaml
from pathlib import Path
from harness.core.task import (
    TaskConfig,
    EnvironmentConfig,
    AgentConfig,
    SandboxConfig,
    VerificationConfig,
    TaskStatus,
    load_task_config,
)


SAMPLE_TASK_YAML = """
id: "bug-123"
name: "修复登录超时"
description: "修复 session 过期问题"
repo: "https://github.com/example/repo"
branch: "main"
base_commit: "abc1234"

environment:
  image: "python:3.11"
  setup_commands:
    - "pip install -r requirements.txt"

agent:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 600
  blocked_commands:
    - "rm -rf /"

verification:
  commands:
    - "pytest tests/"
"""


def test_task_config_from_yaml(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(SAMPLE_TASK_YAML)

    config = load_task_config(str(task_file))

    assert config.id == "bug-123"
    assert config.name == "修复登录超时"
    assert config.repo == "https://github.com/example/repo"
    assert config.branch == "main"
    assert config.base_commit == "abc1234"

    assert config.environment.image == "python:3.11"
    assert config.environment.setup_commands == ["pip install -r requirements.txt"]

    assert config.agent.model == "gpt-4o"
    assert config.agent.max_turns == 30
    assert config.agent.temperature == 0.0

    assert config.sandbox.workdir == "/workspace"
    assert config.sandbox.timeout == 600
    assert config.sandbox.blocked_commands == ["rm -rf /"]

    assert config.verification.commands == ["pytest tests/"]


def test_task_config_without_optional_fields(tmp_path):
    yaml_content = """
id: "bug-456"
name: "simple bug"
description: "simple desc"
repo: "https://github.com/example/repo"
branch: "main"

environment:
  image: "python:3.11"
  setup_commands: []

agent:
  model: "gpt-4o"
  max_turns: 10
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 300
  blocked_commands: []
"""
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml_content)

    config = load_task_config(str(task_file))

    assert config.base_commit is None
    assert config.verification is None


def test_task_status_enum():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_task.py -v
```

Expected: FAIL with import errors

- [ ] **Step 3: Write implementation**

```python
# harness/core/task.py
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import yaml


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EnvironmentConfig:
    image: str
    setup_commands: list[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    model: str
    max_turns: int
    temperature: float


@dataclass
class SandboxConfig:
    workdir: str
    timeout: int
    blocked_commands: list[str] = field(default_factory=list)


@dataclass
class VerificationConfig:
    commands: list[str] = field(default_factory=list)


@dataclass
class TaskConfig:
    id: str
    name: str
    description: str
    repo: str
    branch: str
    environment: EnvironmentConfig
    agent: AgentConfig
    sandbox: SandboxConfig
    base_commit: Optional[str] = None
    verification: Optional[VerificationConfig] = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaskConfig":
        env = EnvironmentConfig(
            image=data["environment"]["image"],
            setup_commands=data["environment"].get("setup_commands", []),
        )
        agent = AgentConfig(
            model=data["agent"]["model"],
            max_turns=data["agent"]["max_turns"],
            temperature=data["agent"]["temperature"],
        )
        sandbox = SandboxConfig(
            workdir=data["sandbox"]["workdir"],
            timeout=data["sandbox"]["timeout"],
            blocked_commands=data["sandbox"].get("blocked_commands", []),
        )
        verification = None
        if "verification" in data and data["verification"] is not None:
            verification = VerificationConfig(
                commands=data["verification"].get("commands", [])
            )

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            repo=data["repo"],
            branch=data["branch"],
            base_commit=data.get("base_commit"),
            environment=env,
            agent=agent,
            sandbox=sandbox,
            verification=verification,
        )


def load_task_config(path: str) -> TaskConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TaskConfig.from_dict(data)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_task.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/task.py tests/core/test_task.py
git commit -m "feat: add task config model with YAML loader"
```

---

### Task 3: Storage Layer

**Files:**
- Create: `harness/storage/db.py`
- Create: `harness/storage/files.py`
- Test: `tests/storage/test_db.py`
- Test: `tests/storage/test_files.py`

**Interfaces:**
- Consumes: `TaskConfig`, `TaskStatus` from `harness.core.task`
- Produces:
  - `TaskStore(data_dir: str)` class with methods: `create(task: TaskConfig, task_file: str) -> str`, `update_status(task_id: str, status: TaskStatus)`, `update_result(task_id: str, turns: int, tokens_used: int, error: Optional[str])`, `get(task_id: str) -> dict`, `list_all(status: Optional[str] = None) -> list[dict]`
  - `FileStore(data_dir: str)` class with methods: `save_messages(task_id: str, messages: list[dict])`, `save_tool_calls(task_id: str, calls: list[dict])`, `save_diff(task_id: str, diff: str)`, `save_agent_log(task_id: str, events: list[dict])`, `load_messages(task_id: str) -> list[dict]`, `load_diff(task_id: str) -> str`

- [ ] **Step 1: Write failing test for TaskStore**

```python
# tests/storage/test_db.py
import pytest
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig, TaskStatus
from harness.storage.db import TaskStore


def make_task_config(**kwargs):
    defaults = {
        "id": "bug-001",
        "name": "test bug",
        "description": "test desc",
        "repo": "https://github.com/test/repo",
        "branch": "main",
        "environment": EnvironmentConfig(image="python:3.11", setup_commands=[]),
        "agent": AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        "sandbox": SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    }
    defaults.update(kwargs)
    return TaskConfig(**defaults)


def test_create_and_get_task(temp_dir):
    store = TaskStore(str(temp_dir))
    task = make_task_config()

    task_id = store.create(task, "tasks/bug-001.yaml")

    assert task_id == "bug-001"

    record = store.get(task_id)
    assert record["id"] == "bug-001"
    assert record["name"] == "test bug"
    assert record["status"] == "pending"
    assert record["repo"] == "https://github.com/test/repo"
    assert record["model"] == "gpt-4o"
    assert record["task_file"] == "tasks/bug-001.yaml"


def test_update_status(temp_dir):
    store = TaskStore(str(temp_dir))
    task = make_task_config()
    store.create(task, "tasks/bug-001.yaml")

    store.update_status("bug-001", TaskStatus.RUNNING)
    record = store.get("bug-001")
    assert record["status"] == "running"


def test_update_result(temp_dir):
    store = TaskStore(str(temp_dir))
    task = make_task_config()
    store.create(task, "tasks/bug-001.yaml")

    store.update_result("bug-001", turns=5, tokens_used=1000, error=None)

    record = store.get("bug-001")
    assert record["turns"] == 5
    assert record["tokens_used"] == 1000
    assert record["error"] is None


def test_list_all(temp_dir):
    store = TaskStore(str(temp_dir))

    for i in range(3):
        task = make_task_config(id=f"bug-{i:03d}", name=f"bug {i}")
        store.create(task, f"tasks/bug-{i:03d}.yaml")

    store.update_status("bug-000", TaskStatus.DONE)

    all_tasks = store.list_all()
    assert len(all_tasks) == 3

    done_tasks = store.list_all(status="done")
    assert len(done_tasks) == 1
    assert done_tasks[0]["id"] == "bug-000"


def test_get_nonexistent_returns_none(temp_dir):
    store = TaskStore(str(temp_dir))
    assert store.get("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/storage/test_db.py -v
```

Expected: FAIL with import errors

- [ ] **Step 3: Write TaskStore implementation**

```python
# harness/storage/db.py
import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional
from harness.core.task import TaskConfig, TaskStatus


class TaskStore:
    def __init__(self, data_dir: str):
        self.db_path = os.path.join(data_dir, "harness.db")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    repo        TEXT NOT NULL,
                    branch      TEXT NOT NULL,
                    model       TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    started_at  TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    turns       INTEGER,
                    tokens_used INTEGER,
                    error       TEXT,
                    task_file   TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    tool_name   TEXT NOT NULL,
                    args        TEXT NOT NULL,
                    result      TEXT,
                    duration_ms INTEGER,
                    success     INTEGER NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)

    def create(self, task: TaskConfig, task_file: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO tasks (id, name, status, repo, branch, model,
                   created_at, task_file)
                   VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)""",
                (task.id, task.name, task.repo, task.branch, task.agent.model, now, task_file),
            )
        return task.id

    def update_status(self, task_id: str, status: TaskStatus):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            if status == TaskStatus.RUNNING:
                conn.execute(
                    "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
                    (status.value, now, task_id),
                )
            elif status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                conn.execute(
                    "UPDATE tasks SET status = ?, finished_at = ? WHERE id = ?",
                    (status.value, now, task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE id = ?",
                    (status.value, task_id),
                )

    def update_result(self, task_id: str, turns: int, tokens_used: int, error: Optional[str] = None):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET turns = ?, tokens_used = ?, error = ? WHERE id = ?",
                (turns, tokens_used, error, task_id),
            )

    def get(self, task_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def list_all(self, status: Optional[str] = None) -> list[dict]:
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
```

- [ ] **Step 4: Run DB test to verify it passes**

```bash
pytest tests/storage/test_db.py -v
```

Expected: PASS

- [ ] **Step 5: Write failing test for FileStore**

```python
# tests/storage/test_files.py
import json
from harness.storage.files import FileStore


def test_save_and_load_messages(temp_dir):
    store = FileStore(str(temp_dir))
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Fix the bug."},
    ]

    store.save_messages("task-001", messages)
    loaded = store.load_messages("task-001")

    assert loaded == messages


def test_save_and_load_diff(temp_dir):
    store = FileStore(str(temp_dir))
    diff = "diff --git a/file.py b/file.py\n+ fixed line"

    store.save_diff("task-001", diff)
    loaded = store.load_diff("task-001")

    assert loaded == diff


def test_save_tool_calls(temp_dir):
    store = FileStore(str(temp_dir))
    calls = [
        {"turn": 1, "tool": "read_file", "args": {"path": "test.py"}, "result": "content"},
        {"turn": 1, "tool": "edit_file", "args": {"path": "test.py"}, "result": "edited"},
    ]

    store.save_tool_calls("task-001", calls)
    task_dir = temp_dir / "tasks" / "task-001"
    assert (task_dir / "tool_calls.jsonl").exists()


def test_save_agent_log(temp_dir):
    store = FileStore(str(temp_dir))
    events = [
        {"type": "turn_start", "turn": 1},
        {"type": "tool_call", "tool": "read_file"},
    ]

    store.save_agent_log("task-001", events)
    task_dir = temp_dir / "tasks" / "task-001"
    assert (task_dir / "agent.log").exists()
```

- [ ] **Step 6: Run file test to verify it fails**

```bash
pytest tests/storage/test_files.py -v
```

Expected: FAIL

- [ ] **Step 7: Write FileStore implementation**

```python
# harness/storage/files.py
import json
import os
from pathlib import Path


class FileStore:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.tasks_dir = self.data_dir / "tasks"

    def _task_dir(self, task_id: str) -> Path:
        d = self.tasks_dir / task_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_messages(self, task_id: str, messages: list[dict]):
        path = self._task_dir(task_id) / "messages.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def load_messages(self, task_id: str) -> list[dict]:
        path = self._task_dir(task_id) / "messages.jsonl"
        if not path.exists():
            return []
        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    def save_tool_calls(self, task_id: str, calls: list[dict]):
        path = self._task_dir(task_id) / "tool_calls.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for call in calls:
                f.write(json.dumps(call, ensure_ascii=False) + "\n")

    def save_diff(self, task_id: str, diff: str):
        path = self._task_dir(task_id) / "diff.patch"
        with open(path, "w", encoding="utf-8") as f:
            f.write(diff)

    def load_diff(self, task_id: str) -> str:
        path = self._task_dir(task_id) / "diff.patch"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_agent_log(self, task_id: str, events: list[dict]):
        path = self._task_dir(task_id) / "agent.log"
        with open(path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
```

- [ ] **Step 8: Run file test to verify it passes**

```bash
pytest tests/storage/test_files.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add harness/storage/ tests/storage/
git commit -m "feat: add SQLite and file storage layer"
```

---

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

### Task 5: Adapter Layer

**Files:**
- Create: `harness/adapters/base.py`
- Create: `harness/adapters/openai.py`
- Test: `tests/adapters/test_openai.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `ToolCall` dataclass: `id: str`, `name: str`, `arguments: dict`
  - `TokenUsage` dataclass: `prompt_tokens: int`, `completion_tokens: int`, `total_tokens: int`
  - `AdapterResponse` dataclass: `content: Optional[str]`, `tool_calls: list[ToolCall]`, `finish_reason: str`, `usage: Optional[TokenUsage]`
  - `BaseAdapter` ABC with `async chat(messages: list[dict], tools: list[dict]) -> AdapterResponse`
  - `OpenAIAdapter(BaseAdapter)` with constructor `__init__(model: str, api_key: str, temperature: float)`

- [ ] **Step 1: Write base.py**

```python
# harness/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AdapterResponse:
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Optional[TokenUsage] = None


class BaseAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict]) -> AdapterResponse:
        ...
```

- [ ] **Step 2: Write failing OpenAI test**

```python
# tests/adapters/test_openai.py
import pytest
import os
from harness.adapters.openai import OpenAIAdapter
from harness.adapters.base import AdapterResponse


@pytest.fixture
def adapter():
    api_key = os.environ.get("OPENAI_API_KEY", "test-key")
    return OpenAIAdapter(model="gpt-4o", api_key=api_key, temperature=0.0)


@pytest.mark.asyncio
async def test_chat_simple_response(adapter):
    if os.environ.get("OPENAI_API_KEY") is None:
        pytest.skip("OPENAI_API_KEY not set")

    messages = [{"role": "user", "content": "Say hello in one word."}]
    tools = []

    response = await adapter.chat(messages, tools)

    assert isinstance(response, AdapterResponse)
    assert response.content is not None
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_chat_with_tools(adapter):
    if os.environ.get("OPENAI_API_KEY") is None:
        pytest.skip("OPENAI_API_KEY not set")

    messages = [{"role": "user", "content": "What is 2+2?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Calculate a math expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"}
                    },
                    "required": ["expression"],
                },
            },
        }
    ]

    response = await adapter.chat(messages, tools)

    assert isinstance(response, AdapterResponse)
    assert response.usage is not None
    assert response.usage.total_tokens > 0
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/adapters/test_openai.py -v
```

Expected: FAIL with import errors

- [ ] **Step 4: Write openai.py**

```python
# harness/adapters/openai.py
import json
from openai import AsyncOpenAI
from harness.adapters.base import BaseAdapter, AdapterResponse, ToolCall, TokenUsage


class OpenAIAdapter(BaseAdapter):
    def __init__(self, model: str, api_key: str, temperature: float):
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(self, messages: list[dict], tools: list[dict]) -> AdapterResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return AdapterResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
```

- [ ] **Step 5: Run OpenAI test to verify it passes**

```bash
OPENAI_API_KEY=sk-test pytest tests/adapters/test_openai.py -v
```

Expected: SKIP if no real key, PASS if key is set

- [ ] **Step 6: Commit**

```bash
git add harness/adapters/ tests/adapters/
git commit -m "feat: add adapter layer with OpenAI implementation"
```

---

### Task 6: Observer Layer

**Files:**
- Create: `harness/observer/base.py`
- Create: `harness/observer/stream.py`
- Create: `harness/observer/logger.py`
- Test: `tests/observer/test_observer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - Event dataclasses: `TurnStart(turn_number: int)`, `ToolCallStart(tool_name: str, args: dict)`, `ToolCallEnd(tool_name: str, result: str, duration: float)`, `AgentThinking(content: str)`, `LoopError(error: str)`, `LoopComplete(status: str, turns: int, tokens_used: int)`, `SandboxEvent(message: str)`
  - `Observer` class with `emit(event)`, `subscribe(handler: callable)`, `unsubscribe(handler: callable)`
  - `StreamObserver` class that prints formatted events to terminal
  - `LogObserver` class that writes JSONL events to file

- [ ] **Step 1: Write base.py**

```python
# harness/observer/base.py
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class TurnStart:
    turn_number: int


@dataclass
class ToolCallStart:
    tool_name: str
    args: dict


@dataclass
class ToolCallEnd:
    tool_name: str
    result: str
    duration: float


@dataclass
class AgentThinking:
    content: str


@dataclass
class LoopError:
    error: str


@dataclass
class LoopComplete:
    status: str
    turns: int
    tokens_used: int


@dataclass
class SandboxEvent:
    message: str


class Observer:
    def __init__(self):
        self._handlers: list[Callable] = []

    def subscribe(self, handler: Callable):
        self._handlers.append(handler)

    def unsubscribe(self, handler: Callable):
        self._handlers.remove(handler)

    def emit(self, event):
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                pass
```

- [ ] **Step 2: Write failing test**

```python
# tests/observer/test_observer.py
import pytest
from harness.observer.base import (
    Observer,
    TurnStart,
    ToolCallStart,
    ToolCallEnd,
    AgentThinking,
    LoopError,
    LoopComplete,
    SandboxEvent,
)
from harness.observer.stream import StreamObserver
from harness.observer.logger import LogObserver


class TestObserver:
    def test_emit_delivers_to_subscriber(self):
        events = []
        observer = Observer()
        observer.subscribe(lambda e: events.append(e))

        observer.emit(TurnStart(turn_number=1))
        observer.emit(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))

        assert len(events) == 2
        assert isinstance(events[0], TurnStart)
        assert events[0].turn_number == 1
        assert isinstance(events[1], ToolCallStart)
        assert events[1].tool_name == "read_file"

    def test_unsubscribe_stops_delivery(self):
        events = []
        observer = Observer()

        def handler(e):
            events.append(e)

        observer.subscribe(handler)
        observer.emit(TurnStart(turn_number=1))
        observer.unsubscribe(handler)
        observer.emit(TurnStart(turn_number=2))

        assert len(events) == 1

    def test_handler_exception_does_not_break_others(self):
        events = []
        observer = Observer()

        def bad_handler(e):
            raise RuntimeError("boom")

        def good_handler(e):
            events.append(e)

        observer.subscribe(bad_handler)
        observer.subscribe(good_handler)
        observer.emit(TurnStart(turn_number=1))

        assert len(events) == 1


class TestStreamObserver:
    def test_stream_observer_does_not_crash(self, capsys):
        stream = StreamObserver()
        stream(TurnStart(turn_number=1))
        stream(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))
        stream(ToolCallEnd(tool_name="read_file", result="file content", duration=0.5))
        stream(AgentThinking(content="I need to read the file"))
        stream(LoopError(error="connection timeout"))
        stream(LoopComplete(status="done", turns=3, tokens_used=1500))
        stream(SandboxEvent(message="Container started"))


class TestLogObserver:
    def test_log_observer_writes_events(self, temp_dir):
        log_path = temp_dir / "test.log"
        logger = LogObserver(str(log_path))

        logger(TurnStart(turn_number=1))
        logger(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))
        logger(LoopComplete(status="done", turns=3, tokens_used=1500))

        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/observer/test_observer.py -v
```

Expected: FAIL

- [ ] **Step 4: Write stream.py**

```python
# harness/observer/stream.py
import sys
from harness.observer.base import (
    TurnStart,
    ToolCallStart,
    ToolCallEnd,
    AgentThinking,
    LoopError,
    LoopComplete,
    SandboxEvent,
)


class StreamObserver:
    def __init__(self, output=None):
        self.output = output or sys.stdout
        self._turn_count = 0

    def __call__(self, event):
        if isinstance(event, TurnStart):
            self._turn_count = event.turn_number
            self.output.write(f"\n{'─' * 50}\n  Turn {event.turn_number}\n{'─' * 50}\n")
        elif isinstance(event, AgentThinking):
            self.output.write(f"🤖 Agent thinking...\n   \"{event.content[:200]}{'...' if len(event.content) > 200 else ''}\"\n\n")
        elif isinstance(event, ToolCallStart):
            self.output.write(f"🔧 {event.tool_name}({self._format_args(event.args)})\n")
        elif isinstance(event, ToolCallEnd):
            short = event.result[:100].replace('\n', ' ')
            self.output.write(f"   ✓ {short}{'...' if len(event.result) > 100 else ''} ({event.duration:.1f}s)\n\n")
        elif isinstance(event, LoopError):
            self.output.write(f"❌ Error: {event.error}\n")
        elif isinstance(event, LoopComplete):
            self.output.write(f"\n{'─' * 50}\n✅ Task {event.status} in {event.turns} turns, {event.tokens_used} tokens\n{'─' * 50}\n")
        elif isinstance(event, SandboxEvent):
            self.output.write(f"  {event.message}\n")
        self.output.flush()

    def _format_args(self, args: dict) -> str:
        parts = []
        for k, v in args.items():
            s = str(v)
            if len(s) > 60:
                s = s[:57] + "..."
            parts.append(f"{k}={s}")
        return ", ".join(parts)
```

- [ ] **Step 5: Write logger.py**

```python
# harness/observer/logger.py
import json
from dataclasses import asdict


class LogObserver:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, event):
        data = {"type": type(event).__name__, **asdict(event)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/observer/test_observer.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add harness/observer/ tests/observer/
git commit -m "feat: add observer layer with stream and log observers"
```

---

### Task 7: Tool System

**Files:**
- Create: `harness/tools/registry.py`
- Create: `harness/tools/files.py`
- Create: `harness/tools/shell.py`
- Create: `harness/tools/search.py`
- Create: `harness/tools/git.py`
- Test: `tests/tools/test_registry.py`
- Test: `tests/tools/test_tools.py`

**Interfaces:**
- Consumes: `Sandbox` from `harness.sandbox.base`, `CommandGuard` from `harness.sandbox.guard`
- Produces:
  - `ToolResult` dataclass: `success: bool`, `output: str`, `error: Optional[str]`
  - `Tool` ABC: `name: str`, `description: str`, `parameters: dict`, `async execute(args: dict, sandbox: Sandbox) -> ToolResult`
  - `ToolRegistry` class: `register(tool: Tool)`, `get(name: str) -> Tool`, `get_all() -> list[Tool]`, `to_openai_schema() -> list[dict]`
  - Built-in tools: `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `RunShellTool`, `SearchContentTool`, `SearchFilesTool`, `GitDiffTool`, `GitLogTool`, `ListDirTool`

- [ ] **Step 1: Write registry.py**

```python
# harness/tools/registry.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from harness.sandbox.base import Sandbox


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        ...

    @abstractmethod
    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        ...


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas
```

- [ ] **Step 2: Write failing registry test**

```python
# tests/tools/test_registry.py
import pytest
from harness.tools.registry import Tool, ToolResult, ToolRegistry
from harness.sandbox.base import Sandbox


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"],
    }

    async def execute(self, args, sandbox):
        return ToolResult(success=True, output=f"got {args['arg1']}")


def test_register_and_get_tool():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)

    assert registry.get("fake_tool") is tool
    assert registry.get("nonexistent") is None


def test_get_all_tools():
    registry = ToolRegistry()
    registry.register(FakeTool())

    tools = registry.get_all()
    assert len(tools) == 1
    assert tools[0].name == "fake_tool"


def test_unregister_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    registry.unregister("fake_tool")

    assert registry.get("fake_tool") is None


def test_to_openai_schema():
    registry = ToolRegistry()
    registry.register(FakeTool())

    schemas = registry.to_openai_schema()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"
    assert "parameters" in schemas[0]["function"]
```

- [ ] **Step 3: Run registry test to verify it passes**

```bash
pytest tests/tools/test_registry.py -v
```

Expected: PASS

- [ ] **Step 4: Write failing tools test**

```python
# tests/tools/test_tools.py
import pytest
import os
from harness.tools.files import ReadFileTool, WriteFileTool, EditFileTool
from harness.tools.shell import RunShellTool
from harness.tools.search import SearchContentTool, SearchFilesTool
from harness.tools.git import GitDiffTool, GitLogTool, ListDirTool
from harness.tools.registry import ToolResult


class FakeSandbox:
    def __init__(self):
        self.files = {}
        self.commands = []

    async def read_file(self, container_id, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def write_file(self, container_id, path, content):
        self.files[path] = content

    async def exec(self, container_id, command, workdir=None):
        self.commands.append(command)
        from harness.sandbox.base import ExecResult
        return ExecResult(exit_code=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_read_file():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "print('hello')"
    tool = ReadFileTool()

    result = await tool.execute({"path": "/ws/test.py"}, sandbox)
    assert result.success
    assert "print('hello')" in result.output


@pytest.mark.asyncio
async def test_read_file_with_offset_limit():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "line1\nline2\nline3\nline4\n"
    tool = ReadFileTool()

    result = await tool.execute({"path": "/ws/test.py", "offset": 2, "limit": 2}, sandbox)
    assert result.success
    assert "line2" in result.output
    assert "line3" in result.output
    assert "line4" not in result.output


@pytest.mark.asyncio
async def test_write_file():
    sandbox = FakeSandbox()
    tool = WriteFileTool()

    result = await tool.execute({"path": "/ws/new.py", "content": "x = 1"}, sandbox)
    assert result.success
    assert sandbox.files["/ws/new.py"] == "x = 1"


@pytest.mark.asyncio
async def test_edit_file():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "old content here"
    tool = EditFileTool()

    result = await tool.execute(
        {"path": "/ws/test.py", "old_str": "old content", "new_str": "new content"},
        sandbox,
    )
    assert result.success
    assert sandbox.files["/ws/test.py"] == "new content here"


@pytest.mark.asyncio
async def test_edit_file_not_found():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "different content"
    tool = EditFileTool()

    result = await tool.execute(
        {"path": "/ws/test.py", "old_str": "not in file", "new_str": "replacement"},
        sandbox,
    )
    assert not result.success


@pytest.mark.asyncio
async def test_run_shell():
    sandbox = FakeSandbox()
    tool = RunShellTool()

    result = await tool.execute({"command": "ls -la"}, sandbox)
    assert result.success
    assert "ls -la" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_content():
    sandbox = FakeSandbox()
    tool = SearchContentTool()

    result = await tool.execute({"pattern": "TODO", "path": "/ws"}, sandbox)
    assert result.success
    assert "grep" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_files():
    sandbox = FakeSandbox()
    tool = SearchFilesTool()

    result = await tool.execute({"pattern": "*.py", "path": "/ws"}, sandbox)
    assert result.success
    assert "find" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_diff():
    sandbox = FakeSandbox()
    tool = GitDiffTool()

    result = await tool.execute({}, sandbox)
    assert result.success
    assert "git diff" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_log():
    sandbox = FakeSandbox()
    tool = GitLogTool()

    result = await tool.execute({"count": 5}, sandbox)
    assert result.success
    assert "git log" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_list_dir():
    sandbox = FakeSandbox()
    tool = ListDirTool()

    result = await tool.execute({"path": "/ws"}, sandbox)
    assert result.success
    assert "ls" in sandbox.commands[0]
```

- [ ] **Step 5: Run test to verify it fails**

```bash
pytest tests/tools/test_tools.py -v
```

Expected: FAIL with import errors

- [ ] **Step 6: Write files.py**

```python
# harness/tools/files.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Use offset and limit for large files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to read"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            lines = content.split("\n")
            offset = args.get("offset", 1) - 1
            limit = args.get("limit")
            if limit:
                lines = lines[offset:offset + limit]
            else:
                lines = lines[offset:]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write or overwrite a file with the given content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            await sandbox.write_file("", args["path"], args["content"])
            return ToolResult(success=True, output=f"File written: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace exact string in a file. The old_str must match exactly including whitespace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "old_str": {"type": "string", "description": "Exact string to replace"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            old_str = args["old_str"]
            new_str = args["new_str"]

            if old_str not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"old_str not found in {args['path']}",
                )

            count = content.count(old_str)
            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} matches for old_str. Provide more context to make it unique.",
                )

            new_content = content.replace(old_str, new_str, 1)
            await sandbox.write_file("", args["path"], new_content)
            return ToolResult(success=True, output=f"File edited: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 7: Write shell.py**

```python
# harness/tools/shell.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class RunShellTool(Tool):
    name = "run_shell"
    description = "Execute a shell command in the sandbox. Use for running tests, installing packages, etc."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "workdir": {"type": "string", "description": "Working directory for the command"},
        },
        "required": ["command"],
    }

    MAX_OUTPUT = 8000

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", args["command"], workdir=args.get("workdir"))
            output = result.stdout
            if len(output) > self.MAX_OUTPUT:
                output = output[:self.MAX_OUTPUT] + "\n... (output truncated)"

            if result.exit_code != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {result.exit_code}",
                )

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 8: Write search.py**

```python
# harness/tools/search.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class SearchContentTool(Tool):
    name = "search_content"
    description = "Search for a regex pattern in file contents. Fast grep-like search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory or file path to search in"},
            "include": {"type": "string", "description": "File pattern filter, e.g. '*.py'"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            cmd_parts = ["grep", "-rn", "--include", args.get("include", "*")]
            search_path = args.get("path", ".")
            cmd_parts.extend([args["pattern"], search_path])
            result = await sandbox.exec("", " ".join(cmd_parts))
            return ToolResult(success=True, output=result.stdout or "No matches found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Find files matching a glob pattern. Fast file name search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
            "path": {"type": "string", "description": "Directory to search in"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            search_path = args.get("path", ".")
            result = await sandbox.exec("", f"find {search_path} -name '{args['pattern']}' -type f")
            return ToolResult(success=True, output=result.stdout or "No files found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 9: Write git.py**

```python
# harness/tools/git.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show the current git diff of all changes made so far."
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", "git diff")
            return ToolResult(success=True, output=result.stdout or "No changes")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitLogTool(Tool):
    name = "git_log"
    description = "Show recent git commit history."
    parameters = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of recent commits to show"},
        },
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            count = args.get("count", 10)
            result = await sandbox.exec("", f"git log --oneline -{count}")
            return ToolResult(success=True, output=result.stdout or "No commits")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(Tool):
    name = "list_dir"
    description = "List the contents of a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the directory"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", f"ls -la {args['path']}")
            return ToolResult(success=True, output=result.stdout)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 10: Run test to verify it passes**

```bash
pytest tests/tools/test_tools.py -v
```

Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add harness/tools/ tests/tools/
git commit -m "feat: add tool system with registry and 9 built-in tools"
```

---

### Task 8: Context Builder

**Files:**
- Create: `harness/core/context.py`
- Test: `tests/core/test_context.py`

**Interfaces:**
- Consumes: `Sandbox` from `harness.sandbox.base`
- Produces: `build_context(sandbox: Sandbox, task: TaskConfig) -> str` async function

- [ ] **Step 1: Write failing test**

```python
# tests/core/test_context.py
import pytest
from harness.core.context import build_context
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
from harness.sandbox.base import ExecResult


class FakeContextSandbox:
    async def exec(self, container_id, command, workdir=None):
        if "find" in command and "-type f" in command:
            return ExecResult(exit_code=0, stdout="src/main.py\nsrc/utils.py\ntests/test_main.py\n", stderr="")
        if "git log" in command:
            return ExecResult(exit_code=0, stdout="abc1234 Fix login bug\ndef5678 Add feature X\n", stderr="")
        if "tree" in command:
            return ExecResult(exit_code=0, stdout="src/\n  main.py\n  utils.py\ntests/\n  test_main.py\n", stderr="")
        return ExecResult(exit_code=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_build_context_includes_repo_summary():
    task = TaskConfig(
        id="bug-001",
        name="test",
        description="Fix the login bug in auth module",
        repo="https://github.com/test/repo",
        branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    sandbox = FakeContextSandbox()
    context = await build_context(sandbox, task)

    assert "Fix the login bug in auth module" in context
    assert "src/main.py" in context
    assert "src/utils.py" in context
    assert "abc1234" in context
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_context.py -v
```

Expected: FAIL

- [ ] **Step 3: Write context.py**

```python
# harness/core/context.py
from harness.core.task import TaskConfig
from harness.sandbox.base import Sandbox


async def build_context(sandbox: Sandbox, task: TaskConfig) -> str:
    parts = []

    result = await sandbox.exec("", f"find . -type f -not -path './.git/*' | head -100")
    file_list = result.stdout.strip()

    result = await sandbox.exec("", "git log --oneline -5")
    recent_commits = result.stdout.strip()

    parts.append("## Repository Structure")
    parts.append("```")
    if file_list:
        parts.append(file_list)
    else:
        parts.append("(empty repository)")
    parts.append("```")

    if recent_commits:
        parts.append("\n## Recent Commits")
        parts.append("```")
        parts.append(recent_commits)
        parts.append("```")

    parts.append(f"\n## Task")
    parts.append(f"**Title:** {task.name}")
    parts.append(f"**Description:** {task.description}")
    parts.append(f"**Repository:** {task.repo}")
    parts.append(f"**Branch:** {task.branch}")

    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_context.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/context.py tests/core/test_context.py
git commit -m "feat: add repository context builder for agent prompts"
```

---

### Task 9: AgentLoop

**Files:**
- Create: `harness/core/agent_loop.py`
- Test: `tests/core/test_agent_loop.py`

**Interfaces:**
- Consumes: `BaseAdapter` from `harness.adapters.base`, `ToolRegistry` from `harness.tools.registry`, `Sandbox` from `harness.sandbox.base`, `CommandGuard` from `harness.sandbox.guard`, `Observer` from `harness.observer.base`, `TaskConfig`, `AgentConfig` from `harness.core.task`, `build_context` from `harness.core.context`
- Produces:
  - `LoopResult` dataclass: `status: str`, `diff: str`, `turns: int`, `tokens_used: int`, `messages: list[dict]`, `tool_calls: list[dict]`, `error: Optional[str]`
  - `AgentLoop` class with `async run(task: TaskConfig, container_id: str) -> LoopResult`

- [ ] **Step 1: Write failing test**

```python
# tests/core/test_agent_loop.py
import pytest
from harness.core.agent_loop import AgentLoop, LoopResult
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
from harness.adapters.base import BaseAdapter, AdapterResponse, TokenUsage
from harness.tools.registry import ToolRegistry, Tool, ToolResult
from harness.sandbox.base import Sandbox, ExecResult
from harness.sandbox.guard import CommandGuard
from harness.observer.base import Observer


class FakeAdapter(BaseAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools):
        if self.call_count >= len(self.responses):
            return AdapterResponse(content="Done", finish_reason="stop", usage=TokenUsage(total_tokens=100))
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class FakeSandbox(Sandbox):
    async def create(self, image, workdir, repo_path):
        return "fake-container"

    async def exec(self, container_id, command, workdir=None):
        if "git diff" in command:
            return ExecResult(exit_code=0, stdout="diff --git a/file.py b/file.py\n+fixed", stderr="")
        return ExecResult(exit_code=0, stdout="ok", stderr="")

    async def read_file(self, container_id, path):
        return "file content"

    async def write_file(self, container_id, path, content):
        pass

    async def setup(self, container_id, commands):
        pass

    async def stop(self, container_id):
        pass


class FakeEchoTool(Tool):
    name = "echo"
    description = "Echo a message"
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    async def execute(self, args, sandbox):
        return ToolResult(success=True, output=args["message"])


@pytest.mark.asyncio
async def test_agent_loop_completes_with_text_response():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    adapter = FakeAdapter([
        AdapterResponse(content="I've fixed the bug", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
    ])
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert isinstance(result, LoopResult)
    assert result.status == "done"
    assert result.turns == 1
    assert result.diff == "diff --git a/file.py b/file.py\n+fixed"


@pytest.mark.asyncio
async def test_agent_loop_with_tool_calls():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    adapter = FakeAdapter([
        AdapterResponse(
            content=None,
            tool_calls=[type("TC", (), {"id": "1", "function": type("F", (), {"name": "echo", "arguments": '{"message": "hello"}'})()})()],
            finish_reason="tool_calls",
            usage=TokenUsage(total_tokens=50),
        ),
        AdapterResponse(content="Task complete", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
    ])
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert result.status == "done"
    assert result.turns == 2
    assert len(result.tool_calls) == 1


@pytest.mark.asyncio
async def test_agent_loop_hits_max_turns():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=2, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    responses = []
    for _ in range(10):
        responses.append(AdapterResponse(
            content=None,
            tool_calls=[type("TC", (), {"id": "1", "function": type("F", (), {"name": "echo", "arguments": '{"message": "x"}'})()})()],
            finish_reason="tool_calls",
            usage=TokenUsage(total_tokens=10),
        ))

    adapter = FakeAdapter(responses)
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert result.status == "failed"
    assert "max turns" in (result.error or "").lower() or "turns" in (result.error or "").lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_agent_loop.py -v
```

Expected: FAIL

- [ ] **Step 3: Write agent_loop.py**

```python
# harness/core/agent_loop.py
import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from harness.core.task import TaskConfig, AgentConfig
from harness.core.context import build_context
from harness.adapters.base import BaseAdapter, AdapterResponse
from harness.tools.registry import ToolRegistry, ToolResult
from harness.sandbox.base import Sandbox
from harness.sandbox.guard import CommandGuard, GuardBlockedError
from harness.observer.base import (
    Observer, TurnStart, ToolCallStart, ToolCallEnd,
    AgentThinking, LoopError, LoopComplete, SandboxEvent,
)


@dataclass
class LoopResult:
    status: str
    diff: str
    turns: int
    tokens_used: int
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    error: Optional[str] = None


SYSTEM_PROMPT = """You are an expert software engineer tasked with fixing bugs in a codebase.

You have access to tools that let you read, write, and edit files, search code, run shell commands, and inspect git history.

Workflow:
1. Understand the bug by reading relevant files and searching the codebase
2. Identify the root cause
3. Implement the fix by editing the affected files
4. Verify your fix works (run tests if available)
5. When done, provide a summary of what you changed and why

Be thorough and precise. Make minimal changes to fix the bug."""


class AgentLoop:
    def __init__(
        self,
        adapter: BaseAdapter,
        tools: ToolRegistry,
        sandbox: Sandbox,
        guard: CommandGuard,
        observer: Observer,
        config: AgentConfig,
        container_id: str,
    ):
        self.adapter = adapter
        self.tools = tools
        self.sandbox = sandbox
        self.guard = guard
        self.observer = observer
        self.config = config
        self.container_id = container_id

    async def run(self, task: TaskConfig) -> LoopResult:
        observer.emit(SandboxEvent(message="Building repository context..."))

        context = await build_context(self.sandbox, task)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        tool_schemas = self.tools.to_openai_schema()
        all_tool_calls = []
        total_tokens = 0
        turn = 0

        try:
            while turn < self.config.max_turns:
                turn += 1
                self.observer.emit(TurnStart(turn_number=turn))

                response = await self.adapter.chat(messages, tool_schemas)
                if response.usage:
                    total_tokens += response.usage.total_tokens

                if response.content:
                    self.observer.emit(AgentThinking(content=response.content))

                message = {"role": "assistant", "content": response.content}

                if response.tool_calls:
                    tool_call_blocks = []
                    for tc in response.tool_calls:
                        tool_call_blocks.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        })
                    message["tool_calls"] = tool_call_blocks

                messages.append(message)

                if not response.tool_calls:
                    break

                tool_results = []
                for tc in response.tool_calls:
                    self.observer.emit(ToolCallStart(tool_name=tc.name, args=tc.arguments))

                    try:
                        self.guard.check(tc.name, tc.arguments)
                    except GuardBlockedError as e:
                        result = ToolResult(success=False, output="", error=str(e))
                        self.observer.emit(ToolCallEnd(tool_name=tc.name, result=str(e), duration=0))
                        tool_results.append({"tool_call_id": tc.id, "role": "tool", "content": str(e)})
                        all_tool_calls.append({"turn": turn, "tool": tc.name, "args": tc.arguments, "result": str(e), "success": False})
                        continue

                    t0 = time.monotonic()
                    tool = self.tools.get(tc.name)
                    if tool is None:
                        err = f"Unknown tool: {tc.name}"
                        result = ToolResult(success=False, output="", error=err)
                    else:
                        result = await tool.execute(tc.arguments, self.sandbox)

                    duration = time.monotonic() - t0
                    self.observer.emit(ToolCallEnd(tool_name=tc.name, result=result.output or result.error or "", duration=duration))

                    tool_results.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": result.output if result.success else f"Error: {result.error}",
                    })
                    all_tool_calls.append({
                        "turn": turn, "tool": tc.name, "args": tc.arguments,
                        "result": result.output or result.error, "success": result.success,
                    })

                messages.extend(tool_results)

            diff = ""
            try:
                diff_result = await self.sandbox.exec(self.container_id, "git diff")
                diff = diff_result.stdout
            except Exception:
                pass

            if turn >= self.config.max_turns and not response.content:
                return LoopResult(
                    status="failed",
                    diff=diff,
                    turns=turn,
                    tokens_used=total_tokens,
                    messages=messages,
                    tool_calls=all_tool_calls,
                    error=f"Reached max turns ({self.config.max_turns}) without completing",
                )

            self.observer.emit(LoopComplete(status="done", turns=turn, tokens_used=total_tokens))

            return LoopResult(
                status="done",
                diff=diff,
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
            )

        except asyncio.CancelledError:
            self.observer.emit(LoopError(error="Task cancelled by user"))
            return LoopResult(
                status="cancelled",
                diff=(await self._safe_diff()),
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
                error="Cancelled by user",
            )
        except Exception as e:
            self.observer.emit(LoopError(error=str(e)))
            return LoopResult(
                status="failed",
                diff=(await self._safe_diff()),
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
                error=str(e),
            )

    async def _safe_diff(self) -> str:
        try:
            result = await self.sandbox.exec(self.container_id, "git diff")
            return result.stdout
        except Exception:
            return ""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_agent_loop.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/agent_loop.py tests/core/test_agent_loop.py
git commit -m "feat: add AgentLoop core engine with tool-calling cycle"
```

---

### Task 10: TaskManager

**Files:**
- Create: `harness/core/task_manager.py`
- Test: `tests/core/test_task_manager.py`

**Interfaces:**
- Consumes: `TaskConfig`, `TaskStatus` from `harness.core.task`, `TaskStore` from `harness.storage.db`, `FileStore` from `harness.storage.files`, `Sandbox` from `harness.sandbox.base`, `DockerSandbox` from `harness.sandbox.docker`, `CommandGuard` from `harness.sandbox.guard`, `AgentLoop`, `LoopResult` from `harness.core.agent_loop`, `BaseAdapter` from `harness.adapters.base`, `ToolRegistry` from `harness.tools.registry`, `Observer` from `harness.observer.base`
- Produces:
  - `TaskManager` class with `async run(task: TaskConfig, task_file: str) -> LoopResult`, `cancel(task_id: str)`, `get_status(task_id: str) -> Optional[dict]`, `list_all(status: Optional[str] = None) -> list[dict]`

- [ ] **Step 1: Write failing test**

```python
# tests/core/test_task_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from harness.core.task_manager import TaskManager
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig, TaskStatus
from harness.core.agent_loop import LoopResult
from harness.adapters.base import BaseAdapter
from harness.tools.registry import ToolRegistry
from harness.sandbox.docker import DockerSandbox
from harness.sandbox.guard import CommandGuard
from harness.observer.base import Observer
from harness.storage.db import TaskStore
from harness.storage.files import FileStore


def make_task(**kwargs):
    defaults = {
        "id": "bug-001", "name": "test", "description": "fix it",
        "repo": "https://github.com/test/repo", "branch": "main",
        "environment": EnvironmentConfig(image="python:3.11", setup_commands=[]),
        "agent": AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        "sandbox": SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    }
    defaults.update(kwargs)
    return TaskConfig(**defaults)


@pytest.mark.asyncio
async def test_task_manager_run_flow(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    observer = Observer()

    manager = TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=str(temp_dir),
    )

    task = make_task()

    with patch("harness.core.task_manager.git") as mock_git:
        with patch("harness.core.task_manager.DockerSandbox") as MockSandboxClass:
            mock_sandbox = AsyncMock()
            MockSandboxClass.return_value = mock_sandbox
            mock_sandbox.create.return_value = "fake-container"

            mock_adapter = AsyncMock()
            mock_registry = ToolRegistry()
            mock_guard = CommandGuard(blocked_patterns=[])

            mock_loop_result = LoopResult(status="done", diff="fake diff", turns=1, tokens_used=100, messages=[], tool_calls=[])
            mock_loop = AsyncMock()
            mock_loop.run.return_value = mock_loop_result

            with patch("harness.core.task_manager.AgentLoop", return_value=mock_loop):
                with patch("harness.core.task_manager.OpenAIAdapter", return_value=mock_adapter):
                    result = await manager.run(task, "tasks/bug-001.yaml")

    assert result.status == "done"
    assert result.diff == "fake diff"

    record = store.get("bug-001")
    assert record["status"] == "done"
    assert record["turns"] == 1


@pytest.mark.asyncio
async def test_task_manager_get_status(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    observer = Observer()

    manager = TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=str(temp_dir),
    )

    task = make_task()
    store.create(task, "tasks/bug-001.yaml")

    status = manager.get_status("bug-001")
    assert status["status"] == "pending"


def test_task_manager_list_all(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    observer = Observer()

    manager = TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=str(temp_dir),
    )

    store.create(make_task(id="bug-001"), "tasks/bug-001.yaml")
    store.create(make_task(id="bug-002"), "tasks/bug-002.yaml")

    tasks = manager.list_all()
    assert len(tasks) == 2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_task_manager.py -v
```

Expected: FAIL

- [ ] **Step 3: Write task_manager.py**

```python
# harness/core/task_manager.py
import os
import tempfile
import docker
import git
from harness.core.task import TaskConfig, TaskStatus
from harness.core.agent_loop import AgentLoop, LoopResult
from harness.adapters.openai import OpenAIAdapter
from harness.tools.registry import ToolRegistry
from harness.tools.files import ReadFileTool, WriteFileTool, EditFileTool
from harness.tools.shell import RunShellTool
from harness.tools.search import SearchContentTool, SearchFilesTool
from harness.tools.git import GitDiffTool, GitLogTool, ListDirTool
from harness.sandbox.docker import DockerSandbox
from harness.sandbox.guard import CommandGuard
from harness.observer.base import Observer
from harness.storage.db import TaskStore
from harness.storage.files import FileStore


class TaskManager:
    def __init__(
        self,
        task_store: TaskStore,
        file_store: FileStore,
        observer: Observer,
        data_dir: str,
        api_key: str = None,
    ):
        self.task_store = task_store
        self.file_store = file_store
        self.observer = observer
        self.data_dir = data_dir
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    async def run(self, task: TaskConfig, task_file: str) -> LoopResult:
        self.task_store.create(task, task_file)
        self.task_store.update_status(task.id, TaskStatus.RUNNING)

        sandbox = None
        container_id = None
        repo_dir = None

        try:
            docker_client = docker.from_env()
            sandbox = DockerSandbox(docker_client)

            repo_dir = tempfile.mkdtemp(prefix="harness_repo_")
            git.Repo.clone_from(task.repo, repo_dir, branch=task.branch)

            container_id = await sandbox.create(
                image=task.environment.image,
                workdir=task.sandbox.workdir,
                repo_path=repo_dir,
            )

            if task.environment.setup_commands:
                await sandbox.setup(container_id, task.environment.setup_commands)

            adapter = OpenAIAdapter(
                model=task.agent.model,
                api_key=self.api_key,
                temperature=task.agent.temperature,
            )

            tools = ToolRegistry()
            tools.register(ReadFileTool())
            tools.register(WriteFileTool())
            tools.register(EditFileTool())
            tools.register(RunShellTool())
            tools.register(SearchContentTool())
            tools.register(SearchFilesTool())
            tools.register(GitDiffTool())
            tools.register(GitLogTool())
            tools.register(ListDirTool())

            guard = CommandGuard(blocked_patterns=task.sandbox.blocked_commands)

            loop = AgentLoop(
                adapter=adapter,
                tools=tools,
                sandbox=sandbox,
                guard=guard,
                observer=self.observer,
                config=task.agent,
                container_id=container_id,
            )

            result = await loop.run(task)

            self.task_store.update_result(
                task.id,
                turns=result.turns,
                tokens_used=result.tokens_used,
                error=result.error,
            )
            self.task_store.update_status(
                task.id,
                TaskStatus.DONE if result.status == "done" else TaskStatus.FAILED,
            )

            self.file_store.save_messages(task.id, result.messages)
            self.file_store.save_tool_calls(task.id, result.tool_calls)
            self.file_store.save_diff(task.id, result.diff)

            return result

        except Exception as e:
            self.task_store.update_result(task.id, turns=0, tokens_used=0, error=str(e))
            self.task_store.update_status(task.id, TaskStatus.FAILED)
            return LoopResult(
                status="failed",
                diff="",
                turns=0,
                tokens_used=0,
                messages=[],
                tool_calls=[],
                error=str(e),
            )
        finally:
            if sandbox and container_id:
                try:
                    await sandbox.stop(container_id)
                except Exception:
                    pass
            if repo_dir:
                import shutil
                shutil.rmtree(repo_dir, ignore_errors=True)

    def cancel(self, task_id: str):
        self.task_store.update_status(task_id, TaskStatus.CANCELLED)

    def get_status(self, task_id: str):
        return self.task_store.get(task_id)

    def list_all(self, status: str = None):
        return self.task_store.list_all(status=status)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_task_manager.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/task_manager.py tests/core/test_task_manager.py
git commit -m "feat: add TaskManager for full task lifecycle orchestration"
```

---

### Task 11: Report Generator

**Files:**
- Create: `harness/report/generator.py`
- Test: `tests/report/test_generator.py`

**Interfaces:**
- Consumes: `TaskStore` from `harness.storage.db`, `FileStore` from `harness.storage.files`
- Produces:
  - `ReportGenerator` class with `generate(task_id: str) -> dict`, `format_summary(task_id: str) -> str`, `format_verbose(task_id: str) -> str`, `format_json(task_id: str) -> str`

- [ ] **Step 1: Write failing test**

```python
# tests/report/test_generator.py
import pytest
from harness.report.generator import ReportGenerator
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig


def make_task(**kwargs):
    defaults = {
        "id": "bug-001", "name": "test bug", "description": "fix it",
        "repo": "https://github.com/test/repo", "branch": "main",
        "environment": EnvironmentConfig(image="python:3.11", setup_commands=[]),
        "agent": AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        "sandbox": SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    }
    defaults.update(kwargs)
    return TaskConfig(**defaults)


def test_generate_summary(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    task = make_task()
    store.create(task, "tasks/bug-001.yaml")
    store.update_result("bug-001", turns=3, tokens_used=1500)
    file_store.save_diff("bug-001", "diff --git a/file.py b/file.py\n+fix")

    report = gen.generate("bug-001")
    assert report["id"] == "bug-001"
    assert report["turns"] == 3
    assert report["tokens_used"] == 1500
    assert "diff --git" in report["diff"]


def test_format_summary(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    task = make_task()
    store.create(task, "tasks/bug-001.yaml")
    store.update_result("bug-001", turns=3, tokens_used=1500)
    file_store.save_diff("bug-001", "+fixed line")

    text = gen.format_summary("bug-001")
    assert "bug-001" in text
    assert "test bug" in text
    assert "3 turns" in text
    assert "1500" in text


def test_format_json(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    task = make_task()
    store.create(task, "tasks/bug-001.yaml")
    store.update_result("bug-001", turns=3, tokens_used=1500)

    import json
    data = json.loads(gen.format_json("bug-001"))
    assert data["id"] == "bug-001"
    assert data["turns"] == 3


def test_generate_nonexistent_raises(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    with pytest.raises(ValueError, match="not found"):
        gen.generate("nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/report/test_generator.py -v
```

Expected: FAIL

- [ ] **Step 3: Write generator.py**

```python
# harness/report/generator.py
import json
from harness.storage.db import TaskStore
from harness.storage.files import FileStore


class ReportGenerator:
    def __init__(self, task_store: TaskStore, file_store: FileStore):
        self.task_store = task_store
        self.file_store = file_store

    def generate(self, task_id: str) -> dict:
        record = self.task_store.get(task_id)
        if record is None:
            raise ValueError(f"Task {task_id} not found")

        diff = self.file_store.load_diff(task_id)
        messages = self.file_store.load_messages(task_id)

        return {
            "id": record["id"],
            "name": record["name"],
            "status": record["status"],
            "repo": record["repo"],
            "branch": record["branch"],
            "model": record["model"],
            "created_at": record["created_at"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "turns": record["turns"],
            "tokens_used": record["tokens_used"],
            "error": record["error"],
            "diff": diff,
            "messages": messages,
        }

    def format_summary(self, task_id: str) -> str:
        report = self.generate(task_id)
        lines = [
            f"Task: {report['id']} - {report['name']}",
            f"Status: {report['status']}",
            f"Agent: {report['model']}",
            f"Turns: {report['turns']}",
            f"Tokens: {report['tokens_used']}",
            f"Repo: {report['repo']} ({report['branch']})",
            "",
        ]
        if report["diff"]:
            lines.append("Diff:")
            lines.append(report["diff"])
        if report["error"]:
            lines.append(f"Error: {report['error']}")
        return "\n".join(lines)

    def format_verbose(self, task_id: str) -> str:
        report = self.generate(task_id)
        text = self.format_summary(task_id)
        text += "\n\n--- Messages ---\n\n"
        for msg in report.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                text += f"[{role}]: {content[:500]}\n\n"
        return text

    def format_json(self, task_id: str) -> str:
        report = self.generate(task_id)
        return json.dumps(report, ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/report/test_generator.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/report/generator.py tests/report/test_generator.py
git commit -m "feat: add report generator with summary, verbose, and JSON formats"
```

---

### Task 12: CLI

**Files:**
- Create: `harness/cli/main.py`
- Create: `harness/cli/formatters.py`
- Test: `tests/cli/test_cli.py`

**Interfaces:**
- Consumes: `TaskManager` from `harness.core.task_manager`, `ReportGenerator` from `harness.report.generator`, `load_task_config` from `harness.core.task`, `TaskStore` from `harness.storage.db`, `FileStore` from `harness.storage.files`, `Observer` from `harness.observer.base`, `StreamObserver` from `harness.observer.stream`, `LogObserver` from `harness.observer.logger`
- Produces: `cli` Click group with commands: `run`, `status`, `report`, `list`, `cancel`, `config`

- [ ] **Step 1: Write failing test**

```python
# tests/cli/test_cli.py
import pytest
from click.testing import CliRunner
from harness.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.output
    assert "status" in result.output
    assert "report" in result.output
    assert "list" in result.output
    assert "cancel" in result.output
    assert "config" in result.output


def test_run_missing_task_file(runner):
    result = runner.invoke(cli, ["run", "nonexistent.yaml"])
    assert result.exit_code != 0


def test_status_no_args(runner, temp_dir):
    result = runner.invoke(cli, ["status", "--data-dir", str(temp_dir)])
    assert result.exit_code == 0


def test_list_no_args(runner, temp_dir):
    result = runner.invoke(cli, ["list", "--data-dir", str(temp_dir)])
    assert result.exit_code == 0


def test_config(runner):
    result = runner.invoke(cli, ["config"])
    assert result.exit_code == 0
    assert "model" in result.output.lower() or "gpt" in result.output.lower() or "config" in result.output.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/cli/test_cli.py -v
```

Expected: FAIL

- [ ] **Step 3: Write formatters.py**

```python
# harness/cli/formatters.py
def format_status_table(tasks: list[dict]) -> str:
    if not tasks:
        return "No tasks found."

    lines = [f"{'ID':<20} {'Name':<30} {'Status':<12} {'Turns':<8} {'Tokens':<10}"]
    lines.append("-" * 80)
    for t in tasks:
        lines.append(
            f"{t['id']:<20} {t['name'][:28]:<30} {t['status']:<12} "
            f"{str(t['turns'] or '-'):<8} {str(t['tokens_used'] or '-'):<10}"
        )
    return "\n".join(lines)


def format_task_detail(task: dict) -> str:
    if task is None:
        return "Task not found."

    lines = [
        f"ID:          {task['id']}",
        f"Name:        {task['name']}",
        f"Status:      {task['status']}",
        f"Repo:        {task['repo']}",
        f"Branch:      {task['branch']}",
        f"Model:       {task['model']}",
        f"Created:     {task['created_at']}",
        f"Started:     {task['started_at'] or '-'}",
        f"Finished:    {task['finished_at'] or '-'}",
        f"Turns:       {task['turns'] or '-'}",
        f"Tokens:      {task['tokens_used'] or '-'}",
    ]
    if task.get("error"):
        lines.append(f"Error:       {task['error']}")
    return "\n".join(lines)
```

- [ ] **Step 4: Write main.py**

```python
# harness/cli/main.py
import os
import asyncio
import click
import yaml
from harness.core.task import load_task_config
from harness.core.task_manager import TaskManager
from harness.report.generator import ReportGenerator
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.observer.base import Observer
from harness.observer.stream import StreamObserver
from harness.observer.logger import LogObserver
from harness.cli.formatters import format_status_table, format_task_detail


def load_config():
    config_paths = ["config.yaml", "harness.yaml"]
    config = {}
    for p in config_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                config.update(loaded)
    return config


def resolve_api_key(config):
    key = config.get("api", {}).get("openai_api_key", "")
    if key.startswith("${") and key.endswith("}"):
        env_var = key[2:-1]
        return os.environ.get(env_var, "")
    return key or os.environ.get("OPENAI_API_KEY", "")


def get_data_dir(config, cli_data_dir):
    if cli_data_dir:
        return cli_data_dir
    return config.get("storage", {}).get("data_dir", "./data")


def make_manager(data_dir, api_key, observer):
    store = TaskStore(data_dir)
    file_store = FileStore(data_dir)
    return TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=data_dir,
        api_key=api_key,
    )


def make_report_gen(data_dir):
    store = TaskStore(data_dir)
    file_store = FileStore(data_dir)
    return ReportGenerator(store, file_store)


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.argument("task_file", type=click.Path(exists=True))
@click.option("--verbose", is_flag=True, help="Stream agent output in real-time")
@click.option("--no-stream", is_flag=True, help="Suppress real-time streaming")
@click.option("--data-dir", default=None, help="Override data directory")
def run(task_file, verbose, no_stream, data_dir):
    """Execute a bug-fixing task from a YAML file."""
    config = load_config()
    api_key = resolve_api_key(config)
    ddir = get_data_dir(config, data_dir)

    if not api_key:
        click.echo("Error: OPENAI_API_KEY not set. Set it via config.yaml or environment variable.", err=True)
        raise SystemExit(1)

    observer = Observer()
    if not no_stream:
        observer.subscribe(StreamObserver())

    log_path = os.path.join(ddir, "harness.log")
    os.makedirs(ddir, exist_ok=True)
    observer.subscribe(LogObserver(log_path))

    manager = make_manager(ddir, api_key, observer)

    task = load_task_config(task_file)

    click.echo(f"Starting task: {task.id} - {task.name}")
    click.echo(f"Agent: {task.agent.model} | Max turns: {task.agent.max_turns}")
    click.echo(f"Repo: {task.repo} ({task.branch})")

    result = asyncio.run(manager.run(task, task_file))

    click.echo(f"\nTask {result.status} in {result.turns} turns, {result.tokens_used} tokens")
    if result.diff:
        click.echo("\nDiff:")
        click.echo(result.diff)
    if result.error:
        click.echo(f"\nError: {result.error}")


@cli.command()
@click.argument("task_id", required=False)
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--data-dir", default=None, help="Override data directory")
def status(task_id, filter_status, as_json, data_dir):
    """View task status."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    if task_id:
        task = store.get(task_id)
        if task is None:
            click.echo(f"Task '{task_id}' not found.")
            return
        if as_json:
            import json
            click.echo(json.dumps(task, indent=2, default=str))
        else:
            click.echo(format_task_detail(task))
    else:
        tasks = store.list_all(status=filter_status)
        if as_json:
            import json
            click.echo(json.dumps(tasks, indent=2, default=str))
        else:
            click.echo(format_status_table(tasks))


@cli.command()
@click.argument("task_id")
@click.option("--verbose", "show_verbose", is_flag=True, help="Show detailed report with messages")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--diff", "show_diff", is_flag=True, help="Show only the diff")
@click.option("--data-dir", default=None, help="Override data directory")
def report(task_id, show_verbose, as_json, show_diff, data_dir):
    """Generate a task report."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    gen = make_report_gen(ddir)

    try:
        if as_json:
            click.echo(gen.format_json(task_id))
        elif show_diff:
            data = gen.generate(task_id)
            click.echo(data["diff"] or "(no diff)")
        elif show_verbose:
            click.echo(gen.format_verbose(task_id))
        else:
            click.echo(gen.format_summary(task_id))
    except ValueError as e:
        click.echo(str(e), err=True)


@cli.command()
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--limit", default=None, type=int, help="Limit number of results")
@click.option("--data-dir", default=None, help="Override data directory")
def list(filter_status, limit, data_dir):
    """List all tasks."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    tasks = store.list_all(status=filter_status)
    if limit:
        tasks = tasks[:limit]
    click.echo(format_status_table(tasks))


@cli.command()
@click.argument("task_id")
@click.option("--data-dir", default=None, help="Override data directory")
def cancel(task_id, data_dir):
    """Cancel a running task."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    task = store.get(task_id)
    if task is None:
        click.echo(f"Task '{task_id}' not found.")
        return
    if task["status"] != "running":
        click.echo(f"Task '{task_id}' is not running (status: {task['status']}).")
        return

    from harness.core.task import TaskStatus
    store.update_status(task_id, TaskStatus.CANCELLED)
    click.echo(f"Task '{task_id}' cancelled.")


@cli.command()
@click.option("--path", "show_path", is_flag=True, help="Show config file path only")
def config(show_path):
    """Show current configuration."""
    config_paths = ["config.yaml", "harness.yaml"]
    found = None
    for p in config_paths:
        if os.path.exists(p):
            found = os.path.abspath(p)
            break

    if show_path:
        if found:
            click.echo(found)
        else:
            click.echo("No config file found (searched: config.yaml, harness.yaml)")
        return

    if found:
        click.echo(f"Config file: {found}\n")
        with open(found, "r", encoding="utf-8") as f:
            click.echo(f.read())
    else:
        click.echo("No config file found (searched: config.yaml, harness.yaml)")
        click.echo("\nDefault config:")
        click.echo("""
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "${OPENAI_API_KEY}"

logging:
  level: "INFO"
  file: "harness.log"
""")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 5: Run test to verify it passes**

```bash
pytest tests/cli/test_cli.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add harness/cli/ tests/cli/
git commit -m "feat: add CLI with run, status, report, list, cancel, config commands"
```

---

### Task 13: Integration Test

**Files:**
- Create: `tests/integration/test_full_flow.py`
- Create: `tasks/example-bug.yaml`

**Interfaces:**
- Consumes: all modules
- Produces: integration test that exercises the full flow

- [ ] **Step 1: Create example task file**

```yaml
# tasks/example-bug.yaml
id: "example-bug"
name: "Example Bug Fix"
description: |
  This is an example bug fix task.
  The repository contains a simple Python project with a bug.
repo: "https://github.com/example/demo-repo"
branch: "main"

environment:
  image: "python:3.11-alpine"
  setup_commands:
    - "echo 'setup complete'"

agent:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 600
  blocked_commands: []

verification:
  commands:
    - "pytest tests/"
```

- [ ] **Step 2: Write integration test**

```python
# tests/integration/test_full_flow.py
import pytest
import os
import yaml
from harness.core.task import load_task_config
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.report.generator import ReportGenerator


def test_load_example_task():
    task_path = os.path.join(os.path.dirname(__file__), "..", "..", "tasks", "example-bug.yaml")
    if not os.path.exists(task_path):
        pytest.skip("example-bug.yaml not found")

    config = load_task_config(task_path)
    assert config.id == "example-bug"
    assert config.name == "Example Bug Fix"
    assert config.agent.model == "gpt-4o"
    assert config.environment.image == "python:3.11-alpine"


def test_full_storage_flow(temp_dir):
    """Test that storage, task creation, and report generation work together."""
    from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig

    task = TaskConfig(
        id="flow-test",
        name="Flow Test",
        description="Testing full flow",
        repo="https://github.com/test/repo",
        branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))

    store.create(task, "tasks/flow-test.yaml")
    assert store.get("flow-test") is not None

    from harness.core.task import TaskStatus
    store.update_status("flow-test", TaskStatus.DONE)
    store.update_result("flow-test", turns=5, tokens_used=2000)

    file_store.save_diff("flow-test", "+fixed bug")
    file_store.save_messages("flow-test", [{"role": "user", "content": "fix it"}])

    gen = ReportGenerator(store, file_store)
    report = gen.generate("flow-test")

    assert report["status"] == "done"
    assert report["turns"] == 5
    assert "+fixed bug" in report["diff"]
    assert len(report["messages"]) == 1
```

- [ ] **Step 3: Run integration test**

```bash
pytest tests/integration/test_full_flow.py -v
```

Expected: PASS

- [ ] **Step 4: Run all tests**

```bash
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/integration/ tasks/example-bug.yaml
git commit -m "test: add integration test and example task file"
```

---

## Plan Summary

| Task | Component | Dependencies |
|------|-----------|-------------|
| 1 | Project Scaffolding | none |
| 2 | Task Model | none |
| 3 | Storage Layer | Task Model |
| 4 | Sandbox Layer | none |
| 5 | Adapter Layer | none |
| 6 | Observer Layer | none |
| 7 | Tool System | Sandbox |
| 8 | Context Builder | Sandbox, Task Model |
| 9 | AgentLoop | Adapter, Tools, Sandbox, Guard, Observer, Task Model, Context |
| 10 | TaskManager | AgentLoop, Storage, Sandbox, Adapter, Tools, Guard, Observer |
| 11 | Report Generator | Storage |
| 12 | CLI | TaskManager, Report Generator, Task Model, Storage, Observer |
| 13 | Integration Test | all |