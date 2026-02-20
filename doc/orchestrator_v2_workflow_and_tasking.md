# Orchestrator v2 工作流与任务分配需求文档

本文描述 **当前仓库中的 `orchestrator_v2/` 实际如何工作**，以及在此机制下，后续应如何进行**任务拆分与分配**（给人类/PM/负责人用的操作与约定文档）。

> 设计基调：harness 极简（接近博客的 `while true`），状态用 git 同步；**不解析 LLM 输出**，由 LLM 直接读写文件维护元数据。

---

## 1. 系统目标与非目标

### 1.1 目标（Must）

- 用 git（bare upstream + push 原子性）作为团队同步原语，支持多 agent 并行协作。
- agent 主循环保持单向：`sync -> pick -> prompt -> LLM -> test -> push -> repeat`。
- 抢占点（任务认领/锁）必须 **立即 commit + push**，让冲突在同步层自然显现。
- 其余变更（代码、PROGRESS、SIGNALS、子任务等）在 session 末尾 **单次 commit + push**。

### 1.2 非目标（Won’t）

- harness 不做“LLM 输出解析”（例如 NEEDS_INPUT: / SUBTASK: 前缀解析等）。
- harness 不做复杂状态机（needs_input/blocked 的创建与流转由 LLM 通过文件系统完成）。
- 目前不实现“超时自动释放 claimed 任务”（仅对 `current_tasks/` 锁做超时释放）。
- `dependencies` 字段目前不参与调度（只做信息承载）。

---

## 2. 核心概念（术语）

- **PROJECT_ROOT**：仓库根目录（由 `orchestrator_v2/infra/paths.py` 探测）。
- **Upstream（bare repo）**：`.agent-upstream.git/`，所有 agent 推送的“共享真相源”。
- **Workspace**：每个 agent 的独立 clone（团队模式下在 `.agent-workspaces/`；容器内路径由 `--workspace` 指定）。
- **Session**：agent_loop 的一次循环迭代（一次 LLM 调用 + 0/2 次测试 + 0/1 次 push）。
- **Task（重量级任务）**：`tasks/` 下的 markdown 文件（带 frontmatter），用于人工分配与追踪。
- **Work Lock（轻量锁/意图声明）**：`current_tasks/` 下的 markdown 文件（带 frontmatter），用于声明“我正在做什么”。

---

## 3. 目录协议（团队共享状态）

### 3.1 `tasks/`：任务队列（重量级）

状态目录（实际由代码创建/扫描）：

- `tasks/available/`：可认领任务池（agent 从这里挑选并原子认领）
- `tasks/claimed/`：已认领任务（仅会被 **同 agent_id** 继续 resume）
- `tasks/done/`：已完成任务
- `tasks/failed/`：失败终止任务（达到最大重试次数后由 harness 移入）
- `tasks/needs_input/`：需要人工决策（由 LLM 创建/移动；人类用 reply-task 回复）
- `tasks/blocked/`：被阻塞（由 LLM 创建/移动；人类用 reply-task 回复）
- `tasks/failures/`：失败记录（`{task_id}_attempt_{n}.md`，harness 写入）

### 3.2 `current_tasks/`：锁与意图（轻量）

默认初始化会创建：

- `current_tasks/manual/`：manual task 的锁（`manual/{task_id}`）
- `current_tasks/test/`：预留（当前 v2 没有“自动测试分工”逻辑）
- `current_tasks/merge/`：预留

锁文件的 key 与路径映射规则：

- lock key：例如 `manual/TASK-001`
- 文件路径：`current_tasks/manual/TASK-001.md`

### 3.3 其他元数据文件（由 LLM 维护）

- `PROJECT_CHARTER.md`：项目目标、优先级、约束（prompt 最先注入）
- `PROGRESS.md`：团队进度流水（LLM 完成工作后追加）
- `SIGNALS.md`：跨 agent 信号（LLM 发现冲突/注意点时追加）
- `DISCOVERIES.md`：Charter 未覆盖的发现（LLM 记录）
- `.agent-logs/`：运行日志（每个 agent 一个 log 文件）
- `project_env.json`：运行环境与命令配置（必须存在，否则 fast-fail）

---

## 4. 数据模型（文件格式要求）

### 4.1 Task 文件格式（必须有 frontmatter，否则会被忽略）

`tasks/*/*.md` 需要满足：

- 文件头必须以 `---` 开始的 frontmatter
- 推荐字段（`create_task()` 会生成）：
  - `id`：任务 ID（例如 `TASK-001`）
  - `title`：标题
  - `role`：`implementer | quality | docs | uat | assistant | performance | critic | dedup | any`
  - `priority`：整数，**越小越优先**
  - `dependencies`：列表（当前不参与调度，仅做信息）
  - `agent_id` / `claimed_at` / `completed_at` / `test_summary`：由系统/LLM补充

模板（建议用于手写 needs_input/blocked/subtask）：

```md
---
id: TASK-001
title: (一句话描述)
role: implementer
priority: 1
dependencies: []
---

## 背景

## 目标 / 验收标准

## 约束

## 测试
- test_fast: ...
- test: ...
```

### 4.2 Lock 文件格式（由 harness 生成；LLM 也可按此约定写）

至少包含：

- `key` / `agent_id` / `started_at`

monitor 的超时检测优先使用 `heartbeat_at`，否则回退到 `started_at`。

> v2 harness 不再 touch heartbeat；因此 **任务粒度/TTL 配置** 会直接影响团队模式稳定性（见第 7 节）。

---

## 5. CLI 能力（人类入口）

对应 `python -m orchestrator_v2 ...`：

- `init`
  - 创建目录结构与模板 `project_env.json`
  - 生成 `PROJECT_CHARTER.md / PROGRESS.md / SIGNALS.md / DISCOVERIES.md`
  - 创建 `.agent-upstream.git` 并安装 pre-receive CI gate
- `add-task "标题" --role <role> --priority <n> --description <text>`
  - 在 `tasks/available/` 创建一个新的 `TASK-xxx.md`
- `status`
  - 从 upstream 扫描并输出任务数量、活跃 agent（由 locks/claimed 推断）
- `reply-task TASK-001 --decision "你的决策"`
  - 将 `tasks/needs_input/` 或 `tasks/blocked/` 中的任务移回 `tasks/available/`
  - 并在正文末尾追加 `## 用户决策`
- `team [--build] [--roles implementer:2,quality:1,docs:1]`
  - 启动 Docker 团队 + monitor（可选 Feishu bot）

---

## 6. Agent 实际工作流（harness/agent_loop.py）

### 6.1 Session 逻辑（事实描述）

每个 session 的核心步骤：

1) `git pull --rebase` 同步 upstream  
2) 选工作：**已认领（claimed by me）> 新认领（available）> 自主模式（无任务）**  
3) `prompt_builder` 组装 prompt（注入 Charter / locks / claimed / signals / progress / failures / commands / 当前任务）  
4) 单次运行 LLM CLI（full-access）  
5) 若自主模式且无任何 git 变更 → 视为 idle  
6) 跑测试（implementer/quality/performance/dedup：fast + full；docs/uat/assistant/critic：不跑）
7) 完成收尾：任务 `claimed -> done`（UAT 任务由 harness 根据验收报告路由：PASS→done / FAIL→available 或 needs_input）、释放 lock  
8) 单次 `git commit` + `git push`（推送本 session 的所有变更）

### 6.2 任务认领与锁（原子点）

为避免两 agent 同时做同一任务：

- `claim_task()`：将 `tasks/available/{id}.md` 移到 `tasks/claimed/{id}.md`，并**立即 commit+push**。
- `try_acquire_lock()`：写 `current_tasks/...` 锁文件，并**立即 commit+push**。

> 这两个步骤是“分布式互斥”的唯一保证点。

### 6.3 测试失败与失败终止（max attempts）

- 测试失败时：写入 `tasks/failures/{id}_attempt_{n}.md`（不改变任务状态）
- 当失败次数达到上限（默认 3 次）：
  - 将 `tasks/claimed/{id}.md` 移入 `tasks/failed/{id}.md`
  - 删除 `current_tasks/manual/{id}.md`
  - **只提交并推送 `tasks/` + `current_tasks/` 元数据**（避免把失败的代码改动推上去）
  - reset 工作区到 upstream，进入下一轮

---

## 7. 任务分配策略（给“以后怎么分配任务”的明确约定）

这里的“分配”指：你如何把 backlog 写进 `tasks/available/`，让团队能稳定、低冲突地自动领取。

### 7.1 角色（role）怎么选

建议约定：

- `implementer`：新增/修改功能、修复 bug、重构（以交付代码为主）
- `quality`：清理 HACK/TODO/FIXME、补充异常处理、改善代码结构（不含重复代码合并）
- `docs`：README / 文档一致性、示例修订（默认不跑测试）
- `uat`：用户验收测试，通过公开接口验证功能（默认不跑测试）
- `assistant`：用户交互、需求转化、系统操作（默认不跑测试）
- `performance`：N+1 查询优化、慢路径识别、资源泄漏检测（可选角色，按需启用）
- `critic`：架构审查、设计反模式识别（只审查不改代码，可选角色）
- `dedup`：重复代码合并、配置常量统一（可选角色，按需启用）
- `any`：任何人都可做的小任务（例如格式化、简单 README 补充）

> harness 的挑选规则很简单：agent 只会领取 `role == 自己` 或 `role == any` 的任务。

**默认团队组成**（`team` 命令）：`assistant:1,implementer:2,quality:1,docs:1,uat:1`（6 个 agent）
**UI 自动启动默认**（`ui --auto-start`）：`implementer:2,quality:1,docs:1`（3 个 agent，不含 assistant/uat，因为 UI 本身充当用户界面）
**可选角色**：performance、critic、dedup 通过 `--roles` 参数按需启用

### 7.2 优先级（priority）怎么用

- `priority` 越小越优先（例如 1 最高、5 最低）。
- 推荐只用 1~5 五档，避免过细。
- 若同一 role 有多个任务，agent 会优先领取最小 priority 的那个。

### 7.3 任务粒度（必须小）

团队模式下 monitor 会对 `current_tasks/` 锁做超时释放（默认 200 分钟），而 v2 harness 不更新 heartbeat。

因此建议：

- **把任务拆到可以在 200 分钟内完成/明显推进并 push 的粒度**；
- 或者显式调整 `TASK_CLAIM_TIMEOUT_MINUTES`（否则会被 monitor 当成 stale lock 重启/释放）。

### 7.4 任务描述写法（减少 LLM 走弯路）

每个任务描述建议包含：

- 背景：为什么要做
- 目标/验收：完成时能客观判断对错
- 约束：不能做什么（例如禁止改测试、禁止引入兜底）
- 测试：应运行哪些命令（与 `project_env.json` 一致）
- 影响范围：建议触达的文件/目录（可选）

### 7.5 dependencies 字段的使用（当前为“信息字段”）

当前调度不看 `dependencies`，因此依赖关系需要用以下方式保证：

- **用 priority 做排序**（依赖项优先级更高）
- 或在任务正文中明确写 `Depends on: TASK-xxx`，让 agent 自行遵守

### 7.6 需要人工决策 / 被阻塞（needs_input / blocked）

约定一个“可操作”的闭环（harness 不替你做）：

1) agent 发现需要人工决策或被外部条件阻塞  
2) agent 将任务文件移动到：
   - `tasks/needs_input/{id}.md` 或 `tasks/blocked/{id}.md`
3) agent **释放对应 lock**（删除 `current_tasks/manual/{id}.md`）并 push  
4) 人类用 `reply-task {id} --decision "..."` 回复，任务回到 `tasks/available/`  
5) 任意 agent 重新领取并继续

> 关键点：要“移动”而不是“复制”，确保全局只有一个状态源。

### 7.7 任务卡死/误认领的人工处理方式（当前系统能力边界）

当前 v2 **不会自动释放** `tasks/claimed/` 的任务（只释放锁文件）。如果出现：

- agent 被永久下线、或想把 claimed 任务换人继续

建议操作流程（人类手动处理）：

1) 将 `tasks/claimed/{id}.md` 移回 `tasks/available/{id}.md`
2) 删除/清空 frontmatter 中的 `agent_id`、`claimed_at`（保持 `role/priority`）
3) 删除 `current_tasks/manual/{id}.md`（若存在）
4) commit + push 到 upstream

这样其他 agent 才能重新认领。

---

## 8. 附录：`project_env.json` 最小要求

`project_env.json` 必须存在，且至少建议配置：

```json
{
  "cli": "claude",
  "commands": {
    "install": "",
    "ci": ""
  },
  "test_stages": [
    "cd project/backend && python -m pytest tests/ -q",
    "cd project/frontend && npx vitest run"
  ],
  "test_fast_stages": [
    "cd project/backend && python -m pytest tests/ -q --lf --maxfail=5",
    "cd project/frontend && npx vitest run --bail 5"
  ],
  "test_timeout": 120,
  "test_timeout_fast": 60
}
```

- `cli`：`claude | codex | opencode`
- `test_stages`：多阶段测试命令数组（推荐），逐阶段执行，某阶段失败则停止后续阶段
- `test_fast_stages`：快速测试命令数组（推荐），用于 session 开始时的基线捕获和快速门禁
- `test_timeout` / `test_timeout_fast`：测试超时秒数（默认 120 / 60）
- `commands.ci`：pre-receive hook 使用的 CI 命令（可选）
- `commands.install`：依赖安装命令（可选）

向后兼容：如果没有 `test_stages`，runner 会降级使用 `commands.test` / `commands.test_fast` 单条命令模式。

