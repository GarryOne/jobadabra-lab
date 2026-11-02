"""Daily triage: pull the form-fill failures from the website's queue and file them as issues in THIS (private) repository.

    python3 triage/triage.py [--site https://www.jobadabra.top] [--dry]

Env: LAB_KEY (the site's owner key), GH_TOKEN (the workflow's, issues: write). The queue is filled by the site when a form-fill failure
recurs (several senders or many reports, or the owner's own app), so a single report never becomes an issue. Pull, not push: the website
needs no token for a private repository, and nothing about which sites or fields fail is published.
One issue per failing FIELD (site + question + cause), found again by a marker in its body: the same field reported beside other fields is
the same issue (20 Oct 2026: 8 of 40 issues were duplicates of that kind). It is told "Seen again" only on a newer extension build than any
it was seen on, reopened when a newer build fails again, and closed after 14 days without a sighting.
Telemetry problems are no longer filed (owner, 20 Oct 2026: 0 of 18 such issues led to a fix; Sentry and its fixer handle crashes and
failed runs, /admin/app shows the rest); queued ones are taken and dropped."""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

SITE = 'https://www.jobadabra.top'
STALE_DAYS = 14
BUILD = re.compile(r'<!-- triage-build:([\w.+-]+) -->')


def marker(key):
    return f'<!-- triage:{key} -->'


def build_marker(build):
    return f'<!-- triage-build:{build} -->' if build else ''


def _norm(label):
    return re.sub(r'[^\w]+', ' ', str(label or '').lower()).strip()


def _parts(build):
    numbers = re.match(r'^(\d+(?:\.\d+)*)', str(build or ''))
    return [int(n) for n in numbers.group(1).split('.')] if numbers else None


def newer(build, than):
    """True when `build` is later than `than` ("0.9.460" > "0.9.448"; "0.9.461-dev" counts as 0.9.461; anything beats none).
    An unstamped copy ("0.9", a checkout loaded as is) is never later than a stamped 0.9.x."""
    mine, theirs = _parts(build), _parts(than)
    if mine is None:
        return False
    if theirs is None:
        return True
    if len(mine) < len(theirs):
        return False
    return mine > theirs + [0] * (len(mine) - len(theirs))


def builds_in(texts):
    return [found for text in texts for found in BUILD.findall(text or '')]


def wanted(build, texts):
    """Is a sighting on `build` news for an issue whose body and comments are `texts`? Only a build newer than every one recorded."""
    seen = builds_in(texts)
    return not seen or all(newer(build, old) for old in seen)


def stale(issue, now):
    """No sighting (the filing, or a "Seen again" comment) in the last STALE_DAYS days."""
    times = [issue.get('createdAt', '')] + [c.get('createdAt', '') for c in issue.get('comments') or [] if str(c.get('body', '')).startswith('Seen again')]
    last = max(datetime.fromisoformat(t.replace('Z', '+00:00')) for t in times if t)
    return now - last > timedelta(days=STALE_DAYS)


def issue_for(item):
    """-> [{key, title, labels, build, body}] for a queue item: one per failing field of a report; [] for anything else."""
    kind, payload = item.get('kind'), item.get('payload') or {}
    if kind != 'report':
        return []   # 'problems' (telemetry): retired on 20 Oct 2026
    try:
        report = json.loads(payload.get('report') or '{}')
    except ValueError:
        return []
    site, build = report.get('site'), str(report.get('version') or '')
    if not site:
        return []
    issues = []
    for field in report.get('fields') or []:
        label, reason = str(field.get('label', '')), field.get('reason', '')
        key = f"field:{site}|{_norm(label)}|{_norm(reason)}"[:200]
        line = f"- **{label.strip() or '?'}** ({field.get('type', '?')}{', required' if field.get('required') else ''}): {reason}"
        issues.append({'key': key, 'title': f"Fill failure: {site} · {label.strip()}"[:120], 'labels': ['fill-failure'], 'build': build,
                       'body': f"Reported from the app (extension build {build or '?'}): the owner's app and questions the reader did not read come at once, others once several installs report them.\n\n"
                               + line
                               + "\n\nReplay fixture (red until fixed): `node tools/fill-fixture.mjs <this issue> --repo GarryOne/jobadabra-lab` in the public repo. A dropdown whose options load from the site: record the site (skill record-applying-sites)."
                               + f"\n\n<details><summary>Snapshot</summary>\n\n```json\n{json.dumps([field], indent=1)[:20000]}\n```\n</details>\n\n{marker(key)} {build_marker(build)}"})
    return issues


def gh(*args, check=True):
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=check).stdout


def find(issue, repo):
    """The issue already filed for this field: by its marker, else (issues filed before 20 Oct 2026) by its exact title."""
    fields = 'number,state,title,body,comments'
    found = json.loads(gh('issue', 'list', '--repo', repo, '--state', 'all', '--search', f'"{marker(issue["key"])}" in:body', '--json', fields, '--limit', '1') or '[]')
    if found:
        return found[0]
    same = json.loads(gh('issue', 'list', '--repo', repo, '--state', 'all', '--label', 'fill-failure', '--search', f'"{issue["title"]}" in:title', '--json', fields, '--limit', '5') or '[]')
    return next((i for i in same if i['title'] == issue['title']), None)


def file_issue(issue, repo, dry):
    found = find(issue, repo)
    if found:
        number = str(found['number'])
        if not wanted(issue['build'], [found.get('body', '')] + [c.get('body', '') for c in found.get('comments') or []]):
            return f"#{number}: seen again on build {issue['build'] or '?'}, not newer: nothing said"
        if dry:
            return f"[dry] update #{number}: {issue['title']}"
        if found['state'] == 'CLOSED':
            gh('issue', 'reopen', number, '--repo', repo, check=False)
        gh('issue', 'comment', number, '--repo', repo, '--body', f"Seen again on build {issue['build'] or '?'}.\n\n{issue['body'].split('<details>')[0][:3000]}\n{build_marker(issue['build'])}")
        return f"updated #{number}"
    if dry:
        return f"[dry] new: {issue['title']}"
    for label in issue['labels']:
        gh('label', 'create', label, '--repo', repo, '--force', check=False)
    url = gh('issue', 'create', '--repo', repo, '--title', issue['title'], '--body', issue['body'], *sum([['--label', l] for l in issue['labels']], [])).strip()
    return f'opened {url}'


def close_stale(repo, dry, now=None):
    now = now or datetime.now(timezone.utc)
    issues = json.loads(gh('issue', 'list', '--repo', repo, '--state', 'open', '--label', 'fill-failure', '--json', 'number,createdAt,comments', '--limit', '200') or '[]')
    for issue in issues:
        if not stale(issue, now):
            continue
        if dry:
            print(f"[dry] close #{issue['number']}: not seen for {STALE_DAYS} days")
            continue
        gh('issue', 'close', str(issue['number']), '--repo', repo, '--reason', 'not planned', '--comment',
           f"Not seen for {STALE_DAYS} days on any build: closed. A newer build that fails on it again reopens it.", check=False)
        print(f"closed #{issue['number']}: not seen for {STALE_DAYS} days")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--site', default=SITE)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'GarryOne/jobadabra-lab'))
    parser.add_argument('--dry', action='store_true')
    options = parser.parse_args()
    key = os.environ.get('LAB_KEY', '')
    if not key:
        print('No LAB_KEY: nothing to do.')
        return
    # urllib's own User-Agent is blocked at Cloudflare's edge (403), so send ours
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'User-Agent': 'jobadabra-internal-triage'}
    with urllib.request.urlopen(urllib.request.Request(f'{options.site}/api/triage', headers=headers), timeout=30) as response:
        items = json.load(response).get('items', [])
    print(f'{len(items)} item(s) in the queue')
    taken = []
    for item in items:
        for issue in issue_for(item):
            print(file_issue(issue, options.repo, options.dry))
        taken.append(item['id'])   # telemetry items too: taken and dropped
    if taken and not options.dry:
        request = urllib.request.Request(f'{options.site}/api/triage', data=json.dumps({'ids': taken}).encode(), headers=headers, method='POST')
        urllib.request.urlopen(request, timeout=30).read()
        print(f'{len(taken)} taken')
    close_stale(options.repo, options.dry)


if __name__ == '__main__':
    sys.exit(main())
