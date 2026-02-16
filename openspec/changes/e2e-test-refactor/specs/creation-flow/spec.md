# Creation Flow Capability

## Requirement: Snowflake Step 1 - Story Idea

用户可以输入一句话故事创意，系统生成结构化的故事核心。

### Scenario: Create wuxia story idea

Given 用户在创作页面
When 用户输入"一个失忆剑客寻找身世真相的武侠故事"
Then 系统生成包含主题、冲突、基调的故事核心
And 故事核心保存到数据库

### Scenario: Validate story idea format

Given 系统生成了故事核心
When 验证返回的数据结构
Then 包含 title、premise、theme、conflict 字段
And 每个字段非空

## Requirement: Snowflake Step 2 - Story Expansion

用户可以将一句话创意扩展为三幕结构大纲。

### Scenario: Expand idea to three-act structure

Given 已有故事核心
When 用户点击"扩展大纲"
Then 系统生成包含开端、发展、高潮、结局的三幕结构
And 大纲总字数在 500-2000 字之间

## Requirement: Snowflake Step 3 - Character Creation

用户可以创建和编辑角色档案。

### Scenario: Create main character

Given 已有故事大纲
When 用户创建主角"叶无痕"
Then 角色档案包含姓名、背景、动机、性格特征
And 角色与故事冲突关联

### Scenario: Create supporting characters

Given 已有主角
When 用户批量创建配角（师父、反派、红颜知己）
Then 每个角色有独立档案
And 角色关系图正确建立

## Requirement: Snowflake Step 4 - Scene Planning

用户可以规划每章的场景节点。

### Scenario: Plan 10 chapter scenes

Given 已有角色和大纲
When 用户规划 10 章场景
Then 每章有标题、摘要、涉及角色、场景地点
And 场景之间有因果关联

## Requirement: Snowflake Step 5 - Chapter Generation

系统根据场景规划生成章节内容。

### Scenario: Generate first chapter

Given 已有完整的场景规划
When 用户触发第一章生成
Then 生成约 2000 字的章节内容
And 内容包含场景描写、对话、动作
And 风格符合武侠小说特征
