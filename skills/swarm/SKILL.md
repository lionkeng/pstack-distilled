---
name: "swarm"
description: "Explicit request or pstack routing only. Run parallel workers on independent tasks and synthesize their results."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/swarm"
  pstack-distilled-activation: "explicit"
---
# Swarm

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


## Start

Maintain a plan or checklist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Pick the worker model from the `swarm workers` line in `.pstack/models.md`; without a configured line, use `auto`. Omit `model` for `auto` or `inherit-parent`. Pass a configured model ID only after the host confirms it is available; if it is rejected, omit `model` and say so. For a model race, name each confirmed arm before spawning. Use the host's effort and speed controls only when it exposes them.
4. Give each worker its own writable output when it writes. When workers verify or measure commits, each brief names the exact SHAs. A measurement brief also names the method (sample count, what one sample is, order). The worker records both in its result.

## Phase B: Fan out

Spawn all N workers in one message with `worker role: general-purpose`, `execution environment: remote when supported`, `run concurrently when supported`, and the step 3 model, left unset for `auto` or `inherit-parent`. Use `execution environment: local` only when the worker needs access to something on the user's computer.

When a worker must start from a non-default pushed branch, name that branch in the brief.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence. A worker that can prove a defect reports `ISSUES` and lists every issue it can prove, not only the first.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. Drop a result that does not record the SHAs and method its brief names, and respawn that worker once. After a second miss, record a gap. A gap does not count as a pass. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

## Phase D: Report

Return one consolidated in-chat report with a result table, issue one-liners, gaps or dropouts, and the race rule when used.
