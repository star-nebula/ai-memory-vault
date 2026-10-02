#!/usr/bin/env python3
"""Todo 归档体检 —— 校验 `Memory/Todo.md` 是否守住「完成 = 移走」。

背景（2026-09-21）：
    「待办 → `Memory/Todo.md`；完成 → `Projects/<项目名>/working/completed.md`」
    这条链路原本只写在会话收尾 checklist 里，**没有任何门禁**，于是静默积累
    「已标完成却未移走」的条目（实测 4 条，含一条 2000 字符的重复复盘）。
    对比：索引漂移有 `mem_index.py --check`、断链有 `link_audit.py`，唯独待办归档没有。
    本脚本把「归档动作」变成可校验项。

检查清单（**计数不在此维护**，以本文件的 `scan_*` 函数为准——写死「N 件事」就是第二份事实源，加一项就漂）：
    1. 完成信号残留 —— Todo 里带完成标记、但未移走的条目（违规）
    2. 分组名映射   —— `## 分组` 标题必须等于 `Projects/` 下的目录名（规则要求）
    3. completed.md —— 被 Todo 提到的项目是否已有 `working/completed.md`
    4. 开场成本     —— 会话开场必读三件的实测体量与超标清单（2026-09-29 增，报告项）
    5. scope 词表   —— 跨层归属字段的非法取值与冗余出现（2026-09-29 增，报告项；
                     合法值 = `global` ∪ `Projects/` 目录名，由实盘推导、脚本内不写死词表）
    6. Todo 声明核对 —— journal/plan 里「已并入 Todo」这类话**是否真有其条**
                     （2026-09-30 增，并入 `--check` 拦；病灶：09-26 journal 声称已并入，
                     Todo 里从来没有那条，静默挂起三天）
    7. 暂存层体量   —— journal / completed 超「压缩为阶段小结」阈值（2026-09-30 增，报告项）。
    8. `type` 词表    —— frontmatter `type` 取值是否在规则正本第 5 条的括号词表内（2026-09-30 增，
                     并入 `--check` 拦；词表机读自规则正本、脚本内不写死；解析失败 = 退出码 1）
                     该阈值原先写在 `rule/写入与禁止.md` 第 3 条与 `Todo.md` 正文里（各一份），
                     用户裁定「数字不进文档」后移入本文件常量；文档只留指针

**为什么体量阈值写在脚本、不写进文档**：
    `Memory/_index.md` §七 曾长期声称开场三件套「≈ 8 KB」。2026-09-29 实测：
    `_index.md` 4708 + `Todo.md` 6623 字符，而 `Projects/某项目/_overview.md` 单件就
    18072 字符—— 三件套最坏情形近 3 万字符，声称值失真约 4~8 倍。
    数字是会变的实测值，写进规则文档就变成第二份事实源（本库对索引条数已有同款教训：
    见 `_index.md` §二「条数不在此表维护」）。故：**阈值 = 本文件顶部常量（策略），
    实测 = 本报告输出（事实）**，文档只指路不抄数。

阈值分档（`--check` 把 1/2/6/8 当门禁；成本、`scope` 与暂存层体量走报告，避免历史欠账或改名当天把每次收尾都判红）：
    · 单文件超过 LIMIT_* 记「待瘦身」；`--cost-check` 才作硬门禁退出码 1。
    · 暂存层（journal / completed）超 LIMIT_STAGING_CHARS（**字符数**口径）记「待压缩」，**只报告不拦**：
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
    python todo_audit.py --cost-check    # 门禁模式：开场成本超标即退出码 1（季度维护用）
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
from pathlib import Path

# Windows 控制台默认 GBK，本脚本输出含中文与符号，不加这行会 UnicodeEncodeError 中断。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

def _find_memory_dir() -> Path:
    """定位记忆库根：环境变量 AI_MEMORY_DIR 优先；否则从 cwd / 脚本位置向上探测
    名为 Memory 且含 Todo.md / _index.md / rule/ 之一的目录（适配任意 vault 布局）。"""
    env = os.environ.get("AI_MEMORY_DIR")
    if env:
        return Path(env)
    for start in (Path.cwd(), Path(__file__).resolve()):
        for p in [start, *start.parents]:
            cand = p / "Memory"
            if cand.is_dir() and any(
                (cand / marker).exists() for marker in ("Todo.md", "_index.md", "rule")
            ):
                return cand
    return Path.cwd() / "Memory"

SCRIPT_DIR = Path(__file__).resolve().parent
MEMORY_DIR = _find_memory_dir()
TODO_PATH = MEMORY_DIR / "Todo.md"
INDEX_PATH = MEMORY_DIR / "_index.md"
PROJECTS_DIR = MEMORY_DIR / "Projects"
DEFAULT_OUT = SCRIPT_DIR / "_out" / "todo_audit.txt"

# —— 开场成本阈值（策略常量；改这里，不改文档）——
LIMIT_INDEX = 5000      # _index.md：唯一入口，超了说明逐篇索引该下沉到各层
LIMIT_TODO = 8000       # Todo.md：长条目细节应移 journal/plan，只留一行指针
LIMIT_OVERVIEW = 4000   # Projects/<名>/_overview.md：只留定位/关键路径/关联资产/状态
LIMIT_TRIO_WORST = 12000  # 三件套最坏情形合计（入口 + Todo + 最大 overview）
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
    overs = []
    for ov in sorted(PROJECTS_DIR.glob("*/_overview.md")) if PROJECTS_DIR.is_dir() else []:
        n = char_len(ov)
        if n > LIMIT_OVERVIEW:
            overs.append({"project": ov.parent.name, "chars": n})
    overs.sort(key=lambda x: -x["chars"])
    index_chars = char_len(INDEX_PATH)
    return {
        "index_chars": index_chars,
        "index_over": index_chars > LIMIT_INDEX,
        "worst_overview": overs[0]["chars"] if overs else 0,
        "trio_worst_chars": index_chars + overs[0]["chars"] if overs else index_chars,
        "overview_offenders": overs,
        "overview_total": len(list(PROJECTS_DIR.glob("*/_overview.md"))) if PROJECTS_DIR.is_dir() else 0,
    }


# 强完成信号：命中即视为「已标完成」→ 必须已移走
STRONG_SIGNALS = ("✅", "✔", "已执行完毕", "已完成：", "已完成:", "已结清", "已归档")


def scan_staging_volume() -> dict:
    """暂存层（journal / completed）体量 —— 「该压缩旧段为阶段小结」的实测来源。

    只报告不拦：压缩是渐进蒸馏，存量不可能当天清零（恒红的门禁等于没有门禁）。
    口径正本 = `rule/写入与禁止.md` 第 3 条；阈值 = 上面的 `LIMIT_STAGING_CHARS`（策略在脚本、事实在报告）。

    度量单位是**字符数**，不是行数：本库 journal 常把一整段实测叙述写成一行，行数口径实测永不触发
    （2026-09-30 用户裁定改口径）。行数仍一并呈报，只作阅读参考列。
    """
    files = []
    if PROJECTS_DIR.is_dir():
        files = sorted(list(PROJECTS_DIR.glob("*/working/journal.md"))
                       + list(PROJECTS_DIR.glob("*/working/completed.md")))
    rows = []
    for f in files:
        text = read_text(f)
        rows.append({"project": f.parent.parent.name, "file": f.name,
                     "lines": len(text.splitlines()), "chars": len(text)})
    over = sorted([x for x in rows if x["chars"] > LIMIT_STAGING_CHARS], key=lambda x: -x["chars"])
    heaviest = sorted(rows, key=lambda x: -x["chars"])[:STAGING_REPORT_TOP]
    return {"scanned": len(rows), "over": over, "heaviest": heaviest}

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
            if f.name == "_index.md":
                continue
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
    # 派生物与路径已表达归属处：两处出现即冗余（第二份事实源）
    for layer in list(SCOPE_LAYERS) + ["Projects"]:
        idx = MEMORY_DIR / layer / "_index.md"
        if idx.is_file() and frontmatter_scope(read_text(idx)) is not None:
            redundant.append(f"{layer}/_index.md")
    for pat in ("*/*.md", "*/*/*.md"):
        for f in sorted(PROJECTS_DIR.glob(pat)) if PROJECTS_DIR.is_dir() else []:
            if f.name == "_index.md" or frontmatter_scope(read_text(f)) is None:
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
# 豁免面与 `scope` 那条同源：登记簿 / 规则文本 / 派生物 / 暂存层台账 / 整块无 frontmatter 的结构性豁免
TYPE_EXEMPT_TOP = ("Inbox", "rule")
TYPE_EXEMPT_NAMES = ("_index.md", "README.md")
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
    """分组标题 → 候选目录名：去首尾空白、去掉结尾的括号补充说明。"""
    t = title.strip()
    t = TRAILING_PAREN.sub("", t).strip()
    return t


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
    lines = read_text(todo_path).splitlines()
    dirs = project_dirs()
    dirs_lower = {k.lower(): k for k in dirs}

    signals: list[dict] = []
    retired: list[dict] = []
    groups: list[dict] = []
    sub_groups = 0
    cur_group = "(文件头)"
    char_total = 0
    char_by_group: dict[str, int] = {}
    item_count = 0

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        char_total += len(line)
        char_by_group[cur_group] = char_by_group.get(cur_group, 0) + len(line)
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
    out.append("## 五、开场成本（会话必读三件；阈值为策略常量，见脚本顶部）")
    out.append("")
    if not c:
        out.append("（未采集——`--todo` 指向库外路径时跳过）")
    else:
        trio = c["trio_worst_chars"] + r["char_total"]
        out.append(f"- `Memory/_index.md`：{c['index_chars']} 字符（限 {LIMIT_INDEX}）{'**超标**' if c['index_over'] else 'ok'}")
        out.append(f"- `Memory/Todo.md`：{r['char_total']} 字符（限 {LIMIT_TODO}）{'**超标**' if r['char_total'] > LIMIT_TODO else 'ok'}")
        out.append(f"- `Projects/*/_overview.md`：共 {c['overview_total']} 份，最大 {c['worst_overview']} 字符（单份限 {LIMIT_OVERVIEW}）")
        if c["overview_offenders"]:
            out.append(f"  **待瘦身 {len(c['overview_offenders'])} 份**（细节移 `working/journal.md`/`plan.md`，overview 只留定位·关键路径·关联资产·状态）：")
            for o in c["overview_offenders"]:
                out.append(f"  - `{o['project']}` {o['chars']} 字符")
        else:
            out.append("  无单份超标。")
        out.append(f"- 最坏情形三件合计：{trio} 字符（限 {LIMIT_TRIO_WORST}）{'**超标**' if trio > LIMIT_TRIO_WORST else 'ok'}")
        out.append("")
        out.append("> 口径：季度维护只看**待瘦身项数是否下降**，不逐条清零（同 `dup_check` 基线口径）。")
        out.append("> 文档里不写体量数字（实测值会漂）；本段是唯一事实源。")
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
            out.append(f"  **冗余出现 {len(s['redundant'])} 处**（`Projects/` 层内路径即归属、`_index.md` 是派生物，都不该带该字段）：")
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
    out.append("## 八、暂存层体量（journal / completed 超阈值 → 该压缩旧段为「阶段小结」）")
    out.append("")
    if not st:
        out.append("（未采集）")
    else:
        out.append(f"- 扫描 `Projects/*/working/` 下 journal 与 completed 共 {st['scanned']} 份，"
                   f"阈值口径 = **字符数** {LIMIT_STAGING_CHARS} 字符/份（**阈值是本文件顶部常量，本段是实测**）。")
        if st["over"]:
            out.append(f"  **超阈值 {len(st['over'])} 份**（旧段压成阶段小结：只留结论 + wikilink 指向已转正笔记）：")
            for x in st["over"]:
                out.append(f"  - `Projects/{x['project']}/working/{x['file']}` {x['chars']} 字符 / {x['lines']} 行")
        else:
            out.append("  按字符数口径**无超标**文件。")
        out.append(f"- 同批按**字符数**最重的 {len(st['heaviest'])} 份（读取成本实际由它决定）：")
        for x in st["heaviest"]:
            flag = "  ← 超阈值" if x["chars"] > LIMIT_STAGING_CHARS else ""
            out.append(f"  - `Projects/{x['project']}/working/{x['file']}` {x['chars']} 字符 / {x['lines']} 行{flag}")
        out.append("")
        out.append("> **单位为什么是字符不是行**（2026-09-30 裁定，阈值移入脚本常量时顺带复检口径）："
                   "原写死在文档里的「约 500 行」在本库**永不触发**——journal 习惯把一整段实测叙述写成一行，"
                   "单行动辄上千字符，于是整批按行数零超标、最重的一份却已是几万字符。"
                   "一个永不报警的阈值和一个正确的阈值在跑之前长得一模一样；行数在本段降级为参考列。")
        out.append("> **只报告不拦**（季度看「待压缩份数」与最重份的字符数是否下降，同开场成本与 `dup_check` 基线口径）："
                   "蒸馏是渐进动作，把存量债当门禁会让每次收尾恒红。")
        out.append("> 口径正本见 `rule/写入与禁止.md` 第 3 条；该行只指路，不抄阈值与份数。")
    tv = r.get("type_vocab") or {}
    out.append("")
    out.append("## 九、frontmatter `type` 词表（取值清单机读自规则正本第 5 条，脚本内不写死）")
    if not tv:
        out.append("（本次未扫描）")
    else:
        out.append(f"- 词表（解析自 `rule/写入与禁止.md` 第 5 条）：{', '.join(tv.get('vocab') or [])}")
        out.append(f"- 参与核对 {tv.get('scanned', 0)} 篇 / 豁免 {tv.get('exempt', 0)} 份"
                   "（`Inbox/` 登记簿、`rule/` 规则文本、各层 `_index.md` 与 README、各 `working/` 台账、整块无 frontmatter 的结构性豁免）")
        for b in (tv.get("bad") or [])[:20]:
            out.append(f"  [!] 词表外取值：{b['file']} -> {b['value']}（改字段还是扩词表，由人裁定）")
        for x in (tv.get("missing") or [])[:20]:
            out.append(f"  [·] 缺 `type`：{x}")
        if not (tv.get("bad") or []) and not (tv.get("missing") or []):
            out.append("  词表外取值 0 / 缺 type 0")
    out.append("> **拦/报划界**：词表外取值进 `--check` 拦；缺 `type` 只报（同「缺 scope」）。**只报告不自动改**。")
    out.append("> 词表只有一处正本：本脚本不复制取值清单，第 5 条改了这里跟着变；解析不出来就退出码 1，不静默通过。")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Todo 归档体检（完成 = 移走）")
    ap.add_argument("--todo", default=str(TODO_PATH), help="Todo 文件路径")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT), help="报告输出路径")
    ap.add_argument("--check", action="store_true", help="门禁模式：有违规退出码 1")
    ap.add_argument("--cost-check", action="store_true", help="门禁模式：开场成本超标即退出码 1（季度维护用）")
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
    claim_violations = len(claims["broken"])
    claim_notes = len(claims["unverifiable"])
    scope_violations = len(scope.get("bad") or []) + len(scope.get("redundant") or [])
    cost_violations = (
        len(cost.get("overview_offenders") or [])
        + (1 if cost.get("index_over") else 0)
        + (1 if result["char_total"] > LIMIT_TODO else 0)
        + (1 if (cost.get("trio_worst_chars", 0) + result["char_total"]) > LIMIT_TRIO_WORST else 0)
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
        f"开场成本待瘦身 {cost_violations} 项 / scope 违规 {scope_violations} 处 / "
        f"Todo 假声明 {claim_violations} 处（另 {claim_notes} 条旧声明无法核对） / "
        f"暂存层待压缩 {len((result['staging'] or {}).get('over') or [])} 份 / "
        f"type 词表违规 {type_violations} 处（另 {len(tv['missing'])} 篇缺 type）"
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
        print(f"[!] 开场成本 {cost_violations} 项超标 —— 细节下沉 working/journal.md|plan.md，overview 只留四要素", file=sys.stderr)
        return 1

    if args.scope_check and scope_violations:
        print(f"[!] scope 违规 {scope_violations} 处 —— 合法值 = global 或 Projects/ 目录名；Projects/ 层内与 _index.md 不填该字段", file=sys.stderr)
        return 1

    print(f"[ok] 干净：无完成信号残留、分组名全部命中项目目录、Todo 声明可核对、`type` 取值在词表内" if not violations else f"[ok] --check 未启用，仅报告（{violations} 处违规）")
    if cost_violations and not args.cost_check:
        print(f"[note] 开场成本待瘦身 {cost_violations} 项 —— 不拦本次门禁，见报告第五节（季度只看项数增减）")
    if scope_violations and not args.scope_check:
        print(f"[note] scope 违规 {scope_violations} 处 —— 不拦本次门禁，见报告第六节（季度用 --scope-check 拦）")
    if claim_notes:
        print(f"[note] {claim_notes} 条旧「已并入 Todo」声明无 `Todo → 「标题」` 形态、无法机器核对 —— "
              f"不拦，见报告第七节（新写必须带形态，否则脚本查不到）")
    if tv["missing"]:
        print(f"[note] {len(tv['missing'])} 篇有 frontmatter 却缺 `type` —— 只提示不拦（补字段是写入侧义务），清单见报告第九节")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
