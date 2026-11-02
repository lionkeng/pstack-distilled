from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PlanContractTest(unittest.TestCase):
    def test_generated_plan_uses_separate_sources_and_bounded_cadence(self) -> None:
        text = (ROOT / "skills/poteto-mode/playbooks/multi-phase-plan.md").read_text()
        for required in ("pstack-plan-context", '"skillSources"', '"trunkRef"', '"sha256"', '"maxWaitSeconds"', "bounded active-session polling", "--startup", "before arming"):
            self.assertIn(required, text)
        self.assertNotIn("git show origin/main:", text)
        self.assertNotIn("Re-read the execution playbook from trunk", text)
        self.assertNotIn("arm the audit tick as an hourly run", text)

    def test_generated_personal_workflow_can_finish_outside_git(self) -> None:
        text = (ROOT / "skills/automate-me/SKILL.md").read_text()
        for required in ("owning repository", "personal-local", "known checkpoint", "mtime", "validate", "previous file", "Save the skill locally", "no commit or PR"):
            self.assertIn(required, text)
        self.assertNotIn("Work in a worktree off main. Commit and open a PR.", text)
        self.assertNotIn("(`git log -1 --format=%cI <path>`)", text)


if __name__ == "__main__":
    unittest.main()
