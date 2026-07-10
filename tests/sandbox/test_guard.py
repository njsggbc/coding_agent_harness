import pytest
from harness.sandbox.guard import CommandGuard, GuardBlockedError


def test_guard_allows_safe_command():
    guard = CommandGuard(blocked_patterns=["rm -rf /", "shutdown"])

    guard.check("run_shell", {"command": "ls -la"})
    guard.check("run_shell", {"command": "pytest tests/"})


def test_guard_blocks_dangerous_command():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    with pytest.raises(GuardBlockedError, match="Command blocked"):
        guard.check("run_shell", {"command": "rm -rf /"})


def test_guard_blocks_dangerous_command_in_subcommand():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    with pytest.raises(GuardBlockedError):
        guard.check("run_shell", {"command": "sudo rm -rf / --no-preserve-root"})


def test_guard_ignores_non_shell_tools():
    guard = CommandGuard(blocked_patterns=["rm -rf /"])

    guard.check("read_file", {"path": "/etc/passwd"})
    guard.check("write_file", {"path": "/tmp/test", "content": "rm -rf /"})


def test_guard_with_empty_blocked_list():
    guard = CommandGuard(blocked_patterns=[])

    guard.check("run_shell", {"command": "rm -rf /"})