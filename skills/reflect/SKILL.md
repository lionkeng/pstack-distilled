---
name: "reflect"
description: "Explicit request or pstack routing only. Review conversation evidence for lessons and propose targeted skill improvements."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/reflect"
  pstack-distilled-activation: "explicit"
---
# Reflect

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


Mine the current conversation for durable learnings, then route them into skill edits.

## When to invoke

Invoke when the user says "reflect" or "reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## Process

### 1. Locate the active conversation record

Use only conversation history explicitly exposed by the host for the active workspace or supplied by the user. Ask the host for recent records and use exposed metadata to identify the active conversation. Do not assume a filesystem layout or JSON schema, and never probe private host storage. If no history capability resolves the active record, write a tight digest of the current conversation and pass that instead.

### 2. Spawn three reviewers in parallel

One message, three delegation calls, `worker role: general-purpose`, with `model` set as below, agent mode (`readonly: false`). Reviewers need MCP access for context lookups (tickets, chat threads, observability traces referenced in the conversation record). Readonly strips MCPs.

Each reviewer and the synthesizer name a role line in the `pstack-models.mdc` rule and a default. Set `model` to that line's value, or to the default if the rule or the line is missing. Leave `model` unset when the value is `auto` or `inherit-parent`. If the host delegation capability rejects a slug, use the default and say so. If it rejects the default, use the closest valid slug of the same family from its error message.

| Lens | Role line | Default `model` | Prompt template |
|---|---|---|---|
| Judgment | `reflect judgment, divergent, synthesizer` | `available-model` | `references/judgment-reviewer.md` |
| Tooling | `reflect tooling` | `deep-code-model` | `references/tooling-reviewer.md` |
| Divergent | `reflect judgment, divergent, synthesizer` | `available-model` | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the conversation-record path or digest where marked. Reviewers return findings in the delegated worker's response.

### 3. Synthesize

One delegation call, `worker role: general-purpose`, with `model` from the `reflect judgment, divergent, synthesizer` line (default `available-model`), agent mode (`readonly: false`). The synthesizer's quality check includes spot-verifying citations, which can require MCP access. Readonly strips MCPs. Use `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. The synthesizer returns a structured Accepted / Rejected / Backlog list.

### 4. Structural enforcement check

Sanity-check the synthesizer's Accepted list. For any item that would be enforced more reliably by a lint rule, script, metadata flag, or runtime check, move it from Accepted to Backlog. See the **encode-lessons-in-structure** principle skill.

### 5. Apply

Before applying any Accepted edit, present the synthesizer's full Accepted/Rejected/Backlog output to the user and wait for explicit approval. The user picks which subset to apply and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

Backlog items file to whatever devex / backlog tracker your team uses automatically. Only the Accepted list waits for approval.

For each approved Accepted item, follow the Routing field exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): parent does directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to Agent Skills authoring workflow and run its draft / test / iterate loop.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to Agent Skills authoring workflow and run its description-optimization loop.
- `new skill via Agent Skills authoring workflow: <kebab-name>`: hand creation to Agent Skills authoring workflow. Do not invent the shape ad hoc.

If your environment ships a SKILL.md validator, run it on every touched skill before declaring done. Skip this step if it doesn't.

### 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
