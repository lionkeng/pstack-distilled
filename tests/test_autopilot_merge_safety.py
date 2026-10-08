from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AutopilotMergeSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pstack-merge-safety-test-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.repo = root / "repo"
        self.repo.mkdir()
        # Keep developer Git configuration, hooks, and repository variables out.
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_DATE="2026-01-01T00:00:00+0000",
            GIT_COMMITTER_DATE="2026-01-01T00:00:00+0000",
            GIT_TERMINAL_PROMPT="0",
        )
        self._git("init", "--quiet", "--template=", "-b", "main")
        self._git("config", "user.name", "Merge Safety Test")
        self._git("config", "user.email", "merge-safety@example.invalid")
        self._git("config", "core.hooksPath", str(root / "no-hooks"))
        self._write("dependency.py", "def value():\n    return 1\n")
        self._write("app.py", "from dependency import value\n\ndef result():\n    return int(value()) + 1\n")
        self._write(
            "test_runtime.py",
            "import unittest\n"
            "from app import result\n\n"
            "class RuntimeTest(unittest.TestCase):\n"
            "    def test_result(self):\n"
            "        self.assertEqual(result(), 2)\n",
        )
        self.base = self._commit("baseline: accept integer or string dependency values")

    def _run(self, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            cwd=self.repo,
            env=self.env,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30,
        )

    def _git(self, *args: str, input_text: str | None = None) -> str:
        result = self._run("git", *args, input_text=input_text)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def _write(self, name: str, content: str) -> None:
        (self.repo / name).write_text(content, encoding="utf-8")

    def _commit(self, message: str) -> str:
        self._git("add", "--all")
        self._git("commit", "--quiet", "-m", message)
        return self._git("rev-parse", "HEAD")

    def _checks(self) -> subprocess.CompletedProcess[str]:
        # Fresh interpreters avoid cached modules; -B keeps bytecode out of Git.
        return self._run(sys.executable, "-B", "-m", "unittest", "-v", "test_runtime")

    def _patch_id(self, commit: str) -> str:
        patch = self._git("show", "--format=", "--no-ext-diff", commit)
        return self._git("patch-id", "--stable", input_text=patch + "\n").split()[0]

    def test_disjoint_clean_merge_and_same_patch_id_do_not_preserve_green_checks(self) -> None:
        baseline_checks = self._checks()
        self.assertEqual(baseline_checks.returncode, 0, baseline_checks.stderr)

        self._git("switch", "--quiet", "-c", "pr")
        self._write("app.py", "from dependency import value\n\ndef result():\n    return value() + 1\n")
        tested_head = self._commit("remove apparently redundant integer conversion")
        head_checks = self._checks()
        self.assertEqual(head_checks.returncode, 0, head_checks.stderr)
        original_patch_id = self._patch_id(tested_head)

        self._git("switch", "--quiet", "main")
        self._write("dependency.py", 'def value():\n    return "1"\n')
        current_trunk = self._commit("return the dependency value as a string")
        trunk_checks = self._checks()
        self.assertEqual(trunk_checks.returncode, 0, trunk_checks.stderr)

        # These are the old shortcut's conditions: trunk advanced, paths are
        # disjoint, both heads are green, and merge-tree reports no conflict.
        self.assertNotEqual(current_trunk, self.base)
        self.assertEqual(self._git("merge-base", tested_head, current_trunk), self.base)
        stale_head_gate = self._run("git", "merge-base", "--is-ancestor", current_trunk, tested_head)
        self.assertEqual(stale_head_gate.returncode, 1, stale_head_gate.stderr)
        pr_paths = set(self._git("diff", "--name-only", self.base, tested_head).splitlines())
        trunk_paths = set(self._git("diff", "--name-only", self.base, current_trunk).splitlines())
        self.assertEqual(pr_paths, {"app.py"})
        self.assertEqual(trunk_paths, {"dependency.py"})
        self.assertTrue(pr_paths.isdisjoint(trunk_paths))
        merged_tree = self._git("merge-tree", "--write-tree", tested_head, current_trunk)
        self.assertEqual(self._git("cat-file", "-t", merged_tree), "tree")

        self._git("switch", "--quiet", "-c", "merged", tested_head)
        self._git("merge", "--quiet", "--no-ff", "-m", "integrate PR and trunk", current_trunk)
        self.assertEqual(self._git("rev-parse", "HEAD^{tree}"), merged_tree)
        merged_checks = self._checks()
        self.assertEqual(merged_checks.returncode, 1, merged_checks.stdout + merged_checks.stderr)
        self.assertIn("TypeError", merged_checks.stderr)
        self.assertIn("test_result", merged_checks.stderr)

        # A fresh rebase has exactly the same patch-id, but its new runtime
        # context fails. Rerunning checks catches what reused green checks miss.
        self._git("switch", "--quiet", "pr")
        self._git("rebase", current_trunk)
        rebased_head = self._git("rev-parse", "HEAD")
        self.assertNotEqual(rebased_head, tested_head)
        self.assertEqual(self._git("rev-parse", "HEAD^"), current_trunk)
        self.assertEqual(self._git("rev-parse", "HEAD^{tree}"), merged_tree)
        self.assertEqual(self._patch_id(rebased_head), original_patch_id)
        updated_head_gate = self._run("git", "merge-base", "--is-ancestor", current_trunk, rebased_head)
        self.assertEqual(updated_head_gate.returncode, 0, updated_head_gate.stderr)
        rebased_checks = self._checks()
        self.assertEqual(rebased_checks.returncode, 1, rebased_checks.stdout + rebased_checks.stderr)
        self.assertIn("TypeError", rebased_checks.stderr)
        self.assertIn("test_result", rebased_checks.stderr)


if __name__ == "__main__":
    unittest.main()
