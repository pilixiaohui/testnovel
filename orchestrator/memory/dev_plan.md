# Dev Plan (Snapshot)

> 本文件由 MAIN 维护（可覆盖编辑）。

## 约束（强制）
- 任务总数必须保持在几十条以内
- 每个任务块必须包含：status / acceptance / evidence
- status 只允许：TODO / DOING / BLOCKED / DONE / VERIFIED
- 只有 REVIEW 的证据才能把 DONE -> VERIFIED

---

## Milestone M1: 前端全面修复

### M1-T1: 调研并修复前端所有已知问题
- status: DOING
- acceptance:
  - 用户报告的7个问题均已验证并修复
  - 项目可正常创建、保存、加载
  - 雪花流程各步骤完整展示生成内容
  - 设置页面显示真实LLM配置
  - 标签页切换正常无JS错误
  - 推演功能前端可正常触发并展示结果
  - 前端单元测试通过
  - 10章短篇小说端到端验收通过
- evidence:
