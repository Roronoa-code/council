from __future__ import annotations

import copy
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from council.cli import main
from council.config import Config
from council.demo import BRIEF
from council.engine import Engine
from council.install import install
from council.report import render_html
from council.schema import CouncilError
from council.store import Store, atomic_text

ROOT = Path(__file__).resolve().parents[1]


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            status = main(list(args))
        return status, out.getvalue(), err.getvalue()

    def test_cli_demo_and_resume(self):
        directory = self.root / 'demo'
        status, out, _ = self.cli('demo', '--out', str(directory))
        self.assertEqual(status, 0)
        self.assertIn('SYNTHETIC DEMO', out)
        self.assertTrue((directory / 'report.html').exists())
        status, _, err = self.cli('resume', str(directory))
        self.assertEqual(status, 0)
        self.assertIn('checkpoint reused', err)

    def test_actual_module_subprocess(self):
        result = subprocess.run([sys.executable, '-m', 'council', 'demo', '--depth', 'quick', '--out', str(self.root / 'module')],
            cwd=ROOT, capture_output=True, text=True, encoding='utf-8', timeout=20,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('SYNTHETIC DEMO', result.stdout)

    def test_missing_live_cli_never_becomes_demo(self):
        with patch('council.providers.shutil.which', return_value=None):
            status, out, err = self.cli('run', 'A real question?', '--out', str(self.root / 'live'))
        self.assertEqual(status, 2)
        self.assertNotIn('SYNTHETIC DEMO', out)
        self.assertIn('CLI not found', err)
        self.assertFalse((self.root / 'live' / 'report.html').exists())

    def test_question_exclusivity_and_recursive_guard(self):
        self.assertEqual(self.cli('run')[0], 2)
        with patch.dict(os.environ, {'COUNCIL_WORKER': '1'}):
            self.assertEqual(self.cli('demo')[0], 2)

    def test_demo_cannot_record_real_outcome(self):
        directory = self.root / 'demo'
        self.cli('demo', '--out', str(directory))
        status, _, err = self.cli('outcome', str(directory), '--result', 'pass', '--note', 'It worked')
        self.assertEqual(status, 2)
        self.assertIn('Synthetic demo', err)

    def test_output_directory_must_be_empty(self):
        directory = self.root / 'occupied'
        directory.mkdir()
        (directory / 'keep.txt').write_text('preserve', encoding='utf-8')
        self.assertEqual(self.cli('demo', '--out', str(directory))[0], 2)
        self.assertEqual((directory / 'keep.txt').read_text(), 'preserve')

    def test_install_both_hosts_and_idempotence(self):
        roots = install('both', home=self.root)
        self.assertEqual(len(roots), 2)
        for root in roots:
            self.assertIn('name: council', (root / 'SKILL.md').read_text(encoding='utf-8'))
            self.assertEqual(json.loads((root / 'runtime.json').read_text())['python'], str(Path(sys.executable).resolve()))
        self.assertEqual(install('both', home=self.root), roots)
        self.assertFalse((self.root / '.codex' / 'config.toml').exists())

    def test_install_conflict_never_overwrites_without_force(self):
        root = self.root / '.claude/skills/council'
        root.mkdir(parents=True)
        (root / 'SKILL.md').write_text('Custom skill', encoding='utf-8')
        with self.assertRaises(CouncilError):
            install('both', home=self.root)
        self.assertFalse((self.root / '.agents').exists())
        install('both', home=self.root, force=True)
        backups = list(root.glob('SKILL.md.backup-*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), 'Custom skill')

    def test_repo_skill_copies_match_packaged_protocol(self):
        for directory in ('.agents', '.claude'):
            for source, target in [('skill.md', 'SKILL.md'), ('protocol.md', 'protocol.md')]:
                self.assertEqual((ROOT / 'council' / source).read_bytes(),
                                 (ROOT / directory / 'skills/council' / target).read_bytes())

    def test_static_html_escapes_every_untrusted_surface(self):
        store = Store.create(self.root / 'xss', copy.deepcopy(BRIEF), Config(profile='demo'), 'xss-test')
        Engine(store).run()
        state = store.load()
        attack = '<script>alert("bad")</script><img src=x onerror=alert(1)>'
        state['brief']['question'] = attack
        state['brief']['evidence'][0]['excerpt'] = attack
        state['jobs']['chair']['data']['recommendation'] = attack
        state['jobs']['chair']['data']['dissent'][0]['view'] = attack
        output = render_html(state)
        self.assertNotIn('<script', output.lower())
        self.assertNotIn('<img', output.lower())
        self.assertIn('&lt;script&gt;', output)
        self.assertIn("default-src 'none'", output)
        self.assertIn('<h1>', output)
        self.assertIn('<dl>', output)

    def test_stale_lock_only_removed_after_owner_exit(self):
        store = Store.create(self.root / 'lock', copy.deepcopy(BRIEF), Config(profile='demo'), 'lock-test')
        atomic_text(store.path / '.lock', json.dumps({'host': socket.gethostname(), 'pid': 12345678}))
        with patch('council.store.pid_alive', return_value=False):
            store.unlock()
        self.assertFalse((store.path / '.lock').exists())

    def test_read_schema_and_validate_saved_result(self):
        status, output, _ = self.cli('schema', 'decision')
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output)['type'], 'object')
        directory = self.root / 'demo'
        self.cli('demo', '--out', str(directory))
        state = Store(directory).load()
        brief, decision = self.root / 'brief.json', self.root / 'decision.json'
        brief.write_text(json.dumps(state['brief']), encoding='utf-8')
        decision.write_text(json.dumps(state['jobs']['chair']['data']), encoding='utf-8')
        self.assertEqual(self.cli('validate', str(decision), '--brief', str(brief))[0], 0)
