#!/usr/bin/env python3
"""Learned priorities: the scout's queue ranked by how well each kind of source has done, not by numbers written once.

For every kind of source (the candidate's origin without its month or crawl tag: "Hacker News", "Common Crawl", "SwissDevJobs employer",
"AI idea"...) the share of probed candidates that gave a useful feed is measured; pending candidates get a priority from that share,
smoothed so a source with few probes stays near the middle. Tier 1 and the owner's manual entries (90 and above) keep theirs.
Runs in the central scout before each probe batch: `python ops/discovery/priorities.py --db data/jobs.sqlite`.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path

FLOOR, CEILING = 20, 89
PRIOR_FOUND, PRIOR_PROBED = 1, 6     # smoothing: a new source starts at about one in six


def kind(origin):
    """Same grouping as the public engine's scout_ideas.origin_kind: 'Common Crawl workday CC-MAIN-2026-39' -> 'Common Crawl workday'."""
    return re.split(r'[:(]|\s\d{4}-|\sCC-MAIN', origin or '')[0].strip()


def shares(db):
    table = {}
    for row in db.execute("SELECT origin, status, COUNT(*) n FROM scout_candidates GROUP BY origin, status"):
        entry = table.setdefault(kind(row['origin']), {'probed': 0, 'found': 0})
        if row['status'] in ('found', 'low', 'none', 'watch'):
            entry['probed'] += row['n']
        if row['status'] == 'found':
            entry['found'] += row['n']
    return {name: (e['found'] + PRIOR_FOUND) / (e['probed'] + PRIOR_PROBED) for name, e in table.items()}, table


def apply(db):
    rates, table = shares(db)
    best = max(rates.values()) if rates else 1
    changed = 0
    for row in db.execute("SELECT key, origin, priority FROM scout_candidates WHERE status = 'pending' AND priority < 90").fetchall():
        rate = rates.get(kind(row['origin']), PRIOR_FOUND / PRIOR_PROBED)
        priority = round(FLOOR + (CEILING - FLOOR) * rate / best) if best else row['priority']
        if priority != row['priority']:
            db.execute('UPDATE scout_candidates SET priority = ? WHERE key = ?', (priority, row['key']))
            changed += 1
    db.commit()
    return {'sources': {name: {**table[name], 'rate': round(rates[name], 3)} for name in sorted(rates, key=lambda n: -rates[n])}, 'changed': changed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=Path('data/jobs.sqlite'))
    args = parser.parse_args()
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    print(json.dumps(apply(db), indent=1))


if __name__ == '__main__':
    main()
