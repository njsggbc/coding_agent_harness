# 冷启动验证操作指南

## 目标

按照通用要求 §4.5，使用一个**与主开发智能体（OpenCode）不同**的 agent，仅凭 `SPEC.md` + `PLAN.md` 尝试实现 1-2 个 task，验证规约的清晰度。

## 操作步骤

### 1. 打开另一个 Agent

选择一个与 OpenCode 不同的编码智能体，例如：
- **Claude Code**（`claude` CLI）
- **GitHub Copilot CLI**（`gh copilot`）
- **Cursor Agent**（Cursor 编辑器内置）
- **Gemini CLI**（Google 的 Gemini 终端工具）

### 2. 启动全新会话

**关键**：不要导入任何历史会话。这是一个"干净"的 agent，它对你的项目一无所知。

### 3. 提供以下材料

将下面两个文件的内容提供给 agent：

1. 项目根目录下的 `SPEC.md`（完整规约）
2. 项目根目录下的 `PLAN.md`（实现计划，选择 Task 2 或 Task 5）

### 4. 使用以下 Prompt

```
你是一个软件工程师。请仅根据以下两份文档来实现一个任务：

**SPEC.md**（项目的完整规约，包含架构、数据模型、接口定义）：
[粘贴 SPEC.md 内容]

**PLAN.md**（实现计划，请只实现 Task 2: Task Model）：
[粘贴 PLAN.md 中 Task 2 的部分]

## 要求

1. 只实现 Task 2: Task Model（TaskConfig 数据类 + YAML 加载器）
2. 不要推测或猜测任何未在文档中明确写下的内容
3. 遇到不确定之处即暂停询问，而非凭猜测继续
4. 遵循 TDD：先写测试，再写实现
5. 完成后告诉我：你遇到了什么不确定的地方？文档中哪些地方不够清晰？

## 项目环境

- 语言: Python 3.11+
- 测试框架: pytest
- 工作目录: [你的工作目录]
```

### 5. 记录结果

将以下信息记录到 `SPEC_PROCESS.md` 的"冷启动验证"章节：

| 项目 | 记录内容 |
|------|----------|
| 使用的 Agent | 名称和版本 |
| 测试的 Task | Task 2 或 Task 5 |
| Agent 在哪里暂停提问 | 具体的不确定点 |
| 暴露了哪些 spec 缺陷 | 什么信息缺失或不清晰 |
| Agent 是否做出了错误解读 | 什么原因（spec 写错 vs agent 读错） |
| 产出与预期差距 | 代码质量、测试覆盖 |
| 据此对 SPEC/PLAN 做了哪些修订 | 修订前后的关键 diff |

### 6. 推荐测试的 Task

**Task 2: Task Model**（推荐）
- 独立性强，无依赖
- 涉及 YAML 解析、数据类定义、错误处理
- 可以很好地测试 SPEC 中"数据模型"和"任务定义"的清晰度

**Task 5: Adapter Layer**（备选）
- 独立性强，无依赖
- 涉及抽象基类、OpenAI SDK 集成
- 可以测试 SPEC 中"Adapter 接口"的清晰度