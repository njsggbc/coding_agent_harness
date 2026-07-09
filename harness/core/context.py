from harness.core.task import TaskConfig
from harness.sandbox.base import Sandbox


async def build_context(sandbox: Sandbox, task: TaskConfig) -> str:
    parts = []

    result = await sandbox.exec("", f"find . -type f -not -path './.git/*' | head -100")
    file_list = result.stdout.strip()

    result = await sandbox.exec("", "git log --oneline -5")
    recent_commits = result.stdout.strip()

    parts.append("## Repository Structure")
    parts.append("```")
    if file_list:
        parts.append(file_list)
    else:
        parts.append("(empty repository)")
    parts.append("```")

    if recent_commits:
        parts.append("\n## Recent Commits")
        parts.append("```")
        parts.append(recent_commits)
        parts.append("```")

    parts.append(f"\n## Task")
    parts.append(f"**Title:** {task.name}")
    parts.append(f"**Description:** {task.description}")
    parts.append(f"**Repository:** {task.repo}")
    parts.append(f"**Branch:** {task.branch}")

    return "\n".join(parts)