# Dev Plan (Snapshot)

> 本文件由 MAIN 维护（可覆盖编辑）。它是"当前计划与进度"的快照；事实证据以 `orchestrator/reports/report_review.md` 与 `orchestrator/memory/project_history.md` 为准。

## 约束（强制）
- 任务总数必须保持在"几十条"以内（少而硬）
- 每个任务块必须包含：`status / acceptance / evidence`
- status 只允许：TODO / DOING / BLOCKED / DONE / VERIFIED
- 可选字段：`verification_status: <PENDING_DEV_VALIDATION|DEV_VALIDATED|TEST_PASSED|VERIFIED|REVIEW_REJECTED>` 用于验证闭环跟踪
- 只有 **REVIEW 的证据** 才能把 DONE -> VERIFIED（evidence 必须引用 Iteration 与验证方式）

---

## Milestone M0: 引导与黑板契约

### M0-T1: 建立 dev_plan 状态机
- status: TODO
- acceptance:
- `orchestrator/memory/dev_plan.md` 存在并遵循固定字段
- 每轮更新在 `orchestrator/memory/project_history.md` 留痕（说明改了什么/为什么）
- evidence:

### M0-T2: 审阅代理输出可核实证据
- status: TODO
- acceptance:
- `orchestrator/reports/report_review.md` 包含可复现的命令与关键输出摘要
  - 进度核实：逐条对照 dev_plan 的任务给出 PASS/FAIL 与证据
- evidence:
