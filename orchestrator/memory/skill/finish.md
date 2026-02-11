# FINISH 输出规范

本文档定义 MAIN 代理输出 FINISH 时的格式规范。

## FINISH 前置检查（强制）

在输出 FINISH 前，**必须**逐项确认以下条件：

| 检查项 | 条件 | 不满足时 |
|--------|------|---------|
| dev_plan 状态 | 所有任务为 TODO 或 VERIFIED | 禁止 FINISH |
| DOING 任务 | 不存在 | 禁止 FINISH |
| BLOCKED 任务 | 不存在 | 禁止 FINISH |
| SYNTHESIZER 结论 | 最近一次为 PASS | 禁止 FINISH |
| BLOCKED 验证器 | 无 | 禁止 FINISH |
| evidence 分析 | 所有 BLOCKED 的 evidence 已分析且无代码错误 | 禁止 FINISH |

### 禁止 FINISH 的情况

- ❌ 存在 BLOCKED 验证器（无论原因）
- ❌ 存在 DOING 状态的任务
- ❌ SYNTHESIZER 结论为 REWORK 或 BLOCKED
- ❌ 未分析 BLOCKED 验证器的 evidence
- ❌ evidence 中包含未修复的代码错误（如 pageerror、TypeError）

---

## MAIN 输出格式

MAIN 输出 FINISH 时，必须使用以下 JSON 格式：

```json
{
  "next_agent": "FINISH",
  "reason": "完成原因",
  "history_append": "## Iteration {N}:\nnext_agent: FINISH\nreason: {原因}\ndev_plan: 所有任务已 VERIFIED",
  "dev_plan_next": "更新后的 dev_plan（所有任务标记为 VERIFIED）"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `next_agent` | ✅ | 固定为 `"FINISH"` |
| `reason` | ✅ | 完成原因，说明为什么可以结束 |
| `history_append` | ✅ | 追加到 project_history 的内容 |
| `dev_plan_next` | ✅ | 最终的 dev_plan，所有任务应为 VERIFIED |

---

## 示例

```json
{
  "next_agent": "FINISH",
  "reason": "M1 所有任务已通过 REVIEW 验收，代码审查无问题，测试覆盖率达标",
  "history_append": "## Iteration 12:\nnext_agent: FINISH\nreason: M1 全部 VERIFIED，REVIEW 确认代码质量合格\ndev_plan: M1-T1/T2/T3 全部 VERIFIED",
  "dev_plan_next": "# Dev Plan\n\n## M1: 前端基础骨架\n\n### M1-T1: 统一项目上下文\n- status: VERIFIED\n- evidence: REVIEW Iteration 11 PASS\n\n### M1-T2: 场景列表数据源\n- status: VERIFIED\n- evidence: REVIEW Iteration 11 PASS\n\n### M1-T3: 主链路可编辑\n- status: VERIFIED\n- evidence: REVIEW Iteration 11 PASS"
}
```

