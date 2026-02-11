# 技能索引

**警告**：输出 JSON 前必须读取对应的 skill 文件，否则格式错误会导致工作流失败重试。

## 使用规则（强制）

1. **确定 next_agent**：分析当前情况，确定要派发的代理类型
2. **读取 skill 文件**：使用 Read 工具读取对应的 skill 文档
3. **按规范输出**：严格按照 skill 文档中的格式输出 JSON

## 约束

- **必须读取 skill 文件**：不读取直接输出会导致格式错误
- 每次决策只读取一个 skill 文件
- 优先选择更具体的技能

---

<available_skills>

## user_decision
- **位置**: `memory/skill/user_decision.md`
- **触发条件**: 需要用户介入决策时
- **适用场景**:
  - 需求不清晰，存在多种理解
  - 方案选择，需要用户确认方向
  - 权限/环境问题，需要用户处理
  - 连续失败，需要用户介入
  - 文档修正需要用户确认

## task_implementer
- **位置**: `memory/skill/task_implementer.md`
- **触发条件**: 需要 TDD 实现（测试+实现）时
- **适用场景**:
  - 新任务：需要完整的 TDD 流程（红灯→绿灯）
  - SYNTHESIZER REWORK：验证失败需要修复
  - 功能实现：需要编写测试和实现代码

## task_validate
- **位置**: `memory/skill/task_validate.md`
- **触发条件**: IMPLEMENTER 报告 PASS 后触发并行验证
- **适用场景**:
  - IMPLEMENTER 完成 TDD 流程并报告 PASS
  - 需要多角度黑盒验证（测试运行、需求验证、作弊检测、边界测试）

## finish
- **位置**: `memory/skill/finish.md`
- **触发条件**: 所有任务已 VERIFIED 时
- **适用场景**:
  - dev_plan 中所有非 TODO 任务均为 VERIFIED
  - 无 FAIL/BLOCKED 状态
  - 准备输出 FINISH 决策

</available_skills>

---

## 决策类型与技能映射速查

| 决策类型 | 对应技能 | 关键判断条件 |
|----------|----------|--------------|
| 派发 IMPLEMENTER | task_implementer | 新任务 / SYNTHESIZER REWORK |
| 派发 VALIDATE | task_validate | IMPLEMENTER 报告 PASS |
| 升级 USER | user_decision | 需求不清 / 连续失败 / 权限问题 |
| 完成项目 | finish | 全部 VERIFIED |

---

## Context-centric 架构说明

本系统采用 Context-centric 架构，基于 Anthropic 多智能体设计原则：

1. **IMPLEMENTER**：TDD 全栈实现者，在单次会话中完成测试+实现，保持完整上下文
2. **VALIDATE**：触发并行黑盒验证（TEST_RUNNER、REQUIREMENT_VALIDATOR、ANTI_CHEAT_DETECTOR、EDGE_CASE_TESTER）
3. **SYNTHESIZER**：汇总验证结果，做出 PASS/REWORK/BLOCKED 决策

### TDD 流程

```
IMPLEMENTER(红灯→绿灯) → VALIDATE(并行验证) → SYNTHESIZER(汇总) → VERIFIED
         ↑                                        ↓
         └────────────── REWORK 时循环 ───────────┘
```
