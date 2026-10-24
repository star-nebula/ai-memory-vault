#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆库索引生成 / 校验（Memory 各层 _index.md）。

背景
----
记忆库的「手工索引」反复漂移（Home.md 曾落后实盘 4~5 条）。根治办法是把索引
变成**派生物**：frontmatter + 正文首段 → `_index.md`，并可用 `--check` 当门禁。

设计要点
--------
1. **合并式生成**：已有行的人工「一句话定位 / 关键词」**原样保留**，只增删行。
   因此可以放心先跑 `--write` 拿机器初稿，再手工润色，后续重跑不会抹掉润色。
2. `--check` 是门禁：报告缺失行 / 失效行 / **「更新」列滞旧**，非 0 退出。
   定位 / 关键词是人工润色值，`--write` 不覆盖已有人工行；改笔记摘要/标签不会自动刷新这两格。
3. 顺带校验**手工**地图页是否漏列顶层项（`Memory/_index.md` 必查；工作区根 `_index.md` 存在时才查）。
4. **同名消歧单一正本**：完整表只允许存在于工作区根 `AGENTS.md` §同名文件消歧；
   `Memory/_index.md` §六 只留指针。校验正本表结构完整（五组、三列、无重复）与指针有效；
   标题 / 表格 / 指针必须落在**真 Markdown 内容**里——写进代码围栏或 HTML 注释等于不存在。
5. **决策锚点守恒**：`Decisions/_index.md` 是人工散文行索引，永不生成；机器只查
   「每张决策卡都有一行带 `[[Decisions/文件名]]`，每个锚点都指向真实文件」。

用法
----
    # 生成 / 更新（幂等，保留人工润色）
    python mem_index.py --write

    # 体检（CI / 收尾用）
    python mem_index.py --check

    # 只看某层（Decisions 只可 --check）
    python mem_index.py --write --layer Lessons

    # 强制按实盘重算人工「定位 / 关键词」（默认保留人工润色）
    python mem_index.py --write --refresh-cells

运行环境：仅标准库（Python 3.9+）。记忆库定位：环境变量 `AI_MEMORY_DIR`，
或从当前目录向上探测 `<根>/Memory`；消歧表唯一正本取「工作区根 AGENTS.md」，
`Memory/_index.md` §六 只留指针。
"""

from __future__ import annotations

import argparse
import datetime as _dt
import io
import os
import re
import sys
from pathlib import Path

# Windows 控制台默认 GBK，输出含中文/符号时不重配编码会 UnicodeEncodeError 中断体检。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

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


MEM = _find_memory_dir()
VAULT = MEM.parent  # 库根：AGENTS.md / Templates 所在层
REPO = VAULT  # 报告相对路径基准
TODAY = _dt.date.today().isoformat()

# 需要生成 _index.md 的层（Decisions 除外：其索引行由人写，且有「一行覆盖多决策」的合并形态）
LAYERS = ["Preferences", "Plans", "Lessons", "Workflows"]
# Projects 以「项目目录」为行单位，不走文件行
PROJECTS = "Projects"
# Decisions：永不进 LAYERS、永不 --write；机器只查锚点守恒
DEC_LAYER = "Decisions"
DEC_ANCHOR = re.compile(r"\[\[Decisions/([^\]\|#]+)\]\]")
# 层级特有的表头说明（会写进 _index.md，故必须放在脚本里才不会下次 --write 时丢失）
EXTRA_NOTE = {
    "Projects": "> 状态标记：🟢 进行中 ・ ⏸ 暂停 ・ 🔒 封存 ・ 无标记 = 资料 / 已归档。",
}

FM = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|(.*?)\|(.*?)\|(.*?)\|\s*$", re.M)


# --------------------------------------------------------------------------- #
# frontmatter / 正文抽取
# --------------------------------------------------------------------------- #
def read_text(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def split_front(text: str) -> tuple[dict[str, str], str]:
    m = FM.match(text)
    if not m:
        return {}, text
    fm: dict[str, str] = {}
    for line in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
        if mm:
            fm[mm.group(1)] = mm.group(2).strip()
    return fm, text[m.end():]


def fm_list(fm: dict[str, str], key: str) -> list[str]:
    v = fm.get(key, "").strip()
    if not v:
        return []
    v = v.strip("[]")
    return [x.strip().strip("'\"") for x in v.split(",") if x.strip()]


LABELLED = re.compile(r"^\*\*(?P<label>[^*]{1,24}?)[:：]?\*\*[:：]?\s*(?P<rest>\S.*)$")


def _clean(s: str, limit: int) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    s = re.sub(r"`([^`]*)`", r"\1", s)
    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda m: m.group(2) or m.group(1), s)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    s = s.strip()
    if not s:
        return ""
    cut = re.split(r"(?<=[。；;!?！？])", s)[0]
    s = cut if len(cut) >= 8 else s
    return s[: limit - 1] + "…" if len(s) > limit else s


def _first_labeled(body: str, limit: int) -> str:
    """加粗标签兜底：`**Why：** 正文` 这类行以 `*` 起手，普通段落扫描会跳过。"""
    in_fence = False
    for raw in body.splitlines():
        s = raw.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not s:
            continue
        m = LABELLED.match(s)
        if not m:
            continue
        out = _clean(m.group("rest"), limit)
        if out:
            return out
    return ""


def _first_plain(body: str, limit: int) -> str:
    in_fence = False
    for raw in body.splitlines():
        s = raw.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not s:
            continue
        if s[0] in "#>-|*+!" or s.startswith("<!--"):
            continue
        if re.match(r"^\d+[.、)]\s", s):
            continue
        s = _clean(s, limit)
        if not s:
            continue
        return s
    return ""


def first_sentence(body: str, limit: int = 62) -> str:
    """正文首个实质段落（跳过标题/引用/列表/表格/代码围栏）。

    找不到 plain 段落时补一次**加粗标签兜底**：本库 Lesson/决策 的主文体常见
    `**Why：** 正文` / `**How to apply：** 正文`，那种行以 `*` 起手、会被普通段落
    跳过规则一并挡掉，于是「正文其实写了、索引却拿不到一句话」。
    """
    old = _first_plain(body, limit)
    if old:
        return old
    return _first_labeled(body, limit)


def note_meta(p: Path) -> tuple[str, str, str]:
    """返回 (一句话定位, 关键词, 更新日期)。"""
    text = read_text(p)
    fm, body = split_front(text)
    summary = fm.get("summary") or fm.get("description") or ""
    loc = summary.strip() or first_sentence(body) or "（待补一句话）"
    tags = fm_list(fm, "tags")
    kw = ", ".join(
        [t for t in tags if t.lower() not in ("lesson", "workflow", "plan", "preference")]
    ) or "—"
    upd = fm.get("updated") or fm.get("created") or ""
    if not upd:
        upd = _dt.date.fromtimestamp(p.stat().st_mtime).isoformat()
    return loc, kw, upd


def project_meta(d: Path) -> tuple[str, str, str]:
    ov = d / "_overview.md"
    if ov.exists():
        text = read_text(ov)
        fm, body = split_front(text)
        loc = (fm.get("summary") or fm.get("description") or "").strip() or first_sentence(body)
        kw = ", ".join(fm_list(fm, "tags")) or "—"
        upd = fm.get("updated") or fm.get("created") or ""
        if not upd:
            upd = _dt.date.fromtimestamp(ov.stat().st_mtime).isoformat()
    else:
        loc, kw, upd = "⚠️ 缺 `_overview.md`", "—", ""
    return loc or "（待补一句话）", kw, upd


# --------------------------------------------------------------------------- #
# 读回既有索引（合并用）
# --------------------------------------------------------------------------- #
def load_existing(idx: Path) -> dict[str, tuple[str, str, str]]:
    if not idx.exists():
        return {}
    out = {}
    for m in ROW.finditer(read_text(idx)):
        out[m.group(1).strip()] = (m.group(2).strip(), m.group(3).strip(), m.group(4).strip())
    return out


def keep_or_auto(exist: dict, key: str, auto: tuple[str, str, str],
                 refresh_cells: bool = False) -> tuple[str, str, str]:
    """人工值优先；但「更新」列始终刷新为实盘（它是事实，不是判断）。
    `refresh_cells=True` 时连人工定位/关键词也按实盘重算——显式 `--refresh-cells` 才启用。"""
    if refresh_cells:
        return auto
    if key in exist:
        loc, kw, _ = exist[key]
        if loc and loc != "（待补一句话）":
            return loc, kw or auto[1], auto[2]
    return auto


def nl_of(p: Path) -> str:
    if p.exists() and b"\r\n" in p.read_bytes()[:4000]:
        return "\r\n"
    return "\n"


def render(idx: Path, title: str, layer_key: str, rows: list[tuple[str, str, str, str]]) -> str:
    n = nl_of(idx)
    created = "created: 2026-09-21"
    if idx.exists():
        m = re.search(r"^created:\s*(\S+)", read_text(idx), re.M)
        if m:
            created = f"created: {m.group(1)}"

    # 不输出 scope：那是「跨层笔记归属」专用字段（见 rule/写入与禁止.md 第 5 条），
    # 索引文件的位置已由文件名给出，复用同名键会长出第二种含义。
    head = [
        "---",
        "type: index",
        created,
        f"updated: {TODAY}",
        f"tags: [索引, 目录, {layer_key}]",
        "---",
        "",
        f"# {title}（目录）",
        "",
        f"> 本层共 **{len(rows)}** 条。本页是生成/校验目录，不参与 Agent 启动；查内容用 `memory_query.py`。",
        "> 维护：`python scripts/mem_index.py --write`。新增条目自动补行；"
        "**本页手工写的「定位 / 关键词」会被保留**，可放心润色。",
        "> 校验：`python scripts/mem_index.py --check`（发现漂移非 0 退出）。",
    ]
    key = layer_key.capitalize()
    if key in EXTRA_NOTE:
        head.append(EXTRA_NOTE[key])
    head += [
        "",
        "| 路径 | 一句话定位 | 关键词 | 更新 |",
        "|---|---|---|---|",
    ]
    body = [f"| `{k}` | {loc} | {kw} | {upd} |" for k, loc, kw, upd in rows]
    return n.join(head + body) + n


def brief(s: str, n: int = 60) -> str:
    return s if len(s) <= n else s[:n] + "…"


def note_mtimes(layer: str) -> dict[str, float]:
    """层内每篇笔记的 mtime，键名与索引行名同构（`层/文件.md`；Projects 为 `Projects/<项目>/`）。"""
    d = MEM / layer
    out: dict[str, float] = {}
    if not d.is_dir():
        return out
    if layer == PROJECTS:
        for sub in (x for x in d.iterdir() if x.is_dir()):
            ov = sub / "_overview.md"
            out[f"{PROJECTS}/{sub.name}/"] = (ov if ov.exists() else sub).stat().st_mtime
        return out
    for p in d.glob("*.md"):
        if p.name not in ("_index.md", "README.md"):
            out[f"{layer}/{p.name}"] = p.stat().st_mtime
    return out


def why_late(key: str, idx: Path, mtimes: dict[str, float] | None) -> str:
    """给已红的滞旧行补时刻证据：是「笔记改完没刷索引」还是「索引侧被手改/写错」。"""
    if not mtimes or key not in mtimes or not idx.exists():
        return ""
    nm, im = mtimes[key], idx.stat().st_mtime
    f = lambda t: _dt.datetime.fromtimestamp(t).strftime("%m-%d %H:%M:%S")  # noqa: E731
    if nm > im:
        return (f"；实盘 mtime {f(nm)} 晚于该层索引生成时刻 {f(im)}"
                f" → 索引生成后该笔记又被改过，该写入方收尾漏跑 --write")
    return f"；笔记 mtime {f(nm)} 早于索引生成时刻 {f(im)} → 不是「改完没刷」，疑为索引侧被手改或行内容写错"


def write_or_check(idx: Path, content: str, check: bool, problems: list[str],
                   mtimes: dict[str, float] | None = None) -> int:
    """check 模式返回「比对过的行数」，write 模式返回 0（写入无需计量）。"""
    if check:
        if not idx.exists():
            problems.append(f"[缺索引] {idx.relative_to(REPO)}")
            return 0
        old_rows = load_existing(idx)
        new_rows = {m.group(1).strip(): tuple(x.strip() for x in m.groups()[1:4])
                    for m in ROW.finditer(content)}
        for k in sorted(set(old_rows) - set(new_rows)):
            problems.append(f"[失效行] {idx.relative_to(REPO)} :: {k}（文件已不存在）")
        for k in sorted(set(new_rows) - set(old_rows)):
            problems.append(f"[缺失行] {idx.relative_to(REPO)} :: {k}（新笔记未登记）")
        # 只比行名会放行「行在、更新列滞旧」的静默漂移。
        # 定位/关键词是人工润色值：keep_or_auto 会保留旧值，故不做自动比对。
        for k in sorted(set(old_rows) & set(new_rows)):
            disk, live = old_rows[k][2], new_rows[k][2]
            if disk != live:
                problems.append(
                    f"[索引更新列滞旧] {idx.relative_to(REPO)} :: {k} 的「更新」列"
                    f" 索引写 {brief(disk)} ≠ 实盘 {brief(live)}（跑 --write 刷新）"
                    f"{why_late(k, idx, mtimes)}"
                )
        return len(set(old_rows) & set(new_rows))
    if idx.exists() and read_text(idx) == content:
        return 0
    idx.parent.mkdir(parents=True, exist_ok=True)
    with io.open(idx, "w", encoding="utf-8", newline="") as f:
        f.write(content)
    print(f"  写入 {idx.relative_to(REPO)}  ({content.count(chr(10))} 行)")
    return 0


# --------------------------------------------------------------------------- #
# 手工地图页的顶层覆盖校验
# --------------------------------------------------------------------------- #
def top_entries(d: Path) -> list[str]:
    """顶层项名，供**手工地图页**的覆盖校验用（「地图页有没有漏列某顶层项」）。

    排除两类，否则门禁会假红：
      ① `_index.md` —— 地图页自身（自引用）；
      ② **点开头的项** —— `.git` / `.obsidian` / `.trash` 等工具与仓库基础设施，
         不是「内容」。（历史注：2026-09-21 曾在 `vault/Memory` 内建独立本地 git 仓，
         多出的 `.git` 与 `.gitignore` 让 `--check` 报「地图页漏列」；该仓同日已删。）
    """
    return sorted(
        p.name for p in d.iterdir()
        if p.name != "_index.md" and not p.name.startswith(".")
    )


def check_top_level(idx: Path, items: list[str], label: str, problems: list[str]) -> None:
    if not idx.exists():
        problems.append(f"[缺地图页] {idx.relative_to(REPO)}")
        return
    text = read_text(idx)
    missing = [x for x in items if x not in text]
    if missing:
        problems.append(
            f"[地图页漏列] {idx.relative_to(REPO)} :: {label} 未提及 → {', '.join(missing)}"
        )


# ---- 同名消歧「单一正本 + 指针有效性」（§6 门禁 ⑤）----
# 旧形态是两份手工表互称「逐字一致」，无派生关系，靠人记得同步，实测已漂过。
# 现行：完整五组表唯一正本 = 工作区根 `AGENTS.md` §同名文件消歧；`Memory/_index.md` §六 只留指针。
# 失明即红：正本 / 索引缺文件、标题改名或重复、表结构畸形、五组缺行或重复、
# 指针缺失 / 路径错 / 节名错 / 落在别节，一律报红。判据只认真 Markdown 内容。
DISAMBIG_CANON = VAULT / "AGENTS.md"
DISAMBIG_INDEX = MEM / "_index.md"
DISAMBIG_HEAD_KEY = "同名文件消歧"
DISAMBIG_CANON_TITLE = "同名文件消歧（易混清单）"
DISAMBIG_GROUPS = ["AGENTS.md", "Inbox/", "Archive/", "Templates/", "Projects/"]
DISAMBIG_COLS = 3
_SEP_CELL = re.compile(r"^:?-{3,}:?$")
_BACKTICK = re.compile(r"`([^`\n]+)`")
_SECTION_REF = re.compile(
    r"§\s*" + re.escape(DISAMBIG_HEAD_KEY) + r"(?![\w一-鿿])"
)


def _norm_slashes(s: str) -> str:
    """把反斜杠归一成正斜杠——路径比较用。"""
    return s.replace("\\", "/")


def _visible_lines(text: str) -> list[str]:
    """按行返回**可见内容**：代码围栏内与 HTML 注释内的内容置空串（行数与下标不变）。"""
    out: list[str] = []
    fence_char = ""
    fence_len = 0
    in_comment = False
    for raw in text.splitlines():
        line = raw
        if fence_char:
            out.append("")
            close = re.match(r"^ {0,3}(`{3,}|~{3,})\s*$", line)
            if close:
                marker = close.group(1)
                if marker[0] == fence_char and len(marker) >= fence_len:
                    fence_char = ""
                    fence_len = 0
            continue
        while True:
            if in_comment:
                end = line.find("-->")
                if end < 0:
                    line = ""
                    break
                line = line[end + 3:]
                in_comment = False
                continue
            start = line.find("<!--")
            if start < 0:
                break
            end = line.find("-->", start + 4)
            if end < 0:
                line = line[:start]
                in_comment = True
                break
            line = line[:start] + line[end + 3:]
        opened = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if opened:
            marker = opened.group(1)
            if marker[0] != "`" or "`" not in opened.group(2):
                fence_char = marker[0]
                fence_len = len(marker)
            out.append("")
            continue
        out.append(line)
    return out


def _md_section_hits(lines: list[str], key: str) -> list[int]:
    return [i for i, ln in enumerate(lines) if ln.startswith("## ") and key in ln]


def _section_slice(lines: list[str], start: int) -> list[str]:
    j = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    return lines[start + 1:j]


def _md_cells(row: str) -> list[str]:
    s = row.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _check_disambig_canon_table(body: list[str], rel: str, problems: list[str]) -> None:
    """校验正本小节内的消歧表结构：表头 / 分隔行 / 三列 / 五组齐全不重复 / 无空单元格。"""
    runs: list[list[str]] = []
    i = 0
    while i < len(body):
        if not body[i].strip().startswith("|"):
            i += 1
            continue
        start = i
        while i < len(body) and body[i].strip().startswith("|"):
            i += 1
        runs.append(body[start:i])
    if len(runs) != 1:
        problems.append(
            f"[正本表畸形] {rel} :: 正本小节内找到 {len(runs)} 段表格（应为 1 段连续表）"
        )
        return
    rows = [ln.strip() for ln in runs[0]]
    if len(rows) < 3:
        problems.append(
            f"[正本表畸形] {rel} :: 正本小节内只取到 {len(rows)} 行连续表格"
            "（需 ≥ 表头 + 分隔行 + 数据行）"
        )
        return
    bad = False
    header = _md_cells(rows[0])
    if len(header) != DISAMBIG_COLS or any(not c for c in header):
        problems.append(f"[正本表畸形] {rel} :: 表头不是 {DISAMBIG_COLS} 列非空格：{rows[0]}")
        bad = True
    sep = _md_cells(rows[1])
    if len(sep) != DISAMBIG_COLS or not all(_SEP_CELL.match(c) for c in sep):
        problems.append(f"[正本表畸形] {rel} :: 分隔行不是 {DISAMBIG_COLS} 格 `---`：{rows[1]}")
        bad = True
    keys: list[str] = []
    for n, r in enumerate(rows[2:], start=3):
        cells = _md_cells(r)
        if len(cells) != DISAMBIG_COLS:
            problems.append(f"[正本表畸形] {rel} :: 第 {n} 行不是 {DISAMBIG_COLS} 列：{r}")
            bad = True
            continue
        if any(not c for c in cells):
            problems.append(f"[正本表空格] {rel} :: 第 {n} 行有空格 / 空单元格：{r}")
            bad = True
            continue
        keys.append(cells[0].strip("`").strip())
    if bad:
        return
    missing = [g for g in DISAMBIG_GROUPS if g not in keys]
    dup = sorted({g for g in keys if keys.count(g) > 1})
    unknown = [k for k in keys if k not in DISAMBIG_GROUPS]
    if missing or dup or unknown or len(keys) != len(DISAMBIG_GROUPS):
        problems.append(
            f"[正本表五组不守恒] {rel} :: 结构契约 = {DISAMBIG_GROUPS}；"
            f"缺行 {missing or '无'}｜重复 {dup or '无'}｜表外组名 {unknown or '无'}｜数据行 {len(keys)} 条"
        )


def _check_disambig_index_pointer(text: str, rel: str, canon: Path,
                                  problems: list[str]) -> None:
    """校验索引侧只剩**指针**：§六 唯一在场、无第二份表、指针给对路径与节名且落在 §六 内。"""
    lines = _visible_lines(text)
    hits = _md_section_hits(lines, DISAMBIG_HEAD_KEY)
    if len(hits) != 1:
        problems.append(
            f"[索引消歧节失明] {rel} :: 标题含「{DISAMBIG_HEAD_KEY}」的小节命中 {len(hits)} 次（应为 1）"
            "——改名 / 删除 / 重复 / 只写进围栏·注释都算"
        )
        return
    body = _section_slice(lines, hits[0])
    table_lines = [ln for ln in body if ln.strip().startswith("|")]
    if table_lines:
        problems.append(
            f"[索引侧第二份正本] {rel} :: §六 小节内又出现 {len(table_lines)} 行表格"
            "——完整表只允许在工作区根正本一处，副本一律判失效"
        )

    def _same_path(tok: str) -> bool:
        tok = _norm_slashes(tok).strip()
        if not tok:
            return False
        try:
            p = Path(tok)
            if not p.is_absolute():
                p = (DISAMBIG_INDEX.parent / p)
            return p.resolve() == canon.resolve()
        except (OSError, ValueError):
            return False

    def _path_only(ln: str) -> bool:
        return any(_same_path(m.group(1)) for m in _BACKTICK.finditer(ln))

    def _is_pointer(ln: str) -> bool:
        for m in _BACKTICK.finditer(ln):
            if not _same_path(m.group(1)):
                continue
            if _SECTION_REF.match(ln[m.end():].lstrip()):
                return True
        return False

    if any(_is_pointer(ln) for ln in body):
        return
    if any(_is_pointer(ln) for ln in lines):
        problems.append(
            f"[索引指针落别节] {rel} :: 指向正本的读取指令不在 §六 小节内——等于 §六 没给指令"
        )
    elif any(_path_only(ln) for ln in body):
        problems.append(
            f"[索引指针错误节] {rel} :: §六 有正本路径却没有节名「{DISAMBIG_HEAD_KEY}」——指针指错小节"
        )
    elif _SECTION_REF.search("\n".join(body)):
        problems.append(
            f"[索引指针错误路径] {rel} :: §六 有节名却没有正本路径「{canon}」——指针指错文件"
        )
    else:
        problems.append(
            f"[索引指针缺失] {rel} :: §六 小节内找不到指向正本「{canon}」§{DISAMBIG_HEAD_KEY} 的读取指令"
        )


def check_disambig_single_source(problems: list[str], canon: Path | None = None,
                                 index: Path | None = None) -> None:
    """门禁 ⑤：同名消歧表「单一正本 + 指针有效性」。"""
    canon = canon or DISAMBIG_CANON
    index = index or DISAMBIG_INDEX
    before = len(problems)

    def _r(p: Path) -> str:
        try:
            return str(p.relative_to(REPO))
        except ValueError:
            return str(p)

    if not canon.exists():
        problems.append(f"[消歧正本缺文件] {_r(canon)} —— 五组消歧表的唯一正本不在位")
        return
    canon_lines = _visible_lines(read_text(canon))
    hits = _md_section_hits(canon_lines, DISAMBIG_HEAD_KEY)
    if len(hits) != 1:
        problems.append(
            f"[消歧正本标题失明] {_r(canon)} :: 标题含「{DISAMBIG_HEAD_KEY}」的小节命中 {len(hits)} 次（应为 1）"
        )
        return
    title = canon_lines[hits[0]].strip()
    if title != "## " + DISAMBIG_CANON_TITLE:
        problems.append(
            f"[消歧正本标题失明] {_r(canon)} :: 正本小节标题须逐字等于 `## {DISAMBIG_CANON_TITLE}`，实为 `{title}`"
        )
        return
    _check_disambig_canon_table(_section_slice(canon_lines, hits[0]), _r(canon), problems)

    if not index.exists():
        problems.append(f"[消歧索引缺文件] {_r(index)} —— 记忆库唯一入口页不在位")
        return
    _check_disambig_index_pointer(read_text(index), _r(index), canon, problems)
    if len(problems) == before:
        print(f"[消歧单一正本] 正本表 + 索引指针在位（{_r(index)} → {_r(canon)} §{DISAMBIG_HEAD_KEY}）")


# ---- 「读时时效」节在场校验（门禁 ① 的覆盖面）----
# 为什么落点是 `Memory/_index.md` 而不是 `rule/`：钩子命令「先读 _index.md，再按路径读原文」把本页放在
# **读取路径**上，而 `rule/` 四节按库规只在写入 / 收尾时被读——时效协议写进 rule 等于装进读者不会打开的抽屉。
# 失明即红：标题改名 / 小节删除 / 重复出现 / 判据指针被抽走，一律判违规，**抽不到绝不视为通过**。
READTIME_HEAD_KEY = "读时时效"
READTIME_POINTER = "批量改写脚本的自检失明"


def check_readtime_protocol(problems: list[str], idx: Path | None = None) -> None:
    idx = idx or (MEM / "_index.md")
    rel = str(idx.relative_to(REPO)) if idx.is_relative_to(REPO) else str(idx)
    if not idx.exists():
        problems.append(f"[读时时效缺文件] {rel}")
        return
    lines = read_text(idx).splitlines()
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ") and READTIME_HEAD_KEY in ln]
    if len(heads) != 1:
        problems.append(
            f"[读时时效节失明] {rel} :: 标题含「{READTIME_HEAD_KEY}」的小节命中 {len(heads)} 次（应为 1）"
            "——改名 / 删除 / 重复都算，本节在读取路径上，不视为通过"
        )
        return
    j = next((k for k in range(heads[0] + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    if READTIME_POINTER not in "\n".join(lines[heads[0]:j]):
        problems.append(
            f"[读时时效缺判据指针] {rel} :: 小节内找不到「{READTIME_POINTER}」"
            "（判据正本在那篇 Lesson，本节只指路不复述）"
        )
        return
    print(f"[读时时效] {rel} 小节在场、判据指针在位")


def check_decisions_anchors(problems: list[str], d: Path | None = None) -> None:
    """Decisions/_index.md 是人工散文行索引，永不生成；机器只查锚点双向守恒。"""
    d = d or (MEM / DEC_LAYER)
    idx = d / "_index.md"
    rel = str(idx.relative_to(REPO)) if idx.is_relative_to(REPO) else str(idx)
    if not idx.exists():
        problems.append(f"[决策索引缺文件] {rel} —— 决策层的唯一入口页不在位")
        return
    text = read_text(idx)
    files = {p.stem for p in sorted(d.glob("*.md")) if p.name not in ("_index.md", "README.md")}
    anchors = set(DEC_ANCHOR.findall(text))
    missing = sorted(files - anchors)
    orphan = sorted(anchors - files)
    for f in missing:
        problems.append(
            f"[决策卡无索引锚] {DEC_LAYER}/{f}.md :: {rel} 内没有 [[Decisions/{f}]]"
            "—— 新增决策卡必须同日补行（页脚约定），改名同理"
        )
    for a in orphan:
        problems.append(
            f"[决策索引锚指向不存在的文件] {rel} :: [[Decisions/{a}]]"
            "—— 删卡 / 改名后索引行没跟着改"
        )
    state = "双向守恒" if not (missing or orphan) else "缺口 %d · 孤儿 %d" % (len(missing), len(orphan))
    print(f"[决策锚点] {len(files)} 卡 / {len(anchors)} 锚：{state}")


def real_layers(refresh_cells: bool = False) -> list[tuple[str, list[tuple[str, str, str, str]]]]:
    out = []
    for layer in LAYERS:
        d = MEM / layer
        if not d.is_dir():
            continue
        exist = load_existing(d / "_index.md")
        rows = []
        for p in sorted(d.glob("*.md")):
            if p.name in ("_index.md", "README.md"):
                continue
            key = f"{layer}/{p.name}"
            rows.append((key, *keep_or_auto(exist, key, note_meta(p), refresh_cells)))
        rows.sort(key=lambda r: r[0].lower())
        out.append((layer, rows))

    d = MEM / PROJECTS
    if d.is_dir():
        exist = load_existing(d / "_index.md")
        rows = []
        for sub in sorted(x for x in d.iterdir() if x.is_dir()):
            key = f"{PROJECTS}/{sub.name}/"
            rows.append((key, *keep_or_auto(exist, key, project_meta(sub), refresh_cells)))
        rows.sort(key=lambda r: r[0].lower())
        out.append((PROJECTS, rows))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="记忆库索引生成/校验")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true", help="生成/更新各层 _index.md")
    g.add_argument("--check", action="store_true", help="体检：报告漂移，非 0 退出")
    ap.add_argument("--layer", help="只处理某一层（生成面：Preferences/Plans/Lessons/Workflows/Projects；"
                                    "Decisions 只可 --check，其索引行由人写、永不生成）")
    ap.add_argument("--refresh-cells", action="store_true",
                    help="--write 时连人工「一句话定位 / 关键词」也按实盘重算（默认保留人工润色）")
    args = ap.parse_args()

    if not MEM.is_dir():
        print(f"!! 记忆库不存在：{MEM}", file=sys.stderr)
        return 2

    problems: list[str] = []
    layers = real_layers(args.refresh_cells)
    if args.layer:
        if args.layer.lower() == DEC_LAYER.lower():
            if args.write:
                print(f"!! {DEC_LAYER}/_index.md 是手工索引，不进生成面（体检请用 --check --layer {DEC_LAYER}）",
                      file=sys.stderr)
                return 2
            layers = []
        else:
            layers = [x for x in layers if x[0].lower() == args.layer.lower()]
            if not layers:
                print(f"!! 未知层：{args.layer}", file=sys.stderr)
                return 2

    mode = "体检" if args.check else "生成"
    print(f"== 记忆库索引 {mode} == {MEM}")

    total = 0
    col_rows = 0
    for layer, rows in layers:
        total += len(rows)
        idx = MEM / layer / "_index.md"
        title = {"Projects": "Projects 项目索引"}.get(layer, f"{layer} 索引")
        content = render(idx, title, layer.lower(), rows)
        print(f"[{layer}] {len(rows)} 条")
        col_rows += write_or_check(idx, content, args.check, problems, note_mtimes(layer))

    if args.check and layers:
        stale = sum(1 for p in problems if p.startswith("[索引更新列滞旧]"))
        print("[更新列] %d 行：%s" % (col_rows, "一致" if not stale else f"滞旧 {stale} 处"))

    # 手工地图页的顶层覆盖（排除地图页自身与点开头的工具/仓库基础设施，见 top_entries）
    if (VAULT / "_index.md").is_file():
        check_top_level(VAULT / "_index.md", top_entries(VAULT), "vault 顶层", problems)
    check_top_level(MEM / "_index.md", top_entries(MEM), "Memory 顶层", problems)
    check_disambig_single_source(problems)
    check_readtime_protocol(problems)
    if not args.layer or args.layer.lower() == DEC_LAYER.lower():
        check_decisions_anchors(problems)

    print(f"-- 共 {total} 条；手工地图页校验完成")
    if args.check:
        if problems:
            print(f"\n!! 发现 {len(problems)} 处漂移：")
            for p in problems:
                print("   " + p)
            return 1
        print("OK：无漂移。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
