#!/usr/bin/env python3
"""Validate the strict, portable Agent Skills subset used by pstack-distilled."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import unquote


ALLOWED_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REFERENCE_DEFINITION_RE = re.compile(
    r"^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))", re.MULTILINE
)
MODEL_SLUG_RE = re.compile(
    r"\b(?:claude|gpt|gemini|grok|llama|mistral|deepseek|qwen)"
    r"(?:-[a-z0-9][a-z0-9._-]*)+\b",
    re.IGNORECASE,
)
PORTABILITY_PATTERNS: Sequence[Tuple[str, re.Pattern[str]]] = (
    ("host-specific skill path", re.compile(r"\.(?:cursor|claude|codex)/")),
    ("Cursor runtime name", re.compile(r"\bCursor\b")),
    ("Cursor Task tool", re.compile(r"(?:`Task`|\bTask tool\b)")),
    ("Cursor question tool", re.compile(r"\bAsk(?:User)?Question\b")),
    ("Cursor subagent field", re.compile(r"\bsubagent_type\b")),
    ("Cursor background field", re.compile(r"\brun_in_background\b")),
    ("Cursor loop command", re.compile(r"/loop\b")),
    ("Cursor companion plugin", re.compile(r"\bcursor-team-kit\b")),
    ("unbundled companion tooling", re.compile(r"\boptional companion tooling\b")),
    ("host-specific skill-authoring primitive", re.compile(r"\bcreate-skill\b")),
    ("nonstandard invocation field", re.compile(r"\bdisable-model-invocation\b")),
    ("Cursor deslop command", re.compile(r"/deslop\b")),
    ("Cursor file-discovery tool", re.compile(r"\bGlob\b")),
    ("Cursor text-search tool", re.compile(r"\bGrep\b")),
    ("malformed converted history path", re.compile(r"\bagent-conversation records\b")),
    ("host-specific question schema field", re.compile(r"\ballow_multiple\b")),
    ("hard-coded Cursor transcript schema", re.compile(r"message\.content\[0\]\.text")),
    ("dangling control-skill dependency", re.compile(r"\bcontrol[- ]skill\b", re.IGNORECASE)),
    ("dangling loop-skill dependency", re.compile(r"\bloop skill\b", re.IGNORECASE)),
    (
        "cloud-only execution wording",
        re.compile(r"\bcloud\b", re.IGNORECASE),
    ),
    ("dangling host PR-monitoring dependency", re.compile(r"another host PR-monitoring workflow")),
    ("malformed delegation wording", re.compile(r"delegation operation subagent")),
    ("assumed system-prompt path", re.compile(r"path in the system prompt", re.IGNORECASE)),
    ("assumed host task dashboard", re.compile(r"host task dashboard", re.IGNORECASE)),
    (
        "assumed nested delegation schema",
        re.compile(r"full delegation operation schema", re.IGNORECASE),
    ),
    (
        "assumed nested delegation depth",
        re.compile(r"nesting works to depth", re.IGNORECASE),
    ),
    ("hard-coded model identifier", MODEL_SLUG_RE),
)


class SkillValidationError(ValueError):
    """Raised when one or more generated skills violate the portable contract."""


def _decode_scalar(value: str, location: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"'):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SkillValidationError(f"{location}: invalid quoted YAML scalar: {exc}") from exc
        if not isinstance(decoded, str):
            raise SkillValidationError(f"{location}: scalar must be a string")
        return decoded
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def parse_frontmatter(path: Path) -> Tuple[Mapping[str, object], str]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise SkillValidationError(f"{path}: SKILL.md must be UTF-8") from exc

    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise SkillValidationError(f"{path}: missing opening YAML frontmatter delimiter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise SkillValidationError(f"{path}: missing closing YAML frontmatter delimiter") from exc

    data: Dict[str, object] = {}
    current_mapping: Optional[str] = None
    for line_number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("  "):
            if current_mapping != "metadata":
                raise SkillValidationError(
                    f"{path}:{line_number}: nested values are supported only under metadata"
                )
            nested = line.strip()
            if ":" not in nested:
                raise SkillValidationError(f"{path}:{line_number}: malformed metadata entry")
            key, raw_value = nested.split(":", 1)
            key = key.strip()
            if not key:
                raise SkillValidationError(f"{path}:{line_number}: empty metadata key")
            metadata = data.setdefault("metadata", {})
            assert isinstance(metadata, dict)
            if key in metadata:
                raise SkillValidationError(f"{path}:{line_number}: duplicate metadata key {key!r}")
            metadata[key] = _decode_scalar(raw_value, f"{path}:{line_number}")
            continue

        current_mapping = None
        if ":" not in line:
            raise SkillValidationError(f"{path}:{line_number}: malformed frontmatter entry")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        if key in data:
            raise SkillValidationError(f"{path}:{line_number}: duplicate frontmatter key {key!r}")
        if key == "metadata" and not raw_value.strip():
            data[key] = {}
            current_mapping = key
        else:
            data[key] = _decode_scalar(raw_value, f"{path}:{line_number}")

    body = "\n".join(lines[end + 1 :]).strip()
    return data, body


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_links(skill_root: Path, markdown_path: Path, text: str, errors: List[str]) -> None:
    def validate_target(raw_target: str) -> None:
        raw_target = raw_target.strip()
        if raw_target.startswith("<") and raw_target.endswith(">"):
            raw_target = raw_target[1:-1]
        if not raw_target or raw_target in {"url", "URL"} or raw_target.startswith(
            ("#", "https://", "http://", "mailto:", "data:")
        ):
            return
        target_without_fragment = raw_target.split("#", 1)[0]
        # A Markdown link title follows whitespace. pstack paths contain no spaces.
        target_without_title = target_without_fragment.split(maxsplit=1)[0]
        target = unquote(target_without_title)
        if not target:
            return
        if Path(target).is_absolute():
            errors.append(f"{markdown_path}: absolute local link is not portable: {raw_target}")
            return
        resolved = (markdown_path.parent / target).resolve()
        if not _is_within(resolved, skill_root.resolve()):
            errors.append(f"{markdown_path}: link escapes skill directory: {raw_target}")
        elif not resolved.exists():
            errors.append(f"{markdown_path}: broken local link: {raw_target}")

    for match in LINK_RE.finditer(text):
        validate_target(match.group(1))
    for match in REFERENCE_DEFINITION_RE.finditer(text):
        if match.group(1).startswith("^"):
            continue
        validate_target(match.group(2) or match.group(3))


def validate_skills(skills_root: Path) -> List[str]:
    errors: List[str] = []
    if not skills_root.is_dir():
        return [f"{skills_root}: skills directory does not exist"]

    skill_dirs = sorted(path for path in skills_root.iterdir() if path.is_dir())
    if not skill_dirs:
        return [f"{skills_root}: no skill directories found"]

    names: Dict[str, Path] = {}
    for skill_dir in skill_dirs:
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            errors.append(f"{skill_dir}: missing SKILL.md")
            continue

        for path in skill_dir.rglob("*"):
            if path.is_symlink():
                errors.append(f"{path}: symlinks are not permitted in portable skills")
            if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
                errors.append(f"{path}: generated cache artifacts are not permitted")

        try:
            frontmatter, body = parse_frontmatter(skill_file)
        except SkillValidationError as exc:
            errors.append(str(exc))
            continue

        unknown = sorted(set(frontmatter) - ALLOWED_FIELDS)
        if unknown:
            errors.append(f"{skill_file}: nonstandard frontmatter keys: {', '.join(unknown)}")

        name = frontmatter.get("name")
        description = frontmatter.get("description")
        if not isinstance(name, str) or not name:
            errors.append(f"{skill_file}: name must be a nonempty string")
        else:
            if len(name) > 64 or not NAME_RE.fullmatch(name):
                errors.append(f"{skill_file}: invalid portable skill name {name!r}")
            if name != skill_dir.name:
                errors.append(
                    f"{skill_file}: name {name!r} must match directory {skill_dir.name!r}"
                )
            if name in names:
                errors.append(f"{skill_file}: duplicate skill name also used by {names[name]}")
            else:
                names[name] = skill_file

        if not isinstance(description, str) or not 1 <= len(description) <= 1024:
            errors.append(f"{skill_file}: description must contain 1-1024 characters")
        elif isinstance(description, str):
            for label, pattern in PORTABILITY_PATTERNS:
                match = pattern.search(description)
                if match:
                    errors.append(
                        f"{skill_file}: description contains {label}: {match.group(0)!r}"
                    )
        if not body:
            errors.append(f"{skill_file}: Markdown body must not be empty")

        license_value = frontmatter.get("license")
        if license_value is not None and (not isinstance(license_value, str) or not license_value):
            errors.append(f"{skill_file}: license must be a nonempty string")
        compatibility = frontmatter.get("compatibility")
        if compatibility is not None and (
            not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500
        ):
            errors.append(f"{skill_file}: compatibility must contain 1-500 characters")
        metadata = frontmatter.get("metadata")
        if metadata is not None:
            if not isinstance(metadata, Mapping):
                errors.append(f"{skill_file}: metadata must be a string-to-string mapping")
            elif any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
                errors.append(f"{skill_file}: metadata keys and values must be strings")
        allowed_tools = frontmatter.get("allowed-tools")
        if allowed_tools is not None and not isinstance(allowed_tools, str):
            errors.append(f"{skill_file}: allowed-tools must be a space-separated string")

        for resource_path in sorted(path for path in skill_dir.rglob("*") if path.is_file()):
            try:
                resource_text = resource_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                if resource_path.suffix.lower() == ".md":
                    errors.append(f"{resource_path}: Markdown resources must be UTF-8")
                continue
            for label, pattern in PORTABILITY_PATTERNS:
                match = pattern.search(resource_text)
                if match:
                    line = resource_text[: match.start()].count("\n") + 1
                    errors.append(
                        f"{resource_path}:{line}: contains {label}: {match.group(0)!r}"
                    )
            if resource_path.suffix.lower() == ".md":
                _validate_links(skill_dir, resource_path, resource_text, errors)

    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skills_root", type=Path, help="Directory containing skill folders")
    parser.add_argument("--json", action="store_true", help="Emit a machine-readable result")
    args = parser.parse_args(argv)

    errors = validate_skills(args.skills_root.resolve())
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
    else:
        count = sum(1 for path in args.skills_root.iterdir() if path.is_dir())
        print(f"validated {count} portable skills")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
