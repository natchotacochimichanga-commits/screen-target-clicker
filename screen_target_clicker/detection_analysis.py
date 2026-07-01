"""Shared detection analysis for test preview and live scanning."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .matcher import Match, TargetImage, annotate_detections, find_matches, find_peak_match
from .rules import ClickRule, RuleEvaluation, annotate_rule_evaluations, evaluate_rule
from .scan_region import (
    ScanRegion,
    annotate_rule_scan_regions,
    annotate_scan_region,
    apply_scan_region,
    offset_match,
    offset_rule_evaluation,
)


@dataclass(frozen=True)
class DetectionAnalysis:
    annotated: np.ndarray
    results_text: str
    best_match: Match | None
    peaks: list[Match]
    rule_evaluations: list[RuleEvaluation]


def pick_best_click_match(
    screen: np.ndarray,
    targets: list[TargetImage],
    click_rules: list[ClickRule],
    threshold: float,
    scan_region: ScanRegion | None,
) -> Match | None:
    candidates: list[Match] = []

    target_search, target_off_x, target_off_y = apply_scan_region(screen, scan_region)
    for target in targets:
        for match in find_matches(target_search, target, threshold):
            candidates.append(offset_match(match, target_off_x, target_off_y))

    for rule in click_rules:
        rule_search, rule_off_x, rule_off_y = apply_scan_region(screen, rule.scan_region)
        evaluation = evaluate_rule(rule_search, rule, threshold)
        if evaluation.click_match is not None:
            candidates.append(
                offset_match(evaluation.click_match, rule_off_x, rule_off_y)
            )

    best: Match | None = None
    for match in candidates:
        if best is None or match.confidence > best.confidence:
            best = match
    return best


def analyze_detection(
    screen: np.ndarray,
    targets: list[TargetImage],
    click_rules: list[ClickRule],
    threshold: float,
    scan_region: ScanRegion | None,
) -> DetectionAnalysis:
    target_search, target_off_x, target_off_y = apply_scan_region(screen, scan_region)
    lines: list[str] = [f"Primary threshold: {threshold:.0%}"]
    if scan_region is not None:
        lines.append(f"Target scan zone: {scan_region.label}")
    lines.append("")

    peaks: list[Match] = []

    if targets:
        lines.append("=== Target images ===")
        for target in targets:
            peak = find_peak_match(target_search, target)
            if peak is None:
                lines.append(f"{target.name}\n  Too small for scan zone.\n")
                continue

            display = offset_match(peak, target_off_x, target_off_y)
            peaks.append(display)
            hits = find_matches(target_search, target, threshold)
            status = (
                "MATCH" if peak.confidence >= threshold else "below threshold"
            )
            lines.append(
                f"{target.name}\n"
                f"  Best: {peak.confidence:.1%} at "
                f"({display.center_x}, {display.center_y})\n"
                f"  Status: {status}\n"
                f"  Hits >= threshold: {len(hits)}\n"
            )

    rule_evaluations: list[RuleEvaluation] = []
    if click_rules:
        lines.append("=== Conditional click rules ===")
        for rule in click_rules:
            rule_search, rule_off_x, rule_off_y = apply_scan_region(
                screen, rule.scan_region
            )
            evaluation = evaluate_rule(rule_search, rule, threshold)
            shifted = offset_rule_evaluation(evaluation, rule_off_x, rule_off_y)
            rule_evaluations.append(shifted)
            primary = shifted.primary_peak
            subsection = shifted.subsection_peak

            lines.append(rule.label)
            if rule.scan_region is not None:
                lines.append(f"  Rule zone: {rule.scan_region.label}")
            else:
                lines.append("  Rule zone: full window")
            if primary is None:
                lines.append("  Primary: too small for rule zone")
            else:
                p_status = (
                    "ok"
                    if evaluation.primary_peak
                    and evaluation.primary_peak.confidence >= threshold
                    else "below threshold"
                )
                lines.append(
                    f"  Primary: {primary.confidence:.1%} "
                    f"at ({primary.center_x}, {primary.center_y}) [{p_status}]"
                )
            if subsection is None:
                lines.append("  Subsection: too small for rule zone")
            else:
                s_status = (
                    "ok"
                    if evaluation.subsection_peak
                    and evaluation.subsection_peak.confidence
                    >= rule.subsection_threshold
                    else "below threshold"
                )
                lines.append(
                    f"  Subsection: {subsection.confidence:.1%} "
                    f"at ({subsection.center_x}, {subsection.center_y}) "
                    f"[{s_status}, need ≥ {rule.subsection_threshold:.0%}]"
                )
            if evaluation.confirmed:
                lines.append("  Status: WOULD CLICK (both matched)\n")
            else:
                lines.append("  Status: blocked (both must match)\n")

    best_match = pick_best_click_match(
        screen, targets, click_rules, threshold, scan_region
    )
    if best_match is not None:
        lines.append(
            f"=== Best click candidate ===\n"
            f"{best_match.target_name} @ {best_match.confidence:.1%}\n"
            f"({best_match.center_x}, {best_match.center_y})"
        )
    else:
        lines.append("=== Best click candidate ===\nNone above threshold")

    annotated = annotate_scan_region(screen, scan_region)
    annotated = annotate_rule_scan_regions(annotated, click_rules)
    annotated = annotate_detections(annotated, peaks, threshold)
    if rule_evaluations:
        annotated = annotate_rule_evaluations(
            annotated, rule_evaluations, threshold
        )

    return DetectionAnalysis(
        annotated=annotated,
        results_text="\n".join(lines),
        best_match=best_match,
        peaks=peaks,
        rule_evaluations=rule_evaluations,
    )
