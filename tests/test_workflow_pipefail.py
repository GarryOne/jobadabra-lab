"""A step that pipes a job that can fail into `tee` must set pipefail (owner, 24 Oct 2026): GitHub's default `bash -e` returns tee's status, so a changelog run ended GREEN while every AI draft was refused.
`echo ... | tee -a "$GITHUB_STEP_SUMMARY"` is fine (echo cannot fail); a node, python, bash, gh or tools/ command before `| tee` is not."""
import pathlib
import re
import unittest

WORKFLOWS = pathlib.Path(__file__).resolve().parent.parent / '.github/workflows'
RISKY = re.compile(r'(?:^|[;&|(]|\brun:|\bthen|\belse|\bdo)\s*(?:\w+=\S+\s+)*(?:node|python3?|npm|npx|bash|sh|gh|pytest|make|curl|\.?/?tools/\S+|\./\S+)\b[^|;]*\|\s*tee\b')


def steps(text):
    return re.split(r'(?m)^\s{6}- (?=\w+:)', text)[1:]


def offenders():
    found = []
    for path in sorted(WORKFLOWS.glob('*.yml')):
        text = path.read_text()
        if re.search(r'(?m)^defaults:\s*\n\s+run:\s*\n\s+shell:\s*bash', text):
            continue
        for step in steps(text):
            code = re.sub(r'\$\{\{.*?\}\}', 'X', re.sub(r'\\\n\s*', ' ', re.sub(r'(?m)^\s*#.*$', '', step)))
            if any(RISKY.search(line) for line in code.splitlines()) and not re.search(r'pipefail|shell:\s*bash', code):
                found.append(f"{path.name}: {step.splitlines()[0].strip()[:70]}")
    return found


class PipefailTests(unittest.TestCase):
    def test_every_step_that_pipes_a_job_into_tee_fails_when_the_job_fails(self):
        self.assertEqual(offenders(), [])
