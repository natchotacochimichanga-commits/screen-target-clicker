"""Sync obfuscated app code to repo root and remove non-app clutter for GitHub."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Paths removed from the public repo (website, old publish helpers, CI for site).
REMOVE_PATHS = (
    ROOT / "website",
    ROOT / ".github",
    ROOT / "publish-to-github.bat",
)

REMOVE_RUNTIME_AT_ROOT = ROOT / "pyarmor_runtime_000000"


def _replace_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def sync() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "prepare_release",
        ROOT / "scripts" / "prepare_release.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load prepare_release.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    release_src = module.prepare()

    pkg_src = release_src / "screen_target_clicker"
    pkg_dest = ROOT / "screen_target_clicker"
    _replace_tree(pkg_src, pkg_dest)

    shutil.copy2(release_src / "main.py", ROOT / "main.py")

    runtime_src = release_src / "pyarmor_runtime_000000"
    if runtime_src.is_dir():
        _replace_tree(runtime_src, REMOVE_RUNTIME_AT_ROOT)

    for path in REMOVE_PATHS:
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"Removed: {path.relative_to(ROOT)}")

    print("GitHub tree updated with obfuscated app code only.")
    print("Next: git add -A && git commit && git push")


def git_add_protected_files() -> None:
    """Stage binary artifacts that .gitignore would otherwise skip."""
    import subprocess

    protected = [
        ROOT / "pyarmor_runtime_000000" / "pyarmor_runtime.pyd",
        ROOT / "screen_target_clicker" / "pyarmor_runtime_000000" / "pyarmor_runtime.pyd",
    ]
    cache = ROOT / "screen_target_clicker" / "__pycache__"
    if cache.is_dir():
        protected.extend(cache.glob("app.*.pyc"))

    for path in protected:
        if path.is_file():
            subprocess.run(["git", "add", "-f", str(path)], cwd=ROOT, check=True)


if __name__ == "__main__":
    sync()
    git_add_protected_files()
