#!/usr/bin/env python3
"""Bounded keyword search over the Agent memory tree.

Search is deliberately small and deterministic: no LLM, no embedding, no whole
note expansion. Results carry paths and snippets so the caller can decide
whether one note deserves a full read.

Budget semantics: ``--budget`` limits the rendered ``text`` field. JSON
metadata is intentionally separate and may be larger than the text budget.
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
    detect_project,
    find_memory_dir,
    first_heading,
    normalize_search_text,
    query_terms,
    read_text,
    rel_posix,
    split_frontmatter,
    truncate_text,
    validate_project_name,
)


DEFAULT_LIMIT = 5
DEFAULT_BUDGET = 5000
SNIPPET_CHARS = 420
SKIP_DIRS = {"__pycache__", ".git", ".obsidian", ".trash", "scripts", "Templates", "rule"}
SKIP_FILES = {"README.md", "AGENTS.md", "Rule.md", "BOOT.md"}
INACTIVE_STATUSES = ("archived", "superseded", "rejected")


def _parse_date(value: str) -> Optional[date]:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value or ""):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year, 12, 31)
    else:
        end = date(year, month + 1, 1)
        end = date.fromordinal(end.toordinal() - 1)
    return start, end


def _quarter_bounds(year: int, quarter: int) -> tuple[date, date]:
    start_month = (quarter - 1) * 3 + 1
    start = date(year, start_month, 1)
    _, end = _month_bounds(year, start_month + 2)
    return start, end


def _note_date_bounds(
    path: Path,
    frontmatter: Dict[str, str],
    body: str,
) -> Optional[tuple[date, date]]:
    dates = []
    for value in re.findall(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", body, re.M):
        parsed = _parse_date(value)
        if parsed:
            dates.append(parsed)
    if dates:
        return min(dates), max(dates)

    month = re.fullmatch(r"(\d{4})-(\d{2})\.md", path.name)
    if month and path.parent.name == "journal":
        try:
            return _month_bounds(int(month.group(1)), int(month.group(2)))
        except ValueError:
            return None

    quarter = re.fullmatch(r"(\d{4})-Q([1-4])\.md", path.name)
    if quarter and path.parent.name == "completed":
        try:
            return _quarter_bounds(int(quarter.group(1)), int(quarter.group(2)))
        except ValueError:
            return None

    created = _parse_date(frontmatter.get("created", ""))
    updated = _parse_date(frontmatter.get("updated", ""))
    if created and updated:
        return min(created, updated), max(created, updated)
    if created or updated:
        point = created or updated
        return point, point
    return None


def _shard_date_bounds(path: Path) -> Optional[tuple[date, date]]:
    month = re.fullmatch(r"(\d{4})-(\d{2})\.md", path.name)
    if month and path.parent.name == "journal":
        try:
            return _month_bounds(int(month.group(1)), int(month.group(2)))
        except ValueError:
            return None
    quarter = re.fullmatch(r"(\d{4})-Q([1-4])\.md", path.name)
    if quarter and path.parent.name == "completed":
        try:
            return _quarter_bounds(int(quarter.group(1)), int(quarter.group(2)))
        except ValueError:
            return None
    return None


def _overlaps(
    bounds: tuple[date, date],
    since: Optional[date],
    until: Optional[date],
) -> bool:
    start, end = bounds
    if since and end < since:
        return False
    if until and start > until:
        return False
    return True


def _is_inactive(status: str) -> bool:
    value = (status or "").strip().lower()
    return any(value.startswith(prefix) for prefix in INACTIVE_STATUSES)


def _iter_notes(
    memory_dir: Path,
    include_history: bool,
    project: Optional[str] = None,
    all_projects: bool = False,
    since: Optional[date] = None,
    until: Optional[date] = None,
    layers: Optional[set[str]] = None,
):
    for path in sorted(memory_dir.rglob("*.md")):
        if not path.is_file() or path.name in SKIP_FILES:
            continue
        rel_parts = path.relative_to(memory_dir).parts
        if any(part in SKIP_DIRS for part in rel_parts):
            continue
        if layers and rel_parts[0].lower() not in layers:
            continue
        shard_bounds = _shard_date_bounds(path)
        if (since or until) and shard_bounds and not _overlaps(shard_bounds, since, until):
            continue
        if not include_history and (rel_parts[0] in ("Inbox", "Archive") or "working" in rel_parts):
            continue
        if rel_parts[0] == "Projects":
            if not project and not all_projects:
                continue
            if project and (len(rel_parts) < 2 or rel_parts[1] != project):
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


def _term_weight(term: str) -> float:
    """Reduce noise from bare IDs while keeping them usable in numeric queries."""
    if len(term) == 1:
        return 0.15
    if term.isascii() and len(term) <= 2:
        return 0.5
    return 1.0


def _count_term(text: str, term: str) -> int:
    """Count ASCII terms as tokens, not substrings inside unrelated words."""
    if not term.isascii():
        return text.count(term)
    pattern = r"(?<![a-z0-9])%s(?![a-z0-9])" % re.escape(term)
    return len(re.findall(pattern, text, re.I))


def search_memory(
    memory_dir: Path,
    query: str,
    project: Optional[str] = None,
    types: Optional[List[str]] = None,
    limit: int = DEFAULT_LIMIT,
    include_inactive: bool = False,
    include_history: bool = False,
    all_projects: bool = False,
    since: Optional[date] = None,
    until: Optional[date] = None,
    layers: Optional[List[str]] = None,
) -> Dict[str, object]:
    if project:
        project = validate_project_name(memory_dir, project)

    terms = query_terms(query)
    if not terms:
        return {
            "query": query,
            "project": project,
            "matches": [],
            "total_before_budget": 0,
            "undated_skipped": 0,
        }

    normalized_query = normalize_search_text(query)
    strong_terms = [
        term for term in terms
        if (term != normalized_query or len(terms) == 1)
        and (len(term) >= 3 or (not term.isascii() and len(term) >= 2))
    ]
    type_filter = {t.strip().lower() for t in types or [] if t.strip()}
    layer_filter = {layer.strip().lower() for layer in layers or [] if layer.strip()}
    if layer_filter:
        available_layers = {
            path.name.lower()
            for path in memory_dir.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        }
        unknown_layers = sorted(layer_filter - available_layers)
        if unknown_layers:
            raise ValueError("unknown layers: %s" % ", ".join(unknown_layers))
    matches: List[Dict[str, object]] = []
    undated_skipped = 0

    for path, rel_parts in _iter_notes(
        memory_dir,
        include_history,
        project=project,
        all_projects=all_projects,
        since=since,
        until=until,
        layers=layer_filter,
    ):
        text = read_text(path)
        frontmatter, body = split_frontmatter(text)
        typ = frontmatter.get("type", "").lower()
        if type_filter and typ not in type_filter:
            continue
        status = frontmatter.get("status", "").lower()
        if not include_inactive and _is_inactive(status):
            continue
        scope = frontmatter.get("scope", "")
        in_project_tree = len(rel_parts) >= 2 and rel_parts[0] == "Projects"
        if project:
            if in_project_tree and rel_parts[1] != project:
                continue
            if not in_project_tree and scope.casefold() not in (project.casefold(), "global"):
                continue
        elif not all_projects:
            if in_project_tree or scope.casefold() != "global":
                continue

        title = frontmatter.get("title") or first_heading(body, path.stem)
        headings = "\n".join(re.findall(r"^#{1,6}\s+(.+?)\s*$", body, re.M))
        tags = frontmatter.get("tags", "")
        searchable = normalize_search_text("\n".join([title, headings, tags, body]))
        counts = {term: _count_term(searchable, term) for term in terms}
        if not any(counts.values()):
            continue
        # A query such as "home-pages PR #8 issue #9" must not rank notes that only
        # happen to contain the bare digits 8 or 9. If the query has stronger terms,
        # require at least one of them before scoring.
        if strong_terms and not any(counts[term] for term in strong_terms):
            continue
        bounds = _note_date_bounds(path, frontmatter, body) if (since or until) else None
        if since or until:
            if bounds is None:
                undated_skipped += 1
                continue
            if not _overlaps(bounds, since, until):
                continue

        title_low = normalize_search_text(title)
        heading_low = normalize_search_text(headings)
        tags_low = normalize_search_text(tags)
        score = 0.0
        if project and in_project_tree:
            score += 25
        if normalized_query and normalized_query in searchable:
            score += 120
        score += sum(3 for term in strong_terms if counts[term])
        for term in terms:
            weight = _term_weight(term)
            if title_low == term:
                score += 100 * weight
            else:
                score += _count_term(title_low, term) * 45 * weight
            score += _count_term(heading_low, term) * 10 * weight
            score += _count_term(tags_low, term) * 8 * weight
            score += min(counts[term], 12) * 2 * weight
        if project and scope.casefold() == project.casefold():
            score += 8
        elif scope.casefold() == "global":
            score += 3

        matches.append({
            "path": rel_posix(path, memory_dir),
            "title": title,
            "type": typ or "note",
            "scope": scope,
            "status": status or "unset",
            "verified_at": frontmatter.get("verified_at", ""),
            "updated": frontmatter.get("updated", ""),
            "date_from": bounds[0].isoformat() if bounds else "",
            "date_to": bounds[1].isoformat() if bounds else "",
            "score": score,
            "snippet": _snippet(body, terms),
        })

    matches.sort(key=lambda item: (float(item["score"]), str(item.get("updated", ""))), reverse=True)
    total = len(matches)
    return {
        "query": query,
        "project": project,
        "matches": matches[:limit],
        "total_before_budget": total,
        "undated_skipped": undated_skipped,
    }


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
                "type: %s | scope: %s | status: %s | updated: %s | verified: %s" % (
                    match["type"], match["scope"] or "-", match["status"],
                    match["updated"] or "-", match["verified_at"] or "-"),
                "range: %s..%s" % (
                    match["date_from"] or "-", match["date_to"] or "-"),
                "> %s" % match["snippet"],
            ])
        text = "\n".join(chunks).strip() + "\n"
        if len(text) <= budget:
            return text
        matches.pop()
    fallback = "# Memory Query\nquery: %s\n\nNo bounded results within budget.\n" % result["query"]
    return truncate_text(fallback, budget)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded keyword search over Agent memory")
    parser.add_argument("query", help="keywords or a short phrase")
    parser.add_argument("--memory-dir", help="explicit Memory/ directory")
    parser.add_argument("--cwd", help="working directory used for project detection")
    parser.add_argument("--project", help="project scope (single directory name)")
    parser.add_argument("--all-projects", action="store_true", help="search project trees across all projects unless --project is explicit")
    parser.add_argument("--types", help="comma-separated frontmatter types")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET, help="maximum characters in the text field")
    parser.add_argument("--include-inactive", action="store_true", help="include archived/superseded/rejected notes")
    parser.add_argument("--include-history", action="store_true", help="include Inbox/Archive/working files")
    parser.add_argument("--since", help="include notes intersecting YYYY-MM-DD or later")
    parser.add_argument("--until", help="include notes intersecting YYYY-MM-DD or earlier")
    parser.add_argument("--layers", help="comma-separated layers, e.g. Decisions,Lessons,Projects")
    parser.add_argument("--json", action="store_true", help="emit metadata plus bounded text as JSON")
    args = parser.parse_args(argv)

    memory_dir = find_memory_dir(args.memory_dir, start=args.cwd)
    if memory_dir is None:
        print("Memory directory not found. Set AI_MEMORY_DIR or pass --memory-dir.", file=sys.stderr)
        return 2
    if args.limit <= 0 or args.budget <= 0:
        print("limit and budget must be positive", file=sys.stderr)
        return 2

    try:
        since = _parse_date(args.since) if args.since else None
        until = _parse_date(args.until) if args.until else None
        if (args.since and since is None) or (args.until and until is None):
            print("since/until must use YYYY-MM-DD", file=sys.stderr)
            return 2
        if since and until and since > until:
            print("since must not be later than until", file=sys.stderr)
            return 2
        project = args.project
        if not project and not args.all_projects:
            project = detect_project(memory_dir, cwd=args.cwd)
        types = args.types.split(",") if args.types else None
        layers = args.layers.split(",") if args.layers else None
        result = search_memory(
            memory_dir=memory_dir,
            query=args.query,
            project=project,
            types=types,
            limit=args.limit,
            include_inactive=args.include_inactive,
            include_history=args.include_history,
            all_projects=args.all_projects,
            since=since,
            until=until,
            layers=layers,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    text = _render_text(result, args.budget)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if args.json:
        payload = dict(result)
        payload["matches"] = [
            {k: v for k, v in match.items() if k != "snippet"}
            for match in result.get("matches", [])
        ]
        payload["budget"] = args.budget
        payload["budget_scope"] = "text"
        payload["since"] = args.since or ""
        payload["until"] = args.until or ""
        payload["layers"] = [layer for layer in (args.layers or "").split(",") if layer]
        full_text = _render_text(result, 10 ** 9)
        payload["text"] = text
        payload["chars"] = len(text)
        payload["truncated"] = len(text) < len(full_text)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
