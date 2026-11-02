"""The lab says Jobadabra everywhere: the old name (Job Pilotto, job-pilotto, JOB_PILOTTO, jobpilotto) survives only on a line that names an external identity
(owner, 2 Nov 2026: "Everything that is job pilotto is renamed/dropped/replaced", "we should not support the 2 versions")."""
import pathlib
import re
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
OLD = re.compile(r'job[-_ ]?pilotto', re.I)
BINARY = re.compile(r'\.(png|jpe?g|gif|ico|pdf|zip|woff2?|sqlite)$', re.I)
KEPT = [
    re.compile(r'Job Pilotto Brain'),   # the Notion connection and the Telegram bot's display name, owned by the owner
    re.compile(r'jobpilotto\.(top|workers\.dev)'),   # the old domain and the workers.dev subdomain: infrastructure we still own
    re.compile(r'secrets\.JOB_PILOTTO_'),   # a GitHub secret not yet copied to its new name
]


class NoOldName(unittest.TestCase):
    def test_every_use_is_a_kept_external_name(self):
        files = [f for f in subprocess.check_output(['git', 'ls-files'], cwd=ROOT, text=True).splitlines()
                 if f and not BINARY.search(f) and f != 'tests/test_no_old_name.py']
        bad = []
        for name in files:
            try:
                text = (ROOT / name).read_text(encoding='utf-8')
            except (UnicodeDecodeError, FileNotFoundError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if OLD.search(line) and not any(rule.search(line) for rule in KEPT):
                    bad.append(f'{name}:{number}: {line.strip()[:110]}')
        self.assertEqual(bad, [], 'say "Jobadabra" (or add the external name to KEPT with its reason):\n' + '\n'.join(bad[:40]))


if __name__ == '__main__':
    unittest.main()
