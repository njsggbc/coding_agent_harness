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

