# jobadabra-lab: notes for Claude

**Private** repo (never make it public): what makes the public product `GarryOne/jobadabra` smart (prompts, proposers, canary, discovery, pool). Read [README.md](README.md) first.
It runs laid over a checkout of the public repo (`tools/public-tree.sh`). **Private reads public, public never reads private.**

## Rules
- **Land with the public ship tool, from your worktree here:** `~/jobadabra/tools/ship.sh --background --body=<file>` (rebase, push, open the PR, watch it: `ship: RED/GREEN/MERGED/CONFLICT` in its log; Monitor it).
  **Never a bare `gh pr create`** (owner, 24 Oct 2026: lab #57 had a free-form description). Without `--body` the ship tool refuses to open the PR.
- **The PR description follows `~/jobadabra/tools/pr-body-template.md`:** verdict line, **Why**, **Unblocks**, the impact table, 2-4 bullets, a Before/After table, "No screenshots: <why>"; the ship tool adds the facts table and folds the commit message.
  Commit subject ≤ 72 characters; with 2+ commits pass `--title="<what the whole PR does>"`. The owner merges by hand.
- The description is checked by `.github/workflows/pr-checks.yml` (jobadabra's reusable `pr-body-check.yml`; the org template, written by `tools/org-repo.sh files`); its "All checks passed" status is what the org ruleset requires. The public repo's `lab-ci` (`tools/lab_ci.py`, dispatched by `ship.sh`) still posts the older status `pr-description` on every lab PR; it covered this while the lab's Actions were blocked (until 1 Nov 2026) and is now a second, redundant check.
- **Secrets** go in the macOS Keychain and the repo's Actions secrets, never in files, prompts or PR text.
- Worktree: `git worktree add .claude/worktrees/<topic> -b <topic> origin/main`. Files: one concern each, ≤ 500 lines.
