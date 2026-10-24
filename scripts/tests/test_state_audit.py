from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from state_audit import scan_states


class StateAuditTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Path(self.temp.name) / "Memory"
        self.projects = self.memory / "Projects"
        self.projects.mkdir(parents=True)
        (self.projects / "missing").mkdir()
        (self.memory / "Todo.md").write_text(
            "# Todo\n\n## current\n\n- task\n\n## stale（说明）\n\n- task\n\n"
            "## placeholder\n\n- task\n\n## missing\n\n- task\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write_state(self, project: str, text: str) -> None:
        directory = self.projects / project
        directory.mkdir()
        (directory / "_state.md").write_text(text, encoding="utf-8")

    def test_scan_reports_missing_placeholder_stale_and_oversize(self):
        self._write_state(
            "current",
            "---\nupdated: 2026-10-20\n---\n## 当前目标\n- ship\n",
        )
        self._write_state(
            "stale",
            "---\nupdated: 2026-01-01\n---\n## 当前目标\n- old\n",
        )
        self._write_state(
            "placeholder",
            "---\nupdated: 2026-10-20\n---\nP0 切换时建立；待项目会话核对。\n",
        )

        result = scan_states(self.memory, max_age_days=30, today=date(2026, 10, 24))

        self.assertEqual(result["scanned"], 4)
        self.assertEqual(result["missing"], ["missing"])
        self.assertEqual(result["placeholder"], ["placeholder"])
        self.assertEqual(result["stale"], ["stale"])
        self.assertEqual(result["too_large"], [])

    def test_scan_marks_state_over_1000_chars(self):
        self._write_state(
            "current",
            "---\nupdated: 2026-10-20\n---\n" + ("x" * 1001),
        )
        result = scan_states(self.memory, today=date(2026, 10, 24))
        self.assertEqual(result["too_large"], ["current"])

    def test_strict_fails_when_no_active_projects(self):
        empty = Path(self.temp.name) / "EmptyMemory"
        (empty / "Projects").mkdir(parents=True)
        env = os.environ.copy()
        env["AI_MEMORY_DIR"] = str(empty)
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "state_audit.py"), "--strict"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)

    def test_missing_updated_is_reported_and_strict_fails(self):
        self._write_state("current", "## 当前目标\n- ship\n")
        result = scan_states(self.memory, today=date(2026, 10, 24))
        self.assertEqual(result["missing_updated"], ["current"])

    def test_cli_json_and_strict_exit(self):
        self._write_state(
            "current",
            "---\nupdated: 2026-10-20\n---\n## 当前目标\n- ship\n",
        )
        self._write_state(
            "stale",
            "---\nupdated: 2026-01-01\n---\n## 当前目标\n- old\n",
        )
        self._write_state("placeholder", "待项目会话核对\n")
        env = os.environ.copy()
        env["AI_MEMORY_DIR"] = str(self.memory)

        report = subprocess.run(
            [sys.executable, str(SCRIPTS / "state_audit.py"), "--json"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        strict = subprocess.run(
            [sys.executable, str(SCRIPTS / "state_audit.py"), "--json", "--strict"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

        self.assertEqual(report.returncode, 0, report.stderr)
        payload = json.loads(report.stdout)
        self.assertEqual(payload["scanned"], 4)
        self.assertEqual(strict.returncode, 1, strict.stderr)


if __name__ == "__main__":
    unittest.main()
