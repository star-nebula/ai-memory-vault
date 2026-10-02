#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
encoding_guard.py —— 文本文件编码守卫 / 批量转码为 UTF-8

背景（本机已复现的坑）：
  本项目多数工具覆写「已存在」的文件时会**沿用该文件原有编码**。
  即：一个原本以 GBK 落盘的中文 md，用编辑器/工具改完内容后仍然是 GBK。
  Obsidian / VitePress 按 UTF-8 读 → 整篇乱码。新建文件则默认 UTF-8，不受影响。

用途：
  1) 体检：扫描目录，列出所有非 UTF-8 文本文件（退出码 1，便于挂到流程里当门禁）。
  2) 修复：--fix 把 GBK/GB18030 文本原地转成 UTF-8（无 BOM），可选备份。
  3) 裸控制符门（2026-09-29 增）：同一次扫描里顺带查 `\a \b \f \r \v` 被当转义吃掉后留下的
     控制符（含「不构成 CRLF 的裸 CR」，以及吞字形态的 `\t`）。**只报告不自动改**——被吞掉的是原文那个字母，
     须按实盘验证补回。**只有权威面（`vault/Memory`）参与拦门禁**，其余面（抓取素材、
     素材库、临时产物）只报告；否则一处清不掉的存量就把门变成恒红。

用法：
  python encoding_guard.py <路径>                      # 只体检
  python encoding_guard.py <路径> --fix                # 体检并转码
  python encoding_guard.py <路径> --fix --backup       # 转码前存 .bak
  python encoding_guard.py <路径> --ext .md,.txt,.html # 自定义扩展名
  python encoding_guard.py <路径> --fix --dry-run      # 只打印将要做的事
  python encoding_guard.py <路径> --no-ctrl            # 跳过裸控制符段（超大树快扫）

说明：
  - 只处理文本类扩展名（默认见 TEXT_EXTS），二进制一律跳过。
  - 自动跳过 .git / node_modules / .obsidian / $RECYCLE.BIN 等目录。
  - 「未知编码」（UTF-8、GBK 都解不开）的文件一律只报告、不动。
  - 转码是 GBK -> UTF-8 的字节级重编码，不做任何换行符转换。
"""

import argparse
import codecs
import os
import shutil
import sys

# 本机控制台默认 GBK，报告含中文/符号时不重配编码会乱码或 UnicodeEncodeError 中断体检。
for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

DEFAULT_EXTS = [".md", ".txt", ".html", ".htm", ".json", ".yml", ".yaml",
                ".csv", ".ts", ".js", ".py", ".css", ".xml"]

SKIP_DIRS = {".git", "node_modules", ".obsidian", "$RECYCLE.BIN",
             ".vitepress", "dist", ".venv", "venv", "__pycache__",
             ".idea", ".vscode", ".trash", "_archive_backup"}

# 先 UTF-8、再 GBK：这台的乱码源基本都是 GBK
CANDIDATES = ["utf-8", "gbk", "gb18030"]


# —— 裸控制符门（2026-09-29 增）——
# 缺陷类：AI 把路径/标识符里的 `\a \b \f \r \v` 当转义吃掉，正文字符被替换成控制符本身。
# 判定 = C0 控制符 + DEL(0x7F) + **不构成 CRLF 的裸 CR**
#       （本库多数 md 是 CRLF，`\r` 型塌陷混在合法行尾里，只看非 CRLF 的 CR 才不误报）。
#       TAB 单独放判据：缩进与行尾对齐是合法用法，只有「正文之后紧跟字母」的吞字形态才算违规。
# 只报告不自动改：被吞掉的是**原文的那个字母**，脚本无从推断，必须人工/按实盘验证补回。
CTRL_EXTS = {".md", ".txt", ".json", ".yml", ".yaml", ".csv",
             ".html", ".htm", ".ts", ".js", ".py", ".css", ".xml"}
# 权威面 = 违规拦门禁；其他面只报告 —— 恒红的门禁等于没有门禁，按「可清零的面」划界。
# 通用化版默认把路径含 `Memory` 的文件当权威面：直接把记忆库路径传作扫描根，整面即权威面。
GATE_MARKS = ["Memory"]
# 非权威面全库扫会有上万处，逐条打印等于没有报告；只列前若干个文件，总数在结尾给。
REPORT_MAX = 20

CTRL_NAMES = {0: "NUL", 7: "BEL(\\a)", 8: "BS(\\b)", 9: "TAB(\\t)", 11: "VT(\\v)",
              12: "FF(\\f)", 13: "CR(裸 \\r)", 27: "ESC", 127: "DEL"}


def _visible(s: str) -> str:
    """把控制符渲染成可见标记，便于报告里直接看出「哪个字母被吞了」。"""
    return "".join(("<%s>" % CTRL_NAMES.get(ord(c), "U+%04X" % ord(c)).split("(")[0])
                   if (ord(c) < 32 and c != "\n") or ord(c) == 127 else c for c in s)


def _tab_is_corrupt(text: str, i: int) -> bool:
    """TAB 只在「吞字」形态下算违规：同行前面已有正文，且紧跟字母/数字（`\t` 吃掉了词首字母）。
    缩进 TAB、行尾对齐 TAB（后面跟空白或行尾）都不算——否则库里的代码块会把门刷成恒红。"""
    start = text.rfind("\n", 0, i) + 1
    return text[start:i].strip() != "" and text[i + 1:i + 2].isalnum()


def find_ctrl(text: str, crlf: bool):
    """返回 [(行, 列, 码点, 名称, 该行可见片段)]。列按「距上一个换行的偏移」计。"""
    out = []
    for i, ch in enumerate(text):
        o = ord(ch)
        if o == 10:
            continue
        if ch == "\r" and crlf and text[i + 1:i + 2] == "\n":
            continue
        if o == 9 and not _tab_is_corrupt(text, i):
            continue
        if o < 32 or o == 127:
            start = text.rfind("\n", 0, i) + 1
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            out.append((text.count("\n", 0, i) + 1, i - start + 1, o,
                        CTRL_NAMES.get(o, "U+%04X" % o), _visible(text[start:end])[:90]))
    return out


def under_gate(path: str) -> bool:
    n = path.replace("\\", "/")
    return any(m in n for m in GATE_MARKS)


def sniff(raw: bytes):
    """返回 (编码名, 是否 unicode 可读)。unreadable 表示 UTF-8/GBK 都解不开。"""
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-bom", True
    for enc in CANDIDATES:
        try:
            raw.decode(enc)
            return enc, True
        except Exception:
            continue
    return "unknown", False


def iter_files(root: str, exts):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in exts:
                yield os.path.join(dirpath, fn)


def main():
    ap = argparse.ArgumentParser(description="扫描 / 修复非 UTF-8 文本文件")
    ap.add_argument("path", help="要扫描的文件或目录")
    ap.add_argument("--fix", action="store_true", help="把 GBK 系列转成 UTF-8")
    ap.add_argument("--backup", action="store_true", help="转码前生成同目录 .bak")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不落盘")
    ap.add_argument("--ext", default="", help="逗号分隔扩展名，覆盖默认（如 .md,.txt）")
    ap.add_argument("--no-ctrl", action="store_true", help="跳过裸控制符段（超大目录树快扫）")
    args = ap.parse_args()

    exts = {e.strip().lower() for e in args.ext.split(",") if e.strip()} or set(DEFAULT_EXTS)
    for e in list(exts):
        if not e.startswith("."):
            exts.add("." + e)
            exts.discard(e)

    root = os.path.abspath(args.path)
    if not os.path.exists(root):
        print("[ERR] 路径不存在: %s" % root)
        return 2

    total = 0
    bad = []
    ctrl_hits = []  # [(文件, [(行, 列, 码点, 名称)])]
    for p in iter_files(root, exts):
        total += 1
        try:
            raw = open(p, "rb").read()
        except Exception as ex:
            bad.append((p, "read-error", str(ex)))
            continue
        enc, ok = sniff(raw)
        if not ok:
            bad.append((p, "unknown", "UTF-8 与 GBK 均无法解码"))
        elif enc != "utf-8":
            bad.append((p, enc, "%d bytes" % len(raw)))
        # 裸控制符段：只扫已是 UTF-8 的文件（GBK 那些本轮先转码，转完再查，避免同一文件双重报）
        if not args.no_ctrl and enc in ("utf-8", "utf-8-bom") \
                and os.path.splitext(p)[1].lower() in CTRL_EXTS:
            try:
                text = raw.decode("utf-8-sig")
            except Exception:
                text = None
            if text:
                got = find_ctrl(text, b"\r\n" in raw)
                if got:
                    ctrl_hits.append((p, got))

    is_utf8 = [b for b in bad if b[1] not in ("unknown", "read-error")]
    others = [b for b in bad if b[1] in ("unknown", "read-error")]

    gate_v = sum(len(h) for p, h in ctrl_hits if under_gate(p))
    report_only = sum(len(h) for p, h in ctrl_hits if not under_gate(p))

    print("扫描根目录 : %s" % root)
    print("文本文件数 : %d" % total)
    print("全程 UTF-8 : %d" % (total - len(bad)))
    print("需要处理   : %d（编码类 %d / 裸控制符 权威面 %d 处、非权威面 %d 处仅报告）"
          % (len(bad) + gate_v, len(bad), gate_v, report_only))
    print()

    if bad:
        print("%-14s %s" % ("编码", "文件"))
        print("-" * 72)
        for p, enc, info in bad:
            print("%-14s %s   (%s)" % (enc, p, info))
        print()

    if ctrl_hits:
        print("—— 裸控制符（\\a \\b \\f \\r \\t \\v 被当转义吃掉的残留；被吞的原文字符以 <名> 显示）——")
        print("%-6s %s" % ("拦/报", "文件 · 位置 · 行片段"))
        print("-" * 72)
        report_files = 0
        for p, got in sorted(ctrl_hits, key=lambda x: (not under_gate(x[0]), x[0])):
            if under_gate(p):
                print("[拦]  %s" % p)
                for line, col, code, name, snip in got:
                    print("        L%-4d 第 %d 列  %-12s %s" % (line, col, name, snip))
                continue
            report_files += 1
            if report_files <= REPORT_MAX:
                kinds = "/".join(sorted({g[3].split("(")[0] for g in got}))
                print("[报]  %s  %d 处（%s）" % (p, len(got), kinds))
        if report_files > REPORT_MAX:
            print("[报]  …其余 %d 个文件未列出（判据不筛面，全量计数见下行）"
                  % (report_files - REPORT_MAX))
        print()

    fixed = 0
    for p, enc, info in is_utf8:
        if enc == "utf-8-bom":
            direction = "GBK"
        else:
            direction = "GBK"
        target = "移除 BOM -> 纯 UTF-8" if enc == "utf-8-bom" else "%s -> UTF-8" % enc.upper()
        print("[%s] %s" % ("DRY " if (args.dry_run or not args.fix) else "FIX ", p))
        print("       %s" % target)
        if args.dry_run or not args.fix:
            continue
        raw = open(p, "rb").read()
        if enc == "utf-8-bom":
            text = raw.decode("utf-8-sig")
        else:
            text = raw.decode(enc)
        if args.backup:
            shutil.copy2(p, p + ".bak")
        with open(p, "wb") as f:
            f.write(text.encode("utf-8"))
        after = sniff(open(p, "rb").read())[0]
        print("       落盘编码 = %s  %s" % (after, "OK" if after == "utf-8" else "!! 异常"))
        fixed += 1

    for p, enc, info in others:
        print("[SKIP] %s  (%s)" % (p, info))

    print()
    if args.fix and not args.dry_run:
        print("完成：转码 %d 个文件。" % fixed)
        if others:
            print("仍有 %d 个文件无法自动处理，需人工确认。" % len(others))
        if gate_v:
            print("转码已完成，但权威面另有 %d 处裸控制符**不自动改**（被吞的是原文字母），见上一段。" % gate_v)
        # 修复成功后返回 0，便于串到流程里
        return 1 if (others or gate_v) else 0
    if bad:
        print("提示：加 --fix 可自动把 GBK 转成 UTF-8（建议先加 --backup）。")
        return 1
    if gate_v:
        print("[gate] 权威面裸控制符违规 %d 处 —— 逐处以实盘（文件是否存在、代码里的标识符）核对原意后手工补回；"
              "非权威面 %d 处只报告（抓取素材类清不动，纳入拦截会把门变成恒红）。" % (gate_v, report_only))
        return 1
    if report_only:
        print("[note] 非权威面裸控制符 %d 处，仅报告不拦（判据见脚本头 GATE_MARKS 注释）。" % report_only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
