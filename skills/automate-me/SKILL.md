---
name: "automate-me"
description: "Use only when explicitly requested or when another pstack skill directs you to it. Use for \"automate me\", \"create/update/refresh my -mode skill\", \"turn/capture my preferences or working style into a skill\", or wanting agents to follow how the user works. Drafts or revises a personal -mode skill with an Agent Skills-compatible authoring workflow and unslop, optionally pulling fresh evidence from recent conversation records."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/automate-me"
  pstack-distilled-activation: "explicit"
---
# Automate me

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


A guided flow for turning the user's working conventions into a skill agents will follow. The output is one `-mode` skill tailored to them (e.g. `jay-mode`, `priya-mode`).

This skill combines an inline mining pass, an Agent Skills-compatible authoring and validation workflow, and the **unslop** skill for prose discipline.

## Flow

### 0. Check for an existing skill

Look recursively for `<project-skill-directory>/**/*-mode/SKILL.md` and `<user-skill-directory>/*-mode/SKILL.md` matching the user's handle. Mode skills can live in a personal category directory (`<project-skill-directory>/<handle>/`), not only at the top level. If one exists, confirm intent with the host's structured user-interaction capability (unless they already said "update my skill" or similar):

- Update the existing skill (default for repeat runs)
- Start fresh (rare; ask why before doing it)

Update mode changes the rest of the flow:
- Step 1 mines only history since the skill was last edited (`git log -1 --format=%cI <path>`).
- Step 2 asks what's changed or missing, not what to capture from zero.
- Step 4 edits the existing file in place. Preserve sections the user hasn't contradicted; revise ones with new evidence; add new sections only for genuinely new rules.

### 1. Mine their history

Locate the active workspace's conversation records before fanning out. Use only a conversation-history source explicitly exposed for the active workspace. Never probe private storage or another workspace's history.

Survey recent agent conversations within that scope for recurring patterns. Run multiple parallel subagents across slices of history (e.g. last 2-4 weeks, split into 3 slices so each has enough material). Each slice mining subagent reads conversation records from the workspace-scoped path the parent provides, looks for the signals below, and returns a short structured list of patterns it saw with evidence pointers. Default signals worth hunting:

- Response preferences (length, tone, format, "dumb it down" corrections)
- Delegation habits (subagents, models, specialized workflows, parallelism)
- Verification posture (what "done" means; unit tests vs live repro; reviewers)
- Code and prose discipline (style, principles cited, lint/format tools)
- Process conventions (worktrees, commits, PRs, review/merge tooling)
- Meta preferences (fixing skills mid-task, proposing new ones)

Cross-check across slices before elevating a signal. Patterns seen in 2+ slices are high-confidence; lone signals are weak and usually get dropped.

### 2. Ask the user directly

Mining misses intent that hasn't come up yet. Use the host's structured user-interaction capability rather than asking the user to type from scratch. Lower cognitive load, higher hit rate.

Shape: one or two questions with 4-6 options each; allow multiple selections for category questions when the host supports it. Start broad ("Which areas matter most?"), then follow up on selected areas with specific options. After the structured rounds, one free-form chat question catches anything the options missed.

Don't dump 20 questions. Two structured rounds plus one open question is usually enough.

### 3. Cluster findings

Group the combined signals into sections. Common ones (use only what applies):

- **Response style**: length, tone, format.
- **Autonomy**: how much to do without asking; MCP tool use.
- **Understand first**: which skills to reach for when scoping or investigating a change.
- **Subagents**: default, parallelism, model-to-task, specialized workflows.
- **Prose / code discipline**: principles, lint tools, style guides.
- **Review and verify**: repro posture, verification skills, live-testing tools.
- **Process**: git worktrees, commits, PRs, review/merge tooling.
- **Skills**: skill-authoring habits, fix-the-skill-first, proposing new skills.

The **poteto-mode** skill shows the shape. Read it for granularity. Don't copy its content; the user's rules are not the same as poteto-mode's.

### 4. Draft the skill

Author the skill against the Agent Skills specification and validate it with the host's available conformance workflow. Placement:

- Path: preserve an existing mode skill's category. For a new mode, use `<project-skill-directory>/<handle>/<handle>-mode/SKILL.md` when the repo has an established personal category for that handle; otherwise default to `<project-skill-directory>/<handle>-mode/SKILL.md` in the project (or `<user-skill-directory>/<handle>-mode/` if the user prefers a personal skill).
- Handle: the user's first name or chosen identifier.
- Frontmatter `description`: trigger on their name, `<handle>-mode`, and "work in their style", not on generic keywords like "write code" or "review PR".
- Frontmatter formatting: follow the Agent Skills frontmatter rules. Keep `description` as one YAML scalar; quote it or use `description: >-` with indented continuation lines when punctuation or wrapping requires it.
- Use only standard Agent Skills frontmatter. Encode explicit activation in the description (for example, "Use only when the user explicitly requests this mode") and optional namespaced metadata; do not add host-specific invocation-control fields.

### 5. Iterate on prose

Apply the **unslop** skill and the Agent Skills authoring guidelines to every line. Both apply to any agent-read prose, not just skills.

Show the draft to the user and take feedback. Expect multiple iterations. Cut ruthlessly; a mode skill is not a manual.

### 6. Land it

Work in a worktree off main. Commit and open a PR so the user can review it. Don't push to main directly.

## Guardrails

- **Don't overfit to one conversation.** A preference stated once and contradicted another time is noise. Require multiple instances before codifying it.
- **Don't be clever.** Restating other skills' contents, inventing metaphors, or writing "poetic" prose for an agent reader is cost without benefit. Keep it operational.
- **Reference, don't inline.** Other skills the user relies on should appear as path references, not pasted excerpts. Same for any principle docs they maintain elsewhere.
- **Keep sections minimal.** Only add a section if the user has a specific, non-default rule there. "Communicate clearly" is not a section. "Short paragraphs. Tables when comparing options. Bullets only when items are genuinely parallel." is.
- **Name conventions generic.** Use "the user" or "the human" in imperatives, not the author's first name. Others may read or adopt the skill.
- **Don't force symmetry.** If a user has no process rules worth writing down, skip the Process section entirely. Sparse is fine; bloated is not.

## Evaluation

A `-mode` skill is subjective output. A generic skill-authoring benchmark loop isn't useful here. Vibe-check with the user: does it read like them? Did it miss anything? Then ship.

Run a description-optimization loop only if the skill's trigger accuracy turns out to be a problem in practice.

## When not to use

- User wants a task-specific skill (not working conventions): use the Agent Skills authoring workflow directly; no mining is required.
- User wants to capture one narrow workflow (e.g. "how I write commit messages"): that's a regular skill, not a mode skill.

## Reference files

- The **poteto-mode** skill: example of the output shape.
- The **unslop** skill: prose discipline for every line.
- Agent Skills authoring workflow: skill authoring process and writing guidelines.
