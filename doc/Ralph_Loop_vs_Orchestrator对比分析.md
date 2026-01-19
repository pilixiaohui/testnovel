# Ralph Loop vs Orchestrator 工作流对比分析

## 一、Ralph Loop 工作原理

### 1.1 核心机制

Ralph Loop 是一个**极简的自引用反馈循环**系统，基于 Claude Code 的 Stop Hook 机制实现：

```
用户启动 → Claude 工作 → 尝试退出 → Stop Hook 拦截 → 喂回相同 Prompt → 循环
```

**关键特征**：
- **单一 AI 实例**：只有一个 Claude 在循环中工作
- **不变的 Prompt**：每次迭代都是完全相同的任务描述
- **文件系统作为记忆**：通过读取自己修改的文件和 git 历史来"记忆"
- **Stop Hook 驱动**：利用 Claude Code 的 Stop Hook API 拦截退出并重新注入 Prompt

### 1.2 实现细节

**状态管理**：
```yaml
# .claude/ralph-loop.local.md
---
active: true
iteration: 5
max_iterations: 20
completion_promise: "COMPLETE"
started_at: "2026-01-19T15:30:00Z"
---

Build a REST API for todos. Requirements: CRUD operations, input validation, tests.
Output <promise>COMPLETE</promise> when done.
```

**Stop Hook 逻辑**（`hooks/stop-hook.sh`）：
1. 检查 `.claude/ralph-loop.local.md` 是否存在
2. 读取当前迭代数、最大迭代数、完成承诺
3. 从 transcript 提取 Claude 最后输出
4. 检查是否包含 `<promise>COMPLETE</promise>`
5. 如果未完成：
   - 迭代数 +1
   - 输出 JSON：`{"decision": "block", "reason": "<原始 Prompt>", "systemMessage": "🔄 Ralph iteration 6"}`
   - 阻止退出，将原始 Prompt 作为新的用户消息注入

**退出条件**：
- 检测到完成承诺：`<promise>COMPLETE</promise>`
- 达到最大迭代数：`iteration >= max_iterations`
- 手动取消：`/cancel-ralph` 删除状态文件

### 1.3 哲学与适用场景

**设计哲学**：
- **迭代 > 完美**：不追求一次完美，让循环自然优化
- **失败即数据**：测试失败是可预测的信息，用于调优
- **操作员技能决定成败**：写好 Prompt 比模型能力更重要
- **持久性获胜**：持续尝试直到成功

**适用场景**：
- ✅ 明确的成功标准（测试通过、覆盖率达标）
- ✅ 需要迭代优化的任务（修 bug、通过测试）
- ✅ 绿地项目（可以放手让 AI 自主工作）
- ✅ 有自动验证机制（测试、linter）

**不适用场景**：
- ❌ 需要人类判断或设计决策
- ❌ 一次性操作
- ❌ 不明确的成功标准
- ❌ 生产环境调试

---

## 二、Orchestrator 工作原理

### 2.1 核心机制

Orchestrator 是一个**黑板模式（Blackboard Pattern）多代理系统**，基于外部 Python 编排器实现：

```
用户启动 → MAIN 决策 → 派发子代理 → 子代理执行 → 报告写入黑板 → MAIN 读取 → 下一轮决策
```

**关键特征**：
- **多个专业化 AI 代理**：MAIN（决策）、TEST（测试）、DEV（开发）、REVIEW（审阅）、FINISH_REVIEW（最终审阅）
- **动态任务分配**：MAIN 根据当前状态决定下一步派发哪个代理
- **黑板共享记忆**：所有代理通过文件系统共享状态（dev_plan.md、project_history.md、reports/）
- **外部编排器驱动**：Python workflow.py 控制循环、注入上下文、落盘报告

### 2.2 实现细节

**代理角色**：
- **MAIN**：最高指挥权，读取黑板状态，输出 JSON 决策（next_agent、task、dev_plan_next、history_append）
- **TEST**：编写/补齐测试代码，运行测试，报告结果（PASS/FAIL/BLOCKED）
- **DEV**：实现功能代码，修复 bug，报告变更
- **REVIEW**：取证验证，更新 dev_plan 状态（DONE → VERIFIED）
- **FINISH_REVIEW**：最终审阅，确认是否真正完成

**黑板文件**：
```
orchestrator/memory/
  ├── dev_plan.md              # 全局开发计划（任务状态：TODO/DOING/BLOCKED/DONE/VERIFIED）
  ├── project_history.md       # 长期记忆（追加写入，最近 N 轮）
  ├── global_context.md        # 全局目标与约束
  └── verification_policy.json # 测试要求与覆盖率门禁

orchestrator/workspace/
  ├── main/dev_plan_next.md    # MAIN 提交的 dev_plan 草案
  ├── test/current_task.md     # TEST 工单
  ├── dev/current_task.md      # DEV 工单
  └── review/current_task.md   # REVIEW 工单

orchestrator/reports/
  ├── report_test.md           # TEST 输出（结论：PASS/FAIL/BLOCKED，阻塞：...）
  ├── report_dev.md            # DEV 输出
  ├── report_review.md         # REVIEW 输出
  ├── report_finish_review.md  # FINISH_REVIEW 输出
  └── report_stage_changes.json # 上一轮代码变更摘要（用于 TDD 规则）
```

**编排器循环**（`workflow.py`）：
```python
while True:
    # 1. 准备 MAIN 上下文（注入黑板文件内容）
    context = build_main_context(
        iteration=iteration,
        global_context=read("orchestrator/memory/global_context.md"),
        project_history=read_last_n_iterations("orchestrator/memory/project_history.md"),
        dev_plan=read("orchestrator/memory/dev_plan.md"),
        report_test=read("orchestrator/reports/report_test.md"),
        report_dev=read("orchestrator/reports/report_dev.md"),
        report_review=read("orchestrator/reports/report_review.md"),
        report_stage_changes=read("orchestrator/reports/report_stage_changes.json"),
        verification_policy=read("orchestrator/memory/verification_policy.json"),
    )

    # 2. 调用 MAIN 代理
    decision = call_claude(prompt=main_prompt, context=context)
    # decision = {"next_agent": "TEST", "reason": "...", "task": "...", "history_append": "...", "dev_plan_next": null}

    # 3. TDD 规则验证（可选）
    if config.enforce_tdd:
        warnings = _validate_tdd_main_decision(
            next_agent=decision["next_agent"],
            must_test_after_dev=stage_changes["agent"] == "DEV" and stage_changes["code_changed"],
            test_required_task_ids=find_open_test_required_task_ids(dev_plan),
            last_test_verdict=extract_verdict(report_test),
            min_coverage=verification_policy["test_requirements"]["min_coverage"],
            coverage_ok=extract_coverage(report_test) >= min_coverage,
        )
        if warnings:
            print(warnings)  # 警告但不阻止

    # 4. 落盘 history_append
    append("orchestrator/memory/project_history.md", decision["history_append"])

    # 5. 落盘 dev_plan_next（如果有变更）
    if decision["dev_plan_next"]:
        write("orchestrator/workspace/main/dev_plan_next.md", decision["dev_plan_next"])
        git_commit("orchestrator/memory/dev_plan.md", decision["dev_plan_next"])

    # 6. 派发子代理
    if decision["next_agent"] == "TEST":
        write("orchestrator/workspace/test/current_task.md", decision["task"])
        before_snapshot = capture_dirty_file_digests(exclude_prefixes=("orchestrator/memory/",))
        report = call_claude(prompt=test_prompt, task=decision["task"])
        after_snapshot = capture_dirty_file_digests(exclude_prefixes=("orchestrator/memory/",))
        changed_files = diff_dirty_file_digests(before_snapshot, after_snapshot)
        write("orchestrator/reports/report_test.md", report)
        write("orchestrator/reports/report_stage_changes.json", {
            "iteration": iteration,
            "agent": "TEST",
            "changed_files": changed_files,
            "code_changed": any(is_code_file(f) for f in changed_files),
        })
    elif decision["next_agent"] == "DEV":
        # 类似 TEST
    elif decision["next_agent"] == "REVIEW":
        # 类似 TEST
    elif decision["next_agent"] == "FINISH":
        # 触发 FINISH_REVIEW，检查是否真正完成
        finish_review_report = call_claude(prompt=finish_review_prompt)
        write("orchestrator/reports/report_finish_review.md", finish_review_report)
        if "结论：PASS" in finish_review_report:
            break  # 真正完成
        else:
            # 进入 FINISH_CHECK 模式，让 MAIN 决定是否采纳 FAIL/阻塞
            decision = call_claude(prompt=main_prompt + finish_check_context)
            # MAIN 必须输出 JSON：采纳则派发子代理，忽略则 FINISH
    elif decision["next_agent"] == "USER":
        # 暂停，向用户展示抉择，收集选择
        user_choice = prompt_user(decision["question"], decision["options"])
        append("orchestrator/memory/project_history.md", f"User choice: {user_choice}")

    iteration += 1
```

**TDD 强制规则**（`workflow.py:_validate_tdd_main_decision`）：
- **【建议】代码变更后优先测试**：上一轮 DEV 有代码变更 → 建议派发 TEST（可跳过，需说明）
- **【条件】test_required 任务优先测试**：dev_plan 存在 `test_required: true` 的未完成任务 → 必须先 TEST PASS + 覆盖率达标（或已达标则可跳过）
- **【建议】REVIEW 前先测试**：verification_policy 启用 `must_pass_before_review` → 建议先 TEST PASS（可跳过，需说明）

**退出条件**：
- dev_plan 所有任务状态为 VERIFIED
- FINISH_REVIEW 报告 PASS
- MAIN 输出 `next_agent: FINISH` 且通过 FINISH_CHECK 复核

### 2.3 哲学与适用场景

**设计哲学**：
- **专业化分工**：每个代理只做自己擅长的事（测试/开发/审阅）
- **显式状态管理**：dev_plan 明确记录任务状态与证据
- **TDD 优先**：强制测试先行，覆盖率门禁
- **证据驱动决策**：MAIN 基于报告证据做决策，不凭空猜测

**适用场景**：
- ✅ 复杂多阶段项目（需要明确的任务分解与状态跟踪）
- ✅ 严格 TDD 流程（测试先行、覆盖率要求）
- ✅ 需要审阅验证的任务（DONE → VERIFIED）
- ✅ 需要人类参与决策的场景（USER 抉择）

**不适用场景**：
- ❌ 简单单步任务（编排开销过大）
- ❌ 快速原型验证（流程过于严格）
- ❌ 不需要测试的任务（如纯文档编写）

---

## 三、核心差异对比

| 维度 | Ralph Loop | Orchestrator |
|------|-----------|--------------|
| **架构模式** | 单代理自引用循环 | 多代理黑板模式 |
| **循环驱动** | Stop Hook（Claude Code 内置） | 外部 Python 编排器 |
| **记忆机制** | 文件系统 + git 历史（隐式） | 黑板文件（显式状态管理） |
| **任务描述** | 不变的 Prompt（每次完全相同） | 动态工单（MAIN 每轮生成） |
| **角色分工** | 无（单一 AI 做所有事） | 有（TEST/DEV/REVIEW 专业化） |
| **决策逻辑** | 无（AI 自主决定下一步） | 有（MAIN 显式决策 next_agent） |
| **TDD 强制** | 无（依赖 Prompt 引导） | 有（workflow.py 强制规则） |
| **状态跟踪** | 无（AI 自行判断是否完成） | 有（dev_plan 明确任务状态） |
| **完成信号** | `<promise>COMPLETE</promise>` | dev_plan 全 VERIFIED + FINISH_REVIEW PASS |
| **人类参与** | 无（只能事后查看） | 有（USER 抉择暂停） |
| **复杂度** | 极简（~200 行 Bash） | 复杂（~1500 行 Python + 多文件） |
| **灵活性** | 高（AI 完全自主） | 中（MAIN 有决策权但受规则约束） |
| **可控性** | 低（只能设置 max_iterations） | 高（TDD 规则、覆盖率门禁、状态验证） |
| **透明度** | 低（只能看文件变更） | 高（每轮决策、报告、状态都记录） |
| **适用规模** | 小型任务（1-50 次迭代） | 中大型项目（10-100+ 次迭代） |

---

## 四、工作流对比示例

### 4.1 Ralph Loop 工作流

**任务**：实现一个 TODO API，要求 CRUD 操作、输入验证、测试覆盖率 > 80%

**Prompt**：
```
Build a REST API for todos. Requirements: CRUD operations, input validation, tests (coverage > 80%).
Output <promise>COMPLETE</promise> when done.
```

**执行流程**：
```
Iteration 1: Claude 创建 app.py（基础 CRUD）、test_app.py（简单测试）
             → 尝试退出 → Stop Hook 拦截 → 喂回相同 Prompt

Iteration 2: Claude 读取 app.py、test_app.py，发现测试不完整
             → 补充测试用例、修复 bug
             → 尝试退出 → Stop Hook 拦截

Iteration 3: Claude 运行 pytest --cov，发现覆盖率 65%
             → 补充边界测试、异常测试
             → 尝试退出 → Stop Hook 拦截

Iteration 4: Claude 运行 pytest --cov，覆盖率 82%，所有测试通过
             → 输出 <promise>COMPLETE</promise>
             → Stop Hook 检测到完成承诺 → 退出循环
```

**特点**：
- AI 完全自主决定每次迭代做什么
- 没有显式的任务分解（AI 自行判断优先级）
- 依赖 AI 自己运行测试并解读结果
- 完成标准由 AI 自行判断（可能不够严格）

### 4.2 Orchestrator 工作流

**任务**：实现一个 TODO API，要求 CRUD 操作、输入验证、测试覆盖率 > 80%

**dev_plan.md**（MAIN 生成）：
```markdown
## Milestone M1: TODO API

### M1-T1: 实现 CRUD 端点
- acceptance: 所有端点可调用，返回正确状态码
- test_required: true
- status: TODO

### M1-T2: 输入验证
- acceptance: 非法输入返回 400，合法输入正常处理
- test_required: true
- status: TODO

### M1-T3: 测试覆盖率达标
- acceptance: pytest --cov 显示覆盖率 >= 80%
- test_required: true
- status: TODO
```

**执行流程**：
```
Iteration 1 (MAIN):
  - 读取 dev_plan（M1-T1 TODO, test_required=true）
  - 决策：next_agent=TEST（测试先行）
  - 工单：为 M1-T1 编写测试（预期失败）

Iteration 2 (TEST):
  - 创建 test_app.py（测试 CRUD 端点）
  - 运行 pytest → 全部失败（app.py 不存在）
  - 报告：结论：FAIL，阻塞：app.py 未实现

Iteration 3 (MAIN):
  - 读取 report_test.md（FAIL，阻塞：app.py 未实现）
  - 决策：next_agent=DEV（实现代码让测试通过）
  - 工单：实现 app.py CRUD 端点

Iteration 4 (DEV):
  - 创建 app.py（实现 CRUD）
  - 运行 pytest → 部分通过
  - 报告：实现了 GET/POST，PUT/DELETE 待完善

Iteration 5 (MAIN):
  - 读取 report_dev.md（部分实现）
  - 读取 report_stage_changes.json（DEV 有代码变更）
  - TDD 规则触发：【建议】代码变更后优先测试
  - 决策：next_agent=TEST（验证实现）

Iteration 6 (TEST):
  - 运行 pytest → 部分失败（PUT/DELETE 未实现）
  - 报告：结论：FAIL，阻塞：PUT/DELETE 端点缺失

Iteration 7 (MAIN):
  - 决策：next_agent=DEV（补齐实现）

Iteration 8 (DEV):
  - 补齐 PUT/DELETE
  - 运行 pytest → 全部通过
  - 报告：所有端点实现完成

Iteration 9 (MAIN):
  - TDD 规则触发：【建议】代码变更后优先测试
  - 决策：next_agent=TEST（验证 + 覆盖率）

Iteration 10 (TEST):
  - 运行 pytest --cov → 覆盖率 65%
  - 报告：结论：FAIL，阻塞：覆盖率不达标（min_coverage=80%）

Iteration 11 (MAIN):
  - 决策：next_agent=TEST（补齐测试）

Iteration 12 (TEST):
  - 补充边界测试、异常测试
  - 运行 pytest --cov → 覆盖率 82%，全部通过
  - 报告：结论：PASS，阻塞：无，coverage: 82%

Iteration 13 (MAIN):
  - 读取 report_test.md（PASS，覆盖率 82%）
  - 决策：next_agent=REVIEW（取证验证）

Iteration 14 (REVIEW):
  - 检查 app.py、test_app.py
  - 验证测试结果与覆盖率
  - 更新 dev_plan：M1-T1 DONE → VERIFIED

Iteration 15 (MAIN):
  - 读取 dev_plan（M1-T1 VERIFIED，M1-T2/M1-T3 TODO）
  - 决策：next_agent=TEST（继续 M1-T2）
  - ... 重复类似流程 ...

Iteration N (MAIN):
  - 读取 dev_plan（所有任务 VERIFIED）
  - 决策：next_agent=FINISH

Iteration N+1 (FINISH_REVIEW):
  - 全面审阅所有任务
  - 运行最终测试
  - 报告：结论：PASS，所有验收标准满足

Iteration N+2 (MAIN FINISH_CHECK):
  - 读取 report_finish_review.md（PASS）
  - 决策：next_agent=FINISH（真正完成）
  - 退出循环
```

**特点**：
- MAIN 显式决策每一步（TEST/DEV/REVIEW）
- 任务分解明确（dev_plan 记录状态）
- TDD 规则强制执行（代码变更后必须测试）
- 覆盖率门禁硬约束（< 80% 无法通过）
- 多轮验证（REVIEW 取证 + FINISH_REVIEW 最终审阅）

---

## 五、优劣势分析

### 5.1 Ralph Loop 优势

1. **极简实现**：~200 行 Bash，无外部依赖，易于理解和修改
2. **高度灵活**：AI 完全自主，可以根据实际情况调整策略
3. **低认知负担**：用户只需写一个 Prompt，无需设计任务分解
4. **快速启动**：无需配置，直接 `/ralph-loop "任务描述"` 即可
5. **适合探索**：AI 可以尝试不同方案，自然收敛到最优解

### 5.2 Ralph Loop 劣势

1. **缺乏可控性**：无法强制 TDD、覆盖率等规则
2. **透明度低**：只能事后查看文件变更，无法实时了解决策逻辑
3. **完成标准模糊**：依赖 AI 自行判断是否完成（可能不够严格）
4. **无状态跟踪**：没有显式的任务列表与状态管理
5. **单点失败**：AI 卡住时无法切换策略（只能重复相同 Prompt）
6. **无人类参与**：无法在关键决策点暂停询问用户

### 5.3 Orchestrator 优势

1. **强可控性**：TDD 规则、覆盖率门禁、状态验证都可强制执行
2. **高透明度**：每轮决策、报告、状态变更都有记录
3. **专业化分工**：TEST/DEV/REVIEW 各司其职，质量更高
4. **显式状态管理**：dev_plan 明确任务列表与完成状态
5. **证据驱动**：MAIN 基于报告证据做决策，避免凭空猜测
6. **人类参与**：USER 抉择可在关键点暂停询问用户
7. **可审计**：project_history 记录完整决策链

### 5.4 Orchestrator 劣势

1. **复杂度高**：~1500 行 Python + 多文件配置，学习曲线陡峭
2. **灵活性低**：MAIN 受 TDD 规则约束，可能过于死板
3. **认知负担高**：用户需要理解黑板模式、代理角色、决策规则
4. **启动成本高**：需要配置 verification_policy、编写 global_context
5. **编排开销**：每轮迭代需要注入大量上下文（~5-10KB）
6. **过度工程**：简单任务也需要走完整流程（TEST → DEV → REVIEW）

---

## 六、适用场景建议

### 6.1 使用 Ralph Loop 的场景

- **快速原型验证**：需要快速尝试一个想法，不在乎过程
- **简单单步任务**：如"修复这个 bug"、"优化这个函数"
- **探索性编程**：不确定最佳方案，让 AI 自由探索
- **学习与实验**：理解 AI 自主工作的能力边界
- **绿地项目**：从零开始，可以放手让 AI 自主设计

### 6.2 使用 Orchestrator 的场景

- **严格 TDD 项目**：必须测试先行、覆盖率达标
- **复杂多阶段任务**：需要明确的任务分解与状态跟踪
- **团队协作项目**：需要审计日志、证据链、可复现流程
- **生产级代码**：需要多轮验证、质量保证
- **需要人类决策**：关键设计决策需要用户参与

### 6.3 混合使用建议

**阶段 1：Ralph Loop 快速原型**
- 用 Ralph Loop 快速验证核心功能可行性
- 生成初始代码框架与测试

**阶段 2：Orchestrator 精细化**
- 将 Ralph 生成的代码导入 Orchestrator
- 用 Orchestrator 补齐测试、提升覆盖率、多轮审阅
- 确保生产级质量

---

## 七、改进建议

### 7.1 Ralph Loop 可借鉴 Orchestrator 的点

1. **显式状态文件**：在 `.claude/ralph-loop.local.md` 中记录任务列表与状态
2. **完成标准检查**：Stop Hook 不仅检查 `<promise>`，还检查测试结果、覆盖率
3. **阶段性报告**：每次迭代生成结构化报告（类似 report_test.md）
4. **TDD 提示**：在 Prompt 中注入"上次迭代有代码变更，本次应先运行测试"

### 7.2 Orchestrator 可借鉴 Ralph Loop 的点

1. **简化小任务流程**：检测到简单任务时，跳过 REVIEW 直接 FINISH
2. **减少编排开销**：缓存不变的上下文（global_context、verification_policy）
3. **增强 MAIN 自主性**：将更多决策权交给 MAIN，减少硬性规则
4. **引入自引用机制**：允许 MAIN 在某些场景下"自我循环"（类似 Ralph）

---

## 八、总结

**Ralph Loop** 和 **Orchestrator** 代表了两种极端的 AI 工作流设计哲学：

- **Ralph Loop**：极简、自主、灵活，适合快速迭代与探索
- **Orchestrator**：复杂、可控、严格，适合生产级项目与团队协作

两者没有绝对的优劣，关键在于**根据任务特性选择合适的工具**：

- 简单任务 → Ralph Loop（快速启动，低开销）
- 复杂项目 → Orchestrator（质量保证，可审计）
- 混合使用 → Ralph 原型 + Orchestrator 精细化（兼顾速度与质量）

**核心差异总结**：
- Ralph Loop = **单代理 + 不变 Prompt + Stop Hook 自引用**
- Orchestrator = **多代理 + 动态工单 + 外部编排器 + 黑板模式**

两者都是优秀的 AI 工作流实现，值得根据实际需求灵活选择与组合。
