from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import todo_audit


class TodoAuditShardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Path(self.temp.name) / "Memory"
        self.projects = self.memory / "Projects"
        self.working = self.projects / "demo" / "working"
        self.working.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def test_has_completed_accepts_legacy_file_or_quarter_shard(self):
        project = self.projects / "legacy"
        (project / "working").mkdir(parents=True)
        (project / "working" / "completed.md").write_text("legacy", encoding="utf-8")
        self.assertTrue(todo_audit.has_completed(project))

        project = self.projects / "sharded"
        (project / "working" / "completed").mkdir(parents=True)
        (project / "working" / "completed" / "2026-Q4.md").write_text("new", encoding="utf-8")
        self.assertTrue(todo_audit.has_completed(project))

        empty = self.projects / "empty"
        (empty / "working" / "completed").mkdir(parents=True)
        (empty / "working" / "completed" / "2026-Q4.md").write_text("", encoding="utf-8")
        self.assertFalse(todo_audit.has_completed(empty))

    def test_staging_scan_includes_journal_and_completed_shards(self):
        (self.working / "journal").mkdir()
        (self.working / "completed").mkdir()
        (self.working / "journal" / "2026-10.md").write_text("j" * 20, encoding="utf-8")
        (self.working / "completed" / "2026-Q4.md").write_text("c" * 10, encoding="utf-8")

        with patch.object(todo_audit, "PROJECTS_DIR", self.projects):
            result = todo_audit.scan_staging_volume()

        self.assertEqual(result["scanned"], 2)
        self.assertEqual(result["scanned_journal"], 1)
        self.assertEqual(
            {row["file"] for row in result["heaviest"]},
            {"journal/2026-10.md", "completed/2026-Q4.md"},
        )

    def test_claim_checks_read_sharded_journal_and_completed(self):
        todo = self.memory / "Todo.md"
        todo.write_text("# Todo\n", encoding="utf-8")
        (self.working / "journal").mkdir()
        (self.working / "completed").mkdir()
        (self.working / "journal" / "2026-10.md").write_text(
            "Todo → 「完成分片迁移」\n",
            encoding="utf-8",
        )
        (self.working / "completed" / "2026-Q4.md").write_text(
            "- 2026-10-24 完成分片迁移\n",
            encoding="utf-8",
        )

        with patch.object(todo_audit, "PROJECTS_DIR", self.projects), \
                patch.object(todo_audit, "MEMORY_DIR", self.memory):
            result = todo_audit.scan_todo_claims(todo)

        self.assertEqual(result["broken"], [])
        self.assertEqual(result["unverifiable"], [])

    def test_shard_health_rejects_bad_names_and_empty_files(self):
        (self.working / "journal").mkdir()
        (self.working / "completed").mkdir()
        (self.working / "journal" / "scratch.md").write_text("x", encoding="utf-8")
        (self.working / "journal" / "2026-10.md").write_text("", encoding="utf-8")
        (self.working / "completed" / "2026-Q4.md").write_text("", encoding="utf-8")

        with patch.object(todo_audit, "PROJECTS_DIR", self.projects):
            result = todo_audit.scan_shard_health()

        self.assertEqual(
            [item["reason"] for item in result["invalid"]],
            ["bad-name"],
        )
        self.assertEqual(result["empty"], [
            {"kind": "journal", "file": "demo/working/journal/2026-10.md", "reason": "empty"},
            {"kind": "completed", "file": "demo/working/completed/2026-Q4.md", "reason": "empty"},
        ])

    def test_legacy_journal_does_not_enter_pressure_face(self):
        (self.working / "journal.md").write_text(
            "x" * (todo_audit.LIMIT_STAGING_CHARS + 1),
            encoding="utf-8",
        )
        (self.working / "journal").mkdir()
        (self.working / "journal" / "2026-10.md").write_text("small", encoding="utf-8")

        with patch.object(todo_audit, "PROJECTS_DIR", self.projects):
            result = todo_audit.scan_staging_volume()

        self.assertEqual(result["over"], [])
        self.assertIn(
            "journal.md",
            {row["file"] for row in result["heaviest"]},
        )

    def test_scope_scan_covers_nested_shards(self):
        (self.working / "journal").mkdir()
        (self.working / "journal" / "2026-10.md").write_text(
            "---\ntype: journal\nscope: demo\n---\n# log\n",
            encoding="utf-8",
        )
        with patch.object(todo_audit, "PROJECTS_DIR", self.projects), \
                patch.object(todo_audit, "MEMORY_DIR", self.memory):
            result = todo_audit.scan_scope_vocab()
        self.assertIn(
            "Projects/demo/working/journal/2026-10.md",
            result["redundant"],
        )

    def test_legacy_plans_layer_is_not_scope_audited(self):
        plans = self.memory / "Plans"
        plans.mkdir()
        (plans / "legacy.md").write_text(
            "---\ntype: plan\nscope: missing-project\n---\n# legacy\n",
            encoding="utf-8",
        )
        with patch.object(todo_audit, "PROJECTS_DIR", self.projects), \
                patch.object(todo_audit, "MEMORY_DIR", self.memory):
            result = todo_audit.scan_scope_vocab()
        self.assertEqual(result["bad"], [])


if __name__ == "__main__":
    unittest.main()
