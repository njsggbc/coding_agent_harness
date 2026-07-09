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
        with patch("harness.core.task_manager.docker") as mock_docker:
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