from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path


HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent if (HERE.parent / "memory_review.py").is_file() else HERE
sys.path.insert(0, str(SCRIPTS))

from memory_review import scan_memory_review


class MemoryReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.memory = Path(self.temp.name) / "Memory"
        for layer in ("Preferences", "Plans", "Decisions", "Lessons", "Workflows"):
            (self.memory / layer).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, relative: str, text: str) -> None:
        (self.memory / relative).write_text(text, encoding="utf-8")

    def test_review_queue_covers_status_and_volatile_dates(self):
        self._write(
            "Lessons/missing-status.md",
            "---\ntype: lesson\nscope: global\n---\n# 稳定事实\n\n无状态字段。\n",
        )
        self._write(
            "Lessons/review.md",
            "---\ntype: lesson\nscope: global\nstatus: review\n---\n# 待复核\n\n内容。\n",
        )
        self._write(
            "Lessons/unverified.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# 工具路径\n\n工具路径 `E:\\Tools\\a.exe`。\n",
        )
        self._write(
            "Lessons/stale.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n"
            "verified_at: 2026-01-01\n---\n# 环境版本\n\n版本号已过期。\n",
        )
        self._write(
            "Lessons/stable.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n# 稳定原则\n\n不涉及环境。\n",
        )

        result = scan_memory_review(
            self.memory,
            today=date(2026, 10, 24),
            max_age_days=90,
        )

        self.assertEqual(result["scanned"], 5)
        self.assertEqual(result["counts"]["missing_status"], 1)
        self.assertEqual(result["counts"]["review_status"], 1)
        self.assertEqual(result["counts"]["volatile_unverified"], 1)
        self.assertEqual(result["counts"]["volatile_stale"], 1)
        self.assertNotIn(
            "Lessons/stable.md",
            {issue["path"] for issue in result["issues"]},
        )

    def test_inactive_notes_skip_freshness_debt(self):
        self._write(
            "Decisions/old.md",
            "---\ntype: decision\nscope: global\nstatus: superseded-by-[[new]]\n---\n"
            "# 旧路径\n\n旧工具路径 `C:\\Tools\\old.exe`。\n",
        )
        result = scan_memory_review(self.memory, today=date(2026, 10, 24))
        self.assertEqual(result["counts"]["volatile_unverified"], 0)

    def test_urls_are_not_volatile_but_paths_are(self):
        self._write(
            "Lessons/url.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# 链接\n\n参考 https://github.com/example/project。\n",
        )
        self._write(
            "Lessons/relative.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# 相对路径\n\n运行 `scripts/memory_boot.py`。\n",
        )
        self._write(
            "Lessons/posix.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n---\n"
            "# POSIX 路径\n\n读取 `/usr/local/bin/tool`。\n",
        )
        result = scan_memory_review(self.memory, today=date(2026, 10, 24))
        volatile = {
            issue["path"]
            for issue in result["issues"]
            if issue["code"] == "volatile_unverified"
        }
        self.assertNotIn("Lessons/url.md", volatile)
        self.assertIn("Lessons/relative.md", volatile)
        self.assertIn("Lessons/posix.md", volatile)

    def test_invalid_and_future_statuses_are_reported(self):
        self._write(
            "Lessons/invalid.md",
            "---\ntype: lesson\nscope: global\nstatus: activ\n---\n"
            "# 拼写错误\n\n普通内容。\n",
        )
        self._write(
            "Lessons/future.md",
            "---\ntype: lesson\nscope: global\nstatus: active\n"
            "verified_at: 2099-01-01\n---\n# 未来核验\n\n工具路径 `E:\\Tools\\x.exe`。\n",
        )
        result = scan_memory_review(self.memory, today=date(2026, 10, 24))
        self.assertEqual(result["counts"]["invalid_status"], 1)
        self.assertEqual(result["counts"]["volatile_future"], 1)

    def test_structural_file_without_frontmatter_is_exempt(self):
        self._write(
            "Workflows/instructions.md",
            "# 部署真源\n\n工具路径 `E:\\Tools\\a.exe`。\n",
        )
        result = scan_memory_review(self.memory, today=date(2026, 10, 24))
        self.assertEqual(result["scanned"], 0)
        self.assertEqual(result["issues"], [])

    def test_cli_strict_returns_one_and_json_contains_counts(self):
        self._write(
            "Lessons/review.md",
            "---\ntype: lesson\nscope: global\nstatus: review\n---\n# 待复核\n\n内容。\n",
        )
        env = os.environ.copy()
        env["AI_MEMORY_DIR"] = str(self.memory)
        completed = subprocess.run(
            [sys.executable, str(SCRIPTS / "memory_review.py"), "--json", "--strict"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(completed.returncode, 1, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertEqual(payload["counts"]["review_status"], 1)


if __name__ == "__main__":
    unittest.main()
