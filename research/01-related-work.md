# Related work and decisions adopted

Reviewed 2026-09-22. These sources informed the architecture; their results are not results achieved by this repository. No third-party implementation code was copied.

## 1. A production multi-agent research system

Source: Anthropic, [How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system), 2025-06-13.

**Reported outcome:** Anthropic reports that its multi-agent research system outperformed its single-agent baseline by 90.2% on an internal research evaluation. This is evidence for a particular research workflow, not a general guarantee about coding, business advice, or this Council. The article also describes substantially greater token consumption and difficulties parallelising tightly coupled tasks.

**Adopted:** independent context windows; explicit task boundaries; an orchestrator; saved intermediate results; traceable tool failures; effort limits; automated and human evaluation. **Rejected:** assuming that more agents are always better, or that a high benchmark score validates a real business decision.

## 2. Simple workflows before elaborate autonomous agents

Source: Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents).

**Evidence type:** engineering guidance and deployed-workflow experience, not a controlled evaluation of this project.

**Adopted:** a small fixed workflow with an optional extra audit round, rather than recursive delegation. Quick, standard, deep and single-agent-baseline modes make the complexity and usage cost explicit. A decision tool should produce a bounded next action, not create an uncontrolled implementation swarm.

## 3. LLM Council

Source: Andrej Karpathy, [llm-council](https://github.com/karpathy/llm-council).

**Demonstrated mechanism:** independent first responses, peer review with identities withheld, then a chair's synthesis. The author describes it as a weekend project; this is not evidence of maintained production reliability or superior commercial decisions.

**Adopted:** independent proposals and identity-reduced review. **Changed:** no provider popularity vote; preserve dissent; require evidence references and explicit next-test thresholds. Its OpenRouter/API billing architecture is not used: this project invokes locally authenticated Codex and Claude Code CLIs instead.

## 4. A native council skill

Source: [tenfoldmarc/llm-council-skill](https://github.com/tenfoldmarc/llm-council-skill).

**Demonstrated mechanism:** role-based independent advisers, neutral framing, peer challenge, synthesis and durable reports. Its five-role vocabulary resembles the terminal footage in the supplied video, but the video does not establish that it is the same source project.

**Adopted:** installable native skill and context-aware decision framing. **Changed:** support both hosts; distinguish native orchestration from the deterministic CLI engine; make degraded single-context operation explicit. No controlled outcome improvement is claimed for this source.

## 5. Debate can worsen answers

Sources: [Free-MAD: Consensus-Free Multi-Agent Debate](https://arxiv.org/abs/2509.11035), 2025; [Demystifying Multi-Agent Debate: The Role of Confidence and Diversity](https://arxiv.org/abs/2601.19921), 2026.

**Reported findings:** these studies investigate conformity, loss of useful diversity and cases where debate does not outperform simpler aggregation. They evaluate specific model/benchmark setups, not this repository or real-world business outcomes.

**Adopted:** immutable independent first passes, a bounded challenge round, no forced consensus, explicit unresolved dissent, and a single-agent baseline. Self-reported confidence is not a calibrated probability; Council reports qualitative evidence strength instead. The operator's next experiment matters more than whether three personas agree.

## 6. Provider contracts, not invented interfaces

Official documentation checked during implementation:

- [Codex non-interactive execution](https://developers.openai.com/codex/noninteractive): `codex exec`, JSONL events, output schema, final-message file, ephemeral execution.
- [Codex configuration](https://developers.openai.com/codex/config-reference) and [security](https://developers.openai.com/codex/security): saved ChatGPT authentication, read-only sandbox, explicit permission and tool restrictions.
- [Codex skills](https://developers.openai.com/codex/skills): `.agents/skills` discovery.
- [Claude Code programmatic execution](https://code.claude.com/docs/en/headless): print mode, JSON envelope, schema-constrained structured output.
- [Claude Code CLI reference](https://code.claude.com/docs/en/cli-reference): authentication status, safe mode, tool/MCP restrictions and ephemeral sessions.
- [Claude Code skills](https://code.claude.com/docs/en/skills) and [authentication](https://code.claude.com/docs/en/authentication): native skill locations and subscription login.

**Important boundary:** documented compatibility is not an authenticated live integration test. This build environment has no installed/authenticated Codex or Claude Code CLI. Offline contract tests and an end-to-end deterministic fixture can verify implementation behaviour; the owner's local `council doctor` and a small live run must verify installed-version/account compatibility. Required safety flags must fail closed rather than silently disappear on an older CLI.

## What would establish that Council is actually better?

Compare a single-agent baseline and Council on the same briefs, model versions, evidence and constraints. Blind reviewers to condition and provider. Grade evidence faithfulness, constraint satisfaction, dissent quality, action specificity and realised outcomes; record total invocations, tokens and time. Include negative cases where the correct answer is stop/defer or a cheap manual test. Do not tune and evaluate on the same examples. Ship measured engineering reliability separately from any unproven decision-quality claim.
