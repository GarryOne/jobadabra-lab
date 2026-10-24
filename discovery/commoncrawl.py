#!/usr/bin/env python3
"""Every public job board Common Crawl has seen, as candidates for the central scout.

Guessing feed addresses from company names finds a few a day. Common Crawl (a free, public web archive) keeps an index of every address it
crawled: asking it for `jobs.ashbyhq.com/*`, `*.teamtailor.com` and the like lists the boards that exist (one crawl held 1,924 Ashby boards
when the index had 121). Each board's address names the job system and its slug, so the scout probes it with one request.

Runs inside the central scout (central-scout.yml), from a checkout of the public engine: `python ops/discovery/commoncrawl.py --db data/jobs.sqlite`.
A crawl is read once (its id is remembered in scout_meta); a new crawl appears about monthly. Polite: one request at a time, a pause between them,
the index's own paging. Nothing about any user is involved.
"""
import argparse
import http.client
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))   # the public engine's checkout
from src import scout  # noqa: E402
from src.sources import ats  # noqa: E402

INDEX = 'https://index.commoncrawl.org'
# What to ask the index for, per job system (the address patterns ats.detect understands).
QUERIES = (
    ('greenhouse', 'url=boards.greenhouse.io/*'), ('greenhouse', 'url=job-boards.greenhouse.io/*'), ('lever', 'url=jobs.lever.co/*'),
    ('ashby', 'url=jobs.ashbyhq.com/*'), ('workable', 'url=apply.workable.com/*'), ('recruitee', 'url=recruitee.com&matchType=domain'),
    ('personio', 'url=jobs.personio.de&matchType=domain'), ('teamtailor', 'url=teamtailor.com&matchType=domain'),
    ('smartrecruiters', 'url=jobs.smartrecruiters.com/*'), ('join', 'url=join.com/companies/*'), ('workday', 'url=myworkdayjobs.com&matchType=domain'),
    # Every other address ats.detect reads (owner, 19 Oct 2026: "every job system ats.py knows"; tests/test_discovery.py checks the list).
    ('umantis', 'url=umantis.com&matchType=domain'), ('greenhouse', 'url=boards.eu.greenhouse.io/*'), ('greenhouse', 'url=job-boards.eu.greenhouse.io/*'),
    ('lever', 'url=jobs.eu.lever.co/*'), ('personio', 'url=jobs.personio.com&matchType=domain'), ('smartrecruiters', 'url=careers.smartrecruiters.com/*'),
)
FIRST_ELEVEN = QUERIES[:11]   # what a crawl marked read before 19 Oct 2026 covered: the rest of that crawl is read on the next run
PAUSE_S = 1.5
PRIORITY = 70          # a board known to exist: above guessed names, below Tier 1 and Swiss catalogs (the learned priorities adjust it)
MAX_NEW = 3000         # candidates added per run, so one run never floods the queue


RETRIES = 4
BACKOFF_S = 15


def get(url, timeout=120, retries=RETRIES, backoff=BACKOFF_S):
    """The archive's answer; its index is often slow (502/503/504, timeouts), so each request is tried a few times with a growing pause."""
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': ats.USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read().decode('utf-8', 'replace')
        except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as error:   # IncompleteRead: a cut-off answer
            status = getattr(error, 'code', None)
            if attempt == retries - 1 or (status and status not in (429, 500, 502, 503, 504)):
                raise
            time.sleep(backoff * (attempt + 1))


def latest_crawl(fetch=get):
    return json.loads(fetch(f'{INDEX}/collinfo.json'))[0]['id']


def boards(crawl, query, fetch=get, pause=PAUSE_S):
    """{(ats, slug)} for one query over one crawl, all pages."""
    base = f'{INDEX}/{crawl}-index?{query}&output=json&fl=url'
    pages = json.loads(fetch(base + '&showNumPages=true')).get('pages', 1)
    found = set()
    for page in range(pages):
        time.sleep(pause)
        text = fetch(f'{base}&page={page}')   # a page that still fails after the retries fails this listing (tried again next run)
        for line in text.splitlines():
            try:
                url = json.loads(line)['url']
            except (ValueError, KeyError):
                continue
            hit = ats.detect(url)
            if hit and hit[0] in ats.FETCHERS and re.fullmatch(r'[\w.-]{2,120}', hit[1]):
                found.add(hit)
    return found


def queries_read(db, crawl):
    """The listings already read for this crawl: the record of each, or the first eleven when the crawl was marked read before it."""
    row = db.execute("SELECT value FROM scout_meta WHERE key = 'commoncrawl_read'").fetchone()
    try:
        record = json.loads(row[0]) if row else {}
    except ValueError:
        record = {}
    if record.get('crawl') == crawl:
        return set(record.get('queries') or [])
    done = db.execute("SELECT value FROM scout_meta WHERE key = 'commoncrawl'").fetchone()
    return {query for _, query in FIRST_ELEVEN} if done and done[0] == crawl else set()


def run(db, fetch=get, pause=PAUSE_S, crawl=None):
    """Add the boards of the newest crawl not read yet. Returns {'crawl', 'boards', 'added'} (added 0 when this crawl was read before)."""
    db.execute('CREATE TABLE IF NOT EXISTS scout_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    crawl = crawl or latest_crawl(fetch)
    read = queries_read(db, crawl)
    todo = [(system, query) for system, query in QUERIES if query not in read]
    if not todo:
        return {'crawl': crawl, 'boards': 0, 'added': 0}
    found, failed = set(), []
    for system, query in todo:
        try:
            got = boards(crawl, query, fetch, pause)
        except Exception as error:  # noqa: BLE001 — one job system's listing failing must not lose the others
            print(f'Warning: {system}: {type(error).__name__}: {error}')
            failed.append(system)
            continue
        print(f'{system}: {len(got)} boards')
        found |= got
        read.add(query)
    known = {(r[0], r[1]) for r in db.execute('SELECT ats, slug FROM scout_candidates WHERE ats IS NOT NULL')}
    known |= {(r[0], r[1]) for r in db.execute('SELECT ats, slug FROM feed_sources')}
    fresh = sorted(found - known)[:MAX_NEW]
    # The job system is part of the source's name ("Common Crawl workday"), so the learned priorities measure each system's yield
    # separately and probe first the systems whose boards turn out to have roles in people's places.
    candidates = [dict(name=slug, origin=f'Common Crawl {system} {crawl}', priority=PRIORITY, ats=system, slug=slug) for system, slug in fresh]
    added = scout.harvest(db, {'excluded': []}, [lambda: candidates])
    # Each listing counts as read for this crawl once it came through, so a failed one, or a job system added later, is read on the next run;
    # the crawl counts as read when all are.
    db.execute("INSERT OR REPLACE INTO scout_meta (key, value) VALUES ('commoncrawl_read', ?)", (json.dumps({'crawl': crawl, 'queries': sorted(read)}),))
    if all(query in read for _, query in QUERIES):
        db.execute("INSERT OR REPLACE INTO scout_meta (key, value) VALUES ('commoncrawl', ?)", (crawl,))
    db.commit()
    return {'crawl': crawl, 'boards': len(found), 'added': added, 'failed': failed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('data/jobs.sqlite'))
    args = parser.parse_args()
    args.db.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    db.executescript(scout.TABLES)
    print(json.dumps(run(db)))


if __name__ == '__main__':
    main()
