"""The private discovery (discovery/commoncrawl.py, discovery/priorities.py) and the canary tool, run against the public engine's code
(JOBADABRA_PUBLIC, default ~/jobadabra). Fake archive answers only: no network."""
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
ENGINE = Path(os.getenv('JOBADABRA_PUBLIC') or Path.home() / 'jobadabra')


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class _Ctx:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self.body

    def __exit__(self, *exc):
        return False


@unittest.skipUnless((ENGINE / 'src' / 'scout.py').exists(), 'the public engine is not checked out next to this repo')
class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ENGINE))
        os.environ['JOBADABRA_FOLLOW_APP'] = '0'
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
        self.assertIn(('ashby', 'acme', 'Common Crawl ashby CC-MAIN-2026-39', 70), rows)
        self.assertEqual(self.prio.kind('Common Crawl ashby CC-MAIN-2026-39'), 'Common Crawl ashby')
        self.assertEqual({r[1] for r in rows}, {'acme', 'beta', 'gamma'})

    def test_a_failing_listing_does_not_stop_the_others_and_the_crawl_is_read_again_next_time(self):
        db = self.database()
        good = self.archive(['https://jobs.lever.co/gamma/abc'])
        def fetch(url):
            if 'ashbyhq' in url and 'collinfo' not in url:
                raise OSError('504')
            return good(url)
        with mock.patch.object(self.cc, 'QUERIES', (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))), redirect_stdout(io.StringIO()):
            first = self.cc.run(db, fetch, pause=0)
            second = self.cc.run(db, good, pause=0)
        self.assertEqual((first['added'], first['failed']), (1, ['ashby']))
        self.assertEqual(second['failed'], [], 'the crawl was not marked as read, so the next run tries again')

    def test_every_job_system_the_engine_reads_from_an_address_is_asked_for(self):
        """Owner, 19 Oct 2026: every job system ats.py knows, not the eleven startup ones; a new pattern there fails here until it has a query."""
        from src.sources import ats
        self.assertEqual({system for system, _ in ats.URL_PATTERNS} - {system for system, _ in self.cc.QUERIES}, set())
        hosts = {'umantis': 'https://recruitingapp-5181.umantis.com/Jobs/All', 'greenhouse': 'https://job-boards.eu.greenhouse.io/acme',
                 'lever': 'https://jobs.eu.lever.co/acme', 'personio': 'https://acme.jobs.personio.com/', 'smartrecruiters': 'https://careers.smartrecruiters.com/Acme',
                 'oracle': 'https://acme.fa.em2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/jobs'}
        for system, url in hosts.items():
            self.assertEqual(ats.detect(url)[0], system, url)

    def test_a_crawl_read_before_new_systems_were_added_reads_only_those_next(self):
        db = self.database()
        db.execute('CREATE TABLE IF NOT EXISTS scout_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute("INSERT INTO scout_meta (key, value) VALUES ('commoncrawl', 'CC-MAIN-2026-39')")
        asked = []
        archive = self.archive([])
        def fetch(url):
            asked.append(url)
            return archive(url)
        with redirect_stdout(io.StringIO()):
            first = self.cc.run(db, fetch, pause=0)
            again = self.cc.run(db, fetch, pause=0)
        listed = {url.split('-index?')[1].split('&output')[0] for url in asked if '-index?' in url}
        self.assertEqual(listed, {query for _, query in self.cc.QUERIES[11:]}, 'only the listings added since')
        self.assertEqual((first['crawl'], again['added'], again['boards']), ('CC-MAIN-2026-39', 0, 0))

    def test_a_run_cut_off_by_the_steps_time_cap_keeps_the_listings_it_finished(self):
        db = self.database()
        urls = ['https://jobs.ashbyhq.com/acme', 'https://jobs.lever.co/gamma/abc']
        inner = self.archive(urls)

        def cut_off(url):   # the second listing never answers: the workflow's timeout kills the process (a BaseException here)
            if 'jobs.lever.co' in url:
                raise SystemExit('timeout')
            return inner(url)
        queries = (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))
        with mock.patch.object(self.cc, 'QUERIES', queries), redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.cc.run(db, cut_off, pause=0)
            again = self.cc.run(db, inner, pause=0)
        self.assertEqual(again['added'], 1, 'the next run reads only the listing that was cut off')
        self.assertEqual({r['slug'] for r in db.execute('SELECT slug FROM scout_candidates')}, {'acme', 'gamma'})

    def test_a_listing_that_failed_last_time_is_tried_last(self):
        db = self.database()
        inner = self.archive(['https://jobs.ashbyhq.com/acme', 'https://jobs.lever.co/gamma/abc'])
        order = []

        def fetch(url):
            if '-index?' in url and 'showNumPages' in url:
                order.append('lever' if 'jobs.lever.co' in url else 'ashby')
            if 'jobs.ashbyhq.com' in url and '-index?' in url:
                raise OSError('504')
            return inner(url)
        queries = (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))
        with mock.patch.object(self.cc, 'QUERIES', queries), mock.patch.object(self.cc.time, 'sleep'), redirect_stdout(io.StringIO()):
            first = self.cc.run(db, fetch, pause=0)
            order.clear()
            self.cc.run(db, fetch, pause=0)
        self.assertEqual(first['failed'], ['ashby'])
        self.assertEqual(order, ['ashby'], 'only the failed one is left to read, and it is asked again')

    def test_failed_listings_go_behind_the_ones_never_tried(self):
        db = self.database()
        crawl = 'CC-MAIN-2026-39'
        db.execute('CREATE TABLE IF NOT EXISTS scout_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        queries = (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))
        db.execute("INSERT INTO scout_meta (key, value) VALUES ('commoncrawl_read', ?)", (json.dumps({'crawl': crawl, 'queries': [], 'failed': ['url=jobs.ashbyhq.com/*']}),))
        asked = []

        def fetch(url):
            if '-index?' in url and 'showNumPages' in url:
                asked.append('lever' if 'jobs.lever.co' in url else 'ashby')
            return json.dumps({'pages': 0}) if 'showNumPages' in url else ''
        with mock.patch.object(self.cc, 'QUERIES', queries), redirect_stdout(io.StringIO()):
            self.cc.run(db, fetch, pause=0, crawl=crawl)
        self.assertEqual(asked, ['lever', 'ashby'])

    def test_a_listing_out_of_time_keeps_its_boards_and_the_next_listing_runs(self):
        db = self.database()
        urls = ['https://jobs.ashbyhq.com/acme', 'https://jobs.lever.co/gamma/abc']
        inner = self.archive(urls)
        ticks = iter(range(0, 10000, 200))   # every clock reading is 200 s later: past the listing's budget after its first page
        queries = (('ashby', 'url=jobs.ashbyhq.com/*'), ('lever', 'url=jobs.lever.co/*'))

        def fetch(url):
            return json.dumps({'pages': 3}) if 'showNumPages' in url else inner(url)
        with mock.patch.object(self.cc, 'QUERIES', queries), mock.patch.object(self.cc.time, 'monotonic', lambda: next(ticks)), \
                mock.patch.object(self.cc.time, 'sleep'), redirect_stdout(io.StringIO()):
            result = self.cc.run(db, fetch, pause=0)
        self.assertEqual({r['slug'] for r in db.execute('SELECT slug FROM scout_candidates')}, {'acme', 'gamma'}, 'both listings ran, the partial one kept its boards')
        record = json.loads(db.execute("SELECT value FROM scout_meta WHERE key = 'commoncrawl_read'").fetchone()[0])
        self.assertEqual(record['queries'], [], 'out-of-time listings are not marked read')
        self.assertEqual(sorted(record['failed']), sorted(query for _, query in queries))
        self.assertEqual(result['failed'], [])

    def test_the_archive_is_asked_again_after_a_gateway_error(self):
        import urllib.error
        calls = []
        def opener(request, timeout):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(request.full_url, 504, 'Gateway Time-out', {}, None)
            return io.BytesIO(b'ok')
        with mock.patch('urllib.request.urlopen', side_effect=lambda r, timeout: _Ctx(opener(r, timeout))):
            self.assertEqual(self.cc.get('https://index.commoncrawl.org/x', backoff=0), 'ok')
        self.assertEqual(len(calls), 3)

    def test_a_cut_off_answer_is_retried_too(self):
        import http.client
        calls = []
        def opener(request, timeout):
            calls.append(1)
            if len(calls) < 2:
                raise http.client.IncompleteRead(b'x')
            return _Ctx(io.BytesIO(b'ok'))
        with mock.patch('urllib.request.urlopen', side_effect=opener):
            self.assertEqual(self.cc.get('https://index.commoncrawl.org/x', backoff=0), 'ok')

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
