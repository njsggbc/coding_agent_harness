import pytest
import json
from fastapi.testclient import TestClient
from harness.webui import create_app
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig, TaskStatus


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


@pytest.fixture
def client(temp_dir):
    app = create_app(str(temp_dir))
    return TestClient(app)


@pytest.fixture
def populated_store(temp_dir):
    store = TaskStore(str(temp_dir))
    for i in range(3):
        task = make_task_config(id=f"bug-{i:03d}", name=f"bug {i}")
        store.create(task, f"tasks/bug-{i:03d}.yaml")
    store.update_status("bug-000", TaskStatus.DONE)
    store.update_result("bug-000", turns=5, tokens_used=1000)
    store.update_status("bug-001", TaskStatus.RUNNING)
    file_store = FileStore(str(temp_dir))
    file_store.save_diff("bug-000", "diff --git a/file.py b/file.py\n+fix")
    file_store.save_messages("bug-000", [
        {"role": "user", "content": "fix the bug"},
        {"role": "assistant", "content": "done"},
    ])
    return store


class TestDashboard:
    def test_get_dashboard_returns_html(self, client, populated_store):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "Coding Agent Harness" in response.text

    def test_dashboard_shows_tasks(self, client, populated_store):
        response = client.get("/")
        assert "loadTasks" in response.text
        assert "taskTableBody" in response.text


class TestListTasks:
    def test_list_all_tasks(self, client, populated_store):
        response = client.get("/api/tasks")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["id"] == "bug-002"

    def test_list_tasks_filter_by_status(self, client, populated_store):
        response = client.get("/api/tasks?status=done")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "bug-000"

    def test_list_empty(self, client):
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []


class TestGetTask:
    def test_get_task_detail(self, client, populated_store):
        response = client.get("/api/tasks/bug-000")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "bug-000"
        assert data["name"] == "bug 0"
        assert data["status"] == "done"
        assert data["turns"] == 5

    def test_get_nonexistent_task(self, client):
        response = client.get("/api/tasks/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRunTask:
    def test_run_missing_task_file(self, client):
        response = client.post("/api/tasks/run", json={})
        assert response.status_code == 422

    def test_run_nonexistent_task_file(self, client):
        response = client.post("/api/tasks/run", json={"task_file": "nonexistent.yaml"})
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()

    def test_run_valid_task_file(self, client, temp_dir, populated_store):
        task_yaml = """
id: web-test
name: Web Test Task
description: Test from webui
repo: https://github.com/test/repo
branch: main
environment:
  image: python:3.11
agent:
  model: gpt-4o
  max_turns: 5
  temperature: 0.0
sandbox:
  workdir: /ws
  timeout: 60
"""
        task_path = temp_dir / "test_task.yaml"
        task_path.write_text(task_yaml)

        response = client.post("/api/tasks/run", json={"task_file": str(task_path)})
        assert response.status_code == 202
        data = response.json()
        assert data["task_id"] == "web-test"
        assert data["status"] == "accepted"


class TestTaskReport:
    def test_get_report(self, client, populated_store):
        response = client.get("/api/tasks/bug-000/report")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "bug-000"
        assert data["turns"] == 5
        assert "diff --git" in data["diff"]

    def test_report_nonexistent_task(self, client):
        response = client.get("/api/tasks/nonexistent/report")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestCancelTask:
    def test_cancel_task(self, client, populated_store):
        response = client.post("/api/tasks/bug-002/cancel")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        detail = client.get("/api/tasks/bug-002").json()
        assert detail["status"] == "cancelled"

    def test_cancel_nonexistent_task(self, client):
        response = client.post("/api/tasks/nonexistent/cancel")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()