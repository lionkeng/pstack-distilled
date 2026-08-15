# pstack-distilled

Portable engineering skills and playbooks sourced from the original
[`pstack`](https://github.com/cursor/plugins/tree/main/pstack) Cursor plugin by
[Lauren Tan](https://github.com/poteto).

This repository is an independent portability fork. It preserves pstack's
high-signal engineering workflows while converting their packaging and
runtime language to the open [Agent Skills specification](https://agentskills.io/specification).
It is not affiliated with or endorsed by Cursor.

## What is included

`skills/` contains the generated, distributable skills. Each skill uses the
portable `SKILL.md` format with standard frontmatter, relative bundled
resources, and capability-oriented instructions. Cursor-only invocation
metadata, fixed model identifiers, and hard-coded host paths are removed or
expressed as portable intent.

The Cursor plugin's custom agents, plugin manifest, documentation site, and
Benny automation pack are not copied because they are not Agent Skills. The
valuable skill instructions, playbooks, references, and bundled scripts are
ported.

## Install

Install the full `skills/` tree by default. Several workflows intentionally
compose sibling skills such as `how`, `why`, `unslop`, and `poteto-mode`, and
the Agent Skills format has no dependency metadata. A single-skill install is
best-effort: also install every sibling skill it names. Discovery paths are
host behavior rather than part of the Agent Skills standard; common
project-level locations include `.agents/skills/` and `.claude/skills/`.

For example, for a host that discovers `.agents/skills/`:

```sh
mkdir -p .agents/skills
cp -R /path/to/pstack-distilled/skills/. .agents/skills/
```

Review third-party skills before installation. Some pstack playbooks can use
optional capabilities such as delegation, conversation history, GitHub CLI,
Bun, or a branch-stacking tool. Portable instructions define an inline or
sequential fallback when a host lacks delegation or background execution.

## Upstream synchronization

Generated files under `skills/` are not edited by hand. The synchronization
command fetches upstream into a temporary sparse checkout, converts the skills,
validates the complete staged result, and only then updates this repository:

```sh
python3 scripts/sync_upstream.py
python3 scripts/validate_skills.py skills
python3 scripts/verify_lock.py
```

The source checkout is discarded and never committed. `upstream.lock.json`
records the exact upstream commit, subtree, plugin version, license checksum,
and generated output digest. Portability behavior belongs in
`porting/rewrites.json` or the conversion code.

Run all offline synchronization and conformance tests with:

```sh
python3 -m unittest discover -s tests -v
```

The scheduled GitHub workflow runs the same command, validates the result, and
opens or updates a reviewable `automation/sync-pstack` pull request. It never
executes scripts fetched from upstream and does not auto-merge changes. The
branch is reserved for bot-authored sync commits; the workflow refuses to
overwrite an unrecognized branch.

For bot-created pull requests, enable **Settings → Actions → General → Allow
GitHub Actions to create and approve pull requests**. The workflow grants only
`actions: write`, `contents: write`, and `pull-requests: write` to its built-in
token. `actions: write` is used only to dispatch the test workflow for the
generated branch, because GitHub suppresses ordinary workflow triggers caused
by its built-in token.

## License and attribution

pstack-distilled uses the same MIT License as upstream. The original copyright
notice is retained in [`LICENSE`](LICENSE), additional provenance is recorded
in [`NOTICE.md`](NOTICE.md), and every generated skill identifies its upstream
source in standard `metadata`.
