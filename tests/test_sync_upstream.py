from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Dict, Optional
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_LICENSE = """MIT License

Copyright (c) 2026 Upstream Author

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction.
"""
SYNC = PROJECT_ROOT / "scripts" / "sync_upstream.py"
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import sync_upstream as sync_module  # noqa: E402


class SyncUpstreamTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="pstack-sync-test-")
        self.root = Path(self.temporary.name)
        self.upstream = self.root / "upstream"
        self.downstream = self.root / "downstream"
        self.upstream.mkdir()
        self.downstream.mkdir()
        self.execution_sentinel = self.root / "UPSTREAM_SCRIPT_EXECUTED"
        self._git(self.upstream, "init", "--quiet", "-b", "main")
        self._git(self.upstream, "config", "user.name", "Sync Test")
        self._git(self.upstream, "config", "user.email", "sync-test@example.invalid")
        self._write_upstream_v1()
        self.v1_commit = self._commit_upstream("upstream v1")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _git(self, cwd: Path, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return result.stdout.strip()

    def _write(self, relative: str, content: str) -> None:
        path = self.upstream / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_upstream_v1(self) -> None:
        self._write("pstack/LICENSE", UPSTREAM_LICENSE)
        self._write(
            "pstack/.cursor-plugin/plugin.json",
            json.dumps({"name": "pstack", "version": "1.0.0", "license": "MIT"}) + "\n",
        )
        self._write(
            "pstack/skills/alpha/SKILL.md",
            """---
name: Alpha Skill
description: Use for /alpha when a Task reviewer should AskQuestion before using gpt-5.6-sol-max or gemini-3-pro.
disable-model-invocation: true
---

# Alpha

Use the Task tool from Cursor with `subagent_type: generalPurpose` and
`run_in_background: true`. Store local output under `.cursor/skills/alpha/`.
Read only the active workspace's `agent-transcripts/` directory.
List candidates under `<agent-transcripts>/*.jsonl`.
Use the control-skill path. Restacks run in cloud. When coordinating workers, nesting works to depth 3, and a nested spawn has the full Task schema including `environment`.
""",
        )
        self._write(
            "pstack/skills/beta/SKILL.md",
            """---
name: beta
description: Explain beta behavior. Use when beta is in scope.
---

# Beta

Keep this skill portable.

This statement has a note.[^1]

[^1]: Explanatory prose, not a resource link.
            """,
        )
        self._write(
            "pstack/skills/alpha/scripts/must-not-run.sh",
            f"#!/usr/bin/env bash\ntouch {self.execution_sentinel}\n",
        )
        (self.upstream / "pstack/skills/alpha/scripts/must-not-run.sh").chmod(0o755)
        self._write(
            "pstack/skills/no-comments/SKILL.md",
            """---
name: no-comments
description: Spawn Comment Sicko and review comments.
disable-model-invocation: true
---

# No comments

## Steps

1. Spawn `Task` with `subagent_type: "Comment Sicko"`. Pass the scope. Do not restate its rules.
""",
        )
        self._write(
            "pstack/agents/comment-sicko.md",
            """---
name: Comment Sicko
description: Review comments.
---

# Comment Sicko

Report comments that should be removed.
""",
        )

    def _configured_copyright(self) -> str:
        config = json.loads((PROJECT_ROOT / "sync-config.json").read_text(encoding="utf-8"))
        return config["license_copyright"]

    def _commit_upstream(self, message: str) -> str:
        self._git(self.upstream, "add", "-A")
        self._git(self.upstream, "commit", "--quiet", "-m", message)
        return self._git(self.upstream, "rev-parse", "HEAD")

    def _sync(self, *, check: bool = False, report: Optional[Path] = None) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(SYNC),
            "--repo-root",
            str(self.downstream),
            "--source",
            str(self.upstream),
            "--ref",
            "main",
        ]
        if check:
            command.append("--check")
        if report:
            command.extend(["--report-json", str(report)])
        return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def _snapshot_downstream(self) -> Dict[str, bytes]:
        return {
            path.relative_to(self.downstream).as_posix(): path.read_bytes()
            for path in sorted(self.downstream.rglob("*"))
            if path.is_file() and ".git" not in path.parts
        }

    def test_sync_updates_adds_deletes_and_is_idempotent(self) -> None:
        unrelated = self.downstream / "KEEP.txt"
        unrelated.write_text("manual content\n", encoding="utf-8")
        report = self.root / "report.json"

        first = self._sync(report=report)
        self.assertEqual(first.returncode, 0, first.stderr)
        alpha = (self.downstream / "skills/alpha/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('name: "alpha"', alpha)
        self.assertIn("license: MIT", alpha)
        self.assertIn('pstack-distilled-origin: "cursor/plugins/pstack/skills/alpha"', alpha)
        self.assertIn('pstack-distilled-activation: "explicit"', alpha)
        self.assertIn("## Portable execution", alpha)
        for forbidden in (
            "disable-model-invocation",
            "Cursor",
            "Task tool",
            "AskQuestion",
            "subagent_type",
            "run_in_background",
            "gpt-5.6-sol-max",
            "gemini-3-pro",
            ".cursor/",
            "agent-conversation records/",
            "control-skill",
            "cloud",
            "full delegation operation schema",
            "nesting works to depth",
        ):
            self.assertNotIn(forbidden, alpha)
        self.assertIn("available-model", alpha)
        self.assertIn("<host-conversation-history>/", alpha)
        self.assertIn("<host-conversation-history>/*.jsonl", alpha)
        beta = (self.downstream / "skills/beta/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("[^1]: Explanatory prose", beta)
        lock = json.loads((self.downstream / "upstream.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["source"]["commit"], self.v1_commit)
        self.assertEqual(lock["output"]["skill_count"], 3)
        shipped = (self.downstream / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Upstream Author", shipped)
        self.assertIn(self._configured_copyright(), shipped)
        self.assertTrue(shipped.startswith("MIT License\n"))
        self.assertIn("Permission is hereby granted", shipped)
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "manual content\n")
        self.assertTrue(json.loads(report.read_text(encoding="utf-8"))["changed"])
        self.assertFalse(self.execution_sentinel.exists(), "synchronization executed an upstream script")
        self.assertTrue((self.downstream / "skills/alpha/scripts/must-not-run.sh").is_file())
        reviewer = self.downstream / "skills/no-comments/references/comment-reviewer.md"
        self.assertTrue(reviewer.is_file())
        no_comments = (self.downstream / "skills/no-comments/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("independent deletion-first lens", no_comments)
        self.assertIn("apply the lens inline", no_comments)

        self._git(self.downstream, "init", "--quiet", "-b", "main")
        self._git(self.downstream, "config", "user.name", "Sync Test")
        self._git(self.downstream, "config", "user.email", "sync-test@example.invalid")
        self._git(self.downstream, "add", "-A")
        self._git(self.downstream, "commit", "--quiet", "-m", "generated v1")
        second = self._sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already synchronized", second.stdout)
        self.assertEqual(self._git(self.downstream, "status", "--porcelain"), "")

        self._write(
            "pstack/skills/alpha/SKILL.md",
            """---
name: alpha
description: Explain updated alpha behavior. Use when alpha changes.
---

# Alpha

Updated portable content.
""",
        )
        shutil.rmtree(self.upstream / "pstack/skills/beta")
        self._write(
            "pstack/skills/gamma/SKILL.md",
            """---
name: gamma
description: Explain gamma behavior. Use when gamma is in scope.
---

# Gamma

New portable content.
""",
        )
        v2_commit = self._commit_upstream("upstream v2")
        third = self._sync(report=report)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertIn("Updated portable content", (self.downstream / "skills/alpha/SKILL.md").read_text())
        self.assertFalse((self.downstream / "skills/beta").exists())
        self.assertTrue((self.downstream / "skills/gamma/SKILL.md").is_file())
        self.assertEqual(unrelated.read_text(encoding="utf-8"), "manual content\n")
        updated_lock = json.loads((self.downstream / "upstream.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(updated_lock["source"]["commit"], v2_commit)
        changes = json.loads(report.read_text(encoding="utf-8"))["changes"]
        self.assertIn("skills/gamma/SKILL.md", changes["added"])
        self.assertIn("skills/beta/SKILL.md", changes["deleted"])
        self.assertIn("skills/alpha/SKILL.md", changes["modified"])

    def test_check_reports_drift_without_mutating(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        self._write(
            "pstack/skills/beta/SKILL.md",
            """---
name: beta
description: Updated beta. Use when beta is in scope.
---

# Beta

Changed upstream.
""",
        )
        self._commit_upstream("change beta")
        check = self._sync(check=True)
        self.assertEqual(check.returncode, 1, check.stderr)
        self.assertIn("would update", check.stdout)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_generated_shell_resources_parse(self) -> None:
        shell_scripts = sorted((PROJECT_ROOT / "skills").rglob("*.sh"))
        self.assertTrue(shell_scripts, "expected generated shell resources")
        for shell_script in shell_scripts:
            with self.subTest(shell_script=shell_script):
                result = subprocess.run(
                    ["bash", "-n", str(shell_script)],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_host_specific_text_resource_is_rejected_without_execution_or_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        self._write(
            "pstack/skills/alpha/scripts/host-specific.sh",
            "#!/usr/bin/env bash\ncursor-agent --project .cursor/skills/demo\n",
        )
        self._commit_upstream("add host-specific script")

        failed = self._sync()

        self.assertEqual(failed.returncode, 2)
        self.assertIn("host-specific skill path", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)
        self.assertFalse(self.execution_sentinel.exists())

    def test_invalid_upstream_leaves_last_good_output_unchanged(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        self._write(
            "pstack/skills/alpha/SKILL.md",
            """---
name: alpha
description: Broken alpha. Use when alpha is in scope.
---

# Alpha

[Missing reference](references/does-not-exist.md)
""",
        )
        self._commit_upstream("break alpha")
        failed = self._sync()
        self.assertEqual(failed.returncode, 2)
        self.assertIn("failed validation", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_broken_reference_style_link_leaves_last_good_output_unchanged(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        self._write(
            "pstack/skills/alpha/SKILL.md",
            """---
name: alpha
description: Broken alpha. Use when alpha is in scope.
---

# Alpha

[Missing reference][resource]

[resource]: references/does-not-exist.md
""",
        )
        self._commit_upstream("break alpha reference-style link")

        failed = self._sync()

        self.assertEqual(failed.returncode, 2)
        self.assertIn("broken local link", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_source_directory_symlink_is_rejected_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        link = self.upstream / "pstack/skills/alpha/references-link"
        link.symlink_to("../../agents", target_is_directory=True)
        self._commit_upstream("add source symlink")
        failed = self._sync()
        self.assertEqual(failed.returncode, 2)
        self.assertIn("source symlinks are not imported", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_source_skills_root_symlink_is_rejected_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        skills = self.upstream / "pstack/skills"
        real_skills = self.upstream / "pstack/real-skills"
        skills.rename(real_skills)
        skills.symlink_to("real-skills", target_is_directory=True)
        self._commit_upstream("replace source skills root with symlink")

        failed = self._sync()

        self.assertEqual(failed.returncode, 2)
        self.assertIn("source skills directory cannot be a symlink", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_top_level_dangling_skill_symlink_is_rejected_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        link = self.upstream / "pstack/skills/ghost"
        link.symlink_to("../missing", target_is_directory=True)
        self._commit_upstream("add dangling top-level skill symlink")

        failed = self._sync()

        self.assertEqual(failed.returncode, 2)
        self.assertIn("top-level source symlinks are not imported", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_destination_directory_symlink_is_rejected(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        outside = self.root / "outside"
        outside.mkdir()
        link = self.downstream / "skills/alpha/linked-directory"
        link.symlink_to(outside, target_is_directory=True)

        failed = self._sync(check=True)

        self.assertEqual(failed.returncode, 2)
        self.assertIn("generated tree cannot contain symlinks", failed.stderr)
        self.assertTrue(link.is_symlink())

    def test_commit_outside_pstack_does_not_create_provenance_churn(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        old_lock = json.loads((self.downstream / "upstream.lock.json").read_text(encoding="utf-8"))
        self._write("unrelated.txt", "outside pstack\n")
        new_head = self._commit_upstream("unrelated upstream change")
        self.assertNotEqual(new_head, old_lock["source"]["commit"])
        second = self._sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already synchronized", second.stdout)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_corrupt_existing_lock_fails_cleanly_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        lock_path = self.downstream / "upstream.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        del lock["source"]["commit"]
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        before = self._snapshot_downstream()

        failed = self._sync()

        self.assertEqual(failed.returncode, 2)
        self.assertIn("invalid existing lock", failed.stderr)
        self.assertIn("source.commit", failed.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_well_formed_false_lock_commit_is_repaired(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        lock_path = self.downstream / "upstream.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["source"]["commit"] = "0" * 40
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        repaired = self._sync()

        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        self.assertIn("updated", repaired.stdout)
        current = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(current["source"]["commit"], self.v1_commit)

    def test_same_tree_commit_outside_configured_ref_is_not_retained(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        self._git(self.upstream, "switch", "-c", "other")
        self._write("other-branch-only.txt", "not reachable from main\n")
        other_commit = self._commit_upstream("other branch only")
        self._git(self.upstream, "switch", "main")
        lock_path = self.downstream / "upstream.lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["source"]["commit"] = other_commit
        lock_path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        repaired = self._sync()

        self.assertEqual(repaired.returncode, 0, repaired.stderr)
        current = json.loads(lock_path.read_text(encoding="utf-8"))
        self.assertEqual(current["source"]["commit"], self.v1_commit)

    def test_shipped_license_keeps_both_copyright_holders(self) -> None:
        result = self._sync()
        self.assertEqual(result.returncode, 0, result.stderr)
        shipped = (self.downstream / "LICENSE").read_text(encoding="utf-8")
        holders = [line for line in shipped.split("\n") if line.startswith("Copyright (c) ")]
        self.assertEqual(holders, ["Copyright (c) 2026 Upstream Author", self._configured_copyright()])
        lock = json.loads((self.downstream / "upstream.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(
            lock["source"]["license_sha256"],
            sync_module._sha256_bytes(UPSTREAM_LICENSE.encode("utf-8")),
        )
        self.assertEqual(
            lock["output"]["license_sha256"],
            sync_module._sha256_bytes(shipped.encode("utf-8")),
        )
        self.assertNotEqual(lock["source"]["license_sha256"], lock["output"]["license_sha256"])

        second = self._sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already synchronized", second.stdout)
        self.assertEqual((self.downstream / "LICENSE").read_text(encoding="utf-8"), shipped)

    def test_ambiguous_upstream_license_is_rejected_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self._snapshot_downstream()
        self._write(
            "pstack/LICENSE",
            UPSTREAM_LICENSE.replace(
                "Copyright (c) 2026 Upstream Author",
                "Copyright (c) 2026 Upstream Author\nCopyright (c) 2026 Someone Else",
            ),
        )
        self._commit_upstream("upstream relicense")
        result = self._sync()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("exactly one copyright line", result.stderr)
        self.assertEqual(self._snapshot_downstream(), before)

    def test_packaged_plugin_version_bumps_only_when_skills_change(self) -> None:
        manifest = self.downstream / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            json.dumps({"name": "pstack", "version": "0.1.0", "keywords": ["skills"]}, indent=2) + "\n",
            encoding="utf-8",
        )
        report = self.root / "report.json"

        first = self._sync(report=report)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["version"], "0.1.1")
        self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["output"]["plugin_version"], "0.1.1")

        second = self._sync()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already synchronized", second.stdout)
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["version"], "0.1.1")

        self._write(
            "pstack/skills/beta/SKILL.md",
            """---
name: beta
description: Explain revised beta behavior. Use when beta is in scope.
---

# Beta

Revised portable content.
""",
        )
        self._commit_upstream("upstream v2")
        third = self._sync()
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["version"], "0.1.2")
        self.assertEqual(json.loads(manifest.read_text(encoding="utf-8"))["keywords"], ["skills"])

    def test_unbumpable_plugin_version_fails_without_mutation(self) -> None:
        first = self._sync()
        self.assertEqual(first.returncode, 0, first.stderr)
        manifest = self.downstream / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"name": "pstack", "version": "0.1"}) + "\n", encoding="utf-8")
        before = self._snapshot_downstream()

        self._write(
            "pstack/skills/beta/SKILL.md",
            """---
name: beta
description: Explain revised beta behavior. Use when beta is in scope.
---

# Beta

Revised portable content.
""",
        )
        self._commit_upstream("upstream v2")
        result = self._sync()
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("MAJOR.MINOR.PATCH", result.stderr)
        self.assertEqual(self._snapshot_downstream(), before)


class ApplyTransactionTest(unittest.TestCase):
    def test_write_failure_restores_skills_license_lock_and_plugin_together(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-transaction-test-") as temporary:
            root = Path(temporary)
            repo = root / "repo"
            output = repo / "skills"
            output.mkdir(parents=True)
            (output / "old.txt").write_text("old skills\n", encoding="utf-8")
            (repo / "LICENSE").write_text("old license\n", encoding="utf-8")
            (repo / "upstream.lock.json").write_text("old lock\n", encoding="utf-8")
            plugin = repo / ".claude-plugin" / "plugin.json"
            plugin.parent.mkdir(parents=True)
            plugin.write_text("old plugin\n", encoding="utf-8")
            staged = root / "staged-skills"
            staged.mkdir()
            (staged / "new.txt").write_text("new skills\n", encoding="utf-8")
            transaction = root / "transaction"
            transaction.mkdir()
            original_write_atomic = sync_module._write_atomic

            def fail_on_plugin(path: Path, content: bytes) -> None:
                if path == plugin:
                    raise OSError("injected plugin write failure")
                original_write_atomic(path, content)

            with mock.patch.object(sync_module, "_write_atomic", side_effect=fail_on_plugin):
                with self.assertRaisesRegex(OSError, "injected plugin write failure"):
                    sync_module._apply_transaction(
                        repo_root=repo,
                        output_path=Path("skills"),
                        staged_output=staged,
                        license_path=Path("LICENSE"),
                        license_bytes=b"new license\n",
                        lock_path=Path("upstream.lock.json"),
                        lock_bytes=b"new lock\n",
                        skills_changed=True,
                        transaction_root=transaction,
                        plugin_path=Path(".claude-plugin/plugin.json"),
                        plugin_bytes=b"new plugin\n",
                    )

            self.assertEqual((output / "old.txt").read_text(encoding="utf-8"), "old skills\n")
            self.assertFalse((output / "new.txt").exists())
            self.assertEqual((repo / "LICENSE").read_text(encoding="utf-8"), "old license\n")
            self.assertEqual(
                (repo / "upstream.lock.json").read_text(encoding="utf-8"), "old lock\n"
            )
            self.assertEqual(plugin.read_text(encoding="utf-8"), "old plugin\n")


if __name__ == "__main__":
    unittest.main()
