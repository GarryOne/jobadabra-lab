#!/usr/bin/env bash
# The private prompts (prompts/*.md) -> encrypted GitHub secrets of the public repo, where the workflows that use
# them run (product-brain.yml, weekly-self-review.yml). Secrets are never shown, not even in logs. Run after editing.
set -euo pipefail
repo=GarryOne/job-pilotto
cd "$(dirname "$0")/.."
for pair in brain-brief:BRAIN_PROMPT_BRIEF brain-review:BRAIN_PROMPT_REVIEW brain-explore:BRAIN_PROMPT_EXPLORE self-review:SELF_REVIEW_PROMPT; do
  gh secret set "${pair#*:}" -R "$repo" < "prompts/${pair%%:*}.md"
  echo "✓ ${pair#*:}"
done
