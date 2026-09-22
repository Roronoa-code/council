"""Small, deliberately closed schema vocabulary. No coercion or JSON extraction guesses.

The same JSON Schemas are sent to both CLIs and validated locally. This validator
implements ONLY the vocabulary generated below, not arbitrary JSON Schema.
"""
from __future__ import annotations

import json
import re
from typing import Any


class CouncilError(Exception):
    """An actionable, safe-to-display operational error."""


class ValidationError(CouncilError):
    pass


def text(limit: int = 900) -> dict:
    return {"type": "string", "minLength": 1, "maxLength": limit}


def enum(*values: str) -> dict:
    return {"type": "string", "enum": list(values)}


def array(items: dict, maximum: int = 5, minimum: int = 0) -> dict:
    return {"type": "array", "items": items, "minItems": minimum, "maxItems": maximum}


def obj(**properties: dict) -> dict:
    return {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}


POSITION = enum("proceed", "test", "revise", "stop", "defer")
REFS = array(text(40), 8)
TEST = obj(action=text(), metric=text(400), pass_threshold=text(400),
           fail_threshold=text(400), timebox=text(200), cost_ceiling=text(200))
CLAIM = obj(claim=text(), kind=enum("fact", "inference", "assumption"),
            evidence_ids=REFS, falsifier=text(600))
OPINION = obj(position=POSITION, summary=text(), claims=array(CLAIM, 5, 1),
              risks=array(obj(risk=text(600), severity=enum("low", "medium", "high", "critical"),
                              evidence_ids=REFS, mitigation=text(600)), 4),
              unknowns=array(text(400), 5), proposed_test=TEST,
              change_mind=array(text(400), 3, 1))
REVIEW = obj(critiques=array(obj(candidate_id=text(8), issue=text(600),
                                basis=enum("evidence", "logical_gap", "assumption"),
                                evidence_ids=REFS, would_change_decision={"type": "boolean"}), 6),
             strongest_counterargument=text(), unresolved=array(text(400), 5))
DECISION = obj(decision=POSITION, recommendation=text(),
               rationale=array(obj(text=text(600), evidence_ids=REFS), 4, 1),
               dissent=array(obj(view=text(600), why_not_resolved=text(600),
                                 test_to_resolve=text(600)), 3),
               uncertainties=array(text(400), 5), next_action=TEST,
               stop_conditions=array(text(400), 4, 1),
               revisit_when=array(text(400), 3, 1),
               evidence_strength=enum("low", "medium", "high"),
               handoff=obj(scope=text(), acceptance_criteria=array(text(400), 5, 1),
                           do_not=array(text(400), 5, 1)))
EVIDENCE = obj(id=text(40), source=text(1000), excerpt=text(16000),
               provenance=enum("user-supplied", "locally-read", "externally-checked"),
               retrieved_at=text(80))
BRIEF = obj(question=text(16000), mode=enum("business", "product", "technical", "general"),
            constraints=array(text(600), 12), evidence=array(EVIDENCE, 20))
SCHEMAS = {"opinion": OPINION, "review": REVIEW, "decision": DECISION, "brief": BRIEF}


def validate(value: Any, schema: dict, path: str = "$", depth: int = 0) -> None:
    if depth > 32:
        raise ValidationError(f"{path}: nested too deeply")
    kind = schema["type"]
    types = {"object": dict, "array": list, "string": str, "boolean": bool}
    if kind not in types or type(value) is not types[kind]:
        raise ValidationError(f"{path}: expected {kind}")
    if "enum" in schema and value not in schema["enum"]:
        raise ValidationError(f"{path}: must be one of {schema['enum']}")
    if kind == "object":
        missing = set(schema["required"]) - set(value)
        extra = set(value) - set(schema["properties"])
        if missing or extra:
            raise ValidationError(f"{path}: missing {sorted(missing)}; unexpected {sorted(extra)}")
        for key, item in value.items():
            validate(item, schema["properties"][key], f"{path}.{key}", depth + 1)
    elif kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", 100):
            raise ValidationError(f"{path}: array length outside allowed range")
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{path}[{i}]", depth + 1)
    elif kind == "string":
        if not value.strip() or not schema.get("minLength", 1) <= len(value) <= schema.get("maxLength", 100000):
            raise ValidationError(f"{path}: blank or oversized text")
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValidationError(f"{path}: disallowed control character")


def strict_json(raw: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        out = {}
        for key, value in items:
            if key in out:
                raise ValidationError(f"Duplicate JSON key: {key}")
            out[key] = value
        return out

    def invalid_constant(_: str) -> None:
        raise ValidationError("Non-finite JSON number")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, RecursionError) as exc:
        raise ValidationError("Expected one complete JSON value, without fences or commentary") from exc


def validate_brief(brief: dict) -> None:
    validate(brief, BRIEF)
    ids = [e["id"] for e in brief["evidence"]]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"E[0-9]{1,4}", i) for i in ids):
        raise ValidationError("Evidence IDs must be unique E1, E2, ...")
    if len(json.dumps(brief, ensure_ascii=False).encode("utf-8")) > 48000:
        raise ValidationError("Brief exceeds 48 KB. Select smaller, relevant excerpts; nothing was truncated.")


def validate_result(data: dict, stage: str, evidence_ids: set[str], candidates: set[str] | None = None) -> None:
    validate(data, SCHEMAS[stage])

    def check(value: Any) -> None:
        if isinstance(value, dict):
            if "evidence_ids" in value:
                unknown = set(value["evidence_ids"]) - evidence_ids
                if unknown:
                    raise ValidationError(f"Unknown evidence IDs: {sorted(unknown)}")
                if len(value["evidence_ids"]) != len(set(value["evidence_ids"])):
                    raise ValidationError("Duplicate evidence reference")
            if value.get("kind") == "fact" and not value.get("evidence_ids"):
                raise ValidationError("A factual claim needs an evidence ID; otherwise label it an assumption/inference")
            for item in value.values():
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    check(data)
    if stage == "review":
        for critique in data["critiques"]:
            if critique["candidate_id"] not in (candidates or set()):
                raise ValidationError("Review names a candidate it was not given")
    if stage == "decision":
        cited = {ref for r in data["rationale"] for ref in r["evidence_ids"]}
        if data["decision"] == "proceed" and not cited:
            raise ValidationError("Proceed requires a cited premise. Without it, recommend a bounded test or defer.")
        if data["evidence_strength"] == "high" and not cited:
            raise ValidationError("High evidence strength requires cited evidence")
