# Architecture decisions

2026-09-22 · Protocol 2026-09-22.1

1. **A local decision engine plus native skills, not a new web platform.** Python 3.11+ standard library avoids a backend service, external database, API-key storage and runtime package supply chain. The static HTML report is optional presentation, not an always-on app.
2. **Subscription CLIs, not provider APIs.** Codex/Claude wrappers preserve normal saved subscription authentication. A missing CLI/account/safety option stops execution. Authentication probes do not make model calls. Billing settings still belong to the provider account; zero additional charges cannot be guaranteed by counting coordinator invocations.
3. **Codex leads mixed mode.** The believer, operator and chair use Codex; skeptic and neutral auditor use Claude. Single-provider profiles still use independent invocations. Model identifiers are explicit optional inputs rather than invented future model constants.
4. **Fresh context before discussion.** First-pass workers never receive peer answers. Standard adds one fresh auditor; deep adds three fresh peer audits, each excluding its own original perspective. Original opinions remain unchanged. Candidates are assigned stable shuffled anonymous IDs, but linguistic cues mean this is not perfect blinding.
5. **Synthesis, not voting.** Evidence-linked dissent can outweigh a majority. Missing evidence favours a bounded test/defer. Qualitative evidence strength is not probability. Structural gates do not establish truth or entailment.
6. **One action, not a roadmap.** The next step includes an observable metric, proposed pass/fail rules, timebox and resource ceiling. Unknown budgets are not invented. A handoff is a proposal that a host may execute only under the user's actual authority.
7. **Bounds and durable failure semantics.** Count invocations before launching, retain failed attempts, stop on auth/quota/permanent errors, allow at most one bounded validation/transient retry per job, and cap total calls. Record successful stages atomically. Explicit resume validates schema, references, fingerprints and hashes before reuse; brief/config changes require a new run.
8. **Coordinator resume, not vendor-session resume.** Both adapters use ephemeral sessions. Session IDs are audit metadata only. Reuse Council's completed results after interruption; do not claim that a vendor chat can be resumed when persistence was disabled.
9. **Least exposure, not magical isolation.** Worker tools/customizations are restricted, evidence is explicitly selected, prompts use stdin, and subprocesses never invoke a shell with model input. Trusted CLI/administrator assumptions remain; native host mode has a different enforcement boundary and must disclose it.
10. **Reliability and decision quality are different claims.** Offline schema/process/orchestration tests can establish specific engineering behaviour. A synthetic laundry fixture cannot establish demand, clinical efficacy, business success, or superiority to one model. The evaluation pack reserves those claims for actual held-out, blinded comparisons and realised outcomes.

## Data flow

`question + bounded source excerpts → validated brief → independent opinions → optional anonymous audit(s) → chair → validated decision → private reports + bounded handoff`

The coordinator never edits the target project or executes the recommendation. It writes only its own explicitly chosen run/installation/output artifacts. Native skills gather context through host tools before invoking workers; the restricted CLI workers themselves do not browse.

## Explicitly unsupported assumptions

- No claim that the source video's negative laundry verdict was correct or commercially tested.
- No claim that the video's terminal shows the same roles described by its narration/captions.
- No claim that more agents, a more eloquent chair or unanimity improve correctness.
- No claim that built-in secret scanning prevents every disclosure.
- No claim that Windows behaviour was verified merely by writing Windows branches in the code; inspect CI results separately.
- No claim of authenticated vendor execution in an environment without installed/authenticated vendor CLIs.
- No model-weight fine-tuning and no automatic self-modification from outcome logs.
