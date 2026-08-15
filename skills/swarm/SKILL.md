---
name: "swarm"
description: "Use only when explicitly requested or when another pstack skill directs you to it. Fan out N parallel workers, drain them, and return one report. Use for swarm, 'swarm this', or parallel coverage, races, gauntlets, and exploration."
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


Fan out N parallel delegated workers when supported. They may cover separate slices, race the same brief, or mix both. The parent waits, aggregates, and returns one report.

## Start

Maintain a plan or checklist with one entry per phase before launching anything.

1. Frame
2. Fan out
3. Aggregate
4. Report

## Phase A: Frame

1. State the done predicate and the artifact or report the swarm must return.
2. Choose the shape. Partition into slices, race N workers on identical briefs, or mix both. For a race or mixed shape, declare `first pass`, `rank all`, or `best-of` before spawning.
3. Set N from the user or derive it from the shape. N is total workers, not the host's concurrency limit.
4. Pick the worker model from `swarm workers` in `.pstack/models.md` when present. Otherwise use `fast-code-model`. For a model race, name each arm's model up front.
5. Give each worker its own writable output when it writes. Use a worktree, branch, or `<host-temp-directory>/swarm-<slug>/worker-<n>/`.

## Phase B: Fan out

Spawn all N workers in one message with `worker role: general-purpose`, `execution environment: remote when supported`, `run concurrently when supported`, and the configured model. Use `execution environment: local` only when the worker needs access to something on the user's computer.

When a worker must start from a non-default pushed branch, pass `remote base branch`.

Every brief stands alone. Include the goal, scope, exact slice or race arm, how to verify, and what to report. Reports use `PASS`, `ISSUES`, or `BLOCKED` with evidence.

If a worker drops out, proceed with N-1 and note it.

## Phase C: Aggregate

Read the terminal results. For coverage, every required slice needs a result. For a race, apply the selection rule declared up front. Use first pass, rank all, or best-of. Do not paste raw worker dumps.

Keep a compact result table, one-line evidenced issues, and explicit gaps or dropouts.

## Phase D: Report

Return one consolidated in-chat report with the table, issue one-liners, gaps or dropouts, and the race rule when used.
