#!/usr/bin/env python3
"""Verify checked-in generated artifacts against upstream.lock.json offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Sequence


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from sync_upstream import (  # noqa: E402
    SyncError,
    _converter_digest,
    _load_config,
    _read_existing_lock,
    _safe_relative,
    _sha256_bytes,
    _tree_digest,
)
from validate_skills import validate_skills  # noqa: E402


def verify_lock(repo_root: Path, config_path: Path) -> List[str]:
    errors: List[str] = []
    repo_root = repo_root.resolve()
    try:
        config = _load_config(config_path.resolve())
        output_path = _safe_relative(str(config["output"]), "output")
        lock_path = _safe_relative(str(config["lock"]), "lock")
        license_path = _safe_relative(str(config["license"]), "license")
        rewrites_path = (
            PROJECT_ROOT / _safe_relative(str(config["rewrites"]), "rewrites")
        ).resolve()
        lock = _read_existing_lock(repo_root / lock_path)
    except (OSError, SyncError) as exc:
        return [str(exc)]

    if lock is None:
        return [f"{repo_root / lock_path}: lock does not exist"]
    source = lock["source"]
    output = lock["output"]
    source_config = config["source"]

    for key in ("repository", "ref", "path"):
        if source.get(key) != source_config.get(key):
            errors.append(
                f"lock source.{key} does not match sync-config.json: "
                f"{source.get(key)!r} != {source_config.get(key)!r}"
            )
    if output.get("path") != output_path.as_posix():
        errors.append(
            f"lock output.path does not match sync-config.json: "
            f"{output.get('path')!r} != {output_path.as_posix()!r}"
        )

    skills_root = repo_root / output_path
    validation_errors = validate_skills(skills_root)
    errors.extend(validation_errors)
    try:
        actual_output_digest = _tree_digest(skills_root)
    except (OSError, SyncError) as exc:
        errors.append(str(exc))
    else:
        if output.get("sha256") != actual_output_digest:
            errors.append(
                f"generated output digest drift: {actual_output_digest} "
                f"!= lock {output.get('sha256')}"
            )
    if skills_root.is_dir():
        actual_count = sum(1 for path in skills_root.iterdir() if path.is_dir())
        if output.get("skill_count") != actual_count:
            errors.append(
                f"generated skill count drift: {actual_count} != lock {output.get('skill_count')}"
            )

    license_file = repo_root / license_path
    if license_file.is_symlink() or not license_file.is_file():
        errors.append(f"{license_file}: checked-in license must be a regular file")
    else:
        actual_license_digest = _sha256_bytes(license_file.read_bytes())
        if source.get("license_sha256") != actual_license_digest:
            errors.append(
                f"license digest drift: {actual_license_digest} "
                f"!= lock {source.get('license_sha256')}"
            )

    try:
        actual_converter_digest = _converter_digest(rewrites_path)
    except OSError as exc:
        errors.append(f"could not hash converter inputs: {exc}")
    else:
        if output.get("converter_sha256") != actual_converter_digest:
            errors.append(
                f"converter digest drift: {actual_converter_digest} "
                f"!= lock {output.get('converter_sha256')}"
            )
    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "sync-config.json")
    args = parser.parse_args(argv)
    errors = verify_lock(args.repo_root, args.config)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("verified checked-in artifacts against upstream.lock.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
