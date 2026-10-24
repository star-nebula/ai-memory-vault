#!/usr/bin/env python3
"""Todo 归档体检 —— 校验 `Memory/Todo.md` 是否守住「完成 = 移走」。

背景（2026-09-21）：
    「待办 → `Memory/Todo.md`；完成 → `Projects/<项目名>/working/completed.md`」
    这条链路原本只写在会话收尾 checklist 里，**没有任何门禁**，于是静默积累
    「已标完成却未移走」的条目（实测 4 条，含一条 2000 字符的重复复盘）。
    对比：断链有 `link_audit.py`，唯独待办归档没有。
    本脚本把「归档动作」变成可校验项。

检查清单（**计数不在此维护**，以本文件的 `scan_*` 函数为准——写死「N 件事」就是第二份事实源，加一项就漂）：
    1. 完成信号残留 —— Todo 里带完成标记、但未移走的条目（违规）
    2. 分组名映射   —— `## 分组` 标题必须等于 `Projects/` 下的目录名（规则要求）
    3. completed.md —— 被 Todo 提到的项目是否已有 `working/completed.md`
    4. Agent 启动硬门禁 + 内容债 —— BOOT 源政策、实际 assembled 启动包为硬门禁；overview/state 源超限与 section 截断为报告项
    5. scope 词表   —— 跨层归属字段的非法取值与冗余出现（2026-09-29 增，报告项；
                     合法值 = `global` ∪ `Projects/` 目录名，由实盘推导、脚本内不写死词表）
    6. Todo 声明核对 —— journal/plan 里「已并入 Todo」这类话**是否真有其条**
                     （2026-09-30 增，并入 `--check` 拦；病灶：09-26 journal 声称已并入，
                     Todo 里从来没有那条，静默挂起三天）
    7. 暂存层体量   —— **判压面只收 journal**；completed 属终态层，只进观测面（报告项）。
    8. `type` 词表    —— frontmatter `type` 取值是否在规则正本第 5 条的括号词表内（2026-09-30 增，
                     并入 `--check` 拦；词表机读自规则正本、脚本内不写死；解析失败 = 退出码 1）
    9. 每日审核积压 —— `Inbox/` 根下「登记日期早于运行当天」却仍未被审掉的日记账份数（报告项）。
                     补的盲区：定时审核任务绑在 app 上，关机/周末记 `skipped` 且不补跑，
                     可能连续多天零落地而**八门全绿、没有任何一处知道**。
                     同一计数有两种成因，脚本不猜、由人分因：①任务没跑；②审过了但块里留着
                     「待本人决定」，按审核 SOP「任一块未过 → 整份不勾不移」被扣在根下。
                     判据正本 = `Workflows/记忆库自动审核与人工入口.md`「审核范围」段；**只报不拦**。

**为什么体量阈值写在脚本、不写进文档**：
    Agent-first 启动不再预读整棵记忆树与整份 Todo，而是由 `memory_boot.py`
    生成 `BOOT.md + 项目切片` 的有界包。本脚本只做存量扫描：BOOT 是否过大、overview
    是否需要瘦身、启动近似上限是否失控。数字会变，写进规则文档就变成第二份事实源；
    因而阈值在脚本常量，实测在报告，文档只指路。

阈值分档（`--check` 把 1/2/6/8/9 当门禁；启动成本、`scope` 与暂存层体量走报告，避免历史欠账或改名当天把每次收尾都判红）：
    · 单文件超过 LIMIT_* 记「内容债」；`--cost-check` 只拦 BOOT 源政策与实际启动包，`--content-check` 才拦内容债。
    · 暂存层**判压面只收 journal**：超 LIMIT_STAGING_CHARS（**字符数**口径）记「待压缩」，**只报告不拦**；
      completed 属终态层，只进「最重几份」观测面。
      压缩旧段是渐进蒸馏，存量不可能当天清零——当门禁就恒红。原「约 500 行」口径永不触发（见报告第八节）。
    · `scope` 违规（非法取值 / 冗余出现）记第六节；`--scope-check` 才作硬门禁退出码 1。
      「缺 scope」的跨层笔记只提示不拦——补字段是写入侧义务，靠审核兜底，不宜让旧笔记天天报红。
    · Todo 声明核对：带 `Todo → 「标题」` 形态却查无此条 = **假声明，进 `--check` 拦**（这类零存量、可当场清零）；
      旧写法没有指针形态、机器无法核对 → 只提示不拦（同「缺 scope」待遇，季度看条数下降）。
    · `type` 词表：词表外取值进 `--check` 拦（装机当日存量为零，见报告第九节）；「有 frontmatter 却缺 `type`」只报不拦。
      规则正本第 5 条的括号词表**解析失败 → 退出码 1**：失明而不吭声的门比没有门更危险。
    · 季度维护只看**超标项数是否下降**，不逐条清零（同 `dup_check` 基线口径）。

不算违规的两类（脚本会单独计数、不拦门禁）：
    · 引用块（`>` 开头的说明行）
    · 「不再继续」的删除线留档（整行含 `~~`）—— 规则明确要求保留在原分组

用法：
    python todo_audit.py                 # 全量报告 → _agent_scripts/_out/todo_audit.txt
    python todo_audit.py --check         # 门禁模式：完成信号残留 / 分组名不映射 / Todo 假声明 即退出码 1
    python todo_audit.py --cost-check    # 硬门禁：BOOT 源政策 / 实际 assembled 启动包超标 → 退出码 1
    python todo_audit.py --content-check # 严格内容债门禁：overview/state/section 截断/缺 state → 退出码 1
    python todo_audit.py -o <文件>        # 指定输出
    python todo_audit.py --json           # 机器可读
    python todo_audit.py --todo <路径>    # 覆盖 Todo 路径

退出码：0 = 干净；1 = 有违规（可当门禁）。

坑：本机 PowerShell 会吞 stdout（exit 0 但无输出）——**实操一律默认写文件**，
    再 Read 读回；`--quiet` 只是额外压掉 stdout。

运行环境：仅标准库（Python 3.9+）。记忆库定位：环境变量 `AI_MEMORY_DIR`，
或从当前目录向上探测 `<根>/Memory`。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

from memory_common import DEFAULT_BUDGET as BOOT_DEFAULT_BUDGET, SECTION_LIMITS as BOOT_SECTION_LIMITS, normalize_group_title
from memory_boot import build_boot_pack

# Windows 控制台默认 GBK，本脚本输出含中文与符号，不加这行会 UnicodeEncodeError 中断。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def _find_memory_dir() -> Path:
    """定位记忆库根：环境变量 AI_MEMORY_DIR 优先；否则从 cwd / 脚本位置向上探测
    名为 Memory 且含 BOOT.md / Todo.md / rule/ 之一的目录（适配任意 vault 布局）。"""
    env = os.environ.get("AI_MEMORY_DIR")
    if env:
        return Path(env)
    for start in (Path.cwd(), Path(__file__).resolve()):
        for p in [start, *start.parents]:
            cand = p / "Memory"
            nested = p / "vault" / "Memory"
            if nested.is_dir() and any(
                (nested / marker).exists() for marker in ("BOOT.md", "Todo.md", "rule")
            ):
                return nested
            if cand.is_dir() and any(
                (cand / marker).exists() for marker in ("BOOT.md", "Todo.md", "rule")
            ):
                return cand
    return Path.cwd() / "Memory"

SCRIPT_DIR = Path(__file__).resolve().parent
MEMORY_DIR = _find_memory_dir()
TODO_PATH = MEMORY_DIR / "Todo.md"
BOOT_PATH = MEMORY_DIR / "BOOT.md"
PROJECTS_DIR = MEMORY_DIR / "Projects"
DEFAULT_OUT = SCRIPT_DIR / "_out" / "todo_audit.txt"
INBOX_DIR = MEMORY_DIR / "Inbox"          # 每日审核的现场（只读扫描，本脚本不写它）
INBOX_DAY_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")

# —— Agent 启动成本阈值（策略常量；改这里，不改文档）——
LIMIT_BOOT = BOOT_SECTION_LIMITS["boot"]
LIMIT_OVERVIEW = BOOT_SECTION_LIMITS["overview"]
LIMIT_STATE = BOOT_SECTION_LIMITS["state"]
LIMIT_BOOT_APPROX = BOOT_DEFAULT_BUDGET
# 暂存层体量阈值（**字符数**）：超过即该把旧段压成「阶段小结」（只留结论 + wikilink）。
# 原写死在 `rule/写入与禁止.md` 第 3 条与 `Todo.md` 正文里（同一事实两份文档各存一处），
# 2026-09-30 用户裁定「数字不进文档」后移入此处——文档只留指针，实测只进本报告「八、」段。
# **同一天把单位从「行数」改成「字符数」**（用户裁定）：原口径「约 500 行」在本库永不触发——
# journal 习惯把一整段实测叙述写成一行，42 份暂存层文件按行数零超标，而最重的一份已是几万字符。
# 取 40000 的理由不是拍脑袋：它恰好只圈出 09-26 全库体检**独立点名**「有蒸馏压力」的那批文件，
# 即阈值与人工判断对齐；季度看「待压缩份数」与最重份字符数是否下降。
LIMIT_STAGING_CHARS = 40000
STAGING_REPORT_TOP = 5      # 「按字符数最重的 N 份」呈报条数（纯展示参数，非阈值）


def char_len(path: Path) -> int:
    return len(read_text(path)) if path.is_file() else 0


def scan_opening_cost() -> dict:
    overviews = []
    states = []
    if PROJECTS_DIR.is_dir():
        for ov in sorted(PROJECTS_DIR.glob("*/_overview.md")):
            overviews.append({"project": ov.parent.name, "chars": char_len(ov)})
        for st in sorted(PROJECTS_DIR.glob("*/_state.md")):
            states.append({"project": st.parent.name, "chars": char_len(st)})
    overs = sorted([x for x in overviews if x["chars"] > LIMIT_OVERVIEW], key=lambda x: -x["chars"])
    state_overs = sorted([x for x in states if x["chars"] > LIMIT_STATE], key=lambda x: -x["chars"])
    boot_chars = char_len(BOOT_PATH)
    worst_overview = max((x["chars"] for x in overviews), default=0)
    worst_state = max((x["chars"] for x in states), default=0)
    return {
        "boot_chars": boot_chars,
        "boot_over": boot_chars > LIMIT_BOOT,
        "worst_overview": worst_overview,
        "worst_state": worst_state,
        "boot_approx_chars": boot_chars + worst_overview + worst_state,
        "overview_offenders": overs,
        "state_offenders": state_overs,
        "overview_total": len(overviews),
        "state_total": len(states),
    }

def scan_boot_health(active_projects) -> dict:
    rows = []
    if PROJECTS_DIR.is_dir():
        for project in sorted(p for p in PROJECTS_DIR.iterdir() if p.is_dir()):
            if not (project / "_overview.md").is_file():
                continue
            try:
                pack = build_boot_pack(MEMORY_DIR, project=project.name, budget=BOOT_DEFAULT_BUDGET)
            except Exception as exc:
                rows.append({"project": project.name, "error": str(exc)})
                continue
            rows.append({
                "project": project.name,
                "active": project.name in active_projects,
                "chars": pack["chars"],
                "assembled_chars": pack["assembled_chars"],
                "source_chars": pack["source_chars"],
                "section_truncated": pack["section_truncated"],
                "budget_truncated": pack["budget_truncated"],
                "files": pack["files"],
            })
    hard = [r for r in rows if r.get("error") or r.get("budget_truncated") or r.get("assembled_chars", 0) > BOOT_DEFAULT_BUDGET]
    section_debt = [r for r in rows if r.get("section_truncated")]
    return {
        "budget": BOOT_DEFAULT_BUDGET,
        "scanned": len(rows),
        "max_chars": max((r.get("chars", 0) for r in rows), default=0),
        "max_assembled_chars": max((r.get("assembled_chars", 0) for r in rows), default=0),
        "hard": hard,
        "section_debt": section_debt,
        "rows": rows,
    }


# 强完成信号：命中即视为「已标完成」→ 必须已移走
STRONG_SIGNALS = ("✅", "✔", "已执行完毕", "已完成：", "已完成:", "已结清", "已归档")


def scan_staging_volume() -> dict:
    """暂存层体量 —— 两个面分开，别把它们混成一件。

    **判压面（`over`）= 只 `journal.md`**：超过 `LIMIT_STAGING_CHARS` 才叫「该把旧段压成阶段小结」。
    **观测面（`heaviest`）= journal 与 completed 混排最重几份**：`completed.md` 属**终态层**，
    对它只报体量、不判压——它没有按日小节（无「旧段」可切单元），同时又是「七、」假声明
    核对的证据面（压掉可能当场把门禁判红）。**覆盖面可以收窄，观测不能归零。**

    只报告不拦：蒸馏是渐进动作，存量不可能当天清零（恒红的门禁等于没有门禁）。
    口径正本 = `rule/写入与禁止.md` 第 3 条；阈值 = 上面的 `LIMIT_STAGING_CHARS`（策略在脚本、事实在报告）。
    """
    files = []
    if PROJECTS_DIR.is_dir():
        files = sorted(list(PROJECTS_DIR.glob("*/working/journal.md"))
                       + list(PROJECTS_DIR.glob("*/working/completed.md")))
    rows = []
    for f in files:
        text = read_text(f)
        rows.append({"project": f.parent.parent.name, "file": f.name,
                     "kind": "journal" if f.name == "journal.md" else "completed",
                     "lines": len(text.splitlines()), "chars": len(text)})
    over = sorted([x for x in rows if x["kind"] == "journal" and x["chars"] > LIMIT_STAGING_CHARS],
                  key=lambda x: -x["chars"])
    heaviest = sorted(rows, key=lambda x: -x["chars"])[:STAGING_REPORT_TOP]
    return {"scanned": len(rows),
            "scanned_journal": sum(1 for x in rows if x["kind"] == "journal"),
            "over": over, "heaviest": heaviest}


def scan_audit_backlog(inbox_dir: Path = INBOX_DIR, run_date=None) -> dict:
    """每日 Inbox 审核积压 —— 让「定时审核停跑」在机器上可见（**只报不拦**）。

    审核对象 = `Inbox/` 根下文件名形如 `YYYY-MM-DD.md` 且日期**早于运行当天**的登记文件；
    `Inbox/Archive/`（留档）与子目录不审；不含合法日期名的文件跳过。
    只扫根目录一层、只读不写 —— 本脚本不代替审核任务移动或勾选任何文件。

    计数不为零有两种成因，脚本不猜、由人分因：
    ① 审核任务没跑；② 审过了但块里留着「待本人决定」，按审核 SOP「任一块未过 → 整份不勾不移」
    被整份扣在根下。报告术语因此叫**待结积压**，不叫「停跑份数」。

    为什么只报不拦：成因 ① 是外因（设备关机 / 节假日 / app 未运行且调度器不补跑），
    成因 ② 要等人的裁定；做成拦停 = 每次收尾恒红，而恒红的门禁等于没有门禁。
    """
    run = run_date or date.today()
    res = {"dir": str(inbox_dir), "exists": inbox_dir.is_dir(), "run_date": run.isoformat(),
           "root_md": 0, "dated": 0, "skipped": [], "overdue": []}
    if not res["exists"]:
        return res
    for p in sorted(inbox_dir.glob("*.md")):
        res["root_md"] += 1
        m = INBOX_DAY_RE.match(p.name)
        if not m:
            res["skipped"].append(p.name)
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            res["skipped"].append(p.name)
            continue
        res["dated"] += 1
        if d < run:
            res["overdue"].append({"name": p.name, "date": m.group(1), "days": (run - d).days})
    res["overdue"].sort(key=lambda x: x["date"])
    return res

# —— `scope` 词表（跨层笔记归属字段；口径见 rule/写入与禁止.md 第 5 条）——
# 合法取值 = {"global"} ∪ Projects/ 下的目录名，**实盘推导、不写死词表**（写死就是第二份事实源）。
SCOPE_LAYERS = ("Preferences", "Plans", "Decisions", "Lessons", "Workflows")
SCOPE_RE = re.compile(r"^scope:\s*(\S.*?)\s*$")


def frontmatter_scope(text: str):
    """仅取 frontmatter 块（首行 `---` 到闭合 `---`）内的 scope 值；无块或无该字段返回 None。

    只认 frontmatter 是有意的：历史笔记正文里的模板示例（`scope: <层名>`）不是数据，
    按正文匹配会把教程/论证内容当违规。
    """
    if not text.startswith("---"):
        return None
    lines = text.replace("\r\n", "\n").split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            for j in range(1, i):
                m = SCOPE_RE.match(lines[j])
                if m:
                    return m.group(1).strip().strip("\"'")
            return None
    return None


def has_frontmatter(text: str) -> bool:
    """是否有 frontmatter 块。整块没有 = 结构性豁免（如部署真源：加块会污染工具位正文）。"""
    if not text.startswith("---"):
        return False
    lines = text.replace("\r\n", "\n").split("\n")
    return any(lines[i].strip() in ("---", "...") for i in range(1, len(lines)))


def scan_scope_vocab() -> dict:
    names = {p.name for p in PROJECTS_DIR.iterdir() if p.is_dir()} if PROJECTS_DIR.is_dir() else set()
    vocab = names | {"global"}
    bad, missing, redundant = [], [], []
    eligible = 0  # 跨层里「有 frontmatter、因此本该带 scope」的篇数（报告口径，不参与拦）
    for layer in SCOPE_LAYERS:
        d = MEMORY_DIR / layer
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            t = read_text(f)
            v = frontmatter_scope(t)
            if v is None:
                if has_frontmatter(t):
                    eligible += 1
                    missing.append(f"{layer}/{f.name}")
            elif v not in vocab:
                eligible += 1
                bad.append({"file": f"{layer}/{f.name}", "value": v})
            else:
                eligible += 1
    # 路径已经表达归属，再填 scope 就是第二份事实源。
    for pat in ("*/*.md", "*/*/*.md"):
        for f in sorted(PROJECTS_DIR.glob(pat)) if PROJECTS_DIR.is_dir() else []:
            if frontmatter_scope(read_text(f)) is None:
                continue
            redundant.append(str(f.relative_to(MEMORY_DIR)).replace("\\", "/"))
    return {
        "vocab_dirs": len(names),
        "bad": bad,
        "missing": missing,
        "redundant": redundant,
        "eligible": eligible,
    }

# —— frontmatter `type` 词表（2026-09-30 增；口径正本 = `rule/写入与禁止.md` 第 5 条）——
# 词表**机读自规则正本、脚本内不写死**：写死等于第二份事实源，加一个取值要改两处（同 `scope` 的「实盘推导」设计）。
# **解析失败必须退出码 1**：静默通过 = 门开着而没人知道，比没有门更糟。
# 拦/报划界：词表外取值 = 拦（存量可当场清零）；「有 frontmatter 却缺 `type`」只报不拦——与「缺 scope」同待遇，
# 补字段是写入侧义务，让旧笔记天天报红等于把门禁调成恒红。
TYPE_RULE_PATH = MEMORY_DIR / "rule" / "写入与禁止.md"
TYPE_LIST_RE = re.compile(r"`type`\(([^)]*)\)")
TYPE_FM_RE = re.compile(r"^type:\s*(\S.*?)\s*$")
# 豁免面与 `scope` 那条同源：登记簿 / 规则文本 / README / 暂存层台账 / 整块无 frontmatter 的结构性豁免
TYPE_EXEMPT_TOP = ("Inbox", "rule")
TYPE_EXEMPT_NAMES = ("README.md",)
TYPE_EXEMPT_DIRS = ("working",)


def parse_type_vocab(rule_path: Path = TYPE_RULE_PATH):
    """从规则正本第 5 条取 `type` 合法取值；任一步失败返回 None（调用方须退出码 1，不得当作「无违规」）。"""
    if not rule_path.is_file():
        return None
    for line in read_text(rule_path).replace("\r\n", "\n").split("\n"):
        if not line.startswith("5."):
            continue
        m = TYPE_LIST_RE.search(line)
        if not m:
            return None
        vals = {x.strip().strip("`") for x in m.group(1).split("/") if x.strip()}
        return vals if len(vals) >= 3 else None
    return None


def frontmatter_type(text: str):
    """仅取 frontmatter 块内的 `type:`；无块或无该字段返回 None（口径同 `frontmatter_scope`：正文里的示例不算数据）。"""
    if not text.startswith("---"):
        return None
    lines = text.replace("\r\n", "\n").split("\n")
    for i in range(1, len(lines)):
        if lines[i].strip() in ("---", "..."):
            for j in range(1, i):
                m = TYPE_FM_RE.match(lines[j])
                if m:
                    return m.group(1).strip().strip('"\'')
            return None
    return None


def scan_type_vocab(memory_dir: Path = MEMORY_DIR, rule_path: Path = TYPE_RULE_PATH) -> dict:
    """扫 `vault/Memory` 全部 md 的 frontmatter `type` 取值；只查不改（改字段还是扩词表是人的判断）。"""
    vocab = parse_type_vocab(rule_path)
    if vocab is None:
        return {"vocab": None, "bad": [], "missing": [], "scanned": 0, "exempt": 0}
    bad, missing = [], []
    scanned = exempt = 0
    for f in sorted(memory_dir.rglob("*.md")):
        rel = f.relative_to(memory_dir)
        if rel.parts[0] in TYPE_EXEMPT_TOP or f.name in TYPE_EXEMPT_NAMES:
            exempt += 1
            continue
        if any(p in TYPE_EXEMPT_DIRS for p in rel.parts[:-1]):
            exempt += 1
            continue
        t = read_text(f)
        if not has_frontmatter(t):
            exempt += 1          # 整块无 frontmatter = 结构性豁免（部署真源那一类）
            continue
        scanned += 1
        v = frontmatter_type(t)
        key = str(rel).replace("\\", "/")
        if v is None:
            missing.append(key)
        elif v not in vocab:
            bad.append({"file": key, "value": v})
    return {"vocab": sorted(vocab), "bad": bad, "missing": missing,
            "scanned": scanned, "exempt": exempt}


# 顶部说明块 / 引用块前缀
QUOTE_PREFIX = ">"

TRAILING_PAREN = re.compile(r"[（(][^）)]*[）)]\s*$")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def norm_group(title: str) -> str:
    """Compatibility wrapper for the shared Todo-heading normalizer."""
    return normalize_group_title(title)


def project_dirs() -> dict[str, Path]:
    if not PROJECTS_DIR.is_dir():
        return {}
    return {p.name: p for p in PROJECTS_DIR.iterdir() if p.is_dir()}


def has_completed(dirname_path: Path) -> bool:
    return (dirname_path / "working" / "completed.md").is_file()


# —— journal/plan 里「已并入 Todo」这类声明的核对（2026-09-30 增）——
# 病灶：journal 写下「待修项已并入 Todo ## 某组」，实测 Todo 里从来没有那条 → 静默挂起三天。
# 合规形态：`Todo → 「条目标题」`（引号里必须是 Todo 行里逐字出现的一段标题文字）。
# 引号标题的核对面 = Todo.md ∪ **所有** working/completed.md：「完成 = 移走」会让条目离开 Todo，
# 只查 Todo 会在条目归档当天把声明判红 —— 恒红的门禁等于没有门禁。
# 旧写法（无指针形态）无法机器核对 → **仅提示不拦**（历史欠账，季度看条数下降，口径同 `scope` 缺字段）。
TODO_CLAIM_RE = re.compile(r"(已并入|已写入|已加入|已登记到|已挂进|已挂|已转|已记入)\s*[`「]?\s*Todo")
TODO_POINTER_RE = re.compile(r"Todo[^「]{0,24}?→\s*「([^」]{4,60})」")
CLAIM_SCAN_GLOBS = ("*/working/journal.md", "*/working/plan.md")


def scan_todo_claims(todo_path: Path) -> dict:
    """核对「已并入 Todo」声明：带指针形态的必须在 Todo 或任一 completed.md 命中；无指针形态的只提示。"""
    corpus = []
    if todo_path.is_file():
        corpus.append(read_text(todo_path))
    for cm in sorted(PROJECTS_DIR.glob("*/working/completed.md")) if PROJECTS_DIR.is_dir() else []:
        corpus.append(read_text(cm))
    broken, unverifiable = [], []
    for glob in CLAIM_SCAN_GLOBS:
        for f in sorted(PROJECTS_DIR.glob(glob)) if PROJECTS_DIR.is_dir() else []:
            project = f.relative_to(PROJECTS_DIR).parts[0]
            for n, line in enumerate(read_text(f).splitlines(), 1):
                if line.strip().startswith(QUOTE_PREFIX) or not TODO_CLAIM_RE.search(line):
                    continue
                titles = TODO_POINTER_RE.findall(line)
                if not titles:
                    unverifiable.append({"file": str(f.relative_to(MEMORY_DIR)), "line": n,
                                         "project": project, "text": line.strip()[:70]})
                    continue
                for t in titles:
                    if not any(t in c for c in corpus):
                        broken.append({"file": str(f.relative_to(MEMORY_DIR)), "line": n,
                                       "project": project, "title": t})
    return {"broken": broken, "unverifiable": unverifiable}


def scan_todo(todo_path: Path) -> dict:
    todo_text = read_text(todo_path)
    lines = todo_text.splitlines(keepends=True)
    dirs = project_dirs()
    dirs_lower = {k.lower(): k for k in dirs}

    signals: list[dict] = []
    retired: list[dict] = []
    groups: list[dict] = []
    sub_groups = 0
    cur_group = "(文件头)"
    char_total = len(todo_text)
    char_by_group: dict[str, int] = {}
    item_count = 0

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        char_by_group[cur_group] = char_by_group.get(cur_group, 0) + len(raw)
        stripped = line.strip()
        if not stripped:
            continue

        if stripped.startswith(QUOTE_PREFIX):
            continue

        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            title = h2.group(1).strip()
            cur_group = title
            char_by_group.setdefault(cur_group, 0)
            cand = norm_group(title)
            hit = dirs_lower.get(cand.lower())
            entry = {
                "line": i,
                "title": title,
                "candidate": cand,
                "matched_dir": dirs[hit].name if hit else None,
                "completed_md": has_completed(dirs[hit]) if hit else None,
            }
            groups.append(entry)
            continue

        if re.match(r"^###\s+", line):
            sub_groups += 1
            continue

        if re.match(r"^[-*]\s", stripped):
            item_count += 1

        typed_item = bool(re.match(r"^[-*]\s", stripped))
        is_retired = typed_item and "~~" in line
        hit_signal = next((s for s in STRONG_SIGNALS if s in line), None)

        if is_retired:
            retired.append({
                "line": i,
                "group": cur_group,
                "signal": hit_signal,
                "text": stripped[:120],
            })
        elif hit_signal:
            signals.append({
                "line": i,
                "signal": hit_signal,
                "group": cur_group,
                "indent": len(line) - len(line.lstrip()),
                "text": stripped[:120],
            })

    # 分组 → completed.md 缺失汇总
    missing_completed = [
        {"group": g["title"], "dir": g["matched_dir"]}
        for g in groups
        if g["matched_dir"] and g["completed_md"] is False
    ]
    unmapped = [g for g in groups if g["matched_dir"] is None]
    active_projects = {g["matched_dir"] for g in groups if g["matched_dir"]}
    boot_health = scan_boot_health(active_projects)
    missing_state = [
        {"group": g["title"], "dir": g["matched_dir"]}
        for g in groups
        if g["matched_dir"] and not (PROJECTS_DIR / g["matched_dir"] / "_state.md").is_file()
    ]

    return {
        "todo": str(todo_path),
        "char_total": char_total,
        "char_by_group": char_by_group,
        "item_count": item_count,
        "sub_group_count": sub_groups,
        "groups": groups,
        "signals": signals,
        "retired": retired,
        "unmapped_groups": unmapped,
        "missing_completed": missing_completed,
        "missing_state": missing_state,
        "boot_health": boot_health,
        "cost": scan_opening_cost(),
        "scope": scan_scope_vocab(),
    }


def render(r: dict) -> str:
    out: list[str] = []
    out.append("# Todo 归档体检报告")
    out.append("")
    out.append(f"对象：`{r['todo']}`")
    out.append(f"体积：{r['char_total']} 字符 / 明确条目 {r['item_count']} 条 / `##` 分组 {len(r['groups'])} 个 / `###` 子分组 {r['sub_group_count']} 个")
    out.append("")

    out.append("## 一、完成信号残留（违规 —— 应移走却还在 Todo）")
    if r["signals"]:
        out.append("")
        out.append(f"共 {len(r['signals'])} 条：")
        for s in r["signals"]:
            kind = "子项（父项可能仍未完成，人工判断）" if s["indent"] > 0 else "顶层"
            out.append(f"- L{s['line']} [{s['signal']}] 分组「{s['group']}」· {kind}")
            out.append(f"  {s['text']}")
    else:
        out.append("")
        out.append("无 —— 干净。")
    out.append("")

    out.append("## 二、分组名 ↔ 项目目录映射（规则：分组标题取 `Projects/` 目录名）")
    out.append("")
    out.append("| L | 分组标题 | 解析为 | 目录命中 | completed.md |")
    out.append("|---|---|---|---|---|")
    for g in r["groups"]:
        cm = g["completed_md"]
        cm_txt = "有" if cm else ("缺" if cm is False else "—")
        out.append(f"| {g['line']} | {g['title']} | {g['candidate'] if g['candidate'] != g['title'] else ''} | {g['matched_dir'] or '**无**'} | {cm_txt} |")
    out.append("")
    if r["unmapped_groups"]:
        out.append(f"**无对应项目目录的分组 {len(r['unmapped_groups'])} 个**（违规 —— 归档无处落地，应改名或结清解散）：")
        for g in r["unmapped_groups"]:
            out.append(f"- L{g['line']}「{g['title']}」")
    else:
        out.append("分组名全部命中项目目录。")
    out.append("")
    if r["missing_completed"]:
        out.append(f"**缺 `working/completed.md` 的项目 {len(r['missing_completed'])} 个**（归档前先建文件）：")
        for m in r["missing_completed"]:
            out.append(f"- `Projects/{m['dir']}/working/completed.md`（分组「{m['group']}」）")
    else:
        out.append("被 Todo 引用的项目均有 `completed.md`。")
    if r.get("missing_state"):
        out.append(f"**缺项目 `_state.md` 的活跃项目 {len(r['missing_state'])} 个**（报告项：项目状态无法进入启动包）：")
        for m in r["missing_state"]:
            out.append(f"- `Projects/{m['dir']}/_state.md`（分组「{m['group']}」）")
    else:
        out.append("被 Todo 引用的项目均有 `_state.md`。")
    out.append("")

    out.append("## 三、合法留档（不拦门禁）")
    out.append("")
    out.append(f"- 引用块说明行：跳过不计")
    out.append(f"- 「不再继续」删除线留档：{len(r['retired'])} 条")
    for s in r["retired"]:
        out.append(f"  - L{s['line']} 分组「{s['group']}」")
    out.append("")

    out.append("## 四、各组体积（找臃肿分组）")
    out.append("")
    ranked = sorted(r["char_by_group"].items(), key=lambda kv: -kv[1])
    for name, cnt in ranked:
        if cnt <= 0:
            continue
        share = (cnt / r["char_total"] * 100) if r["char_total"] else 0
        out.append(f"- {name:<28} {cnt:>6} 字符  {share:5.1f}%")
    out.append("")

    c = r.get("cost") or {}
    bh = r.get("boot_health") or {}
    out.append("## 五、Agent 启动硬门禁 + 内容债报告")
    out.append("")
    if not c:
        out.append("（未采集——`--todo` 指向库外路径时跳过）")
    else:
        out.append(f"- `Memory/BOOT.md`：{c['boot_chars']} 字符（热层源政策限 {LIMIT_BOOT}）{'**超标**' if c['boot_over'] else 'ok'}")
        out.append(f"- `Memory/Todo.md`：{r['char_total']} 字符（源文件；启动只取当前项目切片，不设源文件硬限）")
        out.append(f"- `Projects/*/_overview.md`：共 {c['overview_total']} 份，最大 {c['worst_overview']} 字符（源政策限 {LIMIT_OVERVIEW}，报告项）")
        if c["overview_offenders"]:
            out.append(f"  **内容债 {len(c['overview_offenders'])} 份**（细节移 `working/journal.md`/`plan.md`，不阻断本次启动硬门禁）：")
            for o in c["overview_offenders"]:
                out.append(f"  - `{o['project']}` {o['chars']} 字符")
        else:
            out.append("  无源体量超标。")
        out.append(f"- `Projects/*/_state.md`：共 {c['state_total']} 份，最大 {c['worst_state']} 字符（源政策限 {LIMIT_STATE}，报告项）")
        if c["state_offenders"]:
            for o in c["state_offenders"]:
                out.append(f"  - `{o['project']}` {o['chars']} 字符")
        else:
            out.append("  无源体量超标。")
        if bh:
            out.append(f"- 实际启动包硬门禁：扫描 {bh['scanned']} 个项目，最大 text {bh['max_chars']} / assembled {bh['max_assembled_chars']} 字符（预算 {bh['budget']}）")
            if bh["hard"]:
                out.append(f"  **超预算 {len(bh['hard'])} 个项目**：")
                for row in bh["hard"]:
                    out.append(f"  - `{row['project']}` assembled={row.get('assembled_chars', '?')} budget_truncated={row.get('budget_truncated', '?')}")
            else:
                out.append("  通过：没有项目触发最终预算截断。")
            active_debt = len([row for row in bh["section_debt"] if row.get("active")])
            total_debt = len(bh["section_debt"])
            out.append(f"- 内容债报告：overview 源超限 {len(c['overview_offenders'])} / state 源超限 {len(c['state_offenders'])} / section 截断 {total_debt}（活跃 {active_debt}）/ 缺 state {len(r.get('missing_state') or [])}")
            out.append("  > 内容债不阻断 `--cost-check`；需要严格清零时用 `--content-check`。")
        out.append(f"- 近似诊断（非门禁）：BOOT + 最大 overview + 最大 state = {c['boot_approx_chars']} 字符")
        out.append("")
    out.append("")

    s = r.get("scope") or {}
    out.append("## 六、`scope` 词表（跨层归属字段；合法值 = `global` ∪ `Projects/` 目录名，实盘推导）")
    out.append("")
    if not s:
        out.append("（未采集）")
    else:
        out.append(f"- 词表来源：`Projects/` 下现有 {s['vocab_dirs']} 个目录名 + `global`。改名当天会出现「非法取值」，属预期，改引用即可。")
        if s["bad"]:
            out.append(f"  **非法取值 {len(s['bad'])} 处**（按 scope 反查会落到不存在的目录）：")
            for b in s["bad"]:
                out.append(f"  - `{b['file']}` → `{b['value']}`")
        else:
            out.append("  非法取值：无。")
        if s["redundant"]:
            out.append(f"  **冗余出现 {len(s['redundant'])} 处**（`Projects/` 层内路径即归属，不该再带该字段）：")
            for x in s["redundant"]:
                out.append(f"  - `{x}`")
        else:
            out.append("  冗余出现：无。")
        if s["missing"]:
            out.append(f"- 跨层笔记缺 `scope`（**仅提示不拦**：这五层平铺共享，无字段则无法按项目反查）{len(s['missing'])} 篇：")
            for x in s["missing"]:
                out.append(f"  - `{x}`")
        else:
            out.append(f"- 跨层带 frontmatter 的 {s['eligible']} 篇**全部**有 `scope` 且取值合法。")
        out.append("")
        out.append("> 口径正本见 `rule/写入与禁止.md` 第 5 条；本段是实测来源，文档里不写条数。")
    out.append("")

    cl = r.get("claims") or {}
    out.append("## 七、journal/plan 里「已并入 Todo」声明的核对")
    out.append("")
    if not cl:
        out.append("（未采集）")
    else:
        if cl["broken"]:
            out.append(f"  **假声明 {len(cl['broken'])} 处（拦）**——声明的标题在 Todo 与任何 completed.md 都查不到：")
            for b in cl["broken"]:
                out.append(f"  - `{b['file']}:{b['line']}`（{b['project']}）声明「{b['title']}」")
        else:
            out.append("  带指针形态的声明全部命中，无假声明。")
        if cl["unverifiable"]:
            out.append(f"- 旧写法（无指针形态、机器无法核对）**仅提示不拦** {len(cl['unverifiable'])} 条：")
            for u in cl["unverifiable"]:
                out.append(f"  - `{u['file']}:{u['line']}` {u['text']}")
        else:
            out.append("- 无「无法核对」的旧声明。")
        out.append("")
        out.append("> 合规形态：`… Todo → 「条目在 Todo 里的标题片段」`。"
                   "核对面 = `Todo.md` ∪ 所有 `working/completed.md`——「完成 = 移走」会让条目离开 Todo，"
                   "只查 Todo 就会在归档当天把声明判成红（恒红的门禁等于没有门禁）。")
    out.append("")
    st = r.get("staging") or {}
    out.append("## 八、暂存层体量（判压面 = journal；completed 只观测）")
    out.append("")
    if not st:
        out.append("（未采集）")
    else:
        out.append(f"- 扫描 `Projects/*/working/` 下 journal 与 completed 共 {st['scanned']} 份"
                   f"（其中 journal {st.get('scanned_journal', 0)} 份），"
                   f"阈值口径 = **字符数** {LIMIT_STAGING_CHARS} 字符/份（**阈值是本文件顶部常量，本段是实测**）。")
        if st["over"]:
            out.append(f"  **journal 超阈值 {len(st['over'])} 份**（旧段压成阶段小结：只留结论 + wikilink 指向已转正笔记）：")
            for x in st["over"]:
                out.append(f"  - `Projects/{x['project']}/working/{x['file']}` {x['chars']} 字符 / {x['lines']} 行")
        else:
            out.append("  journal 按字符数口径**无超标**文件。")
        out.append(f"- 同批按**字符数**最重的 {len(st['heaviest'])} 份（读取成本实际由它决定；completed 只在此观测）：")
        for x in st["heaviest"]:
            flag = "  ← journal 超阈值" if x.get("kind") == "journal" and x["chars"] > LIMIT_STAGING_CHARS else ""
            out.append(f"  - `Projects/{x['project']}/working/{x['file']}` {x['chars']} 字符 / {x['lines']} 行{flag}")
        out.append("")
        out.append("> **判压面只收 journal**：`working/completed.md` 属终态层，没有按日小节、无「旧段」可切；"
                   "同时它是「七、」假声明核对的证据面，压掉可能当场把门禁判红。只报体量、不判压。")
        out.append("> **单位为什么是字符不是行**：journal 常把一整段实测叙述写成一行，单行动辄上千字符，"
                   "行数口径可能永不触发；行数在本段只作阅读参考列。")
        out.append("> **只报告不拦**：蒸馏是渐进动作，把存量债当门禁会让每次收尾恒红。"
                   "口径正本见 `rule/写入与禁止.md` 第 3 条；该行只指路，不抄阈值与份数。")
    tv = r.get("type_vocab") or {}
    out.append("")
    out.append("## 九、frontmatter `type` 词表（取值清单机读自规则正本第 5 条，脚本内不写死）")
    if not tv:
        out.append("（本次未扫描）")
    else:
        out.append(f"- 词表（解析自 `rule/写入与禁止.md` 第 5 条）：{', '.join(tv.get('vocab') or [])}")
        out.append(f"- 参与核对 {tv.get('scanned', 0)} 篇 / 豁免 {tv.get('exempt', 0)} 份"
                   "（`Inbox/` 登记簿、`rule/` 规则文本、README、各 `working/` 台账、整块无 frontmatter 的结构性豁免）")
        for b in (tv.get("bad") or [])[:20]:
            out.append(f"  [!] 词表外取值：{b['file']} -> {b['value']}（改字段还是扩词表，由人裁定）")
        for x in (tv.get("missing") or [])[:20]:
            out.append(f"  [·] 缺 `type`：{x}")
        if not (tv.get("bad") or []) and not (tv.get("missing") or []):
            out.append("  词表外取值 0 / 缺 type 0")
    out.append("> **拦/报划界**：词表外取值进 `--check` 拦；缺 `type` 只报（同「缺 scope」）。**只报告不自动改**。")
    out.append("> 词表只有一处正本：本脚本不复制取值清单，第 5 条改了这里跟着变；解析不出来就退出码 1，不静默通过。")
    out.append("")
    ab = r.get("audit_backlog") or {}
    out.append("## 十、每日 Inbox 审核积压（**只报不拦**：定时审核任务「停跑」的机器可见面）")
    if not ab:
        out.append("（本次未采集）")
    elif not ab.get("exists"):
        out.append(f"  [!] 目录不存在：`{ab.get('dir')}` —— 路径变了就同步改本文件顶部 `INBOX_DIR`，"
                   "静默跳过等于这项检查不存在。")
    else:
        od = ab.get("overdue") or []
        out.append(f"- 运行日 = `{ab['run_date']}`；`Inbox/` 根下 `.md` {ab['root_md']} 份"
                   f"（带合法日期名 {ab['dated']} 份 / 无日期名跳过 {len(ab.get('skipped') or [])} 份"
                   f"{'：' + ', '.join('`%s`' % x for x in ab['skipped']) if ab.get('skipped') else ''}）")
        if od:
            out.append(f"  **待结积压 {len(od)} 份**（登记日期早于运行当天）—— 两种成因都要认："
                       "①审核任务没跑；②审过了但块里留着「待本人决定」，按审核 SOP「任一块未过 → 整份不勾不移」被扣在根下：")
            for x in od:
                out.append(f"  - `{x['name']}` 滞留 {x['days']} 天")
        else:
            out.append("  无积压：根下没有早于当天的日记账。")
        out.append("")
        out.append("> **判据正本** = `Workflows/记忆库自动审核与人工入口.md`「审核范围」段"
                   "（本段只回抄它的机器可读形态，不另立口径）；`Archive/` 与各子目录不扫，"
                   "当天及以后新增不算积压，本脚本**不代审核任务移动或勾选任何文件**。")
        out.append("> **为什么只报不拦**：积压的成因是外因（设备关机 / 节假日 / app 未运行且调度器不补跑），"
                   "或需等人裁定「待本人决定」的块；做成拦停 = 每次收尾恒红，恒红的门禁等于没有门禁。"
                   "季度只看积压份数是否归零与最长滞留天数的趋势。")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Todo 归档体检（完成 = 移走）")
    ap.add_argument("--todo", default=str(TODO_PATH), help="Todo 文件路径")
    ap.add_argument("--inbox", default=str(INBOX_DIR),
                    help="Inbox 目录路径（第十节用；指到 fixture 目录可单测积压计数，不碰真实 Inbox）")
    ap.add_argument("--audit-date", default=None,
                    help="覆盖「运行当天」（YYYY-MM-DD）。第十节的积压判定本以真实时钟为准，"
                         "此参数只为 fixture 验收可复现，日常运行不要带")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="报告输出路径")
    ap.add_argument("--check", action="store_true", help="门禁模式：有违规退出码 1")
    ap.add_argument("--cost-check", action="store_true", help="硬门禁：实际启动包 / BOOT 源政策超标即退出码 1")
    ap.add_argument("--content-check", action="store_true", help="严格内容债门禁：overview/state/section 截断/缺 state 任一存在即退出码 1")
    ap.add_argument("--scope-check", action="store_true", help="门禁模式：`scope` 非法取值 / 冗余出现即退出码 1（季度维护用）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="不往 stdout 打印")
    args = ap.parse_args()

    todo = Path(args.todo)
    if not todo.is_file():
        print(f"[!] 找不到 Todo 文件：{todo}", file=sys.stderr)
        return 1

    result = scan_todo(todo)
    result["claims"] = scan_todo_claims(todo)
    result["staging"] = scan_staging_volume()
    run_date = date.today()
    if args.audit_date:
        try:
            run_date = date.fromisoformat(args.audit_date)
        except ValueError:
            print(f"[!] --audit-date 要写成 YYYY-MM-DD，收到的是「{args.audit_date}」", file=sys.stderr)
            return 1
    result["audit_backlog"] = scan_audit_backlog(Path(args.inbox), run_date)
    result["type_vocab"] = scan_type_vocab()
    tv = result["type_vocab"]
    if tv["vocab"] is None:
        print("[!] 规则正本第 5 条的 `type` 括号词表解析失败 —— 类型检查已失明，不静默通过（要改第 5 条写法先修这里）",
              file=sys.stderr)
        return 1
    type_violations = len(tv["bad"])
    violations = (len(result["signals"]) + len(result["unmapped_groups"])
                  + len(result["claims"]["broken"]) + type_violations)
    cost = result.get("cost") or {}
    scope = result.get("scope") or {}
    claims = result["claims"]
    ab = result["audit_backlog"] or {}
    backlog = ab.get("overdue") or []
    claim_violations = len(claims["broken"])
    claim_notes = len(claims["unverifiable"])
    scope_violations = len(scope.get("bad") or []) + len(scope.get("redundant") or [])
    boot_health = result.get("boot_health") or {}
    cost_violations = (1 if cost.get("boot_over") else 0) + len(boot_health.get("hard") or [])
    content_violations = (
        len(cost.get("overview_offenders") or [])
        + len(cost.get("state_offenders") or [])
        + len(result.get("missing_state") or [])
        + len(boot_health.get("section_debt") or [])
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.json:
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        out.write_text(render(result), encoding="utf-8")

    summary = (
        f"完成信号残留 {len(result['signals'])} 条 / 无对应目录分组 {len(result['unmapped_groups'])} 个 / "
        f"缺 completed.md 项目 {len(result['missing_completed'])} 个 / 删除线留档 {len(result['retired'])} 条 / "
        f"Agent 启动硬门禁 {cost_violations} 项 / 内容债 {content_violations} 项 / scope 违规 {scope_violations} 处 / "
        f"Todo 假声明 {claim_violations} 处（另 {claim_notes} 条旧声明无法核对） / "
        f"暂存层待压缩（判压面=journal） {len((result['staging'] or {}).get('over') or [])} 份 / "
        f"type 词表违规 {type_violations} 处（另 {len(tv['missing'])} 篇缺 type） / "
        f"待结积压 {len(backlog)} 份（只报不拦）"
    )
    if not args.quiet:
        print(f"Todo: {todo}")
        print(f"体积: {result['char_total']} 字符 / 条目 {result['item_count']} 条 / 分组 {len(result['groups'])} 个")
        print(summary)
        for s in result["signals"]:
            print(f"  L{s['line']} [{s['signal']}] {s['group']} :: {s['text'][:70]}")
        for g in result["unmapped_groups"]:
            print(f"  L{g['line']} 分组无对应项目目录: {g['title']}")
        for b in (scope.get("bad") or [])[:20]:
            print(f"  scope 非法取值: {b['file']} -> {b['value']}")
        for x in (scope.get("redundant") or [])[:20]:
            print(f"  scope 冗余出现: {x}")
        for b in claims["broken"][:20]:
            print(f"  Todo 假声明: {b['file']}:{b['line']} 声明的「{b['title']}」在 Todo 与任何 completed.md 都查不到")
        for b in tv["bad"][:20]:
            print(f"  type 词表外取值: {b['file']} -> {b['value']}")
        for x in backlog[:20]:
            print(f"  待结积压: Inbox/{x['name']}（登记日 {x['date']}，滞留 {x['days']} 天）")
        print(f"报告: {out}")

    if args.check and violations:
        if claims["broken"]:
            for b in claims["broken"]:
                print(f"[!] {b['file']}:{b['line']} 「{b['title']}」查无此条 —— "
                      f"要么把它真写进 Todo，要么删改这句声明", file=sys.stderr)
        if violations - claim_violations:
            print(f"[!] 有 {violations} 处违规 —— 完成 = 移走（追加到 working/completed.md 并从 Todo 删除该条）", file=sys.stderr)
        return 1

    if args.cost_check and cost_violations:
        print(f"[!] Agent 启动硬门禁 {cost_violations} 项超标 —— 检查 BOOT 源政策或实际 assembled 启动包预算", file=sys.stderr)
        return 1

    if args.content_check and content_violations:
        print(f"[!] 内容债 {content_violations} 项未清零 —— overview/state/section 截断/缺 state；本模式用于季度或切换验收", file=sys.stderr)
        return 1

    if args.scope_check and scope_violations:
        print(f"[!] scope 违规 {scope_violations} 处 —— 合法值 = global 或 Projects/ 目录名；Projects/ 层内不填该字段", file=sys.stderr)
        return 1

    if violations:
        print(f"[ok] --check 未启用，仅报告（{violations} 处违规）")
    elif content_violations:
        print(f"[ok] 结构门禁通过；内容债 {content_violations} 项（报告项，--content-check 可严格检查）")
    else:
        print("[ok] 干净：无完成信号残留、分组名全部命中项目目录、Todo 声明可核对、`type` 取值在词表内")
    if cost_violations and not args.cost_check:
        print(f"[note] 实际启动硬门禁 {cost_violations} 项 —— 见报告第五节")
    if content_violations and not args.content_check:
        print(f"[note] 内容债 {content_violations} 项 —— 不阻断 --cost-check；见报告第五节，严格检查用 --content-check")
    if scope_violations and not args.scope_check:
        print(f"[note] scope 违规 {scope_violations} 处 —— 不拦本次门禁，见报告第六节（季度用 --scope-check 拦）")
    if claim_notes:
        print(f"[note] {claim_notes} 条旧「已并入 Todo」声明无 `Todo → 「标题」` 形态、无法机器核对 —— "
              f"不拦，见报告第七节（新写必须带形态，否则脚本查不到）")
    if tv["missing"]:
        print(f"[note] {len(tv['missing'])} 篇有 frontmatter 却缺 `type` —— 只提示不拦（补字段是写入侧义务），清单见报告第九节")
    if backlog:
        print(f"[note] 待结积压 {len(backlog)} 份（最长滞留 {max(x['days'] for x in backlog)} 天）—— 不拦本次门禁，见报告第十节；"
              f"先分清两种成因：审核任务没跑，还是审过但块里留有『待本人决定』把整份扣住；处置入口在 "
              f"`Workflows/记忆库自动审核与人工入口.md`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
