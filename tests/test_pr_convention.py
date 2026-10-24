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

    def test_the_description_check_runs_in_the_public_lab_ci_not_in_a_lab_workflow(self):
        self.assertFalse((ROOT / '.github' / 'workflows' / 'pr-body.yml').exists(), 'a lab workflow cannot start until 1 Nov: a red X on every PR')
        self.assertIn('lab-ci', (ROOT / 'CLAUDE.md').read_text())


if __name__ == '__main__':
    unittest.main()
