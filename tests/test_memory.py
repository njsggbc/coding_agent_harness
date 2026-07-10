import pytest
import json
from pathlib import Path
from harness.memory import MemoryStore, MemoryEntry


class TestMemoryStore:
    def test_store_and_retrieve_memory(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        store.add(repo, "test_key", "test_value", "convention")
        entry = store.get(repo, "test_key")

        assert entry is not None
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.category == "convention"
        assert entry.timestamp is not None

    def test_memory_project_isolation(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo_a = "https://github.com/a/repo"
        repo_b = "https://github.com/b/repo"

        store.add(repo_a, "key", "value_a")
        store.add(repo_b, "key", "value_b")

        assert store.get(repo_a, "key").value == "value_a"
        assert store.get(repo_b, "key").value == "value_b"

        entries_a = store.get_all(repo_a)
        entries_b = store.get_all(repo_b)
        assert len(entries_a) == 1
        assert len(entries_b) == 1

    def test_memory_persists_across_instances(self, temp_dir):
        repo = "https://github.com/test/repo"

        store1 = MemoryStore(str(temp_dir))
        store1.add(repo, "persist_key", "persist_value", "knowledge")

        store2 = MemoryStore(str(temp_dir))
        entry = store2.get(repo, "persist_key")

        assert entry is not None
        assert entry.value == "persist_value"
        assert entry.category == "knowledge"

    def test_memory_injected_into_context(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        store.add(repo, "coding_style", "use tabs for indentation", "convention")
        store.add(repo, "test_framework", "pytest with fixtures", "knowledge")

        context = store.to_context_string(repo)

        assert "## Project Memory" in context
        assert "[convention] coding_style: use tabs for indentation" in context
        assert "[knowledge] test_framework: pytest with fixtures" in context

    def test_demo_memory_retrieval(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/demo/project"

        store.add(repo, "arch", "microservices with REST APIs", "decision")
        store.add(repo, "lint", "flake8 with max-line-length=100", "convention")
        store.add(repo, "git_flow", "squash-merge from feature branches", "convention")
        store.add(repo, "db_schema", "postgres 15, see docs/schema.sql", "knowledge")

        entries = store.get_all(repo)
        assert len(entries) == 4

        categories = {e.category for e in entries}
        assert "decision" in categories
        assert "convention" in categories
        assert "knowledge" in categories

        context = store.to_context_string(repo)
        assert "microservices with REST APIs" in context
        assert "flake8 with max-line-length=100" in context
        assert "squash-merge from feature branches" in context
        assert "postgres 15" in context

        store.remove(repo, "lint")
        entries = store.get_all(repo)
        assert len(entries) == 3

        store.clear(repo)
        entries = store.get_all(repo)
        assert len(entries) == 0

        context = store.to_context_string(repo)
        assert context == ""

    def test_list_projects(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo_a = "https://github.com/a/project"
        repo_b = "https://github.com/b/project"

        store.add(repo_a, "key", "value")
        store.add(repo_b, "key", "value")

        projects = store.list_projects()
        assert len(projects) == 2

        store.clear(repo_a)
        projects = store.list_projects()
        assert len(projects) == 1

    def test_add_updates_existing_key(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        store.add(repo, "key", "old_value", "note")
        store.add(repo, "key", "new_value", "convention")

        entry = store.get(repo, "key")
        assert entry.value == "new_value"
        assert entry.category == "convention"

        entries = store.get_all(repo)
        assert len(entries) == 1

    def test_get_nonexistent(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        entry = store.get(repo, "nonexistent")
        assert entry is None

        entries = store.get_all(repo)
        assert entries == []

    def test_to_context_string_empty(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        context = store.to_context_string(repo)
        assert context == ""

    def test_remove_nonexistent(self, temp_dir):
        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"

        store.remove(repo, "nonexistent")

        store.add(repo, "real", "value")
        assert store.get(repo, "real") is not None


class TestMemoryIntegration:
    @pytest.mark.asyncio
    async def test_memory_in_context_builder(self, temp_dir):
        from harness.core.context import build_context
        from harness.memory import MemoryStore
        from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
        from harness.sandbox.base import ExecResult

        class FakeContextSandbox:
            async def exec(self, container_id, command, workdir=None):
                if "find" in command and "-type f" in command:
                    return ExecResult(exit_code=0, stdout="src/main.py\n", stderr="")
                if "git log" in command:
                    return ExecResult(exit_code=0, stdout="abc1234 Fix\n", stderr="")
                return ExecResult(exit_code=0, stdout="", stderr="")

        store = MemoryStore(str(temp_dir))
        repo = "https://github.com/test/repo"
        store.add(repo, "coding_style", "use tabs", "convention")

        task = TaskConfig(
            id="bug-001",
            name="test",
            description="Fix the login bug",
            repo=repo,
            branch="main",
            environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
            agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
            sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
        )

        sandbox = FakeContextSandbox()
        context = await build_context(sandbox, task, "test-container", data_dir=str(temp_dir))

        assert "## Project Memory" in context
        assert "[convention] coding_style: use tabs" in context
        assert "## Repository Structure" in context
        assert "Fix the login bug" in context