---
name: "principle-guard-the-context-window"
description: "Explicit request or pstack routing only. Reduce context pressure during large outputs, repeated reads, or long investigations."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/principle-guard-the-context-window"
  pstack-distilled-activation: "explicit"
---
# Guard the Context Window

**Why:** Context overflow degrades reasoning quality, creates compression artifacts, and halts progress.

**Pattern:**
- **Size phases and cap scope.** Limit files per phase, set turn budgets, account for mechanism costs.
