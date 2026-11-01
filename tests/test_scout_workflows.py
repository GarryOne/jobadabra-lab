"""The central scout's and the product brain's workflows, which moved here from the public repo (1 Nov 2026, rs 6b/6; owner: "jobadabra should have no web, no worker").
The wiring tests that read their text moved with them, so the public repo has no server workflow to read. The engine side of each assertion
(scout_core's budgets, the relay, the brain's Codex step) stays tested in the public repo; JOB_PILOTTO_PUBLIC points at its checkout."""
import os
import re
import unittest
from pathlib import Path

OPS = Path(__file__).resolve().parents[1]
ENGINE = Path(os.getenv('JOB_PILOTTO_PUBLIC') or Path.home() / 'jobadabra')
WORKFLOWS = OPS / '.github' / 'workflows'
ACTIVE = False   # Why (1 Nov 2026, rs 6b/6): flipped to True by the switch PR (6b-4), in the same commit that deletes the public copies; two schedulers would publish the index twice.


def code(name):
    """-> the workflow's text with its comments cut, so a word in a comment never counts."""
    text = (WORKFLOWS / name).read_text(encoding='utf-8')
    return '\n'.join(re.sub(r'\s#.*$', '', line) for line in text.splitlines() if not line.lstrip().startswith('#'))


def budget_seconds(name):
    """-> an engine budget in seconds, read from src/scout_core.py's text (`NAME = 8 * 60`), so this test never imports the engine."""
    match = re.search(r'(?m)^%s\s*=\s*(\d+)\s*\*\s*(\d+)' % name, (ENGINE / 'src' / 'scout_core.py').read_text(encoding='utf-8'))
    assert match, f'{name} is no longer "N * M" in src/scout_core.py: update budget_seconds'
    return int(match.group(1)) * int(match.group(2))


class CentralScout(unittest.TestCase):
    def setUp(self):
        self.text = (WORKFLOWS / 'central-scout.yml').read_text(encoding='utf-8')
        self.code = code('central-scout.yml')

    def test_the_engine_is_the_other_checkout_and_the_owner_is_a_variable(self):
        """Why (1 Nov 2026): in this repo "this repo" is the lab; the scout runs the public engine, so it is checked out at the root and the lab at ops. The org move changes the owner once, in OWNER_OF_JOBADABRA."""
        self.assertIn('repository: ${{ vars.OWNER_OF_JOBADABRA }}/jobadabra', self.code)
        self.assertRegex(self.code, r'(?s)uses: actions/checkout@v\d+\s+with:\s+path: ops')
        self.assertNotRegex(self.code, r'(?i)GarryOne/', 'no literal owner in a uses: or repository: line')
        self.assertNotIn('create-github-app-token', self.code, 'the lab is public since 1 Nov 2026: no App token to read it')

    def test_it_waits_for_the_switch(self):
        self.assertEqual(bool(re.search(r'(?m)^\s{2}schedule:', self.code)), ACTIVE, 'dormant until 6b-4, then scheduled: both start by hand either way')
        self.assertIn('workflow_dispatch:', self.code)

    def test_the_scout_keeps_its_places_between_runs(self):
        self.assertEqual(self.text.count('data/geo.json'), self.text.count('data/jobs.sqlite') - self.text.count('--db data/jobs.sqlite'),
                         'every cache restore and save keeps the places the AI judged (asked once, ever)')

    def test_its_ai_runs_behind_the_broker_relay_on_the_40_call_cap(self):
        """Owner, 26 Oct 2026 "keep claude for the scout"; 31 Oct 2026 "We should use fully the Codex": no Anthropic key, no Free AI, no address off this machine."""
        self.assertNotRegex(self.code, r'(?i)anthropic', 'the scout holds no Anthropic key and no base URL')
        self.assertNotRegex(self.code, r'(?i)free_ai|JOB_PILOTTO_AI_ENGINE', 'the scout never switches to Free AI or another engine')
        self.assertIn('id-token: write', self.code)
        self.assertIn("CENTRAL_AI_CAP: '40'", self.code)
        self.assertIn('broker-relay-run.mjs --job central-scout --cap "$CENTRAL_AI_CAP" -- python -m src scout', self.code)
        self.assertIn("steps.scout.outputs.skipped == 'true'", self.code)
        self.assertIn('ai-skipped-alert', self.code, 'a refused call tells the owner once')

    def test_it_is_given_the_title_seed_and_the_country_and_the_search_key_under_their_own_names(self):
        self.assertIn('SCOUT_TITLE_KINDS: ops/config/title_kinds.json.gz', self.text)
        self.assertIn('country: {description', self.text)
        self.assertIn('SCOUT_BOARD_COUNTRY: ${{ inputs.country }}', self.text)
        self.assertIn('SCOUT_SERPAPI_KEY: ${{ secrets.CENTRAL_SCOUT_SERPAPI_KEY }}', self.text)
        self.assertNotIn('SERPAPI_API_KEY:', self.text, "that name turns on the role searches' SerpApi lane, outside the month cap")

    def test_the_job_limit_covers_setup_both_budgets_and_the_publish_reserve(self):
        limit = int(re.search(r'timeout-minutes: (\d+)', self.text).group(1))
        setup, reserve = 6, 3   # minutes: checkout, installs, Common Crawl (3 min cap) before the scout; upload and cost report after
        self.assertLessEqual(setup + (budget_seconds('CENTRAL_BUDGET_S') + budget_seconds('VERIFY_BUDGET_S')) / 60 + reserve, limit)


class ProductBrain(unittest.TestCase):
    def setUp(self):
        self.text = (WORKFLOWS / 'product-brain.yml').read_text(encoding='utf-8')
        self.code = code('product-brain.yml')

    def test_the_engine_is_the_first_checkout_with_a_months_commits(self):
        self.assertRegex(self.code, r'(?s)repository: \$\{\{ vars\.OWNER_OF_JOBADABRA \}\}/jobadabra\s+ref: main\s+fetch-depth: 300')
        self.assertNotRegex(self.code, r'(?i)GarryOne/')

    def test_it_waits_for_the_switch(self):
        self.assertEqual(bool(re.search(r'(?m)^\s{2}schedule:', self.code)), ACTIVE)
        self.assertIn('workflow_dispatch:', self.code)

    def test_the_brain_runs_only_on_the_broker_and_a_refusal_alerts_once(self):
        self.assertNotRegex(self.code, r'(?i)claude-code-action|anthropic_api_key|ANTHROPIC|BRAIN_AI|ai_provider', 'no Anthropic path is left in the brain')
        self.assertIn('id-token: write', self.text)
        self.assertRegex(self.text, r'brain-codex\.mjs --step "\$STEP"')
        self.assertRegex(self.text, r'brain-codex\.mjs --step explore')
        self.assertRegex(self.text, r"Send the brief\n\s+if: [^\n]*steps\.brief_ai\.outputs\.skipped != 'true'")
        self.assertRegex(self.text, r"Send the plan\n\s+if: [^\n]*steps\.explore_ai\.outputs\.skipped != 'true'")
        self.assertIn('uses: ./.github/actions/ai-skipped-alert', self.text)


if __name__ == '__main__':
    unittest.main()
