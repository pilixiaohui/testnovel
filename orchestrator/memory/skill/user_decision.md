# 用户决策输出规范

本文档定义 MAIN 代理向用户请求决策时的输出规范。

## 多问题决策处理规范

### 问题拆分原则

当发现多个需要用户决策的问题时，必须分析问题的独立性：

| 问题类型 | 定义 | 处理方式 |
|---------|------|----------|
| **独立问题** | 问题之间没有依赖关系，可以独立决策 | 拆分成多个 USER 决策，每轮处理一个 |
| **依赖问题** | 问题之间有依赖关系，必须按顺序决策 | 先决策前置问题，后续问题在下一轮决策 |
| **互斥问题** | 问题之间互斥，只能选择一个方向 | 合并成一个决策，选项互斥 |

### 示例

- 构建失败 vs API 契约缺失 → **独立问题**，拆分处理
- 先定义 API 契约 → 再实现 API → **依赖问题**，按顺序决策
- 重构 vs 修补 → **互斥问题**，合并成一个决策

---

## 禁止打包独立问题

### 错误做法

将多个独立问题打包成"全局策略"：

```json
{
  "question": "发现3个问题，请选择修复策略",
  "options": [
    {"option_id": "opt1", "description": "策略A：先修问题1，再修问题2"},
    {"option_id": "opt2", "description": "策略B：先修问题2，再修问题1"},
    {"option_id": "opt3", "description": "策略C：只修问题1"}
  ]
}
```

**问题**：用户无法对每个问题独立决策，只能选择预设的策略组合。

### 正确做法

拆分成多个独立决策，每轮处理一个问题：

**第一轮**：
```json
{
  "next_agent": "USER",
  "decision_title": "构建失败处理",
  "question": "npm run build 因 TS 类型错误失败，如何处理？",
  "options": [
    {"option_id": "fix_now", "description": "立即修复类型错误"},
    {"option_id": "skip_build", "description": "暂时跳过构建检查，先处理其他问题"}
  ],
  "recommended_option_id": "fix_now",
  "reason": "构建失败会阻塞后续测试"
}
```

**第二轮**（上一轮决策后自动继续）：
```json
{
  "next_agent": "USER",
  "decision_title": "API 契约定义",
  "question": "前端调用 /roots 但后端未定义此端点，如何处理？",
  "options": [
    {"option_id": "define_backend", "description": "在后端新增 /roots 端点"},
    {"option_id": "change_frontend", "description": "修改前端调用现有端点"}
  ],
  "recommended_option_id": "define_backend",
  "reason": "新增端点更符合 RESTful 设计"
}
```

---

## 决策拆分流程

1. **识别所有问题**：列出所有需要用户决策的问题
2. **分析依赖关系**：判断问题之间是否有依赖
3. **确定决策顺序**：
   - 独立问题：按优先级排序，逐个决策
   - 依赖问题：先决策前置问题
   - 互斥问题：合并成一个决策
4. **生成第一个决策**：本轮只输出第一个决策
5. **后续决策**：用户回答后，下一轮继续处理剩余问题

---

## 单个决策的格式要求

每个决策必须满足以下要求：

### 必填字段

```json
{
  "next_agent": "USER",
  "decision_title": "具体问题的简短标题（10字以内）",
  "question": "具体问题的详细描述，包括：\n- 当前状态\n- 问题影响\n- 需要用户决定什么",
  "options": [
    {
      "option_id": "opt1",
      "description": "具体行动方案A：做什么、影响什么、风险是什么"
    },
    {
      "option_id": "opt2",
      "description": "具体行动方案B：做什么、影响什么、风险是什么"
    }
  ],
  "recommended_option_id": "opt1",
  "reason": "推荐理由（简短说明为什么推荐这个选项）",
  "history_append": "## Iteration {N}:\nnext_agent: USER\nreason: {决策原因}"
}
```

### 可选字段

```json
{
  "remaining_decisions": 2,  // 告知用户还有几个问题待决策
  "context": "补充背景信息",
  "impact": "选择不同选项的影响说明"
}
```

### 格式规范

1. **聚焦单一问题**：一个决策只处理一个具体问题
2. **提供具体选项**：选项是具体的行动方案，不是抽象策略
3. **说明影响**：每个选项说明其影响和风险
4. **推荐选项**：给出推荐选项和理由
5. **选项数量**：2-4 个选项，不宜过多

---

## 完整示例

### 场景：并行审阅发现 3 个阻塞问题

**问题分析**：
- 问题1：构建失败（独立，可立即处理）
- 问题2：需求契约缺失（独立，需要用户定义）
- 问题3：API 契约不一致（依赖问题2，需要先定义契约）

**决策顺序**：
1. 先决策问题1（构建失败）
2. 再决策问题2（需求契约）
3. 问题3 在问题2 决策后自动处理（或再次询问）

**第一轮输出**：

```json
{
  "next_agent": "USER",
  "decision_title": "构建失败处理",
  "question": "npm run build 因以下 TS 类型错误失败：\n- StateExtractPanel.vue: 类型不匹配\n- project.ts: 缺少类型定义\n- EditorView.vue: 属性不存在\n\n如何处理？",
  "options": [
    {
      "option_id": "fix_now",
      "description": "立即修复：派发 DEV 修复所有类型错误，预计影响 3 个文件"
    },
    {
      "option_id": "fix_later",
      "description": "延后修复：先处理其他问题，构建检查暂时跳过"
    }
  ],
  "recommended_option_id": "fix_now",
  "reason": "构建失败会阻塞后续测试，建议优先修复",
  "remaining_decisions": 2,
  "history_append": "## Iteration 2:\nnext_agent: USER\nreason: 构建失败需要用户决策处理方式\n待决策问题: 1/3"
}
```

---

## 常见错误

| 错误 | 说明 | 正确做法 |
|------|------|----------|
| 打包独立问题 | 将多个独立问题合并成一个决策 | 拆分成多个决策 |
| 选项过于抽象 | 选项是"策略A/B/C"而非具体行动 | 选项应是具体的行动方案 |
| 缺少推荐 | 没有给出推荐选项 | 必须给出推荐和理由 |
| 问题描述模糊 | 用户不知道在决定什么 | 详细描述当前状态和影响 |
| 选项过多 | 超过 4 个选项 | 控制在 2-4 个选项 |

---

## MAIN 输出格式

MAIN 升级 USER 时，必须使用以下 JSON 格式输出：

```json
{
  "next_agent": "USER",
  "reason": "升级原因",
  "decision_title": "具体问题的简短标题（10字以内）",
  "question": "具体问题的详细描述",
  "options": [
    {"option_id": "opt1", "description": "具体行动方案A"},
    {"option_id": "opt2", "description": "具体行动方案B"}
  ],
  "recommended_option_id": "opt1",
  "history_append": "## Iteration {N}:\nnext_agent: USER\nreason: {决策原因}"
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `next_agent` | ✅ | 固定为 `"USER"` |
| `reason` | ✅ | 升级原因 |
| `decision_title` | ✅ | 问题简短标题（10字以内） |
| `question` | ✅ | 问题详细描述 |
| `options` | ✅ | 选项列表（2-4个） |
| `recommended_option_id` | ✅ | 推荐选项的 ID |
| `history_append` | ✅ | 追加到 project_history 的内容 |
| `remaining_decisions` | ❌ | 可选，告知用户还有几个问题待决策 |
