from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import port_skills as port_module  # noqa: E402


class AutopilotConversionTest(unittest.TestCase):
    UPSTREAM_MERGE_EXCEPTION = (
        "Right before merging, fetch trunk and ask whether its changes can affect the patch, "
        "because rebasing for every trunk move never ends. Rebase and wait for CI when the code "
        "that would land was never tested, as with a conflict, a file both sides changed, or a "
        "change to which checks run for the PR. A lockfile both sides changed needs no rebase "
        "when a frozen install passes on the merge result and the packages the PR changes "
        "resolve there as on the head, because that install tests the lockfile that would land, "
        "and a failing install means the rebase must repair it. When trunk changed a caller of "
        "the patch or something the patch depends on, such as code it calls or a dependency "
        "version, run the patch's checks on the merge result and merge on a pass. Otherwise "
        "merge. If trunk would force a third rebase past merge prep, hold and report to the "
        "root, which sequences the colliding work."
    )

    def _port_playbook(self, root: Path, text: str, skill_name: str = "poteto-mode") -> str:
        source = root / "pstack"
        skill = source / "skills" / skill_name
        playbooks = skill / "playbooks"
        playbooks.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: Apply this mode.\n---\n\n# Mode\n",
            encoding="utf-8",
        )
        (playbooks / "autopilot-full.md").write_text(text, encoding="utf-8")
        output = root / "skills"
        port_module.port_skills(source, output, PROJECT_ROOT / "porting" / "rewrites.json")
        return (output / skill_name / "playbooks/autopilot-full.md").read_text(encoding="utf-8")

    def _assert_current_trunk_gate(self, text: str) -> None:
        self.assertNotIn("a later trunk move does not force another rebase", text)
        self.assertNotIn("If either check fails", text)
        self.assertIn(
            "Fresh CI and the load-bearing runtime checks must pass on that head before the merge",
            text,
        )
        self.assertIn("git merge-base --is-ancestor origin/main HEAD", text)
        self.assertIn("rebase onto the new trunk tip", text)
        self.assertIn("wait for fresh CI and the load-bearing runtime checks on that head", text)
        self.assertIn("A clean `git merge-tree` and disjoint paths do not prove", text)
        self.assertIn("an unchanged patch-id does not preserve runtime or CI results", text)
        self.assertIn("Require the forge's up-to-date-branch protection", text)
        self.assertIn("a merge queue that tests the current integrated tree", text)
        self.assertIn("If neither safeguard is available, stop at merge-ready", text)

    def test_conversion_requires_current_trunk_and_fresh_checks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-autopilot-port-") as temporary:
            converted = self._port_playbook(
                Path(temporary),
                "### Autopilot-full\n\n" + self.UPSTREAM_MERGE_EXCEPTION + "\n\nKeep other steps.\n",
            )
            self._assert_current_trunk_gate(converted)
            self.assertTrue(converted.startswith("### Autopilot-full\n\n"))
            self.assertTrue(converted.endswith("\n\nKeep other steps.\n"))

    def test_changed_or_duplicate_upstream_gate_fails_closed(self) -> None:
        for text in ("Upstream rewrote its merge gate.\n", self.UPSTREAM_MERGE_EXCEPTION * 2):
            with self.subTest(text=text), tempfile.TemporaryDirectory(
                prefix="pstack-autopilot-port-"
            ) as temporary:
                with self.assertRaisesRegex(port_module.PortError, "autopilot-full.md.*exactly once"):
                    self._port_playbook(Path(temporary), text)

    def test_checked_in_playbook_requires_current_trunk_and_fresh_checks(self) -> None:
        self._assert_current_trunk_gate(
            (PROJECT_ROOT / "skills/poteto-mode/playbooks/autopilot-full.md").read_text(
                encoding="utf-8"
            )
        )

    def test_same_basename_in_another_skill_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-autopilot-port-") as temporary:
            text = "### Another autopilot\n\nThis is a different playbook.\n"
            self.assertEqual(self._port_playbook(Path(temporary), text, "another-mode"), text)


if __name__ == "__main__":
    unittest.main()
