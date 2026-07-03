"""Prepare obfuscated release source for PyInstaller portable builds."""

from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
SRC_PKG = SRC_ROOT / "screen_target_clicker"
OUT_ROOT = ROOT / "build" / "release_src"
OUT_PKG = OUT_ROOT / "screen_target_clicker"


def _run_pyarmor(sources: list[Path], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "-m",
        "pyarmor.cli",
        "gen",
        "-O",
        str(output_dir),
        *[str(path) for path in sources],
    ]
    print("Obfuscating:", ", ".join(path.name for path in sources))
    subprocess.run(cmd, cwd=ROOT, check=True)


def _compile_app_bytecode_only() -> None:
    import py_compile

    app_src = SRC_PKG / "app.py"
    if not app_src.is_file():
        raise FileNotFoundError(
            f"Missing {app_src}. Keep readable source in src/ for local development."
        )

    OUT_PKG.mkdir(parents=True, exist_ok=True)
    staged = OUT_PKG / "app.py"
    shutil.copy2(app_src, staged)

    cache_dir = OUT_PKG / "__pycache__"
    cache_dir.mkdir(exist_ok=True)
    tag = f"app.cpython-{sys.version_info.major}{sys.version_info.minor}.pyc"
    target = cache_dir / tag
    py_compile.compile(staged, cfile=str(target), optimize=2, doraise=True)
    staged.unlink()
    print("Compiled app.py to optimized bytecode (source not included).")


def _ensure_package_init() -> None:
    init_path = OUT_PKG / "__init__.py"
    if not init_path.exists():
        init_path.write_text("", encoding="utf-8")


def prepare() -> Path:
    if not SRC_PKG.is_dir():
        raise SystemExit(
            "src/screen_target_clicker/ not found. "
            "Develop locally in src/ — it is not pushed to GitHub."
        )

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    obfuscate_targets = sorted(
        path for path in SRC_PKG.glob("*.py") if path.name != "app.py"
    )
    if not obfuscate_targets:
        raise RuntimeError("No modules found to obfuscate.")

    _run_pyarmor(obfuscate_targets, OUT_PKG)
    _compile_app_bytecode_only()
    _ensure_package_init()
    _run_pyarmor([SRC_ROOT / "main.py"], OUT_ROOT)

    print(f"Release source ready: {OUT_ROOT}")
    return OUT_ROOT


if __name__ == "__main__":
    prepare()
