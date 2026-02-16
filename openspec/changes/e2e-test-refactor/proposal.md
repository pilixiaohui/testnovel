## Why

当前项目的测试代码分散在 unit/integration/perf 目录中，缺少一套模拟真实用户创作流程的端到端测试。现有测试只验证单个 API 端点或模型，无法覆盖"用户从零开始创作一部完整小说"的全链路场景。需要一套以"生成10章2000字武侠短篇"为目标的 E2E 测试，确保系统在真实创作习惯下的可靠性。

## What Changes

- 新增 E2E 测试套件，模拟完整的武侠小说创作流程
- 覆盖 Snowflake 方法的 5 步创作流程（创意→大纲→角色→场景→章节）
- 测试章节生成、审阅反馈、世界状态一致性、导出等核心功能
- 测试前端用户体验关键路径（页面导航、表单提交、实时反馈）

## Capabilities

### New Capabilities
- `creation-flow`: 完整创作流程 E2E 测试（Snowflake 5步）
- `chapter-generation`: 章节批量生成与质量验证
- `review-feedback`: 审阅反馈循环测试
- `world-state`: 世界状态一致性检查
- `story-export`: 故事导出与格式验证

### Modified Capabilities

## Impact

- 新增 tests/e2e/ 目录
- 需要 mock LLM 服务（避免真实 API 调用）
- 需要测试数据库 fixture
- 前端 E2E 需要 Playwright 或类似工具
