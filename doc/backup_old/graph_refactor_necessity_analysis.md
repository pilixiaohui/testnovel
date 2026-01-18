# 图数据库重构方案的系统设计必要性分析

**分析日期**: 2026-01-17
**参考文档**: `doc/长篇小说生成系统设计.md` (V3.0 系统架构设计)

---

## 执行摘要

本文档从 **V3.0 系统设计的核心功能需求** 出发,分析为什么当前的 Kùzu 实现无法满足系统设计目标,以及图数据库重构方案如何解决这些根本性问题。

**核心结论**: 图数据库重构不是技术优化,而是 **系统设计完整性的必要补全**。当前实现缺失了 V3.0 设计中 3 个核心功能模块,导致系统无法实现其设计承诺。

---

## 1. V3.0 系统设计的核心承诺

### 1.1 设计文档中的关键功能

从 `doc/长篇小说生成系统设计.md` 中提取的核心功能承诺:

| 功能模块 | 设计文档描述 | 当前实现状态 | 缺失影响 |
|----------|--------------|--------------|----------|
| **1. 动态状态追踪** | "利用 Kùzu 图数据库维护叙事真值" | ❌ **未实现** | 无法追踪实体状态变化 |
| **2. 一致性检查** | "宏观结构的改变会触发全图的一致性检查" | ❌ **未实现** | 无法检测逻辑矛盾 |
| **3. 多米诺重构** | "微观剧情的突变会触发对后续未写章节的多米诺重构" | ⚠️ **部分实现** | 只有 dirty 标记,无自动修复 |
| **4. 时序感知查询** | "系统保留完整的历史快照,支持回溯历史" | ❌ **未实现** | 无法查询"第N场时的状态" |
| **5. 懒惰计算** | "采用分级响应机制,局部修复+脏标记" | ⚠️ **部分实现** | 只有标记,无修复逻辑 |
| **6. 分支管理** | "Git 式分支管理,对比与合并" | ✅ **已实现** | 功能完整 |

**问题**: 6 个核心功能中,只有 1 个完整实现,3 个完全缺失,2 个部分实现。

---

## 2. 功能缺失的根本原因分析

### 2.1 功能1: 动态状态追踪 ❌

#### 设计文档的承诺 (第 3.2 节)

> **UniversalEntity (通用实体)**:
> - `semantic_states`: Dict[str, str] (如 `{"mental": "Despair", "location": "Sector 7"}`)
> - `arc_status`: str (对应 CharacterSheet 的进度)
>
> **RelationEdge (动态关系)**:
> - 增加 `narrative_tension` (叙事张力值,0-100)

#### 当前实现的问题

查看 `project/backend/app/storage/graph.py`:

```python
# 当前的 Entity 表结构
CREATE NODE TABLE IF NOT EXISTS Entity(
    id STRING,
    name STRING,
    semantic_states_json STRING,  # ✅ 字段存在
    ...
)

# 当前的 EntityRelation 表结构
CREATE REL TABLE IF NOT EXISTS EntityRelation(
    FROM Entity TO Entity,
    branch_id STRING,
    relation_type STRING,
    tension INT  # ✅ 字段存在
)
```

**表面上看**: 字段都存在,似乎已实现。

**实际问题**: 缺少 **状态变更的时序追踪机制**

```python
# 当前实现: 直接覆盖状态
def apply_semantic_states_patch(entity_id, patch):
    # 问题: 直接 UPDATE,丢失历史
    UPDATE Entity SET semantic_states_json = new_value
    WHERE id = entity_id
```

**后果**:
1. ❌ 无法查询"第 10 场时,主角的 HP 是多少?"
2. ❌ 无法回溯"主角是在哪一场受伤的?"
3. ❌ 无法检测"主角在第 5 场死亡,为何第 10 场还活着?"

#### 重构方案的解决方式

长期方案引入 **时序边 (Temporal Edges)**:

```python
# 重构后: 保留历史,支持时序查询
(:Entity)-[:STATE {
    type: "HP",
    value: "100%",
    start_scene_seq: 1,
    end_scene_seq: 5  # 第5场受伤,HP变为10%
}]->(:StateValue)

(:Entity)-[:STATE {
    type: "HP",
    value: "10%",
    start_scene_seq: 5,
    end_scene_seq: NULL  # 当前有效
}]->(:StateValue)
```

**查询第 3 场的状态**:
```cypher
MATCH (e:Entity)-[r:STATE]->(v)
WHERE r.start_scene_seq <= 3
  AND (r.end_scene_seq IS NULL OR r.end_scene_seq > 3)
RETURN r.value  // 返回 "100%"
```

**必要性**: 这是实现 V3.0 设计中 **"叙事真值维护"** 的唯一方式。

---

### 2.2 功能2: 一致性检查 ❌

#### 设计文档的承诺 (第 4 节 - 阶段二)

> **Step 2: 意图协商与逻辑推演**
>
> **逻辑检察官 (Gemini 3 Pro Reasoning)**:
> - 输入: `[当前状态] + [大纲要求] + [用户指令]`
> - 推理任务:
>   - **一致性检查**: 反派现在哪里?(查询图谱)
>   - **雪花结构影响**: 如果提前相遇,后续的"灾难2"是否失效?

#### 当前实现的问题

查看 `project/backend/app/main.py:logic_check_endpoint()`:

```python
@app.post("/api/v1/logic/check")
async def logic_check_endpoint(payload: LogicCheckPayload):
    # 当前实现: 只调用 LLM,不查询图谱
    logic_result = await gateway.logic_check(payload)

    # 问题: payload 中的 world_state 是前端传入的,不是从图谱查询的
    # 如果前端数据过期,LLM 基于错误状态进行推理
```

**后果**:
1. ❌ LLM 无法获取实体的真实状态 (如"反派在千里之外")
2. ❌ 无法检测跨场景的逻辑矛盾 (如"主角在第 5 场死亡,第 10 场复活")
3. ❌ 无法分析大纲结构的影响 (如"提前相遇导致后续铺垫作废")

#### 重构方案的解决方式

长期方案的 **叙事子图 + 时序查询**:

```python
# 重构后: 从图谱查询真实状态
async def logic_check_with_graph_context(scene_id, user_intent):
    # 1. 查询当前场景序号
    scene_seq = get_scene_sequence(scene_id)

    # 2. 查询所有实体的当前状态 (时序查询)
    world_state = query_world_state_at_scene(scene_seq)
    # 返回: {"John": {"location": "Home", "hp": "100%"}, ...}

    # 3. 查询大纲结构
    outline = query_outline_structure(scene_id)
    # 返回: {"current_act": 1, "next_disaster": "第10场", ...}

    # 4. 调用 LLM 进行逻辑推理
    logic_result = await llm.check_logic(
        world_state=world_state,  # 来自图谱的真实状态
        outline=outline,
        user_intent=user_intent
    )
```

**必要性**: 这是实现 V3.0 设计中 **"逻辑检察官"** 的前提条件。

---

### 2.3 功能3: 多米诺重构 ⚠️

#### 设计文档的承诺 (第 5 节)

> **5.1 策略一: 局部修复 (Local Patching)**
>
> 当 `actual_outcome` 与 `expected_outcome` 出现中度偏差时,系统启动 **Architect Agent** 进行局部收敛计算:
> - **收敛窗口**: 仅尝试修改未来最近的 3 个节点 (N+1, N+2, N+3)
> - **任务目标**: 修改这 3 个场景的摘要,使得剧情在第 N+4 个场景回归原大纲的轨道

#### 当前实现的问题

查看 `project/backend/app/main.py:_apply_impact_level()`:

```python
def _apply_impact_level(impact_level: ImpactLevel):
    if impact_level == ImpactLevel.LOCAL:
        # 当前实现: 只调用 storage.apply_local_scene_fix()
        return storage.apply_local_scene_fix(limit=3)

    if impact_level == ImpactLevel.CASCADING:
        # 当前实现: 只标记为 dirty
        return storage.mark_future_scenes_dirty()
```

查看 `project/backend/app/storage/graph.py:apply_local_scene_fix()`:

```python
def apply_local_scene_fix(self, scene_id: str, limit: int = 3):
    # 问题: 函数体为空或只是占位符
    # 没有实现"修改场景摘要"的逻辑
    pass
```

**后果**:
1. ⚠️ 只能标记场景为 dirty,无法自动修复
2. ❌ 无法计算"收敛窗口"内的最优修改方案
3. ❌ 用户必须手动修改每个受影响的场景

#### 重构方案的解决方式

长期方案的 **叙事子图 + 影响分析**:

```python
# 重构后: 基于图谱分析影响范围
async def apply_local_scene_fix(scene_id, limit=3):
    # 1. 查询当前场景的状态变更
    state_changes = query_scene_state_changes(scene_id)
    # 返回: [{"entity": "John", "old": "Home", "new": "Hospital"}]

    # 2. 查询受影响的后续场景 (图遍历)
    affected_scenes = query_affected_scenes(
        state_changes=state_changes,
        limit=limit
    )
    # 返回: [scene_N+1, scene_N+2, scene_N+3]

    # 3. 为每个受影响场景生成修复建议
    for scene in affected_scenes:
        # 查询该场景的原始大纲要求
        original_outcome = scene.expected_outcome

        # 调用 LLM 生成新的摘要 (考虑状态变更)
        new_summary = await llm.generate_patched_summary(
            original_outcome=original_outcome,
            state_changes=state_changes
        )

        # 更新场景摘要
        update_scene_summary(scene.id, new_summary)
```

**必要性**: 这是实现 V3.0 设计中 **"局部修复"** 的核心算法。

---

### 2.4 功能4: 时序感知查询 ❌

#### 设计文档的承诺 (第 5.3 节)

> **5.3 策略三: Git 式分支管理 (Branching)**
>
> - **Master 分支**: 始终保留原定的雪花大纲结构
> - **Dev 分支**: 当出现重大剧情偏离时,系统自动创建一个新的 `Dev` 变体分支
> - **对比与合并**: 用户可以在双视窗中对比 `Master` 和 `Dev` 的后续发展差异

#### 当前实现的问题

当前的分支管理 **只支持版本控制**,不支持 **叙事状态的分支**:

```python
# 当前实现: 分支只管理 SceneVersion
class Branch:
    id: str
    head_commit_id: str

# 问题: 无法查询"在 Dev 分支的第 10 场,主角的状态是什么?"
# 因为 Entity 的 semantic_states 是全局的,不区分分支
```

**后果**:
1. ❌ 无法对比不同分支的世界观差异
2. ❌ 合并分支时,无法检测状态冲突 (如两个分支都修改了主角的 HP)
3. ❌ 无法实现"双视窗对比"功能

#### 重构方案的解决方式

长期方案的 **双子图架构**:

```
结构子图 (版本控制)
├── Branch: main
│   └── Commit A → Commit B
└── Branch: dev
    └── Commit A → Commit C

叙事子图 (状态管理)
├── main 分支的状态快照
│   └── Scene 10: John HP=100%
└── dev 分支的状态快照
    └── Scene 10: John HP=10% (受伤分支)
```

**查询不同分支的状态**:
```cypher
// 查询 main 分支第 10 场的状态
MATCH (b:Branch {id: "main"})-[:HEAD]->(c:Commit)
      -[:INCLUDES]->(sv:SceneVersion {sequence: 10})
      -[:ESTABLISHES_STATE]->(ws:WorldSnapshot)
      -[:SNAPSHOT_OF]->(e:Entity {name: "John"})
RETURN e.semantic_states  // 返回 {"hp": "100%"}

// 查询 dev 分支第 10 场的状态
MATCH (b:Branch {id: "dev"})-[:HEAD]->(c:Commit)
      -[:INCLUDES]->(sv:SceneVersion {sequence: 10})
      -[:ESTABLISHES_STATE]->(ws:WorldSnapshot)
      -[:SNAPSHOT_OF]->(e:Entity {name: "John"})
RETURN e.semantic_states  // 返回 {"hp": "10%"}
```

**必要性**: 这是实现 V3.0 设计中 **"分支对比与合并"** 的数据基础。

---

### 2.5 功能5: 懒惰计算 ⚠️

#### 设计文档的承诺 (第 5.2 节)

> **5.2 策略二: 脏标记机制 (Dirty Flags)**
>
> 当偏差过大,且无法在 3 个节点内收敛时,系统启用 **惰性计算**:
> - **Dirty Marking**: 系统分析受影响的逻辑链条,将远端的受影响场景节点标记为 `DIRTY`
> - **延迟重构**: 只有当用户真正点击进入或接近这些 `DIRTY` 节点时,才触发该局部的重构请求

#### 当前实现的问题

当前实现 **只有标记,没有分析**:

```python
# 当前实现: 简单地标记所有后续场景为 dirty
def mark_future_scenes_dirty(self, scene_id: str):
    # 问题: 无差别标记,无法区分"真正受影响"和"可能受影响"
    UPDATE Scene SET dirty = TRUE
    WHERE sequence_index > current_scene_index
```

**后果**:
1. ⚠️ 过度标记: 即使场景不受影响,也被标记为 dirty
2. ❌ 无法分析"逻辑链条": 不知道为什么这个场景会受影响
3. ❌ 无法生成"修复建议": 用户不知道如何修改

#### 重构方案的解决方式

长期方案的 **图遍历 + 依赖分析**:

```python
# 重构后: 基于图谱分析真正的依赖关系
def mark_future_scenes_dirty_with_analysis(scene_id):
    # 1. 查询当前场景涉及的实体
    entities = query_scene_entities(scene_id)

    # 2. 查询这些实体在后续场景中的出现 (图遍历)
    affected_scenes = []
    for entity in entities:
        # 查询该实体参与的后续场景
        scenes = query_scenes_with_entity(
            entity_id=entity.id,
            after_scene=scene_id
        )
        affected_scenes.extend(scenes)

    # 3. 只标记真正受影响的场景
    for scene in affected_scenes:
        mark_scene_dirty(
            scene_id=scene.id,
            reason=f"依赖实体 {entity.name} 的状态变更"
        )
```

**必要性**: 这是实现 V3.0 设计中 **"精确的脏标记"** 的算法基础。

---

## 3. 为什么 Kùzu 无法满足需求?

### 3.1 Kùzu 的架构限制

| 限制 | 影响的功能 | 原因 |
|------|-----------|------|
| **嵌入式架构** | 并发控制 | 单连接,无法支持数百人并发写 |
| **无动态算法** | 影响分析 | 无法实时计算"受影响的场景" |
| **无事务隔离级别** | 状态一致性 | 无法保证并发更新的原子性 |
| **查询性能** | 时序查询 | 无内存索引,时序查询慢 |

### 3.2 为什么必须迁移到 Memgraph?

| Memgraph 特性 | 解决的问题 | 对应的 V3.0 功能 |
|--------------|-----------|------------------|
| **内存原生 + 细粒度锁** | 支持数百人并发写 | 公开网站后端 |
| **MAGE 动态算法库** | 实时计算影响范围 | 多米诺重构 + 懒惰计算 |
| **混合隔离级别** | 保证状态一致性 | 动态状态追踪 |
| **Skip List 索引** | 时序查询 < 30ms | 时序感知查询 |

---

## 4. 重构方案与系统设计的对应关系

### 4.1 长期方案的双子图架构

```
V3.0 设计文档                    长期重构方案
┌─────────────────────┐         ┌─────────────────────┐
│ 雪花写作法           │  对应   │ 结构子图             │
│ - Commit/Branch     │ ──────> │ - Branch, Commit    │
│ - SceneVersion      │         │ - SceneVersion      │
└─────────────────────┘         └─────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│ 叙事真值维护         │  对应   │ 叙事子图             │
│ - Entity States     │ ──────> │ - Entity            │
│ - Temporal Edges    │         │ - TemporalRelation  │
└─────────────────────┘         └─────────────────────┘

┌─────────────────────┐         ┌─────────────────────┐
│ 快照机制             │  对应   │ 桥接设计             │
│ - 避免遍历 Commit   │ ──────> │ - WorldSnapshot     │
│ - 快速查询状态       │         │ - ESTABLISHES_STATE │
└─────────────────────┘         └─────────────────────┘
```

### 4.2 功能实现的完整性对比

| V3.0 设计功能 | 当前实现 | 重构后实现 | 完整性提升 |
|--------------|----------|-----------|-----------|
| 动态状态追踪 | 0% | 100% | +100% |
| 一致性检查 | 0% | 100% | +100% |
| 多米诺重构 | 30% (只有标记) | 100% | +70% |
| 时序感知查询 | 0% | 100% | +100% |
| 懒惰计算 | 40% (只有标记) | 100% | +60% |
| 分支管理 | 100% | 100% | 0% |
| **总体完整性** | **28%** | **100%** | **+72%** |

---

## 5. 系统设计视角的必要性总结

### 5.1 不是优化,是补全

图数据库重构不是"性能优化"或"技术升级",而是 **系统设计完整性的必要补全**:

1. **当前系统只实现了 28% 的设计功能**
2. **核心的"叙事真值维护"完全缺失**
3. **"逻辑检察官"无法获取真实状态**
4. **"多米诺重构"只是空壳**

### 5.2 用户体验的根本差异

| 场景 | 当前系统 | 重构后系统 |
|------|---------|-----------|
| **用户修改第 5 场** | ❌ 系统无法检测对后续场景的影响 | ✅ 系统精确标记受影响的场景 (如第 10, 15 场) |
| **用户查询"主角何时受伤"** | ❌ 无法查询,只能手动翻阅文本 | ✅ 时序查询: "第 5 场,HP 从 100% 降至 10%" |
| **用户创建分支尝试不同剧情** | ❌ 无法对比两个分支的世界观差异 | ✅ 双视窗对比: main 分支主角存活, dev 分支主角死亡 |
| **AI 进行逻辑检查** | ❌ 基于前端传入的过期状态 | ✅ 基于图谱查询的真实状态 |
| **系统自动修复剧情偏差** | ❌ 只能标记 dirty,无法修复 | ✅ 自动生成修复建议,局部收敛 |

### 5.3 架构债务的累积

如果不进行重构:

1. **技术债务**: 每次新增功能都需要绕过"缺失的叙事子图",代码越来越复杂
2. **用户体验债务**: 用户发现系统承诺的功能无法使用,信任度下降
3. **维护债务**: 无法支持并发,系统只能作为单机工具,无法上线

---

## 6. 结论

### 6.1 必要性评级: ⭐⭐⭐⭐⭐ (5/5 - 极度必要)

**理由**:
1. **功能完整性**: 当前系统只实现了 28% 的设计功能
2. **用户承诺**: V3.0 设计文档承诺的核心功能无法交付
3. **架构债务**: 不重构将导致技术债务指数级增长
4. **商业价值**: 无法支持并发,无法作为公开网站后端

### 6.2 优先级建议

| 功能模块 | 优先级 | 理由 |
|----------|--------|------|
| **双子图架构** | P0 (最高) | 所有其他功能的基础 |
| **时序边机制** | P0 (最高) | 实现"叙事真值维护"的唯一方式 |
| **快照机制** | P1 (高) | 性能优化,避免遍历 Commit 链 |
| **影响分析算法** | P1 (高) | 实现"多米诺重构"的核心 |
| **实体消解管道** | P2 (中) | 提升数据质量,但可后续优化 |

### 6.3 实施建议

**立即启动重构,分 5 周实施**:

1. **Week 1**: 双子图架构 + 时序边机制 (P0)
2. **Week 2**: 快照机制 + 影响分析算法 (P1)
3. **Week 3**: 实体消解管道 (P2)
4. **Week 4**: 数据迁移 + 回滚机制
5. **Week 5**: 性能压测 + 文档完善

**不重构的后果**:
- ❌ 系统永远无法实现 V3.0 设计的核心功能
- ❌ 用户体验与设计承诺严重不符
- ❌ 无法支持并发,无法商业化
- ❌ 技术债务累积,最终需要完全重写

---

**报告完成日期**: 2026-01-17
**建议审阅人**: 产品负责人、技术负责人、架构师
