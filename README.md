# AI Memory Vault · 基于 Obsidian 的跨工具 AI 记忆库

> 一套让 Claude Code / Codex / Cursor / Cline / Gemini CLI / Trae / Qoder / ZCode 等**所有 AI 工具共享同一份记忆**的目录结构 + 规则 + 门禁脚本。全部结构、规则、脚本来自作者日常在用的私有配置，本文档即"把方法论开源"。

**为什么需要它**：每个 AI 工具都有自己的"记忆"落点——`~/.claude/`、`~/.codex/`、`.workbuddy/memory/`、各家 auto-memory……工具各记各的，换一个工具就失忆，记忆内容混在工具配置里既不可读也不可审。本方案把**记忆的唯一落点收敛到一个 Obsidian 库**（Markdown + wiki 链接 + 本地文件，任何工具都能读写），工具侧只留一个"指针 + 铁律短钩子"。

三周多的日常实测中，这套体系沉淀出四个门禁脚本与四篇分节规则。仓库内容：

| 目录 | 是什么 |
|---|---|
| [docs/](docs/) | **构建思路**：为什么这么设计、每个门禁背后的事故 |
| [starter/](starter/) | **可整体拷走的骨架**：目录结构 + 全套规则 + 示例项目（脱敏后的正本） |
| [scripts/](scripts/) | **门禁脚本**：索引生成、待办审计、编码守卫、指令分发同步 |

## 核心理念（六条）

1. **记忆唯一落点**。所有跨会话信息只写进 Obsidian 库；禁止写入任何工具私有记忆位（`.workbuddy/memory/`、`~/.claude/`、auto-memory 等）。工具的"自定义指令 / AGENTS.md / 规则文件"里只放**指向记忆库的指针 + 铁律短钩子**——那里不是记忆的仓库，是记忆库的门牌。
2. **结构化分层**。记忆不是一锅笔记，是六个层：`Preferences`（偏好）/ `Plans`（规划）/ `Decisions`（决策）/ `Lessons`（踩坑）/ `Workflows`（流程）/ `Projects/<项目名>/`（项目记忆），外加全局待办 `Todo.md`、写入登记簿 `Inbox/`、季度归档 `Archive/`。
3. **索引是派生物**。手工维护的大索引必然漂移（作者实测落后实盘 4~5 条）。各层 `_index.md` 一律由 `mem_index.py` 从笔记 frontmatter 生成，人工只润色"一句话定位"，脚本重跑不覆盖。
4. **完成 = 移走，不是标注**。待办完成时把条目追加到 `Projects/<项目名>/working/completed.md` 并**从 Todo 删除**，而不是打个 ✅ 留在原地——"完成信号残留"由 `todo_audit.py` 门禁拦截。
5. **有门禁的环节才不漂移**。纯靠"记得同步"的约定已被反复证伪。本库的每个门禁都对应一次真实事故：索引漂移、假成功入库、半部署、编码腐蚀、Todo 假声明……见 [docs/04-演化史.md](docs/04-演化史-门禁背后的事故.md)。
6. **隐私边界硬编码**。记忆库整体被 `.gitignore` 排除出公开仓库，父仓 `pre-commit` 钩子**拒绝任何触碰它的提交**——防私密笔记被误推上 GitHub，不靠自觉靠守卫。

## 目录结构一览

```text
vault/                        ← 你的 Obsidian 库根
├── AGENTS.md                 ← 仓根入口：AI 进来的第一站（四张面孔总表）
├── Templates/                ← Obsidian 模板（Memory-Note / Memory-Inbox-Note）
└── Memory/                   ← 记忆库本体（唯一记忆落点）
    ├── AGENTS.md             ← 铁律正本 + 短版钩子（分发到各工具常驻系统提示）
    ├── _index.md             ← 唯一入口：AI 先读这里，按路由再读原文
    ├── Rule.md               ← 规则目录页：操作 → 分节文件映射
    ├── rule/                 ← 规则分节：写入与禁止 / 收尾与维护 / 子代理与脚本 / vibe-coding
    ├── Todo.md               ← 全局总待办（按项目分组，不用勾选框）
    ├── Preferences/          ← 个人偏好：语言、代码风格、沟通方式
    ├── Plans/                ← 长期规划、路线图
    ├── Decisions/            ← 决策记录（背景 → 选择 → 备选方案 → 后果，带 status 生命周期）
    ├── Lessons/              ← 踩坑与解法
    ├── Workflows/            ← 固定流程手册（步骤 → 验证：<可观测信号>）
    ├── Projects/<项目名>/    ← 项目记忆：_overview.md + working/{journal,plan,completed}.md
    ├── Inbox/                ← 写入登记簿：AI 每次写完记忆留登记，待人工/自动审核
    └── Archive/              ← 季度归档
```

## 快速开始

```bash
# 1. 把骨架拷进你的 Obsidian 库（或任何你想放记忆库的地方）
cp -r starter/* /path/to/your-vault/

# 2. 全局搜索 "<你的记忆库路径>" 占位符，替换为实际路径
#    涉及：starter/AGENTS.md、Memory/AGENTS.md、Memory/rule/*、Workflows 两个文件

# 3. 生成各层索引（派生物，之后新增笔记重跑即可）
python scripts/mem_index.py --write

# 4. 装上门禁（建议挂进会话收尾 / CI）
python scripts/mem_index.py --check     # 索引漂移门禁
python scripts/todo_audit.py --check    # 待办归档门禁
python scripts/encoding_guard.py <路径>  # 编码 + 裸控制符门禁
```

**接入各 AI 工具**：见 `starter/Memory/Workflows/AI工具自定义指令.md`——完整版（贴进自定义指令框）与最小版（放进项目根 `AGENTS.md`）两套现成文案，覆盖 WorkBuddy / ZCode / Trae / Qoder / Claude Code / Codex / Cursor / Copilot / Cline 等常见落点；改完真源用 `scripts/sync_memory_instructions.py` 一键分发到多个工具的用户级指令位。

## 规则体系怎么读

```text
Memory/AGENTS.md   ← 铁律短钩子（约 30 行，常驻各工具系统提示；正本）
Memory/Rule.md     ← 目录页：按操作映射到分节文件，禁止无目的通读
Memory/rule/
├── 写入与禁止.md   ← 写入 / 登记 / Inbox 审核时读
├── 收尾与维护.md   ← 会话收尾 / 季度维护时读（含 5 门禁 + 3 报告项清单）
├── 子代理与脚本.md ← 派发子代理 / 改脚本 / 版本与守卫时读
└── vibe-coding.md  ← 大型项目开发时读（决策 status 生命周期 + 流程笔记格式）
```

设计原则是"**读取范围必须在读取前可见**"：AI 没必要每次会话通读全部规则，目录页把"什么操作读哪节"编码进文件名与钩子，把读取成本压到最低。

## 门禁脚本

| 脚本 | 拦什么 | 对应事故 |
|---|---|---|
| `mem_index.py` | 手工索引漂移、成对"逐字一致"表漂移、读时时效协议失明 | Home.md 索引落后实盘 4~5 条 |
| `todo_audit.py` | 完成信号残留、分组名与项目目录不映射、"已并入 Todo"假声明、`type`/`scope` 词表 | 声称已归档的条目静默挂起三天 |
| `encoding_guard.py` | 非 UTF-8 / BOM 残留、AI 转义吞字留下的裸控制符（让 grep 集体失明的隐形杀手） | `\v` 被当转义吃掉，坏指针存活 7 天 |
| `sync_memory_instructions.py` | 多工具指令位与真源的漂移、真源裸控制符 | 部署链"只有部署没有校验" |

设计取舍（为什么有的检查是门禁、有的只是报告）与全部事故复盘，见 [docs/03-核心设计原则.md](docs/03-核心设计原则.md) 与 [docs/04-演化史.md](docs/04-演化史-门禁背后的事故.md)。

## 文档导航

- [01-为什么需要统一记忆库](docs/01-为什么需要统一记忆库.md) —— 问题定义与方案选型
- [02-目录结构与读取路由](docs/02-目录结构与读取路由.md) —— 六层 + 三根目录、读取成本约定、读时时效协议
- [03-核心设计原则](docs/03-核心设计原则.md) —— 单一事实源 / 派生物 / 门禁文化 / 隐私边界
- [04-演化史-门禁背后的事故](docs/04-演化史-门禁背后的事故.md) —— 每个门禁的设立依据（真实事故复盘）

## License

[MIT](LICENSE) —— 结构、规则、脚本均可自由取用；如果对你有帮助，欢迎 Star / 提 Issue 分享你的改造。
