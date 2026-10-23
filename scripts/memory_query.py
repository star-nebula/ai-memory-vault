#!/usr/bin/env python3
"""Bounded keyword search over the Agent memory tree.

Search is deliberately small and deterministic: no LLM, no embedding, no whole
note expansion. Results carry paths and snippets so the caller can decide
whether one note deserves a full read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

from memory_common import (
    detect_project,
    find_memory_dir,
    first_heading,
    normalize_search_text,
    query_terms,
    read_text,
    rel_posix,
    split_frontmatter,
    truncate_text,
)


DEFAULT_LIMIT = 5
DEFAULT_BUDGET = 5000
SNIPPET_CHARS = 420
SKIP_DIRS = {"__pycache__", ".git", ".obsidian", ".trash", "scripts", "Templates", "rule"}
SKIP_FILES = {"_index.md", "README.md", "AGENTS.md", "Rule.md", "BOOT.md"}
ACTIVE_STATUS = {"", "active", "proposed", "implemented", "accepted"}


def _iter_notes(memory_dir: Path, include_history: bool):
    for path in sorted(memory_dir.rglob("*.md")):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        rel_parts = path.relative_to(memory_dir).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if not include_history and (rel_parts[0] in ("Inbox", "Archive") or "working" in rel_parts):
            continue
        yield path, rel_parts


def _snippet(body: str, terms: List[str], width: int = SNIPPET_CHARS) -> str:
    compact = re.sub(r"\s+", " ", body).strip()
    if not compact:
        return ""
    low = normalize_search_text(compact)
    positions = [low.find(term) for term in terms if term and low.find(term) >= 0]
    if not positions:
        return compact[:width]
    idx = min(positions)
    start = max(0, idx - 120)
    end = min(len(compact), start + width)
    if end - start < width:
        start = max(0, end - width)
    return ("..." if start else "") + compact[start:end].strip() + ("..." if end < len(compact) else "")


def search_memory(
    memory_dir: Path,
    query: str,
    project: Optional[str] = None,
    types: Optional[List[str]] = None,
    limit: int = DEFAULT_LIMIT,
    include_inactive: bool = False,
    include_history: bool = False,
) -> Dict[str, object]:
    terms = query_terms(query)
    if not terms:
        return {"query": query, "project": project, "matches": [], "total_before_budget": 0}

    type_filter = {t.strip().lower() for t in types or [] if t.strip()}
    matches: List[Dict[str, object]] = []

    for path, _ in _iter_notes(memory_dir, include_history):
        text = read_text(path)
        frontmatter, body = split_frontmatter(text)
        typ = frontmatter.get("type", "").lower()
        if type_filter and typ not in type_filter:
            continue
        status = frontmatter.get("status", "").lower()
        if not include_inactive and status not in ACTIVE_STATUS:
            continue
        scope = frontmatter.get("scope", "")
        if project and scope and scope not in (project, "global"):
            continue

        title = frontmatter.get("title") or first_heading(body, path.stem)
        headings = "\n".join(re.findall(r"^#{1,6}\s+(.+?)\s*$", body, re.M))
        tags = frontmatter.get("tags", "")
        searchable = normalize_search_text("\n".join([title, headings, tags, body]))
        counts = {term: searchable.count(term) for term in terms}
        if not any(counts.values()):
            continue

        title_low = normalize_search_text(title)
        heading_low = normalize_search_text(headings)
        tags_low = normalize_search_text(tags)
        score = 0
        for term in terms:
            if title_low == term:
                score += 100
            elif term in title_low:
                score += 45
            score += heading_low.count(term) * 10
            score += tags_low.count(term) * 8
            score += min(counts[term], 12) * 2
        if scope == project:
            score += 8
        elif scope == "global":
            score += 3

        matches.append({
            "path": rel_posix(path, memory_dir),
            "title": title,
            "type": typ or "note",
            "scope": scope,
            "status": status or "active",
            "updated": frontmatter.get("updated", ""),
            "score": score,
            "snippet": _snippet(body, terms),
        })

    matches.sort(key=lambda item: (int(item["score"]), str(item.get("updated", ""))), reverse=True)
    total = len(matches)
    return {"query": query, "project": project, "matches": matches[:limit], "total_before_budget": total}


def _render_text(result: Dict[str, object], budget: int) -> str:
    matches = list(result.get("matches", []))
    while matches:
        chunks = ["# Memory Query", "query: %s" % result["query"]]
        if result.get("project"):
            chunks.append("project: %s" % result["project"])
        chunks.append("returned: %d/%d" % (len(matches), result["total_before_budget"]))
        for i, match in enumerate(matches, 1):
            chunks.extend([
                "",
                "## %d. %s" % (i, match["title"]),
                "path: %s" % match["path"],
                "type: %s | scope: %s | status: %s | updated: %s" % (
                    match["type"], match["scope"] or "-", match["status"], match["updated"] or "-"),
                "> %s" % match["snippet"],
            ])
        text = "\n".join(chunks).strip() + "\n"
        if len(text) <= budget:
            return text
        matches.pop()
    return "# Memory Query\nquery: %s\n\nNo bounded results within budget.\n" % result["query"]


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded keyword search over Agent memory")
    parser.add_argument("query", help="keywords or a short phrase")
    parser.add_argument("--memory-dir", help="explicit Memory/ directory")
    parser.add_argument("--cwd", help="working directory used for project detection")
    parser.add_argument("--project", help="project scope; global notes remain eligible")
    parser.add_argument("--types", help="comma-separated frontmatter types")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--include-inactive", action="store_true")
    parser.add_argument("--include-history", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    memory_dir = find_memory_dir(args.memory_dir, start=args.cwd)
    if memory_dir is None:
        print("Memory directory not found. Set AI_MEMORY_DIR or pass --memory-dir.", file=sys.stderr)
        return 2
    if args.limit <= 0 or args.budget <= 0:
        print("limit and budget must be positive", file=sys.stderr)
        return 2

    project = args.project or detect_project(memory_dir, cwd=args.cwd)
    types = args.types.split(",") if args.types else None
    result = search_memory(
        memory_dir=memory_dir,
        query=args.query,
        project=project,
        types=types,
        limit=args.limit,
        include_inactive=args.include_inactive,
        include_history=args.include_history,
    )
    text = _render_text(result, args.budget)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        payload = dict(result)
        payload["text"] = text
        payload["chars"] = len(text)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
