# **OpenSpec 规范文档编写权威指南：工程标准、架构原则与实施细节**

## **1\. 绪论：规范驱动开发（SDD）与 OpenSpec 的范式转移**

在人工智能辅助软件工程（AI-Native Software Engineering）的演进过程中，开发者面临的核心挑战已从“代码生成的效率”转向了“意图传达的精确性”。传统的开发模式依赖于隐性知识（Tacit Knowledge）和碎片化的文档，这种模式在人类协作中或许尚可维系，但在面对非确定性的大型语言模型（LLM）代理时，会导致严重的上下文漂移（Context Drift）和幻觉（Hallucination）。OpenSpec 作为规范驱动开发（Spec-Driven Development, SDD）的旗舰框架，其核心价值在于将模糊的自然语言意图转化为结构化、可验证、确定性的“意图源代码”1。

本报告旨在为软件架构师、高级工程师及 AI 协同开发者提供一份详尽的 OpenSpec 文档编写指南。我们将深入剖析 OpenSpec 的目录拓扑结构、核心构件（Artifacts）的编写规范、RFC 2119 语义标准的应用，以及 Gherkin 场景描述的最佳实践。特别地，本报告将明确界定“文档中必须包含的信息”与“文档中严禁包含的信息”，以确保 AI 代理在严格的“护栏”内运行，从而实现从随机的“感觉编程”（Vibe Coding）到确定性工程交付的跨越 4。

## ---

**2\. OpenSpec 的架构哲学与目录拓扑**

要编写符合 OpenSpec 要求的文档，首先必须理解其底层的架构哲学。OpenSpec 并非简单的 Markdown 文件集合，而是一个反映软件变更生命周期的状态机。其文件系统设计体现了“单一事实来源”（Single Source of Truth）与“变更提案”（Change Proposal）的分离原则。

### **2.1 双态模型：永恒态与瞬态**

OpenSpec 强制将系统描述分为两种状态，这种分离是编写合规文档的物理基础：

| 状态类型 | 对应目录 | 定义与功能 | 编写原则 |
| :---- | :---- | :---- | :---- |
| **永恒态 (Eternal State)** | openspec/specs/ | 系统的当前真实行为（Source of Truth）。按领域（Domain）组织，如 auth/, payment/。 | **不可直接编辑**。此目录下的文件仅通过归档（Archive）操作由变更合并而来。它是系统的“宪法”。 |
| **瞬态 (Transient State)** | openspec/changes/ | 活跃的开发工作区。每个功能变更（Feature）或修复（Fix）都作为一个独立的文件夹存在。 | **主要编辑区**。包含提案（Proposal）、增量规范（Delta Specs）、设计（Design）和任务（Tasks）。 |

### **2.2 变更文件夹（Change Folder）的微观结构**

编写 OpenSpec 文档的实质，就是在 openspec/changes/\<change-id\>/ 目录下构建一套完整的认知上下文。一个合规的变更文件夹必须包含以下核心构件，它们构成了一个依赖图（Dependency Graph）6：

1. **proposal.md（意图层）**：回答“为什么要做”以及“做什么”。它是依赖图的根节点。  
2. **specs/（行为层）**：回答“系统必须表现出什么行为”。这里存放的是**增量规范（Delta Specs）**，而非全量规范。  
3. **design.md（实现层）**：回答“技术上如何实现”。它是连接行为与代码的桥梁。  
4. **tasks.md（执行层）**：回答“具体步骤是什么”。它是 AI 代理的执行指令列表。

### **2.3 归档机制：意图的版本控制**

OpenSpec 的核心生命周期结束于“归档”（Archive）。当执行 /opsx:archive 指令时，系统会将 changes/ 目录下的增量规范合并入 specs/ 目录，并将变更文件夹移动至 openspec/changes/archive/。这意味着，编写文档时必须考虑到其“历史价值”——归档后的文档将成为永久的审计记录。因此，文档必须具备**自包含性（Self-Containment）**，即在脱离当时开发环境的情况下，依然能被未来的开发者或 AI 理解 1。

## ---

**3\. 全局上下文定义：project.md 的编写规范**

在编写具体的变更文档之前，必须首先定义项目的全局上下文。project.md 文件是 AI 代理进入项目时读取的第一份文件，它充当了项目的“宪法”。一份编写良好的 project.md 能显著降低 AI 的认知负荷，防止其使用错误的技术栈或违背项目约定。

### **3.1 必须包含的信息（Mandatory Inclusions）**

根据 OpenSpec 的最佳实践与社区标准，project.md **必须** 包含以下章节，且内容需具体、准确 10。

#### **3.1.1 \#\# Purpose（项目宗旨）**

* **要求**：简明扼要地阐述项目的核心业务价值和目标用户。  
* **编写示例**：“本项目是一个基于 React 的脑力训练应用，旨在通过间隔重复算法帮助用户记忆日语词汇。”  
* **AI 影响**：帮助 AI 理解业务语境，从而在命名变量（如 userScore vs memoryRetention）时做出更符合语义的选择。

#### **3.1.2 \#\# Tech Stack（技术栈）**

* **要求**：列出所有核心技术及其**确切版本**。模糊的版本描述是导致 AI 生成不可用代码的主要原因。  
* **包含内容**：语言版本（Node.js 20+）、框架版本（React 18.2）、构建工具（Vite 5）、关键库（Tailwind CSS, Zustand）。

* ## **编写示例：**   **Tech Stack**

  * Language: TypeScript 5.3 (Strict Mode enabled)  
  * Frontend: React 18.2 (Functional Components only, Hooks required)  
  * State Management: React Context (No Redux)  
  * Styling: Tailwind CSS 3.4  
* **不包含内容**：不要列出所有 package.json 中的依赖，仅列出对架构有决定性影响的核心库。

#### **3.1.3 \#\# Project Conventions（项目约定）**

* **要求**：明确代码风格、架构模式和文件组织规则。这是防止 AI “自由发挥”的关键护栏。  
* **核心子章节**：  
  * **Code Style**：命名规范（驼峰 vs 下划线）、导出偏好（Named Exports vs Default Exports）。  
  * **Architecture Patterns**：架构模式（如“原子设计”、“六边形架构”）。  
  * **Testing Strategy**：测试工具及覆盖率要求。

* ### **编写示例：**   **Code Style**

  * Use PascalCase for components and camelCase for functions.  
  * Prefer named exports over default exports to facilitate refactoring.  
  * Interfaces must be prefixed with I (e.g., IUser).

#### **3.1.4 \#\# Domain Context（领域上下文）**

* **要求**：定义项目特有的术语表（Glossary）。  
* **编写示例**：“SKU: 库存量单位，指代唯一的商品变体。”

### **3.2 严禁包含的信息（Strict Exclusions）**

* **瞬态任务列表**：不要在 project.md 中包含“待办事项”或“下周计划”。这些属于 changes/ 目录的职责。  
* **大量源码粘贴**：不要直接粘贴核心算法的完整代码。应使用文件引用（File References）引导 AI 读取特定文件。  
* **主观臆测**：避免使用“可能”、“也许”等不确定词汇。project.md 必须是确定性的陈述。

## ---

**4\. 变更提案：proposal.md 的编写规范**

proposal.md 是任何变更的起点，它定义了工作的边界。在 OpenSpec 中，清晰的提案是防止“范围蔓延”（Scope Creep）的第一道防线。

### **4.1 核心章节要求**

#### **4.1.1 \#\# Intent（意图）**

* **要求**：描述“为什么”要进行此变更。必须从用户价值或业务需求的角度出发，而非技术角度。  
* **正例**：“用户反馈夜间使用应用时眼睛疲劳，需要提供深色模式以改善体验。”  
* **反例**：“在 body 标签上添加 dark-theme 类。”（这是实现细节，属于 Design）。

#### **4.1.2 \#\# Scope（范围）**

* **要求**：这是最关键的部分。必须明确列出 **In-Scope（范围内）** 和 **Out-of-Scope（范围外）** 的项目。

* ## **编写示例：**   **Scope**   **In Scope:**

  * Settings page toggle switch.  
  * System preference auto-detection.  
  * LocalStorage persistence.

  **Out of Scope:**

  * Custom color themes (user-defined colors).  
  * Per-page theme overrides.  
* **原理**：AI 代理倾向于过度表现（Over-perform），若不明确排除“自定义配色”，AI 可能会自作主张地引入复杂的配色系统，浪费 Token 并增加维护成本 6。

#### **4.1.3 \#\# Approach（方法摘要）**

* **要求**：高层次的技术策略摘要，不超过 3-5 行。  
* **编写示例**：“使用 CSS 变量定义颜色令牌，并通过 React Context 管理当前的主题状态。”

### **4.2 常见错误与排除项**

* **排除详细需求**：不要在这里写“按钮必须是蓝色的”。详细需求属于 spec.md。  
* **排除具体代码**：不要在提案中写代码片段。  
* **排除任务清单**：不要在这里列出“第一步、第二步”。那是 tasks.md 的内容。

## ---

**5\. 核心规范：spec.md 的编写规范（重点）**

spec.md 是 OpenSpec 体系的核心，是“单一事实来源”的载体。编写合规的 spec.md 需要严格遵循 **增量模式（Delta Model）**、**RFC 2119 语义标准** 和 **Gherkin 场景描述**。这是区分专业 SDD 实践与业余文档的关键所在。

### **5.1 增量规范（Delta Specs）机制**

在 openspec/changes/\<id\>/specs/ 目录下编写的规范文件，实际上是“补丁”（Patch）。你不需要重写整个系统的规范，只需要描述**相对于当前状态的变更**。OpenSpec 通过特定的 Markdown 标题来解析这些变更 6。

#### **5.1.1 必须使用的增量标题**

* **\#\# ADDED Requirements**：用于引入全新的功能或行为。  
* **\#\# MODIFIED Requirements**：用于修改现有的行为。**必须**引用原有需求的名称，并清晰描述变更点。  
* **\#\# REMOVED Requirements**：用于废弃功能。  
* **\#\# RENAMED Requirements**：用于术语的更迭。

### **5.2 语法要求一：规范性关键词（RFC 2119）**

OpenSpec 的验证器（Validator）通常配置为**严格模式（Strict Mode）**，这意味着每一条需求声明（Requirement）都**必须**包含符合 RFC 2119 标准的关键词。如果缺失这些关键词，openspec validate 命令将报错 12。

| 关键词 | 语义定义 | AI 代理的执行逻辑 | 编写示例 |
| :---- | :---- | :---- | :---- |
| **MUST / SHALL** | **绝对要求**。系统必须满足此条件，否则视为失败。 | 赋予最高权重（Logit Bias）。生成的代码若不满足此条件，自我修正机制会介入。 | "The system **MUST** encrypt passwords using bcrypt." |
| **MUST NOT / SHALL NOT** | **绝对禁止**。 | 作为负向约束（Negative Constraint）。 | "The API **MUST NOT** return the password field in the response." |
| **SHOULD** | **推荐**。在不违反 MUST 的前提下尽量满足。 | 作为软约束（Soft Constraint）。AI 会尝试实现，但若遇冲突可能放弃。 | "The response time **SHOULD** be under 200ms." |
| **MAY** | **可选**。 | 作为特性开关或低优先级任务。 | "Users **MAY** upload an avatar." |

### **5.3 语法要求二：需求的层级结构**

OpenSpec 的解析器（markdown-parser.ts）依赖特定的 Markdown 层级结构来提取需求。一个标准的需求块**必须**遵循以下结构 6：

### **Requirement: \[唯一且具描述性的名称\]**

#### **Scenario: \[场景名称\]**

* **GIVEN** \[前置条件\]  
* **WHEN** \[触发动作\]  
* **THEN** \[预期结果\]

### **5.4 语法要求三：Gherkin 场景（Scenarios）**

这是 OpenSpec 文档中最具实操价值的部分。每个 Requirement **必须**至少包含一个 Scenario。没有场景的需求被称为“欠规范”（Underspecified），会被验证工具标记为警告或错误 6。

#### **5.4.1 编写 Gherkin 场景的规则**

1. **关键词加粗**：必须使用 **GIVEN**, **WHEN**, **THEN**, **AND** 并加粗，以便解析器识别。  
2. **覆盖率**：必须覆盖“快乐路径”（Happy Path）、“边缘情况”（Edge Cases）和“错误状态”（Error States）。  
3. **可测试性**：场景描述必须足够具体，以便能直接转化为单元测试或集成测试代码。

#### **5.4.2 编写示例（以双因素认证为例）**

### **Requirement: Two-Factor Authentication**

The system **MUST** enforce TOTP-based 2FA for all users with the admin role.

#### **Scenario: Admin Login Flow**

* **GIVEN** a user with role: admin and 2FA enabled  
* **WHEN** they submit a valid username and password  
* **THEN** the system returns a 2FA\_REQUIRED challenge  
* **AND** does not issue an access token

#### **Scenario: Non-Admin Login Flow**

* **GIVEN** a user with role: user  
* **WHEN** they submit a valid username and password  
* **THEN** the system issues an access token immediately

### **5.5 应该包含的信息（Inclusions）**

* **功能性需求（Functional Requirements）**：用户可见的行为。  
* **非功能性需求（NFRs）**：  
  * **性能**：“API 响应时间 **MUST** 小于 500ms。” 16  
  * **安全性**：“数据在传输过程中 **MUST** 使用 TLS 1.3 加密。” 17  
  * **可访问性**：“所有图片 **MUST** 包含 alt 属性。”  
* **数据约束**：“用户名长度 **MUST** 在 3 到 20 个字符之间。”

### **5.6 不应该包含的信息（Exclusions & Anti-Patterns）**

* **实现细节（Implementation Details）**：这是最严重的错误。**严禁**在 spec.md 中提及具体的类名、函数名、CSS 类名或数据库表名。这些属于 design.md。  
  * *错误写法*：“User 表的 is\_admin 字段必须设为 true。”  
  * *正确写法*：“系统 **MUST** 将该用户识别为管理员。”  
  * *原因*：如果在 Spec 中硬编码了实现细节，一旦重构代码（如将 is\_admin 改为 roles 数组），Spec 就会失效（Context Rot）。Spec 应该描述行为，行为是相对稳定的，而实现是易变的。  
* **伪代码（Pseudocode）**：不要在 Spec 中写伪代码。使用自然语言和 Gherkin。  
* **模糊形容词**：避免使用“快速的”、“用户友好的”、“现代的”。这些词对 AI 没有任何约束力。必须使用可量化的指标。  
* **UI 视觉细节**：不要写“按钮是圆角的”。应写“按钮符合设计系统的主要操作样式”。

## ---

**6\. 技术设计：design.md 的编写规范**

如果说 spec.md 是“做什么”（What），那么 design.md 就是“怎么做”（How）。这个文档将抽象的需求转化为具体的技术决策。

### **6.1 何时需要 design.md？**

对于简单的变更，design.md 可能是可选的（取决于 Schema 配置）。但在以下“复杂度触发”（Complexity Triggers）场景下，**必须**编写 design.md 3：

1. 涉及跨模块或跨服务的变更。  
2. 引入了新的架构模式或第三方库。  
3. 涉及数据库 Schema 的修改。  
4. 涉及高安全性或高性能要求的实现。

### **6.2 核心章节要求**

#### **6.2.1 \#\# Technical Approach（技术方案）**

* **要求**：描述核心技术路径。  
* **示例**：“利用 React Context API 创建 ThemeContext，通过 useLayoutEffect 防止样式闪烁（FOUC）。”

#### **6.2.2 \#\# Architecture Decisions（架构决策）**

* **要求**：记录“决策记录”（ADR）。不仅要写选择了什么，还要写**为什么**选择，以及**放弃了什么**。  
* **示例**：**Decision**: Use localStorage for persistence.  
  **Reason**: No sensitive data is stored; server-side syncing is out of scope.  
  **Alternative Considered**: Cookies (rejected due to unnecessary payload overhead).

#### **6.2.3 \#\# Data Flow（数据流）**

* **要求**：描述数据如何在组件、Store 和 API 之间流动。  
* **示例**：“User Clicks Toggle \-\> Context Update \-\> LocalStorage Write \-\> DOM Class Update.”

#### **6.2.4 \#\# File Changes（文件变更列表）**

* **要求**：明确列出需要创建或修改的文件路径。这能极大地帮助 AI 规划文件系统操作 6。

### **6.3 数据库 Schema 规则（Database Schema Rule）**

这是一个特殊的硬性规定：**如果变更涉及数据持久化，design.md 必须显式定义 Schema 变更。** AI 不应从行为规范中推断数据库结构 3。

* ### **编写示例：**   **Database Changes**   **Table: users**   **Operation: ADD COLUMN**   **Field: preferences type JSONB default {}**

### **6.4 不应该包含的信息**

* **业务规则的重复**：不要复制 spec.md 中的需求。如果需要引用，请使用“See Requirement: Auth”的引用方式。  
* **“待定”标记**：不要在 Design 中留 TBD（待定）。Design 必须在编码开始前确定。

## ---

**7\. 执行计划：tasks.md 的编写规范**

tasks.md 是 AI 代理的执行清单。编写此文档的关键在于**粒度控制（Granularity）**。

### **7.1 结构与格式**

必须使用 Markdown 复选框列表（- \[ \]），并建议使用层级编号（1.1, 1.2）以体现依赖关系 7。

### **7.2 编写原则**

* **原子性（Atomicity）**：每个任务应当足够小，使得 AI 可以在单一的对话回合（Turn）中完成。  
  * *反例*：“实现深色模式。”（太大了，AI 会迷失）。  
  * *正例*：“创建 src/context/ThemeContext.tsx 骨架。”  
* **依赖顺序**：按照 基础设施 \-\> 后端 \-\> 前端 \-\> 测试 的顺序排列。  
* **验证步骤**：明确包含运行测试的任务。  
  * *示例*：“- \[ \] 2.3 Run npm test ThemeToggle to verify behavior.”

## ---

**8\. 代理指令：AGENTS.md 的元编程**

AGENTS.md 是“给机器人的 Readme”。它不描述项目，而是描述**如何开发项目**。

### **8.1 包含内容**

* **指令白名单**：明确允许 AI 自动执行的命令（如 ls, npm test）和需要许可的命令（如 rm, git push）。  
* **输出格式**：要求 AI 在输出代码时总是包含文件路径注释。  
* **工作流覆盖**：定义特殊的 Git 工作流或提交信息规范（Commit Message Convention）。

### **8.2 嵌套规则**

OpenSpec 支持嵌套的 AGENTS.md。你可以在 src/backend/AGENTS.md 中定义后端特有的规则（如“必须使用 Result 类型”），而在根目录定义全局规则。AI 会优先读取距离最近的 AGENTS.md 21。

## ---

**9\. 验证与质量保证**

编写完文档后，必须通过验证。OpenSpec 提供了 CLI 工具来执行此操作。

### **9.1 openspec validate 检查项**

在 CI/CD 流程或本地提交前，运行 openspec validate \--strict。系统将检查：

1. **文件完整性**：Change 文件夹是否包含必要的 Artifacts。  
2. **语法合规性**：Requirement 是否有对应的 Scenario。  
3. **关键词合规性**：Requirement 是否包含 MUST/SHALL。  
4. **引用有效性**：MODIFIED 需求是否正确引用了原需求 15。

## ---

**10\. 总结：文档中的“红线”与最佳实践**

为了满足用户的核心诉求，在此总结 OpenSpec 文档的“红线”（不应包含的信息）与“金标准”（必须包含的信息）。

### **10.1 严禁包含（Prohibited）**

1. **实现细节混入规范**：spec.md 中绝不可出现代码、类名、数据库字段名。  
2. **模糊的自然语言**：禁止使用“最好能”、“尽量”、“用户友好”等非确定性词汇。  
3. **大段源码粘贴**：禁止在任何文档中粘贴巨大的代码块，应使用文件引用。  
4. **混合时态**：  
   * Spec 用将来时（SHALL）。  
   * Design 用现在时（Uses, Implements）。  
   * Tasks 用祈使句（Create, Update）。  
   * **混用时态会导致 AI 无法区分“现状”与“目标”。**

### **10.2 必须包含（Mandatory）**

1. **意图与范围**：proposal.md 中必须有明确的 In-Scope/Out-of-Scope。  
2. **规范性关键词**：spec.md 中必须使用 RFC 2119 关键词。  
3. **Gherkin 场景**：每个需求必须有 GIVEN/WHEN/THEN 场景。  
4. **技术决策理由**：design.md 中必须解释“为什么”选择该技术。  
5. **原子化任务**：tasks.md 必须拆解为可执行的原子步骤。

通过严格遵循上述规范，开发者可以将 OpenSpec 文档打造为一套精确控制 AI 行为的“指令集”，从而在大型项目中实现高质量、可维护的代码生成。

### ---

**参考资料索引**

* 7  
  : OpenSpec 仓库结构与基础概念。  
* 6  
  : Proposal 与 Artifacts 的定义。  
* 6  
  : 增量规范（Delta Specs）机制。  
* 12  
  : RFC 2119 关键词与验证规则。  
* 6  
  : Gherkin 场景编写规范。  
* 10  
  : project.md 的内容要求。  
* 3  
  : 数据库 Schema 在 Design 中的特殊规则。  
* 21  
  : AGENTS.md 的最佳实践。

#### **Works cited**

1. Steering the Agentic Future: A Technical Deep Dive into BMAD, Spec Kit, and OpenSpec in the SDD Landscape | by Aparna Pradhan | Medium, accessed February 16, 2026, [https://medium.com/@ap3617180/steering-the-agentic-future-a-technical-deep-dive-into-bmad-spec-kit-and-openspec-in-the-sdd-4f425f1f8d2b](https://medium.com/@ap3617180/steering-the-agentic-future-a-technical-deep-dive-into-bmad-spec-kit-and-openspec-in-the-sdd-4f425f1f8d2b)  
2. Fission-AI/OpenSpec: Spec-driven development (SDD) for AI coding assistants. \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec](https://github.com/Fission-AI/OpenSpec)  
3. How to make AI follow your instructions more for free (OpenSpec) \- DEV Community, accessed February 16, 2026, [https://dev.to/webdeveloperhyper/how-to-make-ai-follow-your-instructions-more-for-free-openspec-2c85](https://dev.to/webdeveloperhyper/how-to-make-ai-follow-your-instructions-more-for-free-openspec-2c85)  
4. A few random notes from Claude coding quite a bit last few weeks | Hacker News, accessed February 16, 2026, [https://news.ycombinator.com/item?id=46771564](https://news.ycombinator.com/item?id=46771564)  
5. AI \- LLBBL Blog, accessed February 16, 2026, [https://llbbl.blog/categories/ai/](https://llbbl.blog/categories/ai/)  
6. OpenSpec/docs/concepts.md at main \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md)  
7. OpenSpec/docs/getting-started.md at main \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md)  
8. I Found the Simplest AI Dev Tool Ever \- YouTube, accessed February 16, 2026, [https://www.youtube.com/watch?v=cQv3ocbsKHY](https://www.youtube.com/watch?v=cQv3ocbsKHY)  
9. Evolving specs · github spec-kit · Discussion \#152, accessed February 16, 2026, [https://github.com/github/spec-kit/discussions/152](https://github.com/github/spec-kit/discussions/152)  
10. OpenSpec vs Spec Kit: Choosing the Right AI-Driven Development Workflow for Your Team, accessed February 16, 2026, [https://hashrocket.com/blog/posts/openspec-vs-spec-kit-choosing-the-right-ai-driven-development-workflow-for-your-team](https://hashrocket.com/blog/posts/openspec-vs-spec-kit-choosing-the-right-ai-driven-development-workflow-for-your-team)  
11. OpenSpec/docs/customization.md at main \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)  
12. RFC 2119 \- Key words for use in RFCs to Indicate Requirement Levels \- IETF Datatracker, accessed February 16, 2026, [https://datatracker.ietf.org/doc/html/rfc2119](https://datatracker.ietf.org/doc/html/rfc2119)  
13. \[Fix/Enhancement\] Hardcoded spec format prevents custom ... \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/issues/666](https://github.com/Fission-AI/OpenSpec/issues/666)  
14. Richer Spec Validation & Tooling · Issue \#431 · Fission-AI/OpenSpec \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/issues/431](https://github.com/Fission-AI/OpenSpec/issues/431)  
15. OpenSpec Deep Dive: Spec-Driven Development Architecture ..., accessed February 16, 2026, [https://redreamality.com/garden/notes/openspec-guide/](https://redreamality.com/garden/notes/openspec-guide/)  
16. Non-Functional Requirements (with Examples) | Khalil Stemmler, accessed February 16, 2026, [https://khalilstemmler.com/articles/object-oriented/analysis/non-functional-requirements/](https://khalilstemmler.com/articles/object-oriented/analysis/non-functional-requirements/)  
17. Non-Functional Requirements: Tips, Tools, and Examples \- Perforce Software, accessed February 16, 2026, [https://www.perforce.com/blog/alm/what-are-non-functional-requirements-examples](https://www.perforce.com/blog/alm/what-are-non-functional-requirements-examples)  
18. Getting Started with Spec-Driven Development Using AI Coding Assistants (Part 1\) \- Medium, accessed February 16, 2026, [https://medium.com/@bryanlam.dev/getting-started-with-spec-driven-development-using-ai-coding-assistants-part-1-9bad0c079fc1](https://medium.com/@bryanlam.dev/getting-started-with-spec-driven-development-using-ai-coding-assistants-part-1-9bad0c079fc1)  
19. openspec/AGENTS.md, accessed February 16, 2026, [https://forge.apps.education.fr/coopmaths/mathalea/-/blob/8e70b2da43c52b0332c7fe72b2b857143a441e2c/openspec/AGENTS.md](https://forge.apps.education.fr/coopmaths/mathalea/-/blob/8e70b2da43c52b0332c7fe72b2b857143a441e2c/openspec/AGENTS.md)  
20. OpenSpec/docs/commands.md at main \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md](https://github.com/Fission-AI/OpenSpec/blob/main/docs/commands.md)  
21. Improve your AI code output with AGENTS.md (+ my best tips) \- Builder.io, accessed February 16, 2026, [https://www.builder.io/blog/agents-md](https://www.builder.io/blog/agents-md)  
22. AGENTS.md, accessed February 16, 2026, [https://agents.md/](https://agents.md/)  
23. Fission \- GitHub, accessed February 16, 2026, [https://github.com/Fission-AI](https://github.com/Fission-AI)