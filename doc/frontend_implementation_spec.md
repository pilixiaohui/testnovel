# AI Novel V4.0 前端实现技术规格

**文档版本**: 1.2
**最后更新**: 2026-01-30
**对应后端版本**: V4.1

---

## 0. Meta (约束与栈)

**Stack**:
- Vue 3.4+ (Composition API)
- Vite 5.x
- TypeScript 5.4+
- Element Plus 2.x
- Pinia 2.x (状态管理)
- Vue Router 4.x
- Axios 1.x (HTTP 客户端)

**Whitelist**:
- `@vueuse/core` (组合式工具函数)
- `dayjs` (日期处理)
- `lodash-es` (工具函数)
- `echarts` (图表可视化，可选)

**No-Go**:
- 禁止引入 jQuery 或其他 DOM 操作库
- 禁止使用 Class 组件风格
- 禁止直接操作 DOM (除特殊场景)
- 禁止在组件中硬编码 API 地址

**Constraints**:
- 所有 API 调用必须通过统一的 `api/` 模块
- 所有类型定义必须在 `types/` 目录
- 组件必须使用 `<script setup lang="ts">` 语法
- 状态管理必须使用 Pinia Store

**Path**: `/home/zxh/ainovel_v3/project/frontend/`

---

## 1. 项目拓扑 (Topology)

### 1.1 目录结构

```
project/frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/                      # API 调用层
│   │   ├── index.ts              # Axios 实例配置
│   │   ├── snowflake.ts          # 雪花流程 API
│   │   ├── anchor.ts             # 锚点管理 API
│   │   ├── agent.ts              # 角色代理 API
│   │   ├── dm.ts                 # DM 裁决 API
│   │   ├── simulation.ts         # 推演引擎 API
│   │   ├── scene.ts              # 场景管理 API
│   │   ├── entity.ts             # 实体管理 API
│   │   ├── subplot.ts            # 支线管理 API
│   │   ├── branch.ts             # 分支管理 API
│   │   ├── commit.ts             # 提交管理 API
│   │   ├── llm.ts                # LLM 与逻辑检查 API
│   │   ├── feedback.ts           # 递归反馈 API
│   │   └── review.ts             # 审核管理 API
│   │
│   ├── components/               # 通用组件
│   │   ├── common/               # 基础组件
│   │   │   ├── AppHeader.vue
│   │   │   ├── AppSidebar.vue
│   │   │   ├── LoadingOverlay.vue
│   │   │   └── EmptyState.vue
│   │   ├── snowflake/            # 雪花流程组件
│   │   │   ├── StepIndicator.vue
│   │   │   ├── LoglineSelector.vue
│   │   │   ├── CharacterCard.vue
│   │   │   ├── SceneCard.vue
│   │   │   ├── ActCard.vue
│   │   │   └── ChapterCard.vue
│   │   ├── simulation/           # 推演系统组件
│   │   │   ├── AgentStatePanel.vue
│   │   │   ├── ActionTimeline.vue
│   │   │   ├── ArbitrationResult.vue
│   │   │   ├── ConvergenceIndicator.vue
│   │   │   └── RoundPlayer.vue
│   │   ├── editor/               # 编辑器组件
│   │   │   ├── SceneEditor.vue
│   │   │   ├── ContentRenderer.vue
│   │   │   ├── VersionDiff.vue
│   │   │   └── MarkdownPreview.vue
│   │   └── world/                # 世界观组件
│   │       ├── EntityList.vue
│   │       ├── RelationGraph.vue
│   │       ├── AnchorTimeline.vue
│   │       └── SubplotPanel.vue
│   │
│   ├── views/                    # 页面视图
│   │   ├── HomeView.vue          # 首页/项目列表
│   │   ├── SnowflakeView.vue     # 雪花流程向导
│   │   ├── SimulationView.vue    # 推演控制台
│   │   ├── EditorView.vue        # 场景编辑器
│   │   ├── WorldView.vue         # 世界观管理
│   │   └── SettingsView.vue      # 设置页面
│   │
│   ├── stores/                   # Pinia 状态管理
│   │   ├── index.ts              # Store 导出
│   │   ├── project.ts            # 项目状态
│   │   ├── snowflake.ts          # 雪花流程状态
│   │   ├── simulation.ts         # 推演状态
│   │   ├── editor.ts             # 编辑器状态
│   │   └── world.ts              # 世界观状态
│   │
│   ├── types/                    # TypeScript 类型定义
│   │   ├── index.ts              # 类型导出
│   │   ├── snowflake.ts          # 雪花流程类型
│   │   ├── simulation.ts         # 推演系统类型
│   │   ├── scene.ts              # 场景类型
│   │   ├── entity.ts             # 实体类型
│   │   └── api.ts                # API 响应类型
│   │
│   ├── composables/              # 组合式函数
│   │   ├── useSnowflake.ts       # 雪花流程逻辑
│   │   ├── useSimulation.ts      # 推演控制逻辑
│   │   ├── usePolling.ts         # 轮询逻辑
│   │   └── useNotification.ts    # 通知逻辑
│   │
│   ├── router/                   # 路由配置
│   │   └── index.ts
│   │
│   ├── styles/                   # 全局样式
│   │   ├── variables.scss        # CSS 变量
│   │   ├── reset.scss            # 样式重置
│   │   └── global.scss           # 全局样式
│   │
│   ├── utils/                    # 工具函数
│   │   ├── format.ts             # 格式化函数
│   │   └── validation.ts         # 验证函数
│   │
│   ├── App.vue                   # 根组件
│   └── main.ts                   # 入口文件
│
├── index.html
├── vite.config.ts
├── tsconfig.json
├── package.json
└── .env.development
```

---

## 2. 数据契约 (Types)

### 2.1 雪花流程类型 (`types/snowflake.ts`)

```typescript
// 故事根节点
export interface SnowflakeRoot {
  id?: string;
  logline: string;
  theme: string;
  ending: string;
  three_disasters: string[];
  created_at?: string;
}

// 角色小传
export interface CharacterSheet {
  id?: string;
  name: string;
  ambition: string;
  conflict: string;
  epiphany: string;
  voice_dna: string;
  one_sentence_summary?: string;
}

// 场景节点
export interface SceneNode {
  id: string;
  title: string;
  sequence_index: number;
  parent_act_id: string;
  chapter_id?: string;
  is_skeleton: boolean;
}

// 幕结构
export interface Act {
  id: string;
  root_id: string;
  sequence: number;
  title: string;
  purpose: string;
  tone: 'calm' | 'tense' | 'climax' | 'resolution';
}

// 章结构
export interface Chapter {
  id: string;
  act_id: string;
  sequence: number;
  title: string;
  focus: string;
  pov_character_id?: string;
  rendered_content?: string;      // 渲染后的章节内容
  manually_edited: boolean;       // 是否手动编辑过 (默认 false)
  review_status: 'pending' | 'approved' | 'rejected';  // 审核状态
}

// Step4 结果
export interface Step4Result {
  root_id: string;
  branch_id: string;
  scenes: SceneNode[];
}

// 质量评分
export interface QualityScores {
  coherence_score: number;        // 前后文连贯性 (0-1)
  character_consistency: number;  // 角色行为一致性 (0-1)
  word_count: number;             // 字数
  repetition_ratio: number;       // 重复内容比例 (0-1)
}
```

### 2.2 推演系统类型 (`types/simulation.ts`)

```typescript
// BDI 欲望
export interface Desire {
  id: string;
  type: 'short_term' | 'long_term' | 'reactive';
  description: string;
  priority: number; // 1-10
  satisfaction_condition: string;
  created_at_scene: number;
  expires_at_scene?: number;
}

// BDI 意图
export interface Intention {
  id: string;
  desire_id: string;
  action_type: 'attack' | 'flee' | 'negotiate' | 'investigate' | 'wait' | 'other';
  target: string;
  expected_outcome: string;
  risk_assessment: number; // 0-1
}

// 角色行动
export interface AgentAction {
  agent_id: string;
  internal_thought: string;
  action_type: string;
  action_target: string;
  dialogue?: string;
  action_description: string;
}

// 角色代理状态
export interface CharacterAgentState {
  id: string;
  character_id: string;
  branch_id: string;
  beliefs: Record<string, unknown>;
  desires: Desire[];
  intentions: Intention[];
  memory: unknown[];
  private_knowledge: Record<string, unknown>;
  last_updated_scene: number;
  version: number;
}

// 行动结果
export interface ActionResult {
  action_id: string;
  agent_id: string;
  success: 'success' | 'partial' | 'failure';
  reason: string;
  actual_outcome: string;
}

// DM 裁决
export interface DMArbitration {
  round_id: string;
  action_results: ActionResult[];
  conflicts_resolved: Array<{ agents: string[]; resolution: string }>;
  environment_changes: Array<{ type: string; description: string }>;
}

// 收敛检查
export interface ConvergenceCheck {
  next_anchor_id: string;
  distance: number; // 0-1
  convergence_needed: boolean;
  suggested_action?: string;
}

// 推演回合结果
export interface SimulationRoundResult {
  round_id: string;
  agent_actions: AgentAction[];
  dm_arbitration: DMArbitration;
  narrative_events: Array<Record<string, unknown>>;
  sensory_seeds: Array<{ type: string; detail: string; char_id?: string }>;
  convergence_score: number;
  drama_score: number;
  info_gain: number;
  stagnation_count: number;
}

// 动态补路结果
export interface ReplanResult {
  success: boolean;
  new_chapters: Array<Record<string, unknown>>;
  modified_anchor?: Record<string, unknown>;
  reason: string;
}

// 动态补路请求
export interface ReplanRequest {
  current_scene_id: string;
  target_anchor_id: string;
  world_state_snapshot: Record<string, unknown>;
  failed_conditions: string[];
}

// 递归反馈报告
export interface FeedbackReport {
  trigger: string;
  feedback: Record<string, unknown>;
  corrections: Array<{ action: string }>;
  severity: number; // 0-1
}
```

### 2.3 实体与世界观类型 (`types/entity.ts`)

```typescript
// 实体视图
export interface EntityView {
  entity_id: string;
  name?: string;
  entity_type?: 'Character' | 'Location' | 'Item';
  tags: string[];
  arc_status?: string;
  semantic_states: Record<string, unknown>;
  has_agent?: boolean;
  agent_state_id?: string;
}

// 实体关系
export interface EntityRelationView {
  from_entity_id: string;
  to_entity_id: string;
  relation_type: string;
  tension: number; // 0-100
}

// 故事锚点
export interface StoryAnchor {
  id: string;
  root_id: string;
  branch_id: string;
  sequence: number;
  anchor_type: 'inciting_incident' | 'midpoint' | 'climax' | 'resolution' | string;
  description: string;
  constraint_type: 'hard' | 'soft' | 'flexible';
  required_conditions: string[];
  earliest_chapter_seq?: number;  // 最早可达成章节序号
  latest_chapter_seq?: number;    // 最晚应达成章节序号 (deadline)
  achieved: boolean;
}

// 支线
export interface Subplot {
  id: string;
  root_id: string;
  branch_id: string;
  title: string;
  subplot_type: 'romance' | 'mystery' | 'rivalry' | string;
  protagonist_id: string;
  central_conflict: string;
  status: 'dormant' | 'active' | 'resolved';
}

// 场景视图 (与后端 SceneVersion 对应)
export interface SceneView {
  id: string;
  branch_id: string;
  status?: string;
  pov_character_id?: string;
  expected_outcome?: string;
  conflict_type?: string;
  actual_outcome: string;
  summary?: string;
  rendered_content?: string;
  logic_exception?: boolean;
  logic_exception_reason?: string;
  is_dirty: boolean;
  simulation_log_id?: string;
  is_simulated?: boolean;
  review_status: 'pending' | 'approved' | 'rejected';  // 审核状态
}

// 场景上下文视图
export interface SceneContextView {
  root_id: string;
  branch_id: string;
  expected_outcome: string;
  semantic_states: Record<string, unknown>;
  summary: string;
  scene_entities: EntityView[];
  characters: Array<{ entity_id: string; name?: string }>;
  relations: EntityRelationView[];
  prev_scene_id?: string;
  next_scene_id?: string;
}

// 世界状态快照
export interface WorldSnapshot {
  id: string;
  scene_version_id: string;
  branch_id: string;
  scene_seq: number;
  entity_states: Record<string, unknown>;
  relations: EntityRelationView[];
}
```

---

## 3. API 调用层 (API Layer)

### 3.1 Axios 实例配置 (`api/index.ts`)

```typescript
// Axios 实例配置
// baseURL: VITE_API_BASE_URL || '/api/v1'
// timeout: 30000ms
// 请求拦截器: 透传 config
// 响应拦截器: 提取 response.data; 错误时 ElMessage.error(detail)
```

### 3.2 雪花流程 API (`api/snowflake.ts`)

```typescript
export const snowflakeApi = {
  generateLoglines(idea: string) -> string[]           // POST /snowflake/step1; 生成 10 个 logline
  generateStructure(logline: string) -> SnowflakeRoot  // POST /snowflake/step2; 扩展故事结构
  generateCharacters(root: SnowflakeRoot) -> CharacterSheet[]  // POST /snowflake/step3
  generateScenes(root, characters) -> Step4Result      // POST /snowflake/step4; 生成场景骨架
  generateActs(rootId, root, characters) -> Act[]      // POST /snowflake/step5a; 生成 3-5 幕
  generateChapters(rootId, root, characters) -> Chapter[]  // POST /snowflake/step5b; 每幕 3-7 章
  listActs(rootId: string) -> Act[]                    // GET /roots/{id}/acts
  listChapters(actId: string) -> Chapter[]             // GET /acts/{id}/chapters
  renderChapter(chapterId: string) -> { ok: boolean, content: string, quality_scores: QualityScores }  // POST /chapters/{id}/render; 渲染章节内容
}
```

### 3.3 锚点管理 API (`api/anchor.ts`)

```typescript
export const anchorApi = {
  generateAnchors(rootId, branchId, root, characters) -> StoryAnchor[]  // POST /roots/{id}/anchors; 生成 10-15 个锚点
  listAnchors(rootId, branchId) -> StoryAnchor[]       // GET /roots/{id}/anchors
  updateAnchor(id, data: Partial<StoryAnchor>) -> StoryAnchor  // PUT /anchors/{id}
  checkAnchor(id, worldState, sceneVersionId?) -> { id, reachable, missing_conditions, achieved }  // POST /anchors/{id}/check
}
```

### 3.4 角色代理 API (`api/agent.ts`)

```typescript
export const agentApi = {
  initAgent(entityId, branchId, initialDesires) -> CharacterAgentState  // POST /entities/{id}/agent/init; 初始化 BDI 代理
  getAgentState(entityId, branchId) -> CharacterAgentState  // GET /entities/{id}/agent/state
  updateDesires(entityId, branchId, desires) -> CharacterAgentState  // PUT /entities/{id}/agent/desires
  decide(entityId, sceneContext) -> AgentAction  // POST /entities/{id}/agent/decide; 触发角色决策
}
```

### 3.5 DM 裁决 API (`api/dm.ts`)

```typescript
export const dmApi = {
  arbitrate(roundId, actions, worldState) -> DMArbitration  // POST /dm/arbitrate; 裁决角色行动
  checkConvergence(worldState, nextAnchor) -> ConvergenceCheck  // POST /dm/converge; 检查收敛状态
  intervene(check, worldState) -> Record<string, unknown>  // POST /dm/intervene; DM 主动干预
  replan(currentScene, targetAnchor, worldState) -> ReplanResult  // POST /dm/replan; 动态补路
}
```

### 3.6 推演引擎 API (`api/simulation.ts`)

```typescript
export const simulationApi = {
  runRound(sceneContext, agents, roundId) -> SimulationRoundResult  // POST /simulation/round; 单回合推演
  runScene(sceneContext, maxRounds) -> { content: string }  // POST /simulation/scene; 完整场景推演
  getLogs(sceneId) -> SimulationRoundResult[]  // GET /simulation/logs/{id}; 获取推演日志
  renderScene(rounds, scene) -> { content: string }  // POST /render/scene; 智能渲染
}
```

### 3.7 场景管理 API (`api/scene.ts`)

```typescript
export const sceneApi = {
  createScene(rootId, branchId, data) -> { commit_id, scene_origin_id, scene_version_id }  // POST /roots/{id}/scene_origins
  deleteScene(rootId, sceneId, message) -> void  // POST /roots/{id}/scenes/{sid}/delete
  completeScene(sceneId, actualOutcome, summary) -> SceneView  // POST /scenes/{id}/complete
  completeOrchestrated(sceneId, data) -> Record<string, unknown>  // POST /scenes/{id}/complete/orchestrated; 含逻辑检查
  renderScene(sceneId) -> { ok, content, quality_scores }  // POST /scenes/{id}/render; 返回质量评分
  getSceneContext(sceneId, branchId) -> SceneContextView  // GET /scenes/{id}/context
  diffScene(sceneId, branchId) -> Record<string, unknown>  // GET /scenes/{id}/diff; 比较场景版本
  markDirty(sceneId) -> void  // POST /scenes/{id}/dirty
  listDirtyScenes(rootId, branchId) -> SceneView[]  // GET /roots/{id}/dirty_scenes
  reviewScene(sceneId, status, comment?) -> SceneView  // PUT /scenes/{id}/review; 审核场景
}
```

### 3.8 实体管理 API (`api/entity.ts`)

```typescript
export const entityApi = {
  createEntity(rootId, branchId, data) -> EntityView  // POST /roots/{id}/entities
  listEntities(rootId, branchId) -> EntityView[]  // GET /roots/{id}/entities
  upsertRelation(rootId, branchId, data) -> EntityRelationView  // POST /roots/{id}/relations; 创建/更新关系
}
```

### 3.9 支线管理 API (`api/subplot.ts`)

```typescript
export const subplotApi = {
  createSubplot(rootId, data) -> SubplotView  // POST /roots/{id}/subplots; 创建支线
  listSubplots(rootId, branchId) -> SubplotView[]  // GET /roots/{id}/subplots; 列出支线
  resolveSubplot(subplotId) -> SubplotView  // POST /subplots/{id}/resolve; 解决支线
}
```

### 3.10 分支管理 API (`api/branch.ts`)

```typescript
export const branchApi = {
  createBranch(rootId, branchId) -> { root_id, branch_id }  // POST /roots/{id}/branches
  listBranches(rootId) -> string[]  // GET /roots/{id}/branches
  switchBranch(rootId, branchId) -> { root_id, branch_id }  // POST /roots/{id}/branches/{bid}/switch
  mergeBranch(rootId, branchId) -> { root_id, branch_id }  // POST /roots/{id}/branches/{bid}/merge
  revertBranch(rootId, branchId) -> { root_id, branch_id }  // POST /roots/{id}/branches/{bid}/revert
  forkFromCommit(rootId, sourceCommitId, newBranchId) -> { root_id, branch_id }  // POST /roots/{id}/branches/fork_from_commit
  forkFromScene(rootId, sceneOriginId, newBranchId) -> { root_id, branch_id }  // POST /roots/{id}/branches/fork_from_scene
  resetBranch(rootId, branchId, targetCommitId) -> { root_id, branch_id }  // POST /roots/{id}/branches/{bid}/reset
  getBranchHistory(rootId, branchId) -> Array<{ id, parent_id?, message?, created_at }>  // GET /roots/{id}/branches/{bid}/history
  getRootSnapshot(rootId, branchId) -> Record<string, unknown>  // GET /roots/{id}; 获取根节点快照
}
```

### 3.11 提交管理 API (`api/commit.ts`)

```typescript
export const commitApi = {
  commitScene(rootId, branchId, data) -> { commit_id, committed_scenes }  // POST /roots/{id}/branches/{bid}/commit
  gcCommits(rootId, options?) -> { deleted_count, deleted_ids }  // POST /commits/gc; 垃圾回收孤立提交
}
```

### 3.12 LLM 与逻辑检查 API (`api/llm.ts`)

```typescript
export const llmApi = {
  toponeGenerate(data) -> { content, usage }  // POST /llm/topone/generate; 调用 TopOne Gemini
  logicCheck(data) -> { valid, issues[] }  // POST /logic/check; 逻辑检查
  stateExtract(data) -> { entity_changes[], relation_changes[] }  // POST /state/extract; 状态提取
  stateCommit(data) -> { success, applied_changes }  // POST /state/commit; 提交状态变更
}
```

### 3.13 递归反馈 API (`api/feedback.ts`)

```typescript
export const feedbackApi = {
  feedbackLoop(sceneContext, rounds) -> { report: FeedbackReport | null, updated_context }  // POST /simulation/feedback; 递归反馈检测与修正
}
```

### 3.14 审核管理 API (`api/review.ts`)

```typescript
export const reviewApi = {
  reviewScene(sceneId, status, comment?) -> SceneView  // PUT /scenes/{id}/review; 审核场景
  reviewChapter(chapterId, status, comment?) -> Chapter  // PUT /chapters/{id}/review; 审核章节
}
```

---

## 4. 状态管理 (Pinia Stores)

### 4.1 项目状态 (`stores/project.ts`)

```typescript
export const useProjectStore = defineStore('project', () => {
  // State
  currentRootId: Ref<string | null>      // 当前项目 ID
  currentBranchId: Ref<string>           // 当前分支 ID, 默认 'main'
  branches: Ref<string[]>                // 分支列表
  loading: Ref<boolean>

  // Getters
  hasProject: ComputedRef<boolean>       // !!currentRootId

  // Actions
  loadBranches() -> void                 // 调用 branchApi.listBranches
  switchBranch(branchId) -> void         // 调用 branchApi.switchBranch
  createBranch(branchId) -> void         // 调用 branchApi.createBranch
  setProject(rootId, branchId?) -> void  // 设置当前项目
  clearProject() -> void                 // 清空项目状态
})
```

### 4.2 雪花流程状态 (`stores/snowflake.ts`)

```typescript
export type SnowflakeStep = 1 | 2 | 3 | 4 | 5 | 6;  // 6 = 锚点生成

export const useSnowflakeStore = defineStore('snowflake', () => {
  // State
  currentStep: Ref<SnowflakeStep>        // 当前步骤
  loading: Ref<boolean>
  error: Ref<string | null>
  idea: Ref<string>                      // Step 1: 用户想法
  loglineOptions: Ref<string[]>          // Step 1: 生成的 logline 选项
  selectedLogline: Ref<string | null>    // Step 1: 选中的 logline
  root: Ref<SnowflakeRoot | null>        // Step 2: 故事结构
  characters: Ref<CharacterSheet[]>      // Step 3: 角色列表
  scenes: Ref<SceneNode[]>               // Step 4: 场景列表
  rootId: Ref<string | null>             // Step 4: 创建的 root_id
  acts: Ref<Act[]>                       // Step 5: 幕列表
  chapters: Ref<Chapter[]>               // Step 5: 章列表
  anchors: Ref<StoryAnchor[]>            // Step 6: 锚点列表

  // Getters
  canProceed: ComputedRef<boolean>       // 根据 currentStep 判断是否可进入下一步
  progress: ComputedRef<number>          // (currentStep / 6) * 100

  // Actions
  executeStep1() -> void                 // 调用 snowflakeApi.generateLoglines
  executeStep2() -> void                 // 调用 snowflakeApi.generateStructure
  executeStep3() -> void                 // 调用 snowflakeApi.generateCharacters
  executeStep4() -> void                 // 调用 snowflakeApi.generateScenes
  executeStep5() -> void                 // 调用 generateActs + generateChapters
  executeStep6(branchId?) -> void        // 调用 anchorApi.generateAnchors
  selectLogline(logline) -> void         // 选择 logline
  reset() -> void                        // 重置所有状态
})
```

### 4.3 推演状态 (`stores/simulation.ts`)

```typescript
export const useSimulationStore = defineStore('simulation', () => {
  // State
  loading: Ref<boolean>
  running: Ref<boolean>                  // 自动推演运行中
  currentSceneId: Ref<string | null>     // 当前场景 ID
  currentRoundIndex: Ref<number>         // 当前回合索引
  maxRounds: Ref<number>                 // 最大回合数, 默认 10
  rounds: Ref<SimulationRoundResult[]>   // 推演回合列表
  agentStates: Ref<Map<string, CharacterAgentState>>  // 角色代理状态
  lastConvergenceCheck: Ref<ConvergenceCheck | null>  // 最近收敛检查
  renderedContent: Ref<string>           // 渲染后的正文

  // Getters
  currentRound: ComputedRef<SimulationRoundResult | null>  // rounds[currentRoundIndex]
  totalRounds: ComputedRef<number>       // rounds.length
  averageInfoGain: ComputedRef<number>   // 平均信息增量
  isStagnant: ComputedRef<boolean>       // 最近 3 轮 info_gain < 0.2

  // Actions
  loadAgentStates(entityIds, branchId) -> void  // 批量加载代理状态
  runSingleRound(sceneContext) -> SimulationRoundResult  // 单回合推演
  runFullScene(sceneContext) -> { content }  // 完整场景推演
  checkConvergence(worldState, nextAnchor) -> ConvergenceCheck  // 收敛检查
  renderScene(scene) -> string           // 智能渲染
  setCurrentScene(sceneId) -> void       // 设置当前场景
  goToRound(index) -> void               // 跳转到指定回合
  reset() -> void                        // 重置状态
})
```

### 4.4 世界观状态 (`stores/world.ts`)

```typescript
export const useWorldStore = defineStore('world', () => {
  // State
  loading: Ref<boolean>
  entities: Ref<EntityView[]>            // 实体列表
  relations: Ref<EntityRelationView[]>   // 关系列表
  anchors: Ref<StoryAnchor[]>            // 锚点列表
  subplots: Ref<Subplot[]>               // 支线列表

  // Getters
  characters: ComputedRef<EntityView[]>  // entity_type === 'Character'
  locations: ComputedRef<EntityView[]>   // entity_type === 'Location'
  items: ComputedRef<EntityView[]>       // entity_type === 'Item'
  achievedAnchors: ComputedRef<StoryAnchor[]>  // achieved === true
  pendingAnchors: ComputedRef<StoryAnchor[]>   // achieved === false
  nextAnchor: ComputedRef<StoryAnchor | null>  // pendingAnchors 按 sequence 排序后第一个
  anchorProgress: ComputedRef<number>    // (achievedAnchors.length / anchors.length) * 100

  // Actions
  loadEntities(rootId, branchId) -> void  // 调用 entityApi.listEntities
  loadAnchors(rootId, branchId) -> void   // 调用 anchorApi.listAnchors
  createEntity(rootId, branchId, data) -> EntityView  // 调用 entityApi.createEntity
  createRelation(rootId, branchId, data) -> EntityRelationView  // 调用 entityApi.upsertRelation
  updateAnchor(id, data) -> StoryAnchor   // 调用 anchorApi.updateAnchor
  reset() -> void                         // 重置状态
})
```

---

## 5. 实施步骤 (Implementation Steps)

### Phase 1: 项目初始化

**Step 1.1: 创建 Vite 项目**
- **Action**: `Create project/frontend/`
- **Cmd**: `npm create vite@latest frontend -- --template vue-ts && cd frontend && npm install`

**Step 1.2: 安装依赖**
- **Action**: `Mod package.json`
- **Cmd**: `npm install element-plus @element-plus/icons-vue pinia vue-router@4 axios @vueuse/core dayjs lodash-es && npm install -D sass unplugin-auto-import unplugin-vue-components`

**Step 1.3: 配置 Vite**
- **Action**: `Mod vite.config.ts`
- **Spec**: 配置 AutoImport + Components (ElementPlusResolver); alias '@' -> 'src'; proxy '/api' -> 'http://localhost:8000'

**Step 1.4: 配置路由**
- **Action**: `Create src/router/index.ts`
- **Spec**: 6 条路由: / (Home), /snowflake, /simulation/:sceneId?, /editor/:sceneId?, /world, /settings

---

### Phase 2: 雪花流程页面

**Step 2.1: 雪花流程主页面**
- **Action**: `Create src/views/SnowflakeView.vue`
- **Spec**: el-steps 6 步指示器; 根据 store.currentStep 切换 Step1-6Panel; 上一步/下一步按钮
- **Test**:
  - Case: 输入想法 -> 生成 10 个 logline
  - Case: 选择 logline -> 生成故事结构
  - Case: 完成 Step 6 -> 跳转到编辑器

**Step 2.2: Step1 想法输入面板**
- **Action**: `Create src/components/snowflake/Step1Panel.vue`
- **Spec**: el-input textarea 输入想法; 生成按钮调用 store.executeStep1; el-radio-group 展示 loglineOptions

**Step 2.3: 角色卡片组件**
- **Action**: `Create src/components/snowflake/CharacterCard.vue`
- **Spec**: el-card 展示 name, ambition, conflict, epiphany, voice_dna; el-tag 显示 arc_status

---

### Phase 3: 推演控制台页面

**Step 3.1: 推演主页面**
- **Action**: `Create src/views/SimulationView.vue`
- **Spec**: 三栏布局 (6:12:6); 左侧 AgentStatePanel 列表; 中间 ActionTimeline + ArbitrationResult; 右侧 ConvergenceIndicator + 渲染结果

**Step 3.2: 角色代理状态面板**
- **Action**: `Create src/components/simulation/AgentStatePanel.vue`
- **Spec**: el-card 展示角色头像+名称; el-collapse 展示 beliefs/desires/intentions; desires 按 priority 显示 el-tag

**Step 3.3: 行动时间线组件**
- **Action**: `Create src/components/simulation/ActionTimeline.vue`
- **Spec**: el-timeline 展示回合列表; 每回合显示 info_gain 标签 + agent_actions 列表 + conflicts_resolved 警告

**Step 3.4: 收敛指示器组件**
- **Action**: `Create src/components/simulation/ConvergenceIndicator.vue`
- **Spec**: el-progress 显示 (1-distance)*100; el-descriptions 显示目标锚点/距离/平均信息增量; el-alert 显示停滞警告或收敛建议

---

### Phase 4: 场景编辑器页面

**Step 4.1: 编辑器主页面**
- **Action**: `Create src/views/EditorView.vue`
- **Spec**: 三栏布局 (6:12:6); 左侧 el-tree 场景列表; 中间 el-tabs (大纲/正文/推演日志); 右侧 SceneContextPanel

---

### Phase 5: 世界观管理页面

**Step 5.1: 世界观主页面**
- **Action**: `Create src/views/WorldView.vue`
- **Spec**: el-tabs 4 个标签页 (实体/关系图谱/锚点/支线); 实体页三栏展示角色/地点/物品; 关系图谱使用 RelationGraph 组件

**Step 5.2: 锚点时间线组件**
- **Action**: `Create src/components/world/AnchorTimeline.vue`
- **Spec**: el-progress 显示锚点进度; el-timeline 展示锚点列表; 每个锚点显示 constraint_type/anchor_type/sequence/description/required_conditions

---

## 6. 测试规范

### 6.1 测试文件清单

```
tests/
├── unit/
│   ├── stores/
│   │   ├── snowflake.spec.ts
│   │   ├── simulation.spec.ts
│   │   └── world.spec.ts
│   ├── components/
│   │   ├── CharacterCard.spec.ts
│   │   ├── ActionTimeline.spec.ts
│   │   └── AnchorTimeline.spec.ts
│   └── api/
│       ├── snowflake.spec.ts
│       └── simulation.spec.ts
├── integration/
│   ├── SnowflakeFlow.spec.ts
│   └── SimulationFlow.spec.ts
└── e2e/
    └── full-workflow.spec.ts
```

### 6.2 核心测试用例

**测试 1: 雪花流程状态管理**
```
Given: store.idea = "一个失忆的杀手"
When: store.executeStep1()
Then: store.loglineOptions.length === 10
```

**测试 2: 推演回合执行**
```
Given: store.currentSceneId = "scene:1"
When: store.runSingleRound(sceneContext)
Then: store.rounds.length === 1 && store.currentRound.info_gain >= 0
```

**测试 3: 锚点进度计算**
```
Given: anchors = [{ achieved: true }, { achieved: false }, { achieved: true }]
When: computed anchorProgress
Then: anchorProgress === 66.67
```

### 6.3 测试命令

```bash
# 运行单元测试
npm run test:unit

# 运行集成测试
npm run test:integration

# 运行 E2E 测试
npm run test:e2e

# 运行覆盖率报告
npm run test:coverage
```

---

## 7. 部署配置

### 7.1 环境变量

```bash
# .env.development
VITE_API_BASE_URL=http://localhost:8000/api/v1

# .env.production
VITE_API_BASE_URL=/api/v1
```

### 7.2 构建命令

```bash
# 开发模式
npm run dev

# 生产构建
npm run build

# 预览生产构建
npm run preview
```

### 7.3 Nginx 配置示例

```nginx
server {
    listen 80;
    server_name ainovel.example.com;

    root /var/www/ainovel/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 附录 A: 页面路由表

| 路由 | 页面 | 功能 |
|------|------|------|
| `/` | HomeView | 项目列表/创建入口 |
| `/snowflake` | SnowflakeView | 雪花流程向导 (Step 1-6) |
| `/simulation/:sceneId?` | SimulationView | 推演控制台 |
| `/editor/:sceneId?` | EditorView | 场景编辑器 |
| `/world` | WorldView | 世界观管理 (实体/关系/锚点/支线) |
| `/settings` | SettingsView | 系统设置 |

---

## 附录 B: 组件清单 (32 个)

| 类别 | 组件 | 功能 |
|------|------|------|
| common | AppHeader | 顶部导航栏 |
| common | AppSidebar | 侧边栏菜单 |
| common | LoadingOverlay | 加载遮罩 |
| common | EmptyState | 空状态占位 |
| snowflake | StepIndicator | 步骤指示器 |
| snowflake | Step1Panel | 想法输入面板 |
| snowflake | Step2Panel | 结构展示面板 |
| snowflake | Step3Panel | 角色列表面板 |
| snowflake | Step4Panel | 场景列表面板 |
| snowflake | Step5Panel | 幕章结构面板 |
| snowflake | Step6Panel | 锚点生成面板 |
| snowflake | LoglineSelector | Logline 选择器 |
| snowflake | CharacterCard | 角色卡片 |
| snowflake | SceneCard | 场景卡片 |
| snowflake | ActCard | 幕卡片 |
| snowflake | ChapterCard | 章卡片 |
| simulation | AgentStatePanel | 代理状态面板 |
| simulation | ActionTimeline | 行动时间线 |
| simulation | ArbitrationResult | 裁决结果展示 |
| simulation | ConvergenceIndicator | 收敛指示器 |
| simulation | RoundPlayer | 回合播放器 |
| editor | SceneEditor | 场景编辑器 |
| editor | ContentRenderer | 内容渲染器 |
| editor | VersionDiff | 版本对比 |
| editor | MarkdownPreview | Markdown 预览 |
| editor | SimulationLogs | 推演日志查看 |
| editor | SceneContextPanel | 场景上下文面板 |
| world | EntityList | 实体列表 |
| world | RelationGraph | 关系图谱 |
| world | AnchorTimeline | 锚点时间线 |
| world | SubplotPanel | 支线管理面板 |

---

## 附录 C: API 端点映射 (62 个)

### C.1 雪花流程 API (7 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `snowflakeApi.generateLoglines` | POST /api/v1/snowflake/step1 | 生成 logline 选项 |
| `snowflakeApi.generateStructure` | POST /api/v1/snowflake/step2 | 生成故事结构 |
| `snowflakeApi.generateCharacters` | POST /api/v1/snowflake/step3 | 生成角色小传 |
| `snowflakeApi.generateScenes` | POST /api/v1/snowflake/step4 | 生成场景骨架 |
| `snowflakeApi.generateActs` | POST /api/v1/snowflake/step5a | 生成幕结构 |
| `snowflakeApi.generateChapters` | POST /api/v1/snowflake/step5b | 生成章结构 |
| `snowflakeApi.renderChapter` | POST /api/v1/chapters/{id}/render | 渲染章节内容 (返回 quality_scores) |

### C.2 锚点管理 API (4 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `anchorApi.generateAnchors` | POST /api/v1/roots/{id}/anchors | 生成锚点 |
| `anchorApi.listAnchors` | GET /api/v1/roots/{id}/anchors | 列出锚点 |
| `anchorApi.updateAnchor` | PUT /api/v1/anchors/{id} | 更新锚点 |
| `anchorApi.checkAnchor` | POST /api/v1/anchors/{id}/check | 检查可达性 |

### C.3 角色代理 API (4 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `agentApi.initAgent` | POST /api/v1/entities/{id}/agent/init | 初始化代理 |
| `agentApi.getAgentState` | GET /api/v1/entities/{id}/agent/state | 获取代理状态 |
| `agentApi.updateDesires` | PUT /api/v1/entities/{id}/agent/desires | 更新欲望 |
| `agentApi.decide` | POST /api/v1/entities/{id}/agent/decide | 触发决策 |

### C.4 DM 裁决 API (4 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `dmApi.arbitrate` | POST /api/v1/dm/arbitrate | DM 裁决 |
| `dmApi.checkConvergence` | POST /api/v1/dm/converge | 收敛检查 |
| `dmApi.intervene` | POST /api/v1/dm/intervene | DM 干预 |
| `dmApi.replan` | POST /api/v1/dm/replan | 动态补路 |

### C.5 推演引擎 API (5 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `simulationApi.runRound` | POST /api/v1/simulation/round | 单回合推演 |
| `simulationApi.runScene` | POST /api/v1/simulation/scene | 场景推演 |
| `simulationApi.getLogs` | GET /api/v1/simulation/logs/{id} | 获取日志 |
| `simulationApi.renderScene` | POST /api/v1/render/scene | 智能渲染 |
| `simulationApi.feedbackLoop` | POST /api/v1/simulation/feedback | 递归反馈 |

### C.6 分支管理 API (9 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `branchApi.createBranch` | POST /api/v1/roots/{id}/branches | 创建分支 |
| `branchApi.listBranches` | GET /api/v1/roots/{id}/branches | 列出分支 |
| `branchApi.switchBranch` | POST /api/v1/roots/{id}/branches/{bid}/switch | 切换分支 |
| `branchApi.mergeBranch` | POST /api/v1/roots/{id}/branches/{bid}/merge | 合并分支 |
| `branchApi.revertBranch` | POST /api/v1/roots/{id}/branches/{bid}/revert | 回滚分支 |
| `branchApi.forkFromCommit` | POST /api/v1/roots/{id}/branches/fork_from_commit | 从提交创建分支 |
| `branchApi.forkFromScene` | POST /api/v1/roots/{id}/branches/fork_from_scene | 从场景创建分支 |
| `branchApi.resetBranch` | POST /api/v1/roots/{id}/branches/{bid}/reset | 重置分支 |
| `branchApi.getBranchHistory` | GET /api/v1/roots/{id}/branches/{bid}/history | 获取分支历史 |

### C.7 场景管理 API (9 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `sceneApi.createScene` | POST /api/v1/roots/{id}/scene_origins | 创建场景 |
| `sceneApi.deleteScene` | POST /api/v1/roots/{id}/scenes/{sid}/delete | 删除场景 |
| `sceneApi.completeScene` | POST /api/v1/scenes/{id}/complete | 完成场景 |
| `sceneApi.completeOrchestrated` | POST /api/v1/scenes/{id}/complete/orchestrated | 编排完成场景 |
| `sceneApi.renderScene` | POST /api/v1/scenes/{id}/render | 渲染场景 (返回 quality_scores) |
| `sceneApi.getContext` | GET /api/v1/scenes/{id}/context | 获取场景上下文 |
| `sceneApi.diffScene` | GET /api/v1/scenes/{id}/diff | 比较场景版本 |
| `sceneApi.markDirty` | POST /api/v1/scenes/{id}/dirty | 标记场景为脏 |
| `sceneApi.reviewScene` | PUT /api/v1/scenes/{id}/review | 审核场景 |

### C.8 中观层 API (2 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `snowflakeApi.listActs` | GET /api/v1/roots/{id}/acts | 获取幕列表 |
| `snowflakeApi.listChapters` | GET /api/v1/acts/{id}/chapters | 获取章列表 |

### C.9 实体管理 API (3 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `entityApi.createEntity` | POST /api/v1/roots/{id}/entities | 创建实体 |
| `entityApi.listEntities` | GET /api/v1/roots/{id}/entities | 列出实体 |
| `entityApi.upsertRelation` | POST /api/v1/roots/{id}/relations | 创建/更新关系 |

### C.10 支线管理 API (3 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `subplotApi.createSubplot` | POST /api/v1/roots/{id}/subplots | 创建支线 |
| `subplotApi.listSubplots` | GET /api/v1/roots/{id}/subplots | 列出支线 |
| `subplotApi.resolveSubplot` | POST /api/v1/subplots/{id}/resolve | 解决支线 |

### C.11 查询 API (2 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `branchApi.getRootSnapshot` | GET /api/v1/roots/{id} | 获取根节点快照 |
| `sceneApi.listDirtyScenes` | GET /api/v1/roots/{id}/dirty_scenes | 列出脏场景 |

### C.12 提交 API (2 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `commitApi.commitScene` | POST /api/v1/roots/{id}/branches/{bid}/commit | 提交场景 |
| `commitApi.gcCommits` | POST /api/v1/commits/gc | 垃圾回收 |

### C.13 LLM 与逻辑检查 API (4 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `llmApi.toponeGenerate` | POST /api/v1/llm/topone/generate | 调用 TopOne |
| `llmApi.logicCheck` | POST /api/v1/logic/check | 逻辑检查 |
| `llmApi.stateExtract` | POST /api/v1/state/extract | 状态提取 |
| `llmApi.stateCommit` | POST /api/v1/state/commit | 提交状态 |

### C.14 递归反馈 API (1 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `feedbackApi.feedbackLoop` | POST /api/v1/simulation/feedback | 递归反馈检测与修正 |

### C.15 审核管理 API (2 个)

| 前端 API 函数 | 后端端点 | 功能 |
|---------------|----------|------|
| `reviewApi.reviewScene` | PUT /api/v1/scenes/{id}/review | 审核场景 |
| `reviewApi.reviewChapter` | PUT /api/v1/chapters/{id}/review | 审核章节 |

---

**文档结束**

