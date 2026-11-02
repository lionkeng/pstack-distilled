---
name: "principle-laziness-protocol"
description: "Explicit request or pstack routing only. Reduce unnecessary abstractions and edits in a proposed refactor."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/principle-laziness-protocol"
  pstack-distilled-activation: "explicit"
---
# Laziness Protocol

- **Consolidate decisions.** Do not repeat the same choice in several places. Put it behind one source of truth and pass the result as a simple flag.
- **Minimize the diff.** Make the smallest change that solves the problem. Fewer lines beat "elegant" boilerplate.
