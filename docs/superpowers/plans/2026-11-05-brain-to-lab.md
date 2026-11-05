# The product brain's scripts move to jobadabra-lab (5 Nov 2026)

Owner, 5 Nov 2026: chose "Move to lab" for the product brain's scripts. `jobadabra` is the desktop app and the extension only. The brain is back office, and its only caller is this repo's `product-brain.yml`.

## What moves
| File | What it does |
|---|---|
| `tools/product_brain.py` | Notion, Telegram and signals plumbing of the daily brief |
| `tools/site-shots.mjs` | the website's screenshots for the brief |
| `desktop/e2e/brain-codex.mjs` | the brief's one AI call on the Codex plan (imports the engine's `lib/broker-job.mjs`) |

They keep their paths: the workflow lays them over the engine checkout, the same way `tools/public-tree.sh` does.

## PRs
1. `[a8] 1/2` jobadabra-lab: the three files here, and the workflow lays them over the engine.
2. `[a8] 2/2` jobadabra: delete the three files and the lines that name them.

## Progress
- [ ] 1/2 lab holds the files
- [ ] 2/2 jobadabra deletes them
- [ ] One brain run on lab main after 2/2 (the next 05:00 UTC brief) is green
