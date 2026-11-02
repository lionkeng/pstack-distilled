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

Invoke when the user explicitly says "reflect". Skip when the conversation is trivial, off-topic, or already covered by an existing skill the parent followed correctly. One-offs are not learnings.

## 1. Locate the active conversation record

Use the current conversation. If the host explicitly exposes a record of this conversation, use only that record. Otherwise pass a short digest of the session to the reviewers.

## 2. Spawn three reviewers in parallel

Run three independent reviewers when delegation is available. Give them access to the evidence tools needed to check the conversation record. Otherwise apply the three reviewer lenses in sequence.

Each reviewer and the synthesizer reads its role line in `.pstack/models.md`. Without a configured model ID, omit `model` so the parent model runs the role. Pass an ID only after the host confirms it is available; if rejected, omit it and say so. Use effort and speed controls only when the host exposes them.

| Lens | Role line | Default `model` | Prompt template |
|---|---|---|---|
| Judgment | `reflect judgment, divergent, synthesizer` | `auto` | `references/judgment-reviewer.md` |
| Tooling | `reflect tooling` | `auto` | `references/tooling-reviewer.md` |
| Divergent | `reflect judgment, divergent, synthesizer` | `auto` | `references/divergent-reviewer.md` |

Pass each template verbatim, substituting the conversation-record path or digest where marked. Reviewers return findings in the delegated worker's response.

## 3. Synthesize

One delegation call, `worker role: general-purpose`, `model` from the `reflect judgment, divergent, synthesizer` line (default `auto`), with access to the evidence tools needed to spot-check citations. Pass `references/synthesizer.md` verbatim, with each reviewer's full output inlined where marked. It returns an Accepted / Rejected / Backlog list.

## 4. Structural enforcement check

Move any Accepted item that a lint rule, script, metadata flag, or runtime check would enforce more reliably to Backlog. See the **encode-lessons-in-structure** principle skill.

## 5. Apply

Present the synthesizer's full Accepted / Rejected / Backlog output and wait for explicit approval before applying any Accepted edit. The user picks the subset and may redirect routings. Skill changes affect every future agent in the org. Do not auto-apply.

File each Backlog item to your team's devex or backlog tracker without waiting. Only the Accepted list waits for approval.

Never edit a skill under `plugins/cache/`. Before approval, show its destination, `<project-skill-directory>/<skill>/` or `<user-skill-directory>/<skill>/`. After approval, copy the skill folder there and edit the copy. Never open a PR or push.

Follow each approved row's Routing exactly:

- Trivial existing-skill edit (a one-line bullet, a tightened sentence, a stale fact corrected): the parent does it directly.
- Substantive existing-skill edit (a new section, a new pattern table, more than ~10 lines): hand to Agent Skills authoring workflow and run its draft / test / iterate loop.
- `tune description: <skill path>` (the skill exists but didn't trigger when it should have): hand to Agent Skills authoring workflow and run its description-optimization loop.
- `new skill via Agent Skills authoring workflow: <kebab-name>`: hand creation to Agent Skills authoring workflow. Do not invent the shape ad hoc.

If your environment ships a SKILL.md validator, run it on every touched skill before declaring done.

## 6. Summarize for the user

Short list, no preamble:

- Edits applied: `<skill path>`. What changed, one line each.
- New skills created: `<skill path>`. One line each (rare).
- Backlog filed to the devex tracker: `<issue title>` (`<tags>`). One line each.
- Dropped: one line per rejected finding + reason from the synthesizer.
