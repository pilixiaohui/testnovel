# 项目知识库索引

本目录包含项目的结构化知识文档，供 agent 和开发者查阅。

## 目录结构

| 目录/文件 | 用途 |
|-----------|------|
| `coding-standards.md` | 编码原则（KISS/YAGNI/SOLID/DRY）和工作流程 |
| `architecture-constraints.md` | 架构约束（文件大小、import 方向、命名规范） |
| `design-docs/` | 设计文档（功能设计、技术方案） |
| `exec-plans/` | 执行计划（迭代计划、里程碑） |

## 使用指南

- **新功能设计**：在 `design-docs/` 下创建设计文档，命名格式 `YYYY-MM-DD-<topic>.md`
- **执行计划**：在 `exec-plans/` 下创建计划文档
- **架构约束**：修改架构规则前先更新 `architecture-constraints.md`
- **编码标准**：所有 agent 必须遵守 `coding-standards.md` 中的原则
