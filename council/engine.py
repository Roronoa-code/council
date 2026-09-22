"""Independent first passes, bounded audits, a Codex-led chair and durable resume."""
from __future__ import annotations

import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .config import Config
from .context import utc_now
from .demo import DemoProvider
from .prompts import make_prompt
from .providers import CLIProvider, ProviderError, Request
from .schema import CouncilError, SCHEMAS, ValidationError, validate_result
from .store import Store, digest


class Engine:
    def __init__(self, store: Store, providers: dict | None = None,
                 progress: Callable[[str], None] | None = None):
        self.store = store
        self.state = store.load()
        self.config = Config(**self.state['config'])
        self.providers = providers if providers is not None else {
            name: DemoProvider() if name == 'demo' else CLIProvider(name, self.config.model_for(name))
            for name in self.config.required_providers()}
        self.progress = progress or (lambda _: None)
        self.cancel = threading.Event()
        self.mutex = threading.RLock()
        self.deadline = 0.0

    def _job(self, job: str, stage: str, role: str, candidates: list | None = None,
             reviews: list | None = None) -> dict:
        provider = self.config.provider_for(role)
        base_prompt = make_prompt(self.state['brief'], stage, role, provider, candidates, reviews)
        fingerprint = digest({'prompt': base_prompt, 'schema': SCHEMAS[stage],
                              'provider': provider, 'model': self.config.model_for(provider)})
        evidence_ids = {e['id'] for e in self.state['brief']['evidence']}
        candidate_ids = {c['candidate_id'] for c in candidates or []}
        with self.mutex:
            cached = self.state['jobs'].get(job)
            if cached is not None:
                if not isinstance(cached, dict) or cached.get('fingerprint') != fingerprint or cached.get('data_hash') != digest(cached.get('data')):
                    raise CouncilError(f'Checkpoint mismatch in {job}. Start a new run; altered results are not silently reused.')
                validate_result(cached['data'], stage, evidence_ids, candidate_ids)
                self.progress(f'{job}: validated checkpoint reused')
                return cached['data']
        repair = None
        for attempt_number in range(self.config.retries + 1):
            with self.mutex:
                remaining = self.deadline - time.monotonic()
                if self.cancel.is_set() or remaining <= 0:
                    raise CouncilError('Run cancelled or deadline reached; valid checkpoints were kept')
                if self.state['calls_used'] >= self.state['budget_limit']:
                    raise CouncilError('Invocation budget exhausted. Resume with an explicit additional-call allowance.')
                prompt = base_prompt if repair is None else make_prompt(self.state['brief'], stage, role, provider, candidates, reviews, repair)
                attempt = {'job': job, 'provider': provider, 'started_at': utc_now(),
                           'prompt_hash': digest(prompt), 'status': 'running'}
                self.state['calls_used'] += 1
                self.state['attempts'].append(attempt)
                self.store.save(self.state)  # Reserve before launch, including interrupted attempts.
                self.store.event('job_started', job=job, provider=provider, calls_used=self.state['calls_used'])
                self.progress(f'{job}: {provider}, invocation {self.state["calls_used"]}/{self.state["budget_limit"]}')
            try:
                reply = self.providers[provider].invoke(
                    Request(prompt, SCHEMAS[stage], stage, role, tuple(sorted(candidate_ids))),
                    min(self.config.timeout, remaining), self.cancel)
                validate_result(reply.data, stage, evidence_ids, candidate_ids)
                with self.mutex:
                    if self.cancel.is_set():
                        raise CouncilError('Run cancelled before result acceptance')
                    self.state['jobs'][job] = {'stage': stage, 'role': role, 'provider': provider,
                        'fingerprint': fingerprint, 'data_hash': digest(reply.data),
                        'data': reply.data, 'meta': reply.meta, 'completed_at': utc_now()}
                    attempt.update(status='complete', completed_at=utc_now())
                    self.store.save(self.state)
                    self.store.event('job_completed', job=job)
                return reply.data
            except BaseException as exc:
                safe_error = str(exc)[:1200] if isinstance(exc, CouncilError) else type(exc).__name__
                with self.mutex:
                    attempt.update(status='failed', completed_at=utc_now(), error=safe_error)
                    self.store.save(self.state)
                    self.store.event('job_failed', job=job, error=safe_error)
                retry = isinstance(exc, ValidationError) or (isinstance(exc, ProviderError) and exc.retryable)
                if not retry or attempt_number >= self.config.retries or self.cancel.is_set():
                    raise
                repair = safe_error if isinstance(exc, ValidationError) else None
                self.progress(f'{job}: one bounded retry; original failure retained')
        raise CouncilError('Unreachable job state')

    def _parallel(self, tasks: list[tuple]) -> dict[str, dict]:
        if not tasks:
            return {}
        pool = ThreadPoolExecutor(max_workers=self.config.parallel)
        futures = {pool.submit(self._job, *task): task[0] for task in tasks}
        results = {}
        try:
            for future in as_completed(futures):
                results[futures[future]] = future.result()
        except BaseException:
            self.cancel.set()
            for future in futures:
                future.cancel()
            raise
        finally:
            pool.shutdown(wait=True, cancel_futures=True)
        return results

    def _execute(self) -> dict:
        depth = self.config.depth
        roles = [] if depth == 'single' else ['believer', 'skeptic']
        if depth in {'standard', 'deep'}:
            roles.append('operator')
        opinions = self._parallel([(f'opinion-{role}', 'opinion', role) for role in roles])
        order = self.state['candidate_order']
        if not order:
            order = roles.copy()
            random.Random(self.state['run_id']).shuffle(order)
            self.state['candidate_order'] = order
            self.store.save(self.state)
        if sorted(order) != sorted(roles):
            raise CouncilError('Saved candidate mapping does not match this run')
        candidates = [{'candidate_id': chr(65 + i), 'opinion': opinions[f'opinion-{role}']}
                      for i, role in enumerate(order)]
        audits = []
        if depth == 'standard':
            audits = [self._job('review-auditor', 'review', 'auditor', candidates)]
        elif depth == 'deep':
            tasks = []
            for role in roles:
                own = chr(65 + order.index(role))
                others = [c for c in candidates if c['candidate_id'] != own]
                tasks.append((f'review-{role}', 'review', role, others))
            outputs = self._parallel(tasks)
            audits = [outputs[f'review-{role}'] for role in roles]
        reviews = [{'review_id': f'R{i+1}', 'review': data} for i, data in enumerate(audits)]
        return self._job('chair', 'decision', 'chair', candidates, reviews)

    def run(self, additional_calls: int = 0) -> dict:
        if type(additional_calls) is not int or additional_calls < 0:
            raise CouncilError('Additional invocation allowance must be a nonnegative integer')
        with self.store.lock():
            self.state = self.store.load()
            self.config = Config(**self.state['config'])
            if self.state['budget_limit'] + additional_calls > 64:
                raise CouncilError('A run cannot exceed 64 total CLI invocations, including resumes')
            self.state['budget_limit'] += additional_calls
            self.cancel.clear()
            self.deadline = time.monotonic() + self.config.run_timeout
            self.state.update(status='running', last_started_at=utc_now())
            self.store.save(self.state)
            try:
                # Detect missing subscription logins before spending another provider's quota.
                if 'chair' not in self.state['jobs']:
                    for name in sorted(self.config.required_providers()):
                        worker = self.providers.get(name)
                        if worker is None:
                            raise CouncilError(f'Missing provider: {name}; no fallback is permitted')
                        if isinstance(worker, CLIProvider):
                            status = worker.doctor()
                            if not status['ready']:
                                raise ProviderError(f'{name}: {status["message"]}')
                decision = self._execute()
                self.state.update(status='complete', completed_at=utc_now())
                self.state.pop('error', None)
                self.store.save(self.state)
                from .report import write_reports
                write_reports(self.store.path, self.state)
                self.store.event('run_completed', calls_used=self.state['calls_used'])
                return decision
            except BaseException as exc:
                self.cancel.set()
                self.state.update(status='interrupted' if isinstance(exc, KeyboardInterrupt) else 'failed',
                    error=str(exc)[:1200] if isinstance(exc, CouncilError) else type(exc).__name__)
                self.store.save(self.state)
                self.store.event('run_stopped', status=self.state['status'], error=self.state['error'])
                # A stale complete report must not survive a failed revalidation.
                for name in ('report.md', 'report.html', 'report.json', 'handoff.md'):
                    (self.store.path / name).unlink(missing_ok=True)
                raise
