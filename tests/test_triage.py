"""The daily triage's issue building (triage/triage.py): one issue per failing field, found again by a marker; telemetry is not filed."""
import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'triage'))
from triage import builds_in, issue_for, marker, newer, stale, wanted  # noqa: E402

REPORT = {'site': 'job-boards.greenhouse.io', 'version': '0.9.448', 'fields': [
    {'label': 'Nationality', 'type': 'combobox', 'required': True, 'reason': 'dropdown clicked, but no option matched', 'snapshot': '<div/>'},
    {'label': 'Country', 'type': 'combobox', 'required': True, 'reason': 'dropdown not clicked: the click failed'}]}


def item(report=REPORT, trusted='false'):
    return {'kind': 'report', 'payload': {'report': json.dumps(report), 'trusted': trusted}}


class TriageTest(unittest.TestCase):
    def test_each_failing_field_is_its_own_issue_with_its_build_and_a_marker(self):
        issues = issue_for(item())
        self.assertEqual([i['title'] for i in issues], ['Fill failure: job-boards.greenhouse.io · Nationality', 'Fill failure: job-boards.greenhouse.io · Country'])
        self.assertEqual(issues[0]['labels'], ['fill-failure'])
        self.assertEqual(issues[0]['build'], '0.9.448')
        self.assertIn(marker(issues[0]['key']), issues[0]['body'])
        self.assertIn('0.9.448', issues[0]['body'])
        self.assertNotIn('Country', issues[0]['body'])   # one field per issue

    def test_the_same_field_in_another_report_is_the_same_issue(self):
        # 20 Oct 2026: one field reported beside different fields (or once alone) opened a new issue each time (8 duplicates of 40)
        alone = dict(REPORT, fields=[REPORT['fields'][0]], version='0.9.460')
        self.assertEqual(issue_for(item())[0]['key'], issue_for(item(alone, trusted='true'))[0]['key'])
        spaced = dict(REPORT, fields=[dict(REPORT['fields'][0], label='  Nationality :')])
        self.assertEqual(issue_for(item())[0]['key'], issue_for(item(spaced))[0]['key'])

    def test_telemetry_problems_are_not_filed(self):
        # Retired by the owner on 20 Oct 2026: 0 of 18 such issues led to a fix; Sentry and its fixer handle crashes and failed runs
        problems = [{'fingerprint': 'abc1', 'summary': 'TypeError: x', 'users': 4, 'times': 9, 'versions': '0.8.60', 'sample': '{}'}]
        self.assertEqual(issue_for({'kind': 'problems', 'payload': {'problems': json.dumps(problems)}}), [])

    def test_nothing_usable_is_skipped(self):
        self.assertEqual(issue_for(item({'site': 'x', 'fields': []})), [])
        self.assertEqual(issue_for({'kind': 'report', 'payload': {'report': 'not json'}}), [])
        self.assertEqual(issue_for({'kind': 'other', 'payload': {}}), [])

    def test_builds_compare_by_number_and_a_dev_copy_counts_as_its_build(self):
        self.assertTrue(newer('0.9.460', '0.9.448'))
        self.assertTrue(newer('0.10.1', '0.9.999'))
        self.assertFalse(newer('0.9.448', '0.9.448'))
        self.assertFalse(newer('0.9', '0.9.448'))
        self.assertTrue(newer('0.9.461-dev', '0.9.460'))
        self.assertTrue(newer('0.9.1', ''))     # an issue filed before builds were recorded
        self.assertFalse(newer('', '0.9.1'))

    def test_seen_again_only_on_a_newer_build(self):
        # 20 Oct 2026: 64 of 96 "Seen again" comments repeated the same counts
        texts = ['Reported from the app (extension build 0.9.448). <!-- triage-build:0.9.448 -->', 'Seen again on build 0.9.452. <!-- triage-build:0.9.452 -->']
        self.assertEqual(builds_in(texts), ['0.9.448', '0.9.452'])
        self.assertFalse(wanted('0.9.452', texts))
        self.assertFalse(wanted('0.9.450', texts))
        self.assertTrue(wanted('0.9.453', texts))
        self.assertTrue(wanted('0.9.1', ['an issue from before builds were recorded']))

    def test_an_issue_not_seen_for_14_days_is_stale(self):
        issue = {'createdAt': '2026-10-10T08:00:00Z', 'comments': [{'createdAt': '2026-10-19T08:00:00Z', 'body': 'Seen again on build 0.9.452.'},
                                                                    {'createdAt': '2026-10-30T08:00:00Z', 'body': 'A person: still looking at this'}]}
        self.assertFalse(stale(issue, datetime(2026, 11, 2, 7, tzinfo=timezone.utc)))   # last sighting 19 Oct 08:00 (a person's note is no sighting)
        self.assertTrue(stale(issue, datetime(2026, 11, 2, 9, tzinfo=timezone.utc)))
        self.assertFalse(stale({'createdAt': '2026-10-25T08:00:00Z', 'comments': []}, datetime(2026, 11, 2, tzinfo=timezone.utc)))


if __name__ == '__main__':
    unittest.main()
