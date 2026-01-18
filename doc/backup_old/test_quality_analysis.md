# 测试代码质量分析报告

## 0. 分析目的

检查 `project/backend/tests/` 下的测试代码是否：
1. 符合 `doc/测试方案.md` 的预期要求
2. 存在取巧、作弊或无效测试
3. 遵循"快速失败、禁止兜底"原则

---

## 1. 测试文件概览

| 文件 | 测试数量 | 覆盖范围 |
|------|----------|----------|
| `test_api.py` | 31 个 | API 端点、协商闭环、HITL、分支管理 |
| `test_storage.py` | 13 个 | 图数据库存储、分支隔离、合并/回滚 |
| `test_models.py` | 6 个 | Pydantic 模型校验 |
| `test_snowflake_workflow.py` | 8 个 | 雪花流程编排 |
| `test_topone_client.py` | 3 个 | TopOne API 客户端 |
| `test_topone_gateway.py` | 2 个 | TopOne 网关 |
| `test_llm_service.py` | 3 个 | LLM 引擎 |

---

## 2. 有效测试分析

### 2.1 test_api.py - 有效性评估：✅ 良好

#### 优点

1. **真实数据库测试**：使用 `tmp_path` 创建真实 Kùzu 数据库，非内存 Mock
   ```python
   # test_api.py:171
   storage = GraphStorage(db_path=tmp_path / "snowflake.db")
   ```

2. **完整闭环验证**：测试不仅调用 API，还验证数据库状态变更
   ```python
   # test_api.py:364-371
   snapshot = storage.get_root_snapshot(root_id=root_id, branch_id=DEFAULT_BRANCH_ID)
   snapshot_scene = next(item for item in snapshot["scenes"] if item["id"] == str(scene.id))
   assert snapshot_scene["logic_exception"] is True
   assert snapshot_scene["logic_exception_reason"] == "force it"
   ```

3. **边界条件覆盖**：测试空 confirmed_proposals、重复分支等边界情况
   ```python
   # test_api.py:770-841 - 空 confirmed_proposals
   # test_api.py:1151-1174 - 重复分支创建
   ```

4. **背景任务验证**：验证 BackgroundTasks 被正确调度
   ```python
   # test_api.py:604-674
   assert called["func"].__name__ == "_apply_impact_level"
   ```

#### 潜在问题

1. **StubGateway 过于简单**：部分测试的 StubGateway 总是返回固定结果，未测试 LLM 返回异常情况
   ```python
   # test_api.py:338-345
   class StubGateway:
       async def logic_check(self, payload):
           return LogicCheckResult(ok=True, ...)  # 总是成功
   ```
   **建议**：增加 LLM 返回异常/超时的测试用例

2. **缺少并发测试**：未测试多个请求同时操作同一 root_id 的情况

---

### 2.2 test_storage.py - 有效性评估：✅ 良好

#### 优点

1. **快速失败验证**：测试缺少必填字段时直接失败
   ```python
   # test_storage.py:129-141
   def test_graph_storage_missing_required_fields_fails(tmp_path):
       with pytest.raises(ValueError) as excinfo:
           GraphStorage(db_path=db_path)
       assert "required fields" in str(excinfo.value)
   ```

2. **数据完整性验证**：测试 anchor 缺失时的快速失败
   ```python
   # test_storage.py:144-176
   def test_graph_storage_missing_anchor_fails(tmp_path):
       with pytest.raises(ValueError) as excinfo:
           GraphStorage(db_path=db_path)
       assert "anchor" in message
   ```

3. **分支隔离验证**：验证分支修改不影响主分支
   ```python
   # test_storage.py:307-337
   assert branch_scene["actual_outcome"] == "branch outcome"
   assert main_scene["actual_outcome"] == ""  # 主分支未变
   ```

4. **合并/回滚完整性**：验证 merge 和 revert 的数据一致性
   ```python
   # test_storage.py:340-364 - merge
   # test_storage.py:367-397 - revert
   ```

#### 潜在问题

1. **缺少大数据量测试**：未测试 100+ 场景的性能和正确性
2. **缺少并发写入测试**：未测试多线程同时写入的数据一致性

---

### 2.3 test_models.py - 有效性评估：✅ 良好

#### 优点

1. **Pydantic 校验测试**：验证必填字段缺失时抛出 ValidationError
   ```python
   # test_models.py:9-21
   def test_snowflake_root_validation():
       with pytest.raises(ValidationError):
           SnowflakeRoot(logline="仅有一句话")  # 缺少其他字段
   ```

2. **边界值测试**：验证 three_disasters 长度必须为 3
   ```python
   # test_models.py:15-21
   with pytest.raises(ValidationError):
       SnowflakeRoot(three_disasters=["A", "B"], ...)  # 长度不足
   ```

3. **空值校验**：验证 voice_dna 不可为空
   ```python
   # test_models.py:37-45
   with pytest.raises(ValidationError):
       CharacterSheet(voice_dna="", ...)
   ```

#### 无问题

---

### 2.4 test_snowflake_workflow.py - 有效性评估：⚠️ 中等

#### 优点

1. **Mock 隔离**：使用 mocker.AsyncMock 隔离 LLM 调用
2. **业务逻辑验证**：验证 logline 数量、场景 ID 唯一性等业务规则
   ```python
   # test_snowflake_workflow.py:143-188
   def test_step4_scene_validation_duplicate_id(mocker):
       with pytest.raises(ValueError):
           await manager.execute_step_4_scenes(...)
   ```

3. **持久化验证**：验证 storage.save_snowflake 被正确调用
   ```python
   # test_snowflake_workflow.py:257-261
   mock_storage.save_snowflake.assert_called_once_with(...)
   assert manager.last_persisted_root_id == "root-123"
   ```

#### 潜在问题

1. **过度依赖 Mock**：所有测试都使用 Mock，未与真实 storage 集成测试
   ```python
   # test_snowflake_workflow.py:249
   mock_storage = mocker.Mock()
   mock_storage.save_snowflake.return_value = "root-123"
   ```
   **风险**：Mock 行为可能与真实 storage 不一致

2. **缺少 Step 2 测试**：`execute_step_2_structure` 方法未被测试

---

### 2.5 test_topone_client.py - 有效性评估：✅ 良好

#### 优点

1. **真实 HTTP 模拟**：使用 httpx.MockTransport 模拟真实 HTTP 请求
   ```python
   # test_topone_client.py:31
   transport = httpx.MockTransport(handler)
   ```

2. **请求结构验证**：验证发送的 JSON 结构正确
   ```python
   # test_topone_client.py:49-52
   assert captured["json"]["contents"][0]["role"] == "user"
   assert captured["json"]["systemInstruction"]["parts"][0]["text"] == "sys"
   ```

3. **快速失败验证**：验证缺少 API Key 时直接失败
   ```python
   # test_topone_client.py:65-69
   def test_generate_content_requires_api_key():
       client = ToponeClient(api_key="")
       with pytest.raises(ValueError):
           await client.generate_content(...)
   ```

4. **模型白名单验证**：验证不支持的模型被拒绝
   ```python
   # test_topone_client.py:55-62
   def test_generate_content_rejects_unsupported_model():
       with pytest.raises(ValueError):
           await client.generate_content(model="unknown-model", ...)
   ```

#### 无问题

---

### 2.6 test_topone_gateway.py - 有效性评估：⚠️ 中等

#### 优点

1. **Prompt 注入验证**：验证 force_execute 时添加"戏剧性优先"
   ```python
   # test_topone_gateway.py:52-53
   assert result == "Rendered scene text"
   assert "戏剧性优先" in client.calls[0]["system_instruction"]
   ```

#### 潜在问题

1. **覆盖不足**：仅测试 render_scene，未测试 logic_check、state_extract 等核心方法
2. **StubToponeClient 过于简单**：总是返回固定文本，未测试 JSON 解析失败等异常情况

---

### 2.7 test_llm_service.py - 有效性评估：⚠️ 中等

#### 优点

1. **Prompt 结构验证**：验证发送给 LLM 的 Prompt 结构正确
   ```python
   # test_llm_service.py:97-100
   assert messages[0]["role"] == "system"
   assert "50-100 个场景节点" in messages[0]["content"]
   ```

#### 潜在问题

1. **Mock 返回值过于简单**：直接返回预设对象，未测试 LLM 返回格式异常的情况
   ```python
   # test_llm_service.py:22
   mock_client.chat.completions.create.return_value = mock_response
   ```

2. **缺少异步行为测试**：未测试 `inspect.isawaitable` 分支

---

## 3. 与测试方案对照

### 3.1 P0 用例覆盖情况

| 测试方案要求 | 测试文件 | 覆盖状态 | 证据 |
|-------------|----------|----------|------|
| 缺少 `key` 或 `Content-Type` | test_api.py | ✅ 已覆盖 | `test_topone_generate_rejects_missing_content_type` (L261) |
| `contents.parts.text` 缺失/空 | test_api.py | ✅ 已覆盖 | `test_topone_generate_rejects_missing_message_text` (L275), `test_topone_generate_rejects_blank_message_text` (L286) |
| 雪花流程必填字段 | test_models.py | ✅ 已覆盖 | `test_snowflake_root_validation` (L9) |
| 标准协商路径 | test_api.py | ✅ 已覆盖 | `test_complete_scene_orchestrated_endpoint_runs_flow` (L501) |
| Force Execute | test_api.py | ✅ 已覆盖 | `test_logic_check_force_execute_marks_scene` (L333), `test_complete_scene_orchestrated_force_execute_allows_rejected_logic` (L845) |
| HITL 未确认不写入 | test_api.py | ✅ 已覆盖 | `test_state_extract_enriches_diff_and_is_readonly` (L421) |
| Local 修复 N+1~N+3 | test_api.py | ✅ 已覆盖 | `test_complete_scene_orchestrated_endpoint_runs_flow` (L574-591) |
| Cascading Dirty 标记 | test_api.py | ✅ 已覆盖 | `test_complete_scene_orchestrated_marks_cascading_dirty` (L958) |

### 3.2 P1 用例覆盖情况

| 测试方案要求 | 测试文件 | 覆盖状态 | 证据 |
|-------------|----------|----------|------|
| 正常 200 响应 | test_topone_client.py | ✅ 已覆盖 | `test_generate_content_builds_payload` (L8) |
| 实体关系/状态写入 | test_storage.py | ✅ 已覆盖 | `test_apply_semantic_states_patch` (L179) |
| 用户意图改变大纲 | test_api.py | ⚠️ 部分覆盖 | 有 logic_check 测试，但未测试大纲修改触发影响分析 |
| 人工确认流程 | test_api.py | ✅ 已覆盖 | `test_state_commit_endpoint_updates_semantic_states` (L469) |
| 分支管理 | test_api.py, test_storage.py | ✅ 已覆盖 | `test_branch_endpoints_roundtrip` (L1122), `test_branch_merge_endpoint_applies_snapshot` (L1177) |

---

## 4. 问题清单

### 4.1 取巧/作弊问题

| 问题 | 严重程度 | 位置 | 说明 |
|------|----------|------|------|
| **StubGateway 总是成功** | 中 | test_api.py 多处 | StubGateway 的 logic_check 总是返回 ok=True，未测试 LLM 拒绝的情况 |
| **Mock storage 未验证参数** | 低 | test_snowflake_workflow.py:249 | `mock_storage.save_snowflake.return_value = "root-123"` 未验证传入参数的正确性 |

### 4.2 无效测试问题

| 问题 | 严重程度 | 位置 | 说明 |
|------|----------|------|------|
| **无** | - | - | 未发现完全无效的测试 |

### 4.3 覆盖缺失问题

| 缺失项 | 严重程度 | 建议 |
|--------|----------|------|
| **LLM 返回异常测试** | 高 | 增加 LLM 返回格式错误、超时、空响应的测试 |
| **并发测试** | 中 | 增加多线程同时操作同一 root_id 的测试 |
| **大数据量测试** | 中 | 增加 100+ 场景的性能测试 |
| **Step 2 测试** | 低 | 增加 `execute_step_2_structure` 的单元测试 |
| **topone_gateway 覆盖** | 中 | 增加 logic_check、state_extract 的单元测试 |

---

## 5. 快速失败原则检查

### 5.1 符合原则的测试 ✅

```python
# test_storage.py:129-141 - 缺少必填字段直接失败
with pytest.raises(ValueError) as excinfo:
    GraphStorage(db_path=db_path)
assert "required fields" in str(excinfo.value)

# test_topone_client.py:65-69 - 缺少 API Key 直接失败
with pytest.raises(ValueError):
    await client.generate_content(...)

# test_api.py:261-272 - 缺少 Content-Type 返回 422
assert response.status_code == 422
```

### 5.2 潜在违反原则的代码 ⚠️

```python
# test_api.py:338-345 - StubGateway 总是返回成功，未测试失败路径
class StubGateway:
    async def logic_check(self, payload):
        return LogicCheckResult(ok=True, ...)  # 应增加 ok=False 的测试
```

---

## 6. 改进建议

### 6.1 高优先级

1. **增加 LLM 异常测试**
   ```python
   @pytest.mark.asyncio
   async def test_logic_check_handles_llm_error(monkeypatch, tmp_path):
       class ErrorGateway:
           async def logic_check(self, payload):
               raise RuntimeError("LLM timeout")
       # 验证 API 返回 500 或适当错误
   ```

2. **增加 logic_check 拒绝测试**
   ```python
   @pytest.mark.asyncio
   async def test_complete_scene_rejects_when_logic_check_fails(monkeypatch, tmp_path):
       class RejectGateway:
           async def logic_check(self, payload):
               return LogicCheckResult(ok=False, decision="reject", ...)
       # 验证 API 返回 400
   ```

### 6.2 中优先级

1. **增加 topone_gateway 单元测试**
   - `test_logic_check_parses_json_correctly`
   - `test_state_extract_handles_empty_response`

2. **增加并发测试**
   ```python
   @pytest.mark.asyncio
   async def test_concurrent_scene_complete(tmp_path):
       # 多个协程同时完成不同场景
   ```

### 6.3 低优先级

1. **增加 Step 2 测试**
2. **增加大数据量测试**（可放入 `project/scripts/performance_stress_test.py`）

---

## 7. 结论

### 7.1 总体评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **有效性** | 8/10 | 测试逻辑正确，验证了核心功能 |
| **覆盖率** | 7/10 | P0 用例全覆盖，P1 部分覆盖，缺少异常路径 |
| **快速失败** | 9/10 | 大部分测试遵循快速失败原则 |
| **无作弊** | 9/10 | 未发现明显作弊，但 StubGateway 过于简单 |

### 7.2 关键发现

1. **无无效测试**：所有测试都有实际验证逻辑
2. **真实数据库测试**：使用 tmp_path 创建真实 Kùzu 数据库，非内存 Mock
3. **完整闭环验证**：API 测试不仅验证响应，还验证数据库状态
4. **缺少异常路径**：LLM 返回异常、超时等情况未被测试

### 7.3 风险评估

| 风险 | 影响 | 建议 |
|------|------|------|
| LLM 异常未测试 | 生产环境可能出现未处理异常 | 增加异常测试 |
| 并发未测试 | 多用户同时操作可能出现数据不一致 | 增加并发测试 |
| StubGateway 过于简单 | 可能遗漏 LLM 拒绝场景的 bug | 增加拒绝测试 |
