# SPEC.md — Coding Agent Harness

> 版本：2.0 | 日期：2026-07-09 | 状态：已确认

---

## 1. 问题陈述

### 1.1 要解决的问题

AI 编码智能体（如 Claude Code、OpenCode、GitHub Copilot）在单次对话中表现出色，但缺乏一个**系统化的编排框架**来：管理执行环境、追踪变更、收集反馈信号、在出错时自我修正。工程师需要的是一个"测试平台"——能够用标准化的任务定义、隔离的执行环境、确定性的反馈机制来驱动和评测 AI 编码智能体。

### 1.2 目标用户

- **AI/SE 研究者**：需要对比不同 LLM 在代码修复任务上的表现
- **软件工程师**：需要自动化重复性的 bug 修复工作流
- **开源项目维护者**：需要快速验证社区提交的 bug 报告

### 1.3 为什么值得做

当前市场上的 agent 框架（LangChain、AutoGen 等）提供了高层抽象，但：
1. 将核心循环（agent loop）隐藏在框架内部，用户无法修改或验证
2. 反馈机制通常是"让 LLM 自己检查"的提示词，而非确定性的代码
3. 缺乏对凭据安全、分发、可复现测试的工程化考量

本项目构建一个**从零实现的 harness 内核**，将工程师的控制权归还到代码层面。

---

## 2. 用户故事

### US1: 提交 Bug 修复任务
> 作为一名研究者，我希望通过一个 YAML 文件定义 Bug 修复任务（仓库地址、问题描述、环境配置），然后一键执行，获得结构化的执行报告。

**验收标准**：`harness run tasks/bug.yaml` 成功执行，产出 diff + 报告。

### US2: 查看任务执行过程
> 作为一名工程师，我希望在 Agent 执行任务时实时看到它的思考过程和工具调用，以便理解它的决策逻辑。

**验收标准**：`harness run --verbose` 实时流式输出 Agent 思考和工具调用。

### US3: 安全配置凭据
> 作为一名用户，我希望 API Key 不会被写入源码、配置文件或日志，而是安全地存储在操作系统钥匙串中。

**验收标准**：`harness credentials setup` 引导隐藏输入 Key，`harness credentials status` 只显示服务名不显示明文。

### US4: 查看历史任务
> 作为一名研究者，我希望查看所有历史任务的执行状态、耗时、token 消耗，并能按状态筛选。

**验收标准**：`harness list` 和 `harness status` 正确显示所有任务。

### US5: 生成详细报告
> 作为一名工程师，我希望获得包含完整对话日志、diff、工具调用记录的详细报告，支持多种输出格式。

**验收标准**：`harness report <id> --verbose` 和 `harness report <id> --json` 输出正确。

### US6: 危险操作拦截
> 作为一名用户，我希望 Agent 在执行危险 shell 命令（如 `rm -rf /`）时被自动拦截，不会对系统造成损害。

**验收标准**：Agent 尝试执行 `rm -rf /` 时被 `CommandGuard` 拦截，返回错误信息但不终止任务。

### US7: 反馈驱动的自我修正
> 作为一名研究者，我希望 Agent 在工具执行失败后能收到失败反馈，并据此调整下一步动作。

**验收标准**：注入一次工具失败，Agent 的下一次响应包含对失败的引用和修正策略。

### US8: 跨会话记忆
> 作为一名用户，我希望 Harness 能记住项目约定和历史决策，在新的任务中按需提供给 Agent。

**验收标准**：存储项目记忆后，新任务的 Agent 初始 prompt 中包含记忆内容。

---

## 3. 功能规约

### 3.1 任务定义模块

- **输入**：YAML 任务文件（路径）
- **行为**：解析 YAML → 验证字段 → 返回 `TaskConfig` 数据类
- **输出**：`TaskConfig` 实例或验证错误
- **边界条件**：缺少必填字段、YAML 格式错误、空文件 → 明确错误信息
- **错误处理**：`FileNotFoundError`、`yaml.YAMLError`、`KeyError` → 包装为描述性异常

### 3.2 Agent 主循环

- **输入**：`TaskConfig`、`BaseAdapter`、`ToolRegistry`、`Sandbox`、`CommandGuard`、`Observer`
- **行为**：构建上下文 → 调用 LLM → 解析响应 → 分发工具执行 → 回灌结果 → 循环直到完成或超限
- **输出**：`LoopResult`（status, diff, turns, tokens_used, messages, tool_calls, error）
- **边界条件**：max_turns=0（立即返回失败）、工具执行超时 30s、任务总超时
- **错误处理**：API 重试 3 次（指数退避）、rate limit 处理、工具执行超时、用户取消

### 3.3 工具系统

| 工具名 | 功能 | 输入 | 输出 |
|--------|------|------|------|
| `read_file` | 读取文件 | path, offset, limit | 文件内容 |
| `write_file` | 写入文件 | path, content | 成功/失败 |
| `edit_file` | 精确替换 | path, old_str, new_str | 成功/失败 |
| `run_shell` | 执行命令 | command, workdir | stdout/stderr |
| `search_content` | 搜索内容 | pattern, path, include | 匹配行 |
| `search_files` | 搜索文件 | pattern, path | 文件列表 |
| `git_diff` | 查看变更 | 无 | diff 输出 |
| `git_log` | 提交历史 | count | 日志 |
| `list_dir` | 列出目录 | path | 内容列表 |

### 3.4 治理护栏

- **输入**：工具名称、参数
- **行为**：检查命令是否匹配黑名单模式 → 匹配则拦截
- **输出**：`GuardBlockedError` 或通过
- **配置**：`blocked_commands` 列表（如 `["rm -rf /", "shutdown"]`）

### 3.5 反馈闭环（校验器）

- **输入**：工具执行结果
- **行为**：解析输出 → 判断成功/失败 → 分类失败原因
- **输出**：`ToolResult`（success, output, error）→ 回灌到 Agent 消息历史
- **失败分类**：命令执行失败（exit_code≠0）、超时、被拦截、网络错误

### 3.6 记忆机制

- **输入**：项目路径、记忆内容
- **行为**：存储为结构化 JSON → 在构建上下文时按项目路径检索
- **输出**：注入到 Agent 初始 prompt 的"项目记忆"部分
- **存储**：`data/memory/{project_hash}.json`

### 3.7 可观测性

- **事件类型**：`TurnStart`, `ToolCallStart`, `ToolCallEnd`, `AgentThinking`, `LoopError`, `LoopComplete`, `SandboxEvent`
- **输出**：终端实时流式 + 结构化 JSONL 日志文件
- **配置**：`--verbose` 开关、日志级别

---

## 4. 非功能性需求

### 4.1 性能

- 单个任务执行时间主要受 LLM API 延迟和 max_turns 限制
- 工具执行超时：30 秒
- 任务总超时：可配置（默认 600 秒）
- SQLite 操作：< 10ms

### 4.2 安全

**凭据威胁模型**：
- 威胁：API Key 泄露（源码提交、日志输出、配置文件、进程环境）
- 对策：keyring 存储（操作系统级加密）→ 环境变量后备 → .env 文件后备（明文风险已文档化）
- 绝不：硬编码、提交到 Git、写入日志、回显明文

**沙箱**：
- Agent 在 Docker 容器中执行，通过 volume 挂载访问代码
- 危险命令黑名单拦截

### 4.3 可用性

- CLI 一键运行：`harness run tasks/bug.yaml`
- 首次运行引导：`harness credentials setup`
- 错误信息明确：每个失败场景有描述性错误
- WebUI 仪表板：`harness web`

### 4.4 可观测性

- 实时流式输出 Agent 思考和工具调用
- 结构化 JSONL 日志
- SQLite 任务状态查询
- 分层报告：摘要 / 详细 / JSON

### 4.5 可测试性

- 所有核心机制可替换为 mock/stub 进行确定性测试
- FakeAdapter、FakeSandbox 用于单元测试
- 机制演示脚本：护栏拦截、反馈闭环、记忆检索

---

## 5. 系统架构

### 5.1 组件图

```
┌──────────────────────────────────────────────────┐
│                    CLI / WebUI                     │
├──────────────────────────────────────────────────┤
│                  TaskManager                       │
│         (生命周期管理、容器编排、验证)               │
├──────────────────────────────────────────────────┤
│                   AgentLoop                        │
│     (组织上下文 → 调用 LLM → 解析 → 分发 → 回灌)     │
├──────────┬──────────┬──────────┬──────────────────┤
│ Adapter  │  Tools   │ Sandbox  │    Observer      │
│ (OpenAI) │ (9 tools)│ (Docker) │ (stream + log)    │
├──────────┴──────────┴──────────┴──────────────────┤
│              Storage (SQLite + File)               │
├──────────────────────────────────────────────────┤
│        Credentials (keyring + .env fallback)      │
└──────────────────────────────────────────────────┘
```

### 5.2 数据流

```
Task YAML → TaskConfig → TaskManager → Docker Sandbox → AgentLoop
                                                          ├→ Adapter.chat(messages)
                                                          │    ↓
                                                          │  response (text/tool_calls)
                                                          │    ↓
                                                          ├→ ToolRegistry → Tool.execute()
                                                          │    ↓
                                                          ├→ CommandGuard (拦截检查)
                                                          │    ↓
                                                          ├→ Observer.emit (事件流)
                                                          │    ↓
                                                          └→ LoopResult → TaskStore → ReportGenerator
```

### 5.3 外部依赖

- **LLM 供应商**：OpenAI API（GPT-4o，可扩展）
- **容器运行时**：Docker Engine
- **凭据存储**：keyring（Windows Credential Manager / macOS Keychain / Linux Secret Service）
- **Git**：gitpython 用于仓库克隆和历史查询

---

## 6. 数据模型

### 6.1 TaskConfig

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | str | 是 | 任务唯一标识 |
| name | str | 是 | 任务名称 |
| description | str | 是 | 任务描述 |
| repo | str | 是 | Git 仓库 URL |
| branch | str | 是 | 目标分支 |
| base_commit | str? | 否 | 修复起点 commit |
| environment | EnvironmentConfig | 是 | Docker 环境配置 |
| agent | AgentConfig | 是 | Agent 配置 |
| sandbox | SandboxConfig | 是 | 沙箱配置 |
| verification | VerificationConfig? | 否 | 验证步骤 |

### 6.2 TaskRecord (SQLite)

```sql
tasks(id, name, status, repo, branch, model, created_at, started_at,
      finished_at, duration_ms, turns, tokens_used, error, task_file)
```

### 6.3 工具调用记录

```sql
tool_calls(id, task_id, turn_number, tool_name, args, result, duration_ms, success)
```

---

## 7. 凭据与分发设计

### 7.1 Key 存储方案

**优先级**：
1. keyring（操作系统级安全存储）— Windows Credential Manager
2. 环境变量 `OPENAI_API_KEY` — 明文风险，不推荐
3. `.env` 文件 — 明文存储，仅开发环境使用，已加入 `.gitignore`

**录入流程**：`harness credentials setup` → 隐藏输入 → 存入 keyring
**查看流程**：`harness credentials status` → 仅显示服务名，不回显明文
**更新流程**：`harness credentials update <service>` → 重新输入
**清除流程**：`harness credentials clear <service>` → 确认后删除

### 7.2 分发形态

**容器镜像**（Docker）：
```bash
docker build -t harness .
docker run -it harness --help
```

**本地安装**（pip）：
```bash
pip install -e .
harness --help
```

**目标平台**：Linux (CI)、macOS、Windows（需 Docker Desktop）

### 7.3 Key 在目标机器的安全配置

```
# 首次运行
harness credentials setup
# 输入: Service name [harness/openai]:
# 输入: API Key: **** (隐藏输入)

# 之后所有命令自动使用 keyring 中的 key
harness run tasks/bug.yaml
```

---

## 8. 领域与机制设计

### 8.1 领域分析（Coding）

| 维度 | 编码实现 | 说明 |
|------|----------|------|
| **反馈信号** | 测试结果、lint 输出、exit code | 客观、确定、可回灌 |
| **危险动作** | `rm -rf /`、`shutdown`、`git push --force` | 命令模式匹配拦截 |
| **所需工具** | 文件读写、shell 执行、代码搜索、git 操作 | 9 个内置工具 |
| **记忆需求** | 项目约定、历史决策、代码库结构 | 按项目路径存储 |

### 8.2 重点维度：治理护栏

选择**治理（Governance）**作为重点深入维度，原因：
1. 它是 harness 与"提示词驱动"的最本质区别——护栏是代码，不是提示词
2. 它天然由确定性代码构成，在最严格的 mock LLM 测试标准下仍可完整验证
3. 它直接影响系统的安全边界，是工程深度最直观的体现

**实现深度**：
- `CommandGuard`：黑名单模式匹配，`check()` 方法对每个 shell 工具调用做拦截
- 可扩展为白名单模式、正则匹配、HITL（Human-in-the-Loop）状态机
- 拦截事件记录到 Observer 日志，Agent 收到拦截反馈后可调整策略

### 8.3 机制编码验证

移除真实 LLM 后，以下机制可独立通过确定性测试验证：

| 机制 | 测试方式 | 验证属性 |
|------|----------|----------|
| 工具分发 | `ToolRegistry + FakeSandbox` | 工具注册、查找、schema 生成 |
| 治理拦截 | `CommandGuard.check()` | 危险命令被拦截、安全命令通过 |
| 反馈回灌 | `FakeAdapter + LoopResult` | 失败工具结果出现在 messages 中 |
| 记忆读写 | `FileStore` 直接测试 | 存储/检索/项目隔离 |
| 停机判断 | `AgentLoop + FakeAdapter` | max_turns、text response、tool_calls 循环 |

---

## 9. 技术选型与理由

| 组件 | 选型 | 理由 |
|------|------|------|
| 语言 | Python 3.11+ | 生态成熟，AI/LLM 库丰富，快速原型 |
| LLM 供应商 | OpenAI (GPT-4o) | 首版支持，架构预留 Anthropic 扩展 |
| 容器 | Docker (docker-py) | 标准化沙箱，跨平台隔离 |
| CLI | Click | 装饰器风格，子命令支持好 |
| WebUI | FastAPI + Jinja2 | 异步支持，与 asyncio 核心一致 |
| 存储 | SQLite + JSONL 文件 | 零依赖，适合单机工具 |
| 凭据 | keyring + python-dotenv | 操作系统级安全 + 开发环境后备 |
| 测试 | pytest + pytest-asyncio | 异步测试支持 |
| 分发 | Docker + pip | 容器一键部署 + 本地开发 |

---

## 10. 验收标准

| 功能 | 验收标准 |
|------|----------|
| 任务提交 | `harness run tasks/bug.yaml` 成功执行并产出 diff |
| 凭据安全 | `harness credentials setup` → 隐藏输入 → 存入 keyring |
| 危险拦截 | Agent 执行 `rm -rf /` 被 `CommandGuard` 拦截 |
| 反馈闭环 | 工具失败后 Agent 下一轮包含对失败的引用 |
| 跨会话记忆 | 存储记忆后新任务 prompt 包含记忆内容 |
| 实时流式 | `--verbose` 实时输出 Agent 思考和工具调用 |
| 报告生成 | `harness report <id> --json` 输出结构化报告 |
| 单元测试 | `pytest tests/ -v` 全部通过（mock LLM 测试） |
| CI/CD | GitHub Actions unit-test job 通过 |
| 分发 | `docker build` + `docker run` 成功 |

---

## 11. 风险与未决问题

| 风险 | 缓解措施 |
|------|----------|
| Docker 不可用 | CLI 明确提示，测试用 FakeSandbox 绕过 |
| LLM API 不稳定 | 3 次重试 + 指数退避 + rate limit 处理 |
| 工具执行超时 | 30s 单次超时 + 任务总超时 |
| 凭据泄露 | keyring 存储 + .gitignore 检查 + CI 扫描 |
| 上下文窗口溢出 | 输出截断（8000 字符）+ 摘要注入策略 |
| 跨平台兼容 | Docker 统一环境，测试矩阵覆盖 3.11-3.13 |

---

## 12. 不在范围

- 多 Agent 协作
- Anthropic / 其他 LLM 适配器（架构预留）
- 环境快照保存/恢复
- 自定义工具热加载（代码注册支持，配置文件不支持）
- 用户认证与多租户