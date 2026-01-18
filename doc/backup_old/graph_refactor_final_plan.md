# 图数据库重构最终方案（V3.0 完整实施计划）

**文档版本**: 1.0 Final
**创建日期**: 2026-01-17
**项目**: AI Novel V3.0 长篇小说生成系统
**开发模式**: TDD (测试驱动开发)

---

## 执行摘要

### 重构目标

将当前基于 Kùzu 的嵌入式图数据库架构升级为基于 Memgraph 的高并发分布式架构，**补全 V3.0 系统设计中缺失的 72% 核心功能**，使系统从"版本控制工具"升级为"智能叙事引擎"。

### 核心问题

**当前系统功能完整性: 28%**

| V3.0 设计功能 | 当前状态 | 缺失影响 |
|--------------|---------|---------|
| 动态状态追踪 | ❌ 0% | 无法追踪实体状态变化历史 |
| 一致性检查 | ❌ 0% | LLM 无法获取真实世界状态 |
| 多米诺重构 | ⚠️ 30% | 只有标记，无自动修复算法 |
| 时序感知查询 | ❌ 0% | 无法查询历史状态快照 |
| 懒惰计算 | ⚠️ 40% | 无影响分析，过度标记 |
| 分支管理 | ✅ 100% | 功能完整 |

### 重构收益

1. **功能完整性**: 28% → 100% (+72%)
2. **并发能力**: 单连接 → 数百并发 (+∞)
3. **查询性能**: 遍历 Commit 链 → 快照查询 (-60% 延迟)
4. **用户体验**: 手动修复 → 自动修复建议 (+智能化)

### 技术栈决策

| 组件 | 当前 | 目标 | 理由 |
|------|------|------|------|
| 图数据库 | Kùzu (嵌入式) | Memgraph (内存原生) | 支持高并发 ACID 事务 |
| ORM | 手写 Cypher | GQLAlchemy | 类型安全，防注入 |
| 时序记忆 | 无 | 自研时序边 | 适配小说分支结构 |
| 实体消解 | 无 | Gemini 3 Pro 管道 | 轻量级，成本可控 |

### 实施周期

**5 周完整交付**，采用 TDD 开发模式，每周交付可测试的增量功能。

---

## 第一部分: 重构必要性分析

### 1.1 系统设计承诺 vs 实际实现

#### 承诺 1: 动态状态追踪 ❌

**设计文档 (第 3.2 节)**:
> "利用 Kùzu 图数据库维护叙事真值，Entity 包含 semantic_states 字典"

**当前实现问题**:
```python
# project/backend/app/storage/graph.py
def apply_semantic_states_patch(self, entity_id, patch):
    # 问题: 直接 UPDATE，丢失历史
    current = self.get_entity_semantic_states(entity_id)
    current.update(patch)
    # 覆盖写入，无法回溯
    self.conn.execute(f"UPDATE Entity SET semantic_states = '{json.dumps(current)}'")
```

**用户影响**:
- ❌ 无法查询"第 10 场时，主角的 HP 是多少？"
- ❌ 无法回溯"主角是在哪一场受伤的？"
- ❌ 无法检测"主角在第 5 场死亡，为何第 10 场还活着？"

**重构解决方案**:
```python
# 时序边: 保留完整历史
(:John)-[:STATE {
    type: "HP",
    value: "100%",
    start_scene_seq: 1,
    end_scene_seq: 5,
    branch_id: "main"
}]->(:StateValue)

(:John)-[:STATE {
    type: "HP",
    value: "10%",
    start_scene_seq: 5,
    end_scene_seq: NULL,  # 当前有效
    branch_id: "main"
}]->(:StateValue)

# 时序查询
MATCH (e:Entity {id: "john"})-[r:STATE {type: "HP"}]->(v)
WHERE r.branch_id = "main"
  AND r.start_scene_seq <= 3
  AND (r.end_scene_seq IS NULL OR r.end_scene_seq > 3)
RETURN r.value  // 返回 "100%"
```

#### 承诺 2: 一致性检查 ❌

**设计文档 (第 4 节 - 阶段二)**:
> "逻辑检察官查询图谱，检测反派位置，分析大纲结构影响"

**当前实现问题**:
```python
# project/backend/app/main.py:logic_check_endpoint()
@app.post("/api/v1/logic/check")
async def logic_check_endpoint(payload: LogicCheckPayload):
    # 问题: world_state 由前端传入，可能过期
    logic_result = await gateway.logic_check(payload)
    # payload.world_state 不是从图谱查询的
```

**用户影响**:
- ❌ LLM 基于错误状态进行推理（如"反派在千里之外"实际已到达）
- ❌ 无法检测跨场景的逻辑矛盾
- ❌ 无法分析大纲结构的影响

**重构解决方案**:
```python
# 从图谱查询真实状态
async def logic_check_with_graph_context(scene_id, user_intent):
    # 1. 查询当前场景序号
    scene_seq = await storage.get_scene_sequence(scene_id)

    # 2. 时序查询所有实体的当前状态
    world_state = await storage.query_world_state_at_scene(
        scene_seq=scene_seq,
        branch_id=branch_id
    )
    # 返回: {"John": {"location": "Home", "hp": "100%"}, ...}

    # 3. 查询大纲结构
    outline = await storage.query_outline_structure(scene_id)

    # 4. 调用 LLM（基于真实状态）
    logic_result = await gateway.logic_check(
        world_state=world_state,  # 来自图谱
        outline=outline,
        user_intent=user_intent
    )
```

#### 承诺 3: 多米诺重构 ⚠️

**设计文档 (第 5.1 节)**:
> "局部修复: 修改未来 3 个场景的摘要，使剧情在第 N+4 场景回归原大纲"

**当前实现问题**:
```python
# project/backend/app/storage/graph.py
def apply_local_scene_fix(self, scene_id: str, limit: int = 3):
    # 问题: 函数体为空或只是占位符
    pass  # 未实现
```

**用户影响**:
- ⚠️ 只能标记场景为 dirty，无法自动修复
- ❌ 无法计算"收敛窗口"内的最优修改方案
- ❌ 用户必须手动修改每个受影响的场景

**重构解决方案**:
```python
# 基于图谱分析影响范围
async def apply_local_scene_fix(scene_id, limit=3):
    # 1. 查询当前场景的状态变更
    state_changes = await storage.query_scene_state_changes(scene_id)

    # 2. 图遍历查询受影响的后续场景
    affected_scenes = await storage.query_affected_scenes(
        state_changes=state_changes,
        limit=limit
    )

    # 3. 为每个受影响场景生成修复建议
    fix_suggestions = []
    for scene in affected_scenes:
        new_summary = await llm.generate_patched_summary(
            original_outcome=scene.expected_outcome,
            state_changes=state_changes
        )
        fix_suggestions.append({
            "scene_id": scene.id,
            "original_summary": scene.summary,
            "suggested_summary": new_summary,
            "reason": f"适配状态变更: {state_changes}"
        })

    return fix_suggestions
```

### 1.2 Kùzu 架构限制

| Kùzu 限制 | 影响的功能 | 具体表现 |
|-----------|-----------|---------|
| **嵌入式架构** | 并发控制 | 单连接，无法支持数百人并发写 |
| **无动态算法** | 影响分析 | 无法实时计算"受影响的场景" |
| **无事务隔离级别** | 状态一致性 | 无法保证并发更新的原子性 |
| **查询性能** | 时序查询 | 无内存索引，遍历 Commit 链慢 |
| **无连接池** | 资源管理 | 每个请求创建新连接，开销大 |

### 1.3 用户体验的根本差异

| 用户场景 | 当前系统 | 重构后系统 |
|---------|---------|-----------|
| **修改第 5 场剧情** | ❌ 系统无法检测对后续场景的影响 | ✅ 精确标记受影响的场景（如第 10, 15 场），并给出修复建议 |
| **查询"主角何时受伤"** | ❌ 无法查询，只能手动翻阅文本 | ✅ 时序查询: "第 5 场，HP 从 100% 降至 10%，原因: 与反派战斗" |
| **创建分支尝试不同剧情** | ❌ 无法对比两个分支的世界观差异 | ✅ 双视窗对比: main 分支主角存活，dev 分支主角死亡 |
| **AI 进行逻辑检查** | ❌ 基于前端传入的过期状态 | ✅ 基于图谱查询的实时状态，检测矛盾 |
| **系统自动修复剧情偏差** | ❌ 只能标记 dirty，无法修复 | ✅ 自动生成修复建议，局部收敛算法 |

---

## 第二部分: 技术选型决策

### 2.1 核心技术栈

| 组件 | 选型 | 版本 | 理由 |
|------|------|------|------|
| **图数据库** | Memgraph Platform | 2.15+ | 内存原生，支持高并发 ACID 事务 |
| **ORM 框架** | GQLAlchemy | 1.4+ | Memgraph 官方 ORM，类型安全 |
| **Python 版本** | Python | 3.11+ | 支持 TaskGroup 异步并发 |
| **Web 框架** | FastAPI | 0.109+ | 原生异步支持 |
| **LLM 引擎** | Gemini 3 Pro | - | 实体消解、逻辑检查 |

### 2.2 为什么选择 Memgraph？

#### 对比分析

| 特性 | Kùzu | Memgraph | Neo4j |
|------|------|----------|-------|
| **部署模式** | 嵌入式 | Docker 容器 | Docker/云服务 |
| **并发模型** | 单连接 | 细粒度锁 | 细粒度锁 |
| **内存架构** | 磁盘优先 | 内存原生 | 磁盘+缓存 |
| **事务隔离** | 基础 ACID | 混合隔离级别 | 完整 ACID |
| **动态算法** | ❌ | ✅ MAGE 库 | ✅ GDS 库 |
| **Python ORM** | 基础 API | GQLAlchemy | py2neo |
| **开源协议** | MIT | BSL (免费<4核) | AGPL/商业 |
| **适用场景** | 单机分析 | Web 后端 | 企业级 |

#### Memgraph 的关键优势

1. **内存原生**: 所有数据和索引都在内存中，查询延迟 < 10ms
2. **细粒度锁**: 支持数百并发写，无全局锁
3. **MAGE 算法库**: 内置 PageRank、社区检测等动态算法
4. **GQLAlchemy ORM**: 类型安全，自动生成 Cypher
5. **Docker 部署**: 一键启动，适合云原生架构

### 2.3 为什么不直接使用 Graphiti？

#### Graphiti 的问题

1. **Neo4j 强绑定**: 硬编码 Neo4j 特定语法
   ```python
   # Graphiti 的 Neo4j 向量索引创建
   CREATE VECTOR INDEX node_embedding_index
   FOR (n:Chunk) ON (n.embedding)
   OPTIONS {indexConfig: {`vector.dimensions`: 1536}}

   # Memgraph 的向量索引创建（不兼容）
   CREATE VECTOR INDEX node_embedding_index
   ON :Chunk(embedding)
   WITH CONFIG {"dimension": 1536, "capacity": 10000}
   ```

2. **Episode 驱动模型**: 针对聊天机器人，不适配小说场景
3. **维护成本**: Fork 需要长期跟进上游更新

#### 自研时序边的优势

1. **完全可控**: 无外部依赖，可自由定制
2. **适配分支**: 支持 Git 式分支管理
3. **轻量级**: 50 行代码实现核心逻辑
4. **性能优化**: 针对小说场景优化查询

### 2.4 为什么不使用完整 BookCoref？

#### BookCoref 的问题

1. **模型依赖**: 需要 Qwen2-7B-Instruct，显存需求 ~16GB
2. **管道复杂**: 三阶段管道（字符链接 → LLM 过滤 → 聚类扩展）
3. **成本高**: 对每个场景运行完整管道，Token 消耗巨大
4. **实时性差**: 推理延迟 > 5s，不适合交互式场景

#### 轻量级 Gemini 消解的优势

1. **成本可控**: 使用 Gemini 3 Pro，Token 成本低
2. **实时性好**: 推理延迟 < 500ms
3. **上下文感知**: 利用 Gemini 的长上下文能力
4. **易于集成**: 复用现有的 ToponeGateway

---

## 第三部分: 数据模型设计

### 3.1 双子图架构 (Dual Subgraph Architecture)

系统图谱分为两个独立但互联的子图：

```
┌─────────────────────────────────────────────────────────┐
│  结构子图 (Structure Subgraph)                          │
│  职责: 管理写作过程的版本控制 (Git 流)                  │
│  节点: Root, Branch, BranchHead, Commit, SceneOrigin,   │
│        SceneVersion                                     │
│  边: HEAD, PARENT, INCLUDES, OF_ORIGIN                  │
└─────────────────────────────────────────────────────────┘
                        ↓ 桥接关系
              [:ESTABLISHES_STATE]
                        ↓
┌─────────────────────────────────────────────────────────┐
│  叙事子图 (Narrative Subgraph)                          │
│  职责: 管理故事世界观的动态演变 (时序流)                │
│  节点: Entity, WorldSnapshot                            │
│  边: TemporalRelation (带 start_seq/end_seq)            │
└─────────────────────────────────────────────────────────┘
```

### 3.2 结构子图: 版本控制层

#### 节点定义

```python
from gqlalchemy import Node, Field

class Root(Node):
    """小说根节点"""
    id: str = Field(index=True, unique=True, db=db)
    logline: str | None = None
    theme: str | None = None
    ending: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class Branch(Node):
    """分支节点"""
    id: str = Field(index=True, unique=True, db=db)  # 格式: root_id:branch_id
    root_id: str = Field(index=True, db=db)
    branch_id: str = Field(index=True, db=db)
    branch_root_id: str  # 分支所属的 root
    parent_branch_id: str | None = None
    fork_scene_origin_id: str | None = None
    fork_commit_id: str | None = None

class BranchHead(Node):
    """分支 HEAD 指针"""
    id: str = Field(index=True, unique=True, db=db)  # 格式: root_id:branch_id:head
    root_id: str = Field(index=True, db=db)
    branch_id: str = Field(index=True, db=db)
    head_commit_id: str = Field(index=True, db=db)
    fork_point_commit_id: str | None = None
    version: int = Field(default=1)  # 乐观锁版本号

class Commit(Node):
    """提交节点"""
    id: str = Field(index=True, unique=True, db=db)
    parent_id: str | None = Field(index=True, db=db)
    root_id: str = Field(index=True, db=db)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    message: str

class SceneOrigin(Node):
    """场景原点（不可变）"""
    id: str = Field(index=True, unique=True, db=db)
    root_id: str = Field(index=True, db=db)
    title: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    initial_commit_id: str = Field(index=True, db=db)
    sequence_index: int = Field(index=True, db=db)  # 场景序号
    parent_act_id: str | None = None

class SceneVersion(Node):
    """场景版本（可变）"""
    id: str = Field(index=True, unique=True, db=db)
    scene_origin_id: str = Field(index=True, db=db)
    commit_id: str = Field(index=True, db=db)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # 场景内容
    pov_character_id: str | None = None
    status: str | None = None  # draft, committed
    expected_outcome: str | None = None
    conflict_type: str | None = None
    actual_outcome: str | None = None
    summary: str | None = None
    rendered_content: str | None = None
    
    # 逻辑检查
    logic_exception: bool = Field(default=False)
    logic_exception_reason: str | None = None
    
    # 脏标记
    dirty: bool = Field(default=False)
```

#### 边定义

```python
from gqlalchemy import Relationship

class BranchPointsTo(Relationship, type="HEAD"):
    """分支 HEAD 指向 Commit"""
    pass

class CommitParent(Relationship, type="PARENT"):
    """Commit 父子关系"""
    pass

class CommitIncludesSceneVersion(Relationship, type="INCLUDES"):
    """Commit 包含 SceneVersion"""
    pass

class SceneVersionOfOrigin(Relationship, type="OF_ORIGIN"):
    """SceneVersion 属于 SceneOrigin"""
    pass

class BranchContainsCommit(Relationship, type="CONTAINS"):
    """Branch 包含 Commit"""
    pass

class RootContainsSceneOrigin(Relationship, type="CONTAINS"):
    """Root 包含 SceneOrigin"""
    pass
```

### 3.3 叙事子图: 时序状态层

#### 节点定义

```python
class Entity(Node):
    """通用实体（角色、地点、物品）"""
    id: str = Field(index=True, unique=True, db=db)
    root_id: str = Field(index=True, db=db)
    branch_id: str = Field(index=True, db=db)
    name: str | None = None
    entity_type: str | None = None  # Character, Location, Item
    tags: list[str] = Field(default_factory=list)
    arc_status: str | None = None
    
    # 语义状态（当前快照）
    semantic_states: dict[str, Any] = Field(default_factory=dict)
    # 示例: {"hp": "100%", "location": "Home", "mental": "Calm"}

class WorldSnapshot(Node):
    """世界状态快照"""
    id: str = Field(index=True, unique=True, db=db)
    scene_version_id: str = Field(index=True, db=db)
    branch_id: str = Field(index=True, db=db)
    scene_seq: int = Field(index=True, db=db)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # 快照内容（JSON 序列化）
    entity_states: dict[str, dict[str, Any]] = Field(default_factory=dict)
    # 示例: {"john": {"hp": "100%", "location": "Home"}, ...}
```

#### 时序边定义

```python
class TemporalRelation(Relationship, type="RELATION"):
    """时序关系边"""
    relation_type: str  # HATES, LOVES, AT, HAS, etc.
    tension: int = Field(default=50)  # 0-100
    
    # 时序属性（核心）
    start_scene_seq: int = Field(index=True, db=db)
    end_scene_seq: int | None = Field(index=True, db=db)  # NULL 表示当前有效
    branch_id: str = Field(index=True, db=db)
    
    # 元数据
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    invalidated_at: str | None = None

class EstablishesState(Relationship, type="ESTABLISHES_STATE"):
    """SceneVersion 建立 WorldSnapshot"""
    pass

class SnapshotOfEntity(Relationship, type="SNAPSHOT_OF"):
    """WorldSnapshot 包含 Entity 快照"""
    state_diff: dict[str, Any] = Field(default_factory=dict)
    # 记录该场景对实体状态的变更
```

### 3.4 桥接设计: 快照机制

#### 快照创建时机

1. **用户确认状态**: 调用 `/api/v1/state/commit` 时
2. **强制执行**: 调用 `/api/v1/logic/check` 且 mode=force_execute 时
3. **场景完成**: 调用 `/api/v1/scenes/{scene_id}/complete` 时

#### 快照创建流程

```python
async def create_world_snapshot(
    scene_version_id: str,
    branch_id: str,
    scene_seq: int
) -> WorldSnapshot:
    """创建世界状态快照"""
    
    # 1. 时序查询当前有效的所有状态
    query = """
    MATCH (e:Entity)-[r:RELATION]->(target)
    WHERE r.branch_id = $branch_id
      AND r.start_scene_seq <= $scene_seq
      AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq)
    RETURN e.id, e.semantic_states, r.relation_type, target.id
    """
    
    results = await db.execute_and_fetch(
        query,
        {"branch_id": branch_id, "scene_seq": scene_seq}
    )
    
    # 2. 构建快照
    entity_states = {}
    for row in results:
        entity_id = row["e.id"]
        if entity_id not in entity_states:
            entity_states[entity_id] = row["e.semantic_states"].copy()
    
    # 3. 创建快照节点
    snapshot = WorldSnapshot(
        id=str(uuid4()),
        scene_version_id=scene_version_id,
        branch_id=branch_id,
        scene_seq=scene_seq,
        entity_states=entity_states
    )
    
    await db.save_node(snapshot)
    
    # 4. 创建桥接边
    scene_version = await db.load_node(SceneVersion, scene_version_id)
    await db.save_relationship(
        EstablishesState(_start_node_id=scene_version.id, _end_node_id=snapshot.id)
    )
    
    return snapshot
```

### 3.5 索引策略

#### 必须建立的索引

```cypher
-- 结构子图索引
CREATE INDEX ON :Root(id);
CREATE INDEX ON :Branch(id);
CREATE INDEX ON :Branch(root_id, branch_id);
CREATE INDEX ON :BranchHead(id);
CREATE INDEX ON :BranchHead(root_id, branch_id);
CREATE INDEX ON :Commit(id);
CREATE INDEX ON :Commit(root_id);
CREATE INDEX ON :SceneOrigin(id);
CREATE INDEX ON :SceneOrigin(root_id, sequence_index);
CREATE INDEX ON :SceneVersion(id);
CREATE INDEX ON :SceneVersion(scene_origin_id);
CREATE INDEX ON :SceneVersion(commit_id);

-- 叙事子图索引
CREATE INDEX ON :Entity(id);
CREATE INDEX ON :Entity(root_id, branch_id);
CREATE INDEX ON :WorldSnapshot(id);
CREATE INDEX ON :WorldSnapshot(scene_version_id);
CREATE INDEX ON :WorldSnapshot(branch_id, scene_seq);

-- 时序边索引（关键）
CREATE INDEX ON :RELATION(branch_id, start_scene_seq);
CREATE INDEX ON :RELATION(branch_id, end_scene_seq);
```

---

## 第四部分: 核心功能实现

### 4.1 时序边失效机制

#### 功能描述

当实体状态发生变更时，自动失效旧的时序边，创建新的时序边，保留完整历史。

#### 实现代码

```python
# project/backend/app/services/world_state_service.py

from typing import Any, Dict, List
from gqlalchemy import Memgraph

class WorldStateService:
    """世界状态管理服务"""
    
    def __init__(self, db: Memgraph):
        self.db = db
    
    async def update_entity_state(
        self,
        entity_id: str,
        state_key: str,
        new_value: Any,
        scene_seq: int,
        branch_id: str
    ) -> Dict[str, Any]:
        """
        更新实体状态，自动失效旧边
        
        Args:
            entity_id: 实体 ID
            state_key: 状态键（如 "hp", "location"）
            new_value: 新值
            scene_seq: 当前场景序号
            branch_id: 分支 ID
        
        Returns:
            {"old_value": ..., "new_value": ..., "invalidated_edge_id": ...}
        """
        
        # 1. 查询当前有效的状态边
        query_current = """
        MATCH (e:Entity {id: $entity_id})-[r:STATE {type: $state_key}]->(v)
        WHERE r.branch_id = $branch_id
          AND r.end_scene_seq IS NULL
        RETURN r, v.value AS old_value
        """
        
        result = await self.db.execute_and_fetch(
            query_current,
            {
                "entity_id": entity_id,
                "state_key": state_key,
                "branch_id": branch_id
            }
        )
        
        old_value = None
        old_edge_id = None
        
        if result:
            row = result[0]
            old_value = row["old_value"]
            old_edge_id = row["r"].id
        
        # 2. 逻辑判断: 是否需要失效旧边
        if old_value == new_value:
            # 状态未变化，无需操作
            return {"old_value": old_value, "new_value": new_value, "changed": False}
        
        # 3. 失效旧边（设置 end_scene_seq）
        if old_edge_id:
            update_old_edge = """
            MATCH ()-[r:STATE]->()
            WHERE id(r) = $edge_id
            SET r.end_scene_seq = $scene_seq,
                r.invalidated_at = $now
            """
            
            await self.db.execute(
                update_old_edge,
                {
                    "edge_id": old_edge_id,
                    "scene_seq": scene_seq,
                    "now": datetime.utcnow().isoformat()
                }
            )
        
        # 4. 创建新边
        create_new_edge = """
        MATCH (e:Entity {id: $entity_id})
        CREATE (v:StateValue {value: $new_value})
        CREATE (e)-[:STATE {
            type: $state_key,
            start_scene_seq: $scene_seq,
            end_scene_seq: NULL,
            branch_id: $branch_id,
            created_at: $now
        }]->(v)
        """
        
        await self.db.execute(
            create_new_edge,
            {
                "entity_id": entity_id,
                "state_key": state_key,
                "new_value": new_value,
                "scene_seq": scene_seq,
                "branch_id": branch_id,
                "now": datetime.utcnow().isoformat()
            }
        )
        
        # 5. 更新 Entity 的 semantic_states 快照
        update_entity = """
        MATCH (e:Entity {id: $entity_id})
        SET e.semantic_states = apoc.map.setKey(
            e.semantic_states,
            $state_key,
            $new_value
        )
        """
        
        await self.db.execute(
            update_entity,
            {
                "entity_id": entity_id,
                "state_key": state_key,
                "new_value": new_value
            }
        )
        
        return {
            "old_value": old_value,
            "new_value": new_value,
            "changed": True,
            "invalidated_edge_id": old_edge_id
        }
    
    async def query_world_state_at_scene(
        self,
        scene_seq: int,
        branch_id: str,
        root_id: str
    ) -> Dict[str, Dict[str, Any]]:
        """
        时序查询: 查询指定场景时的世界状态
        
        Args:
            scene_seq: 场景序号
            branch_id: 分支 ID
            root_id: 根 ID
        
        Returns:
            {"entity_id": {"state_key": "value", ...}, ...}
        """
        
        query = """
        MATCH (e:Entity)-[r:STATE]->(v:StateValue)
        WHERE e.root_id = $root_id
          AND r.branch_id = $branch_id
          AND r.start_scene_seq <= $scene_seq
          AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq)
        RETURN e.id AS entity_id, r.type AS state_key, v.value AS state_value
        """
        
        results = await self.db.execute_and_fetch(
            query,
            {
                "root_id": root_id,
                "branch_id": branch_id,
                "scene_seq": scene_seq
            }
        )
        
        world_state = {}
        for row in results:
            entity_id = row["entity_id"]
            state_key = row["state_key"]
            state_value = row["state_value"]
            
            if entity_id not in world_state:
                world_state[entity_id] = {}
            
            world_state[entity_id][state_key] = state_value
        
        return world_state
```

### 4.2 实体消解管道

#### 功能描述

使用 Gemini 3 Pro 进行轻量级实体消解，避免创建重复实体，正确映射代词。

#### 实现代码

```python
# project/backend/app/services/entity_resolver.py

from typing import List, Dict, Any
from app.llm.topone_gateway import ToponeGateway
from app.models import Entity

class EntityResolver:
    """实体消解服务"""
    
    def __init__(self, gateway: ToponeGateway):
        self.gateway = gateway
    
    async def resolve_mentions(
        self,
        text: str,
        known_entities: List[Entity],
        context_scenes: List[str] = None
    ) -> Dict[str, str]:
        """
        消解文本中的实体提及
        
        Args:
            text: 场景文本
            known_entities: 已知实体列表
            context_scenes: 上下文场景文本（用于代词消解）
        
        Returns:
            {"mention": "entity_id", ...}
        """
        
        # 构建已知实体列表
        entity_list = "\n".join([
            f"- ID: {e.id}, Name: {e.name}, Type: {e.entity_type}"
            for e in known_entities
        ])
        
        # 构建上下文
        context = ""
        if context_scenes:
            context = "\n\n上下文场景:\n" + "\n".join(context_scenes)
        
        # 构建 Prompt
        prompt = f"""
你是一个实体消解专家。给定一段小说文本和已知实体列表，请将文本中的所有实体提及（包括代词）映射到实体 ID。

已知实体:
{entity_list}

{context}

当前场景文本:
{text}

任务:
1. 提取文本中的所有实体提及（人名、地名、物品名、代词等）
2. 将每个提及映射到已知实体列表中的 ID
3. 如果提及无法映射到已知实体，输出 "UNKNOWN"
4. 代词（他/她/它）必须根据上下文映射到最近提到的实体

输出格式 (JSON):
{{
  "他": "entity_123",
  "Alice": "entity_456",
  "那个黑客": "entity_123",
  "新角色Bob": "UNKNOWN"
}}

规则:
- 不要创建新实体 ID
- 如果同名实体有多个，根据类型和上下文区分
- 代词优先映射到上一句提到的实体
"""
        
        # 调用 Gemini
        response = await self.gateway.generate_structured(
            prompt=prompt,
            schema={
                "type": "object",
                "additionalProperties": {"type": "string"}
            }
        )
        
        return response
    
    async def detect_duplicate_entities(
        self,
        new_entity_name: str,
        new_entity_type: str,
        existing_entities: List[Entity]
    ) -> Entity | None:
        """
        检测重复实体
        
        Args:
            new_entity_name: 新实体名称
            new_entity_type: 新实体类型
            existing_entities: 已存在的实体列表
        
        Returns:
            如果检测到重复，返回已存在的实体；否则返回 None
        """
        
        # 精确匹配
        for entity in existing_entities:
            if entity.name == new_entity_name and entity.entity_type == new_entity_type:
                return entity
        
        # 模糊匹配（使用 LLM）
        entity_list = "\n".join([
            f"- ID: {e.id}, Name: {e.name}, Type: {e.entity_type}"
            for e in existing_entities
        ])
        
        prompt = f"""
你是一个实体去重专家。判断新实体是否与已知实体列表中的某个实体重复。

新实体:
- Name: {new_entity_name}
- Type: {new_entity_type}

已知实体:
{entity_list}

任务:
判断新实体是否与已知实体中的某个重复（考虑别名、昵称、全名/简称等）。

输出格式 (JSON):
{{
  "is_duplicate": true/false,
  "matched_entity_id": "entity_123" or null,
  "reason": "原因说明"
}}

示例:
- "Alice" 和 "Alice Smith" 是重复的
- "John" 和 "John Doe" 是重复的
- "他" 和 "John" 不是重复的（代词需要上下文）
"""
        
        response = await self.gateway.generate_structured(
            prompt=prompt,
            schema={
                "type": "object",
                "properties": {
                    "is_duplicate": {"type": "boolean"},
                    "matched_entity_id": {"type": ["string", "null"]},
                    "reason": {"type": "string"}
                },
                "required": ["is_duplicate", "matched_entity_id", "reason"]
            }
        )
        
        if response["is_duplicate"] and response["matched_entity_id"]:
            # 查找匹配的实体
            for entity in existing_entities:
                if entity.id == response["matched_entity_id"]:
                    return entity
        
        return None
```


### 4.3 影响分析算法

#### 功能描述

基于图遍历分析场景修改对后续场景的影响，精确标记受影响的场景。

#### 实现代码

```python
# project/backend/app/services/impact_analyzer.py

from typing import List, Dict, Any
from gqlalchemy import Memgraph

class ImpactAnalyzer:
    """影响分析服务"""
    
    def __init__(self, db: Memgraph):
        self.db = db
    
    async def analyze_scene_impact(
        self,
        scene_id: str,
        branch_id: str,
        state_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        分析场景修改的影响范围
        
        Args:
            scene_id: 当前场景 ID
            branch_id: 分支 ID
            state_changes: 状态变更列表
                [{"entity_id": "john", "state_key": "hp", "old": "100%", "new": "10%"}]
        
        Returns:
            受影响的场景列表
            [{"scene_id": "...", "reason": "...", "severity": "high/medium/low"}]
        """
        
        # 1. 查询当前场景序号
        scene_seq = await self._get_scene_sequence(scene_id)
        
        # 2. 提取受影响的实体 ID
        affected_entity_ids = [change["entity_id"] for change in state_changes]
        
        # 3. 图遍历：查询这些实体在后续场景中的出现
        query = """
        MATCH (origin:SceneOrigin)-[:CONTAINS]->(sv:SceneVersion)
        WHERE origin.root_id = $root_id
          AND origin.sequence_index > $scene_seq
        MATCH (sv)-[:INVOLVES]->(e:Entity)
        WHERE e.id IN $entity_ids
          AND e.branch_id = $branch_id
        RETURN DISTINCT origin.id AS scene_origin_id,
               origin.sequence_index AS scene_seq,
               collect(e.id) AS involved_entities
        ORDER BY origin.sequence_index
        """
        
        results = await self.db.execute_and_fetch(
            query,
            {
                "root_id": await self._get_root_id(scene_id),
                "scene_seq": scene_seq,
                "entity_ids": affected_entity_ids,
                "branch_id": branch_id
            }
        )
        
        # 4. 分析影响严重程度
        affected_scenes = []
        for row in results:
            scene_origin_id = row["scene_origin_id"]
            involved_entities = row["involved_entities"]
            
            # 计算严重程度
            severity = self._calculate_severity(
                state_changes=state_changes,
                involved_entities=involved_entities,
                scene_distance=row["scene_seq"] - scene_seq
            )
            
            # 生成影响原因
            reason = self._generate_impact_reason(
                state_changes=state_changes,
                involved_entities=involved_entities
            )
            
            affected_scenes.append({
                "scene_id": scene_origin_id,
                "scene_seq": row["scene_seq"],
                "reason": reason,
                "severity": severity,
                "involved_entities": involved_entities
            })
        
        return affected_scenes
    
    def _calculate_severity(
        self,
        state_changes: List[Dict[str, Any]],
        involved_entities: List[str],
        scene_distance: int
    ) -> str:
        """计算影响严重程度"""
        
        # 规则1: 距离越近，影响越大
        if scene_distance <= 3:
            base_severity = "high"
        elif scene_distance <= 10:
            base_severity = "medium"
        else:
            base_severity = "low"
        
        # 规则2: 涉及实体越多，影响越大
        involvement_ratio = len(involved_entities) / len(state_changes)
        if involvement_ratio > 0.8:
            # 提升一级
            if base_severity == "medium":
                base_severity = "high"
            elif base_severity == "low":
                base_severity = "medium"
        
        return base_severity
    
    def _generate_impact_reason(
        self,
        state_changes: List[Dict[str, Any]],
        involved_entities: List[str]
    ) -> str:
        """生成影响原因说明"""
        
        reasons = []
        for change in state_changes:
            if change["entity_id"] in involved_entities:
                reasons.append(
                    f"{change['entity_id']} 的 {change['state_key']} "
                    f"从 {change['old']} 变为 {change['new']}"
                )
        
        return "依赖状态变更: " + ", ".join(reasons)
```

---

## 第五部分: TDD测试规范

### 5.1 测试分层策略

```
E2E Tests (端到端测试)
├── 完整用户场景流程
├── 性能压测
└── 集成多个服务

Integration Tests (集成测试)
├── GraphStorage + Memgraph
├── WorldStateService + 时序边
├── EntityResolver + Gemini
└── ImpactAnalyzer + 图遍历

Unit Tests (单元测试)
├── ORM 模型验证
├── 数据转换逻辑
├── 工具函数
└── Prompt 模板
```

### 5.2 核心功能测试用例

#### 测试1: 双子图架构隔离

```python
# tests/integration/test_dual_subgraph.py

import pytest
from app.storage.graph import GraphStorage
from app.models import Root, Branch, Entity

class TestDualSubgraphIsolation:
    """测试双子图架构的隔离性"""
    
    @pytest.fixture
    def storage(self):
        """提供测试用的 GraphStorage"""
        storage = GraphStorage(db_path=":memory:")
        yield storage
        storage.close()
    
    def test_structure_subgraph_crud(self, storage):
        """
        Given: 空数据库
        When: 创建 Root, Branch, Commit 节点
        Then:
          - 节点成功创建
          - 不影响 Entity 节点
          - 查询结构子图返回正确节点数
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        
        # Act: 创建结构子图节点
        storage.create_root(
            root_id=root_id,
            logline="测试故事",
            theme="测试主题"
        )
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        # Assert: 结构子图节点存在
        root = storage.get_root(root_id)
        assert root.id == root_id
        assert root.logline == "测试故事"
        
        branches = storage.list_branches(root_id)
        assert branch_id in branches
        
        # Assert: 叙事子图不受影响
        entities = storage.list_entities(root_id, branch_id)
        assert len(entities) == 0
    
    def test_narrative_subgraph_crud(self, storage):
        """
        Given: 已有 Root 和 Branch
        When: 创建 Entity 和 TemporalRelation
        Then:
          - 节点和边成功创建
          - 不影响 Commit 节点
          - 查询叙事子图返回正确数据
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        storage.create_root(root_id=root_id, logline="测试")
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        # Act: 创建叙事子图节点
        entity_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name="John",
            entity_type="Character"
        )
        
        # Assert: 叙事子图节点存在
        entities = storage.list_entities(root_id, branch_id)
        assert len(entities) == 1
        assert entities[0].name == "John"
        
        # Assert: 结构子图不受影响
        commits = storage.get_branch_history(root_id, branch_id, limit=10)
        # 应该只有初始 commit
        assert len(commits) == 1
    
    def test_snapshot_bridge(self, storage):
        """
        Given: 已有 SceneVersion 和 Entity
        When: 创建 WorldSnapshot
        Then:
          - 快照成功创建
          - 可通过 SceneVersion 查询到快照
          - 快照包含正确的实体状态
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        storage.create_root(root_id=root_id, logline="测试")
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        entity_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name="John",
            entity_type="Character",
            semantic_states={"hp": "100%", "location": "Home"}
        )
        
        # Act: 创建快照
        scene_version_id = "sv_001"
        snapshot = storage.create_world_snapshot(
            scene_version_id=scene_version_id,
            branch_id=branch_id,
            scene_seq=1
        )
        
        # Assert: 快照包含正确数据
        assert snapshot.scene_version_id == scene_version_id
        assert snapshot.scene_seq == 1
        assert entity_id in snapshot.entity_states
        assert snapshot.entity_states[entity_id]["hp"] == "100%"
        assert snapshot.entity_states[entity_id]["location"] == "Home"

# 验收条件
"""
✅ 结构子图操作不触发叙事子图查询
✅ 叙事子图操作不触发结构子图查询
✅ 快照查询延迟 < 50ms (P99)
"""
```

#### 测试2: 时序边失效机制

```python
# tests/integration/test_temporal_edge.py

import pytest
from app.services.world_state_service import WorldStateService

class TestTemporalEdgeInvalidation:
    """测试时序边失效机制"""
    
    @pytest.fixture
    def service(self, storage):
        return WorldStateService(storage.db)
    
    async def test_edge_creation_with_temporal_attributes(self, service, storage):
        """
        Given: 两个 Entity 节点 (John, Home)
        When: 创建关系 John-[:AT {start_seq: 1, end_seq: NULL}]->Home
        Then:
          - 边成功创建
          - start_scene_seq = 1
          - end_scene_seq = NULL
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        storage.create_root(root_id=root_id, logline="测试")
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        john_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name="John",
            entity_type="Character"
        )
        
        # Act: 更新状态
        result = await service.update_entity_state(
            entity_id=john_id,
            state_key="location",
            new_value="Home",
            scene_seq=1,
            branch_id=branch_id
        )
        
        # Assert
        assert result["new_value"] == "Home"
        assert result["changed"] == True
        
        # 查询时序边
        world_state = await service.query_world_state_at_scene(
            scene_seq=1,
            branch_id=branch_id,
            root_id=root_id
        )
        assert world_state[john_id]["location"] == "Home"
    
    async def test_edge_invalidation_on_state_change(self, service, storage):
        """
        Given:
          - 已有边 John-[:AT {start_seq: 1, end_seq: NULL}]->Home
          - 新状态: John at Hospital (scene_seq=5)
        When: 调用 update_entity_state
        Then:
          - 旧边 end_seq 更新为 5
          - 新边创建: John-[:AT {start_seq: 5, end_seq: NULL}]->Hospital
          - 旧边未被删除
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        storage.create_root(root_id=root_id, logline="测试")
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        john_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name="John",
            entity_type="Character"
        )
        
        # 初始状态: John at Home (scene 1)
        await service.update_entity_state(
            entity_id=john_id,
            state_key="location",
            new_value="Home",
            scene_seq=1,
            branch_id=branch_id
        )
        
        # Act: 状态变更: John at Hospital (scene 5)
        result = await service.update_entity_state(
            entity_id=john_id,
            state_key="location",
            new_value="Hospital",
            scene_seq=5,
            branch_id=branch_id
        )
        
        # Assert: 状态变更成功
        assert result["old_value"] == "Home"
        assert result["new_value"] == "Hospital"
        assert result["changed"] == True
        assert result["invalidated_edge_id"] is not None
        
        # Assert: 时序查询正确
        # 查询 scene 3 时的状态（应该是 Home）
        world_state_3 = await service.query_world_state_at_scene(
            scene_seq=3,
            branch_id=branch_id,
            root_id=root_id
        )
        assert world_state_3[john_id]["location"] == "Home"
        
        # 查询 scene 5 时的状态（应该是 Hospital）
        world_state_5 = await service.query_world_state_at_scene(
            scene_seq=5,
            branch_id=branch_id,
            root_id=root_id
        )
        assert world_state_5[john_id]["location"] == "Hospital"
    
    async def test_time_travel_query(self, service, storage):
        """
        Given:
          - John-[:AT {start_seq: 1, end_seq: 5}]->Home
          - John-[:AT {start_seq: 5, end_seq: NULL}]->Hospital
        When: 查询 scene_seq=3 时的状态
        Then:
          - 返回 John at Home
          - 不返回 John at Hospital
        """
        # Arrange
        root_id = "root_001"
        branch_id = "main"
        storage.create_root(root_id=root_id, logline="测试")
        storage.create_branch(root_id=root_id, branch_id=branch_id)
        
        john_id = storage.create_entity(
            root_id=root_id,
            branch_id=branch_id,
            name="John",
            entity_type="Character"
        )
        
        # 创建时序边
        await service.update_entity_state(john_id, "location", "Home", 1, branch_id)
        await service.update_entity_state(john_id, "location", "Hospital", 5, branch_id)
        
        # Act: 时序查询
        world_state = await service.query_world_state_at_scene(
            scene_seq=3,
            branch_id=branch_id,
            root_id=root_id
        )
        
        # Assert
        assert world_state[john_id]["location"] == "Home"
        assert world_state[john_id]["location"] != "Hospital"

# 验收条件
"""
✅ 边失效操作原子性（事务保证）
✅ 时序查询正确性（100% 准确率）
✅ 并发更新无数据竞争
✅ 历史边保留完整（可回溯）
"""
```

#### 测试3: 实体消解管道

```python
# tests/integration/test_entity_resolver.py

import pytest
from app.services.entity_resolver import EntityResolver
from app.models import Entity

class TestEntityResolution:
    """测试实体消解管道"""
    
    @pytest.fixture
    def resolver(self, gateway):
        return EntityResolver(gateway)
    
    async def test_pronoun_resolution(self, resolver):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="John")]
          - 文本: "John走进房间。他坐下了。"
        When: 调用 resolve_mentions
        Then:
          - 返回 {"John": "e1", "他": "e1"}
          - 不创建新实体
        """
        # Arrange
        known_entities = [
            Entity(id="e1", name="John", entity_type="Character")
        ]
        text = "John走进房间。他坐下了。"
        
        # Act
        mentions = await resolver.resolve_mentions(
            text=text,
            known_entities=known_entities
        )
        
        # Assert
        assert mentions["John"] == "e1"
        assert mentions["他"] == "e1"
        assert "UNKNOWN" not in mentions.values()
    
    async def test_duplicate_entity_prevention(self, resolver):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="Alice")]
          - 文本: "Alice和Alice的朋友见面了。"
        When: 调用 resolve_mentions
        Then:
          - 两个"Alice"都映射到 e1
          - 不创建重复实体
        """
        # Arrange
        known_entities = [
            Entity(id="e1", name="Alice", entity_type="Character")
        ]
        text = "Alice和Alice的朋友见面了。"
        
        # Act
        mentions = await resolver.resolve_mentions(
            text=text,
            known_entities=known_entities
        )
        
        # Assert
        alice_mentions = [k for k, v in mentions.items() if "Alice" in k]
        assert all(mentions[m] == "e1" for m in alice_mentions)
    
    async def test_new_entity_detection(self, resolver):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="John")]
          - 文本: "John遇到了Bob。"
        When: 调用 resolve_mentions
        Then:
          - 返回 {"John": "e1", "Bob": "UNKNOWN"}
          - 标记 Bob 为新实体
        """
        # Arrange
        known_entities = [
            Entity(id="e1", name="John", entity_type="Character")
        ]
        text = "John遇到了Bob。"
        
        # Act
        mentions = await resolver.resolve_mentions(
            text=text,
            known_entities=known_entities
        )
        
        # Assert
        assert mentions["John"] == "e1"
        assert mentions["Bob"] == "UNKNOWN"

# 验收条件
"""
✅ 代词消解准确率 > 90%
✅ 重复实体检测准确率 > 95%
✅ 新实体识别召回率 > 85%
✅ 消解延迟 < 500ms (P95)
"""
```

### 5.3 测试覆盖率要求

| 模块 | 单元测试 | 集成测试 | E2E测试 |
|------|----------|----------|---------|
| GraphStorage (ORM) | > 90% | > 80% | N/A |
| WorldStateService | > 85% | > 90% | > 70% |
| EntityResolver | > 80% | > 75% | N/A |
| ImpactAnalyzer | > 85% | > 80% | N/A |
| API Endpoints | > 70% | > 85% | > 90% |

### 5.4 CI/CD集成

```yaml
# .github/workflows/test.yml
name: TDD Test Pipeline

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run Unit Tests
        run: pytest tests/unit --cov=app --cov-report=xml
      
      - name: Coverage Check
        run: |
          coverage report --fail-under=80

  integration-tests:
    runs-on: ubuntu-latest
    services:
      memgraph:
        image: memgraph/memgraph:latest
        ports:
          - 7687:7687
        options: >-
          --health-cmd "echo 'RETURN 1;' | mgconsole"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run Integration Tests
        env:
          MEMGRAPH_HOST: localhost
          MEMGRAPH_PORT: 7687
        run: pytest tests/integration

  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run Performance Benchmark
        run: pytest tests/performance --benchmark-only
      
      - name: Validate Latency
        run: |
          # P99 < 100ms for reads
          # P99 < 200ms for writes
          python scripts/validate_performance.py
```

---

## 第六部分: 5周实施计划

### 6.1 总体时间线

```
Week 1: 基础设施 + ORM层
├── Memgraph环境搭建
├── GQLAlchemy Schema定义
├── 基础CRUD测试
└── 交付物: Docker Compose + ORM模型

Week 2: 双子图架构 + 时序边
├── 结构子图实现
├── 叙事子图实现
├── 时序边失效逻辑
└── 交付物: WorldStateService + 集成测试

Week 3: 实体消解 + 影响分析
├── EntityResolver实现
├── ImpactAnalyzer实现
├── 并发控制优化
└── 交付物: 完整的状态管理流程

Week 4: 数据迁移 + API适配
├── Kùzu → Memgraph迁移脚本
├── API层适配
├── 回滚机制
└── 交付物: migration.py + 迁移测试

Week 5: 性能优化 + 文档
├── 性能压测
├── 索引优化
├── 文档完善
└── 交付物: 压测报告 + API文档
```

### 6.2 Week 1: 基础设施 + ORM层

#### 目标

搭建 Memgraph 环境，定义 GQLAlchemy ORM 模型，实现基础 CRUD 操作。

#### 任务清单

| 任务 | 负责人 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 1.1 编写 docker-compose.yml | DevOps | 2h | P0 |
| 1.2 定义 GQLAlchemy Node 模型 | 后端 | 4h | P0 |
| 1.3 定义 GQLAlchemy Relationship 模型 | 后端 | 4h | P0 |
| 1.4 实现 GraphStorage 基础类 | 后端 | 8h | P0 |
| 1.5 编写单元测试 | 测试 | 6h | P0 |
| 1.6 编写集成测试 | 测试 | 6h | P0 |

#### 交付物

1. **docker-compose.yml**
```yaml
version: '3.8'

services:
  memgraph:
    image: memgraph/memgraph-platform:latest
    container_name: ainovel_memgraph
    ports:
      - "7687:7687"  # Bolt protocol
      - "7444:7444"  # Monitoring
      - "3000:3000"  # Memgraph Lab
    environment:
      - MEMGRAPH_MEMORY_LIMIT=32GB
      - MEMGRAPH_QUERY_EXECUTION_TIMEOUT_SEC=300
      - MEMGRAPH_LOG_LEVEL=WARNING
    volumes:
      - ./data/memgraph:/var/lib/memgraph
      - ./data/memgraph_log:/var/log/memgraph
    command: ["--log-level=WARNING", "--also-log-to-stderr"]
    healthcheck:
      test: ["CMD", "echo", "RETURN 1;", "|", "mgconsole"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    container_name: ainovel_backend
    ports:
      - "8000:8000"
    environment:
      - MEMGRAPH_HOST=memgraph
      - MEMGRAPH_PORT=7687
      - SNOWFLAKE_ENGINE=gemini
    depends_on:
      memgraph:
        condition: service_healthy
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

2. **project/backend/app/storage/memgraph_storage.py**
```python
from gqlalchemy import Memgraph
from typing import List, Dict, Any
from app.models import Root, Branch, Entity

class MemgraphStorage:
    """Memgraph 存储层"""
    
    def __init__(self, host: str = "localhost", port: int = 7687):
        self.db = Memgraph(
            host=host,
            port=port,
            lazy=False
        )
        self._init_schema()
    
    def _init_schema(self):
        """初始化 Schema 和索引"""
        # 创建索引
        indexes = [
            "CREATE INDEX ON :Root(id);",
            "CREATE INDEX ON :Branch(id);",
            "CREATE INDEX ON :Entity(id);",
            "CREATE INDEX ON :SceneOrigin(id);",
            "CREATE INDEX ON :SceneVersion(id);",
        ]
        
        for index_query in indexes:
            try:
                self.db.execute(index_query)
            except Exception as e:
                # 索引可能已存在
                pass
    
    def create_root(self, root_id: str, logline: str, theme: str = None) -> Root:
        """创建 Root 节点"""
        root = Root(
            id=root_id,
            logline=logline,
            theme=theme
        )
        self.db.save_node(root)
        return root
    
    def get_root(self, root_id: str) -> Root:
        """查询 Root 节点"""
        return self.db.load_node(Root, root_id)
    
    # ... 其他 CRUD 方法
```

#### 验收标准

- ✅ Memgraph 容器成功启动，健康检查通过
- ✅ GQLAlchemy 连接成功，可执行查询
- ✅ 所有 Node 和 Relationship 模型定义完整
- ✅ 单元测试覆盖率 > 90%
- ✅ 集成测试通过，CRUD 操作正常

---

### 6.3 Week 2: 双子图架构 + 时序边

#### 目标

实现双子图架构，实现时序边失效逻辑，支持时序查询。

#### 任务清单

| 任务 | 负责人 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 2.1 实现结构子图 CRUD | 后端 | 8h | P0 |
| 2.2 实现叙事子图 CRUD | 后端 | 8h | P0 |
| 2.3 实现 WorldStateService | 后端 | 12h | P0 |
| 2.4 实现时序边失效逻辑 | 后端 | 10h | P0 |
| 2.5 实现时序查询 | 后端 | 8h | P0 |
| 2.6 编写集成测试 | 测试 | 10h | P0 |

#### 交付物

1. **project/backend/app/services/world_state_service.py** (完整实现)
2. **tests/integration/test_temporal_edge.py** (完整测试)

#### 验收标准

- ✅ 双子图架构隔离测试通过
- ✅ 时序边失效逻辑测试通过
- ✅ 时序查询准确率 100%
- ✅ 集成测试覆盖率 > 90%
- ✅ 查询延迟 < 30ms (P95)

---

### 6.4 Week 3: 实体消解 + 影响分析

#### 目标

实现实体消解管道，实现影响分析算法，优化并发控制。

#### 任务清单

| 任务 | 负责人 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 3.1 实现 EntityResolver | 后端 | 10h | P0 |
| 3.2 实现 ImpactAnalyzer | 后端 | 12h | P0 |
| 3.3 实现乐观锁机制 | 后端 | 6h | P1 |
| 3.4 实现连接池配置 | 后端 | 4h | P1 |
| 3.5 编写集成测试 | 测试 | 10h | P0 |
| 3.6 编写并发测试 | 测试 | 8h | P1 |

#### 交付物

1. **project/backend/app/services/entity_resolver.py** (完整实现)
2. **project/backend/app/services/impact_analyzer.py** (完整实现)
3. **tests/integration/test_entity_resolver.py** (完整测试)
4. **tests/integration/test_concurrency.py** (并发测试)

#### 验收标准

- ✅ 代词消解准确率 > 90%
- ✅ 重复实体检测准确率 > 95%
- ✅ 影响分析准确率 > 85%
- ✅ 乐观锁冲突检测率 100%
- ✅ 连接池利用率 > 80%
- ✅ 并发测试通过（50 并发写）

---

### 6.5 Week 4: 数据迁移 + API适配

#### 目标

实现 Kùzu → Memgraph 数据迁移脚本，适配现有 API，提供回滚机制。

#### 任务清单

| 任务 | 负责人 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 4.1 编写迁移脚本 | 后端 | 12h | P0 |
| 4.2 编写回滚脚本 | 后端 | 6h | P0 |
| 4.3 适配 API 层 | 后端 | 10h | P0 |
| 4.4 更新 main.py 依赖注入 | 后端 | 4h | P0 |
| 4.5 编写迁移测试 | 测试 | 8h | P0 |
| 4.6 执行迁移验证 | 测试 | 6h | P0 |

#### 交付物

1. **scripts/migrate_kuzu_to_memgraph.py**
```python
#!/usr/bin/env python3
"""
Kùzu → Memgraph 数据迁移脚本

Usage:
    python scripts/migrate_kuzu_to_memgraph.py \
        --kuzu-db /path/to/kuzu.db \
        --memgraph-host localhost \
        --memgraph-port 7687 \
        --dry-run
"""

import argparse
import kuzu
from gqlalchemy import Memgraph
from tqdm import tqdm

class KuzuToMemgraphMigrator:
    """数据迁移器"""
    
    def __init__(self, kuzu_db_path: str, memgraph_host: str, memgraph_port: int):
        self.kuzu_conn = kuzu.Connection(kuzu.Database(kuzu_db_path))
        self.memgraph = Memgraph(host=memgraph_host, port=memgraph_port)
    
    def migrate(self, dry_run: bool = False):
        """执行迁移"""
        print("开始迁移...")
        
        # 1. 迁移 Root 节点
        roots = self._export_roots()
        print(f"发现 {len(roots)} 个 Root 节点")
        
        if not dry_run:
            for root in tqdm(roots, desc="迁移 Root"):
                self._import_root(root)
        
        # 2. 迁移 Scene 节点
        scenes = self._export_scenes()
        print(f"发现 {len(scenes)} 个 Scene 节点")
        
        if not dry_run:
            for scene in tqdm(scenes, desc="迁移 Scene"):
                self._import_scene(scene)
        
        # 3. 迁移 Entity 节点
        entities = self._export_entities()
        print(f"发现 {len(entities)} 个 Entity 节点")
        
        if not dry_run:
            for entity in tqdm(entities, desc="迁移 Entity"):
                self._import_entity(entity)
        
        # 4. 迁移关系
        relations = self._export_relations()
        print(f"发现 {len(relations)} 条关系")
        
        if not dry_run:
            for relation in tqdm(relations, desc="迁移关系"):
                self._import_relation(relation)
        
        # 5. 验证迁移
        if not dry_run:
            self._validate_migration(roots, scenes, entities, relations)
        
        print("迁移完成！")
    
    def _export_roots(self) -> list:
        """从 Kùzu 导出 Root 节点"""
        result = self.kuzu_conn.execute(
            "MATCH (r:Root) RETURN r.id, r.logline, r.theme, r.ending"
        )
        return [
            {
                "id": row[0],
                "logline": row[1],
                "theme": row[2],
                "ending": row[3]
            }
            for row in result
        ]
    
    def _import_root(self, root: dict):
        """导入 Root 节点到 Memgraph"""
        query = """
        CREATE (r:Root {
            id: $id,
            logline: $logline,
            theme: $theme,
            ending: $ending
        })
        """
        self.memgraph.execute(query, root)
    
    # ... 其他导入方法
    
    def _validate_migration(self, roots, scenes, entities, relations):
        """验证迁移完整性"""
        # 验证节点数量
        root_count = self.memgraph.execute_and_fetch(
            "MATCH (r:Root) RETURN count(r) AS count"
        )[0]["count"]
        assert root_count == len(roots), f"Root 节点数量不匹配: {root_count} != {len(roots)}"
        
        # ... 其他验证

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kuzu-db", required=True)
    parser.add_argument("--memgraph-host", default="localhost")
    parser.add_argument("--memgraph-port", type=int, default=7687)
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    migrator = KuzuToMemgraphMigrator(
        kuzu_db_path=args.kuzu_db,
        memgraph_host=args.memgraph_host,
        memgraph_port=args.memgraph_port
    )
    
    migrator.migrate(dry_run=args.dry_run)
```

2. **project/backend/app/main.py** (更新依赖注入)
```python
# 更新 get_graph_storage 函数
@lru_cache(maxsize=1)
def get_graph_storage() -> MemgraphStorage:
    """MemgraphStorage 单例"""
    memgraph_host = os.getenv("MEMGRAPH_HOST", "localhost")
    memgraph_port = int(os.getenv("MEMGRAPH_PORT", "7687"))
    return MemgraphStorage(host=memgraph_host, port=memgraph_port)
```

#### 验收标准

- ✅ 迁移脚本成功执行，无数据丢失
- ✅ 数据完整性验证通过（节点数、边数一致）
- ✅ 随机抽样 100 个节点，属性值一致
- ✅ 迁移后功能测试全部通过
- ✅ 回滚脚本测试通过

---

### 6.6 Week 5: 性能优化 + 文档

#### 目标

进行性能压测，优化索引和查询，完善文档。

#### 任务清单

| 任务 | 负责人 | 工作量 | 优先级 |
|------|--------|--------|--------|
| 5.1 编写性能测试脚本 | 测试 | 8h | P0 |
| 5.2 执行性能压测 | 测试 | 6h | P0 |
| 5.3 分析性能瓶颈 | 后端 | 6h | P0 |
| 5.4 优化索引策略 | 后端 | 6h | P0 |
| 5.5 优化查询语句 | 后端 | 6h | P0 |
| 5.6 编写 API 文档 | 文档 | 8h | P1 |
| 5.7 编写部署文档 | DevOps | 6h | P1 |

#### 交付物

1. **tests/performance/test_benchmark.py**
```python
import pytest
from locust import HttpUser, task, between

class NovelUser(HttpUser):
    """模拟用户行为"""
    wait_time = between(1, 3)
    
    @task(3)
    def read_scene_context(self):
        """读取场景上下文（高频操作）"""
        self.client.get(
            "/api/v1/scenes/scene_001/context",
            params={"branch_id": "main"}
        )
    
    @task(1)
    def commit_scene(self):
        """提交场景修改（低频操作）"""
        self.client.post(
            "/api/v1/roots/root_001/branches/main/commit",
            json={
                "scene_origin_id": "scene_001",
                "content": {"summary": "测试摘要"},
                "message": "测试提交"
            }
        )
    
    @task(2)
    def logic_check(self):
        """逻辑检查（中频操作）"""
        self.client.post(
            "/api/v1/logic/check",
            json={
                "outline_requirement": "测试大纲",
                "world_state": {},
                "user_intent": "测试意图",
                "mode": "standard"
            }
        )

# 运行压测
# locust -f tests/performance/test_benchmark.py --host=http://localhost:8000 --users=100 --spawn-rate=10
```

2. **doc/API.md** (完整 API 文档)
3. **doc/DEPLOYMENT.md** (部署文档)

#### 验收标准

- ✅ 读操作 P99 < 100ms
- ✅ 写操作 P99 < 200ms
- ✅ 吞吐量 > 100 QPS (混合读写)
- ✅ 内存占用 < 20GB (32GB 配置)
- ✅ 100 并发用户无错误
- ✅ API 文档完整，示例可运行
- ✅ 部署文档完整，可一键部署

---

## 第七部分: 风险管理

### 7.1 技术风险

| 风险 | 概率 | 影响 | 缓解措施 | 应急方案 |
|------|------|------|----------|----------|
| Memgraph 性能不达标 | 中 | 高 | Week 1 进行性能 POC | 降级至 Neo4j |
| GQLAlchemy 学习曲线 | 中 | 中 | Week 1 完成 ORM 培训 | 使用原生 Cypher |
| 时序边逻辑复杂 | 高 | 中 | Week 2 编写详细设计文档 | 简化为快照模式 |
| 数据迁移失败 | 低 | 高 | 提供回滚脚本 | 保留 Kùzu 数据 |
| 并发冲突频繁 | 中 | 中 | 实现乐观锁 | 降低并发数 |

### 7.2 项目风险

| 风险 | 概率 | 影响 | 缓解措施 | 应急方案 |
|------|------|------|----------|----------|
| 进度延期 | 中 | 高 | 每周 Sprint Review | 砍掉 P2 功能 |
| 需求变更 | 低 | 中 | 冻结核心需求 | 需求变更流程 |
| 人员流动 | 低 | 高 | 编写详细文档 | 知识转移会议 |
| 测试不充分 | 中 | 高 | TDD 强制执行 | 增加测试周期 |

### 7.3 回滚计划

如果重构失败，提供完整的回滚方案：

1. **数据回滚**: 使用 `scripts/rollback_migration.py` 恢复 Kùzu 数据
2. **代码回滚**: Git revert 到重构前的 commit
3. **服务回滚**: 切换 docker-compose 到 Kùzu 版本
4. **验证回滚**: 运行完整测试套件，确保功能正常

---

## 第八部分: 成功标准

### 8.1 功能完整性

- ✅ 动态状态追踪: 100% 实现
- ✅ 一致性检查: 100% 实现
- ✅ 多米诺重构: 100% 实现
- ✅ 时序感知查询: 100% 实现
- ✅ 懒惰计算: 100% 实现
- ✅ 分支管理: 100% 保持

**总体功能完整性: 100%**

### 8.2 性能指标

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 读操作延迟 (P99) | < 100ms | Locust 压测 |
| 写操作延迟 (P99) | < 200ms | Locust 压测 |
| 吞吐量 (混合读写) | > 100 QPS | Locust 压测 |
| 并发用户数 | > 100 | Locust 压测 |
| 内存占用 | < 20GB | Prometheus 监控 |
| 查询准确率 | 100% | 集成测试 |

### 8.3 质量指标

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 单元测试覆盖率 | > 85% | pytest-cov |
| 集成测试覆盖率 | > 80% | pytest-cov |
| E2E 测试覆盖率 | > 70% | pytest-cov |
| 代码审查通过率 | 100% | GitHub PR Review |
| 文档完整性 | 100% | 人工审查 |

### 8.4 用户体验指标

| 指标 | 目标 | 测试方法 |
|------|------|----------|
| 状态查询准确率 | 100% | 用户测试 |
| 影响分析准确率 | > 85% | 用户测试 |
| 修复建议采纳率 | > 70% | 用户反馈 |
| 系统响应速度 | "快" | 用户反馈 |
| 功能易用性 | "易用" | 用户反馈 |

---

## 第九部分: 总结与建议

### 9.1 重构必要性

**评级: ⭐⭐⭐⭐⭐ (5/5 - 极度必要)**

1. **功能完整性**: 当前系统只实现了 28% 的设计功能
2. **用户承诺**: V3.0 设计文档承诺的核心功能无法交付
3. **架构债务**: 不重构将导致技术债务指数级增长
4. **商业价值**: 无法支持并发，无法作为公开网站后端

### 9.2 技术可行性

**评级: ⭐⭐⭐⭐ (4/5 - 高度可行)**

1. **Memgraph 成熟**: 生产级图数据库，性能可靠
2. **GQLAlchemy 完善**: 官方 ORM，文档齐全
3. **迁移路径清晰**: 数据模型兼容，迁移风险可控
4. **团队能力**: Python + FastAPI 技术栈熟悉

### 9.3 实施建议

1. **立即启动**: 不要等待，功能缺失已严重影响用户体验
2. **严格 TDD**: 每个功能先写测试，保证质量
3. **每周交付**: 增量交付，及时发现问题
4. **保留回滚**: 提供完整的回滚方案，降低风险

### 9.4 长期规划

重构完成后，系统将具备以下能力：

1. **智能叙事引擎**: 自动检测逻辑矛盾，生成修复建议
2. **高并发支持**: 支持数百人同时创作
3. **完整的历史追溯**: 查询任意时间点的世界状态
4. **精确的影响分析**: 自动标记受影响的场景
5. **商业化就绪**: 可作为公开网站后端上线

---

**文档版本**: 1.0 Final
**最后更新**: 2026-01-17
**审阅人**: 技术负责人、产品负责人、架构师

