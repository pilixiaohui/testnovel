---
id: TASK-004
title: [BUG] render API 返回 400 导致 Memgraph 数据库被清空
role: implementer
priority: 0
dependencies: []
---

## Bug 描述

当调用 `POST /api/v1/chapters/{id}/render` 返回 400 错误（例如字数验证失败）时，整个 Memgraph 数据库的数据被意外清空。

**影响范围**：严重 - 导致所有故事数据丢失（Root、Commit、Act、Chapter 节点全部被删除）

## 复现步骤

1. 创建一个故事并生成章节
2. 调用 render API 触发 400 错误（例如字数不符合要求）
3. 检查 Memgraph 数据库：所有节点计数变为 0

## 观察到的行为

从日志中可以看到：
```
before_counts: {'Root': 1, 'Commit': 1, 'Act': 1, 'Chapter': 1}
after_counts: {'Root': 0, 'Commit': 0, 'Act': 0, 'Chapter': 0}
```

## 预期行为

render API 返回 400 错误时，不应该影响数据库中的现有数据。

## 根因分析方向

1. 检查 `project/backend/app/main.py` 中 `render_chapter_endpoint` (lines 1151-1196) 的错误处理
2. 检查 `project/backend/app/storage/memgraph_storage.py` 中的事务管理 (lines 235-244)
3. 确认 HTTPException(400) 是否触发了不正确的 rollback 或 cleanup 逻辑
4. 检查是否有全局错误处理器在 400 错误时执行了数据库清理

## 修复要求

1. 修复 bug，确保 render API 返回 400 时不会清空数据库
2. 添加测试用例验证修复：
   - 测试 render 400 错误后数据库数据完整性
   - 测试事务回滚不影响已提交的数据
3. 在 PROGRESS.md 记录修复过程和测试结果

## 发现上下文

在执行 TASK-002（渲染全部10章内容）时发现此 bug。该 bug 阻塞了 TASK-002 的正常完成。
