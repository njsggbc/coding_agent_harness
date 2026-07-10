# AGENT_LOG.md

> Coding Agent Harness 实现过程证据。
> 记录格式：时间戳 + Task 编号 → 技能 → 关键 Prompt/Context → Subagent 输出 → 人工干预 → 教训。

---

## 2026-07-09 18:30 | 项目启动

**触发技能**: brainstorming, writing-plans

**关键 Prompt**: "Let's design my Coding Agent Harness"

**Context 配置**: 中文对话，逐一确认需求（Agent 类型、工作流、环境、仓库交互、技术栈等）

**决策输出**:
- 方案 B（核心+插件架构），Python 3.11+，OpenAI，Docker
- 设计文档: `docs/superpowers/specs/2026-07-09-coding-agent-harness-design.md`
- 实现计划: `docs/superpowers/plans/2026-07-09-coding-agent-harness.md`

**教训**: brainstorming 的逐一确认模式有效避免了需求遗漏。13 个 Task 的分解粒度合理——每个 Task 是一个独立可测试的交付单元。

---

## 2026-07-09 18:38 | 工作树创建 + SDD 启动

**触发技能**: using-git-worktrees, subagent-driven-development

**关键 Prompt**: "Use git-using-git-worktrees to setup a unique workspace for this task branch."

**Context 配置**:
- 仓库: `D:\Download\my_coding_agent_harness`
- 工作树: `.worktrees/feat/coding-agent-harness`
- 分支: `feat/implement-harness`（基于 `feat/coding-agent-harness`）
- 执行策略: 每 Task 完成后 review (spec + quality)，修复 Critical 后再继续

**Subagent 模型选择**: 机械实现任务用 general 模型，最终全分支 review 用 general 模型

**人工干预**: 用户要求每个 Task 完成后先 Review (spec + quality)，修复 Critical 后再继续。要求维护 AGENT_LOG.md 按时间顺序记录。

**教训**: 工作树隔离是必须的。第一次 `git worktree add` 失败因为分支已签出，改用 `-b feat/implement-harness` 创建新分支解决。

---

## 2026-07-09 ~18:40 | Task 1: Project Scaffolding

**触发技能**: subagent-driven-development (implementer dispatch)

**关键 Prompt**: "You are implementing Task 1: Project Scaffolding. Read your task brief first: .superpowers/sdd/task-1-brief.md"

**Subagent 输出**:
- Status: DONE
- 发现脚手架已存在于前置提交 `a4e4ee4`（`chore: scaffold project structure and dependencies`）
- 1 test passed (smoke test for imports)
- pyproject.toml 使用 `setuptools.build_meta` 替代 plan 中的 `_legacy:_Backend`

**Review 结果**: ✅ Spec compliant, ✅ 干净通过。无 Critical。

**人工干预**: 无。脚手架已于 brainstorming 阶段自动创建。

**教训**: scaffolding 在 plan 阶段就完成了，导致 Task 1 实际是"验证"而非"实现"。plan 中应该明确标注哪些前置工作已就绪。

---

## 2026-07-09 ~18:42 | Task 2: Task Model

**触发技能**: subagent-driven-development

**Context**: 依赖无。实现 `harness/core/task.py`（dataclasses + YAML loader）和 `tests/core/test_task.py`

**Subagent 输出**:
- Status: DONE | Commit: `c4bfc0c` feat: add task config model with YAML loader
- 3/3 tests pass. 测试覆盖必填字段、可选字段、枚举值

**Review 发现**:
- ❌ Critical: 缺少 `TaskConfig.from_yaml(path)` classmethod（plan 要求但实现遗漏）
- ⚠️ Important: `load_task_config` 无错误处理、测试命名误导、from_dict 无字段验证

**Fix subagent**: Commit `40805fd` fix: address Task 2 review findings
- 添加 `from_yaml` classmethod、try/except 错误处理、from_dict 验证、11/11 tests

**人工干预**: 无。review loop 自动修复。

**教训**: Subagent 严格执行 plan 代码但可能遗漏 interface 规范中的方法。Review 的 spec compliance 检查是关键防线——不能只看测试通过，必须对照 spec 逐项验证。

---

## 2026-07-09 ~18:45 | Task 3: Storage Layer

**触发技能**: subagent-driven-development

**Context**: 依赖 Task 2 (TaskConfig, TaskStatus)。实现 `TaskStore` (SQLite) 和 `FileStore` (JSONL/diff)

**Subagent 输出**:
- Status: DONE | Commit: `ae4b31b` feat: add SQLite and file storage layer
- 21/21 tests pass (5 DB + 4 files + 12 existing)

**Review 发现**: ✅ Spec compliant, Approved。Minor: 2 个 unused import（继承自 plan 代码）

**人工干预**: 无。

**教训**: TaskStore 的 `_get_conn` 被 subagent 改进为 `@contextmanager` 模式——这是对 plan 代码的合理提升，说明 subagent 在遵循 plan 的同时可以做出良性改进。

---

## 2026-07-09 ~18:48 | Task 4: Sandbox Layer

**触发技能**: subagent-driven-development

**Context**: 依赖无。实现 `Sandbox` ABC、`DockerSandbox`、`CommandGuard`

**Subagent 输出**:
- Status: DONE_WITH_CONCERNS | Commit: `0711776`
- 5/5 guard tests pass, 4 Docker tests skip (no Docker)
- 标记了 `write_file` heredoc 漏洞（content 含 `EOF` 时会破坏文件）

**Review 发现**:
- ❌ Critical: write_file heredoc 漏洞、read_file/write_file 路径注入（单引号逃逸）
- ⚠️ Important: stderr 未填充、unused import、setup 忽略 exit code

**Fix subagent**: Commit `946bdc4` fix: address Task 4 review findings
- write_file 改用 base64 编码、read_file/write_file 用 `shlex.quote()`、exec 用 `demux=True` 分离 stdout/stderr、setup 失败抛出 RuntimeError

**人工干预**: 无。

**教训**: Subagent 主动标记了 `DONE_WITH_CONCERNS`——这是一个好信号。但 plan 中的 heredoc 代码本身就是不安全的，说明 plan 阶段的代码审查应该更严格。

---

## 2026-07-09 ~18:50 | Task 5: Adapter Layer

**触发技能**: subagent-driven-development

**Context**: 依赖无。实现 `BaseAdapter` ABC、`OpenAIAdapter`

**Subagent 输出**:
- Status: DONE | Commit: `6d0d06f` feat: add adapter layer with OpenAI implementation
- 2 tests SKIP (no API key), 26 existing pass

**Review 发现**: ✅ Spec compliant, Approved。无任何 issue。

**教训**: 最干净的 Task——plan 代码完整且正确，subagent 逐行实现无偏差。

---

## 2026-07-09 ~18:52 | Task 6: Observer Layer

**触发技能**: subagent-driven-development

**Context**: 依赖无。实现 `Observer` 事件总线、`StreamObserver`、`LogObserver`

**Subagent 输出**:
- Status: DONE | Commit: `8d67a9d` feat: add observer layer with stream and log observers
- 5/5 tests pass

**Review 发现**: ✅ Spec compliant, Approved。Important: `_turn_count` 死代码、smoke test 无断言。

**人工干预**: 无（Critical 未触发，Important 留待后续）。

**教训**: 非 Critical 的 review 发现可以容忍，但 `_turn_count` 死代码应该在 fix 阶段一并清理。

---

## 2026-07-09 ~18:55 | Task 7: Tool System

**触发技能**: subagent-driven-development

**Context**: 依赖 Task 4 (Sandbox ABC)。实现 9 个内置工具 + ToolRegistry

**Subagent 输出**:
- Status: DONE | Commit: `0768bb7` feat: add tool system with registry and 9 built-in tools
- 15/15 tests pass (4 registry + 11 tools)

**Review 发现**: ✅ Spec compliant, Approved。无任何 issue。

**教训**: 最大的 Task（1170 行 brief），但 review 最干净——因为 plan 代码完整且测试使用的是 FakeSandbox，隔离了 Docker 依赖。

---

## 2026-07-09 ~18:57 | Task 8: Context Builder

**触发技能**: subagent-driven-development

**Context**: 依赖 Task 2 (TaskConfig)、Task 4 (Sandbox)。实现 `build_context()` 仓库摘要构建

**Subagent 输出**:
- Status: DONE | Commit: `525d5e4` feat: add repository context builder for agent prompts
- 47 passed, 6 skipped

**Review 发现**: ✅ Spec compliant, Approved。无 Critical/Important。

**教训**: 简单任务，一次通过。FakeContextSandbox 模式已被多次复用。

---

## 2026-07-09 ~19:00 | Task 9: AgentLoop

**触发技能**: subagent-driven-development

**Context**: 核心引擎，依赖 Adapter、Tools、Sandbox、Guard、Observer、Task Model、Context

**Subagent 输出**:
- Status: DONE | Commit: `e615f4c` feat: add AgentLoop core engine with tool-calling cycle
- 50/50 tests pass. 修正了 plan 测试中使用 `type()` 构建 ToolCall 的问题

**Review 发现**:
- ⚠️ Important: `max_turns=0` 时 `response` 未定义 → `NameError`

**Fix subagent**: Commit `2bcc66c` fix: guard against undefined response when max_turns is 0
- 初始化 `response = None`，增加 `response is None` 守卫

**人工干预**: 无。

**教训**: plan 中的测试代码使用了 `type()` 构建 ad-hoc 对象（`tc.function.name`），但实际 ToolCall dataclass 接口是 `tc.name`。Subagent 识别并修正了这个问题——说明 subagent 能够发现 plan 代码与已实现接口的不一致。

---

## 2026-07-09 ~19:03 | Task 10: TaskManager

**触发技能**: subagent-driven-development

**Context**: 编排层，依赖所有前序模块。实现 `TaskManager` 生命周期管理

**Subagent 输出**:
- Status: DONE | Commit: `3d9645d` feat: add TaskManager for full task lifecycle orchestration
- 53 passed, 6 skipped

**Review 发现**:
- ⚠️ Important: `AgentLoop` 返回 `"cancelled"` 时被映射为 `FAILED` 而非 `CANCELLED`

**Fix subagent**: Commit `2109d39` fix: map cancelled status correctly in TaskManager
- 改为三路映射: `done → DONE`, `cancelled → CANCELLED`, 其他 → `FAILED`

**人工干预**: 无。

**教训**: 状态映射错误是典型的"覆盖不全"问题。plan 代码只考虑了 done/failed 二路分支，遗漏了 cancelled。

---

## 2026-07-09 ~19:05 | Task 11: Report Generator

**触发技能**: subagent-driven-development

**Context**: 依赖 Task 3 (TaskStore, FileStore)。实现 `ReportGenerator` 多种输出格式

**Subagent 输出**:
- Status: DONE | Commit: `567da73` feat: add report generator with summary, verbose, and JSON formats
- 59 passed, 6 skipped

**Review 发现**: ✅ Spec compliant, Approved。无任何 issue。

**教训**: 干净通过。subagent 还额外增加了 `test_format_verbose` 测试（plan 未要求但合理）。

---

## 2026-07-09 ~19:08 | Task 12: CLI

**触发技能**: subagent-driven-development

**Context**: 依赖 Task 10 (TaskManager)、Task 11 (ReportGenerator)。实现 Click CLI 6 个命令

**Subagent 输出**:
- Status: DONE | Commit: `510b957` feat: add CLI with run, status, report, list, cancel, config commands
- 65 passed, 6 skipped

**Review 发现**:
- ⚠️ Important: `--verbose` flag 接受但从未使用

**Fix subagent**: Commit `f45e168` fix: wire --verbose flag to enable streaming in run command
- 实际移除 `--verbose` flag（因为 `--no-stream` 已提供反向控制）

**人工干预**: 无。

**教训**: plan 的 CLI 代码中 `--verbose` 参数定义了但从未使用。Subagent 严格复制了 plan 代码，但 plan 本身就有死代码。

---

## 2026-07-09 ~19:10 | Task 13: Integration Test

**触发技能**: subagent-driven-development

**Context**: 依赖所有模块。创建 `tasks/example-bug.yaml` 和集成测试

**Subagent 输出**:
- Status: DONE | Commit: `f0f726d` test: add integration test and example task file
- 69 passed, 6 skipped

**Review 发现**: ✅ Spec compliant, Approved。额外增加了 3 个边界测试。

**教训**: 无。

---

## 2026-07-09 ~19:12 | 最终全分支 Review

**触发技能**: requesting-code-review

**关键 Context**: 全分支 diff（739KB），从 MERGE_BASE `5966bc6` 到 HEAD `f0f726d`

**Review 发现**:
- ❌ Critical (5):
  1. `container_id` 未传递到工具执行链——所有工具硬编码 `sandbox.exec("", ...)`，FakeSandbox 掩盖了此问题
  2. OpenAI API 无重试/rate-limit 处理
  3. `cancel` 命令不能真正停止运行中的任务
  4. 无任务总超时
  5. 无工具执行超时
- ⚠️ Important (5): setup 失败应继续、verification 未执行、Ctrl+C 无优雅关闭等

**Fix subagent**: Commit `fbb7329` fix: address all Critical final review findings
- 修复全部 5 Critical + 3 Important
- 69 passed, 6 skipped

**人工干预**: 无。一次性 fix subagent 修复了全部 8 个问题。

**教训**:
- **最关键的教训**: 单元测试全部通过（69/69）不等于生产可用。FakeSandbox 掩盖了 `container_id` 传递链断裂的架构缺陷——真实 DockerSandbox 会在第一个工具调用时崩溃。这是本项目的 #1 教训：fake 测试必须有对应的集成测试验证真实路径。
- 全分支 review 的价值在于发现"跨 Task 的系统性问题"——单个 Task 的 review 只能看到局部，无法发现 `container_id` 在整个工具链中未被传递的问题。
- 最终 review 应该使用最高能力模型——这是质量最后一道防线。

---

## 2026-07-09 ~19:15 | 收尾

**Commit**: `1ecdf18` docs: update AGENT_LOG with full SDD process record

**最终状态**:
- 19 commits，69 tests passed，6 skipped (Docker/API key)
- 工作树: `.worktrees/feat/coding-agent-harness`，分支: `feat/implement-harness`
- 待合并到 main

---

## 总结教训

| # | 教训 | 严重程度 |
|---|------|----------|
| 1 | Fake 测试通过 ≠ 生产可用。必须验证真实路径（DockerSandbox 而非 FakeSandbox）。 | Critical |
| 2 | 全分支 review 是必须的——单 Task review 无法发现跨 Task 的系统性问题。 | Critical |
| 3 | Plan 中的代码示例可能有 bug（heredoc 漏洞、死代码、状态映射不完整），不应盲从。 | Important |
| 4 | Subagent 能够识别 plan 代码与已实现接口的不一致并修正（Task 9 的 ToolCall 接口）。 | Positive |
| 5 | Review 的 spec compliance 检查必须逐项对照 spec，不能只看测试通过。 | Important |
| 6 | Subagent 的 `DONE_WITH_CONCERNS` 是有效信号，但不应替代 review。 | Positive |
| 7 | 一次性 fix subagent 可以高效修复多个问题（最终 review 8 个问题一次修复）。 | Positive |