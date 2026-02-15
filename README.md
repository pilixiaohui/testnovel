# AI Novel V3 - 多智能体工作流系统

基于 **Git + Docker + Bare Repo** 的多智能体编排系统，用于开发 AI 小说生成引擎（Snowflake Engine）。

## 📁 项目结构

```
ainovel_v3/
│
├── orchestrator/                # 🎯 Agent Team Orchestrator（Git + Docker）
├── orchestrator.py              # 🎯 Orchestrator CLI 入口（等价于 `python -m orchestrator`）
├── test_project_module.py       # ✅ 模块测试脚本
│
├── project/                     # 📦 AI 小说项目（具体实现）
│   ├── __init__.py              # Orchestrator 配置模块
│   ├── config.py                # ProjectConfig 类
│   ├── templates.py             # ProjectTemplates 类
│   ├── README.md                # 项目文档
│   │
│   ├── backend/                 # AI 小说后端服务
│   │   ├── app/                 # FastAPI 应用
│   │   ├── data/                # Kuzu 数据库
│   │   └── tests/               # 单元测试
│   │
│   └── scripts/                 # 测试和检查脚本
│
└── doc/                         # 📚 文档（含博客原文与对标说明）
```

## 🎯 核心概念

### 1. Orchestrator（通用框架）

基于 **Bare upstream git repo + 多容器并行 agent** 的编排器（对标 `doc/多智能体团队最新博客.md` 的 harness 思路）：

- **implementer / quality / docs**：角色分工（实现 / 质量 / 文档）
- **同步原语**：通过 `.agent-upstream.git`（bare repo）进行 pull/push，同步状态与变更
- **并行去重**：通过 `current_tasks/` 轻量锁 + `tasks/` 重量级任务队列协调
- **测试反馈**：真实跑测试，输出 `ERROR:` / `STATS:` / `TOP_FAILURES:` 等高密度摘要，便于 LLM 自主导航

**特点**：
- ✅ 完全通用，可用于任何项目
- ✅ 快速失败（Fail Fast）设计
- ✅ 提供 Web UI 界面
- ✅ Fast-then-Full 测试策略 + 失败学习（tasks/failures）

### 2. Project（具体实现）

AI 小说生成系统的具体实现：

- **backend/**：FastAPI + Kuzu 图数据库 + Gemini API
- **scripts/**：测试和健康检查脚本
- **config.py/templates.py**：Orchestrator 配置

**核心功能**：
- 小说结构管理（Root、Branch、Scene）
- 逻辑一致性检查
- 状态管理和追踪
- 协商式内容生成

## 🚀 快速开始

### 1. 启动 AI 小说后端

```bash
# 进入后端目录
cd project/backend

# 安装依赖
pip install -e .

# 配置环境变量
cp .env.example .env
# 编辑 .env 设置 GEMINI_API_KEY

# 启动服务
uvicorn app.main:app --reload --port 8000
```

### 2. 运行 Orchestrator

```bash
# 初始化（生成 project_env.json、tasks/、current_tasks/、PROGRESS.md，并创建 bare upstream + CI gate）
python -m orchestrator init

# 启动团队（需要 docker；并在环境中设置 OPENAI_API_KEY/ANTHROPIC_API_KEY）
python -m orchestrator team --build --roles implementer:2,quality:1,docs:1

# 添加任务（可选）
python -m orchestrator add-task "修复 bug XYZ" --role implementer --priority 1 --description "..."

# 查看状态
python -m orchestrator status
```

### 2.1 运行隔离策略

```bash
# 每个 agent 在独立 Docker 容器内运行：
# - /upstream: 挂载 bare upstream repo
# - /workspace: agent 自己的 clone，用于开发/测试/提交
# 细节见：doc/agent_team_orchestrator.md
```

### 3. 运行测试

```bash
# 测试 project 模块
python test_project_module.py

# 后端健康检查
python project/scripts/graph_health_check.py --db project/backend/data/snowflake.db

# 端到端集成测试
python project/scripts/cyberpunk_integration_test.py
```

## 📚 文档

- [Agent Team Orchestrator 使用说明](doc/agent_team_orchestrator.md)
- [多智能体团队博客原文](doc/多智能体团队最新博客.md)
- [Project 模块文档](project/README.md) - AI 小说项目文档
- [Backend 文档](project/backend/README.md) - 后端服务文档

## 🏗️ 架构设计

### 分离设计

```
┌─────────────────────────────────────┐
│   Orchestrator Framework (通用)     │
│   - orchestrator.py                 │
│   - orchestrator/                   │
│   - tasks/ + current_tasks/         │
│   - .agent-upstream.git             │
└─────────────────────────────────────┘
              ↑ 使用配置
              │
┌─────────────────────────────────────┐
│   Project Implementation (具体)     │
│   - project/config.py               │
│   - project/templates.py            │
│   - project/backend/                │
│   - project/scripts/                │
└─────────────────────────────────────┘
```

### Git + Docker 并行模式（对标博客）

```
current_tasks/*.md  ←─┐
tasks/*.md           ←┼─ 共享状态（通过 bare upstream repo 同步）
PROGRESS.md          ←┘

    ↓ pull/merge     ↓ push

┌────────┐      ┌────────┐
│ Agent  │ ───→ │ upstream│
└────────┘      └────────┘
                     ↓
              ┌──────────────┐
              │ 其他 agents  │
              └──────────────┘
```

## 🎨 特色功能

### 1. Web UI

- 实时日志流
- 用户决策交互
- 文件编辑器
- 状态监控

### 2. 快速失败

- 缺少必要文件 → 立即退出
- MAIN 输出非纯 JSON → 立即退出
- 字段不符合契约 → 立即退出
- 未写日志/工单 → 立即退出

### 3. 可复用性

- orchestrator.py 可直接用于其他项目
- 只需替换 project/ 模块即可

## 🔧 开发指南

### 添加新代理

1. 在 `orchestrator/agents/prompts/` 添加角色 prompt
2. 在 `orchestrator/core/config.py` 中为 role 选择 CLI 与 extra_args

### 自定义项目配置

1. 编辑 `project_env.json`（重点是 `commands.test/test_fast/ci`）
2. 参考 `doc/agent_team_orchestrator.md`

### 迁移到新项目

1. 复制 `orchestrator/` + `orchestrator.py` + `pyproject.toml`
2. 在新项目根目录运行 `python -m orchestrator init`
3. 配好 `project_env.json` 的 `commands.*`（测试/CI/Oracle）
4. `python -m orchestrator team --build`

## 📝 许可证

(添加许可证信息)

## 👥 贡献

(添加贡献指南)
