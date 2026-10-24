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
        self.target_dir = self.code_root / "demo"
        self.target_dir.mkdir(parents=True)
        self.target = self.target_dir / "AGENTS.md"
        self.target.write_text(
            "# 记忆库 · 项目级入口（自动生成，勿手改）\n\nold body\n",
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
        self.assertTrue(any((self.root / "backup").glob("AGENTS.md.sync-bak-*")))

    def test_check_reports_drift_without_writing(self):
        before = self.target.read_text(encoding="utf-8")
        self.assertEqual(sync.deploy_projects(check_only=True), 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), before)


if __name__ == "__main__":
    unittest.main()
