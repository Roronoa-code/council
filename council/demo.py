"""Clearly labelled fixtures for exercising the engine without live credentials."""
from __future__ import annotations

import copy
import threading

from .providers import ProviderError, Reply, Request

BRIEF = {
    "question": "Should a small laundry pickup service build a booking app now, or validate demand manually first?",
    "mode": "business",
    "constraints": ["Spend no money without approval", "One small reversible next step", "No customer demand has been verified"],
    "evidence": [{"id": "E1", "source": "Synthetic demo brief; not real market research",
                  "excerpt": "The illustrative operator has not interviewed customers, measured route cost or accepted paid bookings. No spending budget has been approved.",
                  "provenance": "user-supplied", "retrieved_at": "2026-09-22"}],
}
TEST = {"action": "Invite five relevant households to a concrete, manually operated pilot proposal; record responses without collecting payment.",
        "metric": "Number accepting a specified pickup window and explicitly quoted, cost-checked price",
        "pass_threshold": "Proposed screening rule: at least three of five agree to a specific pilot slot; then seek approval for a small paid test, not an app build.",
        "fail_threshold": "Zero accept: revisit the segment or proposition. One or two: inconclusive; do not scale.",
        "timebox": "One 60-minute outreach session after defining the offer",
        "cost_ceiling": "No paid spend; any paid pilot needs separate approval"}


def opinion(role: str) -> dict:
    summaries = {
        "believer": "Convenience might matter to busy households, but willingness to pay is still an assumption. Test a specific offer before building software.",
        "skeptic": "Demand and route economics are unverified. An app cannot repair an uneconomic service; the strongest early test is a real commitment to a concrete offer.",
        "operator": "Manual scheduling can test the workflow without software investment. Cost the route and service before quoting an offer, and cap the pilot.",
    }
    return {"position": "test", "summary": summaries[role],
            "claims": [{"claim": "The demo brief contains no verified demand or measured route economics.", "kind": "fact", "evidence_ids": ["E1"],
                        "falsifier": "Actual booking records and measured delivery/service costs would replace this absence of evidence."}],
            "risks": [{"risk": "Stated interest may not translate into paid repeat demand", "severity": "high", "evidence_ids": [],
                       "mitigation": "Separate a small commitment screen from a subsequently approved paid pilot."}],
            "unknowns": ["Actual willingness to pay", "Net contribution after collection, delivery and service cost"],
            "proposed_test": copy.deepcopy(TEST), "change_mind": ["Verified repeat demand at a positive contribution margin"]}


def decision() -> dict:
    return {"decision": "test", "recommendation": "Validate one narrow manual offer before building the booking app.",
            "rationale": [{"text": "The illustrative operator lacks verified demand, cost measurements and an approved spending budget.", "evidence_ids": ["E1"]}],
            "dissent": [{"view": "An app might make the offer easier to try.", "why_not_resolved": "No evidence shows software is the current bottleneck.",
                         "test_to_resolve": "During the manual test, record actual booking friction rather than assumed friction."}],
            "uncertainties": ["This small screen cannot establish product-market fit", "Interview interest is not paid demand"],
            "next_action": copy.deepcopy(TEST), "stop_conditions": ["Do not spend or collect payments before approval", "Do not build an app on the basis of compliments"],
            "revisit_when": ["A separately approved pilot yields real bookings, repeat behaviour and measured costs"], "evidence_strength": "low",
            "handoff": {"scope": "Prepare a one-page manual offer and response log; no software build yet.",
                        "acceptance_criteria": ["Offer has a named segment, defined service, explicit time window and cost-checked price", "Log distinguishes compliments from concrete commitments"],
                        "do_not": ["Do not spend money, message people automatically or imply market validation"]}}


class DemoProvider:
    def invoke(self, request: Request, timeout: float, cancel: threading.Event) -> Reply:
        if cancel.is_set():
            raise ProviderError("Demo cancelled")
        if request.stage == "opinion":
            data = opinion(request.role)
        elif request.stage == "review":
            data = {"critiques": [{"candidate_id": request.candidate_ids[0],
                                   "issue": "A small commitment screen is not proof of paid repeat demand.", "basis": "logical_gap", "evidence_ids": [],
                                   "would_change_decision": False}] if request.candidate_ids else [],
                    "strongest_counterargument": "Even a popular offer may lose money once route costs are measured.",
                    "unresolved": ["Demand and unit economics still need real-world validation"]}
        else:
            data = decision()
        return Reply(data, {"provider": "demo", "simulated": True, "session_id": None,
                            "duration_seconds": 0, "usage": {}, "warning": "Fixture, not a live AI response"})
