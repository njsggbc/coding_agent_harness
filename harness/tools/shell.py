from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class RunShellTool(Tool):
    name = "run_shell"
    description = "Execute a shell command in the sandbox. Use for running tests, installing packages, etc."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "workdir": {"type": "string", "description": "Working directory for the command"},
        },
        "required": ["command"],
    }

    MAX_OUTPUT = 8000

    async def execute(self, args: dict, sandbox: Sandbox, container_id: str) -> ToolResult:
        try:
            result = await sandbox.exec(container_id, args["command"], workdir=args.get("workdir"))
            output = result.stdout
            if len(output) > self.MAX_OUTPUT:
                output = output[:self.MAX_OUTPUT] + "\n... (output truncated)"

            if result.exit_code != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {result.exit_code}",
                )

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))