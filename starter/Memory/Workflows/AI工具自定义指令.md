---
type: workflow
scope: global
created: 2026-10-02
updated: 2026-10-02
tags: [分发钩子, 自定义指令, 记忆库, AI工具接入]
---

# AI 工具自定义指令（分发钩子）

> **用途**：各工具的指令由单一真源 `AI工具自定义指令-完整版.md` 经 `scripts\sync_memory_instructions.py` 一键部署；新接入其它工具时，从真源文件复制对应版本粘进它的设置框，能进脚本目标列表的优先加进脚本。
> **正本关系**：本页是 `Memory\AGENTS.md`（短版钩子）的**分发手册**；权威全文始终是 `Memory\Rule.md`。
> **防漂移设计**：本页**只写分发机制**（落点、适用哪版、同步命令）。指令正文一律不复制——正文只存在于真源 `AI工具自定义指令-完整版.md`，由脚本派生到各工具位。

## 一、完整版

**适用**：只能靠指令注入的工具——各类 IDE / 客户端的「自定义指令」设置框，以及网页端、手机端 AI（自定义指令框、项目指令框）。

> **正文不在本页**：唯一真源 = `Workflows\AI工具自定义指令-完整版.md`（纯指令正文，脚本 `CANON` 直接读它）。**改规则只改那份文件**，本页不留快照副本——第三份逐字复制必然漂移。改完跑 §四 的命令重新部署。

## 二、最小版

**适用**：会自动读取项目根 `AGENTS.md` 的工具——Claude Code、Codex CLI、Cursor、GitHub Copilot、OpenCode、Gemini CLI、Windsurf、Cline 等。它们进仓即可读到 `AGENTS.md`，结构类信息不必重复写。

```text
记忆库规则见工作区根 `Memory/`：
入口 `Memory\_index.md`（分层路由），权威规则 `Memory\Rule.md`，短版钩子 `Memory\AGENTS.md`。
记忆唯一落点 = 工作区根下的 `Memory/`（Markdown 记忆库），禁写任何工具私有位（`.workbuddy/memory/`、`~/.claude/`、`~/.workbuddy/MEMORY.md` 等）。
写入 / 收尾前先读 `Rule.md` 对应节并做 Inbox 登记。
```

## 三、落点对照

| 工具 | 放哪 | 用哪版 |
|---|---|---|
| 各类客户端 IDE | 设置 → 自定义指令 | 完整版 |
| Claude Code | `<项目>\CLAUDE.md`（项目级）或 `~/.claude/CLAUDE.md`（用户级） | 最小版 |
| Codex CLI | `<项目>\AGENTS.md`（自动读）；用户级 `~/.codex/AGENTS.md` | 最小版 |
| Cursor | Settings → Rules → User Rules（全局）或 `.cursor/rules/*.mdc` | 最小版 |
| GitHub Copilot | `.github/copilot-instructions.md` | 最小版 |
| OpenCode / Gemini CLI | `AGENTS.md` / `GEMINI.md`（自动读） | 最小版 |
| Windsurf / Cline / Roo | Global Rules / `.clinerules` | 最小版 |
| Trae | 设置 → 规则（存 `~\.trae-cn\user_rules\rule-*.md`，扫目录读取） | 完整版 |
| ZCode | `~\.zcode\AGENTS.md`（用户级全局指令文件） | 完整版 |
| Qoder | `~\.qoder\AGENTS.md`（用户级全局指令文件：跨项目自动注入、改后免重启热加载） | 完整版 |
| 网页端 / 手机端 AI | 自定义指令、项目（Project）指令 | 完整版 |

> 注：`~/.claude/CLAUDE.md`、`~\.zcode\AGENTS.md` 等都属**用户自己维护的配置**，与「禁写工具私有位」不冲突——后者禁的是 AI 把**记忆内容**写进工具私有目录。判据：工具位里只准放「指针 + 铁律短钩子」，任何具体偏好/决策/教训一律落记忆库。

## 四、维护约定（单一真源 + 一键同步）

- **唯一可编辑来源**：`Workflows\AI工具自定义指令-完整版.md`（纯指令正文，单一真源）。
- **改动流程**：只改上面那份真源 → 跑一条命令重新派生各处部署，**不再手工逐份抄写**：
  `python scripts\sync_memory_instructions.py`（部署前先在脚本顶部配置你的工具位路径与真源路径）
- **脚本会做**：① 备份各目标原文件；② 注入配置型工具的自定义指令字段；③ 对文件型工具位优先软链、不可用则退化为复制。脚本幂等、可反复跑。
- **改完必跑校验**：`python scripts\sync_memory_instructions.py --check`——逐字比对真源与各部署位，并体检裸控制符；漂移退出码 1。**为什么必须有这条**：只有部署没有校验的分发链，坏指针可以在各工具存活一周无人发现。
- **`--projects`（项目级钩子）**：往代码项目根的 `AGENTS.md` 生成项目入口（需先配置 `CODE_ROOT`），正文取自本手册 §二「最小版」的真源抽取。它把用户级钩子里那句字面占位符 `<项目名>` 填成真值——全链路唯一能填真项目名的一处。安全约定：已有非本脚本生成的 `AGENTS.md` → 不覆盖（用户手改文件绝不自动改）；无唯一代码根 → 只报告不猜。
- `Memory\AGENTS.md`（短版钩子）与 `Memory\Rule.md`（权威全文）不在本脚本同步范围；改铁律时按需同步短钩子（它是精简版，非逐字副本）。
- **路径口径**：真源与最小版默认按**相对路径**表述（工具进入含 `Memory/` 的工作区即自动解析，零配置）；仅当用于用户级全局指令、且项目不在记忆库工作区内时，才把真源首句替换为记忆库绝对路径——一次性动作。
