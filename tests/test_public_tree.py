"""tools/public-tree.sh builds the lab's working tree: public jobadabra at a ref with this repo's files laid over it, its own rules left out."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools' / 'public-tree.sh'


class PublicTreeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = pathlib.Path(self.tmp.name)
        # a stand-in for the public repo: a local git repo with a product file and a README of its own
        self.public = base / 'public'
        self.public.mkdir()
        run = lambda *a: subprocess.run(a, cwd=self.public, check=True, capture_output=True)
        run('git', 'init', '-q', '-b', 'main')
        run('git', 'config', 'user.email', 't@example.com')
        run('git', 'config', 'user.name', 't')
        (self.public / 'extension').mkdir()
        (self.public / 'extension' / 'flow.js').write_text('// public\n')
        (self.public / 'README.md').write_text('public readme\n')
        run('git', 'add', '-A')
        run('git', 'commit', '-qm', 'public')
        self.out = base / 'tree'

    def tearDown(self):
        self.tmp.cleanup()

    def build(self):
        env = dict(os.environ, PUBLIC_REPO_URL=str(self.public))
        return subprocess.run(['bash', str(SCRIPT), str(self.out), 'main'], env=env, capture_output=True, text=True, check=True)

    def test_public_files_and_lab_files_meet_at_the_same_paths(self):
        self.build()
        self.assertEqual((self.out / 'extension' / 'flow.js').read_text(), '// public\n')
        self.assertTrue((self.out / 'tools' / 'public-tree.sh').exists(), 'the lab files are laid over the public tree')

    def test_the_lab_keeps_its_own_readme_tests_and_workflows_out(self):
        self.build()
        self.assertEqual((self.out / 'README.md').read_text(), 'public readme\n')
        self.assertFalse((self.out / 'tests' / 'test_public_tree.py').exists())
        self.assertFalse((self.out / '.github' / 'workflows' / 'public-page-cases.yml').exists())

    def test_lab_files_are_visible_to_git_ls_files(self):
        self.build()
        listed = subprocess.run(['git', 'ls-files'], cwd=self.out, capture_output=True, text=True, check=True).stdout.split()
        self.assertIn('tools/public-tree.sh', listed)


if __name__ == '__main__':
    unittest.main()
