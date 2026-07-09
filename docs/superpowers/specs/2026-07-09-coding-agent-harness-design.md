# Coding Agent Harness 设计文档

> 日期：2026-07-09
> 状态：已确认
> 版本：1.0

## 1. 概述

### 1.1 目标

构建一个 **Bug 修复型 Agent 编排与运行框架**。用户通过结构化任务定义（YAML）提交 Bug 修复任务，Harness 在 Docker 沙箱中驱动 AI Agent 执行工具调用循环，自动分析代码、定位问题、修改代码，最终产出 diff 和执行报告。

### 1.2 核心原则

- **先单机 CLI，预留服务化扩展**：第一版为本地 CLI 工具，架构层面为后续服务化留好接口
- **模块化插件架构**：组件间通过清晰接口通信，适配器、工具、沙箱均可替换扩展
- **YAGNI**：第一版专注核心流程，不提前实现非必需功能

### 1.3 需求全景

| 维度 | 决策 |
|------|------|
| 核心用途 | Bug 修复型 Agent 编排与运行框架 |
| Agent 类型 | 仅 API Agent（首版 OpenAI，架构预留扩展） |
| 工作模式 | 单任务模式，异步执行，预留并发 |
| 环境 | Docker 容器 + Volume 挂载，预配置环境 |
| 仓库交互 | 混合模式（Agent 自由读写文件，Harness 追踪变更） |
| 任务定义 | YAML 任务文件，`tasks/` 目录组织 |
| Agent Loop | Harness 驱动工具调用循环 |
| 工具集 | 可扩展工具注册（文件读写、shell、搜索、git 等） |
| 上下文 | 摘要注入 + 按需获取 |
| 状态存储 | SQLite（元数据）+ 文件（日志/diff） |
| 报告 | 分层报告（默认摘要、--verbose 详细、--json 结构化） |
| 可观测性 | 实时流式输出 + 结构化日志 |
| 安全 | 信任模式 + 可配置命令拦截 |
| 部署 | 单机 CLI 优先，架构预留服务化扩展 |
| 技术栈 | Python 3.11+ |

---

## 2. 架构方案

采用 **核心 + 插件架构**：

```
CLI 层
  ↓
TaskManager（任务生命周期管理）
  ↓
AgentLoop（核心循环引擎）
  ├── Adapter（OpenAI）
  ├── ToolRegistry（可注册工具）
  ├── Sandbox（Docker 容器管理）
  └── Observer（日志/流式输出/事件钩子）
  ↓
Storage（SQLite + File）
ReportGenerator
```

### 2.1 目录结构

```
my_coding_agent_harness/
├── tasks/                    # 任务定义文件 (YAML)
├── reports/                  # 输出报告
├── data/                     # 运行时数据（SQLite + 日志 + diff）
├── harness/                  # 核心包
│   ├── cli/                  # CLI 入口
│   │   ├── main.py           # 命令注册 (run, status, report, list, cancel, config)
│   │   └── formatters.py     # 终端输出格式化 (表格、颜色、进度条)
│   ├── core/                 # 核心引擎
│   │   ├── task.py           # 任务定义模型 (YAML → Task dataclass)
│   │   ├── agent_loop.py     # Agent 工具调用循环
│   │   ├── task_manager.py   # 任务生命周期管理 (创建/运行/取消/状态)
│   │   └── context.py        # 仓库上下文构建 (摘要注入)
│   ├── adapters/             # Agent API 适配器
│   │   ├── base.py           # 抽象基类 (Adapter interface)
│   │   └── openai.py         # OpenAI 适配器实现
│   ├── tools/                # 可扩展工具注册
│   │   ├── registry.py       # 工具注册表 + 工具定义
│   │   ├── files.py          # 文件读写工具
│   │   ├── shell.py          # Shell 命令执行工具
│   │   ├── search.py         # 代码搜索工具 (grep/glob)
│   │   └── git.py            # Git 操作工具 (diff/log/branch)
│   ├── sandbox/              # 沙箱环境管理
│   │   ├── base.py           # Sandbox 抽象接口
│   │   ├── docker.py         # Docker SDK 封装 (创建/启动/exec/停止)
│   │   └── guard.py          # 可配置命令拦截
│   ├── storage/              # 持久化层
│   │   ├── db.py             # SQLite 操作 (任务状态、元数据)
│   │   └── files.py          # 文件存储 (日志、diff)
│   ├── observer/             # 可观测性
│   │   ├── base.py           # Observer 事件总线 + 事件定义
│   │   ├── stream.py         # 终端实时流式输出
│   │   └── logger.py         # 结构化日志写入
│   └── report/               # 报告生成
│       ├── generator.py      # 报告生成器 (摘要/详细/JSON)
│       └── templates.py      # 报告模板
├── tests/                    # 测试
├── config.yaml               # 全局配置 (默认 Agent、超时、Docker 等)
├── pyproject.toml
└── README.md
```

### 2.2 核心数据流

```
1. CLI: harness run tasks/bug-123.yaml
         ↓
2. TaskManager: 加载 YAML → 创建 Task 对象 → 写入 SQLite (status=pending)
         ↓
3. TaskManager: 启动 Docker 容器 → 挂载仓库 volume
         ↓
4. AgentLoop: 构建初始上下文 (仓库摘要) → 调用 Adapter.chat()
         ↓
5. Adapter: 返回响应 (文本/工具调用) → AgentLoop 解析
         ↓
6. 如果是工具调用 → ToolRegistry 找到工具 → 在容器内执行 → 结果回传
         ↓
7. 重复 5-6 直到 Agent 返回最终文本 (无工具调用)
         ↓
8. AgentLoop: 收集 diff → 写入 SQLite (status=done) → 停止容器
         ↓
9. ReportGenerator: 生成报告 → 输出到终端 + 写入 reports/
```

---

## 3. Task 定义模型

### 3.1 YAML 格式

```yaml
# tasks/bug-123.yaml
id: "bug-123"
name: "修复用户登录超时问题"
description: |
  用户反馈登录后约 30 秒自动登出，
  检查 session 过期逻辑和 token 刷新机制。
  涉及的模块：auth/session.py, middleware/auth.py
repo: "https://github.com/example/myapp"
branch: "main"
base_commit: "abc1234"           # 可选，指定修复起点

environment:
  image: "python:3.11"           # Docker 镜像
  setup_commands:                # 容器启动后执行的初始化命令
    - "pip install -r requirements.txt"
    - "pip install pytest"

agent:
  model: "gpt-4o"                # 模型名称
  max_turns: 30                  # 最大工具调用轮次
  temperature: 0.0

sandbox:
  workdir: "/workspace"          # 容器内工作目录
  timeout: 600                   # 任务总超时(秒)
  blocked_commands:               # 可选的命令黑名单
    - "rm -rf /"
    - "shutdown"

verification:                     # 可选：任务完成后的验证步骤
  commands:
    - "pytest tests/auth/test_session.py"
```

### 3.2 Python 数据类

```python
@dataclass
class TaskConfig:
    id: str
    name: str
    description: str
    repo: str
    branch: str
    base_commit: Optional[str]
    environment: EnvironmentConfig
    agent: AgentConfig
    sandbox: SandboxConfig
    verification: Optional[VerificationConfig]

@dataclass
class EnvironmentConfig:
    image: str
    setup_commands: list[str]

@dataclass
class AgentConfig:
    model: str
    max_turns: int
    temperature: float

@dataclass
class SandboxConfig:
    workdir: str
    timeout: int
    blocked_commands: list[str]
```

### 3.3 任务状态流转

```
pending → running → done / failed / cancelled
                ↓
              running → (可被取消)
```

- `pending`: 任务已加载，等待执行
- `running`: Docker 容器已启动，AgentLoop 正在运行
- `done`: 正常完成，diff 已收集
- `failed`: 异常退出（超时、API 错误、容器崩溃等）
- `cancelled`: 用户手动取消

---

## 4. AgentLoop 核心引擎

### 4.1 循环流程

```
1. 构建初始 messages:
   [system_prompt, repo_context_summary, task_description]

2. 调用 Adapter.chat(messages) → 返回 response

3. 解析 response:
   ├── 纯文本 (无 tool_calls) → 循环结束，任务完成
   └── 包含 tool_calls → 进入步骤 4

4. 每个 tool_call:
   ├── ToolRegistry.lookup(tool_name) → 找到工具
   ├── Guard.check(tool_name, args) → 安全检查
   ├── tool.execute(args, sandbox=container) → 在容器内执行
   ├── Observer.emit("tool_call", {name, args, result}) → 流式输出
   └── 将结果追加到 messages

5. 检查终止条件:
   ├── 达到 max_turns → 强制结束，标记为 failed
   ├── 达到 timeout → 强制结束，标记为 failed
   └── 未达上限 → 回到步骤 2

6. 任务完成:
   ├── 执行 sandbox.exec("git diff") → 收集 diff
   └── 返回 LoopResult
```

### 4.2 核心接口

```python
class AgentLoop:
    def __init__(
        self,
        adapter: BaseAdapter,
        tools: ToolRegistry,
        sandbox: Sandbox,
        observer: Observer,
        config: AgentConfig,
    ):
        ...

    async def run(self, task: TaskConfig) -> LoopResult:
        """执行完整的 Agent 工具调用循环，返回结果"""
        ...

@dataclass
class LoopResult:
    status: Literal["done", "failed", "cancelled"]
    diff: str
    turns: int
    tokens_used: int
    messages: list[dict]
    tool_calls: list[ToolCallRecord]
    error: Optional[str]
```

### 4.3 Adapter 抽象接口

```python
class BaseAdapter(ABC):
    @abstractmethod
    async def chat(
        self, messages: list[dict], tools: list[dict]
    ) -> AdapterResponse:
        """发送消息，返回模型响应"""
        ...

@dataclass
class AdapterResponse:
    content: Optional[str]
    tool_calls: list[ToolCall]
    finish_reason: str
    usage: TokenUsage

@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict
```

### 4.4 Observer 事件系统

```python
class Observer:
    """发布/订阅模式的事件总线"""
    def emit(self, event: Event): ...

# 事件类型
@dataclass
class TurnStart: turn_number: int
@dataclass
class ToolCallStart: tool_name: str; args: dict
@dataclass
class ToolCallEnd: tool_name: str; result: str; duration: float
@dataclass
class AgentThinking: content: str
@dataclass
class LoopError: error: str
@dataclass
class LoopComplete: result: LoopResult
```

---

## 5. 工具系统

### 5.1 Tool 接口

```python
class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict:       # JSON Schema (OpenAI function calling)
        """返回 OpenAI function calling 兼容的参数定义"""
        ...

    @abstractmethod
    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        """在 sandbox 内执行工具，返回结果"""
        ...

@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None
```

### 5.2 内置工具清单

| 工具 | 功能 | 关键参数 |
|------|------|----------|
| `read_file` | 读取文件内容 | `path`, `offset`, `limit` |
| `write_file` | 写入/覆盖文件 | `path`, `content` |
| `edit_file` | 精确字符串替换 | `path`, `old_str`, `new_str` |
| `run_shell` | 执行 shell 命令 | `command`, `workdir` |
| `search_content` | 正则搜索文件内容 | `pattern`, `path`, `include` |
| `search_files` | 文件名 glob 搜索 | `pattern`, `path` |
| `git_diff` | 查看当前变更 | (无) |
| `git_log` | 查看提交历史 | `count` |
| `list_dir` | 列出目录内容 | `path` |

### 5.3 ToolRegistry

```python
class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool): ...
    def unregister(self, name: str): ...
    def get(self, name: str) -> Tool: ...
    def get_all(self) -> list[Tool]: ...
    def to_openai_schema(self) -> list[dict]:
        """将所有已注册工具转为 OpenAI function calling schema"""
        ...
```

### 5.4 工具执行流程

```
AgentLoop 收到 tool_calls
  → 对每个 tool_call:
    1. ToolRegistry.get(tool_call.name)
    2. Guard.check(tool_call.name, args)
    3. tool.execute(args, sandbox)
    4. 截断过长输出（>8000 字符截断 + 提示）
    5. 返回 ToolResult → 追加到 messages
```

---

## 6. Sandbox 沙箱管理

### 6.1 Sandbox 抽象接口

```python
class Sandbox(ABC):
    @abstractmethod
    async def create(self, image: str, workdir: str, repo_path: str) -> str:
        """创建容器，挂载仓库 volume，返回 container_id"""
        ...

    @abstractmethod
    async def exec(self, container_id: str, command: str, workdir: str = None) -> ExecResult:
        """在容器内执行命令"""
        ...

    @abstractmethod
    async def read_file(self, container_id: str, path: str) -> str:
        """从容器内读取文件"""
        ...

    @abstractmethod
    async def write_file(self, container_id: str, path: str, content: str):
        """向容器内写入文件"""
        ...

    @abstractmethod
    async def setup(self, container_id: str, commands: list[str]):
        """执行初始化命令"""
        ...

    @abstractmethod
    async def stop(self, container_id: str):
        """停止并删除容器"""
        ...

@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str
```

### 6.2 容器生命周期

```
TaskManager.run(task):
  1. docker pull task.environment.image
  2. 克隆仓库到本地临时目录
  3. sandbox.create(image, workdir, repo_local_path)
  4. sandbox.setup(container_id, task.environment.setup_commands)
  5. AgentLoop.run(task)  ← 在容器内执行
  6. sandbox.exec("git diff") → 收集 diff
  7. sandbox.stop(container_id)
  8. 清理临时仓库目录
```

### 6.3 Guard 命令拦截

```python
class CommandGuard:
    def __init__(self, blocked_patterns: list[str]):
        self.blocked_patterns = blocked_patterns

    def check(self, tool_name: str, args: dict) -> bool:
        """检查工具调用是否安全，不安全则抛出 GuardBlockedError"""
        if tool_name == "run_shell":
            command = args.get("command", "")
            for pattern in self.blocked_patterns:
                if pattern in command:
                    raise GuardBlockedError(
                        f"Command blocked: {command} matches pattern '{pattern}'"
                    )
        return True
```

---

## 7. Storage 持久化层

### 7.1 SQLite 表结构

```sql
CREATE TABLE tasks (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'pending',
    repo        TEXT NOT NULL,
    branch      TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    turns       INTEGER,
    tokens_used INTEGER,
    error       TEXT,
    task_file   TEXT NOT NULL
);

CREATE TABLE tool_calls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL REFERENCES tasks(id),
    turn_number INTEGER NOT NULL,
    tool_name   TEXT NOT NULL,
    args        TEXT NOT NULL,
    result      TEXT,
    duration_ms INTEGER,
    success     INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 7.2 文件存储结构

```
data/
├── harness.db
├── tasks/
│   └── {task_id}/
│       ├── messages.jsonl
│       ├── tool_calls.jsonl
│       ├── diff.patch
│       └── agent.log
```

### 7.3 存储路径

默认 `data/` 目录位于项目根目录（或当前执行路径），支持通过 `config.yaml` 的 `storage.data_dir` 或 CLI 参数 `--data-dir` 覆盖。

---

## 8. CLI 命令行接口

### 8.1 命令概览

```bash
harness run <task-file>          # 执行一个任务
harness status [task-id]         # 查看任务状态
harness report <task-id>         # 生成/查看报告
harness list                     # 列出所有任务
harness cancel <task-id>         # 取消运行中的任务
harness config                   # 显示当前配置
```

### 8.2 详细参数

```bash
harness run tasks/bug-123.yaml
harness run tasks/bug-123.yaml --verbose          # 实时流式输出
harness run tasks/bug-123.yaml --no-stream        # 静默执行
harness run tasks/bug-123.yaml --data-dir ./my_data

harness status                  # 列出所有任务（表格）
harness status --status running # 按状态筛选
harness status bug-123          # 显示单个任务详情
harness status bug-123 --json   # JSON 格式输出

harness report bug-123          # 默认摘要
harness report bug-123 --verbose   # 详细报告（含对话日志）
harness report bug-123 --json      # 结构化 JSON 输出
harness report bug-123 --diff      # 只输出 diff

harness list                    # 所有任务
harness list --status done      # 按状态筛选
harness list --limit 10         # 最近 10 条

harness cancel bug-123
harness config
harness config --path           # 只显示配置文件路径
```

### 8.3 全局配置 config.yaml

```yaml
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
```

---

## 9. 错误处理

| 场景 | 处理方式 |
|------|----------|
| Docker 未安装/未启动 | 启动阶段报错，给出明确提示，终止任务 |
| 镜像拉取失败 | 重试 1 次，仍失败则终止，标记 failed |
| 仓库克隆失败 | 终止任务，标记 failed |
| 初始化命令执行失败 | 记录 stderr，继续执行 |
| OpenAI API 调用失败 | 自动重试 3 次（指数退避），仍失败则终止 |
| API 返回 rate limit | 等待 Retry-After 头指示的时间后重试 |
| 工具执行超时 | 单个工具超时 30 秒，超时则截断，继续循环 |
| 任务总超时 | 给 Agent 发送"超时"消息，再给 1 轮机会，然后强制停止 |
| Guard 拦截命令 | 返回错误消息给 Agent，不终止循环 |
| 容器崩溃 | 尝试重启容器 1 次，失败则终止 |
| 用户 Ctrl+C | 优雅关闭：停止容器，保存日志，标记 cancelled |
| 数据库写入失败 | 记录到 stderr，不阻塞主流程 |

---

## 10. 技术栈

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 用户偏好 |
| 异步框架 | `asyncio` | 标准库 |
| OpenAI SDK | `openai` | 首版只支持 OpenAI |
| Docker | `docker-py` | Python Docker SDK |
| 数据库 | `sqlite3` | 标准库，零依赖 |
| CLI 框架 | `click` | 功能丰富，装饰器风格 |
| YAML | `pyyaml` | 任务文件解析 |
| Git | `gitpython` | 仓库操作 |
| 测试 | `pytest` + `pytest-asyncio` | 标准方案 |
| 包管理 | `pyproject.toml` + `pip` | 现代 Python 标准 |

---

## 11. 不在第一版范围

- Web Dashboard
- 多任务并发执行
- Anthropic / 其他模型适配器
- Dev Container 支持
- 环境快照保存/恢复
- 自定义工具的热加载（支持代码注册，不支持配置文件热加载）
- 任务结果对比评测