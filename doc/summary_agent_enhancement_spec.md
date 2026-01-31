# 总结代理增强规格说明

## 一、设计目标

扩展总结代理（SUMMARY）的职责，在每轮迭代摘要基础上，新增：

1. **代理行为合理性检查**：评估本轮代理行为是否符合用户需求，给出建议
2. **用户决策习惯整合**：从历史用户决策中提取偏好模式，供用户参考

**核心原则**：总结代理的所有输出都是**面向用户**的，不影响工作流决策。

## 二、现状分析

### 2.1 当前工作流结构

```
workflow_loop()
    │
    ├─→ MAIN 决策阶段
    │       │
    │       ├─→ next_agent: FINISH ──→ FINISH_REVIEW ──→ FINISH_CHECK ──→ 结束/继续
    │       ├─→ next_agent: USER ──→ 等待用户决策 ──→ continue（无 SUMMARY）
    │       ├─→ next_agent: PARALLEL_REVIEW ──→ 并发审阅 ──→ continue（无 SUMMARY）
    │       └─→ next_agent: TEST/DEV/REVIEW ──→ 子代理执行 ──→ SUMMARY ──→ 下一轮
    │
    └─→ 迭代结束
```

**关键发现**：
- SUMMARY 仅在 `TEST/DEV/REVIEW` 子代理执行后运行
- `USER` 决策后直接 `continue`，不经过 SUMMARY
- `PARALLEL_REVIEW` 后直接 `continue`，不经过 SUMMARY
- `FINISH` 流程不经过 SUMMARY

### 2.2 当前总结代理职责

- 每轮 MAIN + 子代理（TEST/DEV/REVIEW）结束后生成迭代摘要
- 输出 JSON 格式到 `report_iteration_summary.json`
- 追加到 `report_iteration_summary_history.jsonl`

### 2.3 当前输出内容

```json
{
  "iteration": 5,
  "main_decision": {"next_agent": "REVIEW", "reason": "..."},
  "subagent": {"agent": "REVIEW", "task_summary": "...", "report_summary": "..."},
  "steps": [...],
  "summary": "本轮一句话总结",
  "progress": {...},
  "verdict": "PASS/FAIL/BLOCKED",
  "key_findings": [...]
}
```

### 2.4 缺失内容

- 无行为合理性评估
- 无用户决策模式分析
- 无面向用户的改进建议

## 三、增强方案

### 3.1 新增输出文件与更新策略

基于工作流分析，优化更新频率：

| 文件 | 格式 | 用途 | 触发时机 | 更新方式 |
|------|------|------|----------|----------|
| `reports/user_insight_report.md` | Markdown | 面向用户的洞察报告 | SUMMARY 阶段（TEST/DEV/REVIEW 后） | 覆盖 |
| `reports/user_insight_history.jsonl` | JSONL | 洞察报告历史 | SUMMARY 阶段 | 追加 |
| `memory/user_decision_patterns.md` | Markdown | 用户决策习惯整合 | USER 决策后（workflow.py 中） | 追加 |

**更新频率优化说明**：

1. **user_insight_report.md**：每次 SUMMARY 运行时覆盖
   - 触发条件：`next_agent in {TEST, DEV, REVIEW}` 且子代理执行完成
   - 不触发：USER 决策、PARALLEL_REVIEW、FINISH 流程

2. **user_insight_history.jsonl**：每次 SUMMARY 运行时追加
   - 与 `report_iteration_summary_history.jsonl` 同步
   - 保留历史洞察供用户回溯

3. **user_decision_patterns.md**：USER 决策后立即更新
   - 触发条件：`decision["next_agent"] == "USER"` 且用户完成选择
   - 在 `_prompt_user_for_decision()` 返回后、`continue` 前执行
   - 不依赖 SUMMARY 代理（因为 USER 决策后不运行 SUMMARY）

### 3.2 工作流集成点详解

```python
# workflow.py 中的集成位置

# ========== 位置 1: USER 决策后（约 L2052-2059）==========
if decision["next_agent"] == "USER":
    user_decision = dict(decision)
    user_decision["doc_patches"] = main_output.get("doc_patches")
    user_choice = _prompt_user_for_decision(iteration=iteration, decision=user_decision, ui=ui)
    _clear_resume_state()

    # 【新增】USER 决策后立即更新决策模式文档
    _update_user_decision_patterns(
        iteration=iteration,
        decision=user_decision,
        user_choice=user_choice,
    )

    last_user_decision_iteration = iteration
    continue  # 注意：USER 决策后不运行 SUMMARY

# ========== 位置 2: SUMMARY 阶段后（约 L2188-2210）==========
try:
    _run_summary_stage(...)
    log_event(...)

    # 【新增】SUMMARY 成功后生成用户洞察报告
    _generate_user_insight_from_summary(
        iteration=iteration,
        summary_file=REPORT_ITERATION_SUMMARY_FILE,
    )

except Exception as exc:
    _append_log_line(f"orchestrator: SUMMARY error: {exc}\n")
```

### 3.3 用户洞察报告（user_insight_report.md）

**触发时机**：SUMMARY 阶段成功完成后（即 TEST/DEV/REVIEW 子代理执行后）

**不触发场景**：
- USER 决策后（直接 continue）
- PARALLEL_REVIEW 后（直接 continue）
- FINISH 流程（无 SUMMARY）

**文件结构**：

```markdown
# 用户洞察报告

> 生成时间: 2026-01-31T15:05:24
> 当前迭代: 8

## 本轮摘要

REVIEW 完成第三轮深入分析，发现图信息提取/提交闭环未接入任何 View。

## 行为合理性检查

### 任务对齐度: ✅ 良好 (90%)

- 用户目标: 分析E2E测试覆盖度
- 实际执行: REVIEW 生成覆盖度矩阵并追加到报告
- 评估: 执行符合用户分析需求

### 决策质量: ✅ 合规

- MAIN 决策: REVIEW
- TDD 流程: 符合（分析任务无需 TDD）
- 问题: 无

### 范围控制: ⚠️ 注意

- 修改文件: doc/e2e_test_evaluation_report.md
- 范围外修改: 无
- 注意: 报告文件持续增长，建议关注文件大小

### 效率评估: ✅ 正常

- 连续相同代理: 2 轮（REVIEW）
- 重复失败: 0 次
- 评估: 正常，用户主动要求继续分析

## 建议

1. 当前分析任务已较为全面（累计 74+ 功能点），可考虑进入修复阶段
2. 如需继续分析，建议明确具体功能点，避免范围无限扩大

## 进度概览

| 里程碑 | 状态 | 完成度 |
|--------|------|--------|
| M0: 引导与黑板契约 | VERIFIED | 100% |
| M1: 前端基础骨架 | DOING | 50% |

---
*此报告由总结代理自动生成，仅供参考*
```

### 3.4 用户决策习惯整合（user_decision_patterns.md）

**触发时机**：USER 决策完成后，在 `workflow.py` 中直接调用（不依赖 SUMMARY）

**原因**：USER 决策后直接 `continue`，不经过 SUMMARY 阶段，因此需要在 workflow.py 中单独处理

累积记录用户的决策模式，帮助用户了解自己的偏好。

**文件结构**：

```markdown
# 用户决策习惯整合

> 最后更新: 2026-01-31T15:05:24
> 累计决策次数: 4

## 决策偏好分析

### 分析深度偏好

**倾向**: 深入分析 > 快速修复

**证据**:
- Iteration 4: 选择 "需要更详细的覆盖度矩阵"（opt4）
- Iteration 6: 选择 "继续深入分析其他功能点"（opt2）
- Iteration 8: 选择 "继续分析其他功能点"（opt2）

**置信度**: 高（3/4 次选择深入分析）

### 输出位置偏好

**倾向**: 报告输出到 doc/ 目录

**证据**:
- Iteration 4 备注: "将让审阅代理直接一边分析一边记录详细报告到/home/zxh/ainovel_v3/doc中"

**置信度**: 中（1 次明确表达）

### 关注领域

从用户备注中提取的关注点：
- 错误处理与重试机制
- 提示词配置
- 模型 API 配置（baseurl、超时）
- 创作过程中的保存功能
- 图信息提取到世界观

## 决策历史

| 迭代 | 问题类型 | 选择 | 备注摘要 |
|------|----------|------|----------|
| 2 | 行动方向 | opt4 | 需要更详细分析 |
| 4 | 行动方向 | opt4 | 报告写入doc目录 |
| 6 | 行动方向 | opt2 | 继续分析配置功能 |
| 8 | 行动方向 | opt3 | 启动TDD修复流程 |

## 模式总结

1. **分析优先**: 用户倾向于在充分分析后再进入修复阶段
2. **文档导向**: 用户重视分析报告的输出和保存
3. **功能完整性**: 用户关注配置、错误处理等"非核心但重要"的功能

---
*此文档由总结代理自动整合，帮助您了解自己的决策模式*
```

## 四、实现方案

### 4.1 修改文件清单

| 文件 | 修改内容 |
|------|----------|
| `orchestrator/config.py` | 新增文件路径常量和功能开关 |
| `orchestrator/types.py` | 新增 `BehaviorCheck`、`UserInsight` 类型（可选） |
| `orchestrator/summary.py` | 新增 `_generate_user_insight_report()`、`_append_user_insight_history()` |
| `orchestrator/decision.py` | 新增 `_update_user_decision_patterns()` |
| `orchestrator/memory/prompts/subagent_prompt_summary.md` | 扩展输出要求 |
| `orchestrator/workflow.py` | 两处集成点（USER 决策后 + SUMMARY 后） |

### 4.2 新增配置（config.py）

```python
# 用户洞察报告
USER_INSIGHT_REPORT_FILE = REPORTS_DIR / "user_insight_report.md"
USER_INSIGHT_HISTORY_FILE = REPORTS_DIR / "user_insight_history.jsonl"
USER_DECISION_PATTERNS_FILE = MEMORY_DIR / "user_decision_patterns.md"

# 功能开关（可选）
ENABLE_BEHAVIOR_AUDIT = True  # 是否启用行为审计
ENABLE_DECISION_PATTERNS = True  # 是否启用决策模式整合
```

### 4.3 用户决策模式更新逻辑（decision.py）

```python
def _update_user_decision_patterns(
    *,
    iteration: int,
    decision: MainDecisionUser,
    user_choice: str,
    user_comment: str | None,
) -> None:
    """
    USER 决策后立即更新决策模式文档。

    此函数在 workflow.py 的 USER 分支中调用，
    因为 USER 决策后直接 continue，不经过 SUMMARY 阶段。
    """
    from datetime import datetime

    if not ENABLE_DECISION_PATTERNS:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")

    # 读取现有内容或创建新文件
    if USER_DECISION_PATTERNS_FILE.exists():
        existing = USER_DECISION_PATTERNS_FILE.read_text(encoding="utf-8")
    else:
        existing = _create_decision_patterns_header()

    # 提取决策信息
    decision_title = decision.get("decision_title", "")
    question = decision.get("question", "")
    options = decision.get("options", [])
    recommended = decision.get("recommended_option_id")

    # 找到用户选择的选项描述
    choice_desc = ""
    for opt in options:
        if opt.get("option_id") == user_choice:
            choice_desc = opt.get("description", "")
            break

    # 构建新记录
    new_entry = [
        "",
        f"### Iteration {iteration} ({timestamp})",
        "",
        f"**问题**: {decision_title}",
        "",
        f"- **选择**: {user_choice} - {choice_desc}",
    ]

    if recommended:
        was_recommended = "是" if user_choice == recommended else "否"
        new_entry.append(f"- **是否采纳推荐**: {was_recommended}（推荐: {recommended}）")

    if user_comment and user_comment.strip():
        # 截断过长的备注
        comment = user_comment.strip()
        if len(comment) > 200:
            comment = comment[:200] + "..."
        new_entry.append(f"- **用户备注**: {comment}")

    new_entry.append("")

    # 写入文件
    USER_DECISION_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_DECISION_PATTERNS_FILE.write_text(
        existing + "\n".join(new_entry),
        encoding="utf-8"
    )


def _create_decision_patterns_header() -> str:
    """创建决策模式文档头部"""
    return """# 用户决策习惯整合

> 此文档记录您在工作流中的决策历史，帮助您了解自己的决策模式。

## 决策记录

"""
```

### 4.4 总结代理提示词扩展

在 `subagent_prompt_summary.md` 中新增：

```markdown
## 新增：用户洞察（可选字段）

除了必填的 JSON 摘要字段外，你可以提供 `user_insight` 字段，用于生成面向用户的洞察报告。

### 行为合理性检查

评估本轮代理行为，给出以下维度的评分和说明：

1. **任务对齐度**（0-100%）
   - 对比 project_history.md 中的 Task Goal
   - 评估代理执行是否偏离用户目标

2. **决策质量**
   - 检查 MAIN 的 next_agent 选择是否合理
   - 是否符合 TDD 流程（如适用）

3. **范围控制**
   - 检查修改的文件是否在预期范围内
   - 标记任何可能的范围蔓延

4. **效率评估**
   - 检查是否存在重复失败或无效循环
   - 给出效率改进建议（如有）

### 输出格式

在 JSON 中新增 `user_insight` 字段（可选）：

```json
{
  "user_insight": {
    "behavior_check": {
      "task_alignment": {"score": 90, "status": "good", "detail": "执行符合用户分析需求"},
      "decision_quality": {"status": "compliant", "issues": []},
      "scope_control": {"status": "normal", "detail": "修改在预期范围内"},
      "efficiency": {"status": "normal", "repeated_failures": 0, "same_agent_streak": 1}
    },
    "recommendations": [
      "当前分析任务已较为全面，可考虑进入修复阶段"
    ]
  }
}
```

### 状态值说明

- `task_alignment.status`: "good" (>=80%) / "attention" (60-79%) / "warning" (<60%)
- `decision_quality.status`: "compliant" / "attention" / "violation"
- `scope_control.status`: "normal" / "attention" / "warning"
- `efficiency.status`: "normal" / "attention" / "warning"
```

### 4.5 用户洞察报告生成逻辑（summary.py）

```python
def _generate_user_insight_report(
    *,
    iteration: int,
    summary: IterationSummary,
    user_insight: dict,
) -> None:
    """
    生成面向用户的洞察报告（Markdown 格式）。

    触发时机：SUMMARY 阶段成功完成后
    """
    from datetime import datetime

    if not ENABLE_BEHAVIOR_AUDIT:
        return

    timestamp = datetime.now().isoformat(timespec="seconds")
    behavior = user_insight.get("behavior_check", {})
    recommendations = user_insight.get("recommendations", [])

    lines = [
        "# 用户洞察报告",
        "",
        f"> 生成时间: {timestamp}",
        f"> 当前迭代: {iteration}",
        f"> 代理: {summary.get('subagent', {}).get('agent', 'N/A')}",
        "",
        "## 本轮摘要",
        "",
        summary.get("summary", ""),
        "",
        "## 行为合理性检查",
        "",
    ]

    # 任务对齐度
    alignment = behavior.get("task_alignment", {})
    score = alignment.get("score", 0)
    status = alignment.get("status", "unknown")
    status_icon = "✅" if status == "good" else "⚠️" if status == "attention" else "❌"
    lines.extend([
        f"### 任务对齐度: {status_icon} {status} ({score}%)",
        "",
        f"- {alignment.get('detail', '无详情')}",
        "",
    ])

    # 决策质量
    decision_check = behavior.get("decision_quality", {})
    status = decision_check.get("status", "unknown")
    status_icon = "✅" if status == "compliant" else "⚠️"
    lines.extend([
        f"### 决策质量: {status_icon} {status}",
        "",
    ])
    issues = decision_check.get("issues", [])
    if issues:
        for issue in issues:
            lines.append(f"- ⚠️ {issue}")
    else:
        lines.append("- 无问题")
    lines.append("")

    # 范围控制
    scope = behavior.get("scope_control", {})
    status = scope.get("status", "unknown")
    status_icon = "✅" if status == "normal" else "⚠️"
    lines.extend([
        f"### 范围控制: {status_icon} {status}",
        "",
        f"- {scope.get('detail', '无详情')}",
        "",
    ])

    # 效率评估
    efficiency = behavior.get("efficiency", {})
    status = efficiency.get("status", "unknown")
    status_icon = "✅" if status == "normal" else "⚠️"
    lines.extend([
        f"### 效率评估: {status_icon} {status}",
        "",
        f"- 重复失败: {efficiency.get('repeated_failures', 0)} 次",
        f"- 连续相同代理: {efficiency.get('same_agent_streak', 0)} 轮",
        "",
    ])

    # 建议
    if recommendations:
        lines.extend(["## 建议", ""])
        for idx, rec in enumerate(recommendations, 1):
            lines.append(f"{idx}. {rec}")
        lines.append("")

    # 进度概览
    progress = summary.get("progress")
    if progress and progress.get("milestones"):
        lines.extend(["## 进度概览", "", "| 里程碑 | 完成度 |", "|--------|--------|"])
        for ms in progress.get("milestones", []):
            lines.append(f"| {ms['milestone_id']}: {ms['milestone_name']} | {ms['percentage']:.0f}% |")
        lines.append("")

    lines.extend([
        "---",
        "*此报告由总结代理自动生成，仅供参考*",
    ])

    USER_INSIGHT_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_INSIGHT_REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")


def _append_user_insight_history(
    *,
    iteration: int,
    user_insight: dict,
) -> None:
    """追加用户洞察到历史文件（JSONL 格式）"""
    import json
    from datetime import datetime

    record = {
        "iteration": iteration,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **user_insight,
    }

    USER_INSIGHT_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with USER_INSIGHT_HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
```

### 4.6 工作流集成（workflow.py）

```python
# ========== 集成点 1: USER 决策后（约 L2052-2059）==========

if decision["next_agent"] == "USER":
    user_decision = dict(decision)
    user_decision["doc_patches"] = main_output.get("doc_patches")
    user_choice = _prompt_user_for_decision(iteration=iteration, decision=user_decision, ui=ui)
    _clear_resume_state()

    # 【新增】USER 决策后立即更新决策模式文档
    try:
        from .decision import _update_user_decision_patterns
        _update_user_decision_patterns(
            iteration=iteration,
            decision=user_decision,
            user_choice=user_choice,
            user_comment=None,  # 从 _prompt_user_for_decision 内部获取
        )
        _append_log_line(f"orchestrator: decision_patterns updated for iteration {iteration}\n")
    except Exception as exc:
        _append_log_line(f"orchestrator: decision_patterns error: {exc}\n")

    last_user_decision_iteration = iteration
    continue


# ========== 集成点 2: SUMMARY 阶段内部（_run_summary_stage 函数末尾）==========

def _run_summary_stage(...):
    # ... 现有逻辑：解析摘要、追加历史 ...

    # 【新增】生成用户洞察报告
    user_insight = summary_output.get("user_insight")
    if user_insight:
        try:
            _generate_user_insight_report(
                iteration=iteration,
                summary=summary_output,
                user_insight=user_insight,
            )
            _append_user_insight_history(
                iteration=iteration,
                user_insight=user_insight,
            )
            _append_log_line(f"orchestrator: user_insight_report generated\n")
        except Exception as exc:
            # 洞察报告生成失败不阻塞主流程
            _append_log_line(f"orchestrator: user_insight_report error: {exc}\n")

    if ui is not None:
        ui.state.update(...)
    return
```

## 五、更新频率总结

基于工作流代码分析，各文件的更新时机如下：

```
workflow_loop()
    │
    ├─→ MAIN 决策
    │       │
    │       ├─→ next_agent: USER
    │       │       │
    │       │       ├─→ _prompt_user_for_decision()
    │       │       │
    │       │       ├─→ 【更新】user_decision_patterns.md  ← 立即追加
    │       │       │
    │       │       └─→ continue（不经过 SUMMARY）
    │       │
    │       ├─→ next_agent: PARALLEL_REVIEW
    │       │       │
    │       │       └─→ continue（不经过 SUMMARY，无更新）
    │       │
    │       ├─→ next_agent: FINISH
    │       │       │
    │       │       └─→ FINISH_REVIEW → FINISH_CHECK → 结束（无更新）
    │       │
    │       └─→ next_agent: TEST/DEV/REVIEW
    │               │
    │               ├─→ 子代理执行
    │               │
    │               ├─→ _run_summary_stage()
    │               │       │
    │               │       ├─→ 【覆盖】user_insight_report.md
    │               │       │
    │               │       └─→ 【追加】user_insight_history.jsonl
    │               │
    │               └─→ 下一轮迭代
    │
    └─→ 结束
```

| 文件 | 更新方式 | 触发条件 | 频率 |
|------|----------|----------|------|
| `user_insight_report.md` | 覆盖 | SUMMARY 阶段成功 | 每次 TEST/DEV/REVIEW 后 |
| `user_insight_history.jsonl` | 追加 | SUMMARY 阶段成功 | 每次 TEST/DEV/REVIEW 后 |
| `user_decision_patterns.md` | 追加 | USER 决策完成 | 每次用户决策后 |

**不更新的场景**：
- PARALLEL_REVIEW 后（直接 continue）
- FINISH 流程（无 SUMMARY）
- SUMMARY 失败时（容错，不阻塞主流程）

## 六、输出示例

### 6.1 用户洞察报告示例

```markdown
# 用户洞察报告

> 生成时间: 2026-01-31T15:05:24
> 当前迭代: 8

## 本轮摘要

REVIEW 完成第三轮深入分析，发现图信息提取/提交闭环未接入任何 View，章节正文生成前端缺失。

## 行为合理性检查

### 任务对齐度: ✅ 良好 (90%)

- 评估: 执行符合用户"继续调研分析"的要求，新增 18 个功能点分析

### 决策质量: ✅ 合规

- 无问题

### 范围控制: ⚠️ 注意

- 报告文件 doc/e2e_test_evaluation_report.md 已超过 300 行，建议关注可读性

### 效率评估: ✅ 正常

- 重复失败: 0 次

## 建议

1. 分析任务已累计 74+ 功能点，覆盖较为全面
2. 用户已多次选择"继续分析"，如需进入修复阶段，建议明确优先级
3. 关键缺失（图信息提取、正文生成）属于实现问题，需 DEV 介入

## 进度概览

| 里程碑 | 完成度 |
|--------|--------|
| M0: 引导与黑板契约 | 100% |
| M1: 前端基础骨架 | 50% |

---
*此报告由总结代理自动生成，仅供参考*
```

### 6.2 用户决策习惯文档示例

```markdown
# 用户决策习惯整合

> 此文档记录您在工作流中的决策历史，帮助您了解自己的决策模式。

## 决策记录

### Iteration 2 (2026-01-31T01:44:21)

**问题**: 前端E2E测试评估结果

- **选择**: opt4 - 需要更详细的覆盖度矩阵或其他补充分析
- **是否采纳推荐**: 否（推荐: opt1）
- **用户备注**: 将让审阅代理直接一边分析一边记录详细报告到doc中

### Iteration 4 (2026-01-31T14:00:40)

**问题**: E2E测试分析报告已完成

- **选择**: opt4 - 需要补充其他分析或修改报告内容
- **是否采纳推荐**: 否（推荐: opt1）
- **用户备注**: 继续分析，在实际使用的时候错误修改重试以及提示词配置模型apibaseurl超时时间配置等功能也要有

### Iteration 6 (2026-01-31T14:26:53)

**问题**: 补充分析完成，发现新问题

- **选择**: opt2 - 继续深入分析其他功能点
- **用户备注**: 创作过程中缺少手动提取当前的图信息到世界观中的步骤...

### Iteration 8 (2026-01-31T15:05:24)

**问题**: 创作流程分析完成，发现实现缺失

- **选择**: opt3 - 启动修复流程，按P0优先级补齐前端实现和E2E测试
- **是否采纳推荐**: 否（推荐: opt1）
- **用户备注**: 按照发现补全所有的端对端测试代码，要求合理真实有效，然后进行测试驱动开发

---
*此文档记录您的决策历史，帮助您了解自己的决策模式*
```

## 七、实现优先级

| 优先级 | 功能 | 工作量 | 说明 |
|--------|------|--------|------|
| P0 | 用户决策习惯整合 | 低 | 在 decision.py 中添加追加逻辑 |
| P1 | 用户洞察报告生成 | 中 | 扩展 SUMMARY 提示词 + summary.py |
| P2 | 行为合理性检查 | 中 | 四个维度评估逻辑 |
| P3 | 洞察历史记录 | 低 | JSONL 追加 |

## 八、注意事项

1. **不影响工作流**: 所有输出仅供用户参考，不注入到 MAIN 决策
2. **容错处理**: 报告生成失败不阻塞主流程，仅记录日志
3. **更新时机明确**:
   - `user_insight_report.md`: SUMMARY 阶段成功后覆盖
   - `user_decision_patterns.md`: USER 决策后立即追加（不依赖 SUMMARY）
4. **可选功能**: 可通过 `ENABLE_BEHAVIOR_AUDIT` 和 `ENABLE_DECISION_PATTERNS` 开关禁用

## 九、后续扩展

1. **UI 集成**: 在前端展示用户洞察报告和决策历史
2. **历史对比**: 支持查看历史洞察报告（通过 user_insight_history.jsonl）
3. **偏好分析**: 基于决策历史自动生成偏好总结
4. **跨任务复用**: 支持导出用户偏好供其他项目参考
