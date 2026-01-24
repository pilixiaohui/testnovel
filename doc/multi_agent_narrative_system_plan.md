# 多智能体叙事系统实施协议 v3.1 (Compact Edition)

**版本**: 3.1 | **日期**: 2026-01-24 | **性质**: AI-Native Implementation Protocol

---

## 0. Meta (约束与栈)

**Stack**: Python 3.11+ | FastAPI >= 0.111.0 | Pydantic >= 2.7.0 | Memgraph | GQLAlchemy >= 1.4.0

**Whitelist**: 现有 pyproject.toml 依赖 + asyncio/typing/enum/uuid/datetime (标准库)

**No-Go**:
- 禁止引入新 LLM SDK (必须通过 ToponeGateway)
- 禁止引入 langchain/llamaindex
- 禁止破坏现有 32 个 API 端点

**Constraints**:
- 每个 Step 必须可独立测试
- Step N 使用的类型必须在 Step N-1 前定义
- 禁止模糊描述，必须用伪代码/IF-ELSE

**Path**: `/home/zxh/ainovel_v3/project/backend/`

---

## 1. 现状诊断

### 1.1 问题清单

| 问题 | 表现 | 影响 |
|------|------|------|
| 确定性过强 | 大纲生成后走向锁死 | 无涌现性 |
| 角色无自主性 | 角色只执行大纲 | 角色扁平 |
| 缺少中观层 | 50-100场景扁平列表 | 节奏失控 |
| 无递归反馈 | 单向流水线 | 僵化 |
| 无支线管理 | 只有主线 | 结构单一 |

### 1.2 雪花写作法缺口

| 层级 | 状态 |
|------|------|
| Step 1-4 | ✅ 已实现 |
| Step 5 幕纲/章纲 | ❌ 缺失 |
| Step 6 场景细化 | ⚠️ 仅render |
| Step 7 支线编织 | ❌ 缺失 |
| Step 8 递归反馈 | ❌ 缺失 |

### 1.3 目标转变

| 维度 | 当前 | 目标 |
|------|------|------|
| 大纲 | 完整大纲 (50-100场景) | 稀疏锚点 (10-15个) |
| 角色 | 执行大纲的工具人 | BDI 自主决策 Agent |
| 世界 | 被动记录 | DM 主动裁决 |
| 生成 | 填空渲染 | 推演即生成 |

---

## 2. Topology (拓扑)

### 2.1 新增文件

```
app/storage/schema.py              # [Mod] +6 节点类型
app/models.py                      # [Mod] +18 Pydantic 模型
app/services/character_agent.py    # [New] BDI 决策引擎
app/services/world_master.py       # [New] DM 裁决引擎 + 动态补路
app/services/simulation_engine.py  # [New] 推演引擎
app/services/smart_renderer.py     # [New] 智能渲染管线
app/services/feedback_detector.py  # [New] 反馈检测
app/llm/prompts/character_agent.py # [New] 角色 Prompt
app/llm/prompts/world_master.py    # [New] DM Prompt
app/llm/prompts/renderer.py        # [New] 渲染 Prompt
app/main.py                        # [Mod] +22 API 端点
```

### 2.2 新增测试

```
tests/unit/test_schema_act_chapter.py
tests/unit/test_models_bdi.py
tests/unit/test_character_agent.py
tests/unit/test_world_master.py
tests/unit/test_route_replanner.py
tests/unit/test_smart_renderer.py
tests/integration/test_act_chapter_storage.py
tests/integration/test_anchor_storage.py
tests/integration/test_simulation_flow.py
tests/integration/test_pacing_control.py
```

---

## 3. Contracts (数据契约)

### 3.1 新增节点 (6个)

```python
# schema.py - 使用 GQLAlchemy Node

class Act(Node):
    id: str = Field(index=True, unique=True)  # {root_id}:act:{seq}
    root_id: str = Field(index=True)
    sequence: int
    title: str
    purpose: str
    tone: str  # "calm"|"tense"|"climax"|"resolution"

class Chapter(Node):
    id: str = Field(index=True, unique=True)  # {act_id}:ch:{seq}
    act_id: str = Field(index=True)
    sequence: int
    title: str
    focus: str
    pov_character_id: Optional[str] = None

class StoryAnchor(Node):
    id: str = Field(index=True, unique=True)  # {root_id}:anchor:{seq}
    root_id: str = Field(index=True)
    branch_id: str = Field(index=True)
    sequence: int
    anchor_type: str  # "inciting_incident"|"midpoint"|"climax"|"resolution"|...
    description: str
    constraint_type: str  # "hard"|"soft"|"flexible"
    required_conditions: str  # JSON
    deadline_scene: Optional[int] = None
    achieved: bool = False

class CharacterAgentState(Node):
    id: str = Field(index=True, unique=True)  # agent:{char_id}
    character_id: str = Field(index=True)
    branch_id: str = Field(index=True)
    beliefs: str   # JSON
    desires: str   # JSON
    intentions: str  # JSON
    memory: str    # JSON
    private_knowledge: str  # JSON
    last_updated_scene: int
    version: int = 1

class SimulationLog(Node):
    id: str = Field(index=True, unique=True)  # sim:{scene_id}:round:{n}
    scene_version_id: str = Field(index=True)
    round_number: int
    agent_actions: str  # JSON
    dm_arbitration: str  # JSON
    narrative_events: str  # JSON
    sensory_seeds: str  # JSON - 感官细节种子 (环境/情绪/氛围)
    convergence_score: float
    drama_score: float
    info_gain: float  # 信息增量 (0-1)
    stagnation_count: int = 0  # 连续停滞回合数

class Subplot(Node):
    id: str = Field(index=True, unique=True)
    root_id: str = Field(index=True)
    branch_id: str = Field(index=True)
    title: str
    subplot_type: str  # "romance"|"mystery"|"rivalry"|...
    protagonist_id: str
    central_conflict: str
    status: str = "dormant"  # "dormant"|"active"|"resolved"
```

### 3.2 新增边 (4个)

```python
class CONTAINS_CHAPTER(Relationship): pass  # Act -> Chapter
class CONTAINS_SCENE(Relationship): pass    # Chapter -> SceneOrigin
class DEPENDS_ON(Relationship): pass        # Anchor -> Anchor
class AGENT_OF(Relationship): pass          # AgentState -> Entity
```

### 3.3 现有节点修改

```python
# SceneOrigin 新增
chapter_id: Optional[str] = None
is_skeleton: bool = False

# SceneVersion 新增
simulation_log_id: Optional[str] = None
is_simulated: bool = False

# Entity 新增 (Character类型)
has_agent: bool = False
agent_state_id: Optional[str] = None
```

### 3.4 核心 Pydantic 模型

```python
# models.py

class Desire(BaseModel):
    id: str
    type: Literal["short_term", "long_term", "reactive"]
    description: str
    priority: int = Field(ge=1, le=10)
    satisfaction_condition: str
    created_at_scene: int
    expires_at_scene: Optional[int] = None

class Intention(BaseModel):
    id: str
    desire_id: str
    action_type: Literal["attack", "flee", "negotiate", "investigate", "wait", "other"]
    target: str
    expected_outcome: str
    risk_assessment: float = Field(ge=0, le=1)

class AgentAction(BaseModel):
    agent_id: str
    internal_thought: str
    action_type: str
    action_target: str
    dialogue: Optional[str] = None
    action_description: str

class ActionResult(BaseModel):
    action_id: str
    agent_id: str
    success: Literal["success", "partial", "failure"]
    reason: str
    actual_outcome: str

class DMArbitration(BaseModel):
    round_id: str
    action_results: List[ActionResult]
    conflicts_resolved: List[Dict] = []
    environment_changes: List[Dict] = []

class ConvergenceCheck(BaseModel):
    next_anchor_id: str
    distance: float = Field(ge=0, le=1)  # 0=达成, 1=偏离
    convergence_needed: bool
    suggested_action: Optional[str] = None

class SimulationRoundResult(BaseModel):
    round_id: str
    agent_actions: List[AgentAction]
    dm_arbitration: DMArbitration
    narrative_events: List[Dict]
    sensory_seeds: List[Dict]  # 感官细节种子
    convergence_score: float
    drama_score: float
    info_gain: float  # 信息增量
    stagnation_count: int

class ReplanRequest(BaseModel):
    current_scene_id: str
    target_anchor_id: str
    world_state_snapshot: Dict
    failed_conditions: List[str]

class ReplanResult(BaseModel):
    success: bool
    new_chapters: List[Dict]  # 插入的过渡章节
    modified_anchor: Optional[Dict]  # 若锚点被软化/替换
    reason: str
```

---

## 4. Implementation Steps

### Phase 1: 中观扩充层 (Act/Chapter)

**Step 1.1: 定义 Act/Chapter 节点**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 Act, Chapter 类 (见 3.1)
- **Test**: `pytest tests/unit/test_schema_act_chapter.py`
  - Case: Act(id="r1:act:1", sequence=1) -> assert id正确
  - Case: Chapter(act_id="r1:act:1") -> assert 关联正确

**Step 1.2: 定义边类型**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 CONTAINS_CHAPTER, CONTAINS_SCENE
- **Test**: 同上

**Step 1.3: 扩展 SceneOrigin**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 chapter_id, is_skeleton 字段; ⛔ 禁止删除现有字段
- **Test**: Case: SceneOrigin(无新字段) -> 默认值正确 (向后兼容)

**Step 1.4: 实现存储方法**
- **Action**: `Mod app/storage/memgraph_storage.py`
- **Spec**:
  ```
  create_act(root_id, seq, title, purpose, tone) -> dict
    1. id = f"{root_id}:act:{seq}"
    2. IF exists THEN raise KeyError
    3. CREATE node, RETURN props

  list_acts(root_id) -> list[dict]
    MATCH (a:Act {root_id}) RETURN a ORDER BY a.sequence

  link_scene_to_chapter(scene_id, chapter_id) -> None
    1. IF scene not exists THEN raise KeyError
    2. IF chapter not exists THEN raise KeyError
    3. MERGE edge, SET scene.chapter_id
  ```
- **Test**: `pytest tests/integration/test_act_chapter_storage.py`
  - Case: create 3 acts -> list returns 3, ordered by seq
  - Case: link scene -> scene.chapter_id updated

**Step 1.5: 实现 Step5a/5b API**
- **Action**: `Mod app/main.py`
- **Spec**:
  ```
  POST /api/v1/snowflake/step5a
    1. GET Root, Characters
    2. LLM generate 3-5 Acts
    3. storage.create_act() for each
    4. RETURN acts

  POST /api/v1/snowflake/step5b
    1. GET Acts
    2. FOR each Act: LLM generate 3-7 Chapters
    3. storage.create_chapter() for each
    4. RETURN chapters
  ```
- **Test**: `pytest tests/integration/test_snowflake_step5.py`
  - Case: step5a -> 3-5 acts created
  - Case: step5b -> >= 9 chapters created

---

### Phase 2: 稀疏锚点系统

**Step 2.1: 定义 StoryAnchor 节点**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 StoryAnchor 类 (见 3.1)
- **Test**: `pytest tests/unit/test_schema_anchor.py`

**Step 2.2: 定义边类型**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 DEPENDS_ON, TRIGGERED_AT
- **Test**: 同上

**Step 2.3: 实现锚点存储方法**
- **Action**: `Mod app/storage/memgraph_storage.py`
- **Spec**:
  ```
  create_anchor(root_id, branch_id, seq, type, desc, constraint, conditions) -> dict
    1. VALIDATE type IN ANCHOR_TYPES
    2. VALIDATE constraint IN ["hard","soft","flexible"]
    3. id = f"{root_id}:anchor:{seq}"
    4. CREATE node

  mark_anchor_achieved(anchor_id, scene_version_id) -> dict
    1. IF already achieved THEN raise ValueError
    2. SET achieved=true, achieved_at_scene
    3. CREATE TRIGGERED_AT edge

  get_next_unachieved_anchor(root_id, branch_id) -> dict|None
    MATCH (a:StoryAnchor {achieved:false}) RETURN a ORDER BY seq LIMIT 1
  ```
- **Test**: `pytest tests/integration/test_anchor_storage.py`

**Step 2.4: 实现锚点生成**
- **Action**: `Mod app/services/llm_engine.py`
- **Spec**:
  ```
  generate_story_anchors(root, characters, acts) -> list[dict]
    1. Prompt: 基于 logline/theme/acts 生成 10-15 锚点
    2. VALIDATE: 必须包含 inciting_incident, midpoint, climax, resolution
    3. IF invalid THEN retry once
  ```
- **Test**: `pytest tests/unit/test_anchor_generation.py`

**Step 2.5: 实现锚点 API**
- **Action**: `Mod app/main.py`
- **Spec**:
  ```
  POST /api/v1/roots/{root_id}/anchors  # 生成锚点
  GET /api/v1/roots/{root_id}/anchors   # 列出锚点
  PUT /api/v1/anchors/{id}              # 更新锚点
  POST /api/v1/anchors/{id}/check       # 检查可达性
  ```
- **Test**: `pytest tests/integration/test_anchor_api.py`

---

### Phase 3: 角色代理系统 (BDI)

**Step 3.1: 定义 CharacterAgentState 节点**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 CharacterAgentState, AGENT_OF (见 3.1, 3.2)
- **Test**: `pytest tests/unit/test_schema_agent.py`

**Step 3.2: 扩展 Entity 节点**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 has_agent, agent_state_id; ⛔ 禁止删除现有字段
- **Test**: Case: Entity(无新字段) -> 默认值正确

**Step 3.3: 定义 BDI 模型**
- **Action**: `Mod app/models.py`
- **Spec**: 添加 Desire, Intention, AgentAction 等 (见 3.4)
- **Test**: `pytest tests/unit/test_models_bdi.py`
  - Case: Desire(priority=11) -> ValidationError
  - Case: AgentAction(dialogue=None) -> valid

**Step 3.4: 实现代理存储方法**
- **Action**: `Mod app/storage/memgraph_storage.py`
- **Spec**:
  ```
  init_character_agent(char_id, branch_id, initial_desires) -> dict
    1. IF char not exists THEN raise KeyError
    2. IF agent exists THEN raise ValueError
    3. CREATE AgentState node
    4. CREATE AGENT_OF edge
    5. UPDATE Entity: has_agent=true

  update_agent_beliefs(agent_id, beliefs_patch) -> dict
    1. GET current beliefs (JSON)
    2. DEEP MERGE patch
    3. UPDATE node, version++

  add_agent_memory(agent_id, entry) -> dict
    1. GET memory list
    2. APPEND entry
    3. IF len > 100 THEN keep top 80 by importance (遗忘)
  ```
- **Test**: `pytest tests/integration/test_agent_storage.py`

**Step 3.5: 实现 BDI 决策引擎**
- **Action**: `Create app/services/character_agent.py`
- **Spec**:
  ```python
  class CharacterAgentEngine:
      def __init__(self, storage, llm): ...

      async def perceive(agent_id, scene_context) -> dict:
          # 更新 beliefs: world.location, others.{id}.state
          # RETURN updated beliefs

      async def deliberate(agent_id) -> list[Intention]:
          # 1. Filter valid desires (not expired)
          # 2. Sort by priority DESC
          # 3. FOR top 3: LLM generate intention
          # RETURN intentions

      async def act(agent_id, scene_context) -> AgentAction:
          # 1. GET intentions
          # 2. IF empty THEN return wait action
          # 3. Check preconditions
          # 4. LLM generate action
          # RETURN action

      async def decide(agent_id, scene_context) -> AgentAction:
          await self.perceive(...)
          await self.deliberate(...)
          return await self.act(...)
  ```
- **Test**: `pytest tests/unit/test_character_agent.py`
  - Case: perceive -> beliefs updated
  - Case: decide -> returns valid AgentAction

**Step 3.6: 实现角色 Prompt**
- **Action**: `Create app/llm/prompts/character_agent.py`
- **Spec**: PERCEIVE_PROMPT, DELIBERATE_PROMPT, ACT_PROMPT 模板
- **Test**: `pytest tests/unit/test_prompts.py`

**Step 3.7: 实现角色代理 API**
- **Action**: `Mod app/main.py`
- **Spec**:
  ```
  POST /api/v1/entities/{id}/agent/init    # 初始化代理
  GET /api/v1/entities/{id}/agent/state    # 获取状态
  PUT /api/v1/entities/{id}/agent/desires  # 更新欲望
  POST /api/v1/entities/{id}/agent/decide  # 触发决策
  ```
- **Test**: `pytest tests/integration/test_agent_api.py`

---

### Phase 4: 世界代理/DM 系统

**Step 4.1: 定义 DM 模型**
- **Action**: `Mod app/models.py`
- **Spec**: 添加 ActionResult, DMArbitration, ConvergenceCheck 等 (见 3.4)
- **Test**: `pytest tests/unit/test_models_dm.py`

**Step 4.2: 实现 DM 引擎**
- **Action**: `Create app/services/world_master.py`
- **Spec**:
  ```python
  class WorldMasterEngine:
      async def arbitrate(round_id, actions, world_state, rules) -> DMArbitration:
          # 1. detect_conflicts(actions)
          # 2. resolve each conflict
          # 3. check_action_validity for each
          # 4. generate_environment_changes
          # 5. inject_sensory_seeds() - 注入感官细节种子
          # RETURN DMArbitration

      async def detect_conflicts(actions) -> list[tuple]:
          # IF both attack each other THEN conflict
          # IF same target same action THEN conflict

      async def check_action_validity(action, world_state, rules) -> ActionResult:
          # FOR rule in rules: IF violates THEN failure
          # IF power_level mismatch THEN partial
          # ELSE success

      async def check_convergence(world_state, next_anchor) -> ConvergenceCheck:
          # LLM evaluate distance 0-1
          # IF distance > 0.7 THEN convergence_needed

      async def generate_convergence_action(check, world_state) -> ConvergenceAction:
          # distance < 0.5: npc_hint
          # distance < 0.7: environment_pressure
          # distance < 0.9: deus_ex_machina
          # else: trigger replan_route()

      async def inject_sensory_seeds(scene_context) -> list[dict]:
          # 随机注入感官细节种子 (对推演逻辑无影响，但对渲染至关重要)
          # 类型: weather, ambient_sound, character_gesture, object_detail
          # 示例: {"type": "weather", "detail": "窗外突然下起暴雨"}
          # 示例: {"type": "gesture", "char_id": "c1", "detail": "他注意到对方颤抖的手"}

      async def monitor_pacing(rounds: list[SimulationRoundResult]) -> PacingAction:
          # 计算最近 3 轮的 info_gain 平均值
          avg_info_gain = mean([r.info_gain for r in rounds[-3:]])

          # IF avg < 0.2 THEN 触发突发事件打破僵局
          IF avg_info_gain < 0.2:
              RETURN PacingAction(type="inject_incident", reason="stagnation")

          # IF conflict_escalation 连续下降 THEN 强制升级
          IF is_deescalating(rounds[-3:]):
              RETURN PacingAction(type="force_escalation")

          RETURN PacingAction(type="continue")
  ```
- **Test**: `pytest tests/unit/test_world_master.py`
  - Case: detect_conflicts(mutual_attack) -> 1 conflict
  - Case: check_convergence(close) -> distance < 0.5
  - Case: monitor_pacing(stagnant_rounds) -> inject_incident

**Step 4.3: 实现 DM Prompt**
- **Action**: `Create app/llm/prompts/world_master.py`
- **Spec**: ARBITRATION_PROMPT, CONVERGENCE_CHECK_PROMPT 模板
- **Test**: `pytest tests/unit/test_prompts.py`

**Step 4.4: 实现 DM API**
- **Action**: `Mod app/main.py`
- **Spec**:
  ```
  POST /api/v1/dm/arbitrate   # 裁决行动
  POST /api/v1/dm/converge    # 检查收敛
  POST /api/v1/dm/intervene   # 主动干预
  POST /api/v1/dm/replan      # 动态补路
  ```
- **Test**: `pytest tests/integration/test_dm_api.py`

**Step 4.5: 实现动态补路服务 (RouteReplanner)**
- **Action**: `Mod app/services/world_master.py`
- **Spec**:
  ```python
  async def replan_route(current_scene, target_anchor, world_state) -> ReplanResult:
      # 1. 评估当前状态与目标锚点的差距
      gap_analysis = await analyze_gap(world_state, target_anchor.required_conditions)

      # 2. IF gap.recoverable THEN 生成过渡章节
      IF gap.severity < 0.7:
          new_chapters = await generate_bridge_chapters(
              from_state=world_state,
              to_conditions=target_anchor.required_conditions,
              max_chapters=3
          )
          RETURN ReplanResult(success=true, new_chapters=new_chapters)

      # 3. IF anchor is "soft" THEN 软化锚点条件
      IF target_anchor.constraint_type == "soft":
          modified = await soften_anchor(target_anchor, world_state)
          RETURN ReplanResult(success=true, modified_anchor=modified)

      # 4. IF anchor is "flexible" THEN 替换为等效锚点
      IF target_anchor.constraint_type == "flexible":
          replacement = await generate_equivalent_anchor(target_anchor, world_state)
          RETURN ReplanResult(success=true, modified_anchor=replacement)

      # 5. ELSE 标记为不可恢复，需人工介入
      RETURN ReplanResult(success=false, reason="hard_anchor_unreachable")
  ```
- **Test**: `pytest tests/unit/test_route_replanner.py`
  - Case: recoverable_gap -> new_chapters generated
  - Case: soft_anchor_unreachable -> anchor softened
  - Case: hard_anchor_unreachable -> success=false

---

### Phase 5: 推演引擎

**Step 5.1: 定义 SimulationLog 节点**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 SimulationLog 类 (见 3.1)
- **Test**: `pytest tests/unit/test_schema_simulation.py`

**Step 5.2: 扩展 SceneVersion**
- **Action**: `Mod app/storage/schema.py`
- **Spec**: 添加 simulation_log_id, is_simulated
- **Test**: 向后兼容测试

**Step 5.3: 实现推演引擎**
- **Action**: `Create app/services/simulation_engine.py`
- **Spec**:
  ```python
  class SimulationEngine:
      def __init__(self, character_engine, world_master, storage, llm): ...

      async def run_round(scene_context, agents, config) -> SimulationRoundResult:
          # 1. PARALLEL: agent.decide() for each
          # 2. world_master.arbitrate()
          # 3. apply state changes
          # 4. generate narrative events
          # 5. inject sensory_seeds via world_master
          # 6. calculate scores (convergence, drama, info_gain)
          # 7. update stagnation_count
          # RETURN result

      async def run_scene(scene_skeleton, config) -> SceneVersion:
          rounds = []
          FOR i in range(config.max_rounds):
              round = await run_round()
              rounds.append(round)

              # 节奏监控: 检查是否停滞
              pacing = await world_master.monitor_pacing(rounds)
              IF pacing.type == "inject_incident":
                  await inject_breaking_incident(scene_context)
              ELIF pacing.type == "force_escalation":
                  await force_conflict_escalation(scene_context)

              IF should_end_scene(round) THEN break

          # 智能渲染
          content = await smart_render(rounds, scene_skeleton)
          RETURN SceneVersion(is_simulated=true, content=content)

      async def calculate_info_gain(prev_state, curr_state) -> float:
          # 计算信息增量: 新揭示的信息 / 总信息量
          # 包括: 新事实、关系变化、秘密揭露、冲突升级
          # RETURN 0-1 float
  ```
- **Test**: `pytest tests/unit/test_simulation_engine.py`
  - Case: run_round -> returns valid SimulationRoundResult with info_gain
  - Case: run_scene with stagnation -> inject_incident triggered

**Step 5.4: 实现智能渲染管线 (SmartRenderer)**
- **Action**: `Create app/services/smart_renderer.py`
- **Spec**:
  ```python
  class SmartRenderer:
      async def render(rounds: list[SimulationRoundResult], scene: SceneOrigin) -> str:
          # 1. 降噪: 过滤无效尝试和废话
          clean_beats = await extract_narrative_beats(rounds)
          # 过滤规则:
          #   - 移除 action_result.success == "failure" 且无戏剧价值的动作
          #   - 合并连续的 "wait" 动作
          #   - 保留所有对话和关键冲突

          # 2. 收集感官种子
          sensory_details = collect_sensory_seeds(rounds)
          # 按类型分组: weather, gesture, ambient, object

          # 3. 检索风格上下文
          style_context = await retrieval_service.get_style(
              scene_id=scene.id,
              includes=["previous_foreshadowing", "character_voice", "tone"]
          )

          # 4. 渲染正文
          content = await llm.generate_prose(
              beats=clean_beats,
              sensory=sensory_details,
              style=style_context,
              pov=scene.pov_character_id
          )

          # 5. 一致性检查
          IF await check_continuity_errors(content, scene):
              content = await fix_continuity(content)

          RETURN content

      async def extract_narrative_beats(rounds) -> list[NarrativeBeat]:
          # 从推演日志提取叙事节拍
          # NarrativeBeat: {type, actors, action, outcome, emotional_weight}
          # 过滤 info_gain < 0.1 的回合

      async def check_continuity_errors(content, scene) -> bool:
          # 检查: 角色位置、物品状态、时间线、已知信息
  ```
- **Test**: `pytest tests/unit/test_smart_renderer.py`
  - Case: render with stagnant rounds -> filtered output
  - Case: render with sensory seeds -> details included

**Step 5.5: 实现推演 API**
- **Action**: `Mod app/main.py`
- **Spec**:
  ```
  POST /api/v1/simulation/round  # 单回合推演
  POST /api/v1/simulation/scene  # 完整场景推演
  GET /api/v1/simulation/logs/{scene_id}  # 获取日志
  POST /api/v1/render/scene      # 智能渲染
  ```
- **Test**: `pytest tests/integration/test_simulation_api.py`

---

### Phase 6: 支线编织 (可选)

**Step 6.1**: 定义 Subplot 节点
**Step 6.2**: 实现支线存储方法
**Step 6.3**: 实现支线激活/收束逻辑
**Step 6.4**: 实现支线 API

---

### Phase 7: 递归反馈 (可选)

**Step 7.1**: 定义 FeedbackReport 模型
**Step 7.2**: 实现反馈检测器
**Step 7.3**: 实现反馈处理流程
**Step 7.4**: 实现反馈 API

---

## 5. API Summary (新增 ~22 个)

| Method | Path | Function |
|--------|------|----------|
| POST | /api/v1/snowflake/step5a | 生成幕结构 |
| POST | /api/v1/snowflake/step5b | 生成章结构 |
| GET | /api/v1/roots/{id}/acts | 获取幕列表 |
| GET | /api/v1/acts/{id}/chapters | 获取章列表 |
| POST | /api/v1/roots/{id}/anchors | 生成锚点 |
| GET | /api/v1/roots/{id}/anchors | 获取锚点 |
| PUT | /api/v1/anchors/{id} | 更新锚点 |
| POST | /api/v1/anchors/{id}/check | 检查可达性 |
| POST | /api/v1/entities/{id}/agent/init | 初始化代理 |
| GET | /api/v1/entities/{id}/agent/state | 获取代理状态 |
| PUT | /api/v1/entities/{id}/agent/desires | 更新欲望 |
| POST | /api/v1/entities/{id}/agent/decide | 触发决策 |
| POST | /api/v1/dm/arbitrate | DM裁决 |
| POST | /api/v1/dm/converge | 收敛检查 |
| POST | /api/v1/dm/intervene | DM干预 |
| POST | /api/v1/dm/replan | 动态补路 |
| POST | /api/v1/simulation/round | 单回合推演 |
| POST | /api/v1/simulation/scene | 场景推演 |
| GET | /api/v1/simulation/logs/{id} | 推演日志 |
| POST | /api/v1/render/scene | 智能渲染 |

---

## 6. Risk & Mitigation

| Risk | Mitigation |
|------|------------|
| LLM 延迟高 | 并行调用, Flash模型处理角色决策 |
| 角色行为不一致 | BDI约束, 每回合一致性检查 |
| 推演发散失控 | DM强制收束, 动态补路, 回滚机制 |
| Token消耗大 | 信念压缩, 记忆摘要, 增量状态 |
| 推演拖沓水文 | 节奏监控 (info_gain), 强制突发事件 |
| 正文风格断层 | 感官种子注入, 智能渲染管线 |
| 锚点不可达 | 动态补路: 过渡章节/软化锚点/等效替换 |

---

## 7. Success Metrics

| Metric | Target |
|--------|--------|
| 单回合推演延迟 | < 2s (P95) |
| 单场景推演延迟 | < 10s (P95) |
| 角色行为一致性 | > 85% |
| 锚点达成率 | > 90% |
| 收束成功率 | > 95% |
| 平均 info_gain/回合 | > 0.3 |
| 渲染后正文质量评分 | > 4.0/5.0 (人工评估) |
| 动态补路成功率 | > 80% |

---

## 8. Execution Order

```
Phase 1 (中观层) ──┐
                   ├──> Phase 3 (角色代理) ──┐
Phase 2 (锚点) ────┘                         ├──> Phase 5 (推演引擎)
                   Phase 4 (DM) ─────────────┘
                                                    ↓
                                             Phase 6 (支线) [可选]
                                                    ↓
                                             Phase 7 (反馈) [可选]
```

**建议**: Phase 1-5 为核心，Phase 6-7 为增强功能。

---

**文档结束**
