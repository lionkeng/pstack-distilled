---
name: "principle-outcome-oriented-execution"
description: "Explicit request or pstack routing only. Keep a planned rewrite or migration focused on its target architecture."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/principle-outcome-oriented-execution"
  pstack-distilled-activation: "explicit"
---
# Outcome-Oriented Execution

Optimize for the intended, verifiable end state rather than preserving smooth intermediate states.

**Why:** Keeping every intermediate step fully stable often creates temporary compatibility code that becomes long-lived debt. Converge on the target architecture and prove correctness at explicit verification boundaries.

**Core rule:**
- Prioritize end-state integrity over transitional stability
- Intermediate breakage is acceptable when it is planned, scoped, and reversible
- Always run final verification before declaring done

**Guardrails:**
- Use this for planned rewrites and migrations with explicit phase boundaries
- Declare where temporary breakage is acceptable
- Keep high-signal checks for actively touched areas while migrating
- Require full static and runtime verification at plan completion
