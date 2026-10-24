# 记忆库规则（Agent-first）

记忆唯一存储地：工作区根下的 `Memory/`（Markdown 记忆库）。当前项目名不预填，由运行时按项目根 `AGENTS.md` / 工作目录判定。

## 读取

- 普通问答 / 单轮任务：不默认扫描记忆库；需要用户偏好时只读 `Memory/BOOT.md`。
- 项目任务：运行 `python scripts/memory_boot.py --cwd .`。它只返回全局热记忆、当前项目 `_overview.md`、`_state.md` 与 Todo 切片。
- 查原因 / 历史 / 踩坑：运行 `python scripts/memory_query.py "关键词" --cwd .`；默认返回 top-k 片段，排除 archived/superseded。
- 不要预读整棵记忆树；启动只取上面的有界包，更多背景按需检索。
- 同一会话只加载一次启动包；除非用户要求刷新或记忆已写入，不要反复读取同一文件。

## 写入

1. 先读 `Memory/rule/写入与禁止.md` 对应分节，再写最终位置。
2. 每次写入后在同日 `Memory/Inbox/YYYY-MM-DD.md` 登记路径与一句话摘要。
3. 待办统一进 `Memory/Todo.md`；完成 = 追加到 `Projects/<项目名>/working/completed.md` 并从 Todo 删除。
4. 用户手改的文件绝不自动改；决策反转新建笔记并互链。

## 禁止

- 禁写 `.workbuddy/memory/`、`.memory/`、`.trae/`、`.agent*/`、`~/.workbuddy/MEMORY.md`、`~/.claude/`、`~/.codex/` 等工具私有记忆位。
- 工具自己的 auto-memory 只能视为缓存影子层，不作为落点或证据；需要跨会话存活的事实必须同轮落进 `Memory/`。

## 派发子代理

- 记忆库位于工作区根 `Memory/`；写前按 `Memory/Rule.md` 的映射读对应分节。
- 第一动作：按任务运行 `memory_boot.py` 或 `memory_query.py`，不要预读整棵记忆树。
- 完成重要工作后回传「是否需落记忆库」；只读子代理须列出待落库条目，由父会话代写。
