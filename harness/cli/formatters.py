def format_status_table(tasks: list[dict]) -> str:
    if not tasks:
        return "No tasks found."

    lines = [f"{'ID':<20} {'Name':<30} {'Status':<12} {'Turns':<8} {'Tokens':<10}"]
    lines.append("-" * 80)
    for t in tasks:
        lines.append(
            f"{t['id']:<20} {t['name'][:28]:<30} {t['status']:<12} "
            f"{str(t['turns'] or '-'):<8} {str(t['tokens_used'] or '-'):<10}"
        )
    return "\n".join(lines)


def format_task_detail(task: dict) -> str:
    if task is None:
        return "Task not found."

    lines = [
        f"ID:          {task['id']}",
        f"Name:        {task['name']}",
        f"Status:      {task['status']}",
        f"Repo:        {task['repo']}",
        f"Branch:      {task['branch']}",
        f"Model:       {task['model']}",
        f"Created:     {task['created_at']}",
        f"Started:     {task['started_at'] or '-'}",
        f"Finished:    {task['finished_at'] or '-'}",
        f"Turns:       {task['turns'] or '-'}",
        f"Tokens:      {task['tokens_used'] or '-'}",
    ]
    if task.get("error"):
        lines.append(f"Error:       {task['error']}")
    return "\n".join(lines)