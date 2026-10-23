from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from memory_boot import build_boot_pack
from memory_common import detect_project, extract_todo_section
from memory_query import search_memory


class MemoryAgentContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.memory = self.root / "workspace" / "Memory"
        self.project = self.memory / "Projects" / "demo"
        self.project.mkdir(parents=True)
        (self.memory / "Decisions").mkdir()
        (self.memory / "Lessons").mkdir()
        (self.memory / "BOOT.md").write_text(
            "---\ntype: boot\n---\n# Global hot memory\n\n- Answer in Chinese.\n",
            encoding="utf-8",
        )
        (self.memory / "_index.md").write_text("SHOULD_NOT_APPEAR_IN_BOOT\n", encoding="utf-8")
        (self.memory / "Todo.md").write_text(
            "# Todo\n\n## demo\n\n- finish bounded retrieval\n\n## other\n\n- unrelated\n",
            encoding="utf-8",
        )
        (self.project / "_overview.md").write_text(
            "---\ntype: project-fact\n---\n# Demo\n\nProject overview.\n",
            encoding="utf-8",
        )
        (self.project / "_state.md").write_text(
            "---\ntype: project-fact\n---\n# State\n\nCurrent goal: validate P0.\n",
            encoding="utf-8",
        )
        (self.memory / "Lessons" / "bounded-memory.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\nupdated: 2026-10-23\n"
            "tags: [memory, retrieval]\n---\n# 启动读取过多\n\n按项目切片并使用有界检索，避免读取整个索引。\n",
            encoding="utf-8",
        )
        (self.memory / "Decisions" / "old-memory.md").write_text(
            "---\ntype: decision\nscope: demo\nstatus: archived-2026-Q3\nupdated: 2026-07-01\n"
            "tags: [memory]\n---\n# 启动读取过多（旧）\n\n旧方案已归档。\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_project_detection_from_agents_file(self):
        code_root = self.root / "code" / "demo"
        code_root.mkdir(parents=True)
        (code_root / "AGENTS.md").write_text("**当前项目名：`demo`**\n", encoding="utf-8")
        self.assertEqual(detect_project(self.memory, cwd=str(code_root)), "demo")

    def test_todo_slice_excludes_other_projects(self):
        text = (self.memory / "Todo.md").read_text(encoding="utf-8")
        section = extract_todo_section(text, "demo")
        self.assertIn("finish bounded retrieval", section)
        self.assertNotIn("unrelated", section)

    def test_boot_pack_is_small_and_does_not_read_index(self):
        pack = build_boot_pack(self.memory, project="demo", budget=6000)
        text = pack["text"]
        self.assertIn("Global hot memory", text)
        self.assertIn("Project overview", text)
        self.assertIn("Project state", text)
        self.assertIn("finish bounded retrieval", text)
        self.assertNotIn("SHOULD_NOT_APPEAR_IN_BOOT", text)
        self.assertLessEqual(pack["chars"], 6000)
        self.assertIn("BOOT.md", pack["files"])

    def test_boot_pack_honors_budget(self):
        (self.project / "_overview.md").write_text("A" * 5000, encoding="utf-8")
        pack = build_boot_pack(self.memory, project="demo", budget=1200)
        self.assertLessEqual(pack["chars"], 1200)
        self.assertTrue(pack["truncated"])

    def test_query_finds_active_note_and_excludes_archived_by_default(self):
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertIn("Lessons/bounded-memory.md", paths)
        self.assertNotIn("Decisions/old-memory.md", paths)

    def test_query_can_include_inactive(self):
        result = search_memory(self.memory, "启动读取", project="demo", include_inactive=True)
        paths = [m["path"] for m in result["matches"]]
        self.assertIn("Decisions/old-memory.md", paths)

    def test_query_snippet_is_bounded(self):
        result = search_memory(self.memory, "启动读取", project="demo")
        self.assertTrue(result["matches"])
        self.assertLessEqual(len(result["matches"][0]["snippet"]), 430)

    def test_query_excludes_other_project_scope(self):
        (self.memory / "Lessons" / "other-project.md").write_text(
            "---\ntype: lesson\nscope: other\nstatus: active\n---\n# 启动读取\n\n其他项目。\n",
            encoding="utf-8",
        )
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertNotIn("Lessons/other-project.md", paths)

    def test_query_cli_respects_budget(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "memory_query.py"), "启动读取",
             "--memory-dir", str(self.memory), "--project", "demo",
             "--json", "--budget", "150"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertLessEqual(payload["chars"], 150)

    def test_cli_returns_json_with_bounded_text(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "memory_boot.py"),
             "--memory-dir", str(self.memory), "--project", "demo", "--json", "--budget", "1000"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["project"], "demo")
        self.assertLessEqual(payload["chars"], 1000)


if __name__ == "__main__":
    unittest.main()
