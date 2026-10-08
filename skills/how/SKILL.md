---
name: "how"
description: "Explains subsystem behavior, runtime flow, or module ownership when asked how code works. Use why for historical rationale."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/how"
---
# How

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


Explore the codebase to answer "how does X work?" questions. Produce architectural explanations at the level of a senior engineer onboarding onto a subsystem, enough to build a working mental model, not so much that it reads like annotated source code.

Each spawn below names a role line in `.pstack/models.md` and a default. Set `model` to that line's value, or to the default if the rule or the line is missing. Leave `model` unset when the value is `auto` or `inherit-parent`. If the host delegation capability rejects a slug, use the default and say so. If it rejects the default, use the closest valid slug of the same family from its error message.

## Step 1. Assess Complexity

If the scope is ambiguous, state your interpretation and explore. The user can redirect.

- **Simple** (a single module, a small utility, a narrow question such as "how does function X work"): no explorers. One explainer explores and explains in a single pass. Go to Step 2b.
- **Complex** (a subsystem spanning multiple files or services, a cross-cutting feature, a full architectural overview): spawn parallel explorers first, then hand off to the explainer. Go to Step 2a.

When in doubt, take the simple path.

## Step 2a. Explore (complex questions only)

Decompose the question into 2 to 4 exploration angles, each a distinct slice of the subsystem. Spawn all explorers in a single message:

- `worker role`: `general-purpose`
- `model`: the `how explorer` line, default `fast-code-model`
- `readonly`: `true`

Each explorer gets the prompt in `references/explorer-prompt.md` with its angle filled in. Then go to Step 3.

## Step 2b. Direct Explain (simple questions)

Explore and explain in the current thread for a simple question. Read `references/explainer-prompt.md` if its communication guidance is needed, then proceed to Step 4. Delegation is optional when it adds useful independent work; the following configuration applies only when delegating:

- `worker role`: `general-purpose`
- `model`: the `how explainer` line, default `judgment-model`
- `readonly`: `true`

Build its prompt from `references/explainer-prompt.md` without the explorer-findings section. Go to Step 4.

## Step 3. Synthesize (complex questions only)

Once all explorers have returned, spawn one delegated worker to synthesize their findings into one explanation:

- `worker role`: `general-purpose`
- `model`: the `how explainer` line, default `judgment-model`
- `readonly`: `true`

Build its prompt from `references/explainer-prompt.md` with every explorer's findings filled in.

## Step 4. Present

Present the explainer's output to the user. Light edits for clarity or context from the conversation are fine. Do not substantially rewrite it.

## Output Format

The explanation uses the sections defined in `references/explainer-prompt.md`, dropping any that do not apply: Overview, Key Concepts, How It Works, Where Things Live, Gotchas.
