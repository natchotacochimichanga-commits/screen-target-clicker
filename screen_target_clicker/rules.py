"""Paired click rules: primary target must match together with a subsection image."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .matcher import Match, TargetImage, find_peak_match
from .scan_region import ScanRegion


@dataclass(frozen=True)
class ClickRule:
    primary: TargetImage
    subsection: TargetImage
    subsection_threshold: float = 0.85
    scan_region: ScanRegion | None = None

    @property
    def label(self) -> str:
        text = (
            f"{self.primary.name}  →  {self.subsection.name} "
            f"(sub ≥ {self.subsection_threshold:.0%})"
        )
        if self.scan_region is not None:
            text += f"  [{self.scan_region.label}]"
        return text


@dataclass(frozen=True)
class RuleEvaluation:
    rule: ClickRule
    primary_peak: Match | None
    subsection_peak: Match | None
    confirmed: bool
    click_match: Match | None


def evaluate_rule(
    screen: np.ndarray,
    rule: ClickRule,
    primary_threshold: float,
) -> RuleEvaluation:
    """Check whether primary and subsection each meet their thresholds."""
    primary_peak = find_peak_match(screen, rule.primary)
    subsection_peak = find_peak_match(screen, rule.subsection)

    primary_ok = primary_peak is not None and primary_peak.confidence >= primary_threshold
    subsection_ok = (
        subsection_peak is not None
        and subsection_peak.confidence >= rule.subsection_threshold
    )
    confirmed = primary_ok and subsection_ok

    click_match = primary_peak if confirmed else None
    return RuleEvaluation(
        rule=rule,
        primary_peak=primary_peak,
        subsection_peak=subsection_peak,
        confirmed=confirmed,
        click_match=click_match,
    )


def find_confirmed_clicks(
    screen: np.ndarray,
    rules: list[ClickRule],
    primary_threshold: float,
) -> list[Match]:
    """Return primary matches for every rule where both images match."""
    confirmed: list[Match] = []
    for rule in rules:
        evaluation = evaluate_rule(screen, rule, primary_threshold)
        if evaluation.click_match is not None:
            confirmed.append(evaluation.click_match)
    return confirmed


def annotate_rule_evaluations(
    screen: np.ndarray,
    evaluations: list[RuleEvaluation],
    primary_threshold: float,
) -> np.ndarray:
    """Draw primary (P) and subsection (S) markers for conditional rules."""
    from .matcher import _draw_match_marker

    out = screen.copy()
    for item in evaluations:
        rule = item.rule
        primary = item.primary_peak
        subsection = item.subsection_peak
        if primary is None and subsection is None:
            continue

        primary_ok = primary is not None and primary.confidence >= primary_threshold
        subsection_ok = (
            subsection is not None
            and subsection.confidence >= rule.subsection_threshold
        )

        if item.confirmed:
            primary_color = (40, 220, 40)
            subsection_color = (220, 180, 40)
        elif primary_ok and not subsection_ok:
            primary_color = (40, 170, 255)
            subsection_color = (80, 80, 220)
        else:
            primary_color = (40, 170, 255)
            subsection_color = (80, 80, 220)

        if primary is not None:
            _draw_match_marker(out, primary, primary_color, "P ")
        if subsection is not None:
            _draw_match_marker(out, subsection, subsection_color, "S ")

    return out
