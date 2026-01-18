# Current Task (Iteration 4)
assigned_agent: TEST

## 目标
- 为 M2-T2 先补测试（红）：当 logic_check 请求提供 locator（root_id/branch_id/scene_id 或等价字段）时，必须从图存储构建 world_state，而不是信任请求体 world_state。

## 范围
- 仅改动测试代码：project/backend/tests/**
- 允许使用 mock/test double；禁止真实网络请求（Topone/LLM 必须 stub）

## 必要定位线索
- logic_check 入口：project/backend/app/main.py:1012 附近（REVIEW 取证）
- gateway 实现：project/backend/app/llm/topone_gateway.py
- 存储抽象：project/backend/app/storage/ports.py（GraphStoragePort）

## 任务步骤
1) 定位 logic_check endpoint 的路由与请求/响应模型（从 main.py 反查）。
2) 参考现有测试风格（例如 project/backend/tests/test_api.py），新增 1-2 个测试用例。
3) 通过 FastAPI dependency_overrides 或 monkeypatch 注入：
- stub storage（GraphStoragePort），提供一个用于构建 world_state 的方法（方法名由你在测试中先确定，用于驱动 DEV 实现对齐）。
- stub gateway.logic_check(...)，返回最小可序列化响应，并记录其收到的 payload。
4) 断言至少满足其一：
- storage 的 world_state 构建方法被调用。
- gateway 收到的 payload 中 world_state 等于 storage 返回值，且不等于请求体 world_state。
5) 运行 pytest，确认新增测试在当前代码上失败（红），并记录失败摘要（失败用例名 + 关键断言信息）。

## 验收标准
- 新增测试不依赖网络/外部服务，能在本地 pytest 中稳定运行。
- 至少 1 个新增测试在当前代码上稳定失败，失败原因明确指向 M2-T2 期望行为。
- 提供可复现命令与失败摘要，便于 DEV 按测试驱动修复。

## TDD 要求
- 你只负责测试阶段（红）；不要修改生产代码来让测试变绿。
