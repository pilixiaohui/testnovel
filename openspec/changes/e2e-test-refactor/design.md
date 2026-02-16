## Design Overview

采用分层 E2E 测试架构，以"武侠短篇小说创作"为贯穿场景。

## 测试架构

```
tests/e2e/
├── conftest.py              # 共享 fixture（mock LLM、测试数据库、API client）
├── test_creation_flow.py    # Snowflake 5步创作流程
├── test_chapter_generation.py # 10章批量生成
├── test_review_feedback.py  # 审阅反馈循环
├── test_world_state.py      # 世界状态一致性
├── test_story_export.py     # 导出验证
└── fixtures/
    └── wuxia_seed.json      # 武侠小说种子数据
```

## Mock LLM 策略

使用 deterministic mock 替代真实 LLM 调用，返回预设的武侠风格内容。

## 测试数据

武侠短篇设定：
- 标题：《剑影江湖》
- 10章，每章约2000字
- 角色：主角剑客、师父、反派、红颜知己
- 场景：武林大会、密室修炼、最终决战
