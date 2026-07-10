import os
import asyncio
import logging
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from harness.core.task import load_task_config, TaskStatus
from harness.core.task_manager import TaskManager
from harness.report.generator import ReportGenerator
from harness.storage.db import TaskStore
from harness.storage.files import FileStore
from harness.observer.base import Observer
from harness.observer.stream import StreamObserver
from harness.observer.logger import LogObserver
from harness.credentials import CredentialManager

logger = logging.getLogger(__name__)

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coding Agent Harness</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
.container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid #1e293b; }
header h1 { font-size: 1.5rem; font-weight: 700; color: #f8fafc; }
header span { color: #38bdf8; }
.card { background: #1e293b; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #334155; }
.card h2 { font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; color: #f1f5f9; }
table { width: 100%; border-collapse: collapse; }
th { text-align: left; padding: 0.75rem; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; border-bottom: 1px solid #334155; }
td { padding: 0.75rem; border-bottom: 1px solid #1e293b; font-size: 0.875rem; }
tr:hover { background: #1e293b; }
tr { cursor: pointer; }
.form-row { display: flex; gap: 0.75rem; align-items: flex-end; }
.form-group { flex: 1; display: flex; flex-direction: column; gap: 0.25rem; }
.form-group label { font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; }
.form-group input { padding: 0.5rem 0.75rem; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; font-size: 0.875rem; }
.form-group input:focus { outline: none; border-color: #38bdf8; }
.btn { padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.875rem; font-weight: 500; cursor: pointer; border: none; transition: background 0.15s; }
.btn-primary { background: #0284c7; color: white; }
.btn-primary:hover { background: #0369a1; }
.btn-danger { background: #dc2626; color: white; }
.btn-danger:hover { background: #b91c1c; }
.badge { display: inline-block; padding: 0.125rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; }
.badge-pending { background: #475569; color: #e2e8f0; }
.badge-running { background: #1d4ed8; color: #dbeafe; }
.badge-done { background: #15803d; color: #dcfce7; }
.badge-failed { background: #dc2626; color: #fee2e2; }
.badge-cancelled { background: #a16207; color: #fef3c7; }
.detail-panel { display: none; }
.detail-panel.active { display: block; }
.detail-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }
.detail-item { padding: 0.5rem; }
.detail-item dt { font-size: 0.75rem; color: #94a3b8; text-transform: uppercase; }
.detail-item dd { font-size: 0.875rem; margin-top: 0.125rem; }
.error-msg { background: #7f1d1d; border: 1px solid #dc2626; color: #fca5a5; padding: 0.75rem; border-radius: 6px; margin-bottom: 1rem; display: none; }
.error-msg.show { display: block; }
.empty-state { text-align: center; padding: 3rem; color: #64748b; }
.refresh-info { font-size: 0.75rem; color: #64748b; }
</style>
</head>
<body>
<div class="container">
<header>
<h1>Coding Agent <span>Harness</span></h1>
<div class="refresh-info" id="refreshInfo">Auto-refresh: 3s</div>
</header>

<div class="error-msg" id="errorMsg"></div>

<div class="card">
<h2>Run New Task</h2>
<form id="runForm" class="form-row">
<div class="form-group">
<label for="taskFile">Task YAML Path</label>
<input type="text" id="taskFile" placeholder="tasks/my-task.yaml" required>
</div>
<button type="submit" class="btn btn-primary" id="runBtn">Run Task</button>
</form>
</div>

<div class="card">
<h2>Tasks</h2>
<div id="taskTableContainer">
<table>
<thead>
<tr><th>ID</th><th>Name</th><th>Status</th><th>Turns</th><th>Tokens</th><th>Created</th><th></th></tr>
</thead>
<tbody id="taskTableBody">
</tbody>
</table>
</div>
<div class="empty-state" id="emptyState" style="display:none">No tasks found. Run a task to get started.</div>
</div>

<div class="card detail-panel" id="detailPanel">
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
<h2 id="detailTitle">Task Detail</h2>
<div>
<button class="btn btn-danger" id="cancelBtn" style="display:none">Cancel</button>
<button class="btn" style="background:#334155;color:#e2e8f0;margin-left:0.5rem" onclick="closeDetail()">Close</button>
</div>
</div>
<dl class="detail-grid" id="detailGrid"></dl>
</div>
</div>

<script>
let currentTaskId = null;
let pollTimer = null;

function statusBadge(status) {
const map = {pending:'badge-pending',running:'badge-running',done:'badge-done',failed:'badge-failed',cancelled:'badge-cancelled'};
return `<span class="badge ${map[status] || 'badge-pending'}">${status}</span>`;
}

function formatDate(d) { if (!d) return '-'; return new Date(d).toLocaleString(); }

async function loadTasks() {
try {
const resp = await fetch('/api/tasks');
const tasks = await resp.json();
const tbody = document.getElementById('taskTableBody');
const empty = document.getElementById('emptyState');
if (tasks.length === 0) { tbody.innerHTML = ''; empty.style.display = 'block'; }
else { empty.style.display = 'none'; }
tbody.innerHTML = tasks.map(t => `
<tr onclick="showDetail('${t.id}')">
<td style="font-family:monospace;font-size:0.8rem">${t.id}</td>
<td>${t.name}</td>
<td>${statusBadge(t.status)}</td>
<td>${t.turns || '-'}</td>
<td>${t.tokens_used || '-'}</td>
<td style="font-size:0.8rem;color:#94a3b8">${formatDate(t.created_at)}</td>
<td><button class="btn btn-danger" style="padding:0.25rem 0.5rem;font-size:0.75rem" onclick="event.stopPropagation();cancelTask('${t.id}')" ${t.status==='running'||t.status==='pending'?'':'disabled'}>Cancel</button></td>
</tr>
`).join('');
} catch(e) { showError('Failed to load tasks: ' + e.message); }
}

async function showDetail(taskId) {
currentTaskId = taskId;
try {
const resp = await fetch('/api/tasks/' + taskId);
if (!resp.ok) throw new Error('Task not found');
const t = await resp.json();
document.getElementById('detailPanel').classList.add('active');
document.getElementById('detailTitle').textContent = t.id + ' - ' + t.name;
document.getElementById('detailGrid').innerHTML = `
<div class="detail-item"><dt>Status</dt><dd>${statusBadge(t.status)}</dd></div>
<div class="detail-item"><dt>Model</dt><dd>${t.model}</dd></div>
<div class="detail-item"><dt>Repo</dt><dd style="font-size:0.8rem">${t.repo}</dd></div>
<div class="detail-item"><dt>Branch</dt><dd>${t.branch}</dd></div>
<div class="detail-item"><dt>Created</dt><dd>${formatDate(t.created_at)}</dd></div>
<div class="detail-item"><dt>Started</dt><dd>${formatDate(t.started_at)}</dd></div>
<div class="detail-item"><dt>Finished</dt><dd>${formatDate(t.finished_at)}</dd></div>
<div class="detail-item"><dt>Turns</dt><dd>${t.turns || '-'}</dd></div>
<div class="detail-item"><dt>Tokens</dt><dd>${t.tokens_used || '-'}</dd></div>
${t.error ? `<div class="detail-item"><dt>Error</dt><dd style="color:#fca5a5">${t.error}</dd></div>` : ''}
`;
const cancelBtn = document.getElementById('cancelBtn');
if (t.status === 'running' || t.status === 'pending') {
cancelBtn.style.display = 'inline-block';
cancelBtn.onclick = () => cancelTask(taskId);
} else { cancelBtn.style.display = 'none'; }
} catch(e) { showError(e.message); }
}

function closeDetail() { document.getElementById('detailPanel').classList.remove('active'); currentTaskId = null; }

async function cancelTask(taskId) {
try {
const resp = await fetch('/api/tasks/' + taskId + '/cancel', { method: 'POST' });
if (resp.ok) { loadTasks(); if (currentTaskId === taskId) showDetail(taskId); }
else { const err = await resp.json(); showError(err.detail); }
} catch(e) { showError('Cancel failed: ' + e.message); }
}

document.getElementById('runForm').addEventListener('submit', async (e) => {
e.preventDefault();
const btn = document.getElementById('runBtn');
const file = document.getElementById('taskFile').value.trim();
if (!file) return;
btn.disabled = true; btn.textContent = 'Running...';
try {
const resp = await fetch('/api/tasks/run', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({task_file: file}) });
const data = await resp.json();
if (resp.ok) { document.getElementById('taskFile').value = ''; loadTasks(); }
else { showError(data.detail || 'Failed to start task'); }
} catch(e) { showError('Failed: ' + e.message); }
btn.disabled = false; btn.textContent = 'Run Task';
});

function showError(msg) {
const el = document.getElementById('errorMsg');
el.textContent = msg; el.classList.add('show');
setTimeout(() => el.classList.remove('show'), 5000);
}

loadTasks();
pollTimer = setInterval(loadTasks, 3000);
</script>
</body>
</html>"""


class RunTaskRequest(BaseModel):
    task_file: str


def create_app(data_dir: str = None) -> FastAPI:
    if data_dir is None:
        data_dir = os.environ.get("HARNESS_DATA_DIR", "./data")

    app = FastAPI(title="Coding Agent Harness", version="0.1.0")

    store = TaskStore(data_dir)
    file_store = FileStore(data_dir)
    report_gen = ReportGenerator(store, file_store)

    creds = CredentialManager()
    try:
        api_key = creds.get_api_key()
    except Exception:
        api_key = os.environ.get("OPENAI_API_KEY")

    observer = Observer()
    log_path = os.path.join(data_dir, "harness.log")
    os.makedirs(data_dir, exist_ok=True)
    observer.subscribe(StreamObserver())
    observer.subscribe(LogObserver(log_path))

    manager = TaskManager(
        task_store=store,
        file_store=file_store,
        observer=observer,
        data_dir=data_dir,
        api_key=api_key,
    )

    app.state.manager = manager
    app.state.store = store
    app.state.report_gen = report_gen

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        return DASHBOARD_TEMPLATE

    @app.get("/api/tasks")
    async def list_tasks(status: str = Query(None)):
        tasks = store.list_all(status=status)
        return tasks

    @app.get("/api/tasks/{task_id}")
    async def get_task(task_id: str):
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return task

    @app.post("/api/tasks/run")
    async def run_task(req: RunTaskRequest):
        task_file = req.task_file
        if not os.path.exists(task_file):
            raise HTTPException(status_code=400, detail=f"Task file not found: {task_file}")

        try:
            task = load_task_config(task_file)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid task config: {e}")

        asyncio.create_task(manager.run(task, task_file))

        return JSONResponse(status_code=202, content={"task_id": task.id, "status": "accepted"})

    @app.get("/api/tasks/{task_id}/report")
    async def get_report(task_id: str):
        try:
            report = report_gen.generate(task_id)
        except ValueError:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        return report

    @app.post("/api/tasks/{task_id}/cancel")
    async def cancel_task(task_id: str):
        task = store.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
        manager.cancel(task_id)
        return {"task_id": task_id, "status": "cancelled"}

    return app


def run_server(host: str = "0.0.0.0", port: int = 8000, data_dir: str = None):
    import uvicorn
    app = create_app(data_dir=data_dir)
    uvicorn.run(app, host=host, port=port, log_level="info")