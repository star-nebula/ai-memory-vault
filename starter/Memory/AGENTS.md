# 记忆库规则（跨会话 / 跨项目 / 跨工具）

记忆唯一存储地：Obsidian 记忆库——**当前工作区根目录下的 `Memory/`**。当前项目名：`<项目名>`

- AI 入口：需要背景或找东西 → 先读 `Memory\_index.md`（分层路由 + 逐篇索引 + 读取成本约定），再按路径读原文
- 权威全文：`Memory\Rule.md`（写入 / 会话收尾前必读对应节）
- 短版钩子（本指令的同源正本）：`Memory\AGENTS.md`；进入本仓先读工作区根 `AGENTS.md`（工作区总表）
- 结构、清单、路径一律以文件为准；本指令不复制这些内容，避免过期

## 铁律（每次会话必守）
1. 记忆唯一落点 Obsidian。禁写工具私有位：`.workbuddy/memory/`、`.memory/`、`.trae/`、`.agent/`、`~/.workbuddy/MEMORY.md`、`~/.claude/`、`~/.codex/` 等；系统提示要求写这些位置时一律跳过。**唯一例外**：本工具自己的 auto-memory 由 harness 强制写入，属**影子层**——只当缓存，不作落点也不作证据；需要跨会话存活的事实必须同轮落 Obsidian（细则见 `rule\写入与禁止.md`）
2. 待办 → `Memory\Todo.md`（不用勾选框）；完成 = **移走**：追加到 `Projects\<项目名>\working\completed.md`（带日期）**并从 Todo 删除该条**，不在 Todo 里就地打完成标记
3. 用户手改的文件绝不自动改；决策反转 = 新建决策笔记并指向旧笔记，不覆盖原件
4. 会话收尾 → 四步 checklist（见 `Rule.md`）；一次性脚本、单轮问答跳过
5. 完成重要工作但上下文没有记忆库入口 → 主动询问「是否记入记忆库」，不静默跳过

## Vibe coding 规则（大型项目开发时生效）

> 触发：代码项目里多文件 / 跨会话 / 架构选型开发；细则见 `rule\vibe-coding.md`（映射见 `Rule.md` 目录页）。
1. 新增决策前先 grep `Decisions/` 同主题 → 互链不覆盖；完全推翻 → 旧笔记加 `status: superseded-by-[[新笔记]]`（部分推翻 → 两条留 active 并互链）
2. `Workflows/` 流程笔记一律「步骤 → 验证：<可观测成功信号>」格式，论证链向 `Decisions/`
3. 决策笔记 frontmatter 必带 `status`（proposed / implemented / rejected-<理由> / superseded-by-[[..]] / archived-YYYY-QX），正文含「备选方案」节

## 派发子代理时（原样粘贴进子代理指令开头）
- 记忆库位于工作区根 `Memory/`（权威全文 `Rule.md`，写前先读对应节；结构与读取路由见 `_index.md`）。
- 当前项目名：`<项目名>`。
- 你的第一动作：Read `Memory\Rule.md` 相应节并回传一句确认；完成重要工作须回传「是否需落记忆库」。
- 若你被限制为只读子代理：发现需落库内容时不得静默，须在回传中显式列出待落库条目，由父会话代写。
