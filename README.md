# AI Memory Vault · Cross-Tool AI Memory Vault

[简体中文](readme/zh-CN.md) | [日本語](readme/ja.md) | [한국어](readme/ko.md) | [Español](readme/es.md) | [Português](readme/pt-BR.md) | [Русский](readme/ru.md)

> A directory structure + rulebook + gate scripts that let **every AI tool** — Claude Code, Codex, Cursor, Cline, Gemini CLI, Trae, Qoder, ZCode and more — share **one memory**.
> **Core philosophy: near-zero configuration — deploy nothing locally.** The whole system is Markdown files plus standard-library-only Python scripts: copying it into a plain Markdown directory *is* the deployment. No dependencies, no services, no builds, no placeholders to replace. Tools automatically read the root `AGENTS.md` and start working; scripts auto-detect the memory location.
>
> **Not bound to Obsidian**: the memory vault is just a plain Markdown directory (`Memory/`). Any agent that can read/write files and any Markdown editor can use it. The author personally views it in Obsidian — Templater / Dataview are optional enhancements, not dependencies.

**Why**: every AI tool keeps its own "memory" — `~/.claude/`, `~/.codex/`, `.workbuddy/memory/`, various forced auto-memories… Tools don't share; switching tools means amnesia; memories hidden in tool-private formats are neither readable nor auditable. This project converges the **single source of memory** into one plain Markdown directory that every tool can read and write. Tool-side configs only keep a *pointer + short hook* — they are the doorplate of the memory vault, not the vault itself.

Over three weeks of daily use this system grew gate scripts, bounded retrieval commands, and a four-part rulebook. Contents:

| Directory | What it is |
|---|---|
| [docs/](docs/) | **Design rationale**: why it's built this way, the real incidents behind every gate (Chinese) |
| [docs/06-agent-first-p0验证.md](docs/06-agent-first-p0验证.md) | **P0 prototype**: Agent-first boot pack, bounded query, minimal startup context |
| [starter/](starter/) | **Copy-and-go skeleton**: directory layout + full rulebook + sample project |
| [scripts/](scripts/) | **Agent commands + gates**: boot pack, bounded query, todo auditor, encoding guard, instruction sync |

## Demo

The vault's own workflow, drawn as a **live panel**: fixed layout, packets flowing on the wires, gate scripts spinning, alarms lighting up in turn — every frame is a complete, readable diagram (the numbers are illustrative):

![AI Memory Vault live panel](docs/media/memory-vault-panel.mp4)

*Rendered with the `live-diagram` skill; the panel's own memory is managed in this system as a real example — see [`starter/Memory/Projects/live-diagram/`](starter/Memory/Projects/live-diagram/).*

## Core principles (seven)

1. **Near-zero configuration**. The whole system = Markdown files + stdlib-only scripts. No services, no dependencies, no config files; the entry point is your tool auto-reading the root `AGENTS.md`, and scripts find `Memory/` by walking up the tree — copying it in *is* the install.
2. **One memory location**. All cross-session information lives in the Markdown vault; writing to any tool-private memory spot is forbidden (`.workbuddy/memory/`, `~/.claude/`, auto-memory…). Tool-side configs only keep a pointer + the iron-rule hook.
3. **Structured layers**. Memory is not one pile of notes: `Preferences` / `Plans` / `Decisions` / `Lessons` / `Workflows` / `Projects/<name>/`, plus global `Todo.md`, the write-ledger `Inbox/`, and quarterly `Archive/`.
4. **Minimal context by default**. The agent does not browse the memory tree. `memory_boot.py` builds a bounded hot/project pack, and `memory_query.py` returns ranked snippets on demand, so session startup stays small and predictable.
5. **Closed = moved, not marked**. A finished or cancelled todo is appended to `Projects/<name>/working/completed/YYYY-QX.md` (with date, outcome, reason and source) and **deleted from Todo.md** — never a ✅ or a permanent strikethrough in place. The `todo_audit.py` gate blocks leftovers.
6. **Only gated steps stay drift-free**. "Remember to sync" has been proven to fail repeatedly. Every gate in this repo was born from a real incident — see [docs/04](docs/04-演化史-门禁背后的事故.md).
7. **Privacy boundaries enforced by guards**. The memory layer is `.gitignore`d out of public repos and a `pre-commit` hook **rejects any commit touching it** — don't rely on discipline, rely on guards.

## Layout

```text
your-vault/                   ← your notes repo / workspace root (a plain Markdown directory is enough)
├── AGENTS.md                 ← repo-root entry: the first thing any AI reads
├── Templates/                ← note templates (Memory-Note / Memory-Inbox-Note)
└── Memory/                   ← the memory vault itself (the single memory location)
    ├── AGENTS.md             ← iron rules + short hook (deployed into every tool's system prompt)
    ├── BOOT.md               ← only always-on hot layer (small, stable facts)
    ├── Rule.md               ← rulebook TOC: operation → section mapping
    ├── rule/                 ← four rule sections (write / wrap-up / sub-agents / vibe-coding)
    ├── Todo.md               ← global todos, grouped by project (no checkboxes)
    ├── Preferences/ Plans/ Decisions/ Lessons/ Workflows/
    ├── Projects/<name>/      ← _overview.md + _state.md + working/{journal,plan,completed}.md
    ├── Inbox/                ← write ledger: every AI write gets logged, then reviewed
    └── Archive/              ← quarterly archive
```

## One-sentence deployment

Send this paragraph **verbatim to any AI agent** (Claude Code, Cursor, Cline, web agents with file access…), and it will deploy the vault for you and read back the usage contract:

```text
Clone (or download and unzip) https://github.com/star-nebula/ai-memory-vault ,
copy everything under starter/ into the root of my memory-vault workspace — if I already
have a notes repo use its root, otherwise create an empty directory. Also copy the
scripts/ directory into that workspace (the gates are not inside starter/).
Run python scripts/memory_boot.py --cwd . --json and python scripts/memory_query.py "test" --json. Finally read the workspace-root AGENTS.md, and tell me back:
when you will load memory, how you will query it, and how you will write it.
```

## Manual deployment (without an agent)

```bash
# The only "install" step: copy the skeleton + gate scripts into your workspace root
cp -r starter/* scripts /path/to/your-vault/
```

`scripts/` must be copied too — the gates are not inside `starter/`.

That's it — no placeholders to replace, no dependencies to install. Two **optional** follow-ups:

```bash
python scripts/todo_audit.py --check    # todo archiving gate
python scripts/encoding_guard.py <path> # encoding + bare-control-character gate
```

**Hooking up AI tools**: see `starter/Memory/Workflows/AI工具自定义指令.md` — a full version (paste into "custom instructions" boxes) and a minimal version (drop into a project-root `AGENTS.md`), covering WorkBuddy / ZCode / Trae / Qoder / Claude Code / Codex / Cursor / Copilot / Cline and more. Both are relative-path by default and work as-pasted; only a user-level *global* instruction needs the vault path replaced once, then `scripts/sync_memory_instructions.py` distributes it to every tool in one command.

## Gate scripts

| Script | What it blocks |
|---|---|
| `memory_boot.py` | Unbounded session startup; silent section truncation; missing project context |
| `memory_query.py` | Whole-note expansion; project/scope leakage; archived/superseded results unless explicitly requested |
| `todo_audit.py` | Closed-but-not-moved leftovers; group names not matching project dirs; fake "already moved to Todo" claims; out-of-vocabulary frontmatter types; (report-only) Inbox audit backlog |
| `state_audit.py` | Missing, placeholder, stale, or oversized project `_state.md` cards (report-only by default) |
| `encoding_guard.py` | Non-UTF-8 / BOM leftovers; bare control characters left by AI escape-swallowing — the invisible killer that makes files binary to grep |
| `sync_memory_instructions.py` | Drift between each tool's instruction slot and the single source; bare control characters in the source; `<项目名>` placeholder pseudo-values |

Design trade-offs (why some checks are hard gates and others are report-only) and every incident post-mortem live in the Chinese docs: [01](docs/01-为什么需要统一记忆库.md) · [02](docs/02-目录结构与读取路由.md) · [03](docs/03-核心设计原则.md) · [04](docs/04-演化史-门禁背后的事故.md) · [05](docs/05-记忆库结构与规则详解.md).

## License

[MIT](LICENSE) — structure, rules and scripts are free to use. If it helps you, a Star or an Issue about your own adaptation is very welcome.
