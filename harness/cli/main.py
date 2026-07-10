import os
import signal
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
from harness.credentials import CredentialManager
from harness.memory import MemoryStore


def load_config():
    config_paths = ["config.yaml", "harness.yaml"]
    config = {}
    for p in config_paths:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
                config.update(loaded)
    return config


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
@click.option("--no-stream", is_flag=True, help="Suppress real-time streaming")
@click.option("--data-dir", default=None, help="Override data directory")
def run(task_file, no_stream, data_dir):
    """Execute a bug-fixing task from a YAML file."""
    config = load_config()
    creds = CredentialManager()
    api_key = creds.get_api_key()
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

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    main_task = loop.create_task(manager.run(task, task_file))

    def signal_handler(sig, frame):
        if not main_task.done():
            click.echo("\nCaught signal, cancelling task...")
            manager.cancel(task.id)
            main_task.cancel()

    if os.name != "nt":
        loop.add_signal_handler(signal.SIGINT, signal_handler)
        loop.add_signal_handler(signal.SIGTERM, signal_handler)
    else:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        result = loop.run_until_complete(main_task)
    except asyncio.CancelledError:
        click.echo("\nTask cancelled.")
        result = None
    except KeyboardInterrupt:
        click.echo("\nTask interrupted.")
        result = None
    finally:
        loop.close()

    if result is None:
        return

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

logging:
  level: "INFO"
  file: "harness.log"
""")


@cli.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=8000, type=int, help="Port to listen on")
@click.option("--data-dir", default=None, help="Override data directory")
def web(host, port, data_dir):
    """Start the WebUI server."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    from harness.webui import run_server
    click.echo(f"Starting WebUI at http://{host}:{port}")
    click.echo(f"Data directory: {ddir}")
    run_server(host=host, port=port, data_dir=ddir)


@cli.group()
def credentials():
    """Manage API keys with secure OS-level storage."""


@credentials.command()
def setup():
    """Interactive guided setup for API key storage."""
    CredentialManager().setup_wizard()


@credentials.command()
def status():
    """Show which services have stored credentials (no plaintext)."""
    mgr = CredentialManager()
    services = mgr.list_services()
    if not services:
        click.echo("No credentials stored.")
        return
    click.echo("Stored credentials:")
    for svc in sorted(services):
        click.echo(f"  {svc}")


@credentials.command()
@click.argument("service")
def update(service):
    """Update an existing credential."""
    mgr = CredentialManager()
    if not mgr.has_credentials(service):
        click.echo(f"No credential found for '{service}'.")
        return
    key = click.prompt("New API key", hide_input=True, confirmation_prompt=True)
    mgr.store(service, key)
    click.echo(f"Credential for '{service}' updated.")


@credentials.command()
@click.argument("service", required=False)
@click.option("--all", "clear_all", is_flag=True, help="Remove all stored credentials")
def clear(service, clear_all):
    """Remove stored credentials."""
    mgr = CredentialManager()
    if clear_all:
        services = mgr.list_services()
        if not services:
            click.echo("No credentials to clear.")
            return
        click.echo(f"Found {len(services)} credential(s):")
        for svc in sorted(services):
            click.echo(f"  {svc}")
        if not click.confirm("Remove all credentials?"):
            click.echo("Aborted.")
            return
        for svc in services:
            mgr.delete(svc)
        click.echo("All credentials removed.")
        return
    if not service:
        click.echo("Error: provide a service name or use --all.", err=True)
        raise SystemExit(1)
    if not mgr.has_credentials(service):
        click.echo(f"No credential found for '{service}'.")
        return
    mgr.delete(service)
    click.echo(f"Credential for '{service}' removed.")


@cli.group()
def memory():
    """Manage project memory across sessions."""


@memory.command()
@click.argument("repo")
@click.argument("key")
@click.argument("value")
@click.option("--category", default="note", type=click.Choice(["convention", "decision", "knowledge", "note"]))
@click.option("--data-dir", default=None, help="Override data directory")
def add(repo, key, value, category, data_dir):
    """Add or update a memory entry for a project."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = MemoryStore(ddir)
    store.add(repo, key, value, category)
    click.echo(f"Memory added: [{category}] {key} = {value}")


@memory.command()
@click.argument("repo")
@click.option("--data-dir", default=None, help="Override data directory")
def list(repo, data_dir):
    """List all memory entries for a project."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = MemoryStore(ddir)
    entries = store.get_all(repo)
    if not entries:
        click.echo(f"No memory entries for {repo}")
        return
    click.echo(f"Memory for {repo}:")
    for entry in entries:
        click.echo(f"  [{entry.category}] {entry.key}: {entry.value}")


@memory.command()
@click.argument("repo")
@click.argument("key")
@click.option("--data-dir", default=None, help="Override data directory")
def remove(repo, key, data_dir):
    """Remove a memory entry."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = MemoryStore(ddir)
    store.remove(repo, key)
    click.echo(f"Memory entry '{key}' removed.")


@memory.command()
@click.argument("repo")
@click.option("--data-dir", default=None, help="Override data directory")
def clear(repo, data_dir):
    """Clear all memory for a project."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = MemoryStore(ddir)
    store.clear(repo)
    click.echo(f"All memory cleared for {repo}.")


@memory.command()
@click.option("--data-dir", default=None, help="Override data directory")
def projects(data_dir):
    """List all projects with stored memory."""
    config = load_config()
    ddir = get_data_dir(config, data_dir)
    store = MemoryStore(ddir)
    projects = store.list_projects()
    if not projects:
        click.echo("No projects with stored memory.")
        return
    click.echo("Projects with stored memory:")
    for p in projects:
        click.echo(f"  {p}")


if __name__ == "__main__":
    cli()