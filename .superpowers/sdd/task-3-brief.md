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

