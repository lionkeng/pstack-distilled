# pstack-distilled

Engineering skills and playbooks from Lauren Tan's
[`pstack`](https://github.com/cursor/plugins/tree/main/pstack) Cursor plugin.

This distillation of pstack removes Cursor specific artifacts and writes the skills in standard [Agent Skills specification](https://agentskills.io/specification). This repo is not affiliated with or endorsed by Cursor.

## Contents

`skills/` contains the generated skills. Each skill is a `SKILL.md` file with
frontmatter and bundled resources that use relative paths.

The sync script copies instructions, playbooks, references, and scripts.
It strips Cursor invocation metadata and pinned model names, then replaces
Cursor paths and product names with host-agnostic placeholders. Custom
agents, the plugin manifest, the docs site, and the Benny automation pack
remain upstream. Two skills also remain upstream. `poteto-help` documents
Cursor setup and links into the docs site. `make-bot-ui` depends on Cursor
Automations webhooks and cannot work on another host.

Some playbooks name Bugbot, a GitHub review bot, as an example of an automated
reviewer. The bundled `watch-pr` script treats every unresolved review thread
as a blocker, regardless of its author.

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

### Claude Code

Claude Code reads this repository as a plugin. `.claude-plugin/plugin.json`
marks the root, and `.claude-plugin/marketplace.json` lets Claude Code install
it by repository. Either add the marketplace:

```sh
claude plugin marketplace add lionkeng/pstack-distilled
claude plugin install pstack@pstack-distilled
```

Or point `~/.claude/skills/` at a local clone, which auto-loads on the next
session:

```sh
ln -s /path/to/pstack-distilled ~/.claude/skills/pstack
claude plugin list          # pstack@skills-dir, loaded
claude plugin details pstack
```

Both routes namespace the skills, so `how` is invoked as `pstack:how`. The
namespace keeps names such as `tdd` from colliding with skills already
installed. Skill descriptions stay resident for the session; `claude plugin
details pstack` reports that cost.

Read third-party skills before you install them. Some pstack playbooks call
GitHub CLI, Bun, or a helper that stacks git branches. Others use host
features such as delegation and conversation history. If the host cannot
delegate or run background work, follow the playbook's inline or sequential
instructions.

### Helper compatibility

`watch-pr` emits JSON schema version 2. Consumers must handle the
`mergeability-unknown` wait and timeout reason and the `base-behind` merge
gate. Unknown mergeability waits for another observation. A stale base
blocks readiness. Owner approval remains a separate human decision.

Saved multi-phase plans need a `pstack-plan-context` block. Record the
product trunk separately from the installed instruction paths and their
content hashes. Choose a recurring host task or bounded active-session
polling. Validate the plan before arming a task. At execution startup, run
the checker with `--startup` after creating the progress file and recording
the recurring handle when needed. The checker verifies local state and
the declared handle. Verify the host task itself through the host.

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
version, license checksum, and output digest. `LICENSE` is generated too: the
sync ships upstream's MIT text with the `license_copyright` line from
`sync-config.json` added below upstream's holder, so do not hand-edit it — the
next sync would overwrite the change. When the generated skills change,
the sync bumps the patch version in `.claude-plugin/plugin.json` so anyone who
installed the plugin sees an update. Put conversion rules in
`porting/rewrites.json` or the conversion code, never in `skills/`: the next
sync regenerates that tree, and `verify_lock.py` fails until the lock matches
the checked-in output.

`porting/rewrites.json` has two sections. `literal` lists text replacements
applied to every converted file. `skills` maps an upstream skill name to a
replacement `description` and to `body` rules. Each body rule names an exact
`from` passage that must occur once in the converted `SKILL.md` and the `to`
text that replaces it. When upstream rewrites that passage, the sync fails
instead of dropping the edit. A `files` map applies the same exact rules to
other converted files in the skill, keyed by path relative to the skill, such
as `playbooks/shipping.md`. An `explicit` value of `false` keeps a skill
open to automatic triggering when upstream marks it explicit-only. An
`exclude` value of `true` leaves the skill out of `skills/`, and it cannot
appear with other keys.

Every `literal` rule, and every text rule in `scripts/port_skills.py`, must
match upstream text at least once. When upstream rewords or deletes a passage,
the sync fails and names each rule that matched nothing. Update the rule to the
new wording, or delete it if the passage is gone. Without this check, a
reworded passage would ship its Cursor wording unchanged. The offline tests
pass `--allow-unmatched-rules`, because their upstream fixture holds only a few
skills. In that mode, a `body` or `files` rule whose text or file is absent is
skipped. A rule that matches more than once still fails.

After changing conversion rules, rebuild the tree from the locked upstream
commit and refresh the lock without pulling newer upstream commits:

```sh
python3 scripts/sync_upstream.py --regenerate
```

Run the offline sync and validation tests with:

```sh
python3 -m unittest discover -s tests -v
```

### Verify generated behavior

Keep downstream regressions in `tests/`. They read and execute generated
files, including Markdown examples. After changing a conversion rule, run
the Python suite above and confirm that a second generation is unchanged:

```sh
python3 scripts/sync_upstream.py --regenerate --check
```

Run the bundled and downstream runtime checks with Node 24.18.0 and
Bun 1.4.2:

```sh
cd skills/poteto-mode/scripts
bun install --frozen-lockfile
bun test watch-pr check-plan.test.ts
bun run typecheck
cd ../../..
bun test tests/runtime/watch-pr-readiness.test.ts tests/runtime/check-plan-portability.test.ts tests/runtime/type-examples.test.ts
```

For statechart integration checks, set `JAVA` to a Java executable and
`TLA2TOOLS` to the TLC 1.7.4 jar pinned in `skills/statechart/scripts/run.ts`.
CI uses Temurin 25 and verifies the jar's checksum before running these tests:

```sh
node --disable-warning=ExperimentalWarning --test --test-concurrency=2 skills/statechart/scripts/test/cli.test.ts tests/runtime/statechart.test.mjs
```

The [test workflow](.github/workflows/test.yml) also runs the corpus,
plain-TLC, configuration fuzz, and differential suites. It copies the
generated scripts into a temporary directory and installs their test
dependencies with `tests/runtime/statechart-deps/bun.lock`. Keep that lock
compatible with the generated statechart `package.json`. Required live
tests must have Java and TLC available. A skipped live test is incomplete
verification.

When upstream changes a corrected passage, inspect the failed exact rule.
Remove the rule only if upstream now supplies the correction. Otherwise,
update its anchor and retain the behavioral regression. Do not hand-edit
generated files or allow unmatched rules in a real sync.

### Scheduled synchronization

The scheduled GitHub workflow runs the Python suite, then opens or updates the
`automation/sync-pstack` pull request. It dispatches the test workflow on
the generated branch, including runtime checks of the generated helpers.
The test jobs have read-only repository permissions. You merge the PR.
The sync workflow writes only bot sync commits to that branch. If the
branch's tip is not a prior bot sync commit, the workflow stops.

For bot-created pull requests, enable **Settings > Actions > General > Allow
GitHub Actions to create and approve pull requests**. The workflow grants
only `actions: write`, `contents: write`, and `pull-requests: write` to its
built-in token. It uses `actions: write` to dispatch tests on the generated
branch. GitHub ignores push and pull_request triggers from that token.

## License and attribution

pstack-distilled uses the same MIT License as upstream. [`LICENSE`](LICENSE)
carries upstream's copyright notice and this distribution's, in that order. See
[`NOTICE.md`](NOTICE.md) for attribution. Each generated skill names its upstream source in `metadata`.
