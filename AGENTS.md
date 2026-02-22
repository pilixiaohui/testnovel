# 项目导航地图

整个开发始终贯彻**快速失败**的编程思想，**禁止出现防御性编程**如各种兜底机制。

编码原则详见 `docs/coding-standards.md`。

## 项目结构

| 目录 | 用途 |
|------|------|
| `project/backend/` | Python 后端（FastAPI + 业务逻辑） |
| `project/frontend/` | 前端应用 |
| `orchestrator_v2/` | Agent 编排层（harness、CLI、SCM、测试） |
| `tasks/` | 任务状态机（available/claimed/done/failed/needs_input/blocked） |
| `features/` | Feature 列表（pending/done/blocked） |
| `decisions/` | 用户决策记录（threads/facts） |
| `docs/` | 项目知识库（设计文档、编码标准、架构约束、执行计划） |
| `scripts/` | 工具脚本（架构 linter、日志查看、健康检查） |

## 关键命令

所有命令定义在 `project_env.json` 的 `commands` 字段中：

- `install` — 安装依赖
- `ci` — CI 门禁（pytest）
- `lint_arch` — 架构约束检查
- `logs` — 查看应用日志
- `health` — 健康检查

测试策略见 `project_env.json` 的 `test_stages` / `test_fast_stages`。

## 架构规则

- 架构约束（文件大小、import 方向、命名）：`docs/architecture-constraints.md`
- 编码标准（KISS/YAGNI/SOLID/DRY）：`docs/coding-standards.md`
- push 时自动运行 `scripts/lint_arch.py`，违反约束会被拒绝

## 代码定位

| 内容 | 路径 |
|------|------|
| API routes | `project/backend/` |
| 前端组件 | `project/frontend/` |
| Agent prompts | `orchestrator_v2/agents/prompts/` |
| Agent 角色定义 | `orchestrator_v2/agents/roles.py` |
| 任务调度 | `orchestrator_v2/harness/task_picker.py` |
| Agent 主循环 | `orchestrator_v2/harness/agent_loop.py` |
| Prompt 组装 | `orchestrator_v2/harness/prompt_builder.py` |
| Git 同步 | `orchestrator_v2/scm/sync.py` |
| 测试 | `orchestrator_v2/tests/`、`project/backend/tests/`、`project/frontend/` |

## 工作流文件

| 文件 | 用途 |
|------|------|
| `PROGRESS.md` | 团队进度日志（agent 心跳记录） |
| `SIGNALS.md` | 跨 agent 信号（发现需要其他 agent 关注的问题时写入） |
| `DISCOVERIES.md` | Charter 未覆盖的发现 |
| `PROJECT_CHARTER.md` | 项目目标、优先级和约束 |
| `project_env.json` | 项目环境配置（CLI、命令、测试策略） |
