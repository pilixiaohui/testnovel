# AI Novel V3.0 长篇小说智能创作系统技术规格

**文档版本**: 1.0
**最后更新**: 2026-01-24
**系统状态**: 生产就绪

---

## 一、系统概述

### 1.1 产品定位

AI Novel V3.0 是一个基于 Python 与 Gemini 3 的全链路长篇小说智能创作系统。系统将长篇小说定义为**自顶向下生长**与**自底向上涌现**相结合的复杂系统，通过雪花写作法提供结构化骨架，通过人机协商机制实现微观创作的灵活性。

### 1.2 核心理念：分形叙事对象

- **宏观结构 (Structure)**: 采用雪花写作法作为"编译预处理"阶段，小说由"核心概念 → 人物原型 → 剧情骨架 → 场景节点"逐级展开
- **微观协商 (Negotiation)**: 在场景节点内采用人机协商机制，每个场景的生成都是对宏观设定的实例化与微调
- **动态因果 (Causality)**: 利用 Memgraph 图数据库维护叙事真值，支持一致性检查与多米诺重构

### 1.3 解决的核心矛盾

1. **"写得长"与"记得住"**: 通过雪花层级索引解决，AI 只需读取当前层级的结构数据 + 当前场景的动态状态
2. **"计划性"与"意外感"**: 雪花提供计划，协商机制提供意外，系统允许微观偏离并自动计算逻辑代价与修复方案

### 1.4 代码规模统计

| 类别 | 数量 |
|------|------|
| 应用代码 | 5,013 行 |
| 测试代码 | 7,905 行 |
| 类 | 79 个 |
| 方法/函数 | 289 个 |
| 异步函数 | 71 个 |
| API 端点 | 32 个 |
| 测试函数 | 195 个 |

---

## 二、技术栈与全局约束

### 2.1 技术栈锁定

| 组件 | 技术选型 | 版本要求 |
|------|----------|----------|
| 开发语言 | Python | 3.11+ |
| Web 框架 | FastAPI | >= 0.111.0 |
| 数据验证 | Pydantic | >= 2.7.0 |
| 图数据库 | Memgraph | 最新稳定版 |
| 图数据库 ORM | GQLAlchemy | >= 1.4.0 |
| 图数据库驱动 | neo4j | >= 5.0.0, < 6.0.0 |
| HTTP 客户端 | httpx | >= 0.27.0 |
| ASGI 服务器 | uvicorn | >= 0.30.0 |
| 结构化输出 | instructor | >= 1.3.3 |

### 2.2 LLM 服务配置

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| API 密钥 | `TOPONE_API_KEY` | (必填) |
| 基础 URL | `TOPONE_BASE_URL` | `https://api.toponeapi.top` |
| 默认模型 | `TOPONE_DEFAULT_MODEL` | `gemini-3-pro-preview-11-2025` |
| 快速模型 | `TOPONE_SECONDARY_MODEL` | `gemini-3-flash-preview` |
| 超时时间 | `TOPONE_TIMEOUT_SECONDS` | 30 |

**LLM 角色分工**:
- **ARCHITECT**: 宏观规划，执行雪花法前 4 步
- **REASONING**: 逻辑检察官，检测逻辑漏洞
- **CREATIVE**: 文学渲染，文本生成
- **FLASH**: 快速处理，状态提取

### 2.3 数据库配置

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 主机 | `MEMGRAPH_HOST` | (必填) |
| 端口 | `MEMGRAPH_PORT` | (必填) |
| 连接池最小 | `MEMGRAPH_POOL_MIN` | 10 |
| 连接池最大 | `MEMGRAPH_POOL_MAX` | 100 |
| 获取超时 | `MEMGRAPH_POOL_ACQUIRE_TIMEOUT` | 30.0 |
| 空闲超时 | `MEMGRAPH_POOL_IDLE_TIMEOUT` | 300.0 |

### 2.4 业务配置

| 配置项 | 环境变量 | 默认值 |
|--------|----------|--------|
| 引擎模式 | `SNOWFLAKE_ENGINE` | (必填: local/llm/gemini) |
| 最小场景数 | `SCENE_MIN_COUNT` | 50 |
| 最大场景数 | `SCENE_MAX_COUNT` | 100 |

---

## 三、项目拓扑

### 3.1 目录结构

```
project/backend/
├── app/
│   ├── main.py                    # FastAPI 应用入口，32 个 API 端点 (1,191 行)
│   ├── models.py                  # Pydantic 数据模型 (110 行)
│   ├── config.py                  # 配置管理
│   ├── ports.py                   # 存储接口定义 (179 行)
│   ├── storage/
│   │   ├── memgraph_storage.py    # 核心存储实现 (1,740 行)
│   │   ├── schema.py              # GQLAlchemy ORM 模型 (130 行)
│   │   ├── temporal_edge.py       # 时序边管理 (162 行)
│   │   └── snapshot.py            # 快照机制 (82 行)
│   ├── services/
│   │   ├── world_state_service.py # 世界状态服务 (97 行)
│   │   ├── entity_resolver.py     # 实体消解 (83 行)
│   │   ├── impact_analyzer.py     # 影响分析 (112 行)
│   │   ├── dependency_matrix.py   # 依赖矩阵 (75 行)
│   │   └── llm_engine.py          # LLM 引擎 (205 行)
│   ├── llm/
│   │   ├── topone_client.py       # TopOne 客户端 (112 行)
│   │   └── topone_gateway.py      # TopOne 网关 (171 行)
│   └── utils/
│       └── graph_algorithms.py    # 图算法工具
├── scripts/
│   ├── migrate_kuzu_to_memgraph.py # 数据迁移脚本 (99 行)
│   └── performance_benchmark.py    # 性能压测脚本
├── tests/
│   ├── unit/                      # 单元测试
│   ├── integration/               # 集成测试
│   └── performance/               # 性能测试
├── docker-compose.memgraph.yml    # Docker 配置
└── pyproject.toml                 # 项目依赖
```

### 3.2 文件职责表

| 文件 | 职责 |
|------|------|
| `main.py` | FastAPI 应用入口，定义所有 API 端点，依赖注入配置 |
| `models.py` | 32 个 Pydantic 数据模型，API 请求/响应结构 |
| `ports.py` | GraphStoragePort 接口定义，存储层抽象 |
| `memgraph_storage.py` | 核心存储实现，60+ 方法，连接池管理，三层缓存 |
| `schema.py` | 10 个 GQLAlchemy 节点/边模型定义 |
| `temporal_edge.py` | 时序边失效逻辑，时间旅行查询 |
| `snapshot.py` | 快照创建策略，每 10 场景创建快照 |
| `world_state_service.py` | 世界状态查询，快照+增量混合 |
| `entity_resolver.py` | 实体消解，代词解析，Gemini Flash 集成 |
| `impact_analyzer.py` | 影响分析，受影响场景识别 |
| `dependency_matrix.py` | 依赖矩阵构建，影响查询优化 |
| `llm_engine.py` | LLM 引擎封装，雪花流程调用 |
| `topone_client.py` | TopOne API 客户端，请求构建 |
| `topone_gateway.py` | TopOne 网关，结构化输出，场景渲染 |

---

## 四、全局数据契约

### 4.1 双子图架构

系统图谱分为两个独立但互联的子图：

**结构子图 (Structure Subgraph)** - 管理写作过程的版本控制
- 节点: `Root`, `Branch`, `BranchHead`, `Commit`, `SceneOrigin`, `SceneVersion`
- 边: `HEAD`, `PARENT`, `INCLUDES`, `OF_ORIGIN`

**叙事子图 (Narrative Subgraph)** - 管理故事世界观的动态演变
- 节点: `Entity`, `WorldSnapshot`
- 边: `TemporalRelation` (带 start_scene_seq/end_scene_seq)

**桥接关系**: `[:ESTABLISHES_STATE]` 连接 SceneVersion 和 WorldSnapshot

### 4.2 节点类型定义 (10 个)

#### Root (故事根节点)
```python
class Root:
    id: str              # 唯一标识 (索引)
    logline: str         # 一句话核心
    theme: str           # 核心主旨
    ending: str          # 结局
    created_at: datetime # 创建时间
```

#### Branch (分支节点)
```python
class Branch:
    id: str                    # 格式: root_id:branch_id (索引)
    root_id: str               # 所属根节点 (索引)
    branch_id: str             # 分支标识 (索引)
    parent_branch_id: str      # 父分支
    fork_scene_origin_id: str  # 分叉点场景
    fork_commit_id: str        # 分叉点提交
```

#### BranchHead (分支头指针)
```python
class BranchHead:
    id: str             # 格式: root_id:branch_id:head (索引)
    root_id: str        # 所属根节点
    branch_id: str      # 分支标识
    head_commit_id: str # 当前提交
    version: int        # 乐观锁版本号 (并发控制)
```

#### Commit (提交节点)
```python
class Commit:
    id: str              # 唯一标识 (索引)
    parent_id: str       # 父提交
    message: str         # 提交信息
    created_at: datetime # 创建时间
    root_id: str         # 所属根节点 (索引)
    branch_id: str       # 所属分支
```

#### SceneOrigin (场景身份节点)
```python
class SceneOrigin:
    id: str               # 唯一标识 (索引)
    root_id: str          # 所属根节点
    title: str            # 场景标题 (不可变)
    initial_commit_id: str # 初始提交
    sequence_index: int   # 序号 (关键索引)
    parent_act_id: str    # 所属幕
```

#### SceneVersion (场景版本节点)
```python
class SceneVersion:
    id: str                    # 唯一标识 (索引)
    scene_origin_id: str       # 关联场景原点 (索引)
    commit_id: str             # 关联提交 (索引)
    pov_character_id: str      # 视点人物
    status: str                # 状态
    expected_outcome: str      # 大纲计划结果
    conflict_type: str         # 冲突类型
    actual_outcome: str        # 实际结果
    summary: str               # 摘要
    rendered_content: str      # 渲染内容
    logic_exception: bool      # 逻辑例外标记
    logic_exception_reason: str # 例外原因
    dirty: bool                # 脏标记
```

#### Entity (实体节点)
```python
class Entity:
    id: str                       # 唯一标识 (索引)
    root_id: str                  # 所属根节点
    branch_id: str                # 所属分支 (索引)
    entity_type: str              # 类型: Character, Location, Item
    name: str                     # 名称
    tags: List[str]               # 标签
    semantic_states: Dict[str,str] # 语义状态快照
    arc_status: str               # 弧线状态
```

#### WorldSnapshot (世界状态快照)
```python
class WorldSnapshot:
    id: str                       # 唯一标识 (索引)
    scene_version_id: str         # 关联场景版本 (索引)
    branch_id: str                # 分支标识
    scene_seq: int                # 场景序号 (索引)
    entity_states: Dict           # JSON 序列化的完整世界状态
    relations: List               # 关系列表
```

### 4.3 时序边定义

#### TemporalRelation (时序关系边)
```python
class TemporalRelation:
    relation_type: str      # 关系类型: HATES, LOVES, AT, HAS 等
    tension: int            # 叙事张力值 (0-100)
    start_scene_seq: int    # 生效场景序号 (索引)
    end_scene_seq: int|None # 失效场景序号, NULL=当前有效 (索引)
    branch_id: str          # 分支标识 (索引)
    created_at: datetime    # 创建时间
    invalidated_at: datetime|None # 失效时间
```

**时序查询模式**:
```cypher
WHERE r.branch_id = $branch_id
  AND r.start_scene_seq <= $scene_seq
  AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $scene_seq)
```

### 4.4 索引策略 (16 个索引)

**结构子图索引**:
- `Root(id)`
- `Branch(id)`, `Branch(root_id, branch_id)`
- `BranchHead(id)`, `BranchHead(root_id, branch_id)`
- `Commit(id)`, `Commit(root_id)`
- `SceneOrigin(id)`, `SceneOrigin(root_id, sequence_index)`
- `SceneVersion(id)`, `SceneVersion(scene_origin_id)`, `SceneVersion(commit_id)`

**叙事子图索引**:
- `Entity(id)`, `Entity(branch_id)`, `Entity(root_id, branch_id)`
- `WorldSnapshot(id)`, `WorldSnapshot(scene_version_id)`, `WorldSnapshot(branch_id, scene_seq)`

**时序边索引**:
- `TemporalRelation(branch_id, start_scene_seq)`
- `TemporalRelation(branch_id, end_scene_seq)`

### 4.5 Pydantic 模型 (32 个)

**雪花流程模型**:
- `IdeaPayload`, `LoglinePayload`, `ScenePayload`
- `Step4Result`

**分支管理模型**:
- `BranchView`, `BranchPayload`
- `ForkFromCommitPayload`, `ForkFromScenePayload`, `ResetBranchPayload`

**实体管理模型**:
- `EntityView`, `EntityRelationView`
- `CreateEntityPayload`, `UpsertRelationPayload`

**场景管理模型**:
- `SceneView`, `SceneContextView`
- `SceneCompletePayload`, `SceneCompletionOrchestratePayload`
- `SceneCompletionResult`, `SceneRenderResult`
- `CreateSceneOriginPayload`, `CreateSceneOriginResult`, `DeleteSceneOriginPayload`
- `SceneReorderPayload`, `SceneReorderResult`

**提交管理模型**:
- `CommitScenePayload`, `CommitResult`
- `GcPayload`, `GcResult`

**视图模型**:
- `RootGraphView`, `StructureTreeView`, `StructureTreeActView`

---

## 五、API 端点定义 (32 个)

### 5.1 雪花流程 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/snowflake/step1` | 生成 10 个 logline 选项 |
| POST | `/api/v1/snowflake/step2` | 生成故事结构 (Root) |
| POST | `/api/v1/snowflake/step3` | 生成角色小传 |
| POST | `/api/v1/snowflake/step4` | 生成场景列表 (50-100 个) |

### 5.2 分支管理 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/roots/{root_id}/branches` | 创建分支 |
| GET | `/api/v1/roots/{root_id}/branches` | 列出分支 |
| POST | `/api/v1/roots/{root_id}/branches/{branch_id}/switch` | 切换分支 |
| POST | `/api/v1/roots/{root_id}/branches/{branch_id}/merge` | 合并分支 |
| POST | `/api/v1/roots/{root_id}/branches/{branch_id}/revert` | 回滚分支 |
| POST | `/api/v1/roots/{root_id}/branches/fork_from_commit` | 从提交创建分支 |
| POST | `/api/v1/roots/{root_id}/branches/fork_from_scene` | 从场景创建分支 |
| POST | `/api/v1/roots/{root_id}/branches/{branch_id}/reset` | 重置分支 |
| GET | `/api/v1/roots/{root_id}/branches/{branch_id}/history` | 获取分支历史 |

### 5.3 场景管理 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/roots/{root_id}/scene_origins` | 创建场景 |
| POST | `/api/v1/roots/{root_id}/scenes/{scene_id}/delete` | 删除场景 |
| POST | `/api/v1/scenes/{scene_id}/complete` | 完成场景 |
| POST | `/api/v1/scenes/{scene_id}/complete/orchestrated` | 编排完成场景 (含逻辑检查) |
| POST | `/api/v1/scenes/{scene_id}/render` | 渲染场景 |
| GET | `/api/v1/scenes/{scene_id}/context` | 获取场景上下文 |
| GET | `/api/v1/scenes/{scene_id}/diff` | 比较场景版本 |
| POST | `/api/v1/scenes/{scene_id}/dirty` | 标记场景为脏 |

### 5.4 实体管理 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/roots/{root_id}/entities` | 创建实体 |
| GET | `/api/v1/roots/{root_id}/entities` | 列出实体 |
| POST | `/api/v1/roots/{root_id}/relations` | 创建/更新关系 |

### 5.5 查询 API

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/v1/roots/{root_id}` | 获取根节点快照 |
| GET | `/api/v1/roots/{root_id}/dirty_scenes` | 列出脏场景 |

### 5.6 提交 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/roots/{root_id}/branches/{branch_id}/commit` | 提交场景 |
| POST | `/api/v1/commits/gc` | 垃圾回收孤立提交 |

### 5.7 LLM 和逻辑检查 API

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/api/v1/llm/topone/generate` | 调用 TopOne Gemini |
| POST | `/api/v1/logic/check` | 逻辑检查 |
| POST | `/api/v1/state/extract` | 状态提取 |
| POST | `/api/v1/state/commit` | 提交状态 |

---

## 六、核心算法实现

### 6.1 时序边管理算法

**文件**: `app/storage/temporal_edge.py`

**功能**: 追踪实体状态的完整变化历史，支持时间旅行查询。

**创建/更新关系算法**:
```
输入: from_entity_id, to_entity_id, relation_type, tension, scene_seq, branch_id

步骤:
1. 查找所有活跃的同类型关系:
   WHERE start_scene_seq <= current_seq AND end_scene_seq IS NULL
2. 将这些关系的 end_scene_seq 设置为 current_seq (失效旧边)
3. 创建新关系:
   start_scene_seq = current_seq
   end_scene_seq = NULL
4. 使用事务保证原子性
```

**时间旅行查询算法**:
```
输入: from_entity_id, branch_id, target_scene_seq

查询条件:
WHERE r.branch_id = $branch_id
  AND r.start_scene_seq <= $target_scene_seq
  AND (r.end_scene_seq IS NULL OR r.end_scene_seq > $target_scene_seq)

返回: 该时间点的所有活跃关系
```

### 6.2 快照机制算法

**文件**: `app/storage/snapshot.py`

**功能**: 优化历史状态查询性能，避免遍历所有时序边。

**快照创建规则**:
```python
def should_create_snapshot(scene_seq: int) -> bool:
    return scene_seq > 0 and scene_seq % 10 == 0
```

**世界状态查询优化算法**:
```
输入: branch_id, target_scene_seq

步骤:
1. 计算最近快照点: snapshot_seq = (target_seq // 10) * 10
2. 查询快照节点获取基础状态
3. 如果 snapshot_seq < target_seq:
   - 查询增量变更: start_seq > snapshot_seq AND start_seq <= target_seq
   - 应用增量变更到基础状态
4. 返回完整世界状态

复杂度分析:
- 最坏情况: O(E×10) - 从快照回放 10 个场景
- 最好情况: O(1) - 直接命中快照
- 平均情况: O(E×5)
```

### 6.3 影响分析算法

**文件**: `app/services/impact_analyzer.py`, `app/services/dependency_matrix.py`

**功能**: 分析场景修改对后续剧情的影响，生成修复建议。

**依赖矩阵构建**:
```
输入: scene_entities (场景-实体关系列表)

步骤:
1. 构建 entity_to_scenes 索引: Dict[entity_id, Set[scene_seq]]
2. 遍历 scene_entities，填充索引
3. 缓存矩阵，key = (root_id, branch_id)

复杂度: O(S×E) 首次构建
```

**影响查询算法**:
```
输入: modified_scene_seq, state_changes (实体状态变更列表)

步骤:
1. 提取受影响实体 ID 列表
2. 使用依赖矩阵查询这些实体涉及的所有场景
3. 过滤出 modified_scene_seq 之后的场景
4. 计算影响严重程度:
   - 1 个变化: low
   - 2 个变化: medium
   - 3+ 个变化: high
5. 生成影响原因说明

复杂度: O(E) 后续查询 (矩阵缓存命中时)
```

### 6.4 分支管理算法

**文件**: `app/storage/memgraph_storage.py`

**创建分支**:
```
输入: root_id, branch_id, source_branch_id

步骤:
1. 获取源分支的 HEAD 提交
2. 创建 Branch 节点: fork_commit_id = HEAD
3. 创建 BranchHead 节点: head_commit_id = HEAD, version = 1
4. 返回新分支信息
```

**提交场景**:
```
输入: root_id, branch_id, scene_version_data

步骤:
1. 获取当前 BranchHead
2. 创建新 Commit: parent_id = head_commit_id
3. 创建新 SceneVersion: commit_id = new_commit_id
4. 更新 BranchHead: head_commit_id = new_commit_id, version += 1
5. 使用乐观锁检测并发冲突
```

**合并分支**:
```
输入: root_id, source_branch_id, target_branch_id

步骤:
1. 获取源分支的 HEAD 提交
2. 创建合并提交: parent_id = target_HEAD
3. 更新目标分支 HEAD
4. 保留分支历史链
```

### 6.5 实体消解算法

**文件**: `app/services/entity_resolver.py`

**功能**: 识别文本中的实体提及，解析代词指代。

**全量解析**:
```
输入: text, known_entities

步骤:
1. 调用 Gemini Flash API 提取实体提及
2. 返回 mention -> entity_id 映射
```

**增量解析**:
```
输入: text, known_entities, mention_cache

步骤:
1. 提取文本中的实体提及
2. 检查 mention_cache 中是否已有映射
3. 对未解析的提及调用 Gemini Flash
4. 更新 mention_cache
5. 返回完整映射
```

### 6.6 逻辑检查算法

**功能**: 检查用户意图是否破坏世界观或故事结构。

**检查流程**:
```
输入: outline_requirement, world_state, user_intent, force_execute

步骤:
1. 如果 force_execute = true:
   - 直接通过，标记 "剧情服务于戏剧性"
2. 否则:
   - 检查能力值对比 (逻辑性)
   - 检查大纲一致性
   - 返回 ok/decision/impact_level
```

---

## 七、业务流程

### 7.1 雪花流程数据流

```
用户想法
  ↓
Step 1: POST /api/v1/snowflake/step1
  → 生成 10 个 logline 选项
  ↓
用户选择 logline
  ↓
Step 2: POST /api/v1/snowflake/step2
  → 扩展成故事结构 (Root)
  ├─ logline
  ├─ three_disasters (3 个灾难)
  ├─ ending
  └─ theme
  ↓
Step 3: POST /api/v1/snowflake/step3
  → 生成角色小传
  ├─ name, ambition, conflict, epiphany, voice_dna
  └─ 验证角色与主线冲突
  ↓
Step 4: POST /api/v1/snowflake/step4
  → 生成场景列表 (50-100 个)
  ├─ expected_outcome
  ├─ conflict_type
  ├─ pov_character_id (循环分配)
  └─ 保存到数据库
  ↓
Root + Characters + Scenes 持久化
```

### 7.2 场景完成数据流

```
场景内容输入
  ↓
逻辑检查 (POST /api/v1/logic/check)
  ├─ 检查 outline_requirement 是否满足
  ├─ 检查 world_state 是否一致
  ├─ 返回 ok/decision/impact_level
  └─ 如果失败且非 force_execute，拒绝
  ↓
状态提取 (POST /api/v1/state/extract)
  ├─ 从内容中提取语义状态变化
  ├─ 为每个实体生成 semantic_states_patch
  └─ 返回提议列表
  ↓
用户确认提议 (HITL)
  ↓
应用状态变化
  ├─ 更新实体的 semantic_states
  ├─ 创建 TemporalRelation (时序边)
  ├─ 创建 WorldSnapshot (如果 scene_seq % 10 == 0)
  └─ 标记受影响的场景为脏
  ↓
完成场景
  ├─ 更新 SceneVersion (actual_outcome, summary)
  ├─ 创建新 Commit
  └─ 更新 BranchHead
```

### 7.3 场景渲染数据流

```
场景上下文 (GET /api/v1/scenes/{id}/context)
  ├─ voice_dna (角色语气)
  ├─ conflict_type (冲突类型)
  ├─ outline_requirement (大纲要求)
  ├─ user_intent (用户意图)
  ├─ expected_outcome (预期结果)
  └─ world_state (世界状态)
  ↓
调用 TopOne Gemini 渲染 (POST /api/v1/scenes/{id}/render)
  ├─ 如果 logic_exception，添加"戏剧性优先"指令
  └─ 返回纯文本场景内容
  ↓
保存渲染内容
  └─ 更新 SceneVersion.rendered_content
```

### 7.4 懒惰计算与局部修复

**策略一: 局部修复 (Local Patching)**
- 触发条件: `actual_outcome` 与 `expected_outcome` 出现中度偏差
- 收敛窗口: 仅修改未来最近的 3 个节点
- 任务目标: 使剧情在第 N+4 个场景回归原大纲轨道

**策略二: 脏标记机制 (Dirty Flags)**
- 触发条件: 偏差过大，无法在 3 个节点内收敛
- 处理方式: 将远端受影响场景标记为 `dirty = true`
- 延迟重构: 只有用户进入 DIRTY 节点时才触发重构

---

## 八、性能指标

### 8.1 查询性能目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 简单查询延迟 (P95) | < 200ms | 单节点/单边查询 |
| 复杂查询延迟 (P95) | < 500ms | 时序范围/多跳遍历 |
| 快照直接命中 (P95) | < 100ms | 快照查询 |
| 写操作延迟 (P95) | < 300ms | 含事务提交 |

### 8.2 吞吐量与并发目标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 吞吐量 | > 50 QPS | 混合读写 |
| 并发用户数 | > 50 | 保守估计 |
| 内存占用 | < 20GB | 32GB 配置下 |
| 连接池获取时间 | < 10ms | 平均值 |
| 缓存命中率 | > 80% | 实体/关系缓存 |

### 8.3 实体消解性能目标

| 指标 | 目标值 |
|------|--------|
| 常见代词消解成功率 | > 70% |
| 显式重复实体检测准确率 | > 75% |
| 新实体识别召回率 | > 65% |
| 单场景增量消解延迟 (P95) | < 2000ms |
| 全书消解耗时 (200场景) | < 5分钟 |

### 8.4 影响分析性能目标

| 指标 | 目标值 |
|------|--------|
| 依赖矩阵支持规模 | 1000 场景 × 100 实体 |
| 影响传播深度 | 3 级 (收敛窗口) |
| 缓存命中时查询延迟 (P95) | < 500ms |
| 首次矩阵构建 | O(S×E) |
| 后续查询 | O(E) |

### 8.5 可扩展性目标

| 指标 | 目标值 |
|------|--------|
| 支持故事数 | 1000+ |
| 支持场景数 | 10000+ |
| 支持实体数 | 1000+ |
| 支持并发用户 | 100+ |

---

## 九、测试规范

### 9.1 测试分层

| 层级 | 目录 | 职责 |
|------|------|------|
| 单元测试 | `tests/unit/` | ORM 模型验证，数据转换逻辑 |
| 集成测试 | `tests/integration/` | GraphStorage + Memgraph, 服务层集成 |
| 性能测试 | `tests/performance/` | 压测，基准测试 |

### 9.2 测试文件清单

**单元测试 (tests/unit/)**:
- `test_schema.py` - GQLAlchemy 模型验证
- `test_entity_resolver.py` - 实体消解单元测试
- `test_impact_analyzer.py` - 影响分析单元测试
- `test_dependency_matrix.py` - 依赖矩阵单元测试
- `test_config.py` - 配置验证
- `test_topone_gateway_structured.py` - TopOne 网关测试
- `test_llm_engine_additional.py` - LLM 引擎测试
- `test_local_story_engine.py` - 本地引擎测试

**集成测试 (tests/integration/)**:
- `test_memgraph_storage.py` - 存储 CRUD 操作 (928 行)
- `test_temporal_edge.py` - 时序边管理 (372 行)
- `test_snapshot.py` - 快照创建和查询 (281 行)
- `test_dual_subgraph.py` - 双子图隔离验证 (372 行)
- `test_structure_edges.py` - 结构边完整测试 (855 行)
- `test_world_state_service.py` - 世界状态服务 (387 行)
- `test_entity_resolver.py` - 实体消解集成 (189 行)
- `test_impact_analyzer.py` - 影响分析集成 (137 行)
- `test_migration.py` - 数据迁移验证 (368 行)

**性能测试 (tests/performance/)**:
- `test_benchmark.py` - 性能基准测试
- `test_entity_resolution.py` - 实体消解性能测试

### 9.3 核心测试用例

**测试 1: 双子图架构隔离**
```
Given: 空数据库
When: 创建结构子图节点
Then: 不影响叙事子图，查询正确
```

**测试 2: 时序边失效机制**
```
Given: 已有边 John-[:AT {start_seq: 1, end_seq: NULL}]->Home
When: 更新状态 John at Hospital (scene_seq=5)
Then: 旧边 end_seq=5, 新边 start_seq=5, 旧边未删除
```

**测试 3: 时间旅行查询**
```
Given: John-[:AT {start_seq: 1, end_seq: 5}]->Home
       John-[:AT {start_seq: 5, end_seq: NULL}]->Hospital
When: 查询 scene_seq=3
Then: 返回 John at Home
```

**测试 4: 实体消解 - 代词**
```
Given: 已知实体 [John], 文本 "John走进房间。他坐下了。"
When: 调用 resolve_mentions
Then: {"John": "e1", "他": "e1"}
```

**测试 5: 影响分析**
```
Given: 修改 scene 5, 状态变更 [john.hp: 100% → 10%]
When: 调用 analyze_scene_impact
Then: 返回受影响场景列表，包含 severity 和 reason
```

### 9.4 测试覆盖率目标

| 模块 | 单元测试 | 集成测试 | E2E测试 |
|------|----------|----------|---------|
| GraphStorage | > 80% | > 70% | N/A |
| WorldStateService | > 75% | > 80% | > 60% |
| EntityResolver | > 70% | > 65% | N/A |
| ImpactAnalyzer | > 75% | > 70% | N/A |
| API Endpoints | > 60% | > 75% | > 60% |

### 9.5 测试执行命令

```bash
# 运行所有测试
pytest -q -rs

# 运行集成测试
pytest -q -k memgraph

# 运行性能测试
pytest -q -k benchmark

# 运行覆盖率报告
pytest --cov=app --cov-report=html
```

---

## 十、部署配置

### 10.1 Docker 部署

```bash
# 启动 Memgraph
docker compose -f project/backend/docker-compose.memgraph.yml up -d

# 启动应用
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 10.2 环境变量配置

```bash
# 必填配置
export SNOWFLAKE_ENGINE=gemini
export MEMGRAPH_HOST=localhost
export MEMGRAPH_PORT=7687
export TOPONE_API_KEY=your_key

# 可选配置
export SCENE_MIN_COUNT=50
export SCENE_MAX_COUNT=100
export MEMGRAPH_POOL_MIN=10
export MEMGRAPH_POOL_MAX=100
export MEMGRAPH_POOL_ACQUIRE_TIMEOUT=30.0
export MEMGRAPH_POOL_IDLE_TIMEOUT=300.0
export TOPONE_TIMEOUT_SECONDS=30
```

### 10.3 连接池配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| min_size | 10 | 最小连接数 |
| max_size | 100 | 最大连接数 |
| acquire_timeout | 30s | 获取连接超时 |
| idle_timeout | 300s | 空闲连接超时 |

### 10.4 缓存配置

系统使用三层缓存架构:
- `_entity_cache`: 实体缓存 (root_id, branch_id) -> 实体列表
- `_character_cache`: 角色缓存 (root_id, branch_id) -> 角色列表
- `_scene_relation_cache`: 场景关系缓存 (root_id, branch_id, scene_seq)

缓存使用线程锁保护，支持并发安全访问。

---

## 十一、错误处理

### 11.1 API 错误码

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 400 | 输入验证失败 | 场景数量不在 50-100 范围 |
| 404 | 资源不存在 | 分支/场景/实体不存在 |
| 409 | 冲突 | 分支已存在，并发冲突 |
| 500 | 服务器错误 | 数据库连接失败 |

### 11.2 业务逻辑验证

- 场景数量必须在 50-100 之间
- 场景 ID 必须唯一
- 每个场景必须有 expected_outcome 和 conflict_type
- 角色 voice_dna 不能为空
- 分支 ID 必须唯一
- 提交必须有有效的 parent_id

### 11.3 并发冲突处理

使用乐观锁机制:
1. BranchHead 节点包含 version 字段
2. 更新前查询当前 version
3. 更新时检查 version 是否匹配
4. 不匹配则抛出 `ConcurrentModificationError`

---

## 十二、监控与告警

### 12.1 关键监控指标

- API 响应时间 (P50, P95, P99)
- 数据库查询时间
- 缓存命中率
- 连接池使用率
- LLM API 调用次数和成功率
- 错误率

### 12.2 告警规则

| 指标 | Warning | Critical |
|------|---------|----------|
| P99 延迟 | > 200ms | > 500ms |
| 错误率 | > 1% | > 5% |
| 内存占用 | > 25GB | > 30GB |
| 连接池使用率 | > 80% | > 95% |

### 12.3 日志级别

- **DEBUG**: 详细的执行流程
- **INFO**: 重要事件 (API 调用、数据库操作)
- **WARNING**: 潜在问题 (缓存失效、连接超时)
- **ERROR**: 错误情况 (API 失败、数据库错误)

---

## 附录 A: 逻辑检察官 Prompt 设计

```text
你是一个严苛的小说逻辑编辑。你的任务不是写作，而是检查用户意图是否破坏了世界观或故事结构。

输入数据：
1. [当前大纲要求]：主角在本场应该遭遇挫折。
2. [世界状态]：主角持有神器(ID:X)，HP: 100%（健康），当前位置：安全屋。
3. [用户意图]：让主角在这里被一个小混混打成重伤。
4. [指令模式]：Standard | ForceExecute

分析步骤：
1. 若指令模式为 ForceExecute：直接通过，但在 reasoning 中注明"剧情服务于戏剧性，物理逻辑被重写"。
2. 若指令模式为 Standard：
   - 检查能力值对比：主角持有神器且满状态，被小混混重伤是否合理？(逻辑性)
   - 检查大纲一致性：大纲要求遭遇挫折，"重伤"符合挫折定义，但执行方式可能不合理。

输出格式：JSON (LogicCheckResult)
```

---

## 附录 B: 相关文档索引

| 文档 | 路径 | 说明 |
|------|------|------|
| API 文档 | `doc/API.md` | REST API 接口说明 |
| 部署文档 | `doc/DEPLOYMENT.md` | 部署步骤与配置 |
| 架构文档 | `doc/ARCHITECTURE.md` | 系统架构详解 |
| 性能报告 | `doc/PERFORMANCE_REPORT.md` | 性能压测结果 |
| 迁移指南 | `doc/MIGRATION_GUIDE.md` | 数据迁移说明 |

---

**文档维护说明**: 本文档整合了系统设计与技术实现，描述系统的当前实际状态。如有架构变更，请同步更新本文档。
