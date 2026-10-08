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
        "CI must pass on that head before the merge, and the patch-id rule decides whether "
        "the round's verdict still holds. "
        "Once that head is green and its patch-id matches the verdict's under the patch-id rule "
        "in `playbooks/shipping.md`, a later trunk move does not force another rebase. "
        "Right before the merge, fetch trunk and check that `git merge-tree` of the head against "
        "current trunk is clean. Also check that no path in "
        "`git diff --name-only $(git merge-base HEAD origin/main) origin/main` is a path the PR "
        "changes or a path that decides which CI runs for it, such as the repo's CI config paths. "
        "If either check fails, rebase again, report the new head SHA, wait for CI to pass on it, "
        "and repeat these checks."
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
