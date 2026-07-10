from dataclasses import dataclass
from enum import Enum
from typing import Optional


class FailureType(Enum):
    NONE = "none"
    EXIT_CODE = "exit_code"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


@dataclass
class FeedbackResult:
    success: bool
    failure_type: FailureType
    summary: str
    suggestion: str


class FeedbackAnalyzer:
    @staticmethod
    def analyze(
        tool_name: str,
        result: str,
        exit_code: int = 0,
        error: Optional[str] = None,
    ) -> FeedbackResult:
        if exit_code != 0:
            return FeedbackResult(
                success=False,
                failure_type=FailureType.EXIT_CODE,
                summary=f"Command '{tool_name}' exited with non-zero exit code {exit_code}. Output: {result}",
                suggestion="Check the command output for errors and fix the issue",
            )

        if error:
            error_lower = error.lower()
            if "timeout" in error_lower or "timed out" in error_lower:
                return FeedbackResult(
                    success=False,
                    failure_type=FailureType.TIMEOUT,
                    summary=f"Tool '{tool_name}' timed out. Error: {error}",
                    suggestion="The operation timed out. Try a simpler approach or split into smaller steps",
                )
            if "blocked" in error_lower:
                return FeedbackResult(
                    success=False,
                    failure_type=FailureType.BLOCKED,
                    summary=f"Tool '{tool_name}' was blocked. Error: {error}",
                    suggestion="Your action was blocked by the safety guard. Find an alternative approach",
                )
            if "connection" in error_lower or "network" in error_lower:
                return FeedbackResult(
                    success=False,
                    failure_type=FailureType.NETWORK_ERROR,
                    summary=f"Tool '{tool_name}' encountered a network error. Error: {error}",
                    suggestion="Network error. Check your connection and retry",
                )
            return FeedbackResult(
                success=False,
                failure_type=FailureType.UNKNOWN,
                summary=f"Tool '{tool_name}' failed. Error: {error}",
                suggestion="The operation failed. Review the error and try a different approach",
            )

        return FeedbackResult(
            success=True,
            failure_type=FailureType.NONE,
            summary=f"Tool '{tool_name}' completed successfully.",
            suggestion="",
        )