# Job Pilotto · internal (private)

What makes the public product [GarryOne/job-pilotto](https://github.com/GarryOne/job-pilotto) smart and how it steers
itself. Not published (Notion 🧭 Strategy → 💰 IP & Monetization, 🪜 Stages).

| Here | What |
|---|---|
| `prompts/*.md` | the product brain (brief, explore, Sunday review) and weekly self-review prompts. **Edit here, then run `tools/sync-prompts.sh`**: they become encrypted secrets of the public repo, where the workflows run |
| `triage/` + `.github/workflows/triage.yml` | the **daily triage**: pulls recurring problems from the site's queue (several installs, or very often) and files them as issues here, one per problem. Needs `LAB_KEY` |
| `lab/` + `.github/workflows/form-lab.yml` | the **form lab**: a daily headless browser runs the extension's operators on public application forms (never submits), aimed by the site's plan; reports to the site; gives a candidate recipe a canary. Needs the secret `LAB_KEY`; runs the operators from the public repo's `extension/` |
| `proposer/` + `.github/workflows/proposer.yml` | the **recipe proposer**: daily, for failing controls without a recipe it asks a small model (Haiku, capped at 20 controls and $0.50 a run), validates the answer with the extension's own `recipe-schema.js` and files it as a **candidate**; the form lab tries it, the canary rolls it out. Needs `LAB_KEY` and `ANTHROPIC_API_KEY` |
| `teach/teach.mjs` | **Claude as teacher**: a Claude session that operated a control by hand files how as a candidate recipe (same validator, same path as the proposer, source `claude`). Run: `LAB_KEY=… node teach/teach.mjs --extension ../public/extension --fingerprint <fp> --kind toggle-group --params '{…}'` |
| `playbooks/apply/<board>.md` + `.github/workflows/playbooks.yml` | the **private playbook** for Claude's application sessions: per-board notes (Greenhouse, Ashby, Lever, others) moved out of the public `apply-to-job` skill. Published to the site on every change; the public engine's `apply_run --context` prints the board's notes into the session. Needs `LAB_KEY` |
| `aliases/` + `.github/workflows/aliases.yml` | the **alias proposer**: daily, question wordings that 3+ installs report and no alias places get a profile field proposed by a small model, and the button texts of posting pages where no Apply button was recognised get checked as start-applying phrases (`apply_button`); checked by a second pass and the extension's validator. Confirmed non-sensitive ones with 5+ installs start a 5% canary; sensitive ones (birth date, address ...) and the rest wait as candidates. `aliases/approve.mjs` is the owner's decision (`--list`, `--phrase … --status canary [--approve]`). Needs `LAB_KEY` and `ANTHROPIC_API_KEY` |
| `docs/specs/` | private specs (Brain API, license keys, Stage 2) |
| `.claude/skills/notion-map` | map of the private Notion workspace, linked on the owner's Mac as `~/.claude/skills/notion-map` |

## License keys (Stage 1)
`tools/license.py` mints owner-signed keys (`init` once, then `mint --name "Ana" --kind friend [--until 2027-01-01]`, `list`, `revoke <id>`, `verify <key>`).
The private key is only in the Keychain (`job-pilotto.license.signing_key`); `data/licenses.json` lists who got one (no keys).
Tests: `python3 -m unittest discover -s tests`.

## How a fix reaches users (no pull requests)
The machines here never change code, in either repo. The **form lab** measures, the **proposer** (and `teach/`) write **recipes**, which are
data, and the **canary** rolls them out; all of that lives in the site's database. The public extension already holds the generic operators and
asks the site for the recipes matching the controls on the page, so a fix is a row of data that needs no release. Code changes happen only when
a recipe cannot express the fix (a new kind of widget): triage files a private issue here and a person changes the **public** repo by hand.

