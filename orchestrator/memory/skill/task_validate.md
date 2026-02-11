# VALIDATE 任务派发规范

本文档定义 MAIN 代理派发 VALIDATE 决策时的规范。

## 触发条件

当 IMPLEMENTER 报告 `结论：PASS` 时，MAIN 必须派发 VALIDATE 触发并行验证。

**禁止跳过 VALIDATE**：即使 IMPLEMENTER 自测通过，也必须经过独立的黑盒验证。

---

## 并行验证器

VALIDATE 会触发 4 个并行黑盒验证器：

| 验证器 | 职责 | 黑盒原则 |
|--------|------|----------|
| **TEST_RUNNER** | 运行测试命令，报告结果 | 只执行命令，不理解实现 |
| **REQUIREMENT_VALIDATOR** | 对比需求与实现 | 只做需求对比，不分析代码 |
| **ANTI_CHEAT_DETECTOR** | 检测硬编码、mock滥用 | 只做模式匹配，不理解业务 |
| **EDGE_CASE_TESTER** | 生成边界测试 | 只基于 API 签名，不深入实现 |

---

## SYNTHESIZER 汇总

验证器完成后，SYNTHESIZER 汇总所有结果并做出决策：

| 决策 | 条件 | MAIN 下一步 |
|------|------|------------|
| **PASS** | 所有验证器通过 | 标记任务 VERIFIED，推进下一任务 |
| **REWORK** | 任何验证器失败 | 派发 IMPLEMENTER 修复问题 |
| **BLOCKED** | 验证器无法执行 | 评估原因，USER 或 IMPLEMENTER |

---

## MAIN 输出格式

MAIN 派发 VALIDATE 时，使用以下 JSON 格式：

```json
{
  "next_agent": "VALIDATE",
  "reason": "IMPLEMENTER 报告 PASS，触发并行验证",
  "history_append": "## Iteration {N}:\nnext_agent: VALIDATE\nreason: 实现完成，进行多角度验证",
  "task_body": null,
  "dev_plan_next": null
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `next_agent` | ✅ | 固定为 `"VALIDATE"` |
| `reason` | ✅ | 派发原因 |
| `history_append` | ✅ | 追加到 project_history 的内容 |
| `task_body` | ✅ | **必须为 `null`**（VALIDATE/FINISH/USER 不传工单正文） |
| `dev_plan_next` | ✅ | **必须为 `null`**（等 SYNTHESIZER 结果再更新） |

---

## 验证流程

```
MAIN 派发 VALIDATE
       ↓
┌──────────────────────────────────────────────────┐
│              并行执行 4 个验证器                   │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  │
│  │TEST_RUNNER │  │REQUIREMENT │  │ANTI_CHEAT  │  │
│  │            │  │_VALIDATOR  │  │_DETECTOR   │  │
│  └────────────┘  └────────────┘  └────────────┘  │
│                  ┌────────────┐                   │
│                  │EDGE_CASE   │                   │
│                  │_TESTER     │                   │
│                  └────────────┘                   │
└──────────────────────────────────────────────────┘
       ↓
SYNTHESIZER 汇总结果
       ↓
返回 MAIN（PASS/REWORK/BLOCKED）
```

---

## 处理 SYNTHESIZER 结果

### SYNTHESIZER PASS

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "SYNTHESIZER PASS，M1-T1 验证通过，开始下一任务 M1-T2",
  "history_append": "## Iteration {N}:\nnext_agent: IMPLEMENTER\nreason: M1-T1 VERIFIED，开始 M1-T2\ndev_plan: M1-T1 VERIFIED, M1-T2 DOING",
  "task_body": "## 任务目标\n...",
  "dev_plan_next": "# Dev Plan\n\n## M1\n\n### M1-T1\n- status: VERIFIED\n- evidence: SYNTHESIZER PASS Iteration {N-1}\n\n### M1-T2\n- status: DOING\n..."
}
```

### SYNTHESIZER REWORK

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "SYNTHESIZER REWORK: ANTI_CHEAT_DETECTOR 发现硬编码",
  "history_append": "## Iteration {N}:\nnext_agent: IMPLEMENTER\nreason: 修复 ANTI_CHEAT 问题",
  "task_body": "## 任务目标\n修复 SYNTHESIZER 发现的问题\n\n## 问题清单\n{从 SYNTHESIZER 报告提取}\n\n## 验收标准\n...",
  "dev_plan_next": null
}
```

### SYNTHESIZER BLOCKED

**核心原则**：没有任何 BLOCKED 可以被"忽略"，必须解决后才能继续。

当 SYNTHESIZER 报告 BLOCKED 时，MAIN 必须：

1. **检查 SYNTHESIZER 报告中的 BLOCKED 分类**
2. **根据分类采取对应处理**：

| BLOCKED 分类 | 处理方式 |
|-------------|---------|
| `[代码问题]` | **必须**派发 IMPLEMENTER 修复，禁止忽略 |
| `[环境问题]` | 升级 USER |
| `[信息缺失]` | 补充信息后重试 VALIDATE |
| `[基础设施]` | 重试 VALIDATE，连续 2 次失败则升级 USER |

**禁止行为**：
- ❌ 禁止不分析 BLOCKED 分类就归类为"验证器问题"
- ❌ 禁止在有 `[代码问题]` 分类时选择 FINISH
- ❌ 禁止忽略 BLOCKED 直接标记任务为 VERIFIED

**示例**：

```json
{
  "next_agent": "IMPLEMENTER",
  "reason": "SYNTHESIZER BLOCKED: EDGE_CASE_TESTER 发现边界问题（roots 为 null/undefined 时崩溃）",
  "history_append": "## Iteration {N}:\nnext_agent: IMPLEMENTER\nreason: 修复 EDGE_CASE_TESTER 发现的边界问题",
  "task_body": "## 任务目标\n修复边界情况处理\n\n## 问题清单\n1. roots 缺失时崩溃: Cannot read properties of undefined\n2. roots=null 时崩溃: Cannot read properties of null\n\n## 验收标准\n- 边界情况正确处理，无崩溃",
  "dev_plan_next": null
}
```

---

## 注意事项

1. **VALIDATE 不需要 task**：验证器工单由编排器根据 IMPLEMENTER 报告自动生成
2. **不要跳过 VALIDATE**：即使 IMPLEMENTER 自测通过，也必须验证
3. **信任 SYNTHESIZER**：SYNTHESIZER 的决策基于多个验证器的综合判断
4. **REWORK 时引用具体问题**：从 SYNTHESIZER 报告中提取问题清单
