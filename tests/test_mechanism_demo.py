"""Mechanism demonstration tests — all deterministic, no real LLM required."""

import pytest
from harness.sandbox.guard import CommandGuard, GuardBlockedError
from harness.core.agent_loop import AgentLoop, LoopResult
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
from harness.adapters.base import BaseAdapter, AdapterResponse, TokenUsage, ToolCall
from harness.tools.registry import ToolRegistry, Tool, ToolResult
from harness.sandbox.base import Sandbox, ExecResult
from harness.observer.base import Observer


def test_demo_1_guard_blocks_dangerous_command():
    """Demo 1: 治理护栏拦截危险动作

    Scenario: Agent tries to execute 'rm -rf /'
    Expected: GuardBlockedError raised, command blocked
    """
    guard = CommandGuard(blocked_patterns=["rm -rf /", "shutdown", "sudo rm"])

    blocked = [
        ("rm -rf /", "Command blocked"),
        ("sudo rm -rf / --no-preserve-root", "Command blocked"),
        ("sudo rm -rf /var", "Command blocked"),
    ]
    for cmd, expected_msg in blocked:
        with pytest.raises(GuardBlockedError, match=expected_msg):
            guard.check("run_shell", {"command": cmd})

    safe = ["ls -la", "rm temp_file.txt", "pytest tests/"]
    for cmd in safe:
        guard.check("run_shell", {"command": cmd})


def test_demo_2_feedback_loop_drives_self_correction():
    """Demo 2: 反馈闭环使 Agent 收到反馈并改变下一步动作

    Scenario:
    Turn 1: Agent's tool call fails (e.g., pytest not found)
    Turn 2: The failure is fed back as a tool message → Agent adapts

    This test validates that the agent loop correctly passes tool failure
    results back as messages, enabling the self-correction feedback loop.
    """
    from harness.core.agent_loop import AgentLoop
    from harness.adapters.base import AdapterResponse, TokenUsage, ToolCall
    from harness.tools.registry import ToolRegistry, Tool, ToolResult
    from harness.sandbox.base import Sandbox, ExecResult
    from harness.sandbox.guard import CommandGuard
    from harness.observer.base import Observer

    class FailingTool(Tool):
        name = "run_tests"
        description = "Run test suite"
        parameters = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

        async def execute(self, args, sandbox, container_id):
            return ToolResult(
                success=False,
                output="",
                error="Command 'pytest' not found. Try 'pip install pytest' first.",
            )

    class FeedbackAwareAdapter(BaseAdapter):
        def __init__(self):
            self.call_count = 0
            self.messages_seen = []

        async def chat(self, messages, tools):
            self.messages_seen = [m.copy() for m in messages]
            self.call_count += 1

            if self.call_count == 1:
                return AdapterResponse(
                    content=None,
                    tool_calls=[ToolCall(
                        id="c1", name="run_tests",
                        arguments={"command": "pytest tests/"},
                    )],
                    finish_reason="tool_calls",
                    usage=TokenUsage(total_tokens=50),
                )
            else:
                tool_messages = [m for m in messages if m["role"] == "tool"]
                feedback = tool_messages[-1]["content"] if tool_messages else ""
                adapted = "pytest not found" in feedback
                return AdapterResponse(
                    content=(
                        "I see pytest is not installed. Let me install it and try again."
                        if adapted
                        else "Something went wrong but I don't know why."
                    ),
                    finish_reason="stop",
                    usage=TokenUsage(total_tokens=50),
                )

    class FakeSandboxForDemo(Sandbox):
        async def create(self, image, workdir, repo_path):
            return "demo"

        async def exec(self, container_id, command, workdir=None):
            return ExecResult(exit_code=0, stdout="", stderr="")

        async def read_file(self, container_id, path):
            return ""

        async def write_file(self, container_id, path, content):
            pass

        async def setup(self, container_id, commands):
            pass

        async def stop(self, container_id):
            pass

    task = TaskConfig(
        id="demo", name="demo", description="demo",
        repo="https://github.com/demo/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=5, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    registry = ToolRegistry()
    registry.register(FailingTool())
    adapter = FeedbackAwareAdapter()
    guard = CommandGuard(blocked_patterns=[])
    observer = Observer()

    loop = AgentLoop(
        adapter=adapter, tools=registry, sandbox=FakeSandboxForDemo(),
        guard=guard, observer=observer, config=task.agent, container_id="demo",
    )

    import asyncio
    result = asyncio.run(loop.run(task))

    assert result.status == "done"
    assert result.turns == 2
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["success"] is False
    assert "pytest" in result.tool_calls[0]["result"].lower()


def test_demo_3_governance_deep_behavior():
    """Demo 3: 治理维度深度行为

    Scenario: Multiple tool calls with mixed safe/dangerous commands
    Expected: Guard correctly identifies only dangerous ones
    """
    guard = CommandGuard(
        blocked_patterns=["rm -rf /", "shutdown", ">: /dev/sda", "mkfs."]
    )

    test_cases = [
        ("ls -la", True),
        ("rm -rf /", False),
        ("pytest tests/", True),
        ("shutdown now", False),
        ("git diff", True),
        ("mkfs.ext4 /dev/sda1", False),
        ("cat > /tmp/test.txt", True),
        ("echo 'hello' >: /dev/sda", False),
    ]

    for command, should_pass in test_cases:
        if should_pass:
            guard.check("run_shell", {"command": command})
        else:
            with pytest.raises(GuardBlockedError):
                guard.check("run_shell", {"command": command})


def test_demo_4_agent_loop_with_guard_integration():
    """Demo 4: Agent loop with guard integration

    Scenario: Agent tries to execute a blocked command via tool call
    Expected: Guard intercepts, agent receives error feedback, loop continues
    """

    class FakeShellTool(Tool):
        name = "run_shell"
        description = "Execute shell command"
        parameters = {
            "type": "object",
            "properties": {"command": {"type": "string"}},
            "required": ["command"],
        }

        async def execute(self, args, sandbox, container_id):
            cmd = args["command"]
            if "rm -rf" in cmd:
                return ToolResult(
                    success=False, output="", error="Blocked by guard: dangerous command"
                )
            return ToolResult(success=True, output=f"Executed: {cmd}")

    class GuardDemoAdapter(BaseAdapter):
        def __init__(self):
            self.call_count = 0

        async def chat(self, messages, tools):
            self.call_count += 1
            if self.call_count == 1:
                return AdapterResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="c1", name="run_shell",
                            arguments={"command": "rm -rf /"},
                        )
                    ],
                    finish_reason="tool_calls",
                    usage=TokenUsage(total_tokens=10),
                )
            else:
                return AdapterResponse(
                    content="I cannot execute that command. Let me try a different approach.",
                    finish_reason="stop",
                    usage=TokenUsage(total_tokens=10),
                )

    class FakeSandboxForDemo(Sandbox):
        async def create(self, image, workdir, repo_path):
            return "demo"

        async def exec(self, container_id, command, workdir=None):
            return ExecResult(exit_code=0, stdout="", stderr="")

        async def read_file(self, container_id, path):
            return ""

        async def write_file(self, container_id, path, content):
            pass

        async def setup(self, container_id, commands):
            pass

        async def stop(self, container_id):
            pass

    task = TaskConfig(
        id="demo", name="demo", description="demo",
        repo="https://github.com/demo/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=5, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=["rm -rf /"]),
    )

    registry = ToolRegistry()
    registry.register(FakeShellTool())
    guard = CommandGuard(blocked_patterns=["rm -rf /"])
    observer = Observer()

    loop = AgentLoop(
        adapter=GuardDemoAdapter(),
        tools=registry,
        sandbox=FakeSandboxForDemo(),
        guard=guard,
        observer=observer,
        config=task.agent,
        container_id="demo",
    )

    import asyncio
    result = asyncio.run(loop.run(task))

    assert result.status == "done"
    assert len(result.tool_calls) > 0
    assert result.tool_calls[0]["success"] is False
    assert "blocked" in result.tool_calls[0]["result"].lower()