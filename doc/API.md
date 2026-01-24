
## 基本信息
- Base URL: `http://<host>:<port>`
- API 前缀: `/api/v1`
- 返回格式: JSON (UTF-8)
- 依赖配置:
  - `SNOWFLAKE_ENGINE` 必填：`local` / `llm` / `gemini`
  - `MEMGRAPH_HOST` / `MEMGRAPH_PORT` 必填
  - Gemini 模式需配置 `TOPONE_API_KEY`（可选：`TOPONE_BASE_URL` / `TOPONE_DEFAULT_MODEL` / `TOPONE_SECONDARY_MODEL`）

## 雪花流程
- `POST /api/v1/snowflake/step1`
  - 请求: `{ "idea": "..." }`
  - 返回: `string[]`（logline 候选）
- `POST /api/v1/snowflake/step2`
  - 请求: `{ "logline": "..." }`
  - 返回: `SnowflakeRoot`
- `POST /api/v1/snowflake/step3`
  - 请求: `SnowflakeRoot`
  - 返回: `CharacterSheet[]`
- `POST /api/v1/snowflake/step4`
  - 请求: `{ "root": SnowflakeRoot, "characters": CharacterSheet[] }`
  - 返回: `{ root_id, branch_id, scenes }`

## 分支与版本控制
- `POST /api/v1/roots/{root_id}/branches`
- `GET /api/v1/roots/{root_id}/branches`
- `POST /api/v1/roots/{root_id}/branches/{branch_id}/switch`
- `POST /api/v1/roots/{root_id}/branches/{branch_id}/merge`
- `POST /api/v1/roots/{root_id}/branches/{branch_id}/revert`
- `POST /api/v1/roots/{root_id}/branches/fork_from_commit`
- `POST /api/v1/roots/{root_id}/branches/fork_from_scene`
- `POST /api/v1/roots/{root_id}/branches/{branch_id}/reset`
- `GET /api/v1/roots/{root_id}/branches/{branch_id}/history`
- `POST /api/v1/roots/{root_id}/branches/{branch_id}/commit`
- `POST /api/v1/roots/{root_id}/scene_origins`
- `POST /api/v1/roots/{root_id}/scenes/{scene_id}/delete`
- `POST /api/v1/commits/gc`

## 图谱查询
- `GET /api/v1/roots/{root_id}`
- `GET /api/v1/scenes/{scene_id}/context`
- `GET /api/v1/scenes/{scene_id}/diff`
- `GET /api/v1/roots/{root_id}/dirty_scenes`
- `POST /api/v1/scenes/{scene_id}/dirty`

## 实体与关系
- `POST /api/v1/roots/{root_id}/entities`
- `GET /api/v1/roots/{root_id}/entities`
- `POST /api/v1/roots/{root_id}/relations`

## 场景渲染与状态
- `POST /api/v1/scenes/{scene_id}/render`（仅 `SNOWFLAKE_ENGINE=gemini`）
- `POST /api/v1/scenes/{scene_id}/complete`
- `POST /api/v1/scenes/{scene_id}/complete/orchestrated`（仅 `SNOWFLAKE_ENGINE=gemini`）
- `POST /api/v1/logic/check`（仅 `SNOWFLAKE_ENGINE=gemini`）
- `POST /api/v1/state/extract`（仅 `SNOWFLAKE_ENGINE=gemini`）
- `POST /api/v1/state/commit`
- `POST /api/v1/llm/topone/generate`

## 请求 / 响应 / 错误示例

### 创建实体

**请求**

```bash
curl -X POST 'http://localhost:8000/api/v1/roots/<root_id>/entities?branch_id=main' \
  -H 'Content-Type: application/json' \
  -d '{"name": "Alice", "entity_type": "Character", "tags": ["protagonist"], "arc_status": "seed", "semantic_states": {"hp": 100}}'
```

**响应**

```json
{
  "entity_id": "entity-uuid",
  "name": "Alice",
  "entity_type": "Character",
  "tags": ["protagonist"],
  "arc_status": "seed",
  "semantic_states": {"hp": 100}
}
```

### 获取场景上下文

**请求**

```bash
curl 'http://localhost:8000/api/v1/scenes/<scene_id>/context?branch_id=main'
```

**响应**

```json
{
  "root_id": "root-uuid",
  "branch_id": "main",
  "expected_outcome": "escape",
  "semantic_states": {
    "entity-1": {"AT": "entity-2"}
  },
  "summary": "scene summary",
  "scene_entities": [
    {"entity_id": "entity-1", "name": "Alice", "entity_type": "Character", "tags": [], "arc_status": "seed", "semantic_states": {}}
  ],
  "characters": [
    {"entity_id": "entity-1", "name": "Alice"}
  ],
  "relations": [
    {"from_entity_id": "entity-1", "to_entity_id": "entity-2", "relation_type": "AT", "tension": 5}
  ],
  "prev_scene_id": null,
  "next_scene_id": "scene-2"
}
```

**错误响应（示例）**

```json
{
  "detail": "scene version not found: <scene_id>"
}
```

### 写入关系

**请求**

```bash
curl -X POST 'http://localhost:8000/api/v1/roots/<root_id>/relations?branch_id=main' \
  -H 'Content-Type: application/json' \
  -d '{"from_entity_id": "entity-1", "to_entity_id": "entity-2", "relation_type": "AT", "tension": 10}'
```

**响应**

```json
{
  "from_entity_id": "entity-1",
  "to_entity_id": "entity-2",
  "relation_type": "AT",
  "tension": 10
}
```

**错误响应（示例）**

```json
{
  "detail": "entity not found: entity-1"
}
```

## 其它示例

生成 Logline：

```bash
curl -X POST http://localhost:8000/api/v1/snowflake/step1 \
  -H 'Content-Type: application/json' \
  -d '{"idea": "赛博朋克侦探"}'
```
