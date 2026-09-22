"""Command-line interface. Live runs never silently become demonstrations."""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import Config
from .context import build_brief, evidence_file, read_text, utc_now
from .demo import BRIEF as DEMO_BRIEF
from .engine import Engine
from .install import install
from .providers import CLIProvider
from .schema import CouncilError, SCHEMAS, strict_json, validate_brief, validate_result
from .store import Store, atomic_json


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog='council', description='Evidence-led decision councils for local Codex and Claude Code subscription CLIs.')
    p.add_argument('--version', action='version', version=__version__)
    commands = p.add_subparsers(dest='command', required=True)
    run = commands.add_parser('run', help='Run a real council using your existing subscription login')
    run.add_argument('question', nargs='?')
    run.add_argument('--question-file', type=Path)
    run.add_argument('--mode', choices=['general', 'business', 'product', 'technical'], default='general')
    run.add_argument('--constraint', action='append', default=[])
    run.add_argument('--context', action='append', default=[], metavar='FILE[::FIRST:LAST]')
    run.add_argument('--evidence', type=Path, help='JSON array of source records; URLs are not automatically fetched')
    run.add_argument('--profile', choices=['mixed', 'codex', 'claude'], default='mixed')
    run.add_argument('--depth', choices=['single', 'quick', 'standard', 'deep'], default='standard')
    run.add_argument('--max-calls', type=int, default=8)
    run.add_argument('--parallel', type=int, default=2)
    run.add_argument('--timeout', type=int, default=240, help='Per-CLI invocation seconds')
    run.add_argument('--run-timeout', type=int, default=1200, help='Whole-run seconds; resets explicitly on resume')
    run.add_argument('--retries', type=int, choices=[0, 1], default=1)
    run.add_argument('--codex-model')
    run.add_argument('--claude-model')
    run.add_argument('--out', type=Path)
    demo = commands.add_parser('demo', help='Run the complete engine using clearly labelled deterministic fixtures')
    demo.add_argument('--out', type=Path)
    demo.add_argument('--depth', choices=['single', 'quick', 'standard', 'deep'], default='standard')
    doctor = commands.add_parser('doctor', help='Check installed CLIs and subscription login without calling a model')
    doctor.add_argument('--profile', choices=['mixed', 'codex', 'claude'], default='mixed')
    resume = commands.add_parser('resume', help='Reuse validated completed stages, not vendor chat history')
    resume.add_argument('run', type=Path)
    resume.add_argument('--additional-calls', type=int, default=0)
    ins = commands.add_parser('install', help='Install native skills, without modifying CLI configuration')
    ins.add_argument('--target', choices=['codex', 'claude', 'both'], default='both')
    ins.add_argument('--project', type=Path, help='Project root; omitted means user-wide installation')
    ins.add_argument('--force', action='store_true', help='Back up and replace existing Council-owned skill files')
    schema = commands.add_parser('schema', help='Print the exact shared output contract')
    schema.add_argument('stage', choices=list(SCHEMAS))
    schema.add_argument('--out', type=Path)
    validate = commands.add_parser('validate', help='Validate a saved decision against a brief and its evidence IDs')
    validate.add_argument('decision', type=Path)
    validate.add_argument('--brief', type=Path, required=True)
    unlock = commands.add_parser('unlock', help='Remove a lock only after its local owning process has exited')
    unlock.add_argument('run', type=Path)
    outcome = commands.add_parser('outcome', help='Record an explicitly reported real-world result, not automatic learning')
    outcome.add_argument('run', type=Path)
    outcome.add_argument('--result', choices=['pass', 'fail', 'inconclusive'], required=True)
    outcome.add_argument('--note', required=True)
    return p


def _new_run(brief: dict, config: Config, out: Path | None) -> tuple[Store, dict]:
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid.uuid4().hex[:8]
    directory = out or Path.home() / '.council' / 'runs' / run_id
    store = Store.create(directory, brief, config, run_id)
    result = Engine(store, progress=lambda s: print(s, file=sys.stderr, flush=True)).run()
    return store, result


def _print_result(store: Store, result: dict) -> None:
    print(f'{result["decision"].upper()}: {result["recommendation"]}')
    print(f'Next action: {result["next_action"]["action"]}')
    print(f'Report: {store.path / "report.html"}')
    print(f'Checkpoint: {store.path}')


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if os.environ.get('COUNCIL_WORKER') and args.command in {'run', 'demo', 'resume'}:
            raise CouncilError('Recursive councils are disabled. Return your assigned bounded result to the parent.')
        if args.command == 'doctor':
            names = ['codex', 'claude'] if args.profile == 'mixed' else [args.profile]
            reports = [CLIProvider(name).doctor() for name in names]
            print(json.dumps(reports, indent=2))
            return 0 if all(r['ready'] for r in reports) else 2
        if args.command == 'install':
            for root in install(args.target, args.project, args.force):
                print(f'Installed: {root}')
            print('Restart/reload the host to discover the skill. Codex: $council. Claude Code: /council.')
            return 0
        if args.command == 'schema':
            if args.out:
                if args.out.exists():
                    raise CouncilError('Schema output already exists; choose a new filename')
                atomic_json(args.out, SCHEMAS[args.stage])
            else:
                print(json.dumps(SCHEMAS[args.stage], indent=2))
            return 0
        if args.command == 'validate':
            brief = strict_json(read_text(args.brief, 48000))
            validate_brief(brief)
            validate_result(strict_json(read_text(args.decision, 250000)), 'decision', {e['id'] for e in brief['evidence']})
            print('Schema and evidence IDs valid. Source relevance and real-world truth were not verified.')
            return 0
        if args.command == 'unlock':
            Store(args.run).unlock()
            print('Removed lock belonging to an exited local process.')
            return 0
        if args.command == 'outcome':
            store = Store(args.run)
            if not 1 <= len(args.note.strip()) <= 4000:
                raise CouncilError('Outcome note must contain 1–4,000 characters')
            with store.lock():
                state = store.load()
                if state['status'] != 'complete':
                    raise CouncilError('Only a completed council can receive an outcome record')
                if state['config']['profile'] == 'demo':
                    raise CouncilError('Synthetic demo results cannot be labelled as real-world outcomes')
                from .context import check_secrets
                check_secrets(args.note)
                store.event('user_reported_outcome', result=args.result, note=args.note, recorded_at=utc_now())
            print('Saved as a user-reported outcome, not independent verification or model training.')
            return 0
        if args.command == 'resume':
            store = Store(args.run)
            result = Engine(store, progress=lambda s: print(s, file=sys.stderr, flush=True)).run(args.additional_calls)
            _print_result(store, result)
            return 0
        if args.command == 'demo':
            config = Config(profile='demo', depth=args.depth)
            store, result = _new_run(copy.deepcopy(DEMO_BRIEF), config, args.out)
            print('SYNTHETIC DEMO: no model calls, no customer research, no validated business outcome.')
        else:
            if bool(args.question) == bool(args.question_file):
                raise CouncilError('Supply one question OR --question-file, not both')
            question = read_text(args.question_file, 64000) if args.question_file else args.question
            brief = build_brief(question, args.mode, args.constraint, args.context,
                                evidence_file(args.evidence) if args.evidence else [])
            config = Config(profile=args.profile, depth=args.depth, parallel=args.parallel,
                            timeout=args.timeout, run_timeout=args.run_timeout, max_calls=args.max_calls,
                            retries=args.retries, codex_model=args.codex_model, claude_model=args.claude_model)
            store, result = _new_run(brief, config, args.out)
        _print_result(store, result)
        return 0
    except KeyboardInterrupt:
        print('Interrupted. Completed validated stages remain available through council resume.', file=sys.stderr)
        return 130
    except (CouncilError, OSError) as exc:
        print(f'Council stopped: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
