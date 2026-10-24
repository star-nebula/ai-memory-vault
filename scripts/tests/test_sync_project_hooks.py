from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import sync_memory_instructions as sync


class SyncProjectHookTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.code_root = self.root / "projects"
        self.target_dir = self.code_root / "group" / "demo"
        self.target_dir.mkdir(parents=True)
        self.target = self.target_dir / "AGENTS.md"
        self.target.write_text(
            sync.GENERATED_HEADER + "\n" + sync.GENERATED_MARKER + "\n\nold body\n",
            encoding="utf-8",
        )
        self.memory = self.root / "Memory"
        (self.memory / "Projects" / "demo").mkdir(parents=True)
        self.common = [
            patch.object(sync, "CODE_ROOT", str(self.code_root)),
            patch.object(sync, "MEMORY_ROOT", self.memory),
            patch.object(sync, "MEMORY_PROJECTS", self.memory / "Projects"),
            patch.object(sync, "BAK_DIR", self.root / "backup"),
            patch.object(sync, "minimal_body", return_value="new body"),
            patch.object(sync, "log", side_effect=lambda *_args, **_kwargs: None),
            patch.object(
                sync,
                "project_roots",
                return_value=({"demo": str(self.target_dir)}, {}),
            ),
        ]
        for item in self.common:
            item.start()
            self.addCleanup(item.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_deploy_updates_generated_hook_after_drift(self):
        self.assertEqual(sync.deploy_projects(check_only=False), 0)
        text = self.target.read_text(encoding="utf-8")
        self.assertIn("new body", text)
        self.assertNotIn("old body", text)
        self.assertTrue(any((self.root / "backup").glob("AGENTS.md.*.sync-bak-*")))

    def test_check_reports_drift_without_writing(self):
        before = self.target.read_text(encoding="utf-8")
        self.assertEqual(sync.deploy_projects(check_only=True), 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)

    def test_handwritten_hook_is_kept_unchanged(self):
        handwritten = "# 手写项目规则\n\n不要自动覆盖。\n"
        self.target.write_text(handwritten, encoding="utf-8")
        self.assertEqual(sync.deploy_projects(check_only=False), 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), handwritten)

    def test_header_only_file_is_not_treated_as_generated(self):
        handwritten = sync.GENERATED_HEADER + "\n\n手写内容。\n"
        self.target.write_text(handwritten, encoding="utf-8")
        self.assertEqual(sync.deploy_projects(check_only=False), 0)
        self.assertEqual(self.target.read_text(encoding="utf-8"), handwritten)

    def test_hook_text_uses_absolute_paths(self):
        text = sync.hook_text("demo", "body")
        self.assertIn(sync.GENERATED_MARKER, text)
        self.assertIn(str(sync.SCRIPT_DIR / "memory_boot.py"), text)
        self.assertIn(str(sync.MEMORY_ROOT / "Projects" / "demo" / "_overview.md"), text)
        self.assertNotIn("Memory\\Memory\\", text)

    def test_backup_names_include_target_hash(self):
        other = self.target_dir / "OTHER.md"
        other.write_text("other", encoding="utf-8")
        first = sync.backup_file(str(self.target))
        second = sync.backup_file(str(other))
        self.assertNotEqual(first, second)
        self.assertEqual(Path(first).read_text(encoding="utf-8"), self.target.read_text(encoding="utf-8"))
        self.assertEqual(Path(second).read_text(encoding="utf-8"), "other")

    def test_overview_root_requires_explicit_marker(self):
        overview = self.memory / "Projects" / "demo" / "_overview.md"
        overview.write_text(
            f"题材来源：`{self.target_dir}`\n",
            encoding="utf-8",
        )
        self.assertIsNone(sync.roots_from_overview("demo"))

        overview.write_text(
            f"代码根：`{self.target_dir}`\n",
            encoding="utf-8",
        )
        self.assertEqual(
            sync.roots_from_overview("demo"),
            str(self.target_dir),
        )


if __name__ == "__main__":
    unittest.main()
