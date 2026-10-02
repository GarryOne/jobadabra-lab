# Job Pilotto · internal (private)

What makes the public product [GarryOne/job-pilotto](https://github.com/GarryOne/job-pilotto) smart and how it steers
itself. Not published (Notion 🧭 Strategy → 💰 IP & Monetization, 🪜 Stages).

| Here | What |
|---|---|
| `prompts/*.md` | the product brain (brief, explore, Sunday review) and weekly self-review prompts. **Edit here, then run `tools/sync-prompts.sh`**: they become encrypted secrets of the public repo, where the workflows run |
| `lab/` + `.github/workflows/form-lab.yml` | the **form lab**: a daily headless browser runs the extension's operators on public application forms (never submits), aimed by the site's plan; reports to the site; gives a candidate recipe a canary. Needs the secrets `LAB_KEY` and `EXTENSION_DEPLOY_KEY` |
| `docs/specs/` | private specs (Brain API, license keys, Stage 2) |
| `.claude/skills/notion-map` | map of the private Notion workspace, linked on the owner's Mac as `~/.claude/skills/notion-map` |

## License keys (Stage 1)
`tools/license.py` mints owner-signed keys (`init` once, then `mint --name "Ana" --kind friend [--until 2027-01-01]`, `list`, `revoke <id>`, `verify <key>`).
The private key is only in the Keychain (`job-pilotto.license.signing_key`); `data/licenses.json` lists who got one (no keys).
Tests: `python3 -m unittest discover -s tests`.
