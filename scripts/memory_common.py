#!/usr/bin/env python3
"""Shared helpers for the Agent-first memory boot/query commands.

The Markdown tree remains the source of truth. These helpers only locate it,
parse a small amount of frontmatter, and build bounded context.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple


MEMORY_MARKERS = ("BOOT.md", "Todo.md", "_index.md", "rule")
FRONTMATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n)?", re.S)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.M)
PROJECT_NAME_RE = re.compile(r"当前项目名\s*[：:]\s*(?:`([^`]+)`|\*\*([^*\r\n]+)\*\*|([^\s*`]+))")


def is_memory_root(path: Path) -> bool:
    return any((path / marker).exists() for marker in MEMORY_MARKERS)


def find_memory_dir(explicit: Optional[str] = None, start: Optional[str] = None) -> Optional[Path]:
    """Find the Memory root.

    Precedence: explicit argument, AI_MEMORY_DIR, then walk up from start
    (or cwd), then walk up from this file's directory.
    """
    if explicit:
        candidate = Path(explicit).expanduser()
        return candidate.resolve() if candidate.exists() else None

    env = os.environ.get("AI_MEMORY_DIR")
    if env:
        candidate = Path(env).expanduser()
        return candidate.resolve() if candidate.exists() else None

    starts: List[Path] = []
    if start:
        starts.append(Path(start).expanduser())
    starts.append(Path.cwd())
    starts.append(Path(__file__).resolve().parent)

    seen = set()
    for raw in starts:
        current = raw.resolve()
        for _ in range(16):
            if current in seen:
                break
            seen.add(current)
            if current.name == "Memory" and is_memory_root(current):
                return current
            candidate = current / "Memory"
            if candidate.is_dir() and is_memory_root(candidate):
                return candidate
            if current.parent == current:
                break
            current = current.parent
    return None


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def char_len(text: str) -> int:
    return len(text)


def truncate_text(text: str, limit: int, marker: str = "\n...[truncated]...\n") -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= len(marker):
        return text[:limit]
    return text[: limit - len(marker)].rstrip() + marker


def split_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    data: Dict[str, str] = {}
    for line in match.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip().lower()] = value.strip().strip('"').strip("'")
    return data, text[match.end():]


def first_heading(body: str, fallback: str) -> str:
    match = HEADING_RE.search(body)
    return match.group(1).strip() if match else fallback


def detect_project(memory_dir: Path, cwd: Optional[str] = None) -> Optional[str]:
    """Detect the current project from a nearest AGENTS.md, then path shape.

    Project names are only accepted when a matching directory exists under
    Memory/Projects. This mirrors the existing "do not guess" contract.
    """
    projects = memory_dir / "Projects"
    if not projects.is_dir():
        return None

    current = Path(cwd or os.getcwd()).expanduser().resolve()
    for parent in [current] + list(current.parents):
        agents = parent / "AGENTS.md"
        if not agents.is_file():
            continue
        for line in read_text(agents).splitlines():
            if "当前项目名" not in line:
                continue
            match = PROJECT_NAME_RE.search(line)
            if not match:
                continue
            name = next((g for g in match.groups() if g), "").strip().rstrip("*`")
            if name and (projects / name).is_dir():
                return name
        break

    parts = current.parts
    for i, part in enumerate(parts):
        if part.lower() != "projects" or i + 1 >= len(parts):
            continue
        name = parts[i + 1]
        if (projects / name).is_dir():
            return name

    if (projects / current.name).is_dir():
        return current.name
    return None


def extract_todo_section(text: str, project: str) -> str:
    """Return only the project's ## <name> section from Todo.md."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## %s" % project:
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip()


def normalize_search_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).lower()


def query_terms(query: str) -> List[str]:
    normalized = normalize_search_text(query).strip()
    if not normalized:
        return []
    pieces = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", normalized)
    terms: List[str] = []
    for term in [normalized] + pieces:
        if term and term not in terms:
            terms.append(term)
    return terms


def rel_posix(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()
