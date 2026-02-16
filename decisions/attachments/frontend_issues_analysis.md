# AI Novel V4.0 前端问题分析报告

**分析日期**: 2026-02-01
**分析范围**: project/frontend 全部代码
**对照文档**: doc/frontend_implementation_spec.md, doc/系统架构与技术规格.md

---

## 一、项目管理问题

### 问题 1：项目无法持久化保存

**严重程度**: 致命

**现状**: `stores/project.ts` 只有 9 行代码，仅包含 `project_id` 和 `project_name` 两个字段，没有任何保存/加载逻辑。

```typescript
// stores/project.ts (完整代码)
export const useProjectStore = defineStore('project', {
  state: () => ({
    project_id: '',
    project_name: '',
  }),
})
```

**影响**:
- 雪花流程完成后，刷新页面所有数据丢失
- 项目没有持久化到后端或 localStorage
- 用户无法恢复之前的创作进度

**规格要求** (frontend_implementation_spec.md):
- `loadBranches()` - 调用 branchApi.listBranches
- `switchBranch(branchId)` - 调用 branchApi.switchBranch
- `createBranch(branchId)` - 调用 branchApi.createBranch
- `setProject(rootId, branchId?)` - 设置当前项目
- `clearProject()` - 清空项目状态

---

### 问题 2：项目列表功能缺失

**严重程度**: 致命

**现状**: `HomeView.vue` 显示"当前项目"，但缺少：
- 项目列表 API 调用
- 创建新项目功能
- 加载已有项目功能
- 删除/归档项目功能

**影响**:
- 用户无法管理多个小说项目
- 无法切换或恢复之前的创作

---

## 二、雪花流程问题

### 问题 3：每一步的提示词无法编辑

**严重程度**: 高

**现状**: `SnowflakeView.vue` 中每个步骤只有"Run Step X"按钮，没有：
- 编辑 LLM 提示词的入口
- 自定义约束参数（如角色数量、章节数量）
- 保存/加载提示词模板

**规格要求** (系统架构与技术规格.md 2.5节):
- 支持通过 `prompt_constraint` 字段传递数量约束
- 约束示例："生成 3 幕结构"、"本幕包含 4 个章节"、"生成 5 个主要角色"

---

### 问题 4：生成结果无法编辑

**严重程度**: 高

**现状**: `Step2Panel.vue` 只是展示 `root` 数据，没有编辑功能：

```vue
<el-descriptions-item label="Logline">{{ root.logline }}</el-descriptions-item>
```

**影响**:
- 用户无法修改 AI 生成的 logline、主题、结局
- 无法调整角色小传
- 无法编辑场景骨架

---

### 问题 5：步骤间数据没有保存到后端

**严重程度**: 致命

**现状**: `snowflake.ts` store 的数据只存在内存中，没有调用后端保存 API：

```typescript
async fetchStep2(logline: string) {
  const root = await fetchSnowflakeStep2(logline)
  this.steps.root = root  // 只存内存，没有持久化
  return root
}
```

**影响**:
- Step 1-6 的中间结果没有持久化
- 中途退出或刷新页面，全部数据丢失

---

## 三、编辑器问题

### 问题 6：场景编辑器与雪花流程脱节

**严重程度**: 高

**现状**: `EditorView.vue` 使用硬编码的场景 ID：

```typescript
const sceneId = ref('scene-1')  // 硬编码
```

**影响**:
- 编辑器无法选择雪花流程生成的具体场景
- 无法与项目数据关联

---

### 问题 7：场景列表缺失

**严重程度**: 高

**现状**: 文档规格要求"左侧 el-tree 场景列表"，但实际代码没有实现场景树形结构。

**规格要求** (frontend_implementation_spec.md Step 4.1):
- 三栏布局 (6:12:6)
- 左侧 el-tree 场景列表
- 中间 el-tabs (大纲/正文/推演日志)
- 右侧 SceneContextPanel

---

### 问题 8：保存功能不完整

**严重程度**: 中

**现状**: `saveScene` 只保存 `outcome` 和 `summary`，不保存 `title` 和 `notes`：

```typescript
await updateScene(sceneId.value, branchId, {
  outcome: store.outcome,
  summary: store.summary,
  // 缺少 title 和 notes
})
```

---

### 问题 9：没有自动保存机制

**严重程度**: 中

**现状**: 编辑器有 `is_dirty` 标记，但没有：
- 自动保存定时器
- 离开页面前的保存提醒
- 草稿恢复功能

**影响**:
- 用户编辑内容容易丢失

---

### 问题 10：缺少加载状态和错误处理 UI

**严重程度**: 中

**现状**: 雪花流程页面没有使用 `LoadingOverlay` 组件，API 调用时没有 loading 状态显示。

**影响**:
- 用户不知道 AI 正在生成
- 可能重复点击按钮

---

### 问题 11：组件未被使用

**严重程度**: 中

**现状**: 很多组件是空壳（45-51 字节），如：
- `BeatCard.vue` (45 bytes)
- `EntityList.vue` (47 bytes)
- `AnchorTimeline.vue` (51 bytes)
- `EmptyState.vue` (47 bytes)

**影响**:
- 文档规格中的组件大部分未实现

---

## 四、推演控制台问题

### 问题 12：场景选择硬编码

**严重程度**: 高

**现状**: `SimulationView.vue` 中场景 ID 硬编码：

```typescript
const sceneId = ref('scene-1')  // 硬编码
```

**影响**:
- 用户无法选择要推演的具体场景
- 无法从雪花流程生成的场景列表中选择

---

### 问题 13：缺少场景上下文加载

**严重程度**: 致命

**现状**: 推演时 `runRound` 传入空的 `scene_context` 和 `agents`：

```typescript
const resultPromise = store.runRound({
  round_id: roundId,
  scene_context: {},  // 空对象
  agents: [],         // 空数组
})
```

**影响**:
- 推演没有加载实际的场景上下文和角色代理状态
- 推演结果不正确或无意义

---

### 问题 14：代理状态是静态 Mock 数据

**严重程度**: 高

**现状**: `agentState` 是硬编码的假数据，不是从后端加载：

```typescript
const agentState = ref<CharacterAgentState>({
  id: 'agent-1',
  character_id: 'Nova',  // 硬编码假数据
  branch_id: 'b1',
  beliefs: { focus: 'protect the realm' },
  desires: [],
  intentions: [],
  memory: [],
  private_knowledge: {},
  last_updated_scene: 1,
  version: 1,
})
```

**影响**:
- 推演控制台显示的角色代理状态不是真实数据

---

### 问题 15：缺少多角色代理支持

**严重程度**: 高

**现状**: 文档规格要求"左侧 AgentStatePanel 列表"，但实际只显示单个 `agentState`，没有角色列表。

**规格要求** (frontend_implementation_spec.md Step 3.1):
- 三栏布局 (6:12:6)
- 左侧 AgentStatePanel 列表
- 中间 ActionTimeline + ArbitrationResult
- 右侧 ConvergenceIndicator + 渲染结果

---

### 问题 16：收敛指示器未使用

**严重程度**: 中

**现状**: `ConvergenceIndicator.vue` 组件已实现，但 `SimulationView.vue` 没有引入和使用它。

**影响**:
- 用户看不到收敛进度和锚点距离
- 无法判断推演是否偏离目标

---

### 问题 17：裁决结果组件未使用

**严重程度**: 中

**现状**: `ArbitrationResult.vue` 组件存在但未在推演页面使用。

**影响**:
- DM 裁决结果没有专门的展示区域

---

## 五、世界观管理问题

### 问题 18：世界列表是硬编码数据

**严重程度**: 高

**现状**: `WorldView.vue` 中世界列表是静态数据：

```typescript
const worlds = ref([
  { id: 'world-1', name: 'Default World' },
  { id: 'world-2', name: 'Shadow Realm' },
])
```

**影响**:
- 世界观数据不是从后端加载的
- 与雪花流程生成的项目没有关联

---

### 问题 19：实体创建使用硬编码数据

**严重程度**: 高

**现状**: 创建实体时使用固定的假数据：

```typescript
await createEntity(rootId.value, branchId, {
  name: 'New Entity',  // 硬编码
  entity_type: 'Character',
  tags: [],
  arc_status: 'active',
  semantic_states: {
    position: { x: 0, y: 0, z: 0 },
  },
})
```

**影响**:
- 无法自定义创建实体的名称、类型等属性
- 没有创建表单

---

### 问题 20：锚点只显示 ID，没有详细信息

**严重程度**: 中

**现状**: 锚点列表只显示字符串：

```vue
<li v-for="anchor in anchors" :key="anchor">{{ anchor }}</li>
```

**规格要求** (frontend_implementation_spec.md):
- 锚点应显示：anchor_type, description, constraint_type, required_conditions, achieved 状态
- 应使用 `AnchorTimeline` 组件展示

---

### 问题 21：支线管理功能不完整

**严重程度**: 中

**现状**: `subplots` 只是字符串数组，没有使用 `SubplotPanel` 组件：

```typescript
const subplots = ref<string[]>([])
```

**影响**:
- 支线没有显示详细信息（类型、状态、冲突）
- 无法激活或解决支线

---

### 问题 22：关系图谱未集成到页面

**严重程度**: 中

**现状**: `RelationGraph.vue` 组件已实现，但 `WorldView.vue` 只用 JSON 显示关系：

```typescript
const relationOutput = computed(() => JSON.stringify(relations.value, null, 2))
```

**影响**:
- 关系图谱可视化功能未使用

---

## 六、设置页面问题

### 问题 23：设置页面是空壳

**严重程度**: 中

**现状**: `SettingsView.vue` 只有 19 行代码，没有任何实际设置项：

```vue
<template>
  <section class="settings-view" data-test="settings-view-root">
    <h1>Settings</h1>
    <p>No settings available.</p>
    <button type="button" data-test="settings-save" @click="saveSettings">Save</button>
    <p v-if="saveStatus" data-test="settings-save-status">{{ saveStatus }}</p>
  </section>
</template>
```

**应有功能**:
- LLM 模型选择
- API 密钥配置
- 默认参数设置（章节字数、推演回合数等）
- 主题/语言设置

---

## 七、通用问题

### 问题 24：页面间数据不共享

**严重程度**: 高

**现状**: 各页面使用独立的 `rootId`、`branchId`，没有统一的项目上下文：
- `EditorView.vue`: 从 URL query 读取
- `WorldView.vue`: 硬编码 `worlds[0].id`
- `SimulationView.vue`: 硬编码 `'scene-1'`

**影响**:
- 页面间数据不一致
- 无法在同一个项目上下文中工作

---

### 问题 25：缺少全局错误处理

**严重程度**: 中

**现状**: 各页面的 API 调用错误处理不一致，有的只是 `return`，有的设置 `errorMessage`：

```typescript
// WorldView.vue - 错误被静默忽略
const loadWorld = async () => {
  try {
    // ...
  } catch (error) {
    return  // 静默失败
  }
}
```

---

### 问题 26：缺少路由守卫

**严重程度**: 中

**现状**: 没有路由守卫检查项目是否已加载，用户可以直接访问编辑器等页面。

**影响**:
- 用户可能在没有项目的情况下进入编辑器
- 导致空白页面或错误

---

## 七、类型定义问题

### 问题 27：锚点类型定义过于宽松

**严重程度**: 中

**现状**: `types/snowflake.ts` 中锚点类型定义为 `Record<string, unknown>`：

```typescript
export type SnowflakeAnchor = Record<string, unknown>
```

**规格要求** (frontend_implementation_spec.md):
```typescript
export interface StoryAnchor {
  id: string
  root_id: string
  branch_id: string
  sequence: number
  anchor_type: 'inciting_incident' | 'midpoint' | 'climax' | 'resolution' | string
  description: string
  constraint_type: 'hard' | 'soft' | 'flexible'
  required_conditions: string[]
  earliest_chapter_seq?: number
  latest_chapter_seq?: number
  achieved: boolean
}
```

**影响**:
- 类型检查失效
- IDE 无法提供自动补全
- 容易出现运行时错误

---

### 问题 28：Chapter 类型缺少 rendered_content 字段

**严重程度**: 中

**现状**: `types/snowflake.ts` 中 Chapter 接口缺少关键字段：

```typescript
export interface Chapter {
  id: string
  act_id: string
  sequence: number
  title: string
  focus: string
  pov_character_id?: string
  review_status?: ChapterReviewStatus
  // 缺少 rendered_content, manually_edited
}
```

**规格要求**:
- `rendered_content?: string` - 渲染后的章节内容
- `manually_edited: boolean` - 是否手动编辑过

---

### 问题 29：WorldEntity 类型与 EntityView 不一致

**严重程度**: 低

**现状**: `types/entity.ts` 中定义了两种实体类型，字段不一致：

```typescript
// EntityView 使用 entity_id
export interface EntityView {
  entity_id: string
  // ...
}

// WorldEntity 使用 id
export interface WorldEntity extends EntityBase {
  id: string  // 来自 EntityBase
  type: string
  position: EntityPosition
}
```

**影响**:
- 代码中需要处理两种不同的 ID 字段名
- 容易混淆

---

## 八、API 层问题

### 问题 30：缺少项目列表 API

**严重程度**: 高

**现状**: `api/` 目录下没有项目列表相关的 API：
- 没有 `listRoots()` 或 `listProjects()` 函数
- 无法获取用户的所有项目

**影响**:
- 首页无法显示项目列表
- 无法实现项目切换功能

---

### 问题 31：缺少场景列表 API 调用

**严重程度**: 高

**现状**: `api/scene.ts` 中 `fetchScenes` 函数调用的是根节点 API，不是场景列表：

```typescript
export const fetchScenes = (rootId: string, branchId: string) =>
  apiClient.get(`/roots/${rootId}`, {  // 这是获取根节点，不是场景列表
    params: { branch_id: branchId },
  })
```

**影响**:
- 编辑器无法获取场景列表
- 无法实现场景树形结构

---

### 问题 32：API 返回值类型不一致

**严重程度**: 中

**现状**: 部分 API 函数使用 `as unknown as` 强制类型转换：

```typescript
// stores/snowflake.ts
const logline = (await fetchSnowflakeStep1(idea)) as unknown as string[]
const root = (await fetchSnowflakeStep2(logline)) as unknown as SnowflakeStructure
```

**影响**:
- 类型安全性降低
- 可能隐藏运行时错误

---

### 问题 33：缺少 reviewScene API

**严重程度**: 中

**现状**: `api/scene.ts` 中没有 `reviewScene` 函数，但规格要求有：

**规格要求** (frontend_implementation_spec.md):
```typescript
reviewScene(sceneId, status, comment?) -> SceneView  // PUT /scenes/{id}/review
```

---

## 九、组合式函数问题

### 问题 34：useSnowflake 功能不完整

**严重程度**: 中

**现状**: `composables/useSnowflake.ts` 只是简单包装 store，没有提供：
- 步骤执行逻辑
- 数据验证
- 错误处理

```typescript
// 完整代码只有 30 行，只是 getter 包装
export const useSnowflake = () => {
  const store = useSnowflakeStore()
  const logline = computed(() => store.logline)
  // ... 其他 getter
  return { store, logline, root, characters, scenes, acts, chapters, anchors, reset }
}
```

**规格要求** (frontend_implementation_spec.md):
- `useSimulation.ts` - 推演控制逻辑
- `usePolling.ts` - 轮询逻辑
- `useNotification.ts` - 通知逻辑

---

### 问题 35：缺少 useSimulation 组合式函数

**严重程度**: 中

**现状**: `composables/` 目录下没有 `useSimulation.ts`。

**规格要求**:
- 推演控制逻辑
- 回合管理
- 收敛检查

---

### 问题 36：缺少 usePolling 组合式函数

**严重程度**: 低

**现状**: 没有轮询逻辑的组合式函数。

**影响**:
- 无法实现推演状态的自动刷新
- 无法实现长时间任务的进度查询

---

## 十、布局与样式问题

### 问题 37：页面布局不符合规格

**严重程度**: 中

**现状**: 各页面布局与规格要求不符：

| 页面 | 规格要求 | 实际实现 |
|------|----------|----------|
| SimulationView | 三栏布局 (6:12:6) | 单栏垂直布局 |
| EditorView | 三栏布局 (6:12:6) | 单栏垂直布局 |
| WorldView | el-tabs 4 个标签页 | 4 个独立 section |

---

### 问题 38：缺少响应式布局

**严重程度**: 低

**现状**: 大部分页面没有响应式设计，只有 `HomeView.vue` 有简单的媒体查询：

```css
@media (max-width: 768px) {
  .hero {
    flex-direction: column;
    align-items: flex-start;
  }
}
```

---

### 问题 39：样式变量未统一

**严重程度**: 低

**现状**: 部分组件使用 CSS 变量（如 `var(--color-muted)`），部分直接使用硬编码颜色（如 `#6b7280`）。

---

## 十一、测试问题

### 问题 40：E2E 测试与实际功能不匹配

**严重程度**: 中

**现状**: 存在多个 E2E 测试文件，但测试的功能可能与实际实现不符：
- `tests/e2e/snowflake.spec.ts`
- `tests/e2e/simulation.spec.ts`
- `tests/e2e/chapter-render.spec.ts`

**影响**:
- 测试可能通过但功能实际不可用
- 需要验证测试覆盖率

---

## 问题统计

| 严重程度 | 数量 |
|---------|------|
| 致命 | 4 |
| 高 | 13 |
| 中 | 18 |
| 低 | 5 |
| **总计** | **40** |

---

## 优先修复建议

### 第一优先级（致命问题 - 必须立即修复）

| 序号 | 问题 | 修复内容 |
|------|------|----------|
| 1 | 问题 1：项目持久化 | 完善 project store，添加 localStorage 持久化和后端同步 |
| 2 | 问题 2：项目列表功能 | 添加项目列表 API，实现项目 CRUD |
| 3 | 问题 5：雪花流程数据保存 | 每步完成后调用后端保存 API |
| 4 | 问题 13：推演场景上下文 | 加载真实的场景上下文和代理状态 |

### 第二优先级（核心功能 - 影响基本使用）

| 序号 | 问题 | 修复内容 |
|------|------|----------|
| 5 | 问题 3：提示词编辑 | 添加提示词编辑面板和约束参数输入 |
| 6 | 问题 4：生成结果编辑 | 将展示组件改为可编辑表单 |
| 7 | 问题 6-7：编辑器场景选择 | 实现场景树形列表，支持场景选择 |
| 8 | 问题 12：推演场景选择 | 添加场景选择器 |
| 9 | 问题 14-15：代理状态 | 从后端加载代理状态，支持多角色 |
| 10 | 问题 18-19：世界观数据 | 从后端加载数据，添加创建表单 |
| 11 | 问题 24：页面间数据共享 | 统一使用 project store 管理上下文 |
| 12 | 问题 30-31：API 补全 | 添加项目列表和场景列表 API |

### 第三优先级（功能完善 - 提升用户体验）

| 序号 | 问题 | 修复内容 |
|------|------|----------|
| 13 | 问题 8-9：保存机制 | 完善保存功能，添加自动保存 |
| 14 | 问题 10：加载状态 | 添加 loading 状态和进度显示 |
| 15 | 问题 16-17：组件集成 | 使用已实现的组件 |
| 16 | 问题 20-22：世界观展示 | 完善锚点、支线、关系图谱展示 |
| 17 | 问题 23：设置页面 | 添加实际设置项 |
| 18 | 问题 25-26：错误处理 | 统一错误处理，添加路由守卫 |

### 第四优先级（代码质量 - 长期维护）

| 序号 | 问题 | 修复内容 |
|------|------|----------|
| 19 | 问题 11：空壳组件 | 实现或删除未使用的组件 |
| 20 | 问题 27-29：类型定义 | 完善类型定义，统一字段命名 |
| 21 | 问题 32-33：API 类型 | 修复 API 返回值类型 |
| 22 | 问题 34-36：组合式函数 | 完善 composables |
| 23 | 问题 37-39：布局样式 | 调整布局，统一样式变量 |
| 24 | 问题 40：测试覆盖 | 验证和更新测试用例 |

---

## 附录 A：文件修改清单

### 需要重写的文件

| 文件 | 原因 |
|------|------|
| `stores/project.ts` | 功能严重不足，需要完全重写 |
| `views/SettingsView.vue` | 空壳页面，需要重新设计 |

### 需要大幅修改的文件

| 文件 | 修改内容 |
|------|----------|
| `stores/snowflake.ts` | 添加持久化逻辑 |
| `views/SnowflakeView.vue` | 添加编辑功能、提示词配置 |
| `views/EditorView.vue` | 添加场景列表、三栏布局 |
| `views/SimulationView.vue` | 添加场景选择、多代理支持、三栏布局 |
| `views/WorldView.vue` | 从后端加载数据、使用已有组件 |
| `views/HomeView.vue` | 添加项目列表功能 |

### 需要新增的文件

| 文件 | 功能 |
|------|------|
| `api/project.ts` | 项目列表 API |
| `composables/useSimulation.ts` | 推演控制逻辑 |
| `composables/usePolling.ts` | 轮询逻辑 |
| `composables/useNotification.ts` | 通知逻辑 |
| `components/snowflake/PromptEditor.vue` | 提示词编辑器 |
| `components/editor/SceneTree.vue` | 场景树形列表 |

---

## 附录 B：规格对照表

### 组件实现状态

| 组件 | 规格要求 | 实现状态 |
|------|----------|----------|
| AppHeader | 顶部导航栏 | ✅ 已实现 |
| AppSidebar | 侧边栏菜单 | ✅ 已实现 |
| LoadingOverlay | 加载遮罩 | ✅ 已实现但未使用 |
| EmptyState | 空状态占位 | ❌ 空壳 |
| StepIndicator | 步骤指示器 | ✅ 已实现 |
| Step1-6Panel | 雪花流程面板 | ⚠️ 部分实现，缺少编辑功能 |
| CharacterCard | 角色卡片 | ✅ 已实现 |
| SceneCard | 场景卡片 | ✅ 已实现 |
| ActCard | 幕卡片 | ✅ 已实现 |
| ChapterCard | 章卡片 | ✅ 已实现 |
| AgentStatePanel | 代理状态面板 | ✅ 已实现 |
| ActionTimeline | 行动时间线 | ✅ 已实现 |
| ArbitrationResult | 裁决结果展示 | ✅ 已实现但未使用 |
| ConvergenceIndicator | 收敛指示器 | ✅ 已实现但未使用 |
| RoundPlayer | 回合播放器 | ✅ 已实现 |
| SceneEditor | 场景编辑器 | ⚠️ 部分实现 |
| ContentRenderer | 内容渲染器 | ✅ 已实现 |
| VersionDiff | 版本对比 | ✅ 已实现 |
| MarkdownPreview | Markdown 预览 | ✅ 已实现 |
| SimulationLogs | 推演日志查看 | ✅ 已实现 |
| SceneContextPanel | 场景上下文面板 | ✅ 已实现 |
| EntityList | 实体列表 | ❌ 空壳 |
| RelationGraph | 关系图谱 | ✅ 已实现但未使用 |
| AnchorTimeline | 锚点时间线 | ❌ 空壳 |
| SubplotPanel | 支线管理面板 | ✅ 已实现但未使用 |

### Store 实现状态

| Store | 规格要求 | 实现状态 |
|-------|----------|----------|
| project | 项目状态管理 | ❌ 严重不足 |
| snowflake | 雪花流程状态 | ⚠️ 缺少持久化 |
| simulation | 推演状态 | ⚠️ 功能不完整 |
| editor | 编辑器状态 | ⚠️ 功能不完整 |
| world | 世界观状态 | ⚠️ 功能不完整 |

### API 实现状态

| API 模块 | 规格要求 | 实现状态 |
|----------|----------|----------|
| snowflake | 雪花流程 API | ✅ 已实现 |
| anchor | 锚点管理 API | ✅ 已实现 |
| agent | 角色代理 API | ✅ 已实现 |
| dm | DM 裁决 API | ✅ 已实现 |
| simulation | 推演引擎 API | ✅ 已实现 |
| scene | 场景管理 API | ⚠️ 缺少 reviewScene |
| entity | 实体管理 API | ✅ 已实现 |
| subplot | 支线管理 API | ✅ 已实现 |
| branch | 分支管理 API | ✅ 已实现 |
| commit | 提交管理 API | ✅ 已实现 |
| llm | LLM API | ✅ 已实现 |
| feedback | 递归反馈 API | ✅ 已实现 |
| review | 审核管理 API | ⚠️ 只有 chapter |
| project | 项目列表 API | ❌ 缺失 |

---

**文档结束**

**下次更新**: 修复问题后更新实现状态
