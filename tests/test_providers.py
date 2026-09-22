from __future__ import annotations

import json
import os
import signal
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from council.demo import decision
from council.providers import (CLIProvider, ProcessResult, ProcessRunner, ProviderError, Request,
    child_environment, codex_overrides, executable, parse_claude, parse_codex)
from council.schema import DECISION, ValidationError, validate_result


class ContractTests(unittest.TestCase):
    def test_claude_structured_envelope_and_usage(self):
        reply = parse_claude(json.dumps({'structured_output': decision(), 'session_id': 'fixture-session',
            'usage': {'input_tokens': 3, 'output_tokens': 5, 'secret': 'never copy'},
            'modelUsage': {'fixture-model': {}}}))
        self.assertEqual(reply.data, decision())
        self.assertEqual(reply.meta['usage'], {'input_tokens': 3, 'output_tokens': 5})
        self.assertEqual(reply.meta['reported_models'], ['fixture-model'])

    def test_claude_json_string_result_fallback(self):
        self.assertEqual(parse_claude(json.dumps({'result': json.dumps(decision())})).data, decision())

    def test_claude_errors_even_with_json_and_exit_zero(self):
        for envelope in ({'is_error': True, 'structured_output': decision()},
                         {'subtype': 'error_max_turns', 'result': json.dumps(decision())}):
            with self.assertRaises(ProviderError):
                parse_claude(json.dumps(envelope))

    def test_codex_jsonl_final_and_usage(self):
        raw = '\n'.join(json.dumps(e) for e in [
            {'type': 'thread.started', 'thread_id': 'fixture-thread'},
            {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': 'NOT COPIED'}},
            {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': json.dumps(decision())}},
            {'type': 'turn.completed', 'usage': {'input_tokens': 9, 'output_tokens': 4}}])
        reply = parse_codex(raw, None)
        self.assertEqual(reply.data, decision())
        self.assertEqual(reply.meta['session_id'], 'fixture-thread')
        self.assertNotIn('NOT COPIED', json.dumps(reply.meta))
        self.assertEqual(parse_codex(raw, json.dumps(decision())).data, decision())

    def test_codex_failure_event_overrides_plausible_final(self):
        with self.assertRaises(ProviderError):
            parse_codex('{"type":"turn.failed","error":"quota exceeded"}', json.dumps(decision()))

    def test_invalid_envelopes_are_not_salvaged(self):
        for raw in ('[]', '{}', '{"structured_output":null}'):
            with self.assertRaises(ValidationError):
                parse_claude(raw)
        with self.assertRaises(ValidationError):
            parse_codex('not-json', json.dumps(decision()))

    def test_key_and_cloud_environment_removed_but_nested_guard_kept(self):
        env = child_environment({'OPENAI_API_KEY': 'secret', 'ANTHROPIC_API_KEY': 'secret',
            'ANTHROPIC_AUTH_TOKEN': 'secret', 'CLAUDE_CODE_OAUTH_TOKEN': 'secret',
            'CLAUDE_CODE_USE_BEDROCK': '1', 'OPENAI_BASE_URL': 'wrong', 'CLAUDECODE': '1', 'PATH': 'bin'})
        for key in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN',
                    'CLAUDE_CODE_OAUTH_TOKEN', 'CLAUDE_CODE_USE_BEDROCK', 'OPENAI_BASE_URL'):
            self.assertNotIn(key, env)
        self.assertEqual(env['CLAUDECODE'], '1')
        self.assertEqual(env['COUNCIL_WORKER'], '1')

    def test_codex_config_explicitly_disables_merged_mcp_names(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'config.toml'
            p.write_text('[mcp_servers.tools]\ncommand="dangerous"\n[profiles.x.mcp_servers."nested.name"]\ncommand="no"', encoding='utf-8')
            values = codex_overrides([p])
            self.assertIn('forced_login_method="chatgpt"', values)
            self.assertIn('mcp_servers."tools".enabled=false', values)
            self.assertIn('mcp_servers."nested.name".enabled=false', values)
            self.assertIn('features.multi_agent=false', values)
            self.assertIn('features.apps=false', values)

    def test_malformed_codex_configuration_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'config.toml'
            p.write_text('not valid = [', encoding='utf-8')
            with self.assertRaises(ProviderError):
                codex_overrides([p])

    def test_command_contracts_never_use_bare_or_permission_bypass(self):
        with tempfile.TemporaryDirectory() as temp, patch('council.providers.codex_overrides', return_value=[]):
            request = Request('question; $(do not execute)', DECISION, 'decision', 'chair')
            for name in ('codex', 'claude'):
                provider = CLIProvider(name)
                provider.command = [name]
                args = provider.command_for(request, Path(temp))
                self.assertNotIn(request.prompt, args)
                self.assertNotIn('--bare', args)
                self.assertNotIn('--dangerously-skip-permissions', args)
                if name == 'codex':
                    self.assertIn('read-only', args)
                    self.assertIn('--ephemeral', args)
                    self.assertEqual(args[-1], '-')
                else:
                    self.assertIn('--safe-mode', args)
                    self.assertIn('mcp__*', args)
                    self.assertEqual(args[args.index('--tools') + 1], '')
                    self.assertIn('--no-session-persistence', args)

    def test_windows_known_npm_shim_uses_node_not_cmd(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            shim = root / 'codex.cmd'
            shim.write_text('not executed', encoding='utf-8')
            script = root / 'node_modules/@openai/codex/bin/codex.js'
            script.parent.mkdir(parents=True)
            script.write_text('// fixture', encoding='utf-8')
            with patch('council.providers.shutil.which', side_effect=lambda x: 'node.exe' if x == 'node' else str(shim)):
                self.assertEqual(executable('codex', windows=True), ['node.exe', str(script)])
            script.unlink()
            with patch('council.providers.shutil.which', return_value=str(shim)), self.assertRaises(ProviderError):
                executable('codex', windows=True)

    def test_doctor_rejects_api_login_and_malformed_status(self):
        for name, status in [('claude', '[]'), ('claude', '{"loggedIn":true,"authMethod":"api_key"}'),
                             ('codex', 'Logged in using an API key. Use ChatGPT for subscription access.')]:
            with self.subTest(name=name, status=status), patch('council.providers.executable', return_value=['fixture-cli']):
                class Runner:
                    def run(self, args, *_):
                        return ProcessResult('fixture-1' if '--version' in args else status, '', 0, 0)
                self.assertFalse(CLIProvider(name, runner=Runner()).doctor()['ready'])


class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='council process test ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runner = ProcessRunner()

    def test_real_process_receives_unicode_and_metacharacters_literally(self):
        data = 'hello 世界 & echo OWNED; $(touch wrong)\n"quotes"'
        output = self.runner.run([sys.executable, '-c', 'import sys; print(sys.stdin.read(), end="")'],
                                 data, self.root, 5, threading.Event())
        self.assertEqual(output.stdout, data)
        self.assertEqual(output.returncode, 0)
        self.assertFalse((self.root / 'wrong').exists())

    def test_real_process_timeout(self):
        start = time.monotonic()
        with self.assertRaisesRegex(ProviderError, 'timed out'):
            self.runner.run([sys.executable, '-c', 'import time; time.sleep(20)'], '', self.root, .15, threading.Event())
        self.assertLess(time.monotonic() - start, 8)

    def test_real_process_cancellation(self):
        cancel = threading.Event()
        timer = threading.Timer(.15, cancel.set)
        timer.start()
        try:
            with self.assertRaisesRegex(ProviderError, 'cancelled'):
                self.runner.run([sys.executable, '-c', 'import time; time.sleep(20)'], '', self.root, 10, cancel)
        finally:
            timer.join()

    def test_output_and_input_bounds(self):
        with self.assertRaisesRegex(ProviderError, 'output exceeded'):
            self.runner.run([sys.executable, '-c', 'print("x"*2100000)'], '', self.root, 5, threading.Event())
        with self.assertRaisesRegex(ProviderError, 'prompt exceeds'):
            self.runner.run([sys.executable, '-c', 'pass'], 'x' * 200001, self.root, 5, threading.Event())

    @unittest.skipUnless(sys.platform.startswith('linux'), 'Linux process-group inspection')
    def test_cancellation_kills_grandchild_even_if_parent_exits_first(self):
        child = ('import signal,time,pathlib; signal.signal(signal.SIGTERM,signal.SIG_IGN); '
                 'pathlib.Path("child.ready").write_text("ready"); time.sleep(30)')
        code = ('import subprocess,sys,time; p=subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
                'open("child.pid","w").write(str(p.pid)); time.sleep(30)')
        cancel = threading.Event()
        def after_ready():
            deadline = time.monotonic() + 8
            while not (self.root / 'child.ready').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            cancel.set()
        stopper = threading.Thread(target=after_ready)
        stopper.start()
        try:
            with self.assertRaises(ProviderError):
                self.runner.run([sys.executable, '-c', code], '', self.root, 10, cancel)
        finally:
            stopper.join()
        pid = int((self.root / 'child.pid').read_text())
        try:
            stat = Path(f'/proc/{pid}/stat')
            deadline = time.monotonic() + 2
            while stat.exists() and stat.read_text().split()[2] != 'Z' and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertTrue(not stat.exists() or stat.read_text().split()[2] == 'Z')
        finally:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def test_actual_subprocess_round_trip_both_provider_formats(self):
        # This is an offline CLI contract fixture, NOT either vendor's executable.
        fixture = self.root / 'offline_cli.py'
        payload = json.dumps(decision())
        fixture.write_text('''import json,sys,pathlib
kind=sys.argv[1]; args=sys.argv[2:]
if '--version' in args: print('OFFLINE-FIXTURE/1'); sys.exit(0)
if 'status' in args:
    print('Logged in using ChatGPT' if kind=='codex' else json.dumps({'loggedIn':True,'authMethod':'claude.ai','subscriptionType':'max'})); sys.exit(0)
text=sys.stdin.read()
assert 'UNTRUSTED' in text
result=json.loads(''' + repr(payload) + ''')
if kind=='codex':
    schema=pathlib.Path(args[args.index('--output-schema')+1]); assert json.loads(schema.read_text())['type']=='object'
    pathlib.Path(args[args.index('--output-last-message')+1]).write_text(json.dumps(result),encoding='utf-8')
    print(json.dumps({'type':'thread.started','thread_id':'OFFLINE-CODEX-FIXTURE'}))
    print(json.dumps({'type':'turn.completed','usage':{'input_tokens':1,'output_tokens':1}}))
else:
    assert '--safe-mode' in args and '--strict-mcp-config' in args
    print(json.dumps({'structured_output':result,'session_id':'OFFLINE-CLAUDE-FIXTURE','is_error':False}))
''', encoding='utf-8')
        for name in ('codex', 'claude'):
            with self.subTest(provider=name), patch('council.providers.executable', return_value=[sys.executable, str(fixture), name]), patch('council.providers.codex_overrides', return_value=[]):
                provider = CLIProvider(name)
                reply = provider.invoke(Request('UNTRUSTED test fixture only', DECISION, 'decision', 'chair'), 10, threading.Event())
                validate_result(reply.data, 'decision', {'E1'})
                self.assertEqual(reply.data, decision())
                self.assertIn('OFFLINE', reply.meta['session_id'])
                self.assertEqual(reply.meta['cli_version'], 'OFFLINE-FIXTURE/1')
