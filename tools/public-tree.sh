#!/usr/bin/env bash
# Builds the tree the lab's pool, replays and evals run in: the public jobadabra repo at a ref, with this repo's files laid over it at the same paths
# (the site's tools/overlay.sh pattern, #1599). Private reads public, never the reverse. Guarded by tests/test_public_tree.py.
# Usage: tools/public-tree.sh <out-dir> [public-ref]   (ref = a branch, tag or commit sha; a PR's head sha works)
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
out="${1:?usage: tools/public-tree.sh <out-dir> [public-ref]}"
ref="${2:-main}"
url="${PUBLIC_REPO_URL:-https://github.com/GarryOne/jobadabra.git}"
rm -rf "$out"
mkdir -p "$out"
git -C "$out" init --quiet
git -C "$out" remote add origin "$url"
git -C "$out" fetch --quiet --depth 1 origin "$ref"
git -C "$out" checkout --quiet FETCH_HEAD
# This repo's own files that are not part of the product tree stay out of it (its README, rules, tests of its own tools, git).
rsync -a --exclude '.git' --exclude '.tree/' --exclude 'node_modules/' --exclude '.gitignore' --exclude 'README.md' --exclude 'CLAUDE.md' --exclude 'AGENTS.md' \
  --exclude '/tests/' --exclude '/.github/' "$here"/ "$out"/
# tests that list files with `git ls-files` must see this repo's files too
(cd "$out" && git ls-files -o --exclude-standard -z | xargs -0 -n 500 git add -N --)
echo "public-tree: $(git -C "$out" rev-parse --short HEAD) of jobadabra@$ref + $(git -C "$here" rev-parse --short HEAD 2>/dev/null || echo local) of the lab -> $out"
