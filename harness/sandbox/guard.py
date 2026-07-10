class GuardBlockedError(Exception):
    pass


class CommandGuard:
    def __init__(self, blocked_patterns: list[str]):
        self.blocked_patterns = blocked_patterns

    def check(self, tool_name: str, args: dict) -> bool:
        if tool_name == "run_shell":
            command = args.get("command", "")
            for pattern in self.blocked_patterns:
                if pattern in command:
                    raise GuardBlockedError(
                        f"Command blocked: '{command}' matches pattern '{pattern}'"
                    )
        return True