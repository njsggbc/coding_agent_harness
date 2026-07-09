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