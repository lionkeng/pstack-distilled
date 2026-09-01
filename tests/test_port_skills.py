from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import port_skills as port_module  # noqa: E402


class SourceMetadataTest(unittest.TestCase):
    def test_one_line_description(self) -> None:
        name, description, explicit = port_module._source_metadata(
            [
                "name: beta",
                "description: Explain beta behavior. Use when beta is in scope.",
            ],
            Path("SKILL.md"),
        )
        self.assertEqual(name, "beta")
        self.assertEqual(description, "Explain beta behavior. Use when beta is in scope.")
        self.assertFalse(explicit)

    def test_folded_chomp_description(self) -> None:
        name, description, explicit = port_module._source_metadata(
            [
                "name: Make Bot UI",
                "description: >-",
                "  Use when building a custom UI (page, dashboard, buttons) that should wake a",
                "  Grok Bot over a webhook, when the user must provide a webhook sender key, or",
                "  when exposing that UI on Tailscale.",
            ],
            Path("SKILL.md"),
        )
        self.assertEqual(name, "Make Bot UI")
        self.assertEqual(
            description,
            "Use when building a custom UI (page, dashboard, buttons) that should wake a "
            "Grok Bot over a webhook, when the user must provide a webhook sender key, or "
            "when exposing that UI on Tailscale.",
        )
        self.assertFalse(explicit)

    def test_literal_chomp_description(self) -> None:
        _, description, _ = port_module._source_metadata(
            [
                "name: literal",
                "description: |-",
                "  first line",
                "  second line",
            ],
            Path("SKILL.md"),
        )
        self.assertEqual(description, "first line\nsecond line")

    def test_folded_description_then_explicit_flag(self) -> None:
        _, description, explicit = port_module._source_metadata(
            [
                "name: alpha",
                "description: >-",
                "  Use for /alpha when reviewing.",
                "disable-model-invocation: true",
            ],
            Path("SKILL.md"),
        )
        self.assertEqual(description, "Use for /alpha when reviewing.")
        self.assertTrue(explicit)

    def test_empty_block_scalar_is_rejected(self) -> None:
        with self.assertRaises(port_module.PortError) as raised:
            port_module._source_metadata(
                ["name: empty", "description: >-"],
                Path("SKILL.md"),
            )
        self.assertIn("must be a one-line scalar", str(raised.exception))

    def test_port_skills_writes_folded_description_as_json_scalar(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source = root / "pstack"
            skill = source / "skills" / "folded"
            skill.mkdir(parents=True)
            (source / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            (skill / "SKILL.md").write_text(
                """---
name: Folded Skill
description: >-
  Use when folding yaml descriptions
  across several source lines.
---

# Folded

Portable body.
""",
                encoding="utf-8",
            )
            output = root / "skills"
            count = port_module.port_skills(source, output, PROJECT_ROOT / "porting" / "rewrites.json")
            self.assertEqual(count, 1)
            generated = (output / "folded" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(
                'description: "Use when folding yaml descriptions across several source lines."',
                generated,
            )

    def test_new_poteto_phrases_and_check_plan_model_slug(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source = root / "pstack"
            skill = source / "skills" / "poteto-mode"
            playbooks = skill / "playbooks"
            scripts = skill / "scripts"
            playbooks.mkdir(parents=True)
            scripts.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                """---
name: poteto-mode
description: Apply poteto-mode when requested.
---

# Poteto mode

Portable body.
""",
                encoding="utf-8",
            )
            (playbooks / "opening-a-pr.md").write_text(
                "**PRs.** Run `/deslop` from `cursor-team-kit` over the diff before commit. "
                "Run `/no-comments` before review. Write every PR title, PR description, and "
                "commit body with `/technical-writing`, then apply `/unslop`. Apply every "
                "technical-writing layer except Diátaxis. Use one word for each action, keep "
                "articles, and avoid `-ing` when a plain verb works.\n",
                encoding="utf-8",
            )
            (playbooks / "multi-phase-plan.md").write_text(
                "Ten lanes on `grok-4.6-fast-xhigh` at the PR head drive the real surface "
                "through its control skill.\n"
                "**Control skill.** Pick it by surface. Browser, Electron, and web UIs use "
                "`control-ui` from `cursor-team-kit`. CLIs and TUIs use `control-cli` from "
                "`cursor-team-kit`. Native mobile uses whatever simulator-driving skill the repo "
                "has. A PR that touches two surfaces gets lanes on both. A surface with no control "
                "skill is a risk in Appendix C, and its live block still names how each lane drives "
                "it.\n",
                encoding="utf-8",
            )
            (scripts / "check-plan.mjs").write_text(
                'const LANES = "Ten lanes on `grok-4.6-fast-xhigh` at the PR head";\n',
                encoding="utf-8",
            )
            output = root / "skills"
            port_module.port_skills(source, output, PROJECT_ROOT / "porting" / "rewrites.json")
            opening = (output / "poteto-mode" / "playbooks" / "opening-a-pr.md").read_text(
                encoding="utf-8"
            )
            plan = (output / "poteto-mode" / "playbooks" / "multi-phase-plan.md").read_text(
                encoding="utf-8"
            )
            checker = (output / "poteto-mode" / "scripts" / "check-plan.mjs").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("cursor-team-kit", opening)
            self.assertNotIn("optional companion tooling", opening)
            self.assertIn("available prose-cleanup workflow", opening)
            self.assertNotIn("control skill", plan.lower())
            self.assertNotIn("cursor-team-kit", plan)
            self.assertNotIn("optional companion tooling", plan)
            self.assertIn("Verification harness.", plan)
            self.assertIn("through its verification harness", plan)
            self.assertIn("fast-code-model", plan)
            self.assertIn("fast-code-model", checker)
            self.assertNotIn("grok-4.6-fast-xhigh", checker)


if __name__ == "__main__":
    unittest.main()
