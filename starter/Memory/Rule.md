# Rule.md · Agent 规则路由

> 记忆唯一存储地：工作区根 `Memory/`。本文件只在写入、收尾或维护时按需读；它不是启动页。

## 读取

- **热层**：`BOOT.md`，只放稳定、跨项目、短小的内容。
- **项目启动**：`python scripts/memory_boot.py --cwd .`。
- **按需检索**：`python scripts/memory_query.py "关键词" --cwd .`。
- 读取按需取最小上下文；启动与检索分别使用 `memory_boot.py` / `memory_query.py`。
- 记忆是写下当天的快照；涉及路径、文件存在性、工具行为时，引用前先复测。
- 检索结果里的 `verified_at` 只表示该条易漂移断言最后一次现场复核日期，不等于整篇笔记已核验。

## 操作 → 分节文件

| 操作 | 读哪个文件 |
|---|---|
| 写入 / 登记 / Inbox 审核 | `rule/写入与禁止.md` |
| 会话收尾 / 季度维护 | `rule/收尾与维护.md` |
| 派发子代理 / 改 `scripts/` / 版本与守卫 | `rule/子代理与脚本.md` |
| 大型项目开发（多文件 / 跨会话 / 架构选型） | `rule/vibe-coding.md` |

## 写入与收尾

- 写前先查同主题笔记；跨层笔记按 `scope` 归属，`Projects/` 内不填 `scope`。
- 待办进 `Todo.md`；完成或取消 = 移走，追加到项目 `working/completed/YYYY-QX.md` 并从 Todo 删除。
- 会话结束只把值得跨会话保留的内容写到最终位置；不把整段对话抄进记忆库。
- 用户手改的文件绝不自动改；决策反转时新卡必须指向旧卡。
