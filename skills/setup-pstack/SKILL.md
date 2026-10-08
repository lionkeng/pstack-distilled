---
name: "setup-pstack"
description: "Configure which models pstack uses per role and at what reasoning budget. Detects your available models and writes a shared configuration file that overrides the skill defaults. Use for setup-pstack, \"configure pstack models\", \"pstack budget\", or changing pstack's model choices."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/setup-pstack"
---
# Setup pstack

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


Write `.pstack/models.md`, a shared configuration file that sets pstack's model per role.

## Steps

### 1. Detect available models

Enumerate the model identifiers the host can assign to delegated workers in this session. That is the dependable source. If the host also exposes a models API or CLI that lists the user's entitled models, prefer it for completeness. If you cannot detect any, ask the user to paste the slugs they have access to. Never write a real slug you have not confirmed is available. The aliases `inherit-parent` and `auto` are always valid even though they are not detected slugs.

### 2. Load current state

The default role-to-model mapping is the rule shape shown in step 5 below. If `.pstack/models.md` already exists, read it and treat its `# budget` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it.

### 3. Budget, map, and confirm

**(a) Ask for a budget.** Prefer the host's user-interaction capability over free text. Offer these four options with these exact labels, and name the current budget when the rule records one. With no rule, say that `large` matches the skill defaults.

- `unlimited — max reasoning`
- `large — xhigh reasoning`
- `medium — high reasoning`
- `small — medium reasoning`

**(b) Apply it.** Build the working table from the skill defaults, and on a re-run keep any role you changed by family, list, or alias (`inherit-parent`, `auto`). `unlimited`, `large`, `medium`, and `small` set the effort token of every real slug, panel entries included, to `max`, `xhigh`, `high`, or `medium`. The effort token is the last token, or the one before a trailing `fast`, on the ladder `max` > `xhigh` > `high` > `medium` > `low`. If the result is not a detected slug, use the same family's detected slug with the highest effort at or below the target, else mark the role as needing a choice. `inherit-parent` and `auto` do not change. For example, `unlimited` moves a `<family>-xhigh` slug to `<family>-max` when the host detects that slug. A family whose slugs stop at `xhigh` stays at `xhigh`. `small` moves each real slug to its family's `medium` slug.

**(c) Show the roles and confirm.** Show every role with its model, marking any real slug not in the detected set as needing a choice. Also list each line step 2 dropped. Ask whether to accept as-is or change specific roles, offering the detected models plus `inherit-parent` and `auto` (both mean: this role runs on the parent chat model, which is how Auto users stay on Auto) as the options. Prefer the host's user-interaction capability over free text. For panel roles (arena runners, architect runners, interrogate reviewers) the value is a list, and one subagent runs per entry, alias entries included, so the list length sets the count. `arena cross-judge pool` is also a list, but Arena selects one value from it whose model family differs from the parent's when possible. `swarm workers` is the default model for every worker unless a race or comparison assigns another model per arm.

### 4. Validate

Every real slug written must be in the detected set. `inherit-parent` and `auto` always pass. If a chosen real slug is not available, stop and ask again.

### 5. Write the rule

Write `.pstack/models.md` with `schema-version: 1`, a `# budget` line with the chosen label and its target effort, and one line per role, using the same labels poteto-mode uses. Overwrite the whole file so re-runs stay idempotent. Shape:

```
---
description: pstack per-role model choices (overrides skill defaults)
schema-version: 1
---
# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (omit delegation operation `model`). Alias entries in a panel list still count toward its fan-out.
# budget: large (xhigh)
feature, refactoring: auto
bug-fix: auto
perf-issue: auto
hillclimb: auto
judgment and prose: auto
hardest tasks: auto
how explorer: auto
how explainer: auto
why investigators: auto
why synthesizer: auto
reflect tooling: auto
reflect judgment, divergent, synthesizer: auto
arena runners: auto, auto
arena cross-judge pool: auto, auto
swarm workers: auto
architect runners: auto, auto
interrogate reviewers: auto, auto
```

### 6. Confirm

Tell the user the rule was written and that it applies to new sessions. Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with create-verification-skill." On yes, invoke `create-verification-skill` (resolves wherever pstack is installed: workspace, user, or plugin). On no, move on without pushing.
