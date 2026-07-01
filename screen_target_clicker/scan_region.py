"""Optional rectangular crop within a captured window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .matcher import Match
    from .rules import RuleEvaluation


@dataclass(frozen=True)
class ScanRegion:
    x: int
    y: int
    width: int
    height: int

    @property
    def label(self) -> str:
        return f"x={self.x}, y={self.y}, {self.width}×{self.height}"


def apply_scan_region(
    screen: np.ndarray,
    region: ScanRegion | None,
) -> tuple[np.ndarray, int, int]:
    """Crop screen to region. Returns (cropped_image, offset_x, offset_y)."""
    if region is None:
        return screen, 0, 0

    h, w = screen.shape[:2]
    x1 = max(0, min(region.x, w - 1))
    y1 = max(0, min(region.y, h - 1))
    x2 = max(x1 + 1, min(region.x + region.width, w))
    y2 = max(y1 + 1, min(region.y + region.height, h))
    return screen[y1:y2, x1:x2].copy(), x1, y1


def annotate_scan_region(screen: np.ndarray, region: ScanRegion | None) -> np.ndarray:
    """Draw the active scan zone on a preview image."""
    if region is None:
        return screen

    out = screen.copy()
    x1, y1 = region.x, region.y
    x2, y2 = region.x + region.width, region.y + region.height
    cv2.rectangle(out, (x1, y1), (x2, y2), (255, 120, 40), 2)
    cv2.putText(
        out,
        "target zone",
        (x1 + 4, max(y1 + 18, 18)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (255, 120, 40),
        2,
        cv2.LINE_AA,
    )
    return out


def annotate_rule_scan_regions(
    screen: np.ndarray,
    rules: list,
    *,
    color: tuple[int, int, int] = (200, 80, 255),
) -> np.ndarray:
    """Draw per-rule scan zones on a preview image."""
    from .rules import ClickRule

    out = screen.copy()
    index = 0
    for rule in rules:
        if not isinstance(rule, ClickRule) or rule.scan_region is None:
            continue
        index += 1
        region = rule.scan_region
        x1, y1 = region.x, region.y
        x2, y2 = region.x + region.width, region.y + region.height
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            out,
            f"rule zone {index}",
            (x1 + 4, max(y1 + 18, 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            color,
            2,
            cv2.LINE_AA,
        )
    return out


def offset_match(match: Match, dx: int, dy: int) -> Match:
    """Shift match coordinates (e.g. from cropped scan zone to full window)."""
    from .matcher import Match

    return Match(
        target_name=match.target_name,
        confidence=match.confidence,
        center_x=match.center_x + dx,
        center_y=match.center_y + dy,
        width=match.width,
        height=match.height,
    )


def offset_rule_evaluation(
    evaluation: RuleEvaluation, dx: int, dy: int
) -> RuleEvaluation:
    """Shift rule evaluation peaks to full-window coordinates."""
    from .rules import RuleEvaluation

    primary = evaluation.primary_peak
    subsection = evaluation.subsection_peak
    click = evaluation.click_match
    return RuleEvaluation(
        rule=evaluation.rule,
        primary_peak=offset_match(primary, dx, dy) if primary else None,
        subsection_peak=offset_match(subsection, dx, dy) if subsection else None,
        confirmed=evaluation.confirmed,
        click_match=offset_match(click, dx, dy) if click else None,
    )
