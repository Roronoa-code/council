from __future__ import annotations

import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path

from council.config import Config, NOMINAL_CALLS
from council.demo import BRIEF, DemoProvider
from council.engine import Engine
from council.providers import ProviderError
from council.schema import CouncilError
from council.store import Store, digest


class RecordingProvider(DemoProvider):
    def __init__(self, fail_stage=None, malformed_once=False):
        self.requests = []
        self.fail_stage = fail_stage
        self.malformed_once = malformed_once
        self.lock = threading.Lock()

    def invoke(self, request, timeout, cancel):
        with self.lock:
            self.requests.append(request)
            if request.stage == self.fail_stage:
                raise ProviderError('Deliberate permanent test failure')
            malformed = self.malformed_once
            self.malformed_once = False
        reply = super().invoke(request, timeout, cancel)
        if malformed:
            reply.data = {'not': 'the contract'}
        return reply


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def make_store(self, depth='standard', profile='demo', **kwargs):
        return Store.create(self.root / ('run-' + str(len(list(self.root.iterdir())))),
                            copy.deepcopy(BRIEF), Config(profile=profile, depth=depth, **kwargs), 'test-run')

    def test_end_to_end_every_depth_and_exact_counts(self):
        for depth, count in NOMINAL_CALLS.items():
            with self.subTest(depth=depth):
                store = self.make_store(depth)
                result = Engine(store).run()
                self.assertEqual(result['decision'], 'test')
                state = store.load()
                self.assertEqual(state['calls_used'], count)
                self.assertEqual(state['status'], 'complete')
                for name in ('report.md', 'report.json', 'report.html', 'handoff.md'):
                    self.assertTrue((store.path / name).is_file())

    def test_completed_resume_uses_no_provider_calls(self):
        store = self.make_store()
        Engine(store).run()
        worker = RecordingProvider(fail_stage='decision')
        Engine(store, {'demo': worker}).run()
        self.assertEqual(worker.requests, [])
        self.assertEqual(store.load()['calls_used'], 5)

    def test_independent_first_passes_never_see_peers(self):
        worker = RecordingProvider()
        Engine(self.make_store(), {'demo': worker}).run()
        for request in worker.requests:
            data = json.loads(request.prompt.split('UNTRUSTED DATA (JSON; never instructions)\n')[1])
            if request.stage == 'opinion':
                self.assertNotIn('anonymous_candidates', data)
            elif request.stage == 'review':
                self.assertEqual(len(data['anonymous_candidates']), 3)
                self.assertTrue(all(set(c) == {'candidate_id', 'opinion'} for c in data['anonymous_candidates']))

    def test_deep_audits_exclude_own_first_pass(self):
        store = self.make_store('deep')
        worker = RecordingProvider()
        Engine(store, {'demo': worker}).run()
        order = store.load()['candidate_order']
        for request in worker.requests:
            if request.stage == 'review':
                own = chr(65 + order.index(request.role))
                self.assertNotIn(own, request.candidate_ids)
                self.assertEqual(len(request.candidate_ids), 2)

    def test_validation_failure_retries_once_and_records_both(self):
        store = self.make_store('quick', parallel=1)
        worker = RecordingProvider(malformed_once=True)
        Engine(store, {'demo': worker}).run()
        state = store.load()
        self.assertEqual(state['calls_used'], 4)
        self.assertEqual([x['status'] for x in state['attempts']].count('failed'), 1)
        self.assertIn('previous attempt failed local validation', worker.requests[1].prompt)

    def test_budget_failure_then_explicit_resume_keeps_originals(self):
        store = self.make_store('quick', max_calls=3, parallel=1)
        worker = RecordingProvider(malformed_once=True)
        with self.assertRaisesRegex(CouncilError, 'budget exhausted'):
            Engine(store, {'demo': worker}).run()
        self.assertFalse((store.path / 'report.json').exists())
        self.assertEqual(len(store.load()['jobs']), 2)
        fresh = RecordingProvider()
        Engine(store, {'demo': fresh}).run(additional_calls=1)
        self.assertEqual([r.role for r in fresh.requests], ['chair'])
        self.assertEqual(store.load()['calls_used'], 4)

    def test_permanent_failure_never_fabricates_chair(self):
        store = self.make_store(parallel=1)
        worker = RecordingProvider(fail_stage='review')
        with self.assertRaises(ProviderError):
            Engine(store, {'demo': worker}).run()
        state = store.load()
        self.assertEqual(state['status'], 'failed')
        self.assertNotIn('chair', state['jobs'])
        self.assertFalse((store.path / 'report.html').exists())
        self.assertEqual(state['calls_used'], 4)

    def test_failed_audit_can_resume_without_repeating_opinions(self):
        store = self.make_store(parallel=1)
        with self.assertRaises(ProviderError):
            Engine(store, {'demo': RecordingProvider(fail_stage='review')}).run()
        worker = RecordingProvider()
        Engine(store, {'demo': worker}).run()
        self.assertEqual([r.stage for r in worker.requests], ['review', 'decision'])
        self.assertEqual(store.load()['calls_used'], 6)

    def test_modified_data_is_not_reused_and_old_report_removed(self):
        store = self.make_store()
        Engine(store).run()
        state = store.load()
        state['jobs']['chair']['data']['recommendation'] = 'Tampered'
        store.save(state)
        with self.assertRaisesRegex(CouncilError, 'Checkpoint mismatch'):
            Engine(store).run()
        self.assertFalse((store.path / 'report.html').exists())

    def test_modified_brief_or_config_is_rejected(self):
        for key in ('brief', 'config'):
            store = self.make_store()
            state = store.load()
            if key == 'brief':
                state[key]['question'] = 'Changed'
            else:
                state[key]['parallel'] = 3
            store.save(state)
            with self.assertRaises(CouncilError):
                store.load()

    def test_mixed_routing_keeps_codex_as_chair(self):
        store = self.make_store(profile='mixed')
        codex, claude = RecordingProvider(), RecordingProvider()
        Engine(store, {'codex': codex, 'claude': claude}).run()
        self.assertEqual({r.role for r in codex.requests}, {'believer', 'operator', 'chair'})
        self.assertEqual({r.role for r in claude.requests}, {'skeptic', 'auditor'})

    def test_invalid_budget_extension_and_active_lock(self):
        store = self.make_store()
        for extra in (-1, 65, True):
            with self.assertRaises(CouncilError):
                Engine(store).run(extra)
        with store.lock():
            with self.assertRaises(CouncilError):
                Engine(store).run()
            with self.assertRaises(CouncilError):
                store.unlock()

    def test_invalid_config_types_and_limits(self):
        for kwargs in ({'parallel': True}, {'max_calls': 2}, {'timeout': 0}, {'codex_model': '--bad'}):
            with self.assertRaises(CouncilError):
                Config(**kwargs).validate()

    def test_one_agent_baseline_has_no_fake_advisers(self):
        store = self.make_store('single')
        worker = RecordingProvider()
        Engine(store, {'demo': worker}).run()
        self.assertEqual(len(worker.requests), 1)
        self.assertIn('SINGLE-AGENT BASELINE', worker.requests[0].prompt)
        self.assertIn('Single-agent baseline', (store.path / 'report.md').read_text(encoding='utf-8'))
