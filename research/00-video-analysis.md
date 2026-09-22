# Source-video analysis

Study date: 2026-09-22. Source: the owner's privately supplied 40.300-second video. Original footage is not redistributed in this public repository.

## Method and limits

The video contains 1,209 frames at 30 fps, 576 × 1024 pixels. Every frame was decoded and compared with its predecessor to locate transitions. One-second contact sheets and enlarged cut-adjacent frames were visually inspected. This is frame-indexed analysis, not a claim that every nearly identical frame was separately interpreted. There is no verified audio transcript; descriptions below refer to visible captions and screens.

## Frame-indexed observation log

| Frames (0-based) | Time | Visible mechanism | Interpretation / limitation |
|---|---|---|---|
| 0–44 | 0.00–1.47s | Laundry-service prompt, strongly negative response, warning hook | Illustration, not an evaluation showing that the advice was correct. |
| 45–102 | 1.50–3.40s | Work-at-laptop scene and introduction | Frames do not demonstrate an implementation. |
| 103–153 | 3.43–5.10s | Four visual agent avatars; 'Claude Council' | Introduces separation of perspectives. Four drawings are not proof of four independent sessions. |
| 154–211 | 5.13–7.03s | 'Laundry pickup and delivery service for busy households' | Input is underspecified: location, customer, price, costs, constraints and existing evidence are missing. |
| 212–366 | 7.07–12.20s | The Believer; strongest case, why it could work, who would buy | Keep charitable opportunity analysis, but require a falsifiable hypothesis rather than unconditional optimism. |
| 367–508 | 12.23–16.93s | The Skeptic; challenges demand and overlooked failure modes | Keep disconfirmation, but distinguish evidenced blockers from imagined risks. |
| 509–653 | 16.97–21.77s | The Investor; economics and opportunity | Useful for businesses. For software, reinterpret as delivery feasibility and resource cost, not invented revenue. |
| 654–834 | 21.80–27.80s | The Judge reads the three arguments and returns a final decision | Synthesis is useful; forced yes/no, popularity and confidence are not evidence. Preserve unresolved disagreement. |
| 835–896 | 27.83–29.87s | Contrast with asking a single chat whether the idea is good | Plausible motivation, not proof of superior decisions. |
| 897–962 | 29.90–32.07s | Terminal invokes a council skill; 'Spawning all 5 advisors'; Contrarian, First Principles, Expansionist, Outsider are visible | Important discrepancy: the actual screen is not the advertised three advisers plus judge. The fifth role and full source are not recoverable from these frames. |
| 963–1088 | 32.10–36.27s | Onboarding example and call to request 'COUNCIL' | Suggests broader product decisions, but no tests or real-world outcomes are shown. |
| 1089–1208 | 36.30–40.27s | Platform outro | No additional implementation information. |

## What to build

A local, subscription-CLI decision tool and an installable skill for both Codex and Claude Code. Independent first passes; a bounded adversarial review when requested; a judge that can recommend proceed, test, revise, stop, or defer. Every recommendation needs a smallest useful next action, success/failure thresholds, uncertainties, and conditions that would change the decision.

The tool must not pretend it trained model weights, performed live customer validation, or executed tests it only proposed. Council advice does not itself authorize file edits, spending, deployments, or external messages. Codex remains the default lead in mixed-provider mode; advisers are read-only and cannot recursively delegate.
