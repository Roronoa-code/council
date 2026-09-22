"""Private run artifacts, atomic checkpoints and exclusive run ownership."""
from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path

from . import PROTOCOL_VERSION, __version__
from .config import Config
from .context import read_text, utc_now
from .schema import CouncilError, strict_json, validate_brief


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def atomic_text(path: Path, text: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return True
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION only
        if not handle:
            return ctypes.get_last_error() != 87  # Invalid PID is dead; access denied is not.
        try:
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259  # STILL_ACTIVE
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Store:
    def __init__(self, directory: Path):
        self.path = directory.expanduser().resolve()

    @classmethod
    def create(cls, directory: Path, brief: dict, config: Config, run_id: str) -> "Store":
        validate_brief(brief)
        config.validate()
        store = cls(directory)
        if store.path.exists() and any(store.path.iterdir()):
            raise CouncilError("Output directory is not empty. Choose a new directory or use council resume.")
        store.path.mkdir(parents=True, mode=0o700, exist_ok=True)
        if os.name != "nt":
            store.path.chmod(0o700)
        state = {"format_version": 1, "package_version": __version__, "protocol_version": PROTOCOL_VERSION,
                 "run_id": run_id, "created_at": utc_now(), "status": "created", "brief": brief,
                 "brief_hash": digest(brief), "config": config.to_dict(), "config_hash": digest(config.to_dict()), "calls_used": 0,
                 "budget_limit": config.max_calls, "jobs": {}, "attempts": [], "candidate_order": []}
        atomic_text(store.path / ".gitignore", "# Private council run. Do not publish inputs, logs or reports by accident.\n*\n")
        store.save(state)
        return store

    def load(self) -> dict:
        state = strict_json(read_text(self.path / "state.json", 2_000_000))
        if not isinstance(state, dict) or state.get("format_version") != 1:
            raise CouncilError("Unrecognised council run format")
        if state.get("protocol_version") != PROTOCOL_VERSION:
            raise CouncilError("Run uses a different prompt protocol. Start a new run rather than reusing incompatible stages.")
        try:
            validate_brief(state["brief"])
            Config(**state["config"]).validate()
            if state.get("config_hash") != digest(state["config"]):
                raise CouncilError("Saved configuration changed. Start a new run; use resume --additional-calls to extend its budget.")
            if state["brief_hash"] != digest(state["brief"]):
                raise CouncilError("Saved brief has changed. Start a new run to preserve provenance.")
            if not isinstance(state["jobs"], dict) or not isinstance(state["attempts"], list):
                raise CouncilError("Invalid saved job/attempt ledger")
            if type(state["calls_used"]) is not int or type(state["budget_limit"]) is not int or not 0 <= state["calls_used"] <= state["budget_limit"] <= 64:
                raise CouncilError("Invalid saved invocation budget")
        except (KeyError, TypeError) as exc:
            raise CouncilError("Incomplete or incompatible council checkpoint") from exc
        return state

    def save(self, state: dict) -> None:
        atomic_json(self.path / "state.json", state)

    def event(self, event: str, **details: object) -> None:
        with (self.path / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"time": utc_now(), "event": event, **details}, ensure_ascii=False) + "\n")

    @contextmanager
    def lock(self):
        lock_path = self.path / ".lock"
        try:
            fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            raise CouncilError("Run is locked. Wait for its owner, or use council unlock after a crashed process.") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump({"pid": os.getpid(), "host": socket.gethostname(), "created_at": utc_now()}, stream)
            yield
        finally:
            lock_path.unlink(missing_ok=True)

    def unlock(self) -> None:
        path = self.path / ".lock"
        if not path.exists():
            raise CouncilError("Run has no lock")
        lock = strict_json(read_text(path, 2000))
        if not isinstance(lock, dict) or lock.get("host") != socket.gethostname() or type(lock.get("pid")) is not int:
            raise CouncilError("Cannot safely determine this lock's owner; inspect it manually")
        if pid_alive(lock["pid"]):
            raise CouncilError("Lock owner is still running (or inaccessible). Refusing to unlock an active run.")
        path.unlink()
