# Verification record

Recorded 2026-09-22. **Offline engineering validation, not a live multi-model evaluation.** No API key or subscription model request was used in this build environment.

## Executed locally

Environment: Linux, Python 3.13.5. The four test modules were run separately after implementation changes and all passed:

| Command | Result |
|---|---:|
| `python -m unittest discover -s tests -p test_schema_context.py -v` | 18 passed |
| `python -m unittest discover -s tests -p test_engine.py -v` | 14 passed |
| `python -m unittest discover -s tests -p test_providers.py -v` | 18 passed |
| `python -m unittest discover -s tests -p test_cli_install_report.py -v` | 12 passed |
| **Total** | **62 passed** |

The suite covers strict JSON/schema validation; unknown/duplicate evidence IDs; factual-claim citation requirements; proceed/high-evidence gates; independent first-pass inputs; identity-reduced review; own-answer exclusion in deep audits; all 1/3/5/7-stage depths; mixed routing; bounded retries; permanent failures; cumulative budgets; resume; changed brief/configuration/result rejection; exclusive locks; installation conflict/backup behaviour; recursive-run prevention; and escaped static reports.

Provider tests include **real subprocesses running explicitly named offline fixtures**, not real Codex/Claude executables. They verify stdin/Unicode/metacharacter handling, JSONL and JSON-envelope parsing, zero-exit error envelopes, subscription-auth recognition/rejection, required safety arguments, API/cloud environment stripping, Windows npm-shim resolution, output limits, timeout/cancellation, and Linux child-process-group cleanup. Windows-specific branches are not thereby proven on a real Windows host.

One early process-tree test used an unrealistically short startup deadline in this environment and failed before the child PID file existed. It was replaced with a readiness-synchronised cancellation test, then passed. One combined suite attempt exceeded the surrounding execution tool's time limit; module-level reruns above are the completed results, not an invented all-at-once pass.

## Executed end-to-end and packaging checks

- `python -m council demo`: completed independent opinions, audit, chair, report generation and private checkpoint creation using synthetic fixture data.
- `python -m council resume <completed-demo>`: validated and reused all five completed stages, with no additional invocations.
- Deep-mode demo: completed all seven stages; each peer audit excludes its own original candidate.
- `python -m pip wheel --no-deps --no-build-isolation .`: built `mani_council-0.1.0-py3-none-any.whl` successfully.
- Installed that wheel into a separate target directory; from outside the source checkout, executed a seven-stage demo and installed both native skill resource sets successfully.
- Validated all seven synthetic evaluation briefs against the input contract. **No quality scores or live evaluation outcomes were manufactured.**
- Re-decoded all 1,209 video frames with the included research utility and exported only numerical frame/timing/luminance-change statistics, not the private source footage.

## Explicitly not verified here

`python -m council doctor --profile mixed` correctly reported that neither `codex` nor `claude` was installed in this environment. Therefore this record does **not** claim authenticated live Codex/Claude execution, Windows-native execution, account eligibility/quota, compatibility with every CLI version, correct real-world recommendations, or a measured improvement over one model.

The repository includes a Windows/Linux, Python 3.11/3.13 GitHub Actions matrix. Inspect the actual run before describing it as passed; a workflow file is not execution evidence. CI has no model credentials and does not upload private run artifacts.

## Local live acceptance check

On the owner's machine, using its existing official CLI subscription logins:

1. Run `council doctor --profile mixed`; both entries must report a recognised login. The probe itself makes no model request. Disable provider extra usage/top-ups separately when subscription-only spending is required.
2. Run one small `--profile codex --depth single --max-calls 2` decision and one `--profile claude --depth single --max-calls 2` decision, with a short non-sensitive evidence file.
3. Run the same brief with `--profile mixed --depth quick --max-calls 4`. Inspect provider/session/version metadata, all completed stages, evidence references and the final action.
4. Resume the completed run; invocation count must remain unchanged. Do not weaken flags, bypass nested-session safeguards, or introduce API billing when a compatibility check fails.

These are explicit future acceptance checks for the local installation, not steps claimed to have happened in this build environment.
