# -*- coding: utf-8 -*-
r"""
sync_memory_instructions.py — 记忆库自定义指令「单一真源」同步器（通用化版）

唯一可编辑来源（真源）：
    <记忆库根>\Workflows\AI工具自定义指令-完整版.md      —— 纯指令正文，无 frontmatter
    <记忆库根>\Workflows\AI工具自定义指令.md             —— 分发手册；§二「最小版」代码块是
                                                            项目级钩子的正文来源（运行时抽取，不另存副本）

本脚本读真源，派生部署到各 AI 工具的用户级指令位（避免人手逐份抄写导致漂移）：
    · kind=file：优先软链到真源；软链不可用（部分 Windows 环境无特权）则退化为复制（先备份原文件）
    · kind=json-inject：把真源正文注入某个 JSON 配置的指定键（WorkBuddy 的 customPrompt 形态）

另可部署**项目级钩子**（--projects）：
    在 <代码项目根> 下按目录名匹配 `Memory\Projects\<项目名>\` 对应的代码仓，在其根写一份
    AGENTS.md，内容 = 手册 §二 最小版 + **填好的真项目名**。
    动机：用户级钩子里「当前项目名：<项目名>」是字面占位符、从不被替换；项目级钩子是全链路
    唯一把项目名填成真值的一处。
    安全：已存在非本脚本生成的 AGENTS.md 一律不覆盖（报 [KEEP]）；无唯一代码根不猜路径（报 [NOROOT]）。

用法：
    python sync_memory_instructions.py                  # 部署用户级各处（幂等可重跑）
    python sync_memory_instructions.py --check          # 只读比对（各部署位 + 项目级钩子），漂移退出码 1
    python sync_memory_instructions.py --projects       # 部署项目级钩子（只新建，不覆盖）
    python sync_memory_instructions.py --projects --check   # 只报告项目级钩子状态

记忆库定位：环境变量 AI_MEMORY_DIR，或从当前目录向上探测 <根>/Memory。
工具位配置：见下方 TARGETS —— 接入时按你实际安装的工具增删。

真源卫生门：真源含 0x00-0x08 / 0x0B / 0x0C / 0x0E-0x1F 等裸控制符时拒绝部署——
真源里 `\v` 被当转义吃掉会落成裸 0x0B，部署出去的指针变成不可解析的 `ruleibe-coding.md`
（真实事故：坏指针在各工具存活约 7 天无人发现，因为部署链此前只有部署没有校验）。
"""
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ===========================================================================
# 配置区（接入时改这里；路径支持 ~ 展开）
# ===========================================================================

# 各 AI 工具的用户级指令位。**默认不配置任何目标**——clone 后直接跑不会碰你的工具位；
# 要启用分发时，按你实际安装的工具解开注释（路径支持 ~ 展开），不用的删掉。
TARGETS = [
    # {"label": "ZCode",       "kind": "file", "path": "~/.zcode/AGENTS.md"},
    # {"label": "Codex CLI",   "kind": "file", "path": "~/.codex/AGENTS.md"},
    # {"label": "Claude Code", "kind": "file", "path": "~/.claude/CLAUDE.md"},
    # {"label": "Qoder",       "kind": "file", "path": "~/.qoder/AGENTS.md"},
    # {"label": "Trae",        "kind": "file", "path": "~/.trae-cn/user_rules/rule-memory-library.md"},
    # kind=json-inject：把真源正文写进 JSON 配置的指定键（改完需重启该工具才生效）
    # {"label": "WorkBuddy", "kind": "json-inject", "path": "~/.workbuddy/app/app-config.json",
    #  "keys": ["personalization", "customPrompt"],
    #  "restart_hint": "必须重启 WorkBuddy 生效；重启前勿在「设置→个性化」点保存，否则内存旧值覆盖回旧版"},
]

# 项目级钩子（--projects）：代码项目根目录。也可用环境变量 AI_PROJECT_ROOT 覆盖。
# 可选功能：留空则 --projects 直接跳过并提示，不影响用户级部署。
CODE_ROOT = os.environ.get("AI_PROJECT_ROOT", "")
HOOK_NAME = "AGENTS.md"

# 项目根扫描的噪声目录与深度窗（`<根>\<组>\<项目>` 深度 2~3；分组目录会被深度门挡掉）
DIR_SKIP = {
    ".git", ".github", ".qoder", ".trae", ".trae-cn", ".agent", ".workbuddy", ".claude",
    "node_modules", "__pycache__", ".venv", "venv", "dist", "build", "out",
    "snapshots", "vendor", "docs", "doc", "packages", "scripts", "website", "ui",
    "test", "tests", "extensions", "data", "backup", "_out", "Archive",
}
MAX_DEPTH = 3
MIN_DEPTH = 2

ALLOWED_CTRL = (0x09, 0x0A, 0x0D)

# ===========================================================================
# 以下为实现，通常无需改动
# ===========================================================================


def _find_memory_dir() -> Path:
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


MEMORY_ROOT = _find_memory_dir()
CANON = MEMORY_ROOT / "Workflows" / "AI工具自定义指令-完整版.md"
MANUAL = MEMORY_ROOT / "Workflows" / "AI工具自定义指令.md"
MEMORY_PROJECTS = MEMORY_ROOT / "Projects"
BAK_DIR = MEMORY_ROOT.parent / "backup"


def bad_ctrl(text):
    """返回裸控制符列表 [(偏移, 码位)]——真源里出现即视为转义事故。"""
    return [(i, "0x%02x" % ord(c))
            for i, c in enumerate(text) if ord(c) < 0x20 and ord(c) not in ALLOWED_CTRL]


try:
    # 控制台默认 GBK，遇 ⚠ 等字符会 UnicodeEncodeError 把部署中途打断（半部署事故的根因之一）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(msg):
    print(msg)


def backup_file(path):
    os.makedirs(BAK_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.basename(path)
    bak = os.path.join(BAK_DIR, "%s.sync-bak-%s" % (base, stamp))
    shutil.copyfile(path, bak)
    return bak


def deploy_json_inject(target, keys, restart_hint, canon_text):
    if not os.path.exists(target):
        log("[SKIP] %s: 配置文件不存在" % target)
        return
    bak = backup_file(target)
    raw = io.open(target, encoding="utf-8").read()
    data = json.loads(raw)  # 校验 JSON 合法
    node = data
    for k in keys[:-1]:
        node = node.setdefault(k, {})
    node[keys[-1]] = canon_text
    io.open(target, "w", encoding="utf-8", newline="").write(
        json.dumps(data, ensure_ascii=False, indent=2)
    )
    log("[OK]   %s: 已注入 %s（备份 %s）" % (label_of(target), ".".join(keys), os.path.basename(bak)))
    if restart_hint:
        log("        ⚠ %s" % restart_hint)


def label_of(target):
    for t in TARGETS:
        if os.path.normpath(os.path.expanduser(t["path"])) == os.path.normpath(target):
            return t["label"]
    return target


def deploy_file_based(target, label, canon_text):
    parent = os.path.dirname(target)
    if not os.path.isdir(parent):
        log("[SKIP] %s: 目录不存在（工具未安装），跳过" % label)
        return
    # 移除旧文件 / 失效软链（真文件先备份）
    if os.path.islink(target):
        try:
            os.remove(target)
        except OSError:
            pass
    elif os.path.exists(target):
        backup_file(target)
        try:
            os.remove(target)
        except OSError:
            pass
    method = None
    # 先试软链，再验证确实能读回真源内容；失败则退化为复制
    try:
        os.symlink(CANON, target)
        with io.open(target, encoding="utf-8") as f:
            if f.read().strip() == canon_text:
                method = "软链"
            else:
                raise OSError("软链未能正确解析到真源内容")
    except OSError:
        try:
            os.remove(target)
        except OSError:
            pass
        shutil.copyfile(CANON, target)
        method = "复制"
    if method == "软链":
        log("[OK]   %s: 软链 → %s" % (label, CANON))
    else:
        log("[OK]   %s: 软链不可用，已复制 → %s" % (label, target))


def read_current_file(target):
    """(状态, 内容) —— 父目录不存在=未安装；文件不存在=未部署。"""
    if not os.path.isdir(os.path.dirname(target)):
        return "no-dir", None
    if not os.path.exists(target):
        return "missing", None
    return "ok", io.open(target, encoding="utf-8", errors="replace").read().strip()


def read_current_json_inject(target, keys):
    if not os.path.exists(target):
        return "no-dir", None
    try:
        data = json.loads(io.open(target, encoding="utf-8").read())
    except ValueError:
        return "ok", None
    node = data
    try:
        for k in keys:
            node = node[k]
    except (KeyError, TypeError):
        return "ok", None
    return "ok", node


def iter_targets():
    for t in TARGETS:
        yield t, os.path.normpath(os.path.expanduser(t["path"]))


def check(text):
    log("=== 校验：真源 vs 各部署位（只读，不写）===")
    log("真源: %s (%d 字符)" % (CANON, len(text)))
    ctrl = bad_ctrl(text)
    if ctrl:
        log("[FATAL] 真源含裸控制符 %s —— 多半是 `\\v`/`\\f` 被当转义吃掉，先修真源" % ctrl)
        return 1
    log("[OK]   真源无裸控制符")
    if not TARGETS:
        log("[SKIP] 未配置部署目标（TARGETS 为空）——已做真源体检，跳过逐位比对")
        return 0
    drift = []
    for t, target in iter_targets():
        if t["kind"] == "json-inject":
            state, cur = read_current_json_inject(target, t["keys"])
        else:
            state, cur = read_current_file(target)
        if state == "no-dir":
            log("[SKIP] %s: 未安装，不算漂移" % t["label"])
        elif cur is None:
            log("[MISS] %s: 尚未部署" % t["label"])
            drift.append(t["label"])
        elif cur != text:
            bad = bad_ctrl(cur)
            log("[DRIFT] %s: 与真源不一致（线上 %d 字符%s）"
                % (t["label"], len(cur), "，含裸控制符 " + str(bad) if bad else ""))
            drift.append(t["label"])
        else:
            log("[OK]   %s: 与真源逐字一致" % t["label"])
    if drift:
        log("=> 需重跑部署：%s" % ", ".join(drift))
        return 1
    log("=> 全部一致")
    return 0


# --------------------------------------------------------------------------
# 项目级钩子（--projects）
# --------------------------------------------------------------------------

def minimal_body():
    """从手册 §二 抽 ```text 代码块正文——真源在此，脚本不另存副本。"""
    if not os.path.isfile(MANUAL):
        return None
    t = io.open(MANUAL, encoding="utf-8").read()
    m = re.search(r"^##\s*二、最小版\s*$(.*?)^##\s", t, re.M | re.S)
    if not m:
        return None
    blocks = re.findall(r"```[a-zA-Z]*\n(.*?)```", m.group(1), re.S)
    if not blocks:
        return None
    return blocks[0].strip()


def norm_name(s):
    return "".join(c for c in s.lower() if c.isalnum())


def roots_from_overview(name):
    """兜底解析：项目名与仓目录名不一致时，改读该项目 `_overview.md` 里声明的
    <代码项目根> 路径。只接受**唯一且实际存在**的那条——多条就不认，宁缺不猜。"""
    ov = os.path.join(MEMORY_PROJECTS, name, "_overview.md")
    if not os.path.isfile(ov):
        return None
    t = io.open(ov, encoding="utf-8", errors="replace").read()
    needle = CODE_ROOT
    found = []
    i = 0
    stop = set(" \t`|，。；、）)】<>\"'\n\r*")
    while True:
        k = t.find(needle, i)
        if k < 0:
            break
        j = k
        while j < len(t) and t[j] not in stop:
            j += 1
        cand = t[k:j].rstrip("\\.* ")
        i = j
        if os.path.isdir(cand):
            found.append(os.path.normpath(cand))
    uniq = sorted(set(found))
    if len(uniq) != 1:
        return None
    root = uniq[0]
    # 深度门：代码根自身或某个「组」目录被 overview 顺带提到时不能当代码根
    # （钩子写进 CODE_ROOT 会作用于其下全部项目）。
    rel = os.path.relpath(root, CODE_ROOT)
    parts = [p for p in rel.split(os.sep) if p and p != "."]
    if not (MIN_DEPTH <= len(parts) <= MAX_DEPTH):
        return None
    return root


def project_roots():
    """{项目名: 代码根} —— 先按目录名规范化匹配 <代码项目根> 下的实体仓，
    名字不一致的再回落到该项目 `_overview.md` 声明的唯一路径。

    两种途径都要求「唯一」；零命中或多命中都不返回（宁缺不猜：猜错路径会把钩子
    写进别人的仓库，属不可逆的外部副作用）。
    """
    if not os.path.isdir(CODE_ROOT) or not os.path.isdir(MEMORY_PROJECTS):
        return {}, []
    index = {}
    base = os.path.abspath(CODE_ROOT).rstrip("\\")
    base_depth = base.count("\\")
    for dirpath, dirnames, _ in os.walk(CODE_ROOT):
        dirnames[:] = [d for d in dirnames if d not in DIR_SKIP and not d.startswith(".")]
        depth = os.path.abspath(dirpath).rstrip("\\").count("\\") - base_depth
        for d in dirnames:
            if depth + 1 < MIN_DEPTH or depth + 1 > MAX_DEPTH:
                continue
            index.setdefault(norm_name(d), []).append(os.path.join(dirpath, d))
        if depth + 1 >= MAX_DEPTH:
            dirnames[:] = []
    out, unresolved = {}, []
    for name in sorted(os.listdir(MEMORY_PROJECTS)):
        if not os.path.isdir(os.path.join(MEMORY_PROJECTS, name)):
            continue
        hits = index.get(norm_name(name), [])
        if len(hits) == 1:
            out[name] = hits[0]
            continue
        declared = roots_from_overview(name)
        if declared and declared not in out.values():
            out[name] = declared
        else:
            unresolved.append((name, len(hits)))
    return out, unresolved


def hook_text(project, body):
    ov = os.path.join("Memory", "Projects", project)
    return "\n".join([
        "# 记忆库 · 项目级入口（自动生成，勿手改）",
        "",
        "> 由 `sync_memory_instructions.py --projects` 生成，",
        "> 正文取自真源 `Memory\\Workflows\\AI工具自定义指令.md` §二「最小版」；要改请改真源再重跑。",
        "",
        "**当前项目名：`%s`** —— 本文件是全链路里唯一把项目名填成真值的一处" % project,
        "（用户级钩子里那句是字面占位符 `<项目名>`，从不被替换，所以「当前项目」只能由这里给出。）",
        "",
        body,
        "",
        "## 本项目记忆怎么读",
        "",
        "- 项目档案：`%s\\%s\\_overview.md`（`working\\` 下是台账与流水）" % (MEMORY_ROOT, ov),
        "- 跨层笔记（`Decisions\\` `Lessons\\` `Plans\\` `Preferences\\` `Workflows\\`）平铺在共享层，",
        "  本项目相关的那批只靠 frontmatter 标记：反查 `scope: %s` 与 `scope: global`" % project,
        "- 待办在 `Memory\\Todo.md` 的 `## %s` 分组；完成 = 移走（追加到 `working\\completed.md` 并从 Todo 删除）" % project,
        "- 上面这个分组不存在时**别静默**：先 grep scope，再问用户是否为本项目建档",
        "",
    ])


def deploy_projects(check_only):
    if not CODE_ROOT:
        log("[SKIP] --projects：未配置代码项目根（脚本顶部 CODE_ROOT 或环境变量 AI_PROJECT_ROOT），跳过项目级钩子")
        return 0
    body = minimal_body()
    if not body:
        log("[FATAL] 取不到手册 §二「最小版」正文（%s）——钩子无正文可派生，拒绝部署" % MANUAL)
        return 1
    bad = bad_ctrl(body)
    if bad:
        log("[FATAL] 手册 §二 最小版含裸控制符 %s —— 先修手册" % bad)
        return 1
    roots, unresolved = project_roots()
    log("=== 项目级钩子（真源 §二 最小版 %d 字符；候选项目 %d，其中有代码根 %d）==="
        % (len(body), len(roots) + len(unresolved), len(roots)))
    problems = 0
    for name in sorted(roots):
        target = os.path.join(roots[name], HOOK_NAME)
        want = hook_text(name, body)
        if os.path.exists(target):
            cur = io.open(target, encoding="utf-8", errors="replace").read().strip()
            mine = cur.startswith("# 记忆库 · 项目级入口")
            if not mine:
                log("[KEEP] %-24s 已有非本脚本生成的 %s —— 按「用户手改文件绝不自动改」不覆盖"
                    % (name, HOOK_NAME))
                continue
            if cur != want.strip():
                log("[DRIFT] %-24s 钩子与真源不一致：%s" % (name, target))
                problems += 1
            else:
                log("[OK]   %-24s 钩子在位且一致：%s" % (name, target))
            continue
        if check_only:
            log("[MISS] %-24s 未部署：%s" % (name, roots[name]))
            problems += 1
            continue
        io.open(target, "w", encoding="utf-8", newline="").write(want)
        recheck = io.open(target, encoding="utf-8").read()
        if bad_ctrl(recheck):
            log("[FATAL] %-24s 写入后检出裸控制符，请检查写入链" % name)
            problems += 1
            continue
        git = "（该目录是 git 仓，新文件为未跟踪状态，别误提交进公开仓；含真实路径的项目级钩子用 .git/info/exclude 忽略）" \
            if os.path.isdir(os.path.join(roots[name], ".git")) else ""
        log("[OK]   %-24s 已新建钩子：%s%s" % (name, target, git))
    if unresolved:
        log("--- 无唯一代码根，未处理（%d 个；这些项目走「会话侧从工作目录推断」兜底）---" % len(unresolved))
        for name, k in unresolved:
            log("  [NOROOT] %-24s 目录名命中 %d 个" % (name, k))
    if check_only:
        log("=> 项目级钩子校验：%s" % ("全部在位一致" if problems == 0 else "有 %d 处待部署/漂移" % problems))
        return 1 if problems else 0
    return 0


def main():
    if not os.path.exists(CANON):
        log("[FATAL] 真源文件不存在：%s" % CANON)
        return 1
    text = io.open(CANON, encoding="utf-8").read().strip()
    if not text:
        log("[FATAL] 真源文件为空")
        return 1

    argv = sys.argv[1:]
    if "--projects" in argv:
        return deploy_projects("--check" in argv)
    if "--check" in argv:
        rc = check(text)
        return rc if rc else deploy_projects(True)

    ctrl = bad_ctrl(text)
    if ctrl:
        log("[FATAL] 真源含裸控制符 %s，拒绝部署（先修真源，或跑 --check 看影响面）" % ctrl)
        return 1

    log("=== 记忆库指令同步 ===")
    log("真源: %s (%d 字符)" % (CANON, len(text)))
    if not TARGETS:
        log("[SKIP] 未配置部署目标（TARGETS 为空）——本脚本只做真源体检；要启用分发请按脚本顶部注释配置")
        return 0
    for t, target in iter_targets():
        if t["kind"] == "json-inject":
            deploy_json_inject(target, t["keys"], t.get("restart_hint", ""), text)
        else:
            deploy_file_based(target, t["label"], text)
    log("=== 完成 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
