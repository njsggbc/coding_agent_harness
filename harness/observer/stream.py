import sys
from harness.observer.base import (
    TurnStart,
    ToolCallStart,
    ToolCallEnd,
    AgentThinking,
    LoopError,
    LoopComplete,
    SandboxEvent,
)


class StreamObserver:
    def __init__(self, output=None):
        self.output = output or sys.stdout
        self._turn_count = 0

    def __call__(self, event):
        if isinstance(event, TurnStart):
            self._turn_count = event.turn_number
            self.output.write(f"\n{'─' * 50}\n  Turn {event.turn_number}\n{'─' * 50}\n")
        elif isinstance(event, AgentThinking):
            self.output.write(f"🤔 Agent thinking...\n   \"{event.content[:200]}{'...' if len(event.content) > 200 else ''}\"\n\n")
        elif isinstance(event, ToolCallStart):
            self.output.write(f"🔡 {event.tool_name}({self._format_args(event.args)})\n")
        elif isinstance(event, ToolCallEnd):
            short = event.result[:100].replace('\n', ' ')
            self.output.write(f"   ✔ {short}{'...' if len(event.result) > 100 else ''} ({event.duration:.1f}s)\n\n")
        elif isinstance(event, LoopError):
            self.output.write(f"✖ Error: {event.error}\n")
        elif isinstance(event, LoopComplete):
            self.output.write(f"\n{'─' * 50}\n✔ Task {event.status} in {event.turns} turns, {event.tokens_used} tokens\n{'─' * 50}\n")
        elif isinstance(event, SandboxEvent):
            self.output.write(f"  {event.message}\n")
        self.output.flush()

    def _format_args(self, args: dict) -> str:
        parts = []
        for k, v in args.items():
            s = str(v)
            if len(s) > 60:
                s = s[:57] + "..."
            parts.append(f"{k}={s}")
        return ", ".join(parts)