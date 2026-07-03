"""Remove non-runtime files from a PyInstaller onedir build."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _dir_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def prune(root: Path) -> None:
    internal = root / "_internal"
    if not internal.is_dir():
        raise SystemExit(f"Expected PyInstaller folder with _internal: {root}")

    removed = 0

    for folder in list(internal.rglob("*.dist-info")):
        if folder.is_dir():
            removed += _dir_size(folder)
            shutil.rmtree(folder)

    for folder in list(internal.rglob("licenses")):
        if folder.is_dir() and "numpy" in str(folder).lower():
            removed += _dir_size(folder)
            shutil.rmtree(folder)

    tcl8 = internal / "tcl8"
    if tcl8.is_dir():
        for pattern in ("tcltest-*.tm", "msgcat-*.tm", "http-*.tm"):
            for path in tcl8.rglob(pattern):
                removed += path.stat().st_size
                path.unlink()

    for path in list(internal.rglob("__pycache__")):
        if path.is_dir():
            removed += _dir_size(path)
            shutil.rmtree(path)

    print(f"Pruned ~{removed / (1024 * 1024):.1f} MB from {root}")


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/ScreenTargetClicker")
    prune(target)
