# 架构约束

以下约束由 `scripts/lint_arch.py` 自动检查，push 时违反会被拒绝。

## 文件大小限制

| 文件类型 | 最大行数 | 理由 |
|----------|---------|------|
| Python (`.py`) | 500 行 | 超过 500 行的模块应拆分为更小的子模块 |
| TypeScript (`.ts`/`.tsx`) | 300 行 | 前端组件应保持小而专注 |

## Import 方向

- `project/` 不能导入 `orchestrator_v2/`
  - `project/` 是业务代码，`orchestrator_v2/` 是编排层
  - 业务代码不应依赖编排基础设施

## 命名规范

- Python 文件名必须使用 `snake_case`（如 `my_module.py`）
  - 排除：`__init__.py`、`__main__.py` 等特殊文件
  - 排除：配置文件如 `Dockerfile`、`Makefile`

## 如何修复违规

当 push 被拒绝时，错误信息格式为：
```
{file}:{line}: {rule}: {message} [fix: {hint}]
```

按照 `fix:` 后的提示修复即可。
