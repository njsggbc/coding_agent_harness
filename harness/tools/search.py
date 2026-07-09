from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class SearchContentTool(Tool):
    name = "search_content"
    description = "Search for a regex pattern in file contents. Fast grep-like search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory or file path to search in"},
            "include": {"type": "string", "description": "File pattern filter, e.g. '*.py'"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            cmd_parts = ["grep", "-rn", "--include", args.get("include", "*")]
            search_path = args.get("path", ".")
            cmd_parts.extend([args["pattern"], search_path])
            result = await sandbox.exec("", " ".join(cmd_parts))
            return ToolResult(success=True, output=result.stdout or "No matches found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Find files matching a glob pattern. Fast file name search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
            "path": {"type": "string", "description": "Directory to search in"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            search_path = args.get("path", ".")
            result = await sandbox.exec("", f"find {search_path} -name '{args['pattern']}' -type f")
            return ToolResult(success=True, output=result.stdout or "No files found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))