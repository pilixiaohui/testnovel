# World State Capability

## Requirement: World State Consistency

系统在多章生成过程中维护世界状态一致性。

### Scenario: Character state tracking

Given 主角"叶无痕"在第 3 章受伤
When 生成第 4 章内容
Then 第 4 章中叶无痕的状态反映受伤情况
And 不会出现"叶无痕健步如飞"的矛盾描写

### Scenario: Location continuity

Given 第 5 章场景在"华山之巅"
When 第 6 章开始时角色未移动
Then 第 6 章场景仍在"华山之巅"或有合理的转场描写

## Requirement: Entity Resolution

系统正确识别和追踪实体引用。

### Scenario: Character name consistency

Given 10 章内容全部生成
When 检查角色名称引用
Then 同一角色在所有章节中名称一致
And 无未定义的角色突然出现
