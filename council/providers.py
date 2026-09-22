"""Subscription CLI adapters. No HTTP/API client, shell execution, or key fallback."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import CouncilError, ValidationError, strict_json


class ProviderError(CouncilError):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Request:
    prompt: str
    schema: dict
    stage: str
    role: str
    candidate_ids: tuple[str, ...] = ()


@dataclass
class Reply:
    data: dict
    meta: dict


@dataclass
class ProcessResult:
    stdout: str
    stderr: str
    returncode: int
    elapsed: float


def child_environment(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN",
                "OPENAI_BASE_URL", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
                "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CODE_USE_FOUNDRY",
                "AWS_BEARER_TOKEN_BEDROCK"):
        env.pop(key, None)
    # Do not bypass Claude's nested-session guard (CLAUDECODE).
    env.update({"COUNCIL_WORKER": "1", "NO_COLOR": "1", "PYTHONIOENCODING": "utf-8"})
    return env


def executable(name: str, *, windows: bool | None = None) -> list[str]:
    target = os.environ.get(f"COUNCIL_{name.upper()}_BIN", name)
    found = shutil.which(target)
    if not found:
        raise ProviderError(f"{name} CLI not found. Install its official CLI and sign in using your subscription.")
    path = Path(found).absolute()
    is_windows = os.name == "nt" if windows is None else windows
    if is_windows and path.suffix.lower() in {".cmd", ".bat", ".ps1"}:
        # Never feed model data to cmd.exe/PowerShell. Bypass only a known npm shim,
        # by launching the installed JavaScript entry point through node directly.
        entry = {"codex": Path("@openai/codex/bin/codex.js"),
                 "claude": Path("@anthropic-ai/claude-code/cli.js")}[name]
        script = path.parent / "node_modules" / entry
        node = shutil.which("node")
        if not script.is_file() or not node:
            raise ProviderError(f"Unsupported {name} shell shim. Install the native CLI or the official npm package with node on PATH.")
        return [node, str(script)]
    return [str(path)]


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
        try:
            subprocess.run([str(taskkill), "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
        except (OSError, subprocess.TimeoutExpired):
            proc.kill()
    else:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            pass
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


class ProcessRunner:
    """Bounded output and process-tree cancellation, using real subprocesses."""
    def run(self, args: list[str], stdin: str, cwd: Path, timeout: float,
            cancel: threading.Event, env: dict[str, str] | None = None) -> ProcessResult:
        if timeout <= 0 or cancel.is_set():
            raise ProviderError("Council was cancelled or its deadline expired")
        if len(stdin.encode("utf-8")) > 200000:
            raise ProviderError("Generated prompt exceeds the 200 KB safety limit")
        input_path, out_path, err_path = [cwd / n for n in ("stdin.txt", "stdout.txt", "stderr.txt")]
        input_path.write_text(stdin, encoding="utf-8")
        started = time.monotonic()
        opts = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        with input_path.open("rb") as source, out_path.open("wb") as out, err_path.open("wb") as err:
            try:
                proc = subprocess.Popen(args, stdin=source, stdout=out, stderr=err, cwd=cwd,
                                        env=child_environment() if env is None else env, shell=False, **opts)
            except OSError as exc:
                raise ProviderError("Could not start the CLI executable; check its installation") from exc
            try:
                while proc.poll() is None:
                    if cancel.wait(0.05):
                        raise ProviderError("Council cancelled")
                    if time.monotonic() - started >= timeout:
                        raise ProviderError("CLI timed out; completed council stages remain resumable", retryable=True)
                    if out_path.stat().st_size > 2_000_000 or err_path.stat().st_size > 500_000:
                        raise ProviderError("CLI output exceeded the safety limit")
                if out_path.stat().st_size > 2_000_000 or err_path.stat().st_size > 500_000:
                    raise ProviderError("CLI output exceeded the safety limit")
            except BaseException:
                _terminate(proc)
                raise
        return ProcessResult(out_path.read_text(encoding="utf-8", errors="replace"),
                             err_path.read_text(encoding="utf-8", errors="replace"),
                             proc.returncode, round(time.monotonic() - started, 3))


def _failure(raw: str) -> ProviderError:
    text = raw.lower()
    if any(s in text for s in ("rate limit", "usage limit", "quota", "credit", "billing", "429")):
        return ProviderError("Provider usage/rate limit reached. No API, paid-credit or demo fallback was attempted.")
    if any(s in text for s in ("login", "log in", "sign in", "unauthorized", "authentication", "401")):
        return ProviderError("Provider authentication failed. Sign in to the official CLI with your subscription.")
    if "nested" in text or "claudecode" in text:
        return ProviderError("Claude blocked a nested CLI session. Use the native /council skill inside Claude, or run the CLI from a normal terminal.")
    if any(s in text for s in ("unknown option", "unrecognized", "unexpected argument", "invalid value", "unsupported")):
        return ProviderError("The installed CLI rejected a required option. Update the official CLI; Council will not weaken its safety flags.")
    if any(s in text for s in ("overloaded", "temporarily unavailable", "connection reset", "503", "502")):
        return ProviderError("Provider temporarily unavailable", retryable=True)
    return ProviderError("Provider did not complete successfully. Check CLI login/health; no verdict was fabricated.")


def _usage(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    return {k: v for k, v in value.items() if k in {
        "input_tokens", "output_tokens", "cached_input_tokens", "cache_read_input_tokens",
        "cache_creation_input_tokens"} and type(v) is int and v >= 0}


def parse_claude(raw: str) -> Reply:
    envelope = strict_json(raw)
    if not isinstance(envelope, dict):
        raise ValidationError("Claude returned a non-object envelope")
    if envelope.get("is_error") or str(envelope.get("subtype", "")).startswith("error"):
        raise _failure(json.dumps(envelope))
    if "structured_output" in envelope:
        data = envelope["structured_output"]
    elif isinstance(envelope.get("result"), str):
        data = strict_json(envelope["result"])
    else:
        raise ValidationError("Claude returned no structured_output or JSON result")
    if not isinstance(data, dict):
        raise ValidationError("Claude structured output is not an object")
    sid = envelope.get("session_id")
    return Reply(data, {"session_id": sid if isinstance(sid, str) else None,
                        "usage": _usage(envelope.get("usage")),
                        "reported_models": list(envelope.get("modelUsage", {})) if isinstance(envelope.get("modelUsage"), dict) else []})


def parse_codex(raw: str, final: str | None) -> Reply:
    sid, usage, last = None, {}, None
    for line in raw.splitlines():
        if not line.strip():
            continue
        event = strict_json(line)
        if not isinstance(event, dict):
            raise ValidationError("Codex emitted a non-object JSON event")
        if event.get("type") in {"error", "turn.failed"}:
            raise _failure(json.dumps(event))
        if event.get("type") == "thread.started":
            sid = event.get("thread_id")
        if event.get("type") == "turn.completed":
            usage = _usage(event.get("usage"))
        item = event.get("item", {})
        if event.get("type") == "item.completed" and isinstance(item, dict) and item.get("type") == "agent_message":
            last = item.get("text")
    response = final if final and final.strip() else last
    if not isinstance(response, str):
        raise ValidationError("Codex returned no final agent message")
    data = strict_json(response)
    if not isinstance(data, dict):
        raise ValidationError("Codex final output is not an object")
    return Reply(data, {"session_id": sid if isinstance(sid, str) else None, "usage": usage})


def codex_overrides(config_paths: list[Path] | None = None) -> list[str]:
    settings = ['forced_login_method="chatgpt"', 'model_provider="openai"', 'approval_policy="never"',
                'web_search="disabled"', 'hide_agent_reasoning=true', 'mcp_servers={}']
    for feature in ("shell_tool", "unified_exec", "multi_agent", "hooks", "memories", "apps", "plugins", "remote_plugin", "skill_mcp_dependency_install"):
        settings.append(f"features.{feature}=false")
    if config_paths is None:
        config_paths = [Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "config.toml",
                        Path("/etc/codex/config.toml")]
    names: set[str] = set()

    def collect(value: dict) -> None:
        for key, item in value.items():
            if key == "mcp_servers" and isinstance(item, dict):
                names.update(item)
            elif isinstance(item, dict):
                collect(item)

    for path in config_paths:
        if path.is_file():
            try:
                with path.open("rb") as stream:
                    collect(tomllib.load(stream))
            except (OSError, ValueError, RecursionError) as exc:
                raise ProviderError("Cannot read Codex configuration safely; check its TOML syntax") from exc
    # Explicit leaf overrides also handle installations that merge empty tables.
    settings.extend(f"mcp_servers.{json.dumps(name)}.enabled=false" for name in sorted(names))
    return [part for setting in settings for part in ("-c", setting)]


class CLIProvider:
    def __init__(self, name: str, model: str | None = None, runner: ProcessRunner | None = None):
        if name not in {"codex", "claude"}:
            raise CouncilError("Unsupported live provider")
        self.name, self.model = name, model
        self.runner = runner or ProcessRunner()
        self.command: list[str] | None = None
        self.version = "not-probed"
        self.ready = False
        self._auth_lock = threading.Lock()

    def command_for(self, request: Request, directory: Path) -> list[str]:
        prefix = self.command or executable(self.name)
        schema = json.dumps(request.schema, separators=(",", ":"))
        if self.name == "codex":
            (directory / "schema.json").write_text(schema, encoding="utf-8")
            args = prefix + codex_overrides() + ["exec", "--sandbox", "read-only", "--skip-git-repo-check",
                    "--ephemeral", "--json", "--output-schema", str(directory / "schema.json"),
                    "--output-last-message", str(directory / "final.json")]
            if self.model:
                args += ["--model", self.model]
            return args + ["-"]
        args = prefix + ["-p", "--safe-mode", "--output-format", "json", "--json-schema", schema,
                         "--tools", "", "--disallowedTools", "mcp__*", "--strict-mcp-config",
                         "--mcp-config", '{"mcpServers":{}}', "--disable-slash-commands",
                         "--permission-mode", "dontAsk", "--no-session-persistence", "--max-turns", "4"]
        if self.model:
            args += ["--model", self.model]
        return args

    def invoke(self, request: Request, timeout: float, cancel: threading.Event) -> Reply:
        with self._auth_lock:
            if not self.ready:
                status = self.doctor()
                if not status["ready"]:
                    raise ProviderError(status["message"])
        # A separate temporary working directory prevents project configuration and
        # workspace writes. Existing official CLI authentication is left in place.
        with tempfile.TemporaryDirectory(prefix="council-worker-") as temp:
            directory = Path(temp)
            result = self.runner.run(self.command_for(request, directory), request.prompt, directory, timeout, cancel)
            if result.returncode:
                raise _failure(result.stderr + "\n" + result.stdout)
            final_path = directory / "final.json"
            if final_path.exists() and final_path.stat().st_size > 250000:
                raise ProviderError("Codex final output exceeded the safety limit")
            reply = parse_codex(result.stdout, final_path.read_text(encoding="utf-8") if final_path.exists() else None) if self.name == "codex" else parse_claude(result.stdout)
            reply.meta.update({"provider": self.name, "cli_version": self.version, "model_requested": self.model,
                               "duration_seconds": result.elapsed, "simulated": False})
            return reply

    def doctor(self) -> dict:
        self.ready = False
        result = {"provider": self.name, "installed": False, "subscription_auth": False, "ready": False}
        try:
            self.command = executable(self.name)
            result["installed"] = True
            with tempfile.TemporaryDirectory(prefix="council-probe-") as temp:
                directory = Path(temp)
                version = self.runner.run(self.command + ["--version"], "", directory, 20, threading.Event())
                if version.returncode:
                    raise ProviderError("CLI version check failed")
                self.version = (version.stdout.strip() or version.stderr.strip())[:160]
                result["version"] = self.version
                command = self.command + (["login", "status"] if self.name == "codex" else ["auth", "status"])
                auth = self.runner.run(command, "", directory, 20, threading.Event())
                if self.name == "codex":
                    ok = auth.returncode == 0 and bool(re.search(r"^Logged in (?:using|with) ChatGPT(?:\s|\.|$)", auth.stdout + "\n" + auth.stderr, re.I | re.M))
                else:
                    status = strict_json(auth.stdout) if auth.stdout.strip() else {}
                    if not isinstance(status, dict):
                        raise ProviderError("CLI authentication status is not a recognised object")
                    method = str(status.get("authMethod", "")).lower()
                    subscription = str(status.get("subscriptionType", "")).lower()
                    ok = auth.returncode == 0 and status.get("loggedIn") is True and (method in {"claude.ai", "claudeai"} or (method == "oauth" and subscription in {"pro", "max", "team", "enterprise"}))
                result["subscription_auth"] = ok
                result["ready"] = ok
                self.ready = ok
                result["message"] = "Subscription login detected; this probe made no model request." if ok else "No recognised subscription login. Sign in with the official CLI; API authentication is not accepted."
        except CouncilError as exc:
            result["message"] = str(exc)
        result["billing_note"] = "Council does not enable extra usage. Disable provider-account extra usage/automatic top-ups to avoid charges beyond your subscription."
        return result
