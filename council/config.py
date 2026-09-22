from __future__ import annotations

from dataclasses import asdict, dataclass

from .schema import CouncilError

NOMINAL_CALLS = {"single": 1, "quick": 3, "standard": 5, "deep": 7}


@dataclass(frozen=True)
class Config:
    profile: str = "mixed"
    depth: str = "standard"
    parallel: int = 2
    timeout: int = 240
    run_timeout: int = 1200
    max_calls: int = 8
    retries: int = 1
    codex_model: str | None = None
    claude_model: str | None = None

    def validate(self) -> None:
        if self.profile not in {"codex", "claude", "mixed", "demo"} or self.depth not in NOMINAL_CALLS:
            raise CouncilError("Unknown provider profile or depth")
        ranges = {"parallel": (1, 3), "timeout": (1, 1800), "run_timeout": (1, 7200),
                  "max_calls": (NOMINAL_CALLS[self.depth], 32), "retries": (0, 1)}
        for key, (low, high) in ranges.items():
            value = getattr(self, key)
            if type(value) is not int or not low <= value <= high:
                raise CouncilError(f"{key} must be an integer from {low} to {high}")
        for model in (self.codex_model, self.claude_model):
            if model is not None and (not isinstance(model, str) or not model.strip() or len(model) > 120 or model.startswith("-") or any(ord(c) < 32 for c in model)):
                raise CouncilError("Invalid model identifier")

    def provider_for(self, role: str) -> str:
        if self.profile != "mixed":
            return self.profile
        # Codex is the lead/chair; Claude contributes disconfirmation and auditing.
        return "claude" if role in {"skeptic", "auditor"} else "codex"

    def model_for(self, provider: str) -> str | None:
        return self.codex_model if provider == "codex" else self.claude_model if provider == "claude" else None

    def to_dict(self) -> dict:
        return asdict(self)

    def required_providers(self) -> set[str]:
        roles = ["chair"] if self.depth == "single" else ["believer", "skeptic", "chair"]
        if self.depth in {"standard", "deep"}:
            roles += ["operator", "auditor"]
        return {self.provider_for(role) for role in roles}
