# REFLECTION.md — 反思报告

> 作者：学生本人撰写 | 字数：约 2400 字

---

## 一、哪些 Superpowers 技能发挥了最大作用

**brainstorming** 是整个过程最有价值的技能。它通过逐一追问的方式，把"做一个 Coding Agent 的评测工具"这个模糊想法，逐步收敛为一份包含 13 个 Task 的精确实现计划。最让我印象深刻的是，它不会一次性抛出所有问题，而是每次只问一个，基于前一个答案推导下一个——这种"逐步收敛"的模式远优于"一次性列出所有需求"。

**subagent-driven-development** 是第二关键的技能。每个 Task 派发一个全新 subagent，意味着每个 subagent 只看到它需要的信息（task brief + 依赖接口），不会被前序任务的上下文污染。这倒逼我必须把每个 task 的规格写清楚——因为 subagent 不会"猜"我脑子里想什么。Task 2 的 review 发现缺少 `from_yaml` 方法，正是因为我只在接口规范中写了，但 plan 代码中没有——subagent 严格按 plan 代码实现，暴露了规约与代码之间的不一致。

**requesting-code-review** 的两阶段评审（spec compliance + code quality）是质量防线。最终全分支 review 发现了 5 个 Critical 问题——其中最关键的是 `container_id` 未传递到工具执行链。这个 bug 在单元测试中完全不可见（因为 FakeSandbox 忽略了 container_id 参数），只有在真实 DockerSandbox 中才会崩溃。这个发现让我深刻理解了"fake 测试通过 ≠ 生产可用"。

---

## 二、哪些"形式大于实质"

**TDD 的强制**在 AI 协作下有部分形式化倾向。理论上，每个 task 都应该"先写失败测试 → 实现 → 变绿"。但实际操作中，plan 已经包含了完整代码，subagent 直接复制代码并让测试通过，RED 阶段的"失败"是 import error 而非逻辑错误——这虽然符合流程，但 RED 阶段的测试价值有限。

**writing-plans 的粒度**有时过于细碎。比如 Task 1（scaffolding）和 Task 13（integration test）都是极简单的任务，作为一个独立 task 有过度分解之嫌。

**finishing-a-development-branch** 的四个选项（合并/PR/保留/丢弃）在单机项目中略显冗余。对于没有多人协作的场景，"本地合并"和"创建 PR"之间的选择缺乏实际意义。

---

## 三、TDD 强制在 AI 协作下是阻碍还是放大器

**是放大器，但有前提**。TDD 在 AI 协作下的最大价值不是"防止写出 bug"（AI 写测试和写实现的水平差不多），而是"强迫我把验收标准写清楚"。当 subagent 必须让测试通过时，测试本身就成为了行为规约。Task 2 的测试明确要求 `from_yaml` 类方法，但 plan 代码中没有——如果测试写得更早（在 plan 阶段），这个不一致会更早暴露。

但 TDD 的"重构"阶段在 AI 协作中几乎被跳过。Subagent 完成实现后，代码通常已经是最简形式，因为 AI 倾向于写"刚好够用"的代码。传统 TDD 中"先用最笨的方法让测试通过，再重构"的模式在 AI 协作中不适用——AI 的一次性实现质量通常已经接近重构后的水平。

---

## 四、subagent-driven 工作流让智能体能自主运行多久而不偏离主题

**单个 Task 内：几乎不偏离**。每个 subagent 的上下文是精心裁剪的（task brief + 依赖接口），它不需要理解整个项目，只需要完成一个明确的任务。这大大降低了偏离概率。

**跨 Task 之间：偏离发生在"接口不一致"处**。Task 9 的 subagent 发现 plan 测试代码使用 `tc.function.name`，但实际 `ToolCall` 接口是 `tc.name`——它正确修正了。但 Task 10 的 subagent 没有发现 `cancelled` 状态映射错误——因为它只看自己的 task brief，不知道 `AgentLoop` 能返回 `cancelled` 状态。

**教训**：Subagent 在单个 task 内很可靠，但跨 task 的接口一致性必须由 review 来保证。这正是 SDD 流程中"每个 task 后 review"的设计意图。

---

## 五、什么样的 task 颗粒度最优

**最优粒度**：一个 task = 一个可独立测试的模块（1-2 个源文件 + 对应的测试文件），实现时间 5-15 分钟。

**过细的 task**（如 Task 1 scaffolding）：subagent 发现工作已做完，只是验证了现有代码。这种 task 应该合并到前序步骤。

**过大的 task**（如 Task 7 工具系统，9 个工具 + 2 个测试文件）：subagent 仍然能完成，但 review 时需要检查更多代码，review 质量下降。应该拆分为"工具注册表"和"具体工具实现"两个 task。

**最佳案例**：Task 3（Storage Layer）——TaskStore + FileStore，两个文件，9 个测试，review 一次通过。

---

## 六、SPEC/PLAN 质量如何影响实现质量

**最具体的案例：`container_id` 传递链断裂**

Plan 的 AgentLoop 代码中，`self.container_id` 被存储但从未传递给 `build_context()` 或 `tool.execute()`。所有工具内部硬编码 `sandbox.exec("", ...)`。Plan 的测试使用 FakeSandbox（忽略第一个参数），所以测试全部通过。但 SPEC 要求"Agent 在 Docker 容器中执行"，这个要求在 plan 层面就没有被正确实现。

**原因**：在写 plan 时，我（和 brainstorming）关注的是"功能逻辑"（Agent 如何调用工具、如何循环），但忽略了"数据流"（container_id 如何在组件间传递）。这是一个典型的"规约清楚但实现细节遗漏"的案例。

**修正**：最终全分支 review 发现了这个问题，fix subagent 为所有 `Tool.execute()`、`build_context()` 添加了 `container_id` 参数。

---

## 七、最有效的 prompt / context 策略

**1. Task Brief 模式**：不把整个 plan 交给 subagent，而是用 `task-brief` 脚本提取单个 task 的完整文本。Subagent 只看到它需要的信息，不会被其他 task 的上下文干扰。

**2. 接口契约明确**：每个 task prompt 中明确列出"Consumes"（依赖的接口）和"Produces"（产出的接口），subagent 知道什么是"已实现的"、什么是"需要实现的"。

**3. 两阶段 review prompt**：reviewer 的 prompt 明确分为"spec compliance"和"code quality"两部分，防止 reviewer 只看代码质量而忽略规格一致性。

**4. Fix subagent 全量修复**：最终 review 发现 8 个问题，我一次性派发一个 fix subagent 修复全部，而不是分 8 次派发。这避免了重复的上下文构建和测试运行。

---

## 八、凭据与分发迫使我想清楚了什么

**凭据安全**：在实现 keyring 存储之前，API Key 只是被我放在 `.env` 文件里（已 gitignore）。但课程要求迫使我思考：如果换一台机器怎么办？如果`.env` 被意外提交怎么办？keyring 方案解决了这些问题，但也暴露了 keyring 库的局限性（`list_services()` 在不同后端行为不一致）。

**分发**：Dockerfile 看起来简单，但写的时候发现真正的难点是"key 如何在目标机器上配置"。最终方案是：Docker 镜像只包含 harness 代码，不包含任何凭据；用户通过 `harness credentials setup` 在本地配置 key。这迫使我把"凭据配置"从"软件分发"中分离出来。

**CI/CD**：GitHub Actions 的单元测试不依赖真实 LLM 或 Docker。所有测试都使用 mock/fake 组件，这意味着 CI 可以在任何环境运行。这是"机制必须是代码"原则的自然延伸。

---

## 九、如果重做我会改变什么

1. **在 brainstorming 阶段就明确四类机制**（反馈、危险、记忆、工具），而不是在实现后期才补充。这会在 SPEC 中形成一个更完整的"领域与机制设计"章节。

2. **Plan 中的代码示例应该更严格地审查**。几个 bug（heredoc 漏洞、`cancelled` 状态映射错误、`container_id` 遗漏）都源自 plan 代码本身。如果我在 plan 阶段做了更仔细的代码审查，很多 review 发现的问题可以提前避免。

3. **冷启动验证应该在实现前完成**。我直到写 SPEC_PROCESS.md 时才意识到需要做冷启动验证。如果提前做，spec 的清晰度会更高。

4. **Task 粒度应该更均匀**。Task 1（scaffolding）和 Task 13（integration test）太小，Task 7（9 个工具）太大。应该调整粒度使每个 task 的复杂度相近。

---

## 十、对 Superpowers 方法论的批判

**Superpowers 假设了什么**：
1. 假设用户能够清晰地表达需求，且需求在 brainstorming 后不会大幅变化
2. 假设 plan 的代码示例是正确的，subagent 可以逐行实现
3. 假设 task 之间的依赖关系是树状的，不会出现循环依赖
4. 假设 review 能发现所有问题——但 review 的质量取决于 reviewer 的能力

**这些假设在我的项目里成立吗**：
- 假设 1 基本成立。brainstorming 的逐一追问模式确实帮助我澄清了需求。但需求在实现过程中仍然有变化（凭据存储、WebUI 是后期补充的）。
- 假设 2 不成立。Plan 的代码中有多个 bug，subagent 严格复制了这些 bug。这说明 plan 的代码质量需要更严格的审查。
- 假设 3 成立。我的 13 个 task 确实形成了清晰的依赖树。
- 假设 4 基本成立。最终全分支 review 确实发现了关键问题（container_id 传递链），但一些更细微的问题（如 `max_turns=0` 时的边界条件）在单 task review 中被遗漏了。

**Superpowers 的真正价值**：它不是在"帮你写代码"，而是在"强制你遵守工程纪律"。TDD、review、worktree 隔离、task 拆分——这些都不是新技术，但 Superpowers 把它们固化为流程，让你在 AI 协作中不容易松懈。它的真正产品不是代码，而是**一个有纪律的开发过程**。