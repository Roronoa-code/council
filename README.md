# Council

**A decision tool, not three agreeable personalities.** Independent opportunity, skeptic and operator passes → bounded evidence review → an actionable verdict. Built for **Codex and Claude Code**, with **Codex leading mixed councils**.

Council uses your locally installed, subscription-authenticated CLIs. It does not ask for API keys, enable paid extra usage, or silently substitute a different provider. Runtime: Python 3.11+, standard library only. This repository is the install source; no PyPI publication is implied.

> **Verification boundary:** the complete offline workflow, adapters, subprocess handling, failure paths and native-skill installation are tested. An offline fixture is not a live AI result. A successful local `doctor` and small live run are still required to establish compatibility with your installed CLIs and accounts. Prompt/workflow tuning is not model-weight fine-tuning.

## What changed from the video

The video's strongest idea is separating the positive case, disconfirmation, feasibility and judgement. Council adds genuinely separate first passes; identity-reduced audits; evidence IDs; preserved dissent; bounded retries and invocation budgets; durable checkpoints; and one next experiment with an observable metric, pass/fail rules, timebox and resource ceiling. It does **not** decide by voting or force agreement.

For software, the Investor becomes an **Operator**: real interfaces, dependencies, integration risk, tests and maintenance—not invented revenue. A verdict can be **proceed, test, revise, stop or defer**. `handoff.md` gives the coding agent a bounded proposal, not permission to execute arbitrary actions.

[Frame-indexed video study](research/00-video-analysis.md) · [Research and source links](research/01-related-work.md) · [Architecture and tradeoffs](research/02-design-decisions.md) · [Verification record](research/03-verification.md)

## Windows setup

Install Python 3.11+ and Git. Install/sign in to the official [Codex CLI](https://developers.openai.com/codex/cli) and [Claude Code](https://code.claude.com/docs/en/setup) with your existing subscriptions. Ordinary saved logins are used; do not choose API/Console billing. Disable provider-account extra usage/top-ups when you need subscription-only spending. Council cannot enforce account billing settings.

In PowerShell:

```powershell
git clone https://github.com/Roronoa-code/council.git
cd council
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\python.exe -m council install --target both
.\.venv\Scripts\python.exe -m council doctor --profile mixed
```

The explicit interpreter path avoids PowerShell activation-policy problems. The installer records that interpreter in each installed skill's local `runtime.json`; keep the virtual environment in place. It does not edit either CLI's global settings. Existing different skills are refused unless `--force` is supplied; replacements are backed up.

Restart/reload the host, then use **`$council` in Codex** or **`/council` in Claude Code**, followed by the decision. Both hosts can use their real native independent subagents. The mixed CLI workflow is best launched from Codex or a normal terminal; inside Claude, its nested-session safeguard may require the native skill path. Do not bypass that safeguard.

Native mode follows the protocol but does **not** have the CLI engine's enforced checkpoint/schema/budget machinery. With no independent workers available, the skill must disclose a single-agent structured review instead of pretending several agents ran. Generic ChatGPT/Claude web chats do not automatically inherit a local CLI login or these skills.

Linux/macOS: replace `py -3 -m venv .venv` with `python3 -m venv .venv`, and the executable path with `./.venv/bin/python`.

## Try the complete offline workflow

```powershell
.\.venv\Scripts\python.exe -m council demo
```

This uses a clearly labelled, deterministic laundry-service fixture. It exercises the actual orchestration, validation, reports and checkpoint machinery, without a model request or customer research. Its business thresholds are illustrative proposed screening rules—not proof of a successful business.

## Run a real council

```powershell
.\.venv\Scripts\python.exe -m council run "Should we prototype this feature or test the manual workflow first?" --profile mixed --mode product --depth standard --context "docs\brief.md::1:40"
```

Select a file and valid line range that actually exists. Omit `--context` for an evidence-poor first question; the result should expose uncertainty rather than invent facts. Prefer a private question file for sensitive or shell-complex input:

```powershell
.\.venv\Scripts\python.exe -m council run --question-file decision.txt --evidence evidence.json --mode technical --constraint "No target-project writes without approval" --profile mixed
```

`evidence.json` is a JSON array of records with exactly `id`, `source`, `excerpt`, `provenance` and `retrieved_at`. IDs are `E1`, `E2`, etc. See [the synthetic example](examples/evidence.json). `externally-checked` means **you/the host actually checked it**, not that Council verified it. The CLI does not browse URLs or recursively upload your repository. A host skill may gather current official sources before calling the restricted workers.

| Setting | Behaviour |
|---|---|
| `--profile mixed` | Codex believer/operator/chair; Claude skeptic/auditor |
| `--profile codex` / `claude` | That provider alone, still separate invocations |
| `--depth single` | 1 invocation; explicitly labelled baseline |
| `--depth quick` | 2 independent opinions + chair = 3 |
| `--depth standard` | 3 opinions + neutral audit + chair = 5 |
| `--depth deep` | 3 opinions + 3 fresh peer audits + chair = 7 |
| Defaults | 2 concurrent workers; 8 maximum CLI invocations; at most 1 retry per job |
| Time limits | 240 seconds per invocation; 1,200 seconds per run attempt |
| Model choice | Existing CLI default, or explicit `--codex-model` / `--claude-model` |

A CLI invocation is **not** a token, API-request or currency cap. Internal CLI retries/structured-output calls can consume additional usage. An API login, unsupported safety flag, usage limit or missing provider stops the run rather than switching to paid APIs or fake demo output.

## Reports and recovery

Each run creates `report.html` (static, escaped, no JavaScript/CDN/tracking), `report.md`, `report.json`, `handoff.md`, `state.json`, and an event ledger. Private runs default to `~/.council/runs/`; `--out` must name an empty/new directory. A run-level `.gitignore` helps prevent accidental publication. Inputs and reports remain sensitive even when their repository is public.

```powershell
.\.venv\Scripts\python.exe -m council resume "C:\Users\YOUR_NAME\.council\runs\RUN_ID"
# Only when deliberately extending an exhausted invocation allowance:
.\.venv\Scripts\python.exe -m council resume "C:\path\to\run" --additional-calls 2
```

Resume validates the original brief/configuration and completed-stage fingerprints, schemas and data hashes. It reuses only compatible results. The cumulative invocation counter never resets; explicit extensions are capped at 64 total. The whole-run timer restarts on each explicit resume. Vendor sessions are ephemeral: session IDs are audit metadata, not resumable vendor conversations. Pin model identifiers for controlled comparisons; a CLI-default model may change between runs/resumes.

`council unlock RUN` removes a lock only when its owning local process is no longer running. `council outcome RUN --result pass|fail|inconclusive --note "What actually happened"` records a **user-reported** outcome on a completed live run. It does not train a model or independently verify success.

## Verification and development

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m council schema decision
```

[GitHub Actions](https://github.com/Roronoa-code/council/actions) runs offline tests and installed-package smoke checks on Windows/Linux with Python 3.11/3.13. CI uses no model credentials and uploads no private run artifacts. A workflow definition alone is not a passed run; inspect the actual check result.

See [evaluation cases and rubric](docs/evaluation.md) for comparing a single-agent baseline with Council without confusing test-suite correctness with better advice. The project makes no measured superiority claim.

## Boundaries worth knowing

Schema/reference checks catch malformed output and unknown citations; they do **not** prove source relevance or truth. Role/provider labels are withheld during reviews, but writing style can leak identity. Worker tool restrictions and isolated temporary working directories reduce risk, but are not containment against a malicious installed CLI or administrator-managed hooks/policy. Windows file privacy inherits OS ACLs; POSIX run directories use restrictive modes. Secret detection is a defence-in-depth heuristic, not a guarantee.

The coordinator does not edit target projects, spend money, contact customers or deploy. A coding host may implement an accepted handoff only within the user's actual authorization and normal safeguards. Health, legal, financial and safety-critical decisions need qualified human review. See [SECURITY.md](SECURITY.md).
