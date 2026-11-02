---
name: "arena"
description: "Explicit request or pstack routing only. Build independent candidates for the same task and combine their strongest parts."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/arena"
  pstack-distilled-activation: "explicit"
---
# Arena

## Portable execution

Use the host's native planning, user-interaction, and delegation capabilities.
When delegation or parallel execution is unavailable, perform the same
independent roles sequentially in the current context and then synthesize.
When model selection is unavailable, use the current model. Treat model-role
names as capability labels, not vendor identifiers. Access conversation
history only when the host explicitly exposes it; otherwise use the current
conversation and durable repository artifacts.


Open a plan or checklist with one entry per phase (Frame, Fan out, Cross-judge, Pick, Graft, Verify) before launching anything.

## Phase A: Frame

Every candidate gets the same prompt, so the prompt is the contract.

1. State the artifact each candidate is producing.
2. Derive the rubric, 3-6 concrete gradeable criteria for what success looks like on *this* task. It is the picker's tool in Phase D. Candidates only see the task.
3. Pick the runners from the `arena runners` line in `.pstack/models.md`; without a configured line, use two `auto` seats. `auto` and `inherit-parent` mean omit `model` and use the parent model. Pass a configured model ID only after the host confirms it is available. If it is unavailable or rejected, omit `model` for that seat and say so. Keep the requested number of candidates, even when they share a model. Pick effort and speed only through controls the host exposes. Add runners for distinct design directions; use the same model for generation-bound work when useful.
4. Give each candidate its own output location (a git worktree where possible, otherwise `<host-temp-directory>/arena-<slug>/candidate-<n>/`), per the **separate-before-serializing-shared-state** principle skill.

## Phase B: Fan out

Spawn all N subagents in one message with `run concurrently when supported`, each with the task, the path to the shared grounding, its own output path, and instructions to produce the artifact and a short rationale naming the alternatives it considered and what it rejected.

If a candidate produces no output, proceed with N-1 and note the dropout.

## Phase C: Cross-judge

After all Phase B candidates complete, choose one independent judge from the `arena cross-judge pool` line in `.pstack/models.md`; without a configured pool, use `auto`. Pass `model` only for a confirmed available ID. Prefer a different model family when the host explicitly provides family information. Do not infer family from an ID or a role label. If family diversity cannot be confirmed, use an independent judge on an available model or the parent model and report that limit. When delegation is unavailable, apply the judge rubric inline. The judge sees the rubric and candidates by path label, scores each criterion, and recommends a base with rationale. Start judging after candidates finish writing.

## Phase D: Pick a base

Read every candidate end to end before picking. Score each against the rubric criterion by criterion, not on holistic feel, and compare with the cross-judge when Phase C ran one. Agreement on the base confirms the pick. Disagreement means one of you is biased or the rubric was ambiguous. Read both rationales before deciding.

Pick the base a future maintainer can extend most easily without breaking invariants. When two feel tied, prefer the cleaner boundary or smaller API, per the Laziness Protocol.

## Phase E: Graft

Walk each losing candidate once more for what is worth porting into the base, usually one or two things per candidate, not most of it. Fold each graft in by hand, per the **redesign-from-first-principles** principle skill, so the result stays coherent under one mental model. Don't paste mechanically.

If the candidates converge on one shape, that is strong agreement. Note it and ship the consensus shape. No graft is needed. If they wildly diverge, Phase A was under-specified. Reframe and re-run rather than averaging the divergence.

## Phase F: Verify

Verify the synthesized artifact like any other output, per the **prove-it-works** principle skill. If verification finds a problem the arena missed, either Phase A was wrong (re-frame and re-run) or a candidate caught it and you missed the graft (go back to Phase E). Don't paper over it.

## Outputs

One synthesized artifact, with a short synthesis note alongside naming the base and why, the cross-judge's verdict or that Phase C skipped the judge, each graft with its source candidate, what was rejected and why, any convergence or dropouts, and the verification result.
