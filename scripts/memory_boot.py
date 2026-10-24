#!/usr/bin/env python3
"""Build a small, bounded context pack for an Agent session.

Contract:
- BOOT.md is the only always-on hot-memory file.
- If a project is detected, add its overview, current state, and Todo slice.
- Only read the explicit boot inputs; never preload the memory tree.
- --budget limits the returned ``text`` field, not JSON diagnostics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from memory_common import (
    DEFAULT_BUDGET,
    SECTION_LIMITS,
    detect_project,
    extract_todo_section,
    find_memory_dir,
    read_text,
    split_frontmatter,
    truncate_text,
    validate_project_name,
)


def _read_if_exists(path: Path, files: List[str], root: Path) -> str:
    if not path.is_file():
        return ""
    files.append(path.relative_to(root).as_posix())
    return read_text(path).strip()


def _section(name: str, title: str, raw: str, limit: int) -> Dict[str, object]:
    content = truncate_text(raw, limit)
    return {
        "name": name,
        "title": title,
        "source_chars": len(raw),
        "chars": len(content),
        "truncated": len(content) < len(raw),
        "content": content,
    }


def build_boot_pack(
    memory_dir: Path,
    project: Optional[str] = None,
    cwd: Optional[str] = None,
    budget: int = DEFAULT_BUDGET,
) -> Dict[str, object]:
    if budget <= 0:
        raise ValueError("budget must be positive")

    if project:
        detected = validate_project_name(memory_dir, project)
    else:
        detected = detect_project(memory_dir, cwd=cwd)

    files: List[str] = []
    boot = _read_if_exists(memory_dir / "BOOT.md", files, memory_dir)
    if not boot:
        boot = "[BOOT.md missing: add only stable, cross-project facts here]"

    sections: List[Dict[str, object]] = [
        _section("global_hot_memory", "## Global hot memory", boot, SECTION_LIMITS["boot"])
    ]

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
            if raw:
                sections.append(_section(name, title, raw, limit))

    header_lines = ["# Memory Boot Pack", "project: %s" % (detected or "(none)")]
    if not detected:
        header_lines.append("note: no project detected; global hot memory only")

    chunks = ["\n".join(header_lines)]
    for section in sections:
        chunks.append(str(section["title"]))
        chunks.append(str(section["content"]))

    footer = "Use memory_query.py for deeper lookup; do not preload whole notes."
    chunks.append("## Retrieval")
    chunks.append(footer)
    full_text = "\n\n".join(chunks).strip() + "\n"
    final_text = truncate_text(full_text, budget)
    source_chars = sum(int(section["source_chars"]) for section in sections)
    any_section_truncated = any(bool(section["truncated"]) for section in sections)

    public_sections = [
        {k: v for k, v in section.items() if k != "content"}
        for section in sections
    ]
    return {
        "project": detected,
        "budget": budget,
        "budget_scope": "text",
        "chars": len(final_text),
        "source_chars": source_chars,
        "assembled_chars": len(full_text),
        "section_truncated": any_section_truncated,
        "budget_truncated": len(final_text) < len(full_text),
        "truncated": any_section_truncated or len(final_text) < len(full_text),
        "files": files,
        "sections": public_sections,
        "text": final_text,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build an Agent-first memory boot pack")
    parser.add_argument("--memory-dir", help="explicit Memory/ directory")
    parser.add_argument("--cwd", help="working directory used for project detection")
    parser.add_argument("--project", help="explicit project name (single directory name)")
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="maximum characters in the text field")
    parser.add_argument("--json", action="store_true", help="emit metadata plus bounded text as JSON")
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

