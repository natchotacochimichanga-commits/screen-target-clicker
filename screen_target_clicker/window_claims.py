"""Cross-process claims so each target window is used by one instance."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

CLAIM_DIR = Path(tempfile.gettempdir()) / "screen-target-clicker" / "claims"


@dataclass(frozen=True)
class WindowClaim:
    pid: int
    hwnd: int
    title: str
    instance: int


def _claim_path(pid: int) -> Path:
    return CLAIM_DIR / f"{pid}.json"


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION, False, pid
    )
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    return False


def cleanup_stale_claims() -> None:
    CLAIM_DIR.mkdir(parents=True, exist_ok=True)
    for path in CLAIM_DIR.glob("*.json"):
        try:
            pid = int(path.stem)
        except ValueError:
            path.unlink(missing_ok=True)
            continue
        if not _is_process_alive(pid):
            path.unlink(missing_ok=True)


def read_all_claims() -> list[WindowClaim]:
    cleanup_stale_claims()
    claims: list[WindowClaim] = []
    for path in CLAIM_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            claims.append(
                WindowClaim(
                    pid=int(data["pid"]),
                    hwnd=int(data["hwnd"]),
                    title=str(data.get("title", "")),
                    instance=int(data.get("instance", 1)),
                )
            )
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
            path.unlink(missing_ok=True)
    return claims


def get_blocked_hwnds(*, exclude_pid: int | None = None) -> set[int]:
    blocked: set[int] = set()
    for claim in read_all_claims():
        if exclude_pid is not None and claim.pid == exclude_pid:
            continue
        if _is_process_alive(claim.pid):
            blocked.add(claim.hwnd)
    return blocked


def claim_window(
    pid: int,
    hwnd: int,
    title: str,
    instance: int,
) -> tuple[bool, str | None]:
    """Reserve a window for this process. Returns (ok, blocking_instance_label)."""
    cleanup_stale_claims()
    for claim in read_all_claims():
        if claim.pid == pid:
            continue
        if claim.hwnd == hwnd and _is_process_alive(claim.pid):
            label = f"instance {claim.instance}"
            if claim.title:
                label = f"{claim.title} ({label})"
            return False, label

    CLAIM_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": pid,
        "hwnd": hwnd,
        "title": title,
        "instance": instance,
    }
    _claim_path(pid).write_text(json.dumps(payload), encoding="utf-8")
    return True, None


def release_claim(pid: int | None = None) -> None:
    target_pid = os.getpid() if pid is None else pid
    _claim_path(target_pid).unlink(missing_ok=True)


def current_claim(pid: int | None = None) -> WindowClaim | None:
    target_pid = os.getpid() if pid is None else pid
    path = _claim_path(target_pid)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WindowClaim(
            pid=int(data["pid"]),
            hwnd=int(data["hwnd"]),
            title=str(data.get("title", "")),
            instance=int(data.get("instance", 1)),
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        path.unlink(missing_ok=True)
        return None
