# Constitution

## Workflow
- 模式：spec-driven (OpenSpec style)
- 变更入口：`orchestrator/memory/specs/changes/<change_id>/`
- 执行入口：仅允许从 `tasks.md` 的任务 ID 派发 IMPLEMENTER

## Non-goals
- 禁止在运行时使用 legacy `spec_anchor/spec_gate` 门禁链路
- 禁止无 change_id 的实现任务

## Quality Gates
- 实现前：spec 草案必须经过用户确认
- 实现后：验证阶段必须产出可追溯证据
