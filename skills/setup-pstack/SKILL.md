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

Use the host's model inventory if it exposes one. Confirm every explicit model ID before writing it. If no inventory is available, leave roles on `auto`; ask the user for IDs only when they request explicit model choices. Never guess availability or family from an ID's spelling. `auto` and `inherit-parent` always mean use the parent model.

### 2. Load current state

The default role-to-model mapping is the file shape shown in step 5 below. If `.pstack/models.md` already exists, read it and treat its `# budget` line and its role values as the current choices. Otherwise start from those defaults. A line whose role is not in step 5, such as `how critics`, is from a retired role. Drop it.

### 3. Budget, map, and confirm

**(a) Choose effort only when supported.** If the host exposes a reasoning-effort control, ask the user whether to use its default, a lower level, or a higher level. Show the host's actual choices. Without such a control, keep the host default and do not ask for a budget.

**(b) Apply it.** Keep confirmed model IDs unchanged. Set effort through the host's documented control when it exists; never edit an ID to guess an effort level, speed, or family. `auto` and `inherit-parent` keep the parent model and its default effort. Record the choice in the configuration file only when the host can apply it.

**(c) Show the roles and confirm.** Show every role and its configured ID or `auto`. Offer only confirmed available IDs, `auto`, and `inherit-parent`. For panel roles, each entry is one seat. Order the cross-judge pool by preference; prefer a different family only when the host explicitly identifies families. If it does not, an independent judge on the parent model is valid. Drop retired role lines and tell the user which ones changed.

### 4. Validate

Every explicit model ID must be confirmed available in this session. `auto` and `inherit-parent` always pass. If a chosen ID is unavailable, keep that role on `auto` and report it.

### 5. Write the configuration file

Write `.pstack/models.md` with `schema-version: 1`, a `# budget` line with the host default or a confirmed effort choice, and one line per role, using the same labels poteto-mode uses. Overwrite the whole file so re-runs stay idempotent. Shape:

```
---
description: pstack per-role model choices (overrides skill defaults)
schema-version: 1
---
# pstack model configuration. One line per role. Delete a line to fall back to the skill default.
# `inherit-parent` or `auto` as a value: the role runs on the parent chat model (leave the model unset on the delegation call). Alias entries in a panel list still count toward its fan-out.
# budget: host default
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

Tell the user the configuration file was written and that it applies to new sessions. Re-running this skill updates it.

### 7. Offer a verification skill (optional)

Check whether the project has a way to drive the real app for proof (a `verify-*` skill, or an existing harness). If not, offer once: "want a project-local verification skill, so agents can drive the app the way a user does and prove changes work? I can generate one with create-verification-skill." On yes, invoke `create-verification-skill` (resolves wherever pstack is installed: workspace, user, or plugin). On no, move on without pushing.

### 8. Offer a formal verification skill (optional)

Check whether the project already has a formal verification skill (a project skill that runs a model checker, a proof, or another verifier against the code). If not, offer once: "want a formal verification skill, so agents can prove a key property of your code holds in every case in scope, not only the cases tests reach? I can generate one with create-formal-verification-skill." On yes, invoke `create-formal-verification-skill` (resolves wherever pstack is installed: workspace, user, or plugin). On no, move on without pushing.
