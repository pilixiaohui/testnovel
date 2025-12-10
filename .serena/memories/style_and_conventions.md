语言与文档：默认英文/中文双语，翻译文本集中在 i18n.ts，UI 文案走 t() 取值。
代码风格：React 函数组件 + Hooks，TypeScript interface 定义模型；使用 Context 提供全局状态；状态更新多用不可变拷贝 map/展开；异步函数直接 async/await。
样式：依赖 Tailwind CDN 类名（无 PostCSS/TW 构建），类名写在组件 className 中；字体 JetBrains Mono + Inter；背景深色系。
状态/存储：ProjectState 持久化到 localStorage（除 apiKey、isGenerating）。API Key 不写入存储，默认从 process.env.API_KEY 注入，可在设置弹窗输入。
数据约定：Scene 包含 beats、entities、content；Beat Sheet 先生成节拍再生成 prose；EntityState 类型固定枚举；SnowflakeStep 枚举驱动流程。
其他：vite.config.ts 通过 define 注入 GEMINI_API_KEY；import 路径支持 @/ 别名指向项目根。