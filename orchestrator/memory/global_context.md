# Global Context

请在此维护本项目的全局目标、约束与黑板协议（Blackboard Contract）。

## 必要约束
- JSON 字段使用 `snake_case`
- 快速失败：不要添加兜底/容错逻辑来让流程继续
- 允许测试双/Mock：测试可使用真实依赖或测试双

## Blackboard Paths（以项目根目录为基准）
- `orchestrator/memory/`：长期记忆、全局上下文
- `orchestrator/memory/prompts/`：各代理提示词（固定文件，重置时保留）
- `orchestrator/memory/dev_plan.md`：全局开发计划快照（MAIN 维护，REVIEW 核实）
- New Task 目标：由用户在 New Task 时输入，追加写入 `orchestrator/memory/project_history.md`（MAIN 注入 history 后读取）
- `orchestrator/workspace/`：各子代理工单（由 MAIN 覆盖写入）
- `orchestrator/reports/`：各子代理输出报告（由编排器保存）
