### Opening a PR

Invoked at the end of every other playbook.

**Worktree.** Work from a git worktree off main; subagents inherit it. Multiple delegation calls on the same branch each get their own worktree, or `git fetch && git reset --hard origin/<branch>` between them. Dirty branch with unrelated work: patch out, fresh worktree, apply. Snarled worktree: reset from main, redo minimally.

**Commits.** Commit liberally; rebase into small, ordered commits before opening PRs. Each commit is a future PR: landable, ordered to tell the story. Amend when the fix belongs in a just-made commit; new commit when separable.

**PRs.** Apply an available prose-cleanup workflow to agent-authored text before commit; run the **no-comments** skill before review; apply the **unslop** skill to the PR description and commit bodies. Small PRs, 5 narrow over 1 fat; stack follow-ups, branch off main only for genuinely independent work. For stacked PRs, use whatever stacking tool your team uses; the principle is small, ordered slices with the stack visible to reviewers. On GitHub, use `gh pr view <number>` before referencing PR status when `gh` is available; otherwise use the host's source-control connector or state that status could not be verified. Rebase on `main` before substantial stack work. No `## Summary` / `## Test plan` boilerplate on small PRs; commit bodies don't restate the subject. After opening, follow `playbooks/babysit.md` to monitor checks and review feedback; push back when feedback drifts from intent.

A subagent that opens a PR runs `interrogate`, prose-cleanup workflow, and `no-comments`, returns the URL, and does NOT babysit. Return to the parent.
