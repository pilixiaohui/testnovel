---
id: TASK-001
title: 生成武侠短篇小说大纲
role: implementer
priority: 1
dependencies: []
agent_id: implementer-1
claimed_at: 2026-02-22T03:06:34+00:00
---

使用雪花法生成一篇10章武侠短篇小说的完整大纲。要求：1) 调用 POST /api/v1/snowflake/step1 生成10个logline候选 2) 选择最佳logline调用step2生成故事骨架 3) 调用step3生成角色 4) 调用step4生成场景列表 5) 调用step5a生成三幕结构 6) 调用step5b生成10个章节。每章约1000字，武侠题材。在 PROGRESS.md 记录每一步的结果。
