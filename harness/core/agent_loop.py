import json
import time
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from harness.core.task import TaskConfig, AgentConfig
from harness.core.context import build_context
from harness.adapters.base import BaseAdapter, AdapterResponse
from harness.tools.registry import ToolRegistry, ToolResult
from harness.sandbox.base import Sandbox
from harness.sandbox.guard import CommandGuard, GuardBlockedError
from harness.observer.base import (
    Observer, TurnStart, ToolCallStart, ToolCallEnd,
    AgentThinking, LoopError, LoopComplete, SandboxEvent,
)


@dataclass
class LoopResult:
    status: str
    diff: str
    turns: int
    tokens_used: int
    messages: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    error: Optional[str] = None


SYSTEM_PROMPT = """You are an expert software engineer tasked with fixing bugs in a codebase.

You have access to tools that let you read, write, and edit files, search code, run shell commands, and inspect git history.

Workflow:
1. Understand the bug by reading relevant files and searching the codebase
2. Identify the root cause
3. Implement the fix by editing the affected files
4. Verify your fix works (run tests if available)
5. When done, provide a summary of what you changed and why

Be thorough and precise. Make minimal changes to fix the bug."""


class AgentLoop:
    def __init__(
        self,
        adapter: BaseAdapter,
        tools: ToolRegistry,
        sandbox: Sandbox,
        guard: CommandGuard,
        observer: Observer,
        config: AgentConfig,
        container_id: str,
    ):
        self.adapter = adapter
        self.tools = tools
        self.sandbox = sandbox
        self.guard = guard
        self.observer = observer
        self.config = config
        self.container_id = container_id

    async def run(self, task: TaskConfig) -> LoopResult:
        self.observer.emit(SandboxEvent(message="Building repository context..."))

        context = await build_context(self.sandbox, task)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        tool_schemas = self.tools.to_openai_schema()
        all_tool_calls = []
        total_tokens = 0
        turn = 0

        try:
            while turn < self.config.max_turns:
                turn += 1
                self.observer.emit(TurnStart(turn_number=turn))

                response = await self.adapter.chat(messages, tool_schemas)
                if response.usage:
                    total_tokens += response.usage.total_tokens

                if response.content:
                    self.observer.emit(AgentThinking(content=response.content))

                message = {"role": "assistant", "content": response.content}

                if response.tool_calls:
                    tool_call_blocks = []
                    for tc in response.tool_calls:
                        tool_call_blocks.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                        })
                    message["tool_calls"] = tool_call_blocks

                messages.append(message)

                if not response.tool_calls:
                    break

                tool_results = []
                for tc in response.tool_calls:
                    self.observer.emit(ToolCallStart(tool_name=tc.name, args=tc.arguments))

                    try:
                        self.guard.check(tc.name, tc.arguments)
                    except GuardBlockedError as e:
                        result = ToolResult(success=False, output="", error=str(e))
                        self.observer.emit(ToolCallEnd(tool_name=tc.name, result=str(e), duration=0))
                        tool_results.append({"tool_call_id": tc.id, "role": "tool", "content": str(e)})
                        all_tool_calls.append({"turn": turn, "tool": tc.name, "args": tc.arguments, "result": str(e), "success": False})
                        continue

                    t0 = time.monotonic()
                    tool = self.tools.get(tc.name)
                    if tool is None:
                        err = f"Unknown tool: {tc.name}"
                        result = ToolResult(success=False, output="", error=err)
                    else:
                        result = await tool.execute(tc.arguments, self.sandbox)

                    duration = time.monotonic() - t0
                    self.observer.emit(ToolCallEnd(tool_name=tc.name, result=result.output or result.error or "", duration=duration))

                    tool_results.append({
                        "tool_call_id": tc.id,
                        "role": "tool",
                        "content": result.output if result.success else f"Error: {result.error}",
                    })
                    all_tool_calls.append({
                        "turn": turn, "tool": tc.name, "args": tc.arguments,
                        "result": result.output or result.error, "success": result.success,
                    })

                messages.extend(tool_results)

            diff = ""
            try:
                diff_result = await self.sandbox.exec(self.container_id, "git diff")
                diff = diff_result.stdout
            except Exception:
                pass

            if turn >= self.config.max_turns and not response.content:
                return LoopResult(
                    status="failed",
                    diff=diff,
                    turns=turn,
                    tokens_used=total_tokens,
                    messages=messages,
                    tool_calls=all_tool_calls,
                    error=f"Reached max turns ({self.config.max_turns}) without completing",
                )

            self.observer.emit(LoopComplete(status="done", turns=turn, tokens_used=total_tokens))

            return LoopResult(
                status="done",
                diff=diff,
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
            )

        except asyncio.CancelledError:
            self.observer.emit(LoopError(error="Task cancelled by user"))
            return LoopResult(
                status="cancelled",
                diff=(await self._safe_diff()),
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
                error="Cancelled by user",
            )
        except Exception as e:
            self.observer.emit(LoopError(error=str(e)))
            return LoopResult(
                status="failed",
                diff=(await self._safe_diff()),
                turns=turn,
                tokens_used=total_tokens,
                messages=messages,
                tool_calls=all_tool_calls,
                error=str(e),
            )

    async def _safe_diff(self) -> str:
        try:
            result = await self.sandbox.exec(self.container_id, "git diff")
            return result.stdout
        except Exception:
            return ""