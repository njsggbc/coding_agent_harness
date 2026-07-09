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
