# Current Task (Iteration 1)
assigned_agent: SPEC_ANALYZER

## 任务目标
为变更单 CHG-0002 产出可执行规格草案与任务拆解，作为后续实现唯一锚点。

## 用户原始需求
前端存在大量问题，请对照各个功能进行分析列出所有存在的问题并修正，包括但不限于项目无法保存，提示词没有显示当前使用的实际提示词，各个标签页切换出错，无法提取图信息和推演，设置中的LLM 配置不是显示真实使用的数据库内配置，项目管理内容不完善，无法新建项目，雪花步骤生成的各个内容如角色等信息无法在前端看到完整信息只能看到名字列表，需要能够直接显示原始信息和解析结果 @doc:requirements/frontend_implementation_spec.md @doc:requirements/系统架构与技术规格.md 参考文档和代码进行分析是否还有其他问题并进行修正，注意先调研检查问题是否实属再进行修正，前端测试验收时注意用户的实际使用体验，以生成一个10章每章2000字的短片小说为验收测试任务，确保多代理推理、图知识库提取等功能正确可靠

## 文档线索
- requirements/frontend_implementation_spec.md
- requirements/系统架构与技术规格.md

## 工件目标（仅用于 MAIN 落盘，SPEC_ANALYZER 禁止直接写文件）
- proposal: orchestrator/memory/specs/changes/CHG-0002/proposal.md
- design: orchestrator/memory/specs/changes/CHG-0002/design.md
- delta_spec: orchestrator/memory/specs/changes/CHG-0002/delta_spec.md
- tasks: orchestrator/memory/specs/changes/CHG-0002/tasks.md
- validation: orchestrator/memory/specs/changes/CHG-0002/validation.md
- questions: orchestrator/memory/specs/changes/CHG-0002/questions.md
- proofs: orchestrator/memory/specs/changes/CHG-0002/proofs.md
- meta: orchestrator/memory/specs/changes/CHG-0002/meta.json

## 工作要求
1. 先调研真实代码与接口契约，再写规格，不允许凭空假设
2. 任务拆解必须生成 TASK-xxx，可直接作为 implementation_scope
3. 每个任务必须可验证，并在 validation.md 给出证据类型
4. 列出需用户确认的问题（accept_spec/refine_spec 决策）
5. 只能输出结构化工件更新建议，禁止直接修改 orchestrator 黑板文件

## 输出要求
- 报告中必须给出本轮主要改动点与证据
- 报告中必须提供可供 MAIN 转换为 artifact_updates 的建议（file/action/content/reason）
- 不要返回旧协议字段（spec_anchor_next/target_reqs）
