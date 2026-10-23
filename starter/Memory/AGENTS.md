# 记忆库 Agent 钩子

记忆唯一存储地：工作区根下的 `Memory/`（Markdown）。当前项目名不预填，由 `scripts/memory_boot.py` / `memory_query.py` 在运行时判定。

## 读取契约

- **普通任务**：不默认扫描记忆库；需要用户偏好时只读 `Memory/BOOT.md`。
- **项目任务**：运行 `python scripts/memory_boot.py --cwd <项目根或当前目录>`，只加载该项目的 overview、`_state.md` 和 Todo 切片。
- **历史 / 原因 / 排障**：运行 `python scripts/memory_query.py "关键词" --cwd <项目根或当前目录>`；默认排除 archived/superseded，返回 top-k 片段。
- **不要**在启动时读 `Memory/_index.md` 或各层 `_index.md`。它们是生成/校验用目录，不是 Agent 启动入口。
- 同一会话只加载一次启动包；除非用户要求刷新或记忆已写入，不要反复读同一文件。

## 写入契约

- 先读 `Memory/rule/写入与禁止.md` 对应分节，再写最终位置。
- 每次写入后在同日 `Memory/Inbox/YYYY-MM-DD.md` 登记路径与一句话摘要。
- 待办统一进 `Memory/Todo.md`。完成 = 追加到 `Projects/<项目名>/working/completed.md` 并从 Todo 删除，不在 Todo 中打勾。
- `BOOT.md` 只放稳定、跨项目、短小的内容；项目状态放 `_state.md`，过程历史放 `journal.md`。

## 铁律

1. 记忆只落 `Memory/`，禁写任何工具私有记忆位；auto-memory 只能当缓存影子层。
2. 用户手改的文件绝不自动改；决策反转新建笔记并互链。
3. 检索起点必须在 `Memory/` 内；「无匹配」不等于「不存在」。
4. 记忆是写下当天的快照；涉及路径、文件存在性、工具行为时，引用前先复测。
5. 完成重要工作后询问用户是否记入记忆库，不静默跳过。
