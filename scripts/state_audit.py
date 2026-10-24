#!/usr/bin/env python3
"""Report stale, missing, or placeholder project _state.md cards.

This is a report-only tool. It never edits memory files.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from memory_common import (
    STATE_PLACEHOLDER_MARKERS,
    find_memory_dir,
    normalize_group_title,
    parse_iso_date,
    read_text,
)


def _active_projects(memory_dir: Path) -> List[str]:
    todo = memory_dir / "Todo.md"
    projects = memory_dir / "Projects"
    if not projects.is_dir():
        return []
    names: List[str] = []
    if todo.is_file():
        for line in read_text(todo).splitlines():
            if not line.startswith("## "):
                continue
            name = normalize_group_title(line)
            if name and (projects / name).is_dir() and name not in names:
                names.append(name)
    for project in sorted(projects.iterdir()):
        if project.is_dir() and (project / "_state.md").is_file() and project.name not in names:
            names.append(project.name)
    return names


def _updated_date(text: str) -> Optional[date]:
    match = re.search(r"^updated:\s*(\d{4}-\d{2}-\d{2})\s*$", text, re.M)
    return parse_iso_date(match.group(1)) if match else None


def scan_states(
    memory_dir: Path,
    max_age_days: int = 30,
    today: Optional[date] = None,
) -> Dict[str, object]:
    today = today or date.today()
    rows = []
    for project in _active_projects(memory_dir):
        path = memory_dir / "Projects" / project / "_state.md"
        row = {"project": project, "path": str(path), "exists": path.is_file()}
        if path.is_file():
            text = read_text(path)
            row["chars"] = len(text)
            updated = _updated_date(text)
            row["updated"] = updated.isoformat() if updated else ""
            row["placeholder"] = any(marker in text for marker in STATE_PLACEHOLDER_MARKERS)
            row["stale"] = bool(updated and (today - updated).days > max_age_days)
            row["missing_updated"] = updated is None
            row["too_large"] = len(text) > 1000
        else:
            row["chars"] = 0
            row["updated"] = ""
            row["placeholder"] = False
            row["stale"] = False
            row["missing_updated"] = False
            row["too_large"] = False
        rows.append(row)
    return {
        "scanned": len(rows),
        "missing": [r["project"] for r in rows if not r["exists"]],
        "placeholder": [r["project"] for r in rows if r["placeholder"]],
        "stale": [r["project"] for r in rows if r["stale"]],
        "missing_updated": [r["project"] for r in rows if r["missing_updated"]],
        "too_large": [r["project"] for r in rows if r["too_large"]],
        "rows": rows,
    }


def render(result: Dict[str, object], max_age_days: int) -> str:
    lines = [
        "# Project state audit",
        "",
        f"- active projects: {result['scanned']}",
        f"- missing _state.md: {len(result['missing'])}",
        f"- placeholder state: {len(result['placeholder'])}",
        f"- stale (> {max_age_days} days): {len(result['stale'])}",
        f"- missing/invalid updated: {len(result['missing_updated'])}",
        f"- too large (> 1000 chars): {len(result['too_large'])}",
        "",
        "| project | exists | chars | updated | placeholder | stale | too large |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for row in result["rows"]:
        lines.append(
            "| %s | %s | %s | %s | %s | %s | %s |" % (
                row["project"], "yes" if row["exists"] else "no", row["chars"],
                row["updated"] or "-", "yes" if row["placeholder"] else "no",
                "yes" if row["stale"] else "no",
                "yes" if row["too_large"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Report project _state health")
    parser.add_argument("--memory-dir")
    parser.add_argument("--max-age-days", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", help="write report to a file")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit 1 on empty coverage or any missing/missing-updated/placeholder/stale/oversized state",
    )
    args = parser.parse_args(argv)

    memory_dir = find_memory_dir(args.memory_dir)
    if memory_dir is None:
        print("Memory directory not found.", file=sys.stderr)
        return 2
    result = scan_states(memory_dir, args.max_age_days)
    text = json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result, args.max_age_days)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"report: {args.out}")
    else:
        print(text, end="")
    if args.strict and (
        result["scanned"] == 0
        or result["missing"]
        or result["placeholder"]
        or result["stale"]
        or result["missing_updated"]
        or result["too_large"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
