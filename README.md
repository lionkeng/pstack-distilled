# pstack-distilled

Engineering skills and playbooks from Lauren Tan's
[`pstack`](https://github.com/cursor/plugins/tree/main/pstack) Cursor plugin.

This distillation of pstack removes Cursor specific artifacts and writes the skills in standard [Agent Skills specification](https://agentskills.io/specification). Thi repo is not affiliated with or endorsed by Cursor.

## Contents

`skills/` contains the generated skills. Each skill is a `SKILL.md` file with
frontmatter and bundled resources that use relative paths.

The sync script copies instructions, playbooks, references, and scripts.
It strips Cursor invocation metadata and pinned model names, then replaces
Cursor paths and product names with host-agnostic placeholders. Custom
agents, the plugin manifest, the docs site, and the Benny automation pack
remain upstream.

## Install

Copy the full `skills/` tree. Skills such as `how`, `why`, `unslop`, and
`poteto-mode` call other skills in the tree. Agent Skills has no dependency
field, so if you copy one skill, copy every skill it names.

The host looks in a configured directory. Common project paths are
`.agents/skills/` and `.claude/skills/`.

If the host reads `.agents/skills/`:

```sh
mkdir -p .agents/skills
cp -R /path/to/pstack-distilled/skills/. .agents/skills/
```

Read third-party skills before you install them. Some pstack playbooks call
GitHub CLI, Bun, or a helper that stacks git branches. Others use host
features such as delegation and conversation history. If the host cannot
delegate or run background work, follow the playbook's inline or sequential
instructions.

## Upstream sync

Sync upstream and check the result:

```sh
python3 scripts/sync_upstream.py
python3 scripts/validate_skills.py skills
python3 scripts/verify_lock.py
```

The sync script fetches upstream into a temporary sparse checkout and converts
the skills. It validates the staged tree, updates this repository, and deletes
the checkout. `upstream.lock.json` records the upstream commit, subtree, plugin
version, license checksum, and output digest. Put conversion rules in
`porting/rewrites.json` or the conversion code.

Run the offline sync and validation tests with:

```sh
python3 -m unittest discover -s tests -v
```

The scheduled GitHub workflow runs those tests, then opens or updates the
`automation/sync-pstack` pull request. It does not run scripts fetched from
upstream. You merge the PR. The workflow writes only bot sync commits to that
branch. If that branch's tip is not a prior bot sync commit, the workflow
stops.

For bot-created pull requests, enable **Settings > Actions > General > Allow
GitHub Actions to create and approve pull requests**. The workflow grants
only `actions: write`, `contents: write`, and `pull-requests: write` to its
built-in token. It uses `actions: write` to dispatch tests on the generated
branch. GitHub ignores push and pull_request triggers from that token.

## License and attribution

pstack-distilled uses the same MIT License as upstream. The original copyright
notice is in [`LICENSE`](LICENSE). See [`NOTICE.md`](NOTICE.md) for
attribution. Each generated skill names its upstream source in `metadata`.
