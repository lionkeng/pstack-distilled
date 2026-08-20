#!/usr/bin/env python3
"""Fetch upstream pstack ephemerally and update the generated portable skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from port_skills import PortError, port_skills  # noqa: E402
from validate_skills import validate_skills  # noqa: E402


class SyncError(RuntimeError):
    """Raised when synchronization cannot complete without risking partial output."""


GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SEMVER_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
PLUGIN_VERSION_RE = re.compile(r'("version"\s*:\s*)"([^"\\]*)"')


def _run(command: Sequence[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            list(command),
            cwd=str(cwd),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError as exc:
        raise SyncError(f"required command is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or f"exit {exc.returncode}"
        raise SyncError(f"command failed ({' '.join(command)}): {detail}") from exc
    return result.stdout.strip()


def _safe_relative(value: str, label: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise SyncError(f"{label} must be a non-empty relative path without '..': {value!r}")
    return path


def _load_config(path: Path) -> Mapping[str, object]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"could not read configuration {path}: {exc}") from exc
    if not isinstance(config, Mapping):
        raise SyncError(f"{path}: configuration must be a JSON object")
    if config.get("schema_version") != 1:
        raise SyncError(f"{path}: unsupported schema_version")
    source = config.get("source")
    if not isinstance(source, Mapping):
        raise SyncError(f"{path}: source must be an object")
    for key in ("repository", "ref", "path"):
        if not isinstance(source.get(key), str) or not source[key]:
            raise SyncError(f"{path}: source.{key} must be a non-empty string")
    for key in ("output", "lock", "license", "rewrites"):
        if not isinstance(config.get(key), str) or not config[key]:
            raise SyncError(f"{path}: {key} must be a non-empty string")
    return config


def _checkout(source: str, ref: str, source_path: Path, destination: Path) -> None:
    _run(["git", "init", "--quiet", str(destination)], destination.parent)
    _run(["git", "remote", "add", "origin", source], destination)
    _run(["git", "sparse-checkout", "init", "--cone"], destination)
    _run(["git", "sparse-checkout", "set", source_path.as_posix()], destination)
    fetch = ["git", "fetch", "--quiet", "--depth=1"]
    if not Path(source).expanduser().exists():
        fetch.append("--filter=blob:none")
    fetch.extend(["origin", ref])
    _run(fetch, destination)
    _run(["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"], destination)


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _tree_snapshot(root: Path) -> Dict[str, Tuple[str, bytes]]:
    snapshot: Dict[str, Tuple[str, bytes]] = {}
    if not root.exists():
        return snapshot
    if root.is_symlink():
        raise SyncError(f"{root}: generated tree cannot be a symlink")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise SyncError(f"{path}: generated tree cannot contain symlinks")
        if not path.is_file():
            continue
        mode = "100755" if path.stat().st_mode & 0o111 else "100644"
        snapshot[path.relative_to(root).as_posix()] = (mode, path.read_bytes())
    return snapshot


def _tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for relative, (mode, content) in sorted(_tree_snapshot(root).items()):
        for value in (mode.encode("ascii"), relative.encode("utf-8"), content):
            digest.update(len(value).to_bytes(8, "big"))
            digest.update(value)
    return digest.hexdigest()


def _converter_digest(rewrites_path: Path) -> str:
    digest = hashlib.sha256()
    for path in (SCRIPT_DIR / "port_skills.py", SCRIPT_DIR / "validate_skills.py", rewrites_path):
        content = path.read_bytes()
        label = path.name.encode("utf-8")
        digest.update(len(label).to_bytes(8, "big"))
        digest.update(label)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _json_bytes(value: Mapping[str, object]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _read_existing_lock(path: Path) -> Optional[Mapping[str, object]]:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SyncError(f"could not read existing lock {path}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise SyncError(f"{path}: lock must be a JSON object")
    _validate_existing_lock(value, path)
    return value


def _validate_existing_lock(value: Mapping[str, object], path: Path) -> None:
    """Reject corrupt provenance instead of preserving or dereferencing it."""

    errors: List[str] = []
    if value.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    source = value.get("source")
    output = value.get("output")
    if not isinstance(source, Mapping):
        errors.append("source must be an object")
        source = {}
    if not isinstance(output, Mapping):
        errors.append("output must be an object")
        output = {}

    for key in ("repository", "ref", "path", "plugin_version"):
        if not isinstance(source.get(key), str) or not source[key]:
            errors.append(f"source.{key} must be a non-empty string")
    for key in ("commit", "tree", "skills_tree"):
        item = source.get(key)
        if not isinstance(item, str) or not GIT_OBJECT_RE.fullmatch(item):
            errors.append(f"source.{key} must be a 40- or 64-character lowercase Git object ID")
    license_digest = source.get("license_sha256")
    if not isinstance(license_digest, str) or not SHA256_RE.fullmatch(license_digest):
        errors.append("source.license_sha256 must be a lowercase SHA-256 digest")

    output_path = output.get("path")
    if not isinstance(output_path, str) or not output_path:
        errors.append("output.path must be a non-empty string")
    for key in ("sha256", "converter_sha256"):
        item = output.get(key)
        if not isinstance(item, str) or not SHA256_RE.fullmatch(item):
            errors.append(f"output.{key} must be a lowercase SHA-256 digest")
    skill_count = output.get("skill_count")
    if isinstance(skill_count, bool) or not isinstance(skill_count, int) or skill_count < 1:
        errors.append("output.skill_count must be a positive integer")

    if errors:
        raise SyncError(f"{path}: invalid existing lock: {'; '.join(errors)}")


def _same_source_tree(existing: Optional[Mapping[str, object]], candidate: Mapping[str, object]) -> bool:
    if not existing:
        return False
    existing_source = existing.get("source")
    candidate_source = candidate.get("source")
    existing_output = existing.get("output")
    candidate_output = candidate.get("output")
    if not all(isinstance(item, Mapping) for item in (existing_source, candidate_source, existing_output, candidate_output)):
        return False
    source_keys = ("repository", "ref", "path", "tree", "skills_tree", "plugin_version", "license_sha256")
    output_keys = ("path", "sha256", "skill_count", "converter_sha256")
    return all(existing_source.get(key) == candidate_source.get(key) for key in source_keys) and all(
        existing_output.get(key) == candidate_output.get(key) for key in output_keys
    )


def _locked_commit_matches_source(
    checkout: Path, existing: Mapping[str, object], source_path: Path, source_ref: str
) -> bool:
    """Prove a retained lock commit resolves to the trees it claims."""

    source = existing["source"]
    assert isinstance(source, Mapping)
    commit = str(source["commit"])

    def commit_exists() -> bool:
        try:
            _run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], checkout)
        except SyncError:
            return False
        return True

    def is_reachable_from_ref() -> bool:
        if not commit_exists():
            return False
        try:
            _run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], checkout)
        except SyncError:
            return False
        return True

    if not is_reachable_from_ref():
        # The checkout is intentionally shallow. Fetch the configured ref's
        # remaining commit history before deciding that an older locked commit
        # is unrelated. Blobs remain filtered for remote partial clones.
        try:
            shallow = _run(["git", "rev-parse", "--is-shallow-repository"], checkout) == "true"
        except SyncError:
            return False
        if shallow:
            try:
                _run(["git", "fetch", "--quiet", "--unshallow", "origin", source_ref], checkout)
            except SyncError:
                return False
        if not is_reachable_from_ref():
            return False
    try:
        locked_tree = _run(["git", "rev-parse", f"{commit}:{source_path.as_posix()}"], checkout)
        locked_skills_tree = _run(
            ["git", "rev-parse", f"{commit}:{(source_path / 'skills').as_posix()}"], checkout
        )
    except SyncError:
        return False
    return locked_tree == source["tree"] and locked_skills_tree == source["skills_tree"]


def _bump_patch(version: str) -> str:
    match = SEMVER_RE.match(version)
    if not match:
        raise SyncError(f"packaged plugin version must be MAJOR.MINOR.PATCH to bump: {version!r}")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch + 1}"


def _plugin_candidate(path: Path, skills_changed: bool) -> Optional[Tuple[bytes, str]]:
    """Return the manifest bytes and version to publish, bumping the patch when skills changed."""
    if path.is_symlink():
        raise SyncError(f"{path}: packaged plugin manifest cannot be a symlink")
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    try:
        manifest = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SyncError(f"{path}: packaged plugin manifest is not valid JSON: {exc}") from exc
    if not isinstance(manifest, Mapping):
        raise SyncError(f"{path}: packaged plugin manifest must be a JSON object")
    version = manifest.get("version")
    if not isinstance(version, str) or not version:
        raise SyncError(f"{path}: packaged plugin version must be a non-empty string")
    if not skills_changed:
        return raw.encode("utf-8"), version
    matches = PLUGIN_VERSION_RE.findall(raw)
    if len(matches) != 1 or matches[0][1] != version:
        raise SyncError(f"{path}: expected exactly one top-level version string to bump")
    bumped = _bump_patch(version)
    rewritten = PLUGIN_VERSION_RE.sub(lambda match: f'{match.group(1)}"{bumped}"', raw, count=1)
    return rewritten.encode("utf-8"), bumped


def _candidate_snapshot(
    repo_root: Path,
    output_path: Path,
    old_skills: Mapping[str, Tuple[str, bytes]],
    new_skills: Mapping[str, Tuple[str, bytes]],
    scalar_files: Sequence[Tuple[Path, bytes]],
) -> Tuple[Dict[str, Tuple[str, bytes]], Dict[str, Tuple[str, bytes]]]:
    old: Dict[str, Tuple[str, bytes]] = {}
    new: Dict[str, Tuple[str, bytes]] = {}
    for relative, value in old_skills.items():
        old[(output_path / relative).as_posix()] = value
    for relative, value in new_skills.items():
        new[(output_path / relative).as_posix()] = value

    for relative_path, candidate_bytes in scalar_files:
        current = repo_root / relative_path
        if current.exists():
            mode = "100755" if current.stat().st_mode & 0o111 else "100644"
            old[relative_path.as_posix()] = (mode, current.read_bytes())
        new[relative_path.as_posix()] = ("100644", candidate_bytes)
    return old, new


def _classify_changes(
    old: Mapping[str, Tuple[str, bytes]], new: Mapping[str, Tuple[str, bytes]]
) -> Mapping[str, List[str]]:
    old_paths = set(old)
    new_paths = set(new)
    return {
        "added": sorted(new_paths - old_paths),
        "modified": sorted(path for path in old_paths & new_paths if old[path] != new[path]),
        "deleted": sorted(old_paths - new_paths),
    }


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.pstack-sync-{os.getpid()}")
    temporary.write_bytes(content)
    temporary.chmod(0o644)
    os.replace(str(temporary), str(path))


def _apply_transaction(
    repo_root: Path,
    output_path: Path,
    staged_output: Path,
    license_path: Path,
    license_bytes: bytes,
    lock_path: Path,
    lock_bytes: bytes,
    skills_changed: bool,
    transaction_root: Path,
    plugin_path: Optional[Path] = None,
    plugin_bytes: Optional[bytes] = None,
) -> None:
    output = repo_root / output_path
    backup_output = transaction_root / "backup-skills"
    output_existed = output.exists()

    writes: List[Tuple[str, Path, bytes, Path, bool]] = []
    targets = [("license", license_path, license_bytes), ("lock", lock_path, lock_bytes)]
    if plugin_path is not None and plugin_bytes is not None:
        targets.append(("plugin", plugin_path, plugin_bytes))
    for label, relative_path, content in targets:
        target = repo_root / relative_path
        backup = transaction_root / f"backup-{label}"
        existed = target.exists()
        if existed:
            shutil.copy2(target, backup)
        writes.append((label, target, content, backup, existed))

    try:
        if skills_changed:
            if output_existed:
                os.replace(str(output), str(backup_output))
            os.replace(str(staged_output), str(output))
        for _label, target, content, _backup, _existed in writes:
            _write_atomic(target, content)
    except Exception:
        if skills_changed:
            if output.exists():
                shutil.rmtree(output)
            if output_existed and backup_output.exists():
                os.replace(str(backup_output), str(output))
        for _label, target, _content, backup, existed in writes:
            if existed:
                shutil.copy2(backup, target)
            elif target.exists():
                target.unlink()
        raise


def synchronize(
    repo_root: Path,
    config_path: Path,
    source_override: Optional[str] = None,
    ref_override: Optional[str] = None,
    check: bool = False,
) -> Mapping[str, object]:
    repo_root = repo_root.resolve()
    if not repo_root.is_dir():
        raise SyncError(f"{repo_root}: repository root does not exist")
    config = _load_config(config_path)
    source_config = config["source"]
    assert isinstance(source_config, Mapping)
    source = source_override or str(source_config["repository"])
    ref = ref_override or str(source_config["ref"])
    source_path = _safe_relative(str(source_config["path"]), "source.path")
    output_path = _safe_relative(str(config["output"]), "output")
    lock_path = _safe_relative(str(config["lock"]), "lock")
    license_path = _safe_relative(str(config["license"]), "license")
    plugin_config = config.get("plugin")
    plugin_path = _safe_relative(str(plugin_config), "plugin") if plugin_config else None
    rewrites_path = (PROJECT_ROOT / _safe_relative(str(config["rewrites"]), "rewrites")).resolve()
    if not rewrites_path.is_file():
        raise SyncError(f"{rewrites_path}: rewrite configuration does not exist")

    existing_lock = _read_existing_lock(repo_root / lock_path)
    with tempfile.TemporaryDirectory(prefix="pstack-upstream-") as checkout_name:
        checkout = Path(checkout_name)
        _checkout(source, ref, source_path, checkout)
        commit = _run(["git", "rev-parse", "HEAD"], checkout)
        tree = _run(["git", "rev-parse", f"HEAD:{source_path.as_posix()}"], checkout)
        skills_tree = _run(["git", "rev-parse", f"HEAD:{(source_path / 'skills').as_posix()}"], checkout)
        pstack_root = checkout / source_path

        license_source = pstack_root / "LICENSE"
        if license_source.is_symlink():
            raise SyncError(f"{license_source}: upstream license cannot be a symlink")
        if not license_source.is_file():
            raise SyncError(f"{license_source}: upstream license is missing")
        license_bytes = license_source.read_bytes()
        license_text = license_bytes.decode("utf-8", errors="strict")
        if not license_text.startswith("MIT License\n") or "Permission is hereby granted" not in license_text:
            raise SyncError("upstream pstack license is no longer recognizably MIT; review manually")

        manifest_path = pstack_root / ".cursor-plugin" / "plugin.json"
        if manifest_path.is_symlink() or manifest_path.parent.is_symlink():
            raise SyncError(f"{manifest_path}: upstream manifest cannot use symlinks")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_version = manifest["version"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise SyncError(f"could not read upstream plugin version from {manifest_path}: {exc}") from exc
        if not isinstance(plugin_version, str) or not plugin_version:
            raise SyncError(f"{manifest_path}: version must be a non-empty string")

        with tempfile.TemporaryDirectory(prefix=".pstack-sync-", dir=str(repo_root)) as transaction_name:
            transaction = Path(transaction_name)
            staged_output = transaction / "skills"
            try:
                skill_count = port_skills(pstack_root, staged_output, rewrites_path)
            except PortError as exc:
                raise SyncError(str(exc)) from exc
            validation_errors = validate_skills(staged_output)
            if validation_errors:
                joined = "\n".join(f"- {error}" for error in validation_errors)
                raise SyncError(f"generated skills failed validation:\n{joined}")

            output_digest = _tree_digest(staged_output)
            candidate_lock: Mapping[str, object] = {
                "schema_version": 1,
                "source": {
                    "repository": source,
                    "ref": ref,
                    "path": source_path.as_posix(),
                    "commit": commit,
                    "tree": tree,
                    "skills_tree": skills_tree,
                    "plugin_version": plugin_version,
                    "license_sha256": _sha256_bytes(license_bytes),
                },
                "output": {
                    "path": output_path.as_posix(),
                    "sha256": output_digest,
                    "skill_count": skill_count,
                    "converter_sha256": _converter_digest(rewrites_path),
                },
            }
            if (
                _same_source_tree(existing_lock, candidate_lock)
                and existing_lock is not None
                and _locked_commit_matches_source(checkout, existing_lock, source_path, ref)
            ):
                candidate_lock = existing_lock  # Ignore upstream commits outside pstack.
            lock_bytes = _json_bytes(candidate_lock)
            old_skills = _tree_snapshot(repo_root / output_path)
            new_skills = _tree_snapshot(staged_output)
            skills_changed = old_skills != new_skills
            scalar_files: List[Tuple[Path, bytes]] = [
                (license_path, license_bytes),
                (lock_path, lock_bytes),
            ]
            plugin_bytes: Optional[bytes] = None
            packaged_version: Optional[str] = None
            if plugin_path is not None:
                candidate_plugin = _plugin_candidate(repo_root / plugin_path, skills_changed)
                if candidate_plugin is not None:
                    plugin_bytes, packaged_version = candidate_plugin
                    scalar_files.append((plugin_path, plugin_bytes))
            old_snapshot, new_snapshot = _candidate_snapshot(
                repo_root,
                output_path,
                old_skills,
                new_skills,
                scalar_files,
            )
            changes = _classify_changes(old_snapshot, new_snapshot)
            changed = any(changes.values())
            report: Mapping[str, object] = {
                "changed": changed,
                "check": check,
                "source": {
                    "repository": source,
                    "ref": ref,
                    "path": source_path.as_posix(),
                    "previous_commit": (
                        existing_lock.get("source", {}).get("commit")
                        if isinstance(existing_lock, Mapping) and isinstance(existing_lock.get("source"), Mapping)
                        else None
                    ),
                    "commit": candidate_lock["source"]["commit"],
                    "tree": candidate_lock["source"]["tree"],
                    "plugin_version": plugin_version,
                },
                "output": {
                    "skill_count": skill_count,
                    "sha256": output_digest,
                    "plugin_version": packaged_version,
                },
                "changes": changes,
            }
            if changed and not check:
                _apply_transaction(
                    repo_root,
                    output_path,
                    staged_output,
                    license_path,
                    license_bytes,
                    lock_path,
                    lock_bytes,
                    skills_changed,
                    transaction,
                    plugin_path=plugin_path if plugin_bytes is not None else None,
                    plugin_bytes=plugin_bytes,
                )
            return report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "sync-config.json")
    parser.add_argument("--source", help="Override upstream Git URL/path (primarily for tests)")
    parser.add_argument("--ref", help="Override upstream Git ref")
    parser.add_argument("--check", action="store_true", help="Report drift without writing")
    parser.add_argument("--report-json", type=Path, help="Write a deterministic synchronization report")
    args = parser.parse_args(argv)

    try:
        report = synchronize(
            repo_root=args.repo_root,
            config_path=args.config.resolve(),
            source_override=args.source,
            ref_override=args.ref,
            check=args.check,
        )
    except (OSError, UnicodeError, SyncError) as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 2

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    change_count = sum(len(paths) for paths in report["changes"].values())
    if report["changed"]:
        verb = "would update" if args.check else "updated"
        print(f"{verb} {change_count} paths from upstream {report['source']['commit']}")
        return 1 if args.check else 0
    print(f"already synchronized with upstream tree {report['source']['tree']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
