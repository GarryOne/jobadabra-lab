"""Lab PRs follow the public repo's description convention (owner, 24 Oct 2026: lab #57 was a free-form body from a bare `gh pr create`).
The lab's Actions can be blocked, so CLAUDE.md names the public ship tool as the gate and the workflow runs the public checker once they run."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PrConventionTest(unittest.TestCase):
    def test_claude_md_says_to_land_with_the_public_ship_tool(self):
        text = (ROOT / 'CLAUDE.md').read_text()
        self.assertIn('~/jobadabra/tools/ship.sh', text)
        self.assertIn('Never a bare `gh pr create`', text)
        self.assertIn('pr-body-template.md', text)

    def test_a_workflow_runs_the_public_description_check_on_every_pr(self):
        text = (ROOT / '.github' / 'workflows' / 'pr-body.yml').read_text()
        self.assertIn('pull_request:', text)
        self.assertIn('edited', text)
        self.assertIn('repository: GarryOne/jobadabra', text)
        self.assertIn('tools/pr-body-check.py', text)
        self.assertIn('github.event.pull_request.body', text)


if __name__ == '__main__':
    unittest.main()
