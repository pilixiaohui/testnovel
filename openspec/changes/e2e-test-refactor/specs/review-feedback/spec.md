# Review Feedback Capability

## Requirement: Chapter Review

用户可以对生成的章节进行审阅并提供反馈。

### Scenario: Submit review feedback

Given 已生成第 1 章
When 用户提交审阅意见"对话太少，需要增加师徒互动"
Then 系统记录反馈
And 反馈关联到具体章节

### Scenario: Apply feedback and regenerate

Given 第 1 章有审阅反馈
When 用户触发基于反馈的重新生成
Then 新版本章节体现了反馈意见
And 保留原版本供对比

## Requirement: Review History

系统保留完整的审阅历史。

### Scenario: View review history

Given 第 1 章经过 3 次审阅
When 用户查看审阅历史
Then 显示所有版本和对应反馈
And 可以回退到任意历史版本
