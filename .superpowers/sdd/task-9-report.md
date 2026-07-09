# Task 9 Report: AgentLoop

**Status:** Complete

## Files
- Created: `harness/core/agent_loop.py` (180 lines)
- Created: `tests/core/test_agent_loop.py` (169 lines)

## Implementation
- `LoopResult` dataclass: `status`, `diff`, `turns`, `tokens_used`, `messages`, `tool_calls`, `error`
- `AgentLoop` class with `async run(task: TaskConfig) -> LoopResult` — the main agent loop engine
- Conversation loop: system prompt + context → chat → tool calls → execute → repeat until stop or max turns
- Emits observer events: `SandboxEvent`, `TurnStart`, `AgentThinking`, `ToolCallStart`, `ToolCallEnd`, `LoopComplete`, `LoopError`
- Handles max turns limit (returns `status="failed"` with error message)
- Handles `asyncio.CancelledError` (returns `status="cancelled"`)
- Handles general exceptions (returns `status="failed"` with error)
- Safe diff retrieval via `_safe_diff()` helper

## Tests
- `test_agent_loop_completes_with_text_response` — single turn with text response, verifies diff is captured
- `test_agent_loop_with_tool_calls` — two turns with an echo tool call, verifies tool_calls list
- `test_agent_loop_hits_max_turns` — max_turns=2 with persistent tool_calls, verifies status=failed and error message

Uses `FakeAdapter`, `FakeSandbox`, `FakeEchoTool` in test file.

## Note
The test in the brief used ad-hoc `type()` objects for tool calls (with `tc.function.name` pattern). This was corrected to use `ToolCall` dataclass instances from `harness.adapters.base` to match the actual `ToolCall` dataclass interface (`tc.name`, `tc.arguments`).

## Verification
```
pytest tests/core/test_agent_loop.py -v  # 3 PASSED
pytest -v                                  # 50 passed, 6 skipped
```

## Commit
```
e615f4c feat: add AgentLoop core engine with tool-calling cycle
```

## Fix: guard against undefined response when max_turns=0
- **Issue:** `response` may be undefined when `max_turns=0` (`agent_loop.py:149`). If `max_turns=0`, the while loop never executes, `response` is never assigned, and `not response.content` at line 149 raises `NameError`.
- **Fix:** Initialize `response = None` before the loop, then guard the max_turns check with `if response is None or (turn >= self.config.max_turns and not response.content)`.
- **Commit:** `fix: guard against undefined response when max_turns is 0`

## Self-Review
- [x] Implementation matches task brief exactly
- [x] Test passes
- [x] No regressions in full suite (50/50)
- [x] Commit message follows conventional format