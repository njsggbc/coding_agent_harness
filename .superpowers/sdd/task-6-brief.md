### Task 6: Observer Layer

**Files:**
- Create: `harness/observer/base.py`
- Create: `harness/observer/stream.py`
- Create: `harness/observer/logger.py`
- Test: `tests/observer/test_observer.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - Event dataclasses: `TurnStart(turn_number: int)`, `ToolCallStart(tool_name: str, args: dict)`, `ToolCallEnd(tool_name: str, result: str, duration: float)`, `AgentThinking(content: str)`, `LoopError(error: str)`, `LoopComplete(status: str, turns: int, tokens_used: int)`, `SandboxEvent(message: str)`
  - `Observer` class with `emit(event)`, `subscribe(handler: callable)`, `unsubscribe(handler: callable)`
  - `StreamObserver` class that prints formatted events to terminal
  - `LogObserver` class that writes JSONL events to file

- [ ] **Step 1: Write base.py**

```python
# harness/observer/base.py
from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class TurnStart:
    turn_number: int


@dataclass
class ToolCallStart:
    tool_name: str
    args: dict


@dataclass
class ToolCallEnd:
    tool_name: str
    result: str
    duration: float


@dataclass
class AgentThinking:
    content: str


@dataclass
class LoopError:
    error: str


@dataclass
class LoopComplete:
    status: str
    turns: int
    tokens_used: int


@dataclass
class SandboxEvent:
    message: str


class Observer:
    def __init__(self):
        self._handlers: list[Callable] = []

    def subscribe(self, handler: Callable):
        self._handlers.append(handler)

    def unsubscribe(self, handler: Callable):
        self._handlers.remove(handler)

    def emit(self, event):
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                pass
```

- [ ] **Step 2: Write failing test**

```python
# tests/observer/test_observer.py
import pytest
from harness.observer.base import (
    Observer,
    TurnStart,
    ToolCallStart,
    ToolCallEnd,
    AgentThinking,
    LoopError,
    LoopComplete,
    SandboxEvent,
)
from harness.observer.stream import StreamObserver
from harness.observer.logger import LogObserver


class TestObserver:
    def test_emit_delivers_to_subscriber(self):
        events = []
        observer = Observer()
        observer.subscribe(lambda e: events.append(e))

        observer.emit(TurnStart(turn_number=1))
        observer.emit(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))

        assert len(events) == 2
        assert isinstance(events[0], TurnStart)
        assert events[0].turn_number == 1
        assert isinstance(events[1], ToolCallStart)
        assert events[1].tool_name == "read_file"

    def test_unsubscribe_stops_delivery(self):
        events = []
        observer = Observer()

        def handler(e):
            events.append(e)

        observer.subscribe(handler)
        observer.emit(TurnStart(turn_number=1))
        observer.unsubscribe(handler)
        observer.emit(TurnStart(turn_number=2))

        assert len(events) == 1

    def test_handler_exception_does_not_break_others(self):
        events = []
        observer = Observer()

        def bad_handler(e):
            raise RuntimeError("boom")

        def good_handler(e):
            events.append(e)

        observer.subscribe(bad_handler)
        observer.subscribe(good_handler)
        observer.emit(TurnStart(turn_number=1))

        assert len(events) == 1


class TestStreamObserver:
    def test_stream_observer_does_not_crash(self, capsys):
        stream = StreamObserver()
        stream(TurnStart(turn_number=1))
        stream(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))
        stream(ToolCallEnd(tool_name="read_file", result="file content", duration=0.5))
        stream(AgentThinking(content="I need to read the file"))
        stream(LoopError(error="connection timeout"))
        stream(LoopComplete(status="done", turns=3, tokens_used=1500))
        stream(SandboxEvent(message="Container started"))


class TestLogObserver:
    def test_log_observer_writes_events(self, temp_dir):
        log_path = temp_dir / "test.log"
        logger = LogObserver(str(log_path))

        logger(TurnStart(turn_number=1))
        logger(ToolCallStart(tool_name="read_file", args={"path": "test.py"}))
        logger(LoopComplete(status="done", turns=3, tokens_used=1500))

        assert log_path.exists()
        lines = log_path.read_text().strip().split("\n")
        assert len(lines) == 3
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/observer/test_observer.py -v
```

Expected: FAIL

- [ ] **Step 4: Write stream.py**

```python
# harness/observer/stream.py
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
            self.output.write(f"\n{'鈹€' * 50}\n  Turn {event.turn_number}\n{'鈹€' * 50}\n")
        elif isinstance(event, AgentThinking):
            self.output.write(f"馃 Agent thinking...\n   \"{event.content[:200]}{'...' if len(event.content) > 200 else ''}\"\n\n")
        elif isinstance(event, ToolCallStart):
            self.output.write(f"馃敡 {event.tool_name}({self._format_args(event.args)})\n")
        elif isinstance(event, ToolCallEnd):
            short = event.result[:100].replace('\n', ' ')
            self.output.write(f"   鉁?{short}{'...' if len(event.result) > 100 else ''} ({event.duration:.1f}s)\n\n")
        elif isinstance(event, LoopError):
            self.output.write(f"鉂?Error: {event.error}\n")
        elif isinstance(event, LoopComplete):
            self.output.write(f"\n{'鈹€' * 50}\n鉁?Task {event.status} in {event.turns} turns, {event.tokens_used} tokens\n{'鈹€' * 50}\n")
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
```

- [ ] **Step 5: Write logger.py**

```python
# harness/observer/logger.py
import json
from dataclasses import asdict


class LogObserver:
    def __init__(self, path: str):
        self.path = path

    def __call__(self, event):
        data = {"type": type(event).__name__, **asdict(event)}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")
```

- [ ] **Step 6: Run test to verify it passes**

```bash
pytest tests/observer/test_observer.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add harness/observer/ tests/observer/
git commit -m "feat: add observer layer with stream and log observers"
```

---

