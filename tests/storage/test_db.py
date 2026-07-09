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