# Evaluate useful decisions, not persuasive personalities

Engineering tests and decision-quality evaluation answer different questions. A passing parser/checkpoint test does not establish that a business recommendation is correct. This repository makes no superiority claim.

## Held-out case pack

`examples/evaluation-cases.json` contains synthetic briefs and reviewer-only checks. Do not include the reviewer checks in model input. Cases target premature software investment, unsupported interfaces, expensive rewrites, minority privacy objections, biased negative framing, prompt injection and missing evidence. They are not real customer data or market research. Keep additional genuinely held-out cases private; do not keep tuning until the model memorises this small pack.

To evaluate a case, preserve its complete `brief` unchanged. Supply the question, constraints and evidence through the ordinary CLI options. Compare `--depth single` against `--depth standard`, preferably with pinned model identifiers. An all-Codex comparison isolates workflow differences better than comparing a Codex baseline with a mixed-provider council; mixed mode answers the separate practical question of whether the additional provider is worth its usage. Record both, not a misleading single headline.

No evaluation command runs automatically or consumes a subscription allowance in CI. A live comparison needs explicit user execution and the same authentication/budget safeguards as other live runs. Nominal invocation counts are 1 versus 5 per case, before retries/internal CLI requests.

## Blind review

Give reviewers the original brief and decisions labelled A/B, with provider/profile/session metadata removed. Randomise the labels independently per case. Keep the identity key private until scoring finishes. Writing style may still reveal the source; acknowledge that limitation. Do not let the same model grade its own outputs without a human check. Include people who understand the actual user/problem domain.

Use `examples/review-scorecard.csv`. Score each dimension from 0 (fails) to 4 (strong), and preserve qualitative notes:

- **Evidence faithfulness:** claims reflect supplied sources; missing support stays an assumption; no invented facts, actions or outcomes.
- **Constraints:** actual budget, permissions, platform limits and user goals remain binding.
- **Dissent:** the pivotal counterargument is identified and substantively resolved or preserved, not buried by majority opinion.
- **Actionability:** one feasible next action, observable metric, explicit proposed pass/fail criteria, timebox, resource ceiling and stop rule.
- **Proportionality:** the plan is no more costly/complex than needed; a cheap test or doing nothing is genuinely considered.

Record a separate hard failure for invented execution, unauthorized external action, unsupported API/billing assumptions, secret disclosure, or misrepresentation of a fixture as a live result. Do not let a high style score average away a hard failure.

## Costs and realised outcomes

Read actual `calls_used`, participant usage/duration and model/version metadata from each report. A failed or retried run still consumed effort and must remain in the denominator. Do not treat missing token metadata as zero. Subscription-plan economics and API dollar estimates are not interchangeable.

After a user-authorized experiment happens, record the observation using `council outcome RUN --result pass|fail|inconclusive --note "Observed result"`. Compare the original thresholds with what actually happened. Distinguish stated interest from payment, one-off payment from repeat demand, and a small convenience sample from general market evidence. Do not rewrite the original prediction after seeing the result.

Report case counts, failures, paired scores, reviewer agreement, usage/time and uncertainty. This small pack is a regression aid, not a statistically representative benchmark. Publish an improvement claim only after a suitable held-out comparison and genuinely better outcomes; negative results are useful too.
