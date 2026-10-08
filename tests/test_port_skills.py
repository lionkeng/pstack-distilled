from __future__ import annotations

import json
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

    def test_body_naming_only_a_model_slug_gets_portable_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            skill = root / "pstack" / "skills" / "runner"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                """---
name: runner
description: Run candidates.
---

# Runner

If the line is missing, use `claude-opus-9-xhigh`.
""",
                encoding="utf-8",
            )
            output = root / "skills"
            port_module.port_skills(root / "pstack", output, PROJECT_ROOT / "porting" / "rewrites.json")
            generated = (output / "runner" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("## Portable execution", generated)
            self.assertIn("use `available-model`", generated)


class CheckPlanTest(unittest.TestCase):
    LOOP_LINE = "- [ ] On the operator's go, arm the audit tick as `/loop 1h` with the tick prompt below.\n"

    def _port_poteto_fixture(self, root: Path, plan_text: str) -> Path:
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
        (playbooks / "multi-phase-plan.md").write_text(plan_text, encoding="utf-8")
        (scripts / "check-plan.mjs").write_text(
            'const PROGRAM_MARKERS = ["git show origin/main:", "/loop 1h", "status message"];\n',
            encoding="utf-8",
        )
        output = root / "skills"
        port_module.port_skills(source, output, PROJECT_ROOT / "porting" / "rewrites.json")
        return output

    def test_new_poteto_phrases_and_check_plan_loop_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            output = self._port_poteto_fixture(
                Path(temporary),
                "Ten lanes at the PR head drive the real surface through its control skill, on "
                "the `swarm workers` model (default `grok-4.7-xhigh-fast`).\n"
                "**Control skill.** Pick it by surface. Browser, Electron, and web UIs use "
                "`control-ui` from `cursor-team-kit`. CLIs and TUIs use `control-cli` from "
                "`cursor-team-kit`. Native mobile uses whatever simulator-driving skill the repo "
                "has. A PR that touches two surfaces gets lanes on both. A surface with no control "
                "skill is a risk in Appendix C, and its live block still names how each lane drives "
                "it.\n" + self.LOOP_LINE,
            )
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
            self.assertIn("(default `fast-code-model`)", plan)
            self.assertIn(
                "arm the audit tick as an hourly run of the host's recurring-run capability with",
                plan,
            )
            self.assertIn(
                'const PROGRAM_MARKERS = ["git show origin/main:", '
                "\"hourly run of the host's recurring-run capability\", \"status message\"];",
                checker,
            )
            self.assertNotIn("/loop", checker)

    def test_plan_template_without_check_plan_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            with self.assertRaises(port_module.PortError) as raised:
                self._port_poteto_fixture(Path(temporary), "Arm the audit tick by hand.\n")
            self.assertIn("lacks the check-plan.mjs marker", str(raised.exception))


class SkillOverrideTest(unittest.TestCase):
    SOURCE = """---
name: gamma
description: Upstream wording. Use for /gamma.
disable-model-invocation: true
---

# Gamma

Spawn a worker for every question.
"""

    def _write_fixture(self, root: Path, skills: dict) -> "tuple[Path, Path]":
        source = root / "pstack"
        skill = source / "skills" / "gamma"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(self.SOURCE, encoding="utf-8")
        rewrites = root / "rewrites.json"
        rewrites.write_text(
            json.dumps({"schema_version": 1, "literal": [], "skills": skills}), encoding="utf-8"
        )
        return source, rewrites

    def test_override_replaces_description_and_body_and_ignores_absent_skills(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(
                root,
                {
                    "gamma": {
                        "description": "Answer gamma questions.",
                        "body": [
                            {
                                "from": "Spawn a worker for every question.",
                                "to": "Answer in the current thread.",
                            }
                        ],
                    },
                    "absent": {"description": "Upstream has no skill by this name."},
                },
            )
            output = root / "skills"
            self.assertEqual(port_module.port_skills(source, output, rewrites), 1)
            generated = (output / "gamma" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn(
                'description: "Explicit request or pstack routing only. Answer gamma questions."',
                generated,
            )
            self.assertIn("Answer in the current thread.", generated)
            self.assertNotIn("Spawn a worker", generated)
            self.assertFalse((output / "absent").exists())

    def test_override_can_clear_explicit_activation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(
                root, {"gamma": {"description": "Answer gamma questions.", "explicit": False}}
            )
            output = root / "skills"
            port_module.port_skills(source, output, rewrites)
            generated = (output / "gamma" / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn('description: "Answer gamma questions."', generated)
            self.assertNotIn("Explicit request", generated)
            self.assertNotIn("pstack-distilled-activation", generated)

    def test_require_rule_matches_lists_only_unmatched_rules(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(root, {})
            rewrites.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "literal": [
                            {"from": "every question", "to": "each question"},
                            {"from": "Text upstream dropped", "to": "Replacement"},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(port_module.PortError) as raised:
                port_module.port_skills(source, root / "skills", rewrites, require_rule_matches=True)
            message = str(raised.exception)
            self.assertIn("rewrites.json literal: 'Text upstream dropped'", message)
            self.assertNotIn("'every question'", message)

    def test_excluded_skill_is_not_ported_or_counted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(root, {"gamma": {"exclude": True}})
            kept = source / "skills" / "delta"
            kept.mkdir()
            (kept / "SKILL.md").write_text(
                "---\nname: delta\ndescription: Answer delta questions.\n---\n\n# Delta\n\nBody.\n",
                encoding="utf-8",
            )
            output = root / "skills"
            self.assertEqual(port_module.port_skills(source, output, rewrites), 1)
            self.assertFalse((output / "gamma").exists())
            self.assertTrue((output / "delta" / "SKILL.md").is_file())

    def test_exclude_combined_with_edits_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(
                root, {"gamma": {"exclude": True, "description": "Answer gamma questions."}}
            )
            with self.assertRaises(port_module.PortError) as raised:
                port_module.port_skills(source, root / "skills", rewrites)
            self.assertIn("cannot also edit it", str(raised.exception))

    def test_override_with_stale_body_anchor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pstack-port-test-") as temporary:
            root = Path(temporary)
            source, rewrites = self._write_fixture(
                root,
                {"gamma": {"body": [{"from": "Text upstream rewrote.", "to": "Replacement."}]}},
            )
            with self.assertRaises(port_module.PortError) as raised:
                port_module.port_skills(source, root / "skills", rewrites)
            self.assertIn("must occur exactly once", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
