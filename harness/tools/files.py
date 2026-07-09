from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Use offset and limit for large files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to read"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            lines = content.split("\n")
            offset = args.get("offset", 1) - 1
            limit = args.get("limit")
            if limit:
                lines = lines[offset:offset + limit]
            else:
                lines = lines[offset:]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write or overwrite a file with the given content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            await sandbox.write_file("", args["path"], args["content"])
            return ToolResult(success=True, output=f"File written: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace exact string in a file. The old_str must match exactly including whitespace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "old_str": {"type": "string", "description": "Exact string to replace"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            old_str = args["old_str"]
            new_str = args["new_str"]

            if old_str not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"old_str not found in {args['path']}",
                )

            count = content.count(old_str)
            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} matches for old_str. Provide more context to make it unique.",
                )

            new_content = content.replace(old_str, new_str, 1)
            await sandbox.write_file("", args["path"], new_content)
            return ToolResult(success=True, output=f"File edited: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))