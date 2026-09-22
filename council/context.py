"""Explicit, bounded context intake. Never recursively uploads a repository."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

from .schema import BRIEF, EVIDENCE, CouncilError, strict_json, validate, validate_brief

SECRET = re.compile(r"(?:sk-(?:proj-|ant-|or-)?[A-Za-z0-9_-]{20,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{20,})", re.I)
DENIED_PARTS = {".ssh", ".aws", ".gnupg", ".kube"}
DENIED_NAMES = {"auth.json", ".credentials.json", "credentials.json", "credentials", "id_rsa", "id_ed25519"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def check_secrets(text: str) -> None:
    if SECRET.search(text):
        raise CouncilError("Input appears to contain a credential/private key. Remove it before sending context.")


def read_text(path: Path, limit: int = 1_000_000) -> str:
    if not path.is_file():
        raise CouncilError(f"Not a regular file: {path.name}")
    # Read at most limit+1, even if another process grows the file while it is read.
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise CouncilError(f"File too large: {path.name}; select a smaller excerpt")
    try:
        result = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise CouncilError(f"Expected UTF-8 text: {path.name}") from exc
    if "\x00" in result:
        raise CouncilError(f"Binary input is not supported: {path.name}")
    return result


def evidence_file(path: Path) -> list[dict]:
    data = strict_json(read_text(path, 48000))
    if not isinstance(data, list) or len(data) > 20:
        raise CouncilError("Evidence file must contain a JSON array of at most 20 evidence records")
    for item in data:
        validate(item, EVIDENCE)
    return data


def context_record(spec: str, evidence_id: str) -> dict:
    """Accept file.py or file.py::10:40; the delimiter also works with C:\\ paths."""
    name, sep, selection = spec.rpartition("::")
    if not sep:
        name, selection = spec, ""
    path = Path(name).expanduser().resolve()
    parts = {part.lower() for part in path.parts}
    if parts & DENIED_PARTS or path.name.lower() in DENIED_NAMES or path.name.lower().startswith(".env") or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        raise CouncilError("Credential/configuration files cannot be attached as council evidence")
    body = read_text(path)
    lines = body.splitlines()
    first, last = 1, len(lines)
    if selection:
        match = re.fullmatch(r"([1-9][0-9]*):([1-9][0-9]*)", selection)
        if not match:
            raise CouncilError("Line selection must look like file.py::10:40")
        first, last = map(int, match.groups())
        if first > last or last > len(lines):
            raise CouncilError("Line selection is outside the file")
    excerpt = "\n".join(lines[first - 1:last])
    if not excerpt.strip() or len(excerpt) > 16000:
        raise CouncilError("Context excerpt must contain 1–16,000 characters; select a narrower line range")
    check_secrets(excerpt)
    digest = hashlib.sha256(excerpt.encode()).hexdigest()
    return {"id": evidence_id, "source": f"file:{path.name}#L{first}-L{last}; sha256:{digest}",
            "excerpt": excerpt, "provenance": "locally-read", "retrieved_at": utc_now()}


def build_brief(question: str, mode: str, constraints: list[str], contexts: list[str], evidence: list[dict]) -> dict:
    evidence = [dict(e) for e in evidence]
    used = {e["id"] for e in evidence}
    for spec in contexts:
        index = 1
        while f"E{index}" in used:
            index += 1
        eid = f"E{index}"
        evidence.append(context_record(spec, eid))
        used.add(eid)
    brief = {"question": question.strip(), "mode": mode, "constraints": constraints, "evidence": evidence}
    validate_brief(brief)
    import json
    check_secrets(json.dumps(brief))
    return brief
