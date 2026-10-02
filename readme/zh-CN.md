# AI Memory Vault · 跨工具 AI 记忆库

[English](../README.md) | [简体中文](zh-CN.md) | [日本語](ja.md) | [한국어](ko.md) | [Español](es.md) | [Português](pt-BR.md) | [Русский](ru.md)

> 一套让 Claude Code / Codex / Cursor / Cline / Gemini CLI / Trae / Qoder / ZCode 等**所有 AI 工具共享同一份记忆**的目录结构 + 规则 + 门禁脚本。
> **核心理念：几乎零配置成本——本地不部署任何配置。** 全部内容就是 Markdown 文件加四个仅标准库的 Python 脚本：拷进一个纯 Markdown 目录即完成"部署"，无依赖、无服务、无构建、无占位符替换；工具进入工作区自动读到根 `AGENTS.md` 即开始工作，脚本自动探测记忆库位置。
>
> **它不绑定 Obsidian**：记忆库就是一个纯 Markdown 目录（`Memory/`），任何能读写文件的 Agent、任何 Markdown 编辑器都能用。作者本人用 Obsidian 查看记忆库——Templater / Dataview 等是可选增强，不是依赖。

**为什么需要它**：每个 AI 工具都有自己的"记忆"落点——`~/.claude/`、`~/.codex/`、`.workbuddy/memory/`、各家 auto-memory……工具各记各的，换一个工具就失忆，记忆内容混在工具配置里既不可读也不可审。本方案把**记忆的唯一落点收敛到一个纯 Markdown 目录**（Markdown + wiki 链接 + 本地文件，任何工具都能读写），工具侧只留一个"指针 + 铁律短钩子"。

三周多的日常实测中，这套体系沉淀出四个门禁脚本与四篇分节规则。仓库内容：

| 目录 | 是什么 |
|---|---|
| [docs/](../docs/) | **构建思路**：为什么这么设计、每个门禁背后的事故 |
| [starter/](../starter/) | **可整体拷走的骨架**：目录结构 + 全套规则 + 示例项目（脱敏后的正本） |
| [scripts/](../scripts/) | **门禁脚本**：索引生成、待办审计、编码守卫、指令分发同步 |

## 核心理念（七条）

1. **几乎零配置**：整个体系 = Markdown 文件 + 仅标准库的脚本。不部署服务、不装依赖、不写配置文件；入口靠工具自动读取工作区根 `AGENTS.md`，脚本靠向上探测找到 `Memory/`——拷进去就算装完了。规则文本用相对路径表述，唯一可能的一次性配置（用户级全局指令的绝对路径）也是可选的。
2. **记忆唯一落点**。所有跨会话信息只写进这个 Markdown 目录；禁止写入任何工具私有记忆位（`.workbuddy/memory/`、`~/.claude/`、auto-memory 等）。工具的"自定义指令 / AGENTS.md / 规则文件"里只放**指向记忆库的指针 + 铁律短钩子**——那里不是记忆的仓库，是记忆库的门牌。
3. **结构化分层**。记忆不是一锅笔记，是六个层：`Preferences`（偏好）/ `Plans`（规划）/ `Decisions`（决策）/ `Lessons`（踩坑）/ `Workflows`（流程）/ `Projects/<项目名>/`（项目记忆），外加全局待办 `Todo.md`、写入登记簿 `Inbox/`、季度归档 `Archive/`。
4. **索引是派生物**。手工维护的大索引必然漂移（作者实测落后实盘 4~5 条）。各层 `_index.md` 一律由 `mem_index.py` 从笔记 frontmatter 生成，人工只润色"一句话定位"，脚本重跑不覆盖。
5. **完成 = 移走，不是标注**。待办完成时把条目追加到 `Projects/<项目名>/working/completed.md` 并**从 Todo 删除**，而不是打个 ✅ 留在原地——"完成信号残留"由 `todo_audit.py` 门禁拦截。
6. **有门禁的环节才不漂移**。纯靠"记得同步"的约定已被反复证伪。本库的每个门禁都对应一次真实事故：索引漂移、假成功入库、半部署、编码腐蚀、Todo 假声明……见 [docs/04-演化史.md](../docs/04-演化史-门禁背后的事故.md)。
7. **隐私边界硬编码**。记忆库整体被 `.gitignore` 排除出公开仓库，父仓 `pre-commit` 钩子**拒绝任何触碰它的提交**——防私密笔记被误推上 GitHub，不靠自觉靠守卫。

## 目录结构一览

```text
你的库根/                     ← 笔记库 / 工作区根（纯 Markdown 目录即可）
├── AGENTS.md                 ← 仓根入口：AI 进来的第一站（四张面孔总表）
├── Templates/                ← 笔记模板（Memory-Note / Memory-Inbox-Note）
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

## 一句话部署

把下面这段话**原样发给任意 AI Agent**（Claude Code、Cursor、Cline、通义……网页端带文件操作的也行），它会替你完成部署、并向你复述使用约定：

```text
克隆（无法克隆就下载 zip 解压）https://github.com/star-nebula/ai-memory-vault ，
把 starter/ 目录下的全部内容拷进我的记忆库工作区根目录——我已有笔记库就用它的根，
没有就新建一个空目录。然后在该目录运行 python scripts/mem_index.py --write 生成索引。
最后读一遍工作区根的 AGENTS.md 和 Memory/_index.md，向我复述：你以后在什么时机读记忆、怎么写记忆。
```

## 手动部署（不经过 Agent）

```bash
# 唯一的"安装"动作：把骨架拷进你的笔记库 / 工作区根（Obsidian 等任何 Markdown 库均可）
cp -r starter/* /path/to/your-vault/
```

没有占位符要替换、没有依赖要安装、没有服务要部署——到这里记忆库已经可用了。AI 工具进入工作区会自动读到根 `AGENTS.md`，按 `Memory/_index.md` 的路由开始读写记忆。

两个**可选**动作（不改也不影响运行）：

```bash
# 生成各层索引（派生物；之后新增笔记重跑即可，人工只润色"一句话定位"）
python scripts/mem_index.py --write
python scripts/mem_index.py --check     # 索引漂移门禁
python scripts/todo_audit.py --check    # 待办归档门禁
python scripts/encoding_guard.py <路径>  # 编码 + 裸控制符门禁
```

**接入各 AI 工具**：见 `starter/Memory/Workflows/AI工具自定义指令.md`——完整版（贴进自定义指令框）与最小版（放进项目根 `AGENTS.md`）两套现成文案，覆盖 WorkBuddy / ZCode / Trae / Qoder / Claude Code / Codex / Cursor / Copilot / Cline 等常见落点。文案默认相对路径、即贴即用；若要把记忆库挂成**用户级全局指令**（跨工作区），才需要把首句替换成一次绝对路径，并用 `scripts/sync_memory_instructions.py` 一键分发到多个工具。

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

设计取舍（为什么有的检查是门禁、有的只是报告）与全部事故复盘，见 [docs/03-核心设计原则.md](../docs/03-核心设计原则.md) 与 [docs/04-演化史.md](../docs/04-演化史-门禁背后的事故.md)。

## 文档导航

- [01-为什么需要统一记忆库](../docs/01-为什么需要统一记忆库.md) —— 问题定义与方案选型
- [02-目录结构与读取路由](../docs/02-目录结构与读取路由.md) —— 六层 + 三根目录、读取成本约定、读时时效协议
- [03-核心设计原则](../docs/03-核心设计原则.md) —— 单一事实源 / 派生物 / 门禁文化 / 隐私边界
- [04-演化史-门禁背后的事故](../docs/04-演化史-门禁背后的事故.md) —— 每个门禁的设立依据（真实事故复盘）

## License

[MIT](../LICENSE) —— 结构、规则、脚本均可自由取用；如果对你有帮助，欢迎 Star / 提 Issue 分享你的改造。
