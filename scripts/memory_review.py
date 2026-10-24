#!/usr/bin/env python3
"""Report lifecycle and freshness debt in long-term memory notes.

This is a report-only review queue. It never edits notes and never treats
missing historical metadata as a hard failure unless ``--strict`` is used.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional

from memory_common import find_memory_dir, first_heading, read_text, rel_posix, split_frontmatter


LAYERS = ("Preferences", "Decisions", "Lessons", "Workflows")
DEFAULT_MAX_AGE_DAYS = 90
DEFAULT_LIMIT = 50
INACTIVE_PREFIXES = ("archived", "superseded", "rejected")
ALLOWED_STATUS_EXACT = {"active", "review", "proposed", "implemented"}
VOLATILE_RE = re.compile(
    r"(?<![A-Za-z])[A-Za-z]:[\\/](?![\\/])"
    r"|(?<![\w:])/(?:[\w.-]+/)+[\w.-]*"
    r"|(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+\.(?:py|md|json|toml|yaml|yml|js|ts|tsx|ps1|cmd|sh)"
    r"|安装目录|可执行文件|命令行|环境版本|版本号|工具行为|盘符|代码根"
)
DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def _read_date(value: str) -> Optional[date]:
    value = (value or "").strip()
    if not DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _is_inactive(status: str) -> bool:
    return any((status or "").lower().startswith(prefix) for prefix in INACTIVE_PREFIXES)


def _has_volatile_claim(body: str) -> bool:
    for line in body.splitlines():
        if "://" in line:
            line = re.sub(r"https?://\S+", "", line)
        if VOLATILE_RE.search(line):
            return True
    return False


def _valid_status(status: str) -> bool:
    if not status:
        return False
    if status in ALLOWED_STATUS_EXACT:
        return True
    return any(status.startswith(prefix + "-") for prefix in INACTIVE_PREFIXES)


def scan_memory_review(
    memory_dir: Path,
    today: Optional[date] = None,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> Dict[str, object]:
    today = today or date.today()
    issues: List[Dict[str, object]] = []
    scanned = 0

    for layer in LAYERS:
        root = memory_dir / layer
        if not root.is_dir():
            continue
        for path in sorted(root.glob("*.md")):
            if path.name == "README.md":
                continue
            text = read_text(path)
            frontmatter, body = split_frontmatter(text)
            if not frontmatter:
                if text.lstrip("\ufeff").startswith("---"):
                    issues.append({
                        "path": rel_posix(path, memory_dir),
                        "title": path.stem,
                        "status": "",
                        "code": "frontmatter_invalid",
                        "priority": 1,
                    })
                continue
            scanned += 1
            status = frontmatter.get("status", "").strip().lower()
            title = frontmatter.get("title") or first_heading(body, path.stem)
            common = {
                "path": rel_posix(path, memory_dir),
                "title": title,
                "status": status,
            }
            if not status:
                issues.append({**common, "code": "missing_status", "priority": 1})
            elif status == "review":
                issues.append({**common, "code": "review_status", "priority": 1})
            elif not _valid_status(status):
                issues.append({**common, "code": "invalid_status", "priority": 1})

            if _is_inactive(status):
                continue
            if not _has_volatile_claim(body):
                continue

            verified_raw = frontmatter.get("verified_at", "")
            verified = _read_date(verified_raw)
            if verified is None:
                issues.append({
                    **common,
                    "code": "volatile_unverified",
                    "priority": 2,
                    "verified_at": verified_raw,
                })
            elif verified > today:
                issues.append({
                    **common,
                    "code": "volatile_future",
                    "priority": 2,
                    "verified_at": verified.isoformat(),
                })
            elif (today - verified).days > max_age_days:
                issues.append({
                    **common,
                    "code": "volatile_stale",
                    "priority": 2,
                    "verified_at": verified.isoformat(),
                    "age_days": (today - verified).days,
                })

    issues.sort(key=lambda row: (int(row["priority"]), str(row["path"])))
    counts = {}
    for code in (
        "missing_status", "review_status", "invalid_status",
        "frontmatter_invalid",
        "volatile_unverified", "volatile_stale", "volatile_future",
    ):
        counts[code] = sum(1 for row in issues if row["code"] == code)
    return {
        "scanned": scanned,
        "max_age_days": max_age_days,
        "counts": counts,
        "issues": issues,
    }


def render(result: Dict[str, object], limit: int = DEFAULT_LIMIT) -> str:
    counts = result["counts"]
    lines = [
        "# Memory Review",
        "",
        f"- scanned long-term notes: {result['scanned']}",
        f"- missing status: {counts['missing_status']}",
        f"- status review: {counts['review_status']}",
        f"- invalid status: {counts['invalid_status']}",
        f"- invalid frontmatter: {counts['frontmatter_invalid']}",
        f"- volatile without verified_at: {counts['volatile_unverified']}",
        f"- volatile verified > {result['max_age_days']} days: {counts['volatile_stale']}",
        f"- volatile future-dated: {counts['volatile_future']}",
        "",
    ]
    labels = {
        "missing_status": "missing status",
        "review_status": "review",
        "invalid_status": "invalid status",
        "frontmatter_invalid": "invalid frontmatter",
        "volatile_unverified": "unverified volatile claim",
        "volatile_stale": "stale volatile claim",
        "volatile_future": "future-dated volatile claim",
    }
    shown = result["issues"][:limit]
    for issue in shown:
        detail = ""
        if issue["code"] == "volatile_stale":
            detail = f" (verified {issue['verified_at']}, {issue['age_days']}d)"
        elif issue["code"] == "volatile_future":
            detail = f" (future verified_at {issue['verified_at']})"
        elif issue["code"] == "volatile_unverified":
            detail = " (no verified_at)"
        lines.append(f"- [{labels[issue['code']]}] {issue['path']} — {issue['title']}{detail}")
    remaining = len(result["issues"]) - len(shown)
    if remaining:
        lines.append(f"- ... {remaining} more; use --json for the full list")
    if not result["issues"]:
        lines.append("- no lifecycle debt found")
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Report long-term memory lifecycle debt")
    parser.add_argument("--memory-dir")
    parser.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out")
    parser.add_argument("--strict", action="store_true", help="exit 1 when any review item exists")
    args = parser.parse_args(argv)

    if args.max_age_days < 0 or args.limit <= 0:
        print("max-age-days must be non-negative and limit must be positive", file=sys.stderr)
        return 2
    memory_dir = find_memory_dir(args.memory_dir)
    if memory_dir is None:
        print("Memory directory not found.", file=sys.stderr)
        return 2

    result = scan_memory_review(memory_dir, max_age_days=args.max_age_days)
    text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result, args.limit)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"report: {args.out}")
    else:
        print(text, end="")
    if args.strict and result["issues"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
