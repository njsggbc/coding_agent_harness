from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show the current git diff of all changes made so far."
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", "git diff")
            return ToolResult(success=True, output=result.stdout or "No changes")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitLogTool(Tool):
    name = "git_log"
    description = "Show recent git commit history."
    parameters = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of recent commits to show"},
        },
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            count = args.get("count", 10)
            result = await sandbox.exec("", f"git log --oneline -{count}")
            return ToolResult(success=True, output=result.stdout or "No commits")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(Tool):
    name = "list_dir"
    description = "List the contents of a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the directory"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", f"ls -la {args['path']}")
            return ToolResult(success=True, output=result.stdout)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))