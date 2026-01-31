# 编排器工作流核心思想

## 一、设计哲学

### 1.1 核心原则

**协作优于执行**
- 多个专业代理协作完成复杂任务，而非单个代理包揽一切
- 每个代理专注于自己的职责领域，通过报告传递信息
- 主控负责调度，子代理负责执行，决策基于黑板共享信息

**简单优于复杂**
- 格式解析保持最小必要性，避免过度依赖特定格式
- 关键字段缺失即失败，不做格式容忍
- 解析失败直接中断并上报

**配置优于硬编码**
- 领域逻辑（TDD/文学创作/推理分析）通过配置和提示词定义
- 工作流代码保持通用性，不绑定特定场景
- 切换场景只需修改配置和提示词，代码改动最小化

**快速失败优于隐性容错**
- 关键路径失败立即中断并上报
- 不使用默认值掩盖失败
- 不提供兜底/降级方案

---

## 二、架构模型

### 2.1 黑板模式（Blackboard Pattern）

```
┌─────────────────────────────────────────────────────────┐
│                    共享黑板（Shared Memory）              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ dev_plan.md  │  │ history.md   │  │ report_*.md  │  │
│  │ (任务计划)    │  │ (历史记录)    │  │ (代理报告)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
         ↑ 读取                    ↑ 读取                ↑ 写入
         │                        │                      │
    ┌────┴────┐            ┌──────┴──────┐      ┌───────┴────────┐
    │  MAIN   │            │   执行代理   │      │   执行代理      │
    │  代理   │───派发───→ │ (TEST/DEV)  │      │ (REVIEW/etc)   │
    └─────────┘            └─────────────┘      └────────────────┘
         ↑
         │ 调度
    ┌────┴────┐
    │编排器核心│
    └─────────┘
```

**关键特性**：
- 所有代理通过黑板共享信息，无直接通信
- 代理只负责读取黑板、执行任务、写入报告
- MAIN 代理读取所有信息后做出下一步判断
- 编排器负责调度和状态管理

### 2.2 主控与执行分离

**当前模式（实用）**：
```
编排器 → 调用 MAIN 代理 → MAIN 读取黑板 → 输出结构化决策 → 编排器派发子代理
                              ↓ 理解语义
                         关键字段严格校验 ✅
```

**关键设计**：
- MAIN 代理负责决策，输出结构化 JSON
- 编排器负责解析 JSON 并派发子代理
- 子代理写报告（自由格式），MAIN 读取并理解
- 格式解析保持最小必要性，失败即终止

---

## 三、关键机制

### 3.1 最小格式解析

**问题**：过度依赖格式解析导致系统脆弱，模型稍有偏差就崩溃

**方案**：
- 报告文件保持相对自由格式，只解析关键字段
- 关键字段：`iteration:`、`结论：`、`阻塞：`（必需）
- 其他内容完全自由，MAIN 代理自行理解
- 解析失败直接抛错并中断流程

**示例**：
```python
# 必需字段解析（简单正则）
iteration = extract_iteration(report)  # 必需
verdict = extract_verdict(report)      # 可选字段，解析失败直接报错
blockers = extract_blockers(report)    # 可选字段，解析失败直接报错

# 其他内容由 MAIN 代理理解
# 不强制要求特定格式
```

**快速失败策略**：
```python
blockers = extract_blockers(report)  # 失败直接抛错
if iteration is None:
    raise RuntimeError("Report missing iteration (critical field)")
```

### 3.2 MAIN 代理决策

**职责**：
- 读取所有历史报告和计划文档
- 根据提示词中的规则，决定下一步派发哪个代理
- 输出结构化决策 JSON

**输入**：
- `memory/dev_plan.md`（或其他计划文档）
- `memory/project_history.md`
- `reports/report_*.md`（最近 N 轮报告）
- `memory/verification_policy.json`（验证策略）

**输出**：
```json
{
  "next_agent": "TEST",
  "reason": "M1-T1 需要测试覆盖",
  "dev_plan": "update M1-T1 status to IN_PROGRESS",
  "finish_review_override": null
}
```

**优势**：
- 编排器不包含领域逻辑，只负责调度
- TDD 规则全部在 `prompts/subagent_prompt_main.md` 中定义
- 切换场景只需替换 prompt，代码改动最小

### 3.3 领域配置化

**当前实现**：
- 验证策略在 `memory/verification_policy.json` 中定义
- 报告规则、TDD 规则在 MAIN 提示词中定义
- 子代理行为在各自提示词中定义

**TDD 场景配置示例**：
```json
{
  "report_rules": {
    "apply_to": ["TEST", "DEV", "REVIEW"],
    "require_verdict": true,
    "verdict_prefix": "结论：",
    "verdict_allowed": ["PASS", "FAIL", "BLOCKED"],
    "blocker_prefix": "阻塞：",
    "blocker_clear_value": "无"
  },
  "tdd_rules": {
    "test_first": true,
    "test_required_gate": true,
    "min_coverage": 80
  }
}
```

**扩展到其他场景**：
- 文学创作：修改 `verdict_allowed` 为 `["APPROVED", "NEEDS_REVISION", "BLOCKED"]`
- 推理分析：修改为 `["VALID", "INVALID", "INSUFFICIENT_EVIDENCE"]`
- 提示词中的规则相应调整

### 3.4 快速失败机制

**策略**：
```python
try:
    decision = json.loads(main_output)
except json.JSONDecodeError as exc:
    raise RuntimeError("MAIN 输出非 JSON") from exc
```

**关键原则**：
- 关键字段解析失败立即中断
- 不对任何字段做降级或默认值补全
- 失败即上报，问题可追踪

---

## 四、通用性设计

### 4.1 领域无关的工作流

**核心循环**（适用于所有场景）：
```python
while iteration <= max_iterations:
    # 1. 调用 MAIN 代理决策
    main_output = call_main_agent(iteration)
    decision = parse_main_output(main_output)

    # 2. 执行决策
    if decision["next_agent"] == "FINISH":
        break
    elif decision["next_agent"] == "USER":
        wait_for_user_input()
    else:
        call_subagent(decision["next_agent"], iteration)

    # 3. 更新黑板
    update_project_history(iteration, decision)
    iteration += 1
```

**领域特定逻辑**全部在配置和提示词中：
- `memory/verification_policy.json`：定义验证规则
- `memory/prompts/subagent_prompt_main.md`：MAIN 代理的决策规则
- `memory/prompts/subagent_prompt_*.md`：各执行代理的行为规范

### 4.2 场景切换示例

**从 TDD 开发切换到小说创作**：

1. **修改验证策略**：
```json
// memory/verification_policy.json
{
  "report_rules": {
    "apply_to": ["OUTLINE", "DRAFT", "CRITIQUE"],
    "verdict_allowed": ["APPROVED", "NEEDS_REVISION", "BLOCKED"]
  }
}
```

2. **替换 MAIN 提示词**：
```bash
cp memory/prompts/subagent_prompt_main_novel.md memory/prompts/subagent_prompt_main.md
```

3. **替换子代理提示词**：
```bash
cp memory/prompts/subagent_prompt_outline.md memory/prompts/subagent_prompt_outline.md
cp memory/prompts/subagent_prompt_draft.md memory/prompts/subagent_prompt_draft.md
cp memory/prompts/subagent_prompt_critique.md memory/prompts/subagent_prompt_critique.md
```

4. **代码零改动，直接运行**：
```bash
python orchestrator.py
```

---

## 五、与理想架构对比

| 维度 | 当前架构 | 理想架构（未来） |
|------|---------|----------------|
| **格式依赖** | 最小必要解析（iteration/verdict/blockers） | 零格式要求，LLM 提取语义 |
| **领域绑定** | 部分 TDD 逻辑在代码中 | 完全配置化，代码领域无关 |
| **失败处理** | 任一字段解析失败即中断 | 失败显式化，不做降级 |
| **可扩展性** | 新场景需修改少量代码 | 只需改 prompt 和配置 |
| **协作模式** | MAIN 决策 + 子代理执行 | 决策代理 + 执行代理 |
| **代码复杂度** | workflow.py ~2000 行 | workflow.py < 500 行 |
| **决策逻辑** | 部分硬编码在 Python 中 | 自然语言规则在 prompt 中 |
| **报告格式** | 最小格式要求 | 完全自由格式 |

**当前架构优势**：
- 实用性强，已验证可行
- 格式解析简单可靠
- 性能开销小（无需额外 LLM 调用）

**理想架构优势**：
- 失败显式化更强，问题定位更清晰
- 通用性更好，零代码改动切换场景
- 代码更简洁，易于维护

**演进路径**：
1. 当前架构作为基线，保持稳定
2. 逐步减少格式依赖，强化失败显式化
3. 将更多领域逻辑迁移到配置和提示词
4. 最终演进到理想架构（可选）

---

## 六、核心优势

### 6.1 实用性

- **已验证可行**：当前架构已在实际项目中运行
- **格式解析简单**：只解析关键字段，不依赖复杂正则
- **性能开销小**：无需额外 LLM 调用提取信息

### 6.2 失败可见性

- **失败显式**：解析失败立即抛错，不使用默认值
- **格式要求清晰**：关键字段缺失即失败
- **无降级策略**：问题必须被真实暴露

### 6.3 通用性

- **领域可配置**：验证规则和决策规则在配置和提示词中
- **代码简洁**：核心循环逻辑清晰，易于理解
- **易于扩展**：新增代理或规则只需修改提示词

### 6.4 协作性

- **专业分工**：每个代理专注于自己的领域
- **信息共享**：通过黑板模式共享信息，无需直接通信
- **决策透明**：MAIN 代理输出明确的理由和上下文

---

## 七、适用场景

### 7.1 软件开发（TDD）

- **代理**：TEST、DEV、REVIEW
- **规则**：test_required 任务必须先测试，测试失败必须修复
- **完成标准**：所有任务 VERIFIED，测试覆盖率达标

### 7.2 文学创作

- **代理**：OUTLINE、DRAFT、POLISH、CRITIQUE
- **规则**：大纲未完成不能写作，CRITIQUE 发现问题必须修改
- **完成标准**：所有章节 POLISHED，无重大问题

### 7.3 推理分析

- **代理**：COLLECT、ANALYZE、VERIFY、CONCLUDE
- **规则**：证据不足不能下结论，矛盾必须重新分析
- **完成标准**：结论有充分证据支撑，无逻辑矛盾

### 7.4 其他场景

- 数据分析流程
- 内容审核流程
- 知识图谱构建
- 多轮对话系统

---

## 八、总结

### 核心思想三要素

1. **黑板模式**：代理通过共享内存协作，无直接通信
2. **主控分离**：MAIN 代理负责决策，子代理负责执行
3. **最小解析**：只解析关键字段，其他内容由 MAIN 理解

### 设计目标

- **实用性**：已验证可行，性能开销小
- **鲁棒性**：失败显式可追踪，避免问题被掩盖
- **通用性**：支持多种协作场景，易于扩展
- **简洁性**：核心逻辑清晰，易于理解和维护

### 演进方向

1. **短期**：优化当前架构，减少格式依赖
2. **中期**：强化失败显式化，提升定位效率
3. **长期**：演进到零格式解析，完全配置化（可选）

---

**这是一个实用的多代理协作框架，通过黑板模式、主控分离和最小解析，实现了鲁棒、通用、简洁的工作流系统。**
