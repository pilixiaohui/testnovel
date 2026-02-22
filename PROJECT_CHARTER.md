# Project Charter

<!--
  本文档由 agent 自动维护，用户无需手动编辑
  - 目标、优先级：从用户飞书消息和 features/ 自动提取
  - 核心模块：从代码结构自动生成
  - 架构约束：从 docs/architecture-constraints.md 同步
  - 验收标准：从 features/*/verify_type 自动生成

  最后更新：由 assistant/gardener agent 维护
-->

## 目标

<!-- 从 features/done/ 和 features/pending/ 自动提取 -->
<!-- 用户通过飞书发送需求时，assistant 会自动添加新目标 -->

- [ ] 目标1: (待 assistant 从用户消息中提取)

## 当前优先级（从高到低）

<!-- 从用户飞书消息和最近任务创建时间自动推断 -->
<!-- 最新的用户请求会自动插入到列表顶部 -->

1. (待 assistant 从用户消息中提取)

## 核心模块

<!-- 由 docs/gardener agent 从项目结构自动生成 -->

| 模块 | 路径 | 说明 |
|------|------|------|
| 后端 API | project/backend/app/ | FastAPI 服务 |
| 前端 UI | project/frontend/ | React 应用 |

## 架构约束

<!-- 从 docs/architecture-constraints.md 自动同步 -->

- Python ≥ 3.11
- 文件不超过 500 行

## 验收标准

<!-- 从 features/*/verify_type 模式自动生成 -->

- 后端测试全部通过：`cd project/backend && python -m pytest tests/ -q`
- 前端测试全部通过：`cd project/frontend && npx vitest run`

## 不做的事

<!-- 用户通过飞书明确说"不要做X"时，assistant 会添加到此列表 -->

- (待用户明确边界)
