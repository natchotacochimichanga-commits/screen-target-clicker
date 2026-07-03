"""Save and load app configuration as JSON files."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .scan_region import ScanRegion

CONFIG_VERSION = 1


def config_directory() -> Path:
    base = Path(os.environ.get("APPDATA", Path.home())) / "ScreenTargetClicker"
    base.mkdir(parents=True, exist_ok=True)
    return base


def auto_config_path(instance_number: int) -> Path:
    if instance_number <= 1:
        return config_directory() / "config.json"
    return config_directory() / f"config-{instance_number}.json"


def scan_region_to_dict(region: ScanRegion | None) -> dict[str, int] | None:
    if region is None:
        return None
    return {
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
    }


def scan_region_from_dict(data: dict[str, Any] | None) -> ScanRegion | None:
    if not data:
        return None
    try:
        return ScanRegion(
            x=int(data["x"]),
            y=int(data["y"]),
            width=int(data["width"]),
            height=int(data["height"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def save_config_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_config_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Config file must contain a JSON object.")
    if data.get("version", CONFIG_VERSION) != CONFIG_VERSION:
        raise ValueError("Unsupported config file version.")
    return data


@dataclass(frozen=True)
class RuleConfig:
    primary_path: str
    subsection_path: str
    subsection_threshold: float
    scan_region: ScanRegion | None


def rule_from_dict(entry: dict[str, Any]) -> RuleConfig | None:
    try:
        return RuleConfig(
            primary_path=str(entry["primary"]),
            subsection_path=str(entry["subsection"]),
            subsection_threshold=float(entry.get("subsection_threshold", 0.85)),
            scan_region=scan_region_from_dict(entry.get("scan_region")),
        )
    except (KeyError, TypeError, ValueError):
        return None
