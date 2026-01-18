已阅读测试行为规范  
iteration: 4

## 测试目标
- 为 M2-T2 补红测：当 `/api/v1/logic/check` 请求提供 locator（`root_id/branch_id/scene_id`）时，必须从图存储构建 `world_state`，而不是信任请求体 `world_state`。

## 测试计划
- 定位 `logic_check` endpoint（`project/backend/app/main.py:973`）的入参/依赖注入点（`get_topone_gateway` / `get_graph_storage`）。
- 新增 1-2 个测试用例（stub storage + stub gateway），断言 locator 存在时 `world_state` 必须来自 storage。
- 运行 pytest，确认新增测试在当前代码上稳定失败（红），并记录失败摘要。

## 测试变更（仅测试代码）
- 新增 `project/backend/tests/test_logic_check_world_state.py:1`
  - 约定（用于驱动 DEV 对齐实现）：GraphStorage 侧新增方法名 `build_logic_check_world_state(root_id, branch_id, scene_id) -> dict`

## 执行命令
- `./.venv/bin/python -m pytest -q tests/test_logic_check_world_state.py`（cwd: `project/backend`）

## 结果与失败摘要
- 结果：1 failed, 1 passed
- 失败用例：`tests/test_logic_check_world_state.py::test_logic_check_with_locator_builds_world_state_from_storage`
- 关键断言失败：`assert seen.world_state == storage_world_state`  
  实际：`{'from_request': True}`；期望：`{'from_storage': True}`

## 研判
- `project/backend/app/main.py:973` 的 `logic_check_endpoint` 当前把请求体 `world_state` 直接透传给 `gateway.logic_check(...)`；即使 locator 已提供，也未从 storage 构建/覆盖 `world_state`。

结论：PASS  
阻塞：无

## 给 DEV 的下一步建议
- 在 `project/backend/app/main.py:973`：当 locator 三件套齐全时，调用 `storage.build_logic_check_world_state(root_id=..., branch_id=..., scene_id=...)`，并在调用 `gateway.logic_check(...)` 前用其返回值覆盖 payload 的 `world_state`（locator 缺失时保持现状）。
- 在存储层补齐 `build_logic_check_world_state`（并同步到 `GraphStoragePort`），以确保“不信任请求体 world_state”。

【MCP调用简报】  
服务: serena  
触发: 定位 logic_check endpoint 并新增 TDD 红测  
参数: `search_for_pattern(relative_path=project/backend/app/main.py, substring_pattern=logic_check)`；`create_text_file(project/backend/tests/test_logic_check_world_state.py)`；`execute_shell_command(cwd=project/backend, command=./.venv/bin/python -m pytest -q tests/test_logic_check_world_state.py)`  
结果: pytest 结果 `1 failed, 1 passed`；失败点为 locator 存在时 `world_state` 仍来自请求体  
状态: 成功