from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
VERIFY = PROJECT_ROOT / "scripts" / "verify_lock.py"


class VerifyLockTest(unittest.TestCase):
    def _run(self, repo_root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFY), "--repo-root", str(repo_root)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def test_checked_in_artifacts_match_lock(self) -> None:
        result = self._run(PROJECT_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("verified checked-in artifacts", result.stdout)

    def test_generated_tree_drift_is_detected_offline(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-lock-test-") as name:
            root = Path(name)
            for filename in ("LICENSE", "sync-config.json", "upstream.lock.json"):
                shutil.copy2(PROJECT_ROOT / filename, root / filename)
            shutil.copytree(PROJECT_ROOT / "skills", root / "skills")
            alpha = root / "skills/arena/SKILL.md"
            alpha.write_text(alpha.read_text(encoding="utf-8") + "\nDrift.\n", encoding="utf-8")

            result = self._run(root)

            self.assertEqual(result.returncode, 1)
            self.assertIn("generated output digest drift", result.stderr)


if __name__ == "__main__":
    unittest.main()
