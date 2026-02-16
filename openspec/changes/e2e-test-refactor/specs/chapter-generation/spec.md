# Chapter Generation Capability

## Requirement: Batch Chapter Generation

系统支持批量生成多章内容，保持前后一致性。

### Scenario: Generate 10 chapters sequentially

Given 已有完整的 Snowflake 规划（10章场景）
When 用户触发批量生成 10 章
Then 每章生成约 2000 字内容
And 总字数在 18000-22000 字范围内
And 章节之间情节连贯

### Scenario: Chapter content quality check

Given 已生成一章内容
When 验证章节质量
Then 包含场景描写（环境、氛围）
And 包含角色对话（至少 3 轮）
And 包含动作描写
And 无重复段落

## Requirement: Chapter Persistence

生成的章节内容正确持久化。

### Scenario: Save and reload chapter

Given 已生成第 3 章内容
When 保存后重新加载
Then 内容完全一致
And 元数据（字数、生成时间、版本）正确

## Requirement: Chapter Regeneration

用户可以重新生成不满意的章节。

### Scenario: Regenerate single chapter

Given 已生成 10 章
When 用户对第 5 章不满意，触发重新生成
Then 第 5 章内容更新
And 其他章节不受影响
And 新内容与前后章节保持连贯
