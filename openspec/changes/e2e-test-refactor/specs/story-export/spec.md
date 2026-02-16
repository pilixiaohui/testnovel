# Story Export Capability

## Requirement: Full Story Export

用户可以将完整故事导出为多种格式。

### Scenario: Export as markdown

Given 10 章内容全部完成
When 用户导出为 Markdown 格式
Then 生成包含目录、章节标题、正文的完整文档
And 格式正确可渲染

### Scenario: Export metadata

Given 导出完整故事
When 检查导出文件
Then 包含故事元数据（标题、作者、创建时间、总字数）
And 包含角色列表
And 包含章节目录
