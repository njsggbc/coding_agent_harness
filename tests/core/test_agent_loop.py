import pytest
from harness.core.agent_loop import AgentLoop, LoopResult
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
from harness.adapters.base import BaseAdapter, AdapterResponse, TokenUsage, ToolCall
from harness.tools.registry import ToolRegistry, Tool, ToolResult
from harness.sandbox.base import Sandbox, ExecResult
from harness.sandbox.guard import CommandGuard
from harness.observer.base import Observer


class FakeAdapter(BaseAdapter):
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    async def chat(self, messages, tools):
        if self.call_count >= len(self.responses):
            return AdapterResponse(content="Done", finish_reason="stop", usage=TokenUsage(total_tokens=100))
        response = self.responses[self.call_count]
        self.call_count += 1
        return response


class FakeSandbox(Sandbox):
    async def create(self, image, workdir, repo_path):
        return "fake-container"

    async def exec(self, container_id, command, workdir=None):
        if "git diff" in command:
            return ExecResult(exit_code=0, stdout="diff --git a/file.py b/file.py\n+fixed", stderr="")
        return ExecResult(exit_code=0, stdout="ok", stderr="")

    async def read_file(self, container_id, path):
        return "file content"

    async def write_file(self, container_id, path, content):
        pass

    async def setup(self, container_id, commands):
        pass

    async def stop(self, container_id):
        pass


class FakeEchoTool(Tool):
    name = "echo"
    description = "Echo a message"
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": ["message"],
    }

    async def execute(self, args, sandbox):
        return ToolResult(success=True, output=args["message"])


@pytest.mark.asyncio
async def test_agent_loop_completes_with_text_response():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    adapter = FakeAdapter([
        AdapterResponse(content="I've fixed the bug", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
    ])
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert isinstance(result, LoopResult)
    assert result.status == "done"
    assert result.turns == 1
    assert result.diff == "diff --git a/file.py b/file.py\n+fixed"


@pytest.mark.asyncio
async def test_agent_loop_with_tool_calls():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    adapter = FakeAdapter([
        AdapterResponse(
            content=None,
            tool_calls=[ToolCall(id="1", name="echo", arguments={"message": "hello"})],
            finish_reason="tool_calls",
            usage=TokenUsage(total_tokens=50),
        ),
        AdapterResponse(content="Task complete", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
    ])
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert result.status == "done"
    assert result.turns == 2
    assert len(result.tool_calls) == 1


@pytest.mark.asyncio
async def test_agent_loop_hits_max_turns():
    task = TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=2, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    responses = []
    for _ in range(10):
        responses.append(AdapterResponse(
            content=None,
            tool_calls=[ToolCall(id="1", name="echo", arguments={"message": "x"})],
            finish_reason="tool_calls",
            usage=TokenUsage(total_tokens=10),
        ))

    adapter = FakeAdapter(responses)
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    sandbox = FakeSandbox()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=task.agent, container_id="fake-container")
    result = await loop.run(task)

    assert result.status == "failed"
    assert "max turns" in (result.error or "").lower() or "turns" in (result.error or "").lower()