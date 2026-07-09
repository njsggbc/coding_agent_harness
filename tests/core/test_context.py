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