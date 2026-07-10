# Coding Agent Harness

A CLI tool for orchestrating OpenAI-powered coding agents to fix bugs inside Docker sandboxes. Define tasks in YAML, run agents in isolated containers, and review results with structured reports.

**Who it's for**: developers and QA engineers who want to automate bug-fixing workflows with LLM agents in a safe, reproducible environment.

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for sandbox containers)

### Installation

```bash
git clone <repo-url>
cd coding-agent-harness
pip install -e .
```

### Setup

```bash
# Store your OpenAI API key in the OS keyring
harness credentials setup

# Or use an environment variable
export OPENAI_API_KEY=sk-...
```

### Run a Task

```bash
harness run tasks/example-bug.yaml
```

The agent will clone the target repo into a Docker sandbox, explore the codebase, apply fixes, and verify the result.

```bash
# View task status
harness status
harness status <task-id> --json

# Generate a report
harness report <task-id>
harness report <task-id> --verbose
harness report <task-id> --diff

# List all tasks
harness list
harness list --status running

# Cancel a running task
harness cancel <task-id>

# View current config
harness config
```

## Credential Management

The API key is **never embedded in the Docker image**. Use one of these methods:

| Method | Command | Best for |
|--------|---------|----------|
| OS keyring | `harness credentials setup` | Desktop use |
| Environment variable | `export OPENAI_API_KEY=sk-...` | Docker, CI |
| `.env` file | Create `.env` with `OPENAI_API_KEY=sk-...` | Local development |

```bash
harness credentials setup    # Interactive guided setup
harness credentials status   # List stored services (no plaintext)
harness credentials update <service>
harness credentials clear --all
```

The credential lookup order is: OS keyring → environment variable → `.env` file.

## Task Format

Define bug-fix tasks in YAML:

```yaml
id: "fix-division-by-zero"
name: "Fix Division by Zero"
description: |
  The `divide` function crashes when denominator is 0.
repo: "https://github.com/user/repo"
branch: "main"

environment:
  image: "python:3.11-alpine"
  setup_commands:
    - "pip install pytest"

agent:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 600
  blocked_commands: []

verification:
  commands:
    - "pytest tests/"
```

## Docker Distribution

### Build

```bash
docker build -t harness:latest .
```

### Run

```bash
# Pass credentials via environment variable (never in the image)
docker run --rm \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/tasks:/app/tasks \
  -v $(pwd)/data:/app/data \
  harness:latest run tasks/example-bug.yaml
```

The harness container needs access to the host Docker socket (`/var/run/docker.sock`) to spawn sandbox containers. Mount your task files and data directory for persistence.

### With `.env` file

```bash
docker run --rm \
  --env-file .env \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/tasks:/app/tasks \
  -v $(pwd)/data:/app/data \
  harness:latest run tasks/example-bug.yaml
```

## Directory Structure

```
├── config.yaml              # Default configuration
├── pyproject.toml           # Project metadata and dependencies
├── tasks/                   # Task definition files (YAML)
│   └── example-bug.yaml
├── harness/
│   ├── cli/                 # Click CLI commands
│   ├── core/                # Task model, AgentLoop, TaskManager
│   ├── adapters/            # AI model adapters (OpenAI)
│   ├── sandbox/             # Docker sandbox abstraction
│   ├── tools/               # Agent tools (shell, file ops, etc.)
│   ├── observer/            # Event streaming and logging
│   ├── report/              # Report generation
│   ├── storage/             # SQLite task store + file store
│   └── credentials.py       # OS keyring credential management
├── tests/                   # pytest test suite
├── data/                    # Runtime data (git ignored)
├── reports/                 # Generated reports
└── docs/                    # Design docs and plans
```

## Known Limitations

- **Windows-only keyring**: `harness credentials setup` uses the OS keyring, which may not work in headless Linux containers. Use `OPENAI_API_KEY` environment variable or `.env` file in Docker/CI environments.
- **Docker required for sandbox**: All agent tasks run inside Docker containers. The sandbox layer requires a running Docker daemon and access to the Docker socket.
- **Single agent per task**: Each task runs one agent. No parallel or multi-agent orchestration.
- **Keyring on headless Linux**: `harness credentials setup` requires a keyring backend. On headless Linux, use `OPENAI_API_KEY` environment variable or `.env` file instead.

## Deployment

### WebUI (Render)

This project includes a FastAPI WebUI (`harness web`). To deploy on Render:

1. Fork this repo
2. Create a new Web Service on [Render](https://render.com)
3. Connect your repo and use the settings from `render.yaml`
4. Set the `OPENAI_API_KEY` environment variable in Render dashboard

**Deployed URL**: [待部署后填写]

### Docker

```bash
docker build -t harness .
docker run -it -v /var/run/docker.sock:/var/run/docker.sock harness --help
```

Note: The harness needs Docker socket access to create sandbox containers.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.11+ |
| CLI | Click |
| AI | OpenAI API (GPT-4o) |
| Sandbox | Docker |
| Config | YAML |
| Storage | SQLite, JSONL |
| Credentials | keyring, python-dotenv |
| Version control | GitPython |

## License

MIT