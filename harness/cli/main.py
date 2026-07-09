import os
import asyncio
import click
import yaml
from harness.core.task import load_task_config
from harness.core.task_manager import TaskManager
from harness.report.generator import ReportGenerator
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.observer.base import Observer
from harness.observer.stream import StreamObserver
from harness.observer.logger import LogObserver
from harness.cli.formatters import format_status_table, format_task_detail


def load_config():
    config_paths = ["config.yaml", "harness.yaml"]
    config = {}
    for p in config_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                config.update(loaded)
    return config


def resolve_api_key(config):
    key = config.get("api", {}).get("openai_api_key", "")
    if key.startswith("${") and key.endswith("}"):
        env_var = key[2:-1]
        return os.environ.get(env_var, "")
    return key or os.environ.get("OPENAI_API_KEY", "")


def get_data_dir(config, cli_data_dir):
    if cli_data_dir:
        return cli_data_dir
    return config.get("storage", {}).get("data_dir", "./data")


def make_manager(data_dir, api_key, observer):
    store = TaskStore(data_dir)
    file_store = FileStore(data_dir)
    return TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=data_dir,
        api_key=api_key,
    )


def make_report_gen(data_dir):
    store = TaskStore(data_dir)
    file_store = FileStore(data_dir)
    return ReportGenerator(store, file_store)


@click.group()
@click.pass_context
def cli(ctx):
    pass


@cli.command()
@click.argument("task_file", type=click.Path(exists=True))
@click.option("--verbose", is_flag=True, help="Stream agent output in real-time")
@click.option("--no-stream", is_flag=True, help="Suppress real-time streaming")
@click.option("--data-dir", default=None, help="Override data directory")
def run(task_file, verbose, no_stream, data_dir):
    """Execute a bug-fixing task from a YAML file."""
    config = load_config()
    api_key = resolve_api_key(config)
    ddir = get_data_dir(config, data_dir)

    if not api_key:
        click.echo("Error: OPENAI_API_KEY not set. Set it via config.yaml or environment variable.", err=True)
        raise SystemExit(1)

    observer = Observer()
    if not no_stream:
        observer.subscribe(StreamObserver())

    log_path = os.path.join(ddir, "harness.log")
    os.makedirs(ddir, exist_ok=True)
    observer.subscribe(LogObserver(log_path))

    manager = make_manager(ddir, api_key, observer)

    task = load_task_config(task_file)

    click.echo(f"Starting task: {task.id} - {task.name}")
    click.echo(f"Agent: {task.agent.model} | Max turns: {task.agent.max_turns}")
    click.echo(f"Repo: {task.repo} ({task.branch})")

    result = asyncio.run(manager.run(task, task_file))

    click.echo(f"\nTask {result.status} in {result.turns} turns, {result.tokens_used} tokens")
    if result.diff:
        click.echo("\nDiff:")
        click.echo(result.diff)
    if result.error:
        click.echo(f"\nError: {result.error}")


@cli.command()
@click.argument("task_id", required=False)
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--data-dir", default=None, help="Override data directory")
def status(task_id, filter_status, as_json, data_dir):
    """View task status."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    if task_id:
        task = store.get(task_id)
        if task is None:
            click.echo(f"Task '{task_id}' not found.")
            return
        if as_json:
            import json
            click.echo(json.dumps(task, indent=2, default=str))
        else:
            click.echo(format_task_detail(task))
    else:
        tasks = store.list_all(status=filter_status)
        if as_json:
            import json
            click.echo(json.dumps(tasks, indent=2, default=str))
        else:
            click.echo(format_status_table(tasks))


@cli.command()
@click.argument("task_id")
@click.option("--verbose", "show_verbose", is_flag=True, help="Show detailed report with messages")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.option("--diff", "show_diff", is_flag=True, help="Show only the diff")
@click.option("--data-dir", default=None, help="Override data directory")
def report(task_id, show_verbose, as_json, show_diff, data_dir):
    """Generate a task report."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    gen = make_report_gen(ddir)

    try:
        if as_json:
            click.echo(gen.format_json(task_id))
        elif show_diff:
            data = gen.generate(task_id)
            click.echo(data["diff"] or "(no diff)")
        elif show_verbose:
            click.echo(gen.format_verbose(task_id))
        else:
            click.echo(gen.format_summary(task_id))
    except ValueError as e:
        click.echo(str(e), err=True)


@cli.command()
@click.option("--status", "filter_status", default=None, help="Filter by status")
@click.option("--limit", default=None, type=int, help="Limit number of results")
@click.option("--data-dir", default=None, help="Override data directory")
def list(filter_status, limit, data_dir):
    """List all tasks."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    tasks = store.list_all(status=filter_status)
    if limit:
        tasks = tasks[:limit]
    click.echo(format_status_table(tasks))


@cli.command()
@click.argument("task_id")
@click.option("--data-dir", default=None, help="Override data directory")
def cancel(task_id, data_dir):
    """Cancel a running task."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = TaskStore(ddir)

    task = store.get(task_id)
    if task is None:
        click.echo(f"Task '{task_id}' not found.")
        return
    if task["status"] != "running":
        click.echo(f"Task '{task_id}' is not running (status: {task['status']}).")
        return

    from harness.core.task import TaskStatus
    store.update_status(task_id, TaskStatus.CANCELLED)
    click.echo(f"Task '{task_id}' cancelled.")


@cli.command()
@click.option("--path", "show_path", is_flag=True, help="Show config file path only")
def config(show_path):
    """Show current configuration."""
    config_paths = ["config.yaml", "harness.yaml"]
    found = None
    for p in config_paths:
        if os.path.exists(p):
            found = os.path.abspath(p)
            break

    if show_path:
        if found:
            click.echo(found)
        else:
            click.echo("No config file found (searched: config.yaml, harness.yaml)")
        return

    if found:
        click.echo(f"Config file: {found}\n")
        with open(found, "r", encoding="utf-8") as f:
            click.echo(f.read())
    else:
        click.echo("No config file found (searched: config.yaml, harness.yaml)")
        click.echo("\nDefault config:")
        click.echo("""
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "${OPENAI_API_KEY}"

logging:
  level: "INFO"
  file: "harness.log"
""")


if __name__ == "__main__":
    cli()