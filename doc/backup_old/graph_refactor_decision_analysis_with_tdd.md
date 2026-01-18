# 图数据库重构方案决策对比分析（含TDD测试规范）

**分析日期**: 2026-01-17
**对比文档**:
- `doc/graph_refactor_plan.md` (短期方案)
- `doc/图数据库架构重构方案（长期版）.md` (长期方案)

---

## 1. 核心决策对比分析

### 1.1 架构分层设计

| 决策点 | 短期方案 | 长期方案 | 更合理的选择 | 理由 |
|--------|----------|----------|--------------|------|
| **版本控制与时序状态** | 混淆在一起 | ✅ **明确分离为两个子图** | **长期方案** | 长期方案明确区分"结构子图"(Git流)和"叙事子图"(时序流),避免概念混淆 |
| **快照机制** | 未提及 | ✅ **WorldSnapshot节点** | **长期方案** | 避免每次查询都遍历Commit链,性能优势明显 |
| **时序边设计** | `start_scene_seq`/`end_scene_seq` | ✅ **同样设计+失效逻辑** | **长期方案** | 长期方案补充了完整的边失效流程(不删除旧边,只更新end_seq) |

**决策**: ✅ **采纳长期方案的双子图架构**

---

### 1.2 技术栈选型

| 组件 | 短期方案 | 长期方案 | 更合理的选择 | 理由 |
|------|----------|----------|--------------|------|
| **图数据库** | Memgraph | Memgraph | ✅ **一致** | 两方案一致,正确 |
| **ORM** | GQLAlchemy | GQLAlchemy | ✅ **一致** | 两方案一致,正确 |
| **Graphiti集成** | ❌ 建议自研 | ✅ **自研(Custom Impl)** | **长期方案** | 长期方案明确"不直接使用Graphiti库",避免Neo4j绑定 |
| **BookCoref集成** | ⚠️ 轻量级LLM消解 | ✅ **Custom Pipeline (Inspired by BookCoref)** | **长期方案** | 长期方案明确"复用三阶段管道逻辑",而非完整模型 |

**决策**: ✅ **采纳长期方案的"借鉴思想,自研实现"策略**

---

### 1.3 并发控制策略

| 决策点 | 短期方案 | 长期方案 | 更合理的选择 | 理由 |
|--------|----------|----------|--------------|------|
| **连接池** | 提及但无细节 | ✅ **明确配置(pool_size=50)** | **长期方案** | 长期方案给出具体参数 |
| **异步IO** | 提及 | ✅ **明确使用TaskGroup** | **长期方案** | 长期方案明确Python 3.11特性 |
| **乐观锁** | ❌ 未提及 | ❌ 未提及 | **需补充** | 两方案都缺失,需要在TDD中验证 |
| **索引优化** | ❌ 未提及 | ✅ **明确索引字段** | **长期方案** | 长期方案列出必须建立的索引 |

**决策**: ⚠️ **采纳长期方案,但需补充乐观锁测试**

---

### 1.4 实施路径

| 阶段 | 短期方案 | 长期方案 | 更合理的选择 | 理由 |
|------|----------|----------|--------------|------|
| **Week 1** | 环境+Schema | 环境+ORM定义 | ✅ **长期方案** | 长期方案明确"替换Pydantic直接操作DB" |
| **Week 2** | 核心API迁移 | 时序失效逻辑 | ⚠️ **混合** | 应先迁移API(短期),再实现新功能(长期) |
| **Week 3** | 时序边+实体消解 | Gemini实体清洗 | ✅ **长期方案** | 长期方案明确Prompt策略 |
| **Week 4** | 数据迁移+测试 | ❌ 未提及 | ⚠️ **短期方案** | 长期方案缺失数据迁移步骤 |

**决策**: ⚠️ **混合方案**: Week1-2采纳长期方案,Week3-4补充短期方案的迁移步骤

---

## 2. TDD测试规则与验收条件

### 2.1 测试分层策略

```
┌─────────────────────────────────────────┐
│  E2E Tests (端到端测试)                 │
│  - 完整用户场景流程                     │
│  - 性能压测                             │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Integration Tests (集成测试)           │
│  - GraphStorage + Memgraph              │
│  - 时序边失效逻辑                       │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  Unit Tests (单元测试)                  │
│  - ORM模型验证                          │
│  - 实体消解逻辑                         │
└─────────────────────────────────────────┘
```

---

### 2.2 核心功能测试规范

#### 功能1: 双子图架构隔离

**测试目标**: 验证"结构子图"与"叙事子图"的数据隔离性

**测试用例**:
```python
class TestDualSubgraphIsolation:
    """测试双子图架构的隔离性"""

    def test_structure_subgraph_crud(self):
        """
        Given: 空数据库
        When: 创建 Branch, Commit, SceneVersion 节点
        Then:
          - 节点成功创建
          - 不影响 Entity, TemporalRelation 节点
          - 查询结构子图返回正确节点数
        """

    def test_narrative_subgraph_crud(self):
        """
        Given: 空数据库
        When: 创建 Entity, TemporalRelation 边
        Then:
          - 边成功创建
          - 不影响 Commit, SceneVersion 节点
          - 查询叙事子图返回正确边数
        """

    def test_snapshot_bridge(self):
        """
        Given: 已有 SceneVersion 和 Entity 节点
        When: 创建 ESTABLISHES_STATE 桥接边
        Then:
          - 桥接边成功创建
          - 可通过 SceneVersion 查询到关联的 WorldSnapshot
          - WorldSnapshot 包含正确的时序边快照
        """
```

**验收条件**:
- ✅ 结构子图操作不触发叙事子图查询
- ✅ 叙事子图操作不触发结构子图查询
- ✅ 快照查询延迟 < 50ms (P99)

---

#### 功能2: 时序边失效机制

**测试目标**: 验证 Graphiti 风格的边失效逻辑

**测试用例**:
```python
class TestTemporalEdgeInvalidation:
    """测试时序边失效机制"""

    def test_edge_creation_with_temporal_attributes(self):
        """
        Given: 两个 Entity 节点 (John, Home)
        When: 创建关系 John-[:AT {start_scene_seq: 1, end_scene_seq: NULL}]->Home
        Then:
          - 边成功创建
          - start_scene_seq = 1
          - end_scene_seq = NULL (表示当前有效)
        """

    def test_edge_invalidation_on_state_change(self):
        """
        Given:
          - 已有边 John-[:AT {start_seq: 1, end_seq: NULL}]->Home
          - 新状态: John at Hospital (scene_seq=5)
        When: 调用 update_world_state(john_id, "Hospital", 5)
        Then:
          - 旧边 end_seq 更新为 5
          - 新边创建: John-[:AT {start_seq: 5, end_seq: NULL}]->Hospital
          - 旧边未被删除 (保留历史)
        """

    def test_time_travel_query(self):
        """
        Given:
          - John-[:AT {start_seq: 1, end_seq: 5}]->Home
          - John-[:AT {start_seq: 5, end_seq: NULL}]->Hospital
        When: 查询 scene_seq=3 时的状态
        Then:
          - 返回 John at Home
          - 不返回 John at Hospital (未来状态)
        """

    def test_concurrent_edge_updates(self):
        """
        Given: 两个并发请求同时更新同一实体的状态
        When:
          - Request A: John at Hospital (seq=5)
          - Request B: John at Office (seq=5)
        Then:
          - 使用 Memgraph 事务隔离
          - 后提交的请求失败或覆盖
          - 数据库状态一致 (无脏数据)
        """
```

**验收条件**:
- ✅ 边失效操作原子性 (事务保证)
- ✅ 时序查询正确性 (100% 准确率)
- ✅ 并发更新无数据竞争 (隔离级别验证)
- ✅ 历史边保留完整 (可回溯)

---

#### 功能3: 实体消解管道

**测试目标**: 验证 BookCoref 风格的实体消解逻辑

**测试用例**:
```python
class TestEntityResolution:
    """测试实体消解管道"""

    def test_pronoun_resolution(self):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="John")]
          - 文本: "John走进房间。他坐下了。"
        When: 调用 resolve_entity_mentions(text, known_entities)
        Then:
          - 返回 {"John": "e1", "他": "e1"}
          - 不创建新实体
        """

    def test_duplicate_entity_prevention(self):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="Alice")]
          - 文本: "Alice和Alice的朋友见面了。"
        When: 调用 resolve_entity_mentions(text, known_entities)
        Then:
          - 两个"Alice"都映射到 e1
          - 不创建重复实体
        """

    def test_new_entity_detection(self):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="John")]
          - 文本: "John遇到了Bob。"
        When: 调用 resolve_entity_mentions(text, known_entities)
        Then:
          - 返回 {"John": "e1", "Bob": "UNKNOWN"}
          - 标记 Bob 为新实体
        """

    def test_context_aware_resolution(self):
        """
        Given:
          - 已知实体: [Entity(id="e1", name="Alice", type="Person"),
                       Entity(id="e2", name="Alice", type="Location")]
          - 文本: "Alice(人)去了Alice(地点)。"
        When: 调用 resolve_entity_mentions(text, known_entities)
        Then:
          - 根据上下文正确区分两个Alice
          - 使用 Gemini 3 Pro 的语义理解能力
        """
```

**验收条件**:
- ✅ 代词消解准确率 > 90%
- ✅ 重复实体检测准确率 > 95%
- ✅ 新实体识别召回率 > 85%
- ✅ 消解延迟 < 500ms (P95)

---

#### 功能4: 并发控制与乐观锁

**测试目标**: 验证多用户并发编辑的正确性

**测试用例**:
```python
class TestConcurrencyControl:
    """测试并发控制机制"""

    def test_optimistic_locking_on_commit(self):
        """
        Given:
          - Branch HEAD 指向 Commit A (version=1)
          - 两个用户同时读取 HEAD
        When:
          - User1 提交 Commit B (expected_head_version=1)
          - User2 提交 Commit C (expected_head_version=1)
        Then:
          - User1 提交成功, HEAD 更新为 B (version=2)
          - User2 提交失败, 返回 409 Conflict
          - User2 需要重新拉取 HEAD 并解决冲突
        """

    def test_connection_pool_exhaustion(self):
        """
        Given: 连接池大小 pool_size=50
        When: 同时发起 100 个并发请求
        Then:
          - 前 50 个请求立即获得连接
          - 后 50 个请求等待连接释放
          - 无请求因连接池耗尽而失败
          - 所有请求最终成功
        """

    def test_transaction_isolation(self):
        """
        Given: 两个事务同时修改同一 Entity 的 semantic_states
        When:
          - Tx1: UPDATE Entity SET states = {"hp": 50}
          - Tx2: UPDATE Entity SET states = {"hp": 80}
        Then:
          - 使用 Memgraph 的 READ_COMMITTED 隔离级别
          - 后提交的事务覆盖前者
          - 无脏读、不可重复读
        """

    def test_deadlock_prevention(self):
        """
        Given: 两个事务交叉访问资源
        When:
          - Tx1: 锁定 Entity A, 尝试锁定 Entity B
          - Tx2: 锁定 Entity B, 尝试锁定 Entity A
        Then:
          - Memgraph 检测到死锁
          - 回滚其中一个事务
          - 另一个事务成功提交
        """
```

**验收条件**:
- ✅ 乐观锁冲突检测率 100%
- ✅ 连接池利用率 > 80% (无空闲浪费)
- ✅ 事务隔离级别符合 ACID
- ✅ 死锁自动恢复 (无需人工干预)

---

#### 功能5: 性能基准测试

**测试目标**: 验证"数百人并发"的性能承诺

**测试场景**:
```python
class TestPerformanceBenchmark:
    """性能基准测试"""

    def test_read_scene_context_latency(self):
        """
        Given: 数据库包含 1000 个场景, 500 个实体
        When: 100 个并发用户同时调用 get_scene_context()
        Then:
          - P50 延迟 < 20ms
          - P95 延迟 < 50ms
          - P99 延迟 < 100ms
          - 无请求超时
        """

    def test_commit_scene_throughput(self):
        """
        Given: 数据库包含 1000 个场景
        When: 50 个并发用户同时提交场景修改
        Then:
          - 吞吐量 > 100 commits/sec
          - P99 延迟 < 200ms
          - 无事务回滚 (除乐观锁冲突)
        """

    def test_temporal_query_performance(self):
        """
        Given:
          - 数据库包含 10000 条时序边
          - 查询 scene_seq=500 时的状态
        When: 执行时序查询
        Then:
          - 查询延迟 < 30ms
          - 使用索引 (EXPLAIN 验证)
          - 无全表扫描
        """

    def test_memory_usage_under_load(self):
        """
        Given: Memgraph 配置 32GB 内存
        When:
          - 数据库包含 10000 场景, 5000 实体
          - 100 并发用户持续读写 10 分钟
        Then:
          - 内存占用 < 20GB
          - 无 OOM 错误
          - GC 暂停 < 100ms
        """
```

**验收条件**:
- ✅ 读操作 P99 < 100ms
- ✅ 写操作 P99 < 200ms
- ✅ 吞吐量 > 100 QPS (混合读写)
- ✅ 内存占用 < 配置上限的 70%

---

### 2.3 数据迁移测试规范

**测试目标**: 验证 Kùzu → Memgraph 数据迁移的正确性

**测试用例**:
```python
class TestDataMigration:
    """测试数据迁移流程"""

    def test_schema_mapping_correctness(self):
        """
        Given: Kùzu 数据库包含 Root, Scene, Entity 节点
        When: 执行迁移脚本
        Then:
          - Memgraph 中创建对应的节点
          - 字段映射正确 (如 Kùzu.id → Memgraph.id)
          - 数据类型一致 (STRING, INT, BOOLEAN)
        """

    def test_relationship_preservation(self):
        """
        Given: Kùzu 中存在 SceneNext, EntityRelation 边
        When: 执行迁移脚本
        Then:
          - Memgraph 中创建对应的边
          - 边属性完整 (branch_id, tension 等)
          - 边方向正确 (FROM → TO)
        """

    def test_data_integrity_validation(self):
        """
        Given: 迁移完成
        When: 对比 Kùzu 和 Memgraph 数据
        Then:
          - 节点数量一致
          - 边数量一致
          - 随机抽样 100 个节点, 属性值一致
          - 查询结果一致 (如 get_root_snapshot)
        """

    def test_rollback_on_failure(self):
        """
        Given: 迁移过程中发生错误 (如网络中断)
        When: 迁移脚本检测到错误
        Then:
          - 自动回滚 Memgraph 事务
          - Kùzu 数据不受影响
          - 可重新执行迁移
        """
```

**验收条件**:
- ✅ 数据完整性 100% (无丢失)
- ✅ 迁移速度 > 1000 节点/秒
- ✅ 迁移失败自动回滚
- ✅ 迁移后功能测试全部通过

---

## 3. 综合决策建议

### 3.1 架构决策矩阵

| 决策维度 | 短期方案评分 | 长期方案评分 | 最终决策 |
|----------|--------------|--------------|----------|
| **架构清晰度** | 5/10 (混淆) | 9/10 (分层明确) | ✅ 长期方案 |
| **技术可行性** | 7/10 | 8/10 (细节更完善) | ✅ 长期方案 |
| **实施完整性** | 6/10 (缺迁移) | 5/10 (缺迁移+测试) | ⚠️ 混合 |
| **性能优化** | 4/10 (无细节) | 8/10 (明确策略) | ✅ 长期方案 |
| **可测试性** | 3/10 (无TDD) | 3/10 (无TDD) | ⚠️ 需补充 |

### 3.2 最终推荐方案

**采纳长期方案的核心架构 + 补充短期方案的迁移步骤 + 新增TDD测试规范**

#### 修正后的实施路径 (5周)

| 周次 | 任务 | 交付物 | TDD验收 |
|------|------|--------|---------|
| **Week 1** | Memgraph环境 + GQLAlchemy ORM | Docker Compose + ORM模型 | 单元测试通过 |
| **Week 2** | 双子图架构实现 + 时序边逻辑 | WorldStateService | 集成测试通过 |
| **Week 3** | 实体消解管道 + 并发控制 | EntityResolver + 乐观锁 | 并发测试通过 |
| **Week 4** | 数据迁移脚本 + 回滚机制 | migration.py | 迁移测试通过 |
| **Week 5** | 性能压测 + 文档完善 | 压测报告 + API文档 | 性能基准达标 |

---

### 3.3 关键决策总结

#### ✅ 采纳长期方案的决策:
1. **双子图架构** - 明确分离版本控制与时序状态
2. **快照机制** - WorldSnapshot 节点提升查询性能
3. **自研时序边** - 避免 Graphiti 的 Neo4j 绑定
4. **轻量级实体消解** - 使用 Gemini 3 Pro 而非完整 BookCoref
5. **明确的性能优化策略** - 连接池、索引、异步IO

#### ⚠️ 需补充的内容:
1. **数据迁移方案** - 从短期方案补充
2. **TDD测试规范** - 本文档新增
3. **乐观锁机制** - 两方案都缺失,需实现
4. **性能基准测试** - 两方案都缺失,需实现

#### ❌ 拒绝的决策:
1. **短期方案的架构混淆** - 版本控制与时序状态未分离
2. **完整集成 Graphiti** - 维护成本高,不适配小说场景
3. **完整集成 BookCoref** - 实时性差,成本过高

---

## 4. TDD实施检查清单

### 4.1 测试覆盖率要求

| 模块 | 单元测试覆盖率 | 集成测试覆盖率 | E2E测试覆盖率 |
|------|----------------|----------------|---------------|
| GraphStorage (ORM) | > 90% | > 80% | N/A |
| WorldStateService | > 85% | > 90% | > 70% |
| EntityResolver | > 80% | > 75% | N/A |
| API Endpoints | > 70% | > 85% | > 90% |

### 4.2 CI/CD集成要求

```yaml
# .github/workflows/test.yml
name: TDD Test Pipeline

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run Unit Tests
        run: pytest tests/unit --cov=app --cov-report=xml
      - name: Coverage Check
        run: |
          if [ $(coverage report | grep TOTAL | awk '{print $4}' | sed 's/%//') -lt 80 ]; then
            echo "Coverage below 80%"
            exit 1
          fi

  integration-tests:
    runs-on: ubuntu-latest
    services:
      memgraph:
        image: memgraph/memgraph:latest
    steps:
      - name: Run Integration Tests
        run: pytest tests/integration

  performance-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run Performance Benchmark
        run: pytest tests/performance --benchmark-only
      - name: Validate Latency
        run: |
          # P99 < 100ms for reads
          # P99 < 200ms for writes
```

### 4.3 测试数据管理

```python
# tests/fixtures/test_data.py
import pytest
from app.storage.graph import GraphStorage

@pytest.fixture
def sample_root():
    """提供标准测试用的 Root 数据"""
    return {
        "id": "root_test_001",
        "logline": "测试故事核心",
        "theme": "测试主题",
        "ending": "测试结局"
    }

@pytest.fixture
def sample_entities():
    """提供标准测试用的 Entity 数据"""
    return [
        {"id": "e1", "name": "John", "type": "Character"},
        {"id": "e2", "name": "Alice", "type": "Character"},
        {"id": "e3", "name": "Home", "type": "Location"}
    ]

@pytest.fixture
def clean_db():
    """每个测试前清空数据库"""
    db = GraphStorage(db_path=":memory:")
    yield db
    db.close()
```

---

## 5. 风险缓解措施

### 5.1 技术风险

| 风险 | 缓解措施 | 验证方式 |
|------|----------|----------|
| **Memgraph性能不达标** | Week 1 进行性能POC | 压测报告 |
| **GQLAlchemy学习曲线** | Week 1 完成ORM培训 | 代码Review |
| **时序边逻辑复杂** | Week 2 编写详细设计文档 | 集成测试 |
| **数据迁移失败** | 提供回滚脚本 | 迁移测试 |

### 5.2 项目风险

| 风险 | 缓解措施 | 验证方式 |
|------|----------|----------|
| **进度延期** | 每周进行 Sprint Review | 燃尽图 |
| **需求变更** | 冻结核心需求 | 需求文档签字 |
| **人员流动** | 编写详细文档 | 知识库完整性 |

---

## 6. 结论

### 最终决策:
✅ **采纳长期方案的核心架构,补充短期方案的迁移步骤,新增完整的TDD测试规范**

### 关键优势:
1. **架构清晰** - 双子图设计避免概念混淆
2. **性能可控** - 明确的优化策略和基准测试
3. **质量保证** - 完整的TDD测试覆盖
4. **可维护性** - 自研核心逻辑,避免外部依赖

### 实施建议:
1. **立即启动 Week 1** - Memgraph 环境搭建和 POC 验证
2. **并行编写测试用例** - 在实现功能前先写测试 (TDD)
3. **每周进行代码审查** - 确保架构一致性
4. **Week 4 前完成迁移脚本** - 避免阻塞上线

---

**报告完成日期**: 2026-01-17
**建议审阅人**: 技术负责人、测试负责人、架构师
