#!/usr/bin/env bash
# The private prompts (prompts/*.md) -> encrypted GitHub secrets of THIS repo (lab), where the workflows that use
# them run (product-brain.yml). Secrets are never shown, not even in logs. Run after editing.
# Why (2 Nov 2026, owner: "jobadabra should have no web, no worker"; spec 2026-11-01-desktop-extension-only.md 6b): the brain
# runs in lab now, so its prompts are lab secrets; the repo is read from the checkout, never a hard-coded owner. PROMPTS_REPO overrides.
set -euo pipefail
cd "$(dirname "$0")/.."
repo=${PROMPTS_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}
# Why (2 Nov 2026, Gitar on lab#70): the public-tree overlay (tools/public-tree.sh) copies this script next to the public repo's origin, and
# gh prefers an `upstream` remote; either would write the private prompts into the public repo's secrets. Refuse unless the repo is lab.
case "$repo" in
  */jobadabra-lab) ;;
  *) [[ -n "${PROMPTS_REPO:-}" ]] || { echo "refusing: $repo is not the lab repo (set PROMPTS_REPO to override)" >&2; exit 1; } ;;
esac
for pair in brain-brief:BRAIN_PROMPT_BRIEF brain-review:BRAIN_PROMPT_REVIEW brain-explore:BRAIN_PROMPT_EXPLORE self-review:SELF_REVIEW_PROMPT; do
  gh secret set "${pair#*:}" -R "$repo" < "prompts/${pair%%:*}.md"
  echo "✓ ${pair#*:}"
done
