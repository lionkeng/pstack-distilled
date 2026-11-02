from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT = PROJECT_ROOT / "skills/poteto-mode/scripts/worktree-audit.sh"
PLAYBOOK = PROJECT_ROOT / "skills/poteto-mode/playbooks/worktree-cleanup.md"


class WorktreeAuditTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="pstack-audit-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git = shutil.which("git")
        self.assertIsNotNone(self.git)
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        self.env.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
            PSTACK_CONVERSATION_HISTORY_DIR="",
        )
        self._git("init", "--quiet", "--template=", "-b", "main")
        self._git("config", "user.name", "Audit Test")
        self._git("config", "user.email", "audit@example.invalid")
        self._git("config", "core.hooksPath", str(self.root / "no-hooks"))
        (self.repo / "tracked.txt").write_text("committed\n")
        (self.repo / ".gitignore").write_text("*.db\n")
        self._git("add", "--all")
        self._git("commit", "--quiet", "-m", "fixture")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in ("gh", "origin"):
            script = self.bin / name
            script.write_text("#!/bin/sh\nexit 1\n")
            script.chmod(0o755)
        self.env["PATH"] = str(self.bin) + os.pathsep + self.env["PATH"]
        self.calls = self.root / "git-calls.jsonl"
        wrapper = self.bin / "git"
        wrapper.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "args = sys.argv[1:]\n"
            f"with open({str(self.calls)!r}, 'a') as log:\n"
            "    log.write(json.dumps(args) + '\\n')\n"
            "mode = os.environ.get('AUDIT_FAIL', '')\n"
            "failed = (mode == 'list' and args[:2] == ['worktree', 'list'])\n"
            "if args[:1] == ['-C']:\n"
            "    command = args[2:]\n"
            "    failed |= mode == 'status' and command[:1] == ['status']\n"
            "    failed |= mode == 'head' and command == ['rev-parse', 'HEAD']\n"
            "    failed |= mode == 'untracked' and command[:1] == ['ls-files'] and '--ignored' not in command\n"
            "    failed |= mode == 'ignored' and command[:1] == ['ls-files'] and '--ignored' in command\n"
            "if failed:\n"
            "    print('injected Git failure', file=sys.stderr)\n"
            "    sys.exit(128)\n"
            f"os.execv({self.git!r}, [{self.git!r}, *args])\n"
        )
        wrapper.chmod(0o755)

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            [str(self.git), *args], cwd=self.repo, env=self.env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def _worktree(self, name: str) -> Path:
        path = self.root / name
        self._git("worktree", "add", "--quiet", "--detach", str(path), "main")
        return path

    def _audit(self, failure: str = "") -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(AUDIT), "-b", "main", str(self.repo)],
            env={**self.env, "AUDIT_FAIL": failure},
            capture_output=True, text=True, timeout=30,
        )

    def _rows(self, result: subprocess.CompletedProcess[str]) -> list[list[str]]:
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [line.split("\t") for line in result.stdout.splitlines() if not line.startswith(("#", "SIZE"))]
        for row in rows:
            self.assertEqual(len(row), 9, result.stdout)
        return rows

    def test_complete_paths_reach_git_and_stay_on_one_table_row(self) -> None:
        paths = [self._worktree(name) for name in ("with spaces", "with\ttab", "with\nnewline")]
        rows = self._rows(self._audit())
        self.assertEqual(len(rows), len(paths))
        self.assertTrue(all(row[3] == "clean" and row[7] == "safe" for row in rows), rows)
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        status_paths = {args[1] for args in calls if args[:1] == ["-C"] and args[2:3] == ["status"]}
        self.assertEqual(status_paths, {str(path) for path in paths})
        for path in paths:
            quoted = subprocess.check_output(["bash", "-c", 'printf "%q" "$1"', "_", str(path)], text=True)
            self.assertIn(quoted, [row[8] for row in rows])

    def test_unknown_local_files_are_held_and_preserved(self) -> None:
        for name, file in (("untracked", "new-feature.ts"), ("ignored", "local-only.db")):
            with self.subTest(kind=name):
                worktree = self._worktree(name)
                (worktree / file).write_bytes(b"valuable local data\x00\xff")
                (worktree / "link").symlink_to(file)
                before = ((worktree / file).read_bytes(), os.readlink(worktree / "link"))
                rows = self._rows(self._audit())
                row = next(row for row in rows if row[8] == str(worktree))
                self.assertEqual(row[3], "local-files")
                self.assertEqual(row[7], "hold-local-files")
                self.assertEqual(before, ((worktree / file).read_bytes(), os.readlink(worktree / "link")))

    def test_ignored_data_alone_is_held(self) -> None:
        worktree = self._worktree("ignored-only")
        (worktree / "local-only.db").write_text("cannot regenerate\n")
        row, = self._rows(self._audit())
        self.assertEqual(row[3:4] + row[7:8], ["local-files", "hold-local-files"])
        self.assertEqual((worktree / "local-only.db").read_text(), "cannot regenerate\n")

    def test_tracked_changes_and_locked_worktrees_are_held(self) -> None:
        changed = self._worktree("changed")
        (changed / "tracked.txt").write_text("uncommitted work\n")
        locked = self._worktree("locked")
        self._git("worktree", "lock", str(locked))
        rows = {row[8]: row for row in self._rows(self._audit())}
        self.assertEqual(rows[str(changed)][7], "hold-wip")
        self.assertEqual(rows[str(locked)][7], "hold-locked")

    def test_failed_queries_are_held_and_not_clean(self) -> None:
        self._worktree("candidate")
        for failure in ("head", "status", "untracked", "ignored"):
            with self.subTest(failure=failure):
                result = self._audit(failure)
                row, = self._rows(result)
                self.assertEqual(row[3], "error")
                self.assertEqual(row[7], "hold-error")
                self.assertIn("could not", result.stderr)

    def test_failed_enumeration_stops_the_audit(self) -> None:
        self._worktree("candidate")
        result = self._audit("list")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("could not list worktrees", result.stderr)
        self.assertNotIn("\tsafe\t", result.stdout)

    def test_generated_cleanup_instructions_preserve_unknown_data(self) -> None:
        text = PLAYBOOK.read_text()
        self.assertIn("untracked and ignored", text)
        self.assertIn("explicit disposition", text)
        self.assertIn("ordinary `git worktree remove <path>`", text)
        self.assertIn("If removal refuses", text)
        self.assertNotIn("scratch:N", text)
        self.assertNotIn("git worktree remove --force", text)
        self.assertNotIn("`rm -rf`", text)


if __name__ == "__main__":
    unittest.main()
