#!/usr/bin/env python3
"""Build a small, bounded context pack for an Agent session.

Contract:
- BOOT.md is the only always-on hot-memory file.
- If a project is detected, add its overview, current state, and Todo slice.
- Never read _index.md or layer indexes during boot.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from memory_common import (
    detect_project,
    extract_todo_section,
    find_memory_dir,
    read_text,
    split_frontmatter,
    truncate_text,
)


DEFAULT_BUDGET = 6000
SECTION_LIMITS = {
    "boot": 2600,
    "overview": 1800,
    "state": 1200,
    "todo": 1400,
}


def _read_if_exists(path: Path, files: List[str], root: Path) -> str:
    if not path.is_file():
        return ""
    files.append(path.relative_to(root).as_posix())
    return read_text(path).strip()


def build_boot_pack(
    memory_dir: Path,
    project: Optional[str] = None,
    cwd: Optional[str] = None,
    budget: int = DEFAULT_BUDGET,
) -> Dict[str, object]:
    if budget <= 0:
        raise ValueError("budget must be positive")

    files: List[str] = []
    boot = _read_if_exists(memory_dir / "BOOT.md", files, memory_dir)
    if not boot:
        boot = "[BOOT.md missing: add only stable, cross-project facts here]"

    detected = project or detect_project(memory_dir, cwd=cwd)
    sections: List[Dict[str, object]] = []

    boot_content = truncate_text(boot, SECTION_LIMITS["boot"])
    sections.append({
        "name": "global_hot_memory",
        "title": "## Global hot memory",
        "content": boot_content,
        "truncated": len(boot_content) < len(boot),
    })

    if detected:
        project_dir = memory_dir / "Projects" / detected
        overview = split_frontmatter(_read_if_exists(project_dir / "_overview.md", files, memory_dir))[1].strip()
        state = split_frontmatter(_read_if_exists(project_dir / "_state.md", files, memory_dir))[1].strip()
        todo_text = _read_if_exists(memory_dir / "Todo.md", files, memory_dir)
        todo = extract_todo_section(todo_text, detected) if todo_text else ""

        for name, title, raw, limit in (
            ("project_overview", "## Project overview", overview, SECTION_LIMITS["overview"]),
            ("project_state", "## Project state", state, SECTION_LIMITS["state"]),
            ("active_todo", "## Active todo", todo, SECTION_LIMITS["todo"]),
        ):
            if not raw:
                continue
            content = truncate_text(raw, limit)
            sections.append({
                "name": name,
                "title": title,
                "content": content,
                "truncated": len(content) < len(raw),
            })

    header_lines = ["# Memory Boot Pack", "project: %s" % (detected or "(none)")]
    if not detected:
        header_lines.append("note: no project detected; generic task context only")

    chunks = ["\n".join(header_lines)]
    for section in sections:
        chunks.append(str(section["title"]))
        chunks.append(str(section["content"]))

    footer = "Use memory_query.py for deeper lookup; do not read _index.md or layer indexes during boot."
    chunks.append("## Retrieval")
    chunks.append(footer)
    full_text = "\n\n".join(chunks).strip() + "\n"
    original_chars = len(full_text)
    final_text = truncate_text(full_text, budget)
    if len(final_text) < len(full_text):
        final_text = final_text.rstrip() + "\n"

    return {
        "project": detected,
        "budget": budget,
        "chars": len(final_text),
        "original_chars": original_chars,
        "truncated": len(final_text) < original_chars,
        "files": files,
        "sections": sections,
        "text": final_text,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build an Agent-first memory boot pack")
    parser.add_argument("--memory-dir", help="explicit Memory/ directory")
    parser.add_argument("--cwd", help="working directory used for project detection")
    parser.add_argument("--project", help="explicit project name")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="maximum output characters")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    memory_dir = find_memory_dir(args.memory_dir, start=args.cwd)
    if memory_dir is None:
        print("Memory directory not found. Set AI_MEMORY_DIR or pass --memory-dir.", file=sys.stderr)
        return 2

    try:
        pack = build_boot_pack(memory_dir, project=args.project, cwd=args.cwd, budget=args.budget)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        print(json.dumps(pack, ensure_ascii=False, indent=2))
    else:
        print(str(pack["text"]), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
