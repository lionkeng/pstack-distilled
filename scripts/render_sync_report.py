#!/usr/bin/env python3
"""Render a sync report as a concise pull-request body."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping, Optional, Sequence


def render(report: Mapping[str, object]) -> str:
    source = report["source"]
    changes = report["changes"]
    output = report["output"]
    assert isinstance(source, Mapping)
    assert isinstance(changes, Mapping)
    assert isinstance(output, Mapping)
    previous = source.get("previous_commit") or "initial import"
    lines = [
        "Automated portability sync from the original pstack distribution.",
        "",
        f"- Upstream: `{source['repository']}` at `{source['commit']}`",
        f"- Previous: `{previous}`",
        f"- Upstream plugin version: `{source['plugin_version']}`",
        f"- Portable skills: `{output['skill_count']}`",
        f"- Output digest: `{output['sha256']}`",
    ]
    packaged_version = output.get("plugin_version")
    if packaged_version:
        lines.append(f"- Packaged plugin version: `{packaged_version}`")
    lines += [
        "",
        "The workflow fetched upstream ephemerally, converted the skills, ran the offline",
        "sync tests, and validated the complete Agent Skills output. Upstream scripts were",
        "treated as data and were not executed.",
        "",
        "## Generated changes",
        "",
    ]
    for label in ("added", "modified", "deleted"):
        paths = changes.get(label, [])
        assert isinstance(paths, list)
        lines.append(f"### {label.title()} ({len(paths)})")
        lines.append("")
        if paths:
            lines.extend(f"- `{path}`" for path in paths)
        else:
            lines.append("- None")
        lines.append("")
    lines.append("Review semantic portability changes before merging; this workflow never auto-merges.")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    report = json.loads(args.report.read_text(encoding="utf-8"))
    args.output.write_text(render(report), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
