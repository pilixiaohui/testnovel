基于您提供的 V3.0 架构设计、图数据库重构草案，以及对 Memgraph、BookCoref、Graphiti 的深度调研，针对“支持几百人并发”且“作为公开网站后端”的需求，我为您制定了一套**融合型图数据知识库重构方案**。

### 核心决策摘要

1.  **基础设施升级**：将嵌入式 **Kùzu** 替换为 **Memgraph**。
    *   *理由*：Kùzu 适合单机分析，但难以支撑数百人并发写的 Web 场景。Memgraph 是内存原生，支持高并发 ACID 事务，且 Python 生态（GQLAlchemy）极佳。
2.  **逻辑模型分层**：**Draft Versioning (Git流)** 与 **Narrative State (时序流)** 分离。
    *   *理由*：您原有的重构方案解决了“写作版本控制”（Git），而 Graphiti 解决了“故事世界观演变”（时序）。两者需要在图谱中并存。
3.  **管道智能化**：引入 **BookCoref 思想**改造您的“状态提取”环节。
    *   *理由*：Gemini Flash 提取状态容易产生同名实体混淆（Hallucination），需要 BookCoref 的消解逻辑来清洗数据。

---

### 1. 技术选型架构 (The Tech Stack)

| 组件 | 选型 | 作用与实施策略 |
| :--- | :--- | :--- |
| **图数据库** | **Memgraph (Platform)** | **核心存储**。运行于 Docker 容器中。利用其全内存特性处理高频的“逻辑推演”查询。**替代 Kùzu**。 |
| **ORM 框架** | **GQLAlchemy** | **数据映射**。Memgraph 官方的 Python OGM。用于替代手写 Cypher 字符串拼接，提升代码可维护性和防注入能力。 |
| **实体消解** | **Custom Pipeline (Inspired by BookCoref)** | **状态清洗**。不直接引入庞大的 BookCoref 模型，而是复用其“三阶段管道”逻辑，利用 Gemini 3 Pro 实现轻量级消解。 |
| **时序记忆** | **Graphiti Logic (Custom Impl)** | **动态世界观**。借鉴 Graphiti 的 `valid_at` / `invalid_at` 概念，但需适配小说分支结构，**不直接使用 Graphiti 库** (因其绑定 Neo4j)。 |

---

### 2. 数据模型重构 (Unified Ontology)

我们需要将您的**Git 式版本控制**（用户草案）与 **Graphiti 式时序状态**融合。图谱将分为两个子图：**结构子图 (Structure Subgraph)** 和 **叙事子图 (Narrative Subgraph)**。

#### 2.1 结构子图：管理“写作过程” (Refining your Draft Plan)
这部分沿用您设计的 Commit/Branch 模型，适配 Memgraph。

*   **Nodes**: `Branch`, `Commit`, `SceneOrigin`, `SceneVersion`
*   **Edges**:
    *   `(:Branch)-[:HEAD]->(:Commit)`
    *   `(:Commit)-[:PARENT]->(:Commit)`
    *   `(:Commit)-[:INCLUDES]->(:SceneVersion)`
    *   `(:SceneVersion)-[:OF_ORIGIN]->(:SceneOrigin)`

#### 2.2 叙事子图：管理“故事状态” (Integrating Graphiti)
这是关键的**动态记忆层**。不同于 Graphiti 使用物理时间，小说使用**叙事时间（Narrative Time）**，即 `SceneSequence`。

*   **Nodes**: `Entity` (Character, Location, Item), `Fact` (Abstract Node for complex states)
*   **Edges (Temporal Edges)**:
    *   **关键改进**：边不再只有 `type`，而是包含**生命周期属性**。
    *   关系定义：`(:Entity)-[:RELATION {type: "HATES", start_scene_seq: 10, end_scene_seq: 15}]->(:Entity)`
    *   *解读*：这两个人在第10场到第15场之间互相憎恨。

#### 2.3 桥接设计：Snapshotting
为了避免每次查询都要遍历 Commit 链来计算当前状态，我们在 `SceneVersion` 上挂载状态快照。

*   `(:SceneVersion)-[:ESTABLISHES_STATE]->(:WorldSnapshot)`
*   当用户点击“强制执行”或“确认状态”时，系统将当前的 `Narrative Subgraph` 的切片计算出来，存储为该 Version 的 Diff。

---

### 3. 核心工作流重构 (Pipeline Implementation)

#### 3.1 写入流程：从“文本”到“动态图”
结合 **BookCoref** 的清洗思路与 **Graphiti** 的边失效机制。

1.  **用户提交场景 (Commit Scene)**：
    *   用户在前端编辑器完成第 N 场写作。
    *   后端生成 `SceneVersion` 和 `Commit` 节点。
2.  **实体消解 (Entity Resolution - BookCoref Style)**：
    *   *System Prompt*: "提取文本中的实体。注意：'他'指代上一段提到的'John'。如果出现'Alice'，请检查现有图谱中是否已有 ID 为 X 的 Alice，不要创建新节点。"
    *   使用 Gemini 3 Pro 进行**上下文感知过滤**（BookCoref Phase 2）。
3.  **时序边计算 (Temporal Edge Invalidation - Graphiti Style)**：
    *   **输入**：当前文本提取的新状态（如 `John at Hospital`）。
    *   **查询**：查询该实体在上一个场景（N-1）的状态（如 `John at Home`）。
    *   **逻辑判断**：位置互斥。
    *   **图操作**：
        *   找到旧边 `(:John)-[r:AT]->(:Home)`。
        *   **不删除**旧边。
        *   更新旧边属性：`r.end_scene_seq = N`。
        *   创建新边：`(:John)-[:AT {start_scene_seq: N, end_scene_seq: NULL}]->(:Hospital)`。
4.  **持久化**：利用 Memgraph 的事务，原子性地写入 Commit 结构和叙事边更新。

#### 3.2 读取流程：上下文加载 (Context Loading)
当 AI 需要生成第 N+1 场时，如何获取“当前世界状态”？

1.  **确定基准**：获取当前 Branch 的 HEAD Commit 对应的 `SceneSequence` (假设为 N)。
2.  **时序查询 (Time-Travel Query)**：
    ```cypher
    // 伪代码：查找在第 N 场依然有效的关系
    MATCH (s:Entity)-[r]->(o:Entity)
    WHERE r.start_scene_seq <= $N 
      AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $N)
    RETURN s, r, o
    ```
3.  **结果**：AI 获得的 Context 是一个干净的、符合当前时间点的切片，不会混杂未来的剧透或过去已失效的事实。

---

### 4. 针对“几百人并发”的性能优化策略

Memgraph 是高性能的，但 Python 往往是瓶颈。

1.  **连接池 (Connection Pooling)**：
    *   使用 GQLAlchemy 或 `pymgclient` 时，必须在 FastAPI 中配置连接池。每个 Request 从池中借用连接，用完归还。
2.  **异步 IO (Async/Await)**：
    *   将所有图数据库操作封装为 Async 函数。FastAPI 原生支持异步，配合 Python 3.11 的 `TaskGroup` 并发执行“状态提取”和“结构检查”。
3.  **Memgraph 索引优化**：
    *   必须为 `Entity(id)`, `SceneOrigin(sequence_index)`, `SceneVersion(commit_id)` 建立索引。
    *   Memgraph 的 Skip List 索引在内存中极快。
4.  **只读副本 (Read Replicas) - 进阶**：
    *   如果读写比极高（浏览多，写少），可以部署 Memgraph 集群，主节点写，从节点读。但在数百人规模下，**单节点 Memgraph (32GB+ RAM)** 绰绰有余。

---

### 5. 代码迁移与实施路径

#### 第一步：环境与 ORM 定义 (Week 1)
使用 GQLAlchemy 定义 Schema，替换原有的 Pydantic 模型直接操作 DB。

```python
from gqlalchemy import Node, Relationship, Field

class SceneVersion(Node):
    id: str = Field(index=True, unique=True)
    content: str
    rendered_content: str
    
class TemporalRelation(Relationship):
    start_seq: int
    end_seq: int | None = None
    relation_type: str
```

#### 第二步：实现“时序失效”逻辑 (Week 2)
编写核心 Python 服务 `WorldStateService`。

```python
async def update_world_state(entity_id, new_state, current_seq, tx):
    # 1. 查找当前有效状态
    query = """
    MATCH (e:Entity {id: $eid})-[r:STATE]->(v)
    WHERE r.end_seq IS NULL
    RETURN r
    """
    # 2. 逻辑判断：如果状态冲突，将旧边的 end_seq 设为 current_seq
    # 3. 创建新边 start_seq = current_seq
```

#### 第三步：集成 Gemini 实体清洗 (Week 3)
实现简化的 BookCoref 管道。不需训练模型，使用 Gemini 的 Few-shot 能力。
*   Prompt 策略：提供 `[Known Entities List]`，要求 Gemini 将提取的 Mention 映射到 List ID，无法映射的才标记为 New。

### 6. 结论

这个方案将 **Memgraph 的速度**、**BookCoref 的精准度** 和 **Graphiti 的动态性** 结合在了一起。

*   **可行性**：Memgraph 完全兼容 Docker 部署，适合公开网站后端；GQLAlchemy 对 Python 友好。
*   **满足预期**：
    *   **并发**：内存数据库无磁盘 I/O 瓶颈，轻松抗住数百并发。
    *   **长篇逻辑**：通过 `Temporal Edge` 解决了“长篇小说前后矛盾”的问题。
    *   **分支管理**：Git 模型保证了用户可以随时“后悔”或“分叉”而不破坏世界观的一致性。

**建议立即废弃 Kùzu 代码，直接基于 GQLAlchemy + Memgraph 启动 V3.0 后端开发。**