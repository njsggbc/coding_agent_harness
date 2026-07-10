import pytest
from harness.feedback import FeedbackAnalyzer, FeedbackResult, FailureType
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
        self.seen_messages = []

    async def chat(self, messages, tools):
        self.seen_messages.append(messages)
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


class FailingTool(Tool):
    name = "failing_tool"
    description = "A tool that always fails"
    parameters = {
        "type": "object",
        "properties": {"error_type": {"type": "string"}},
        "required": [],
    }

    async def execute(self, args, sandbox, container_id):
        error_type = args.get("error_type", "exit_code")
        if error_type == "exit_code":
            return ToolResult(success=False, output="", error="Command failed with exit code 1")
        elif error_type == "timeout":
            return ToolResult(success=False, output="", error="Command execution timed out after 30s")
        elif error_type == "blocked":
            return ToolResult(success=False, output="", error="Command blocked: rm -rf / matches blocked pattern")
        elif error_type == "network":
            return ToolResult(success=False, output="", error="Connection refused: network is unreachable")
        elif error_type == "unknown":
            return ToolResult(success=False, output="", error="Something went horribly wrong")
        return ToolResult(success=True, output="success", error=None)


class SuccessTool(Tool):
    name = "success_tool"
    description = "A tool that always succeeds"
    parameters = {
        "type": "object",
        "properties": {"message": {"type": "string"}},
        "required": [],
    }

    async def execute(self, args, sandbox, container_id):
        return ToolResult(success=True, output=args.get("message", "ok"))


def _make_task():
    return TaskConfig(
        id="bug-001", name="test", description="fix it",
        repo="https://github.com/test/repo", branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )


class TestFeedbackAnalyzer:
    def test_feedback_classifies_exit_code_error(self):
        result = FeedbackAnalyzer.analyze("run_shell", "some output", exit_code=1, error="Command failed")
        assert result.success is False
        assert result.failure_type == FailureType.EXIT_CODE
        assert "exit code" in result.summary.lower() or "command" in result.summary.lower()

    def test_feedback_classifies_timeout(self):
        result = FeedbackAnalyzer.analyze("run_shell", "", exit_code=0, error="Tool execution timed out after 30s")
        assert result.success is False
        assert result.failure_type == FailureType.TIMEOUT
        assert "timeout" in result.summary.lower() or "timed out" in result.summary.lower()

    def test_feedback_classifies_blocked(self):
        result = FeedbackAnalyzer.analyze("run_shell", "", exit_code=0, error="Command blocked: rm -rf / matches blocked pattern")
        assert result.success is False
        assert result.failure_type == FailureType.BLOCKED
        assert "blocked" in result.summary.lower()

    def test_feedback_classifies_network_error(self):
        result = FeedbackAnalyzer.analyze("run_shell", "", exit_code=0, error="Connection refused: network is unreachable")
        assert result.success is False
        assert result.failure_type == FailureType.NETWORK_ERROR
        assert "network" in result.summary.lower()

    def test_feedback_classifies_unknown_error(self):
        result = FeedbackAnalyzer.analyze("run_shell", "", exit_code=0, error="Something went horribly wrong")
        assert result.success is False
        assert result.failure_type == FailureType.UNKNOWN
        assert result.suggestion

    def test_feedback_success_no_failure_type(self):
        result = FeedbackAnalyzer.analyze("run_shell", "all good", exit_code=0, error=None)
        assert result.success is True
        assert result.failure_type == FailureType.NONE
        assert result.summary

    def test_feedback_success_with_no_error(self):
        result = FeedbackAnalyzer.analyze("echo", "hello world", exit_code=0, error=None)
        assert result.success is True
        assert result.failure_type == FailureType.NONE


class TestFeedbackAgentLoop:
    @pytest.mark.asyncio
    async def test_feedback_success_no_feedback(self):
        adapter = FakeAdapter([
            AdapterResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="success_tool", arguments={"message": "hello"})],
                finish_reason="tool_calls",
                usage=TokenUsage(total_tokens=50),
            ),
            AdapterResponse(content="Task complete", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
        ])
        registry = ToolRegistry()
        registry.register(SuccessTool())
        sandbox = FakeSandbox()
        guard = CommandGuard(blocked_patterns=[])
        observer = Observer()

        loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=_make_task().agent, container_id="fake-container")
        result = await loop.run(_make_task())

        assert result.status == "done"
        for msg in result.messages:
            if msg.get("role") == "user":
                assert "[FEEDBACK]" not in msg.get("content", "")

    @pytest.mark.asyncio
    async def test_feedback_fed_into_agent_loop(self):
        adapter = FakeAdapter([
            AdapterResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="failing_tool", arguments={"error_type": "exit_code"})],
                finish_reason="tool_calls",
                usage=TokenUsage(total_tokens=50),
            ),
            AdapterResponse(content="I see the error and will fix it", finish_reason="stop", usage=TokenUsage(total_tokens=50)),
        ])
        registry = ToolRegistry()
        registry.register(FailingTool())
        sandbox = FakeSandbox()
        guard = CommandGuard(blocked_patterns=[])
        observer = Observer()

        loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=_make_task().agent, container_id="fake-container")
        result = await loop.run(_make_task())

        assert result.status == "done"
        feedback_found = False
        for msg in result.messages:
            if msg.get("role") == "user" and "[FEEDBACK]" in msg.get("content", ""):
                feedback_found = True
                break
        assert feedback_found, "Feedback message should be present in the conversation"

        messages_seen_by_second_call = adapter.seen_messages[1] if len(adapter.seen_messages) > 1 else []
        feedback_in_second_call = any(
            "[FEEDBACK]" in msg.get("content", "")
            for msg in messages_seen_by_second_call
            if msg.get("role") == "user"
        )
        assert feedback_in_second_call, "Second LLM call should include feedback message"

    @pytest.mark.asyncio
    async def test_demo_feedback_loop(self):
        adapter = FakeAdapter([
            AdapterResponse(
                content=None,
                tool_calls=[ToolCall(id="1", name="failing_tool", arguments={"error_type": "exit_code"})],
                finish_reason="tool_calls",
                usage=TokenUsage(total_tokens=50),
            ),
            AdapterResponse(
                content="I see the exit code error. Let me check the command output and fix the issue.",
                finish_reason="stop",
                usage=TokenUsage(total_tokens=50),
            ),
        ])
        registry = ToolRegistry()
        registry.register(FailingTool())
        sandbox = FakeSandbox()
        guard = CommandGuard(blocked_patterns=[])
        observer = Observer()

        loop = AgentLoop(adapter=adapter, tools=registry, sandbox=sandbox, guard=guard, observer=observer, config=_make_task().agent, container_id="fake-container")
        result = await loop.run(_make_task())

        assert result.status == "done"
        second_response = adapter.responses[1].content or ""
        assert "error" in second_response.lower() or "exit" in second_response.lower() or "fix" in second_response.lower()