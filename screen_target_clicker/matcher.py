"""Template matching for target images inside a screenshot."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class TargetImage:
    path: Path
    name: str
    template: np.ndarray


@dataclass(frozen=True)
class Match:
    target_name: str
    confidence: float
    center_x: int
    center_y: int
    width: int
    height: int

    @property
    def left(self) -> int:
        return self.center_x - self.width // 2

    @property
    def top(self) -> int:
        return self.center_y - self.height // 2


def load_target(path: Path) -> TargetImage:
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        raise ValueError(f"Could not load image: {path}")
    return TargetImage(path=path, name=path.name, template=template)


def _suppress_overlaps(
    candidates: list[tuple[int, int, float]],
    template_w: int,
    template_h: int,
    min_distance: float,
) -> list[tuple[int, int, float]]:
    """Keep highest-confidence matches that are not too close together."""
    candidates.sort(key=lambda item: item[2], reverse=True)
    kept: list[tuple[int, int, float]] = []

    for cx, cy, score in candidates:
        too_close = False
        for kx, ky, _ in kept:
            if ((cx - kx) ** 2 + (cy - ky) ** 2) ** 0.5 < min_distance:
                too_close = True
                break
        if not too_close:
            kept.append((cx, cy, score))

    return kept


def find_matches(
    screen: np.ndarray,
    target: TargetImage,
    threshold: float = 0.85,
) -> list[Match]:
    """Find all template matches above threshold in the screen image."""
    template = target.template
    th, tw = template.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return []

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    candidates: list[tuple[int, int, float]] = []
    for y, x in zip(*locations):
        score = float(result[y, x])
        candidates.append((x + tw // 2, y + th // 2, score))

    min_distance = min(tw, th) * 0.6
    filtered = _suppress_overlaps(candidates, tw, th, min_distance)

    return [
        Match(
            target_name=target.name,
            confidence=score,
            center_x=cx,
            center_y=cy,
            width=tw,
            height=th,
        )
        for cx, cy, score in filtered
    ]


def find_peak_match(screen: np.ndarray, target: TargetImage) -> Match | None:
    """Return the single best-scoring match location regardless of threshold."""
    template = target.template
    th, tw = template.shape[:2]
    if screen.shape[0] < th or screen.shape[1] < tw:
        return None

    result = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc
    return Match(
        target_name=target.name,
        confidence=float(max_val),
        center_x=x + tw // 2,
        center_y=y + th // 2,
        width=tw,
        height=th,
    )


def _draw_match_marker(
    out: np.ndarray,
    peak: Match,
    color: tuple[int, int, int],
    label_prefix: str = "",
) -> None:
    x1, y1 = peak.left, peak.top
    x2, y2 = x1 + peak.width, y1 + peak.height

    cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
    cv2.drawMarker(
        out,
        (peak.center_x, peak.center_y),
        color,
        markerType=cv2.MARKER_CROSS,
        markerSize=14,
        thickness=2,
    )

    label = f"{label_prefix}{peak.confidence:.1%}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.55
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    label_y = max(y1 - 8, th + 4)
    cv2.rectangle(
        out,
        (x1, label_y - th - 4),
        (x1 + tw + 6, label_y + baseline),
        color,
        -1,
    )
    cv2.putText(
        out,
        label,
        (x1 + 3, label_y),
        font,
        scale,
        (20, 20, 20),
        thickness,
        cv2.LINE_AA,
    )


def annotate_detections(
    screen: np.ndarray,
    peaks: list[Match],
    threshold: float,
) -> np.ndarray:
    """Draw boxes, crosshair markers, and confidence labels on a copy of the screen."""
    out = screen.copy()

    for peak in peaks:
        hit = peak.confidence >= threshold
        color = (40, 220, 40) if hit else (40, 170, 255)
        _draw_match_marker(out, peak, color)
    return out
