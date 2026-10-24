from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import memory_boot
import memory_query
from memory_boot import build_boot_pack
from memory_common import InvalidProjectError, detect_project, extract_todo_section
from memory_query import search_memory


class MemoryAgentContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.memory = self.root / "workspace" / "Memory"
        self.project = self.memory / "Projects" / "demo"
        self.other = self.memory / "Projects" / "other"
        self.project.mkdir(parents=True)
        self.other.mkdir(parents=True)
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
        (self.other / "_overview.md").write_text(
            "---\ntype: project-fact\n---\n# Other\n\n启动读取 other project.\n",
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

    def test_project_detection_uses_code_root_not_group(self):
        code_root = self.root / "code" / "Projects" / "personal" / "demo"
        source = code_root / "src"
        source.mkdir(parents=True)
        (code_root / ".git").mkdir()
        (self.memory / "Projects" / "src").mkdir()
        self.assertEqual(detect_project(self.memory, cwd=str(source)), "demo")

    def test_nested_agents_without_declaration_continues_upward(self):
        repo = self.root / "repo"
        package = repo / "packages" / "foo"
        package.mkdir(parents=True)
        (repo / ".git").mkdir()
        (repo / "AGENTS.md").write_text("**当前项目名：`demo`**\n", encoding="utf-8")
        (package / "AGENTS.md").write_text("普通包规则，无项目声明。\n", encoding="utf-8")
        self.assertEqual(detect_project(self.memory, cwd=str(package)), "demo")

    def test_prose_about_project_name_is_not_a_declaration(self):
        code_root = self.root / "code" / "demo"
        code_root.mkdir(parents=True)
        (code_root / "AGENTS.md").write_text("当前项目名不预填：按工作目录判断。\n", encoding="utf-8")
        self.assertEqual(detect_project(self.memory, cwd=str(code_root)), "demo")

    def test_invalid_project_declaration_fails_closed(self):
        code_root = self.root / "code" / "bad"
        code_root.mkdir(parents=True)
        (code_root / "AGENTS.md").write_text("**当前项目名：`../../outside`**\n", encoding="utf-8")
        with self.assertRaises(InvalidProjectError):
            detect_project(self.memory, cwd=str(code_root))

    def test_explicit_project_traversal_is_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "_overview.md").write_text("OUTSIDE_SECRET_CONTENT", encoding="utf-8")
        with self.assertRaises(InvalidProjectError):
            build_boot_pack(self.memory, project="../../outside")
        with self.assertRaises(InvalidProjectError):
            search_memory(self.memory, "secret", project="../../outside")

    def test_todo_slice_excludes_other_projects(self):
        text = (self.memory / "Todo.md").read_text(encoding="utf-8")
        section = extract_todo_section(text, "demo")
        self.assertIn("finish bounded retrieval", section)
        self.assertNotIn("unrelated", section)

    def test_todo_slice_accepts_trailing_parenthetical(self):
        section = extract_todo_section("## demo（说明）\n\n- task\n", "demo")
        self.assertIn("- task", section)

    def test_boot_pack_is_small_and_does_not_read_index(self):
        with patch("memory_boot.read_text", wraps=memory_boot.read_text) as read_mock:
            pack = build_boot_pack(self.memory, project="demo", budget=6000)
        text = pack["text"]
        self.assertIn("Global hot memory", text)
        self.assertIn("Project overview", text)
        self.assertIn("Project state", text)
        self.assertIn("finish bounded retrieval", text)
        self.assertNotIn("SHOULD_NOT_APPEAR_IN_BOOT", text)
        self.assertNotIn("type: project-fact", text)
        self.assertLessEqual(pack["chars"], 6000)
        self.assertIn("BOOT.md", pack["files"])
        read_names = [call.args[0].name for call in read_mock.call_args_list]
        self.assertNotIn("_index.md", read_names)

    def test_boot_truncation_fields_are_separate(self):
        (self.project / "_overview.md").write_text("A" * 5000, encoding="utf-8")
        section_only = build_boot_pack(self.memory, project="demo", budget=6000)
        self.assertTrue(section_only["section_truncated"])
        self.assertFalse(section_only["budget_truncated"])
        total_cut = build_boot_pack(self.memory, project="demo", budget=1200)
        self.assertTrue(total_cut["section_truncated"])
        self.assertTrue(total_cut["budget_truncated"])

    def test_cost_gate_passes_content_debt_and_content_check_fails(self):
        fixture = self.root / "gate-fixture"
        shutil.copytree(SCRIPTS.parent / "starter" / "Memory", fixture / "Memory")
        memory = fixture / "Memory"
        project = memory / "Projects" / "demo"
        (project / "working").mkdir(parents=True)
        (project / "_overview.md").write_text("A" * 3000, encoding="utf-8")
        (project / "_state.md").write_text("state " * 80, encoding="utf-8")
        (project / "working" / "completed.md").write_text("", encoding="utf-8")
        (memory / "Todo.md").write_text("# Todo\n\n## demo\n\n- test\n", encoding="utf-8")
        env = os.environ.copy()
        env["AI_MEMORY_DIR"] = str(memory)
        cost_out = self.root / "cost.txt"
        content_out = self.root / "content.txt"
        cost = subprocess.run(
            [sys.executable, str(SCRIPTS / "todo_audit.py"), "--cost-check", "-o", str(cost_out)],
            cwd=str(fixture), env=env, capture_output=True, text=True, encoding="utf-8",
        )
        content = subprocess.run(
            [sys.executable, str(SCRIPTS / "todo_audit.py"), "--content-check", "-o", str(content_out)],
            cwd=str(fixture), env=env, capture_output=True, text=True, encoding="utf-8",
        )
        self.assertEqual(cost.returncode, 0, cost.stdout + cost.stderr)
        self.assertEqual(content.returncode, 1, content.stdout + content.stderr)
        self.assertIn("内容债", cost.stdout)
        self.assertIn("内容债", content.stderr)

    def test_boot_pack_honors_text_budget(self):
        (self.project / "_overview.md").write_text("A" * 5000, encoding="utf-8")
        pack = build_boot_pack(self.memory, project="demo", budget=1200)
        self.assertLessEqual(pack["chars"], 1200)
        self.assertTrue(pack["truncated"])
        self.assertGreater(pack["source_chars"], pack["chars"])

    def test_tiny_boot_budget_is_still_hard(self):
        pack = build_boot_pack(self.memory, project="demo", budget=5)
        self.assertLessEqual(len(pack["text"]), 5)
        self.assertLessEqual(pack["chars"], 5)

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

    def test_query_excludes_other_project_tree(self):
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertNotIn("Projects/other/_overview.md", paths)

    def test_project_lookup_is_case_insensitive_and_returns_actual_name(self):
        case_memory = self.root / "case-memory"
        (case_memory / "Projects" / "Demo").mkdir(parents=True)
        (case_memory / "Projects" / "Demo" / "_overview.md").write_text(
            "---\ntype: project-fact\n---\n# Demo\n\n启动读取 case project.\n",
            encoding="utf-8",
        )
        result = search_memory(case_memory, "启动读取", project="demo")
        self.assertTrue(result["matches"])
        self.assertEqual(result["matches"][0]["path"], "Projects/Demo/_overview.md")

    def test_project_query_does_not_read_other_project_tree(self):
        with patch("memory_query.read_text", wraps=memory_query.read_text) as read_mock:
            search_memory(self.memory, "启动读取", project="demo", include_history=True)
        read_parts = [call.args[0].relative_to(self.memory).parts for call in read_mock.call_args_list]
        self.assertFalse(any(parts[:2] == ("Projects", "other") for parts in read_parts))

    def test_query_without_project_defaults_to_global_only(self):
        result = search_memory(self.memory, "启动读取")
        self.assertEqual(result["matches"], [])
        result_all = search_memory(self.memory, "启动读取", all_projects=True)
        self.assertTrue(result_all["matches"])

    def test_review_status_is_searchable_by_default(self):
        (self.memory / "Lessons" / "review-status.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: review\n---\n# 启动读取\n\n待复核。\n",
            encoding="utf-8",
        )
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertIn("Lessons/review-status.md", paths)

    def test_project_query_fails_closed_without_scope(self):
        (self.memory / "Lessons" / "no-scope.md").write_text(
            "---\ntype: lesson\nstatus: active\n---\n# 启动读取\n\n无 scope。\n",
            encoding="utf-8",
        )
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertNotIn("Lessons/no-scope.md", paths)

    def test_bom_frontmatter_is_parsed_and_can_be_filtered(self):
        (self.memory / "Lessons" / "bom.md").write_text(
            "---\ntype: lesson\nscope: other\nstatus: archived-2026-Q3\n---\n# 启动读取\n\nBOM 文件。\n",
            encoding="utf-8-sig",
        )
        result = search_memory(self.memory, "启动读取", project="demo")
        paths = [m["path"] for m in result["matches"]]
        self.assertNotIn("Lessons/bom.md", paths)

    def test_cli_returns_compact_json(self):
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
        self.assertTrue(all("content" not in section for section in payload["sections"]))

    def test_query_cli_respects_text_budget(self):
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
        self.assertEqual(payload["budget_scope"], "text")


if __name__ == "__main__":
    unittest.main()
