---
name: "principle-migrate-callers-then-delete-legacy-apis"
description: "Explicit request or pstack routing only. Plan caller migration and legacy removal when replacing an internal API."
license: MIT
metadata:
  pstack-distilled-origin: "cursor/plugins/pstack/skills/principle-migrate-callers-then-delete-legacy-apis"
  pstack-distilled-activation: "explicit"
---
# Migrate Callers Then Delete Legacy APIs

- Update tests to assert the new contract, and delete tests that only protect pre-refactor implementation details

**When this applies:**
- No external users depend on backward compatibility
- The project can absorb coordinated breaking changes
- The new API is part of a simplification or refactor initiative
