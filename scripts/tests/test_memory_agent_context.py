from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import memory_boot
import memory_query
from memory_boot import build_boot_pack
from memory_common import DEFAULT_BUDGET, InvalidProjectError, detect_project, extract_todo_section, find_memory_dir
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
        (self.memory / "Todo.md").write_text(
            "# Todo\n\n## demo\n\n- finish bounded retrieval\n\n## other\n\n- unrelated\n",
            encoding="utf-8",
        )
        (self.project / "_overview.md").write_text(
            "---\ntype: project-fact\n---\n# Demo\n\nProject overview.\n",
            encoding="utf-8",
        )
        (self.project / "_state.md").write_text(
            "---\ntype: project-fact\nstatus: active\nupdated: 2026-10-23\n---\n"
            "# State\n\nCurrent goal: validate P0.\n",
            encoding="utf-8",
        )
        (self.other / "_overview.md").write_text(
            "---\ntype: project-fact\n---\n# Other\n\n启动读取 other project.\n",
            encoding="utf-8",
        )
        (self.memory / "Lessons" / "bounded-memory.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\nupdated: 2026-10-23\n"
            "tags: [memory, retrieval]\n---\n# 启动读取过多\n\n按项目切片并使用有界检索，避免预读整棵记忆树。\n",
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

    def test_memory_discovery_prefers_root_memory_over_nested_vault_copy(self):
        workspace = self.root / "discovery"
        primary = workspace / "Memory"
        nested = workspace / "vault" / "Memory"
        primary.mkdir(parents=True)
        nested.mkdir(parents=True)
        (primary / "BOOT.md").write_text("primary", encoding="utf-8")
        (nested / "BOOT.md").write_text("nested", encoding="utf-8")

        self.assertEqual(find_memory_dir(start=str(workspace)), primary.resolve())

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

    def test_boot_pack_is_small_and_reads_only_whitelisted_files(self):
        with patch("memory_boot.read_text", wraps=memory_boot.read_text) as read_mock:
            pack = build_boot_pack(self.memory, project="demo", budget=6000)
        text = pack["text"]
        self.assertIn("Global hot memory", text)
        self.assertIn("Project overview", text)
        self.assertIn("Project state", text)
        self.assertIn("finish bounded retrieval", text)
        self.assertNotIn("type: project-fact", text)
        self.assertLessEqual(pack["chars"], 6000)
        self.assertIn("BOOT.md", pack["files"])
        self.assertEqual(pack["state_health"]["status"], "active")
        self.assertEqual(pack["state_health"]["updated"], "2026-10-23")
        self.assertFalse(pack["state_health"]["placeholder"])
        read_names = {call.args[0].name for call in read_mock.call_args_list}
        self.assertEqual(read_names, {"BOOT.md", "_overview.md", "_state.md", "Todo.md"})

    def test_boot_pack_signals_placeholder_state(self):
        (self.project / "_state.md").write_text(
            "---\ntype: project-fact\nstatus: active\nupdated: 2026-10-23\n---\n"
            "# State\n\nP0 切换时建立；待项目会话核对。\n",
            encoding="utf-8",
        )
        pack = build_boot_pack(self.memory, project="demo", budget=6000)
        self.assertTrue(pack["state_health"]["placeholder"])
        self.assertIn("placeholder=yes", pack["text"])

    def test_boot_truncation_fields_are_separate(self):
        (self.project / "_overview.md").write_text("A" * 5000, encoding="utf-8")
        section_only = build_boot_pack(self.memory, project="demo", budget=6000)
        self.assertTrue(section_only["section_truncated"])
        self.assertFalse(section_only["budget_truncated"])
        total_cut = build_boot_pack(self.memory, project="demo", budget=1200)
        self.assertTrue(total_cut["section_truncated"])
        self.assertTrue(total_cut["budget_truncated"])

    def test_boot_budget_covers_all_section_caps_and_overhead(self):
        (self.memory / "BOOT.md").write_text("B" * 3000, encoding="utf-8")
        (self.project / "_overview.md").write_text("O" * 3000, encoding="utf-8")
        (self.project / "_state.md").write_text(
            "---\ntype: project-fact\nstatus: active\nupdated: 2026-10-23\n---\n"
            + "S" * 1500,
            encoding="utf-8",
        )
        (self.memory / "Todo.md").write_text(
            "# Todo\n\n## demo\n\n" + "T" * 1800,
            encoding="utf-8",
        )

        pack = build_boot_pack(self.memory, project="demo", budget=DEFAULT_BUDGET)

        self.assertTrue(pack["section_truncated"])
        self.assertFalse(pack["budget_truncated"])

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

    def test_query_treats_rejected_as_inactive(self):
        (self.memory / "Decisions" / "rejected.md").write_text(
            "---\ntype: decision\nscope: demo\nstatus: rejected-no\n---\n"
            "# 拒绝路径\n\n不再采用。\n",
            encoding="utf-8",
        )
        default = search_memory(self.memory, "拒绝路径", project="demo")
        included = search_memory(
            self.memory,
            "拒绝路径",
            project="demo",
            include_inactive=True,
        )
        self.assertEqual(default["matches"], [])
        self.assertIn(
            "Decisions/rejected.md",
            {match["path"] for match in included["matches"]},
        )

    def test_query_reports_missing_status_as_unset(self):
        (self.memory / "Lessons" / "no-status.md").write_text(
            "---\ntype: lesson\nscope: demo\n---\n# 无状态命中\n\n旧笔记。\n",
            encoding="utf-8",
        )
        result = search_memory(self.memory, "无状态命中", project="demo")
        self.assertEqual(result["matches"][0]["status"], "unset")

    def test_query_history_can_reach_sharded_journal(self):
        working = self.project / "working" / "journal"
        working.mkdir(parents=True)
        (working / "2026-10.md").write_text(
            "---\ntype: journal\n---\n# 启动读取分片\n\n只在使用历史检索时返回。\n",
            encoding="utf-8",
        )
        default = search_memory(self.memory, "启动读取分片", project="demo")
        history = search_memory(
            self.memory,
            "启动读取分片",
            project="demo",
            include_history=True,
        )
        self.assertEqual(default["matches"], [])
        self.assertEqual(
            [match["path"] for match in history["matches"]],
            ["Projects/demo/working/journal/2026-10.md"],
        )

    def test_query_filters_sharded_history_by_date_window(self):
        working = self.project / "working" / "journal"
        working.mkdir(parents=True)
        (working / "2026-09.md").write_text(
            "---\ntype: journal\n---\n# 时间窗命中 九月\n\n旧记录。\n",
            encoding="utf-8",
        )
        (working / "2026-10.md").write_text(
            "---\ntype: journal\n---\n# 时间窗命中 十月\n\n新记录。\n",
            encoding="utf-8",
        )
        with patch("memory_query.read_text", wraps=memory_query.read_text) as read_mock:
            result = search_memory(
                self.memory,
                "时间窗命中",
                project="demo",
                include_history=True,
                since=date(2026, 10, 1),
            )
        read_names = {call.args[0].name for call in read_mock.call_args_list}
        self.assertNotIn("2026-09.md", read_names)
        self.assertIn("2026-10.md", read_names)
        self.assertEqual(
            [match["path"] for match in result["matches"]],
            ["Projects/demo/working/journal/2026-10.md"],
        )
        self.assertEqual(result["matches"][0]["date_from"], "2026-10-01")
        self.assertEqual(result["matches"][0]["date_to"], "2026-10-31")

    def test_query_skips_malformed_shard_dates_instead_of_aborting(self):
        working = self.project / "working" / "journal"
        working.mkdir(parents=True)
        (working / "2026-13.md").write_text(
            "---\ntype: journal\n---\n# bad shard\n\nmalformed date note\n",
            encoding="utf-8",
        )
        (working / "2026-10.md").write_text(
            "---\ntype: journal\n---\n## 2026-10-24\n\nvalid shard result\n",
            encoding="utf-8",
        )
        completed = self.project / "working" / "completed"
        completed.mkdir(parents=True)
        (completed / "0000-Q1.md").write_text(
            "---\ntype: completed\n---\n# malformed shard result\n",
            encoding="utf-8",
        )

        result = search_memory(
            self.memory,
            "shard result",
            project="demo",
            include_history=True,
            since=date(2026, 10, 1),
        )

        self.assertEqual(
            [match["path"] for match in result["matches"]],
            ["Projects/demo/working/journal/2026-10.md"],
        )

    def test_all_projects_cli_overrides_detected_project(self):
        code_root = self.root / "code" / "demo"
        code_root.mkdir(parents=True)
        (code_root / "AGENTS.md").write_text("**当前项目名：`demo`**\n", encoding="utf-8")
        (self.other / "cross-project.md").write_text(
            "---\ntype: project-fact\nstatus: active\n---\n"
            "# 跨项目查询目标\n\nneedle-across-projects\n",
            encoding="utf-8",
        )
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "memory_query.py"),
                "needle-across-projects",
                "--memory-dir",
                str(self.memory),
                "--cwd",
                str(code_root),
                "--all-projects",
                "--json",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertIn(
            "Projects/other/cross-project.md",
            {match["path"] for match in payload["matches"]},
        )

    def test_short_multiword_query_matches_nonadjacent_tokens(self):
        (self.memory / "Lessons" / "short-tokens.md").write_text(
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# Short tokens\n\nAI is useful, and ML is one application.\n",
            encoding="utf-8",
        )

        result = search_memory(self.memory, "ai ml")

        self.assertIn(
            "Lessons/short-tokens.md",
            {match["path"] for match in result["matches"]},
        )

    def test_query_filters_by_layer(self):
        (self.memory / "Decisions" / "layer-decision.md").write_text(
            "---\ntype: decision\nscope: demo\nstatus: implemented\n---\n"
            "# 层级过滤命中\n\n决策层。\n",
            encoding="utf-8",
        )
        (self.memory / "Lessons" / "layer-lesson.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\n---\n"
            "# 层级过滤命中\n\n教训层。\n",
            encoding="utf-8",
        )
        result = search_memory(
            self.memory,
            "层级过滤命中",
            project="demo",
            layers=["Lessons"],
        )
        self.assertEqual(
            [match["path"] for match in result["matches"]],
            ["Lessons/layer-lesson.md"],
        )

    def test_query_rejects_unknown_layer(self):
        with self.assertRaisesRegex(ValueError, "unknown layers"):
            search_memory(
                self.memory,
                "层级过滤命中",
                project="demo",
                layers=["Decisons"],
            )

    def test_query_counts_undated_matching_notes_when_window_is_active(self):
        (self.memory / "Lessons" / "undated.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\n---\n"
            "# 无日期命中\n\n没有 created / updated。\n",
            encoding="utf-8",
        )
        result = search_memory(
            self.memory,
            "无日期命中",
            project="demo",
            since=date(2026, 10, 1),
        )
        self.assertEqual(result["matches"], [])
        self.assertEqual(result["undated_skipped"], 1)

    def test_query_uses_created_to_updated_range(self):
        (self.memory / "Lessons" / "long-range.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\n"
            "created: 2026-08-01\nupdated: 2026-10-01\n---\n"
            "# 跨期命中\n\n长期有效的结论。\n",
            encoding="utf-8",
        )
        result = search_memory(
            self.memory,
            "跨期命中",
            project="demo",
            since=date(2026, 8, 15),
            until=date(2026, 8, 31),
        )
        self.assertEqual(
            [match["path"] for match in result["matches"]],
            ["Lessons/long-range.md"],
        )
        self.assertEqual(result["matches"][0]["date_from"], "2026-08-01")
        self.assertEqual(result["matches"][0]["date_to"], "2026-10-01")

    def test_query_snippet_is_bounded(self):
        result = search_memory(self.memory, "启动读取", project="demo")
        self.assertTrue(result["matches"])
        self.assertLessEqual(len(result["matches"][0]["snippet"]), 430)

    def test_query_ignores_bare_number_noise_and_boosts_project_tree(self):
        (self.project / "query-target.md").write_text(
            "---\ntype: project-fact\nstatus: active\n---\n"
            "# PR #8 issue #9\n\n项目内目标记录。\n",
            encoding="utf-8",
        )
        (self.memory / "Lessons" / "numeric-noise.md").write_text(
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# 8 9\n\n" + "8 9 " * 50,
            encoding="utf-8",
        )
        (self.memory / "Lessons" / "substring-noise.md").write_text(
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# proxy issues\n\nproxy preparations and print providers; issues remain.\n",
            encoding="utf-8",
        )
        result = search_memory(
            self.memory,
            "home-pages PR #8 issue #9",
            project="demo",
        )
        paths = [match["path"] for match in result["matches"]]
        self.assertEqual(paths[0], "Projects/demo/query-target.md")
        self.assertNotIn("Lessons/numeric-noise.md", paths)
        self.assertNotIn("Lessons/substring-noise.md", paths)

    def test_query_reports_last_verification_date(self):
        (self.memory / "Lessons" / "verified-path.md").write_text(
            "---\ntype: lesson\nscope: demo\nstatus: active\n"
            "verified_at: 2026-10-24\n---\n# 路径验证\n\n工具路径已复核。\n",
            encoding="utf-8",
        )
        result = search_memory(self.memory, "工具路径已复核", project="demo")
        match = next(m for m in result["matches"] if m["path"] == "Lessons/verified-path.md")
        self.assertEqual(match["verified_at"], "2026-10-24")

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
