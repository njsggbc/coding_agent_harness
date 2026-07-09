import pytest
import json
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

    data = json.loads(gen.format_json("bug-001"))
    assert data["id"] == "bug-001"
    assert data["turns"] == 3


def test_format_verbose(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    task = make_task()
    store.create(task, "tasks/bug-001.yaml")
    store.update_result("bug-001", turns=3, tokens_used=1500)
    file_store.save_messages("bug-001", [
        {"role": "user", "content": "fix the bug"},
        {"role": "assistant", "content": "done"},
    ])

    text = gen.format_verbose("bug-001")
    assert "bug-001" in text
    assert "--- Messages ---" in text
    assert "[user]: fix the bug" in text
    assert "[assistant]: done" in text


def test_generate_nonexistent_raises(temp_dir):
    store = TaskStore(str(temp_dir))
    file_store = FileStore(str(temp_dir))
    gen = ReportGenerator(store, file_store)

    with pytest.raises(ValueError, match="not found"):
        gen.generate("nonexistent")