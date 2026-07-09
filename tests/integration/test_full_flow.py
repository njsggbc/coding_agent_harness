import pytest
import os
from harness.core.task import load_task_config, TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig, TaskStatus
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
    assert config.agent.max_turns == 30
    assert config.agent.temperature == 0.0
    assert config.sandbox.workdir == "/workspace"
    assert config.sandbox.timeout == 600
    assert config.verification is not None
    assert config.verification.commands == ["pytest tests/"]


def test_full_storage_flow(temp_dir):
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

    store.update_status("flow-test", TaskStatus.RUNNING)
    record = store.get("flow-test")
    assert record["status"] == "running"

    store.update_status("flow-test", TaskStatus.DONE)
    store.update_result("flow-test", turns=5, tokens_used=2000)

    file_store.save_diff("flow-test", "+fixed bug")
    file_store.save_messages("flow-test", [{"role": "user", "content": "fix it"}])

    gen = ReportGenerator(store, file_store)
    report = gen.generate("flow-test")

    assert report["status"] == "done"
    assert report["turns"] == 5
    assert report["tokens_used"] == 2000
    assert "+fixed bug" in report["diff"]
    assert len(report["messages"]) == 1
    assert report["messages"][0]["role"] == "user"
    assert report["messages"][0]["content"] == "fix it"


def test_task_not_found_report(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)
    with pytest.raises(ValueError, match="Task nonexistent not found"):
        gen.generate("nonexistent")


def test_list_all_tasks(temp_dir):
    store = TaskStore(str(temp_dir))

    task_a = TaskConfig(
        id="task-a",
        name="Task A",
        description="First task",
        repo="https://github.com/test/repo",
        branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )
    task_b = TaskConfig(
        id="task-b",
        name="Task B",
        description="Second task",
        repo="https://github.com/test/repo",
        branch="dev",
        environment=EnvironmentConfig(image="python:3.12", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=20, temperature=0.5),
        sandbox=SandboxConfig(workdir="/ws", timeout=600, blocked_commands=[]),
    )

    store.create(task_a, "tasks/a.yaml")
    store.create(task_b, "tasks/b.yaml")

    all_tasks = store.list_all()
    assert len(all_tasks) == 2

    store.update_status("task-a", TaskStatus.DONE)
    done_tasks = store.list_all(status="done")
    assert len(done_tasks) == 1
    assert done_tasks[0]["id"] == "task-a"


def test_empty_messages_and_diff(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))

    task = TaskConfig(
        id="empty-test",
        name="Empty Test",
        description="Task with no messages or diff",
        repo="https://github.com/test/repo",
        branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    store.create(task, "tasks/empty-test.yaml")
    store.update_status("empty-test", TaskStatus.DONE)

    gen = ReportGenerator(store, file_store)
    report = gen.generate("empty-test")

    assert report["status"] == "done"
    assert report["diff"] == ""
    assert report["messages"] == []