"""The private discovery (discovery/commoncrawl.py, discovery/priorities.py) and the canary tool, run against the public engine's code
(JOB_PILOTTO_PUBLIC, default ~/job-pilotto). Fake archive answers only: no network."""
import importlib.util
import io
import json
import os
import sqlite3
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

OPS = Path(__file__).resolve().parents[1]
ENGINE = Path(os.getenv('JOB_PILOTTO_PUBLIC') or Path.home() / 'job-pilotto')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


@unittest.skipUnless((ENGINE / 'src' / 'scout.py').exists(), 'the public engine is not checked out next to this repo')
class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ENGINE))
        os.environ['JOB_PILOTTO_FOLLOW_APP'] = '0'
        cls.cc = module(OPS / 'discovery' / 'commoncrawl.py', 'commoncrawl')
        cls.prio = module(OPS / 'discovery' / 'priorities.py', 'priorities')
        from src import scout
        cls.scout = scout

    def database(self):
        db = sqlite3.connect(':memory:')
        db.row_factory = sqlite3.Row
        db.executescript(self.scout.TABLES)
        self.scout.harvest(db, {'excluded': []}, [lambda: []])
        return db

    def archive(self, urls):
        def fetch(url):
            if url.endswith('collinfo.json'):
                return json.dumps([{'id': 'CC-MAIN-2026-39'}])
            if 'showNumPages' in url:
                return json.dumps({'pages': 1})
            return '\n'.join(json.dumps({'url': u}) for u in urls if any(part in u for part in ('ashbyhq', 'lever')) and (('ashbyhq' in url) == ('ashbyhq' in u)))
        return fetch

    def test_boards_in_the_archive_become_candidates_with_their_feed_address_once_per_crawl(self):
        db = self.database()
        urls = ['https://jobs.ashbyhq.com/acme', 'https://jobs.ashbyhq.com/acme/123-sre', 'https://jobs.ashbyhq.com/beta?x=1', 'https://jobs.lever.co/gamma/abc']
        with mock.patch.object(self.cc, 'QUERIES', (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))), redirect_stdout(io.StringIO()):
            first = self.cc.run(db, self.archive(urls), pause=0)
            again = self.cc.run(db, self.archive(urls), pause=0)
        self.assertEqual((first['crawl'], first['boards'], first['added']), ('CC-MAIN-2026-39', 3, 3))
        self.assertEqual(again['added'], 0, 'a crawl is read once')
        rows = {(r['ats'], r['slug'], r['origin'], r['priority']) for r in db.execute('SELECT ats, slug, origin, priority FROM scout_candidates')}
        self.assertIn(('ashby', 'acme', 'Common Crawl CC-MAIN-2026-39', 70), rows)
        self.assertEqual({r[1] for r in rows}, {'acme', 'beta', 'gamma'})

    def test_priorities_follow_each_sources_measured_yield_and_tier1_keeps_its_own(self):
        db = self.database()
        def add(name, origin, status, priority=50):
            db.execute("INSERT INTO scout_candidates (key, name, origin, priority, status, added_at) VALUES (?, ?, ?, ?, ?, 'x')", (name.lower(), name, origin, priority, status))
        for i in range(10):
            add(f'good{i}', 'SwissDevJobs employer', 'found' if i < 6 else 'low')
            add(f'poor{i}', 'Hacker News: (September 2026', 'none')
        add('NextGood', 'SwissDevJobs employer', 'pending')
        add('NextPoor', 'Hacker News: (October 2026', 'pending')
        add('Google', 'Tier 1 seed', 'pending', 95)
        report = self.prio.apply(db)
        priority = {r['name']: r['priority'] for r in db.execute('SELECT name, priority FROM scout_candidates WHERE status = "pending"')}
        self.assertGreater(priority['NextGood'], priority['NextPoor'])
        self.assertEqual(priority['Google'], 95)
        self.assertEqual(list(report['sources'])[0], 'SwissDevJobs employer')

    def test_the_canary_tool_reads_its_private_list_and_fails_when_too_few_sites_work(self):
        tool = module(OPS / 'canary' / 'scout_canary.py', 'scout_canary')
        config = json.loads((OPS / 'config' / 'scout_canary.json').read_text())
        self.assertGreaterEqual(len(config['sites']), 20)
        for answer, code in ((('careers', 'x', [1]), 0), (None, 1)):
            with mock.patch.object(tool.scout, 'find_feed', return_value=answer), redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(), code)


if __name__ == '__main__':
    unittest.main()
