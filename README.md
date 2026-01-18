# AI Novel V3 - 多智能体工作流系统

基于黑板模式的多智能体编排系统，用于开发 AI 小说生成引擎（Snowflake Engine）。

## 📁 项目结构

```
ainovel_v3/
│
├── orchestrator.py              # 🎯 多智能体编排器（通用框架）
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
├── memory/                      # 🧠 Orchestrator 长期记忆
│   ├── global_context.md        # 全局上下文
│   ├── project_history.md       # 项目历史（追加）
│   ├── dev_plan.md              # 开发计划快照
│   └── subagent_prompt_*.md     # 各代理提示词
│
├── workspace/                   # 📋 Orchestrator 工作区
│   ├── main/                    # MAIN 代理工作区
│   ├── test/                    # TEST 代理工单
│   ├── dev/                     # DEV 代理工单
│   └── review/                  # REVIEW 代理工单
│
└── reports/                     # 📊 Orchestrator 报告输出
    ├── report_test.md           # TEST 代理报告
    ├── report_dev.md            # DEV 代理报告
    ├── report_review.md         # REVIEW 代理报告
    └── orchestrator.log         # 编排器日志
```

## 🎯 核心概念

### 1. Orchestrator（通用框架）

基于**黑板模式（Blackboard Pattern）**的多智能体编排器：

- **MAIN**：指挥官 + 记录员，负责读黑板、写日志、写工单、输出调度 JSON
- **TEST/DEV/REVIEW**：无状态执行者，只读取各自工单文件执行并输出报告
- **Orchestrator**：搬运工，只负责触发 `codex exec`、落盘最后消息、解析 JSON、控制循环

**特点**：
- ✅ 完全通用，可用于任何项目
- ✅ 快速失败（Fail Fast）设计
- ✅ 提供 Web UI 界面
- ✅ 会话持久化和恢复

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
# 启动 Web UI（推荐）
python orchestrator.py --ui
# 访问 http://127.0.0.1:8765

# 或命令行模式
python orchestrator.py --max-iterations 10 --task "实现新功能"

# 或新任务模式
python orchestrator.py --new-task --task "修复 bug XYZ"
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

- [Orchestrator 重构总结](REFACTORING_SUMMARY.md) - 代码重构详细说明
- [Project 模块文档](project/README.md) - AI 小说项目文档
- [Backend 文档](project/backend/README.md) - 后端服务文档

## 🏗️ 架构设计

### 分离设计

```
┌─────────────────────────────────────┐
│   Orchestrator Framework (通用)     │
│   - orchestrator.py                 │
│   - memory/                         │
│   - workspace/                      │
│   - reports/                        │
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

### 黑板模式

```
memory/project_history.md  ←─┐
memory/dev_plan.md         ←─┼─ 黑板（共享状态）
workspace/*/current_task.md ←┘

    ↓ 读取          ↓ 写入

┌────────┐      ┌────────┐
│  MAIN  │ ───→ │工单文件│
└────────┘      └────────┘
                     ↓
              ┌──────────────┐
              │ TEST/DEV/    │
              │ REVIEW       │
              └──────────────┘
                     ↓
              ┌──────────────┐
              │ 报告文件      │
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

1. 修改 `project/config.py` 添加代理名称
2. 创建提示词文件 `memory/subagent_prompt_<agent>.md`
3. orchestrator 自动支持

### 自定义项目配置

1. 修改 `project/config.py` 中的配置
2. 修改 `project/templates.py` 中的模板
3. orchestrator.py 无需修改

### 迁移到新项目

1. 复制 `orchestrator.py` 到新项目
2. 复制 `project/` 目录并修改配置
3. 创建 `memory/` 初始文件
4. 运行！

## 📝 许可证

(添加许可证信息)

## 👥 贡献

(添加贡献指南)
