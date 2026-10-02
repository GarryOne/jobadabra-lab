"""The daily triage's issue building (triage/triage.py): one issue per recurring problem, found again by a marker."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'triage'))
from triage import issue_for, marker  # noqa: E402


class TriageTest(unittest.TestCase):
    def test_a_recurring_failure_becomes_one_issue_with_its_fields_and_a_marker(self):
        report = {'site': 'job-boards.greenhouse.io', 'version': '0.8.60', 'fields': [
            {'label': 'Nationality', 'type': 'combobox', 'required': True, 'reason': 'dropdown clicked, but no option matched', 'snapshot': '<div/>'}]}
        issue = issue_for({'kind': 'report', 'payload': {'report': json.dumps(report), 'trusted': 'false'}})
        self.assertEqual(issue['labels'], ['fill-failure'])
        self.assertIn('Nationality', issue['title'])
        self.assertIn(marker(issue['key']), issue['body'])
        again = issue_for({'kind': 'report', 'payload': {'report': json.dumps(report), 'trusted': 'true'}})
        self.assertEqual(issue['key'], again['key'])    # the same failure is the same issue, however it arrives

    def test_daily_problems_become_one_issue_each_keyed_by_fingerprint(self):
        problems = [{'fingerprint': 'abc1', 'summary': 'TypeError: x', 'users': 4, 'times': 9, 'versions': '0.8.60', 'sample': '{}'},
                    {'fingerprint': 'def2', 'summary': 'Run failed', 'users': 3, 'times': 30, 'versions': '0.8.60', 'sample': '{}'}]
        issues = issue_for({'kind': 'problems', 'payload': {'problems': json.dumps(problems)}})
        self.assertEqual([i['key'] for i in issues], ['problem:abc1', 'problem:def2'])
        self.assertEqual(issues[0]['labels'], ['telemetry'])
        self.assertIn('4 installs', issues[0]['body'])

    def test_nothing_usable_is_skipped(self):
        self.assertIsNone(issue_for({'kind': 'report', 'payload': {'report': '{"site": "x", "fields": []}'}}))
        self.assertIsNone(issue_for({'kind': 'report', 'payload': {'report': 'not json'}}))
        self.assertIsNone(issue_for({'kind': 'other', 'payload': {}}))
        self.assertEqual(issue_for({'kind': 'problems', 'payload': {'problems': '[{"summary": "no fingerprint"}]'}}), [])


if __name__ == '__main__':
    unittest.main()
