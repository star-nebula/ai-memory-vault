# AGENTS.md — Agent 记忆入口

> 记忆库是给 Agent 按需读取的 Markdown 数据层，不是人类浏览目录。
> 工作区根 `AGENTS.md` 只放门牌、硬规则和读取命令；具体记忆内容一律在 `Memory/`。

## 启动契约

1. **普通问答 / 单轮任务**：不要默认扫描记忆库。只有任务涉及用户偏好、项目背景、历史决策或排障时，才读 `Memory/BOOT.md`。
2. **项目任务**：先运行
   `python scripts/memory_boot.py --cwd .`
   它只返回：全局热记忆 + 当前项目 `_overview.md` + `_state.md` + 当前项目 Todo 切片。
3. **查原因 / 查历史 / 查踩坑**：运行
   `python scripts/memory_query.py "关键词" --cwd .`，
   默认只返回前几条命中片段，不展开整篇笔记。
4. **禁止预读整棵记忆树**。启动只取 `memory_boot.py` 返回的包；需要更多背景时再用 `memory_query.py` 做有界检索。
5. 同一会话中，启动包只加载一次；除非用户要求刷新或记忆发生变化，否则不要反复读取同一文件。

## 硬规则

1. **记忆唯一落点 = 工作区根 `Memory/`**（纯 Markdown）。禁止写入 `.workbuddy/memory/`、`.memory/`、`.trae/`、`.agent*/`、`~/.workbuddy/MEMORY.md`、`~/.claude/`、`~/.codex/` 等工具私有记忆位。工具自己的 auto-memory 只能视为缓存影子层，不作为落点或证据；跨会话事实必须同轮落进 `Memory/`。
2. **写入 / 收尾前**读 `Memory/rule/写入与禁止.md` 或 `Memory/rule/收尾与维护.md` 对应分节；写完在该日 `Memory/Inbox/YYYY-MM-DD.md` 登记。
3. **用户手改的文件绝不自动改**；决策反转 = 新建决策笔记并指向旧笔记，不覆盖原件。
4. **检索起点必须放在 `Memory/`**。记忆层若被 `.gitignore` 忽略，从工作区根起手的 ripgrep 系检索会返回「无匹配」；「无匹配」不等于不存在。
5. **当前项目名不预填**：优先由项目根 `AGENTS.md` 的 `当前项目名` 行提供，其次从工作目录推断；无法确定时问用户，不猜。`memory_boot.py` / `memory_query.py` 已封装这套判定。

## 写入与读取的分工

- 待办：`Memory/Todo.md`；完成 = 移走，追加到 `Projects/<项目名>/working/completed/YYYY-QX.md` 后从 Todo 删除。
- 过程历史：`Projects/<项目名>/working/journal/YYYY-MM.md`；默认不读全文，需要时用 `memory_query.py --include-history`。
- 长期知识：`Preferences/`、`Plans/`、`Decisions/`、`Lessons/`、`Workflows/`；按任务检索，不按目录通读。
- `Memory/BOOT.md` 是唯一常驻热层，只放稳定、跨项目、短小的内容。

## 同名文件消歧（易混清单）

> 完整五组表只此一份；不再维护人看索引或第二份副本。

| 易混名 | 有两处（或多处） | 该取 |
|---|---|---|
| `AGENTS.md` | 工作区根 `AGENTS.md`（Agent 入口）／`Memory/AGENTS.md`（记忆钩子） | 看工作区红线 → 根版；写记忆/收尾 → Memory 版 |
| `Inbox/` | 工作区级 `Inbox/`（闪念捕获，如有）／`Memory/Inbox/`（**记忆登记簿**） | 记忆登记 → `Memory/Inbox/` |
| `Archive/` | 工作区级 `Archive/`（素材归档，如有）／`Memory/Archive/`（季度归档）／`Memory/Inbox/Archive/`（登记结案留档） | 记忆归档按用途取 |
| `Templates/` | 工作区根 `Templates/`（记忆笔记模板）／其他同名目录 | 记忆笔记模板一律取工作区根 `Templates/` |
| `Projects/` | `Memory/Projects/`（项目记忆）／代码项目根（工作区外） | 记忆 → `Memory/Projects/`；代码 → 代码项目根 |

## 脚本

- `scripts/memory_boot.py`：生成小型启动包。
- `scripts/memory_query.py`：有界关键词检索，返回路径与片段。
- `scripts/todo_audit.py`、`scripts/encoding_guard.py`、`scripts/state_audit.py`：校验与维护。
- `scripts/sync_memory_instructions.py`：分发并校验各 AI 工具的用户级/项目级指令。
