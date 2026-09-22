# Working on Council

Read README.md and council/protocol.md. Codex leads mixed-provider work; Claude receives bounded independent reviews. Preserve unrelated user changes. Do not recursively invoke councils, silently change providers, introduce API-key billing, remove safety flags to get a green run, or claim a fixture is live AI.

Runtime is Python 3.11+ standard library only. Keep CLI adapters explicit and fail closed on unsupported options/auth/output. Keep first-pass opinions independent, original results immutable, budgets cumulative, reports escaped, and private run data out of Git. Council advice is not execution permission.

After edits run `python -m unittest discover -s tests -v`, an offline `python -m council demo`, and a resume check. Build/install the package when packaging or skill resources change. Keep `.agents/skills/council` and `.claude/skills/council` copies byte-identical to packaged skill.md/protocol.md. Document actual checks, failures and live-provider limitations in research/03-verification.md. Do not claim model fine-tuning or decision-quality gains without an appropriate evaluation.
