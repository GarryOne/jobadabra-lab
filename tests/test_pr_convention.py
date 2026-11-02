"""Lab PRs follow the public repo's description convention (owner, 24 Oct 2026: lab #57 was a free-form body from a bare `gh pr create`).
The lab's Actions can be blocked, so CLAUDE.md names the public ship tool as the gate and the public lab-ci checks the description."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PrConventionTest(unittest.TestCase):
    def test_claude_md_says_to_land_with_the_public_ship_tool(self):
        text = (ROOT / 'CLAUDE.md').read_text()
        self.assertIn('~/jobadabra/tools/ship.sh', text)
        self.assertIn('Never a bare `gh pr create`', text)
        self.assertIn('pr-body-template.md', text)

    def test_the_description_check_is_the_org_pr_checks_workflow(self):
        """Gitar on #73: the lab runs the org's pr-checks.yml (a call of jobadabra's reusable pr-body-check.yml) and CLAUDE.md names it."""
        flow = (ROOT / '.github' / 'workflows' / 'pr-checks.yml').read_text()
        self.assertIn('uses: jobadabra/jobadabra/.github/workflows/pr-body-check.yml@main', flow)
        self.assertIn('name: All checks passed', flow)
        text = (ROOT / 'CLAUDE.md').read_text()
        self.assertIn('pr-checks.yml', text)
        self.assertNotIn('The lab has no workflow for it', text)


if __name__ == '__main__':
    unittest.main()
