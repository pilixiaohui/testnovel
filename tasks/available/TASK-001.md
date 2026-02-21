---
id: TASK-001
title: 武侠短篇小说 e2e 全流程测试
role: implementer
priority: 1
dependencies: []
---

## 目标

为系统编写一套完整的端到端测试，模拟用户真实的创作过程：以生成10章、每章约2000字的短篇武侠小说为测试目标，全面测试系统的所有功能。

## 核心要求

### 1. 模拟真实创作流程（按用户实际操作顺序）

测试必须按照前端用户的真实操作路径设计，完整覆盖以下流程：

**阶段一：雪花法构思（Snowflake）**
- Step 1: 用户输入一句话故事核心 → POST /api/v1/snowflake/step1 → 返回多个扩展方向
- Step 2: 用户选择/编辑方向 → POST /api/v1/snowflake/step2 → 生成 SnowflakeRoot（logline, theme, ending）
- Step 3: 生成角色表 → POST /api/v1/snowflake/step3 → 返回 CharacterSheet 列表
- Step 4: 生成场景大纲 → POST /api/v1/snowflake/step4 → 返回 Step4Result（含 scenes）
- Step 5a: 保存到图数据库 → POST /api/v1/snowflake/step5a → 返回 root_id
- Step 5b: 验证结构完整性 → POST /api/v1/snowflake/step5b → 确认 entities/scenes 数量正确

**阶段二：世界观管理（World）**
- 查看实体列表 → GET /api/v1/roots/{root_id}/...
- 设置锚点（关键剧情节点）→ POST /api/v1/roots/{root_id}/anchors
- 创建支线剧情 → POST /api/v1/roots/{root_id}/subplots

**阶段三：章节渲染（Editor）**
- 获取幕/章结构 → GET /api/v1/roots/{root_id}/acts → GET /api/v1/acts/{act_id}/chapters
- 逐章渲染 → POST /api/v1/chapters/{chapter_id}/render
- 验证字数范围（1800-2200字）
- 章节审阅 → POST /api/v1/chapters/{chapter_id}/review

**阶段四：模拟引擎（Simulation，可选）**
- 角色 agent 初始化 → POST /api/v1/entities/{id}/agent/init
- 角色决策 → POST /api/v1/entities/{id}/agent/decide
- DM 仲裁 → POST /api/v1/dm/arbitrate
- 模拟回合 → POST /api/v1/simulation/round
- 场景模拟 → POST /api/v1/simulation/scene

### 2. 测试设计原则

- **符合真实创作习惯**：测试数据使用有意义的武侠小说内容（如"江湖少年复仇记"），不用 lorem ipsum
- **考虑前端用户体验**：每个 API 调用对应前端的一个用户操作，验证返回数据能被前端正确渲染
- **渐进式验证**：每一步都验证前一步的输出是否可以作为下一步的输入
- **错误路径覆盖**：测试参数缺失、类型错误、非法状态转换等边界情况
- **幂等性检查**：重复调用同一接口不应产生副作用

### 3. 技术要求

- 使用 pytest + FastAPI TestClient
- 所有 LLM 调用必须 mock（使用 monkeypatch 或 dependency_overrides）
- 图数据库操作使用 stub（参考 tests/shared_stubs.py 中的 GraphStorageStub）
- 测试文件放在 project/backend/tests/ 下，按功能模块组织
- 确保测试可以在没有外部依赖（Memgraph、LLM API）的情况下运行
- 所有测试必须通过 `python -m pytest tests/ -q`

### 4. 验收标准

- [ ] 完整覆盖 Snowflake step1-step5b 流程
- [ ] 覆盖章节渲染和审阅流程
- [ ] 覆盖世界观管理（锚点、支线）
- [ ] 覆盖模拟引擎基本流程
- [ ] 所有测试通过，无 skip、无 xfail
- [ ] 测试数据使用武侠小说主题内容
- [ ] 错误路径至少覆盖每个主要端点的 422/400 场景
