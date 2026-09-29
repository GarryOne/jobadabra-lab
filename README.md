# Job Pilotto · ops (private)

The private brain around the public product [GarryOne/job-pilotto](https://github.com/GarryOne/job-pilotto):
what makes it smart and how it steers itself. Not published (see 🧭 Strategy → IP & Monetization in Notion).

| Here | What |
|---|---|
| `.github/workflows/product-brain.yml`, `tools/product_brain.py`, `tools/site-shots.mjs` | daily product brief + Sunday strategy review (Telegram: Job Pilotto Brain) |
| `.github/workflows/weekly-self-review.yml` | weekly rule/skill proposals, as a PR on the public repo |
| `.claude/skills/notion-map` | the map of the private Notion workspace (linked into local sessions) |

**Secrets:** `ANTHROPIC_API_KEY`, `PRODUCT_TOKEN` (fine-grained PAT: job-pilotto + job-pilotto-ops), `NOTION_BRAIN_TOKEN`,
`BRAIN_BOT_TOKEN`, `BRAIN_CHAT_ID`, `JOB_PILOTTO_TELEMETRY_KEY`; variable `BRAIN_DATABASE_ID`.
Tests: `python3 -m unittest discover -s tests`.
