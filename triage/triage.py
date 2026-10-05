"""Daily triage: pull the problems that recur from the website's queue and file them as issues in THIS (private) repository.

    python3 triage/triage.py [--site https://www.jobpilotto.workers.dev] [--dry]

Env: LAB_KEY (the site's owner key), GH_TOKEN (the workflow's, issues: write). The queue is filled by the site when a form-fill failure
recurs (several senders or many reports) and by its daily top-problems run, so a single report never becomes an issue. Pull, not
push: the website needs no token for a private repository, and nothing about which sites or fields fail is published.
One issue per problem, found again by a marker in its body, so a problem that comes back updates its issue instead of opening a new one."""
import argparse
import json
import os
import subprocess
import sys
import urllib.request

SITE = 'https://www.jobpilotto.workers.dev'


def marker(key):
    return f'<!-- triage:{key} -->'


def issue_for(item):
    """-> {key, title, labels, body} for a queue item, or None when it has nothing usable."""
    kind, payload = item.get('kind'), item.get('payload') or {}
    if kind == 'report':
        try:
            report = json.loads(payload.get('report') or '{}')
        except ValueError:
            return None
        fields = report.get('fields') or []
        if not report.get('site') or not fields:
            return None
        labels = [f.get('label', '') for f in fields][:3]
        key = f"report:{report['site']}:{'|'.join(sorted(f.get('label', '') + f.get('reason', '') for f in fields))}"[:200]
        lines = [f"- **{f.get('label', '?')}** ({f.get('type', '?')}{', required' if f.get('required') else ''}): {f.get('reason', '')}" for f in fields]
        return {'key': key, 'title': f"Fill failure: {report['site']} · {', '.join(labels)}"[:120], 'labels': ['fill-failure'],
                'body': f"Reported from the app (extension {report.get('version', '?')}): the owner's app and questions the reader did not read come at once, others once several installs report them.\n\n"
                        + '\n'.join(lines)
                        + "\n\nReplay fixtures (one per field with a snapshot, red until fixed): `node tools/fill-fixture.mjs <this issue> --repo GarryOne/job-pilotto-internal` in the public repo."
                        + f"\n\n<details><summary>Snapshots</summary>\n\n```json\n{json.dumps(fields, indent=1)[:20000]}\n```\n</details>\n\n{marker(key)}"}
    if kind == 'problems':
        try:
            problems = json.loads(payload.get('problems') or '[]')
        except ValueError:
            return None
        return [{'key': f"problem:{p['fingerprint']}", 'title': f"Problem: {p.get('summary', '')}"[:120], 'labels': ['telemetry'],
                 'body': f"Seen by {p.get('users', '?')} installs, {p.get('times', '?')} times (versions {p.get('versions', '?')}).\n\n```json\n{str(p.get('sample', ''))[:4000]}\n```\n\n{marker('problem:' + p['fingerprint'])}"}
                for p in problems if p.get('fingerprint')]
    return None


def gh(*args, check=True):
    return subprocess.run(['gh', *args], capture_output=True, text=True, check=check).stdout


def file_issue(issue, repo, dry):
    found = json.loads(gh('issue', 'list', '--repo', repo, '--state', 'all', '--search', f'"{marker(issue["key"])}" in:body', '--json', 'number,state', '--limit', '1') or '[]')
    if dry:
        return f"[dry] {'update #' + str(found[0]['number']) if found else 'new'}: {issue['title']}"
    if found:
        number = str(found[0]['number'])
        if found[0]['state'] == 'CLOSED':
            gh('issue', 'reopen', number, '--repo', repo, check=False)
        gh('issue', 'comment', number, '--repo', repo, '--body', f"Seen again.\n\n{issue['body'].split('<details>')[0][:3000]}")
        return f"updated #{number}"
    for label in issue['labels']:
        gh('label', 'create', label, '--repo', repo, '--force', check=False)
    url = gh('issue', 'create', '--repo', repo, '--title', issue['title'], '--body', issue['body'], *sum([['--label', l] for l in issue['labels']], [])).strip()
    return f'opened {url}'


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--site', default=SITE)
    parser.add_argument('--repo', default=os.environ.get('GITHUB_REPOSITORY', 'GarryOne/job-pilotto-internal'))
    parser.add_argument('--dry', action='store_true')
    options = parser.parse_args()
    key = os.environ.get('LAB_KEY', '')
    if not key:
        print('No LAB_KEY: nothing to do.')
        return
    # urllib's own User-Agent is blocked at Cloudflare's edge (403), so send ours
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json', 'User-Agent': 'job-pilotto-internal-triage'}
    with urllib.request.urlopen(urllib.request.Request(f'{options.site}/api/triage', headers=headers), timeout=30) as response:
        items = json.load(response).get('items', [])
    print(f'{len(items)} item(s) in the queue')
    taken = []
    for item in items:
        made = issue_for(item)
        for issue in (made if isinstance(made, list) else [made] if made else []):
            print(file_issue(issue, options.repo, options.dry))
        taken.append(item['id'])
    if taken and not options.dry:
        request = urllib.request.Request(f'{options.site}/api/triage', data=json.dumps({'ids': taken}).encode(), headers=headers, method='POST')
        urllib.request.urlopen(request, timeout=30).read()
        print(f'{len(taken)} taken')


if __name__ == '__main__':
    sys.exit(main())
