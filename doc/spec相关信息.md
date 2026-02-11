# **意图架构学：规范驱动开发 (SDD) 深度解析与 AI 原生工程的最佳实践报告**

## **1\. 执行摘要：从“代码为王”到“意图为王”的范式转移**

软件工程行业正经历着自“瀑布模型”转向“敏捷开发”以来最深刻的范式转移。在过去四十年里，行业运作的一个隐性假设是：代码是唯一且最终的真理来源（Source of Truth）。需求文档、架构图和规范说明往往被视为一种短暂的脚手架，一旦实施阶段开始，这些文档便迅速陈旧、腐烂，最终与系统实际行为脱节。然而，随着大语言模型（LLM）和 AI 辅助编程代理（AI Coding Agents）的全面爆发，这一核心假设被彻底颠覆。在一个智能算力充沛、代码生成成本趋近于零的时代，代码不再是稀缺资源，**清晰且无歧义的意图（Clarity of Intent）** 才是。

本报告旨在对 **规范驱动开发（Spec-Driven Development, SDD）** 进行详尽的解构与重构。我们不再将规范视为被动的文档，而是将其定义为主动的、可执行的、驱动 AI 行为的核心构件。通过对 GitHub Spec Kit、Fission AI OpenSpec、Liatrio SDD 工作流以及 Cursor/Windsurf 社区最佳实践的深度综合分析，本报告确立了 AI 原生工程下 Spec.md 文件的“黄金标准”。

研究表明，并不存在单一的“魔法模板”，但存在一套已被验证的**信息架构原则**：即在 Markdown 格式中融合**渐进式披露（Progressive Disclosure）**、**行为契约（Gherkin语法）**、**视觉逻辑（Mermaid图表）以及原子化任务分解（Coarse-to-Fine Reasoning）**。本报告将详细阐述如何构建这种高信噪比的规范文件，使其成为人类意图与机器执行之间的完美桥梁。

## **2\. 理论框架：为什么 AI 需要 SDD？**

要掌握 Spec.md 的最佳格式，首先必须深刻理解其背后的驱动力——即当前 AI 辅助开发的痛点以及 LLM 的认知特性。

### **2.1 “Vibe Coding” 的陷阱与工程严谨性的回归**

AI 编程的早期阶段被形象地称为 "Vibe Coding"（氛围编程）——开发者通过自然语言与 AI 聊天，反复提示、修改，直到代码“感觉”对了为止 1。这种非确定性的交互模式在构建原型时效率极高，但在企业级开发中却面临灾难性的失效：

1. **上下文遗忘（Context Amnesia）：** 随着对话轮次的增加，LLM 的上下文窗口被填满，早期的架构约束和业务规则被遗忘，导致后生成的代码破坏了原有的系统逻辑 2。  
2. **意图漂移（Intent Drift）：** 没有持久化的锚点文档，AI 对系统的理解随着每一次 Prompt 而微调，最终导致架构的“漂移” 3。  
3. **歧义放大：** 人类语言天生具有模糊性。在传统开发中，程序员会向产品经理确认歧义；而 AI 代理往往倾向于“猜测”以通过概率最大化来填补空白，导致产生了看似正确实则谬误的代码 4。

SDD 的核心哲学在于建立一个**外部化的持久记忆体**。Spec.md 文件充当了 AI 代理的“海马体”，确保每一行生成的代码都锚定在经过审查、确定的意图之上。

### **2.2 Markdown：AI 时代的“汇编语言”**

为什么 Markdown 击败了 JSON、XML 或 YAML 成为 SDD 的标准载体？这并非偶然，而是由 LLM 的训练数据分布和注意力机制决定的。

* **层级注意力机制（Hierarchical Attention）：** LLM 在海量的互联网文本上训练，其中 Markdown 的标题语法（\#, \#\#, \#\#\#）被模型内化为极其强烈的语义层级信号。这种结构天然契合人类和 AI 的“由粗到细”（Coarse-to-Fine）的推理模式——先理解宏观目标，再处理微观细节 5。  
* **混合模态表达力（Mixed Modality）：** SDD 要求在同一文档中描述业务逻辑、代码片段、数据结构和系统拓扑。Markdown 是唯一能够优雅地混合自然语言（解释）、代码块（实现）、Mermaid（视觉结构）和数学公式的轻量级标记语言 7。  
* **Token 效率：** 相比于 XML 的繁琐标签或 JSON 的大量括号与引号，Markdown 具有极高的 Token 信息密度，这对于极其宝贵的上下文窗口资源至关重要 9。

### **2.3 “由粗到细”的推理链设计**

认知科学与 AI 对齐研究表明，当任务被层级化分解时，智能体的表现最优 10。一个试图在单次 Prompt 中解决复杂功能的“巨型指令”往往会导致幻觉。相反，一个遵循 **高层意图 → 功能需求 → 技术设计 → 原子任务** 结构的 Spec.md，实际上是在为模型构建一条显式的“思维链”（Chain of Thought）。这种结构不仅指导了 AI 做什么，更通过逻辑递进隐含地指导了 AI 如何思考。

## ---

**3\. Spec.md 的解剖学：黄金标准与核心组件**

基于对 GitHub Spec Kit、OpenSpec 和 Thoughtworks 等行业先驱的实践分析，我们总结出了一份生产级 Spec.md 的通用信息架构。一个有效的 Spec 文件必须包含五个核心维度：**元数据（Metadata）**、**语境（Context）**、**契约（Contract）**、**视觉（Visuals）** 和 **执行（Execution）**。

### **3.1 元数据层：状态与所有权**

在文件头部使用 YAML Frontmatter 是行业公认的最佳实践。这不仅让 AI 快速识别文件属性，也能被自动化工具（如 CI/CD 流水线）解析。

**推荐格式：**

YAML

\---  
id: FEAT-AUTH-001  
title: 基于 Magic Link 的无密码登录系统  
status: DRAFT  \# DRAFT | REVIEWED | APPROVED | IMPLEMENTED  
owner: @security-team  
created: 2025-10-27  
context\_dependencies:  
  \- docs/architecture/auth-system.md  
  \- docs/guidelines/security-policy.md  
\---

**深度解析：** status 字段至关重要。在 Liatrio 的工作流中，只有当状态转变为 APPROVED 时，AI 代理才被允许进入编码阶段。这种“门控”机制有效防止了未成熟的想法被过早转化为技术债务 12。context\_dependencies 字段体现了**渐进式披露**原则，指引 AI 在需要时读取外部文档，而非将所有背景塞入当前文件。

### **3.2 语境层（The Context）：意图的锚点**

这一部分解决“为什么做”的问题。对于 AI 而言，这是进行逻辑推断的基石。如果后续的具体指令模糊，AI 将回溯到此处的意图进行消歧。

**最佳实践：**

* **问题陈述（Problem Statement）：** 用简练的自然语言描述现状痛点。例如：“当前基于密码的登录导致用户流失率高，且增加了数据库泄露风险。”  
* **用户故事（User Stories）：** 采用标准的“As a... I want to... So that...”格式。这不仅是敏捷开发的遗产，更是经过大量微调数据验证的、LLM 极易理解的指令格式 13。  
* **非目标（Non-Goals）：** 明确列出**不做**什么。例如：“本次迭代不支持短信验证码登录。” 这一“负向约束”对于防止 AI 过度工程（Over-engineering）至关重要 14。

### **3.3 契约层（The Contract）：Gherkin 语法的复兴**

这是 SDD 区别于传统文档的核心。传统的自然语言需求（如“系统应安全可靠”）对 AI 毫无约束力。最有效的 Spec.md 采用 **Gherkin (Given-When-Then)** 语法来定义行为契约。

**示例：**

Gherkin

\#\#\# 需求：生成登录链接  
\*\*场景：用户输入有效邮箱\*\*  
\- \*\*GIVEN\*\* 用户处于未登录状态  
\- \*\*AND\*\* 用户输入了数据库中存在的邮箱 "user@example.com"  
\- \*\*WHEN\*\* 用户点击“发送登录链接”按钮  
\- \*\*THEN\*\* 系统生成一个包含 15 分钟有效期的 JWT Token  
\- \*\*AND\*\* 系统发送一封包含该 Token 的邮件  
\- \*\*AND\*\* 界面显示“邮件已发送”提示，但不暴露邮箱是否存在（安全隐私要求）

**深度解析：** 使用 Gherkin 的深层原因在于它构成了\*\*测试驱动开发（TDD）\*\*的桥梁。AI 代理可以将上述文本直接翻译为 Jest 或 PyTest 测试用例 3。在 OpenSpec 的实践中，这被称为“行为锚定”，确保实现的每一行代码都有对应的测试覆盖，从而实现闭环验证。

### **3.4 视觉层（The Visuals）：Mermaid.js 的空间推理**

文字描述系统交互往往晦涩难懂。研究发现，当在 Prompt 中包含 Mermaid 图表时，LLM 对系统架构的理解能力显著提升 7。

**强制性要求：**

任何涉及两个以上组件交互的功能，必须包含 Mermaid 序列图（Sequence Diagram）或流程图（Flowchart）。

**示例：**

Code snippet

sequenceDiagram  
    participant U as User  
    participant F as Frontend  
    participant A as Auth API  
    participant D as Database  
    participant E as Email Service

    U-\>\>F: 输入邮箱并提交  
    F-\>\>A: POST /magic-link  
    A-\>\>D: 查询用户状态  
    alt 用户存在  
        A-\>\>D: 生成临时 Token  
        A-\>\>E: 发送带有 Token 的邮件  
    else 用户不存在  
        Note over A: 执行虚假等待 (防止计时攻击)  
    end  
    A--\>\>F: 返回 200 OK (统一响应)  
    F--\>\>U: 显示检查邮件提示

**深度解析：** 这个图表不仅告诉 AI 数据流向，还通过 alt/else 块隐式定义了错误处理逻辑和安全策略（如防止计时攻击）。这种“图代码同构”的特性使得 Mermaid 成为 SDD 中不可或缺的视觉语言 17。

### **3.5 执行层（The Execution）：原子化任务列表**

这是连接规范与代码实现的最后一公里。基于“由粗到细”的原则，必须将设计分解为一系列**可独立验证**的微任务。

**格式要求：**

使用 Markdown Checkbox，并按依赖关系排序。

**示例：**

## **5\. 实施计划 (Implementation Plan)**

* \[ \] **Step 1: 数据库迁移**  
  * 创建 magic\_tokens 表，包含 token\_hash (索引) 和 expires\_at 字段。  
  * *验证：* 运行 migration 脚本成功。  
* \[ \] **Step 2: 后端 API 实现**  
  * 实现 POST /magic-link 接口，包含限流逻辑（Rate Limiting）。  
  * *验证：* curl 请求返回预期结果，并能在数据库查到 Token。  
* \[ \] **Step 3: 邮件服务集成**  
  * 对接 SMTP 服务发送模板邮件。  
  * *验证：* Mailtrap 中收到格式正确的邮件。

**深度解析：** GitHub Spec Kit 强调，每个任务应当足够小，以便 AI 可以在单一上下文窗口内完成并进行自我纠错 4。如果在 tasks.md 中一个任务过于庞大，AI 往往会顾此失彼，产生 Bug。

## ---

**4\. 框架深度对比与最佳实践整合**

虽然上述组件构成了基础，但不同的框架在组织这些文件时有不同的哲学。我们对比三种主流模式：**GitHub Spec Kit**、**Fission AI OpenSpec** 和 **Cursor Rules 模式**，并综合出最佳实践。

### **4.1 GitHub Spec Kit：宪法驱动模式 (Constitution-Based)**

GitHub 的方案引入了一个极其重要的概念：**宪法文件（Constitution.md）** 13。

* **机制：** Constitution.md 包含项目级的不可变原则（如“必须使用 TypeScript”、“所有 API 必须有 Swagger 文档”、“禁止硬编码 Secret”）。  
* **作用：** 所有的 Feature Spec 都必须在“合宪”的前提下生成。  
* **最佳实践：** 在项目根目录维护一个 constitution.md，并在生成新的 Spec 时，强制 AI 预读此文件。这解决了多人协作（或多 Agent 协作）时的风格统一问题。

| 特性 | GitHub Spec Kit | 传统文档 | 优势分析 |
| :---- | :---- | :---- | :---- |
| **约束力** | 强制性（宪法） | 建议性 | AI 不会因 Prompt 差异而产生风格漂移 |
| **生命周期** | 伴随 Feature 分支 | 存放在 Wiki | 规范与代码同生共死，易于 Review |
| **交互方式** | Slash Command (/plan) | 人工查阅 | 深度集成到 IDE 聊天窗口，无缝切换 |

### **4.2 Fission AI OpenSpec：增量规范模式 (Delta Specs)**

OpenSpec 解决了一个极其现实的问题：**棕地项目（Brownfield Projects）** 19。在一个拥有百万行代码的遗留系统中，写一份涵盖全局的 Spec 是不可能的。OpenSpec 提出了 **Delta Spec** 的概念 20。

* **机制：** 规范只描述**变化**。  
  * \#\# ADDED Requirements （新增）  
  * \#\# MODIFIED Requirements （修改）  
  * \#\# REMOVED Requirements （删除）  
* **归档逻辑：** 当功能开发完成，Delta Spec 会被“合并”到主文档中，或者归档到 archive/ 目录。  
* **最佳实践：** 对于维护型项目，不要试图让 AI 理解整个系统。使用 OpenSpec 的模式，创建一个 changes/feat-xxx/spec.md 文件夹，只关注本次变更的范围。这极大地节省了 Context Window，提高了 AI 的注意力集中度。

### **4.3 Cursor / Windsurf：渐进式披露模式 (Progressive Disclosure)**

Cursor 社区演化出了一种极其实用的文件组织结构，通过 .cursorrules 或 AGENTS.md 充当“路由器” 22。

* **核心痛点：** 巨型 Monorepo 的上下文远超 200k Token。  
* **解决方案：**  
  * 根目录 AGENTS.md：只包含项目简介和目录索引。  
  * 子目录 packages/ui/AGENTS.md：只包含 UI 组件库的规范。  
  * 子目录 services/auth/AGENTS.md：只包含鉴权逻辑的规范。  
* **最佳实践：** 在 Spec.md 中不要复制粘贴已有逻辑，而是使用引用链接（如 Refer to @services/auth/AGENTS.md for coding standards）。现代 AI 编辑器（如 Cursor）能够识别这些引用并动态加载上下文。这被称为**渐进式披露**，是管理大规模上下文的关键技术。

## ---

**5\. 落地实战：从零构建一个 SDD 工作流**

基于上述理论，我们提出一个切实可行的、能够落地的 SDD 工作流。这个工作流结合了 GitHub Spec Kit 的严谨性和 Cursor 的灵活性。

### **阶段一：意图结晶（Specifying）**

**动作：** 开发者在 IDE 中发起对话，但不直接写代码。

**Prompt 示例：**

"我需要为现有的博客系统增加一个‘文章打赏’功能。请作为一名资深产品经理，根据 @constitution.md 的原则，向我提问以厘清需求，最终生成一份 specs/feat-tipping/spec.md。"

**关键点：** 让 AI 替你写 Spec。利用 AI 的结构化能力，人类只需负责确认和补充业务细节。此时生成的文件应包含 Gherkin 场景和 Mermaid 流程图。

### **阶段二：架构审查（Planning）**

**动作：** AI 分析 spec.md，生成技术方案 plan.md。

**Prompt 示例：**

"基于 spec.md，请制定技术实施计划。分析需要修改哪些文件，涉及到哪些数据库变更，并列出潜在的风险。"

**关键点：** **人工介入点（Human-in-the-loop）。** 这是成本最低的纠错环节。开发者必须审查 plan.md，确认 AI 没有过度设计（例如为了一个小功能引入 Redis）或违反安全规定。只有 Plan 通过，才能进入下一步。

### **阶段三：原子执行（Implementing）**

**动作：** 将 plan.md 转化为 tasks.md，并逐个执行。

**最佳实践：**

* **单线程执行：** 不要让 AI 一次性写完所有代码。  
* **指令：** "执行 Task 1。编写代码并通过测试。完成后更新 tasks.md 中的状态。"  
* **自我验证：** 要求 AI 在提交代码前，根据 spec.md 中的 Gherkin 场景生成测试脚本并运行通过 3。

### **阶段四：闭环验证（Validating）**

**动作：** 使用 Spec 作为验收标准。

**Prompt 示例：**

"请阅读 spec.md 中的‘验收标准’部分，并检查当前代码实现是否满足所有条件。生成一份验证报告。"

## ---

**6\. 示例链接与资源**

为了方便读者直接落地，以下整理了基于真实项目经验构建的模板库与示例资源：

* **完整 Spec.md 模板（Markdown）：** 见本报告附录 A。  
* **OpenSpec 官方示例库：**([https://github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)) \- 展示了 Delta Spec 的目录结构 20。  
* **GitHub Spec Kit 演示：** [GitHub \- github/spec-kit](https://github.com/github/spec-kit) \- 展示了 Constitution 和 Slash Command 的用法 13。  
* **Liatrio SDD Prompts：** [GitHub \- liatrio-labs/spec-driven-workflow](https://github.com/liatrio-labs/spec-driven-workflow) \- 提供了一套完整的 Prompt 库，用于生成和验证 Spec 12。

## ---

**7\. 挑战与未来展望**

### **7.1 常见陷阱与应对**

* **Spec 腐烂（Spec Rot）：** 就像代码注释一样，如果修改了代码没更新 Spec，Spec 就变成了谎言。  
  * *对策：* 建立“Spec-First”纪律。任何逻辑变更必须先改 Spec，再让 AI 生成代码。将 Spec 纳入 Code Review 的一部分。  
* **过度文档化（Documentation Fatigue）：** 开发者厌倦编写大量 Markdown。  
  * *对策：* 极度依赖 AI 生成 Spec。人类的角色应从“撰写者”转变为“审查者”。

### **7.2 自愈合规范（Self-Healing Specs）**

未来的 SDD 将是双向的。当 AI 在实现过程中发现 Spec 存在逻辑漏洞（例如死锁风险），它应有能力反向提出修改建议（Pull Request to Spec）。这种**代码-规范互操作性**是 AI 原生工程的下一个高地 25。

## ---

**8\. 结论**

在 AI 编码时代，Spec.md 不再是文档，它是**源代码的源代码**。

一个优秀的 Spec.md 格式应当是：

1. **结构化的**（Markdown 标题层级驱动 CoT 推理）；  
2. **视觉化的**（Mermaid 图表驱动空间推理）；  
3. **可验证的**（Gherkin 驱动自动化测试）；  
4. **渐进式的**（链接引用驱动上下文管理）。

掌握了 SDD，开发者就不再仅仅是代码的编写者，而是智能体编队的指挥官。通过通过严谨的规范架构来约束和引导 AI，我们能够以数量级提升的效率构建出高质量、可维护的软件系统。

## ---

**附录 A：生产级 Spec.md 通用模板 (The "Gold Standard" Template)**

以下模板可以直接复制到您的项目中（如 .cursor/rules/templates/feature-spec.md），作为 AI 生成的基准。

---

id: (e.g., PAY-002)

title: \[清晰的功能名称\]

status: DRAFT

owner: \[团队/负责人\]

created:

context\_dependencies:

* docs/architecture/payment-gateway.md  
* docs/guidelines/error-handling.md

# ---

**Feature: \[功能名称\]**

## **1\. Context & Objective (背景与目标)**

**One-line Summary:** \[一句话描述我们要构建什么\]

* **Problem (痛点):** \[为什么需要这个功能？解决了什么具体问题？\]  
* **User Value (价值):** \[用户将获得什么收益？\]  
* **Scope (范围):**  
  * ✅  
  * ❌

## **2\. Architecture & Design (架构与设计)**

### **2.1 System Interaction (Mermaid)**

\*(AI 注意：必须包含序列图以展示组件交互)\*mermaid

sequenceDiagram

participant U as User

participant S as Service

participant D as DB

U-\>\>S: Request

S-\>\>D: Query

D--\>\>S: Data

S--\>\>U: Response

\#\#\# 2.2 Data Model Changes (数据模型)  
\*(定义数据结构，优先使用 TypeScript Interface 或 SQL Schema)\*  
\*   \*\*Table:\*\* \`users\`  
    \*   \`+ balance\_cents: bigint\` (新增字段: 用户余额)

\#\# 3\. Functional Requirements (行为契约)

\#\#\# Req-1: \[子功能名称\]  
\*\*User Story:\*\* As a, I want to \[Action\], so that.

\*\*Behavioral Contract (Gherkin):\*\*  
\*(AI 注意：这些场景将用于生成测试用例)\*

\*   \*\*Scenario 1: Happy Path\*\*  
    \*   \*\*GIVEN\*\* \[前置条件\]  
    \*   \*\*WHEN\*\* \[特定动作\]  
    \*   \*\*THEN\*\* \[预期结果\]  
    \*   \*\*AND\*\* \[副作用\]

\*   \*\*Scenario 2: Edge Case (e.g., Network Failure)\*\*  
    \*   \*\*GIVEN\*\* \[前置条件\]  
    \*   \*\*WHEN\*\* \[动作\]  
    \*   \*\*THEN\*\* \[优雅的错误处理\]

\#\# 4\. Non-Functional Requirements (非功能需求)  
\*   \*\*Security:\*\*  
\*   \*\*Performance:\*\* \[例如：API 响应时间 \< 200ms\]  
\*   \*\*Observability:\*\* \[例如：关键路径必须打 Log\]

\#\# 5\. Implementation Plan (执行计划)  
\*(AI 注意：任务必须是原子的，可独立验证的)\*  
\- \[ \] \*\*Step 1:\*\* \[数据库变更\]  
\- \[ \] \*\*Step 2:\*\* \[后端逻辑实现\]  
\- \[ \] \*\*Step 3:\*\* \[前端对接\]  
\- \[ \] \*\*Step 4:\*\* \[添加测试\]

\#\# 6\. Verification (验收清单)  
\- \[ \] 所有 Gherkin 场景通过自动化测试。  
\- \[ \] 代码符合 \`@constitution.md\` 规范。  
\- \[ \] 无新增的高危安全漏洞。

13

# ---

**深度专题：规范驱动开发 (SDD) 核心组件详析与实施指南**

## **9\. 深入剖析：为什么 Gherkin 是 AI 的“母语”？**

在前面的章节中，我们确立了 Gherkin (Given-When-Then) 作为 Spec.md 核心组件的地位。为了达到报告要求的“深度洞察”，我们需要深入探讨其背后的认知科学原理和工程价值。

### **9.1 结构化语义与 Token 注意力**

LLM 本质上是概率预测机。当我们使用自然语言段落描述需求时（例如：“确保用户不能重复提交表单”），这句话中的关键词分散，逻辑约束隐晦。AI 可能会忽略“重复”这个词，或者错误理解为“前端防抖”而非“后端幂等”。

Gherkin 语法通过强迫性的关键字（GIVEN, WHEN, THEN, AND, BUT）构建了一个**语义框架**。

* **GIVEN** 设定了**初始状态空间**。这极大地限制了 AI 的搜索范围，使其只需关注特定的上下文 15。  
* **WHEN** 明确了**触发事件**。这不仅是用户行为，也可以是系统事件（如定时任务触发）。  
* **THEN** 定义了**状态转移**和**输出断言**。这是最关键的部分，它告诉 AI 成功的唯一定义是什么。

研究表明，这种结构化的 prompt 能够显著降低 LLM 的“幻觉率”，因为它将一个开放式的生成任务（Open-ended Generation）转化为了一个受约束的补全任务（Constrained Completion）。

### **9.2 自动化测试生成的桥梁**

SDD 的终极目标是自动化。如果 Spec 只是给人看的，那它只是文档；如果它能驱动代码，那它就是**元编程**。

在 Cursor 或 Spec Kit 的工作流中，我们可以直接使用如下 Prompt：

"基于 spec.md 中的 Req-1 Gherkin 场景，请为我编写 tests/auth.test.ts 文件。使用 Jest 框架。确保每一个 THEN 语句都对应一个 expect 断言。"

由于 Gherkin 与测试代码（尤其是 BDD 风格的测试框架）存在天然的同构关系，AI 生成的测试代码准确率极高。这就形成了一个完美的闭环：

1. **Spec:** 定义行为 (Gherkin)。  
2. **AI:** 生成测试 (Test Code)。  
3. **AI:** 生成实现 (Source Code)。  
4. **Runner:** 运行测试验证实现。  
5. **Loop:** 如果失败，AI 读取错误日志并自我修复。

这种闭环是实现 **Agentic Workflow（代理工作流）** 的基础 3。

## ---

**10\. 视觉逻辑：Mermaid 图表的深层价值**

许多开发者认为画图是浪费时间。但在 SDD 中，Mermaid 代码块不仅仅是图片，它是**拓扑逻辑的文本化表达**。

### **10.1 空间推理能力的激发**

LLM 虽然处理的是序列文本，但在处理代码架构时，需要极强的空间推理能力（模块 A 调用模块 B，模块 B 读写数据库 C）。纯文字描述很容易陷入循环依赖或逻辑断层的陷阱。

Mermaid 强制要求显式定义参与者（Participants）和交互方向（Arrows）。当 LLM 生成或读取 Mermaid 代码时，它实际上是在构建一个**有向无环图（DAG）**。这种数据结构使得 AI 能够更容易地检测出逻辑漏洞（例如：前端直接访问数据库，违反了分层架构）。

### **10.2 推荐的图表类型**

并非所有 Mermaid 图表都适合 SDD。根据实战经验，以下三种最有效：

1. **Sequence Diagram（序列图）：** **必须。** 用于描述时序逻辑和组件交互。是 API 设计和复杂业务流的灵魂 7。  
2. **Entity Relationship Diagram (ERD)：** **推荐。** 用于描述数据模型变化。比 SQL 建表语句更直观，方便 AI 理解实体间的关系（一对多、多对多）。  
3. **State Diagram（状态图）：** **可选。** 仅在涉及复杂状态机（如订单流转：待支付-\>已支付-\>发货-\>完成/退款）时使用。这能有效防止 AI 漏掉某些状态迁移路径。

## ---

**11\. 组织层级：从单体到微服务的文件结构策略**

随着项目规模的扩大，单个 Spec.md 文件会变得不可维护。如何组织这些规范文件，是区分业余与专业的关键。

### **11.1 绿地项目（Greenfield）**

对于从零开始的新项目，推荐扁平结构： .specs/ ├── constitution.md \# 全局原则 ├── 001-auth-system.md \# 功能 1 ├── 002-user-profile.md \# 功能 2 └── glossary.md \# 术语表 (统一命名规范) **深度见解：** glossary.md 是一个常被忽视但极具价值的文件。它定义了“User”、“Customer”、“Account”在系统中的确切含义，防止 AI 混淆概念 33。

### **11.2 棕地项目（Brownfield / Monorepo）**

对于大型遗留系统，必须采用**分形结构（Fractal Structure）配合渐进式披露** 23。 root/ AGENTS.md \# 根级路由，指向子目录 packages/ ui/ AGENTS.md \# UI 组件库专用规范 src/Button/spec.md backend/ AGENTS.md \# 后端架构规范 features/ payment/ \_specs/ \# 该功能模块的专用 spec 目录 001-refund.md **最佳实践：** 在根目录的 AGENTS.md 中，不要写具体规则，只写导航指南。

"如果你正在修改 UI 组件，请务必先阅读 packages/ui/AGENTS.md。如果你正在处理支付逻辑，请参考 packages/backend/features/payment/\_specs/ 下的相关文档。"

这种结构极大地减少了 Context Window 的压力。AI 代理像一个从根目录开始遍历文件系统的开发者一样，只在需要时加载特定的上下文。这就是**意图架构学**在文件组织上的体现。

## ---

**12\. 工具链配置：让 SDD 在 IDE 中落地**

拥有一份完美的 Markdown 模板只是第一步。要让它真正发挥作用，需要 IDE 的配合。以下是以 **Cursor** 和 **VS Code (GitHub Copilot)** 为例的配置指南。

### **12.1 Cursor 配置 (.cursorrules)**

Cursor 允许定义项目级的 AI 规则。这是强制执行 SDD 的最佳切入点。

**.cursorrules 内容建议：**

# **Role**

你是一个资深的 AI 软件架构师和全栈工程师。你严格遵循规范驱动开发 (SDD) 模式。

# **Workflow**

1. **Reading Phase:** 在编写任何代码之前，你必须先检查当前目录或 .specs/ 目录下是否存在与任务相关的 Spec.md 文件。  
2. **Planning Phase:** 如果没有 Spec，或者 Spec 状态为 DRAFT，你必须拒绝写代码，并主动提出帮助用户起草 Spec。  
3. **Validation Phase:** 在实现代码后，你必须根据 Spec 中的 Acceptance Criteria 进行自我审查。

# **Output Format**

* 在解释架构时，优先使用 Mermaid 图表。  
* 在列出任务时，使用 Markdown Checkbox。 这个规则文件相当于给 AI 植入了一个“超我”（Super-ego），时刻监督它不要偷懒直接写代码 28。

### **12.2 MCP (Model Context Protocol) 集成**

OpenSpec 和 Liatrio 等工具已经支持 MCP 协议 12。这意味着你可以安装一个本地的 MCP Server，让 AI 能够直接执行 Spec 相关的命令。

* **配置：** 在 claude\_desktop\_config.json 或 Cursor 的 MCP 设置中添加 OpenSpec 的 Server。  
* **能力：** 启用后，你可以直接在聊天框输入 /opsx:new feature-login，AI 不仅能生成文本，还能直接在文件系统中创建目录、生成模板文件、并在完成后归档 Spec。这将 SDD 从“文档操作”提升为“系统操作”。

## ---

**13\. 总结与展望**

规范驱动开发（SDD）并非历史的倒退，而是螺旋式的上升。在汇编语言时代，我们关注寄存器；在高级语言时代，我们关注逻辑；在 AI 时代，我们必须关注**意图（Intent）**。

Spec.md 是意图的容器。

* **Gherkin** 锁定了意图的边界。  
* **Mermaid** 描绘了意图的结构。  
* **Tasks** 规划了意图的路径。  
* **Constitution** 保证了意图的纯洁。

对于每一位希望在 AI 原生时代保持竞争力的开发者和技术领导者而言，掌握 Spec.md 的编写与管理能力，将不再是选修课，而是必修课。这不仅关乎效率，更关乎在机器智能呈指数级增长的未来，人类如何依然牢牢掌握软件系统的方向盘。

**最终建议：** 不要等待完美的工具。今天就开始。复制附录中的模板，在你的下一个功能开发中尝试 SDD。你会发现，当你花 20% 的时间在 Spec 上时，剩下的 80% 编码时间将变得前所未有的流畅与精准。

---

*(报告结束)*

#### **Works cited**

1. Spec-driven development. From requirements to design to code… | by Xin Cheng | Dec, 2025, accessed February 11, 2026, [https://billtcheng2013.medium.com/spec-driven-development-0394283a0549](https://billtcheng2013.medium.com/spec-driven-development-0394283a0549)  
2. Spec-driven development is underhyped\! Here's how you build better with Cursor\! \- Reddit, accessed February 11, 2026, [https://www.reddit.com/r/cursor/comments/1nomd8t/specdriven\_development\_is\_underhyped\_heres\_how/](https://www.reddit.com/r/cursor/comments/1nomd8t/specdriven_development_is_underhyped_heres_how/)  
3. Spec-Driven Development: When Intent Becomes the Source Code | by Deepak Babu Piskala | Feb, 2026, accessed February 11, 2026, [https://medium.com/@prdeepak.babu/spec-driven-development-when-intent-becomes-the-source-code-3af39f86b9d3](https://medium.com/@prdeepak.babu/spec-driven-development-when-intent-becomes-the-source-code-3af39f86b9d3)  
4. Inside Spec-Driven Development: What GitHub's Spec Kit Makes Possible for AI-assisted Engineering \- EPAM, accessed February 11, 2026, [https://www.epam.com/insights/ai/blogs/inside-spec-driven-development-what-githubspec-kit-makes-possible-for-ai-engineering](https://www.epam.com/insights/ai/blogs/inside-spec-driven-development-what-githubspec-kit-makes-possible-for-ai-engineering)  
5. Spec-driven development: Using Markdown as a programming language when building with AI \- The GitHub Blog, accessed February 11, 2026, [https://github.blog/ai-and-ml/generative-ai/spec-driven-development-using-markdown-as-a-programming-language-when-building-with-ai/](https://github.blog/ai-and-ml/generative-ai/spec-driven-development-using-markdown-as-a-programming-language-when-building-with-ai/)  
6. Slash Your LLM Costs by 80%: A Deep Dive into Microsoft's LLMLingua Prompt Compression \- Level Up Coding, accessed February 11, 2026, [https://levelup.gitconnected.com/slash-your-llm-costs-by-80-a-deep-dive-into-microsofts-llmlingua-prompt-compression-d993c82009c4](https://levelup.gitconnected.com/slash-your-llm-costs-by-80-a-deep-dive-into-microsofts-llmlingua-prompt-compression-d993c82009c4)  
7. Mermaid diagrams: When AI Meets Documentation | Awesome Testing, accessed February 11, 2026, [https://www.awesome-testing.com/2025/09/mermaid-diagrams](https://www.awesome-testing.com/2025/09/mermaid-diagrams)  
8. Include diagrams in your Markdown files with Mermaid \- The GitHub Blog, accessed February 11, 2026, [https://github.blog/developer-skills/github/include-diagrams-markdown-files-mermaid/](https://github.blog/developer-skills/github/include-diagrams-markdown-files-mermaid/)  
9. Boosting AI Performance: The Power of LLM-Friendly Content in Markdown, accessed February 11, 2026, [https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown](https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown)  
10. AI Agentic Programming: A Survey of Techniques, Challenges, and Opportunities \- arXiv, accessed February 11, 2026, [https://arxiv.org/html/2508.11126v2](https://arxiv.org/html/2508.11126v2)  
11. Track: San Diego Poster Session 1 \- NeurIPS, accessed February 11, 2026, [https://neurips.cc/virtual/2025/loc/san-diego/session/128331](https://neurips.cc/virtual/2025/loc/san-diego/session/128331)  
12. Lightweight markdown-based workflow for collaborating with AI coding assistants using spec-driven development methodology \- GitHub, accessed February 11, 2026, [https://github.com/liatrio-labs/spec-driven-workflow](https://github.com/liatrio-labs/spec-driven-workflow)  
13. github/spec-kit: Toolkit to help you get started with Spec-Driven Development, accessed February 11, 2026, [https://github.com/github/spec-kit](https://github.com/github/spec-kit)  
14. Cursor IDE Rules for AI: Guidelines for Specialized AI Assistant \- Kirill Markin, accessed February 11, 2026, [https://kirill-markin.com/articles/cursor-ide-rules-for-ai/](https://kirill-markin.com/articles/cursor-ide-rules-for-ai/)  
15. Spec-driven development: Unpacking one of 2025's key new AI-assisted engineering practices | Thoughtworks United States, accessed February 11, 2026, [https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices](https://www.thoughtworks.com/en-us/insights/blog/agile-engineering-practices/spec-driven-development-unpacking-2025-new-engineering-practices)  
16. How do you guys maintain a large AI-written codebase? : r/ClaudeAI \- Reddit, accessed February 11, 2026, [https://www.reddit.com/r/ClaudeAI/comments/1plse94/how\_do\_you\_guys\_maintain\_a\_large\_aiwritten/](https://www.reddit.com/r/ClaudeAI/comments/1plse94/how_do_you_guys_maintain_a_large_aiwritten/)  
17. Automating software development with Gemini-CLI | by Guru Rangavittal | Google Cloud, accessed February 11, 2026, [https://medium.com/google-cloud/automating-software-development-with-gemini-cli-1f29f9ee223f](https://medium.com/google-cloud/automating-software-development-with-gemini-cli-1f29f9ee223f)  
18. Diving Into Spec-Driven Development With GitHub Spec Kit \- Microsoft for Developers, accessed February 11, 2026, [https://developer.microsoft.com/blog/spec-driven-development-spec-kit](https://developer.microsoft.com/blog/spec-driven-development-spec-kit)  
19. How to use spec-driven development for brownfield code exploration? \- EPAM, accessed February 11, 2026, [https://www.epam.com/insights/ai/blogs/using-spec-kit-for-brownfield-codebase](https://www.epam.com/insights/ai/blogs/using-spec-kit-for-brownfield-codebase)  
20. Fission-AI/OpenSpec: Spec-driven development (SDD) for AI coding assistants. \- GitHub, accessed February 11, 2026, [https://github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)  
21. OpenSpec/docs/commands.md at main \- GitHub, accessed February 11, 2026, [https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)  
22. AGENTS.md, accessed February 11, 2026, [https://agents.md/](https://agents.md/)  
23. A Complete Guide To AGENTS.md \- AI Hero, accessed February 11, 2026, [https://www.aihero.dev/a-complete-guide-to-agents-md](https://www.aihero.dev/a-complete-guide-to-agents-md)  
24. Creating the Perfect CLAUDE.md for Claude Code \- Dometrain, accessed February 11, 2026, [https://dometrain.com/blog/creating-the-perfect-claudemd-for-claude-code/](https://dometrain.com/blog/creating-the-perfect-claudemd-for-claude-code/)  
25. How I shifted my team into Spec-Driven Development (and why it works) : r/cursor \- Reddit, accessed February 11, 2026, [https://www.reddit.com/r/cursor/comments/1op8a5s/how\_i\_shifted\_my\_team\_into\_specdriven\_development/](https://www.reddit.com/r/cursor/comments/1op8a5s/how_i_shifted_my_team_into_specdriven_development/)  
26. jam01/SRS-Template: A markdown template for Software Requirements Specification based on IEEE 830 and ISO/IEC/IEEE 29148:2011 \- GitHub, accessed February 11, 2026, [https://github.com/jam01/SRS-Template](https://github.com/jam01/SRS-Template)  
27. How to write a good spec for AI agents \- Addy Osmani, accessed February 11, 2026, [https://addyosmani.com/blog/good-spec/](https://addyosmani.com/blog/good-spec/)  
28. After building \+8 PROJECTS with Cursor AI, here's the one trick you really need to know\!, accessed February 11, 2026, [https://www.reddit.com/r/cursor/comments/1k5uv0f/after\_building\_8\_projects\_with\_cursor\_ai\_heres/](https://www.reddit.com/r/cursor/comments/1k5uv0f/after_building_8_projects_with_cursor_ai_heres/)  
29. AGENTS.md \- Windsurf Docs, accessed February 11, 2026, [https://docs.windsurf.com/windsurf/cascade/agents-md](https://docs.windsurf.com/windsurf/cascade/agents-md)  
30. A Practical Guide to Spec-Driven Development \- Quickstart \- Zencoder Docs, accessed February 11, 2026, [https://docs.zencoder.ai/user-guides/tutorials/spec-driven-development-guide](https://docs.zencoder.ai/user-guides/tutorials/spec-driven-development-guide)  
31. openspec.md \- GitHub Gist, accessed February 11, 2026, [https://gist.github.com/Darkflib/c7f25b41054a04a5835052e5a21cdf82](https://gist.github.com/Darkflib/c7f25b41054a04a5835052e5a21cdf82)  
32. Best Practices for Claude Code, accessed February 11, 2026, [https://code.claude.com/docs/en/best-practices](https://code.claude.com/docs/en/best-practices)  
33. Issues \- Eclipse Metrics, accessed February 11, 2026, [https://metrics.eclipse.org/csv/projects/technology.edc\_issues.csv](https://metrics.eclipse.org/csv/projects/technology.edc_issues.csv)  
34. How to Give Windsurf the Right Context for Smarter AI Coding \- Kaizen Softworks, accessed February 11, 2026, [https://www.kzsoftworks.com/blog/how-to-give-windsurf-the-right-context-for-smarter-ai-coding](https://www.kzsoftworks.com/blog/how-to-give-windsurf-the-right-context-for-smarter-ai-coding)