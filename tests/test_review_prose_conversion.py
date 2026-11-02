from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import port_skills as port_module


DESIGN = "It also applies to product design decisions where user experience depends on feel, not logic."
VISUAL = "A visual is a picture: a screenshot, a video, a Mermaid diagram, a chart or diagram from `/visualize`, or a generated image. A Markdown table is not a visual, even with before and after columns."
CHART = "Draw diagrams and charts from facts you have: a Mermaid diagram for how things connect and a `/visualize` chart for numbers."
NONEMPTY = '''Non-empty, via a variadic tuple:

```ts
type NonEmpty<T> = [T, ...T[]];

// Don't: T[] plus a length check every caller must repeat
function pickWinner(entries: string[]): string {
  if (entries.length === 0) throw new Error("no entries");
  return entries[Math.floor(Math.random() * entries.length)];
}

// Do: an empty value of the type can't exist
function pickWinner(entries: NonEmpty<string>): string {
  return entries[Math.floor(Math.random() * entries.length)];
}
```'''
RANGE = '''A time range, as start plus duration:

```ts
// Don't: a comment holds the invariant
type TimeRange = { start: Date; end: Date }; // start <= end

// Do: a negative range can't be written; derive end when needed
type TimeRange = { start: Date; durationMs: number };
```

Keep `durationMs` a plain number. Brand it (per Branded types) only if a raw number could be passed where a duration is expected, not by reflex. Pick the representation that makes the bad state unconstructable, then expose the reading you need on top (`pairs.flat()`, a `rangeEnd()` helper).'''

CASES = {
    "principle-exhaust-the-design-space": ("SKILL.md", [DESIGN]),
    "ketchup": ("SKILL.md", [VISUAL, CHART]),
    "typescript-best-practices": ("references/patterns.md", [NONEMPTY, RANGE]),
}


class ReviewProseConversionTest(unittest.TestCase):
    def _assert_design(self, text: str) -> None:
        self.assertIn("two or three distinct prototypes", text)
        self.assertIn("comparison criteria before", text)
        self.assertIn("Compare the observed results", text)
        self.assertIn("Choose", text)
        self.assertIn("reasons", text)

    def _assert_chart(self, text: str) -> None:
        self.assertNotIn("/visualize", text)
        self.assertIn("available chart capability", text)
        self.assertIn("inline SVG", text)
        self.assertIn("supported Mermaid", text)
        self.assertIn("data table", text)
        self.assertIn("cannot be rendered", text)
        self.assertIn("Do not install", text)
        self.assertIn("product repository", text)
        self.assertIn("observed values", text)

    def _assert_types(self, text: str) -> None:
        self._assert_tuple(text)
        self._assert_numeric_bounds(text)

    def _assert_tuple(self, text: str) -> None:
        self.assertIn("function firstEntry(entries: NonEmpty<string>): string", text)
        self.assertIn("return entries[0]", text)
        self.assertIn("computed index", text)
        self.assertNotIn("Math.random()", text)

    def _assert_numeric_bounds(self, text: str) -> None:
        self.assertIn("boundary validation", text)
        self.assertNotIn("durationMs", text)
        self.assertNotIn("negative range can't be written", text)

    def _assert_contract(self, name: str, text: str) -> None:
        {
            "principle-exhaust-the-design-space": self._assert_design,
            "ketchup": self._assert_chart,
            "typescript-best-practices": self._assert_types,
        }[name](text)

    def _fixture(self, root: Path, name: str, content: str) -> tuple[Path, Path]:
        relative, _ = CASES[name]
        source = root / "pstack"
        skill = source / "skills" / name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Review this workflow.\n---\n\n# Example\n\n"
            + (content if relative == "SKILL.md" else "Use the reference.") + "\n",
            encoding="utf-8",
        )
        if relative != "SKILL.md":
            target = skill / relative
            target.parent.mkdir(parents=True)
            target.write_text(content + "\n", encoding="utf-8")
        return source, Path(name) / relative

    def test_f3_generated_design_skill_has_a_complete_standalone_procedure(self) -> None:
        self._assert_design((PROJECT_ROOT / "skills/principle-exhaust-the-design-space/SKILL.md").read_text())

    def test_f4_generated_chart_instructions_have_a_read_only_fallback(self) -> None:
        ketchup = (PROJECT_ROOT / "skills/ketchup/SKILL.md").read_text()
        self._assert_chart(ketchup)
        self.assertIn("Keep this turn read-only", ketchup)
        self.assertIn("Never invent a number", ketchup)
        self.assertIn("Follow `ketchup`", (PROJECT_ROOT / "skills/ketchup-video/SKILL.md").read_text())

    def test_f10_generated_reference_does_not_claim_plain_numbers_enforce_bounds(self) -> None:
        self._assert_numeric_bounds((PROJECT_ROOT / "skills/typescript-best-practices/references/patterns.md").read_text())

    def test_f11_generated_reference_uses_the_guaranteed_tuple_index(self) -> None:
        self._assert_tuple((PROJECT_ROOT / "skills/typescript-best-practices/references/patterns.md").read_text())

    def test_conversion_applies_fixes_and_preserves_unrelated_prose(self) -> None:
        for name, (_, anchors) in CASES.items():
            with self.subTest(skill=name), tempfile.TemporaryDirectory(prefix="pstack-prose-") as temporary:
                root = Path(temporary)
                source, target = self._fixture(root, name, "\n\n".join(anchors) + "\n\nKeep this unrelated sentence.")
                output = root / "skills"
                port_module.port_skills(source, output, PROJECT_ROOT / "porting/rewrites.json")
                text = (output / target).read_text()
                self._assert_contract(name, text)
                self.assertIn("Keep this unrelated sentence.", text)

    def test_strict_conversion_rejects_changed_and_duplicate_anchors(self) -> None:
        configured = json.loads((PROJECT_ROOT / "porting/rewrites.json").read_text())["skills"]
        for name, (relative, anchors) in CASES.items():
            override = configured.get(name, {})
            available = override.get("body", []) if relative == "SKILL.md" else override.get("files", {}).get(relative, [])
            rules = [rule for rule in available if rule["from"] in anchors]
            self.assertEqual({rule["from"] for rule in rules}, set(anchors), name)
            selected = {"body": rules} if relative == "SKILL.md" else {"files": {relative: rules}}
            for anchor in anchors:
                for mode in ("missing", "duplicate"):
                    with self.subTest(skill=name, anchor=anchor[:40], mode=mode), tempfile.TemporaryDirectory(prefix="pstack-prose-drift-") as temporary:
                        root = Path(temporary)
                        content = "\n\n".join(anchors)
                        content = content.replace(anchor, "Upstream changed this passage." if mode == "missing" else anchor + "\n\n" + anchor)
                        source, _ = self._fixture(root, name, content)
                        rewrites = root / "rewrites.json"
                        rewrites.write_text(json.dumps({"schema_version": 1, "literal": [], "skills": {name: selected}}))
                        with self.assertRaisesRegex(port_module.PortError, "must occur exactly once") as raised:
                            port_module.port_skills(source, root / "skills", rewrites, require_rule_matches=True)
                        self.assertIn(f"found {0 if mode == 'missing' else 2}", str(raised.exception))
                        self.assertIn(repr(anchor[:80]), str(raised.exception))


if __name__ == "__main__":
    unittest.main()
