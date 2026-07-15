"""Tests for balancelab.fixes."""

from __future__ import annotations

import pytest

from balancelab.economy import ExploitPath, ExploitReport
from balancelab.fixes import BalanceFix, recommend_fixes


def _make_report(exploits: list[ExploitPath]) -> ExploitReport:
    return ExploitReport(
        graph_item_count=3,
        graph_rule_count=3,
        exploits=exploits,
        total_found=len(exploits),
    )


def _make_exploit(path: list[str], gain_ratio: float) -> ExploitPath:
    return ExploitPath(path=path, rules_used=[], gain_ratio=gain_ratio)


def test_recommend_fixes_empty_report() -> None:
    """Empty ExploitReport returns an empty list of fixes."""
    report = _make_report([])
    fixes = recommend_fixes(report)
    assert fixes == []


def test_recommend_fixes_rate_cap() -> None:
    """Exploit with gain_ratio > 2.0 returns a 'rate_cap' fix."""
    exploit = _make_exploit(["gold", "silver", "gold"], gain_ratio=3.5)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert len(fixes) == 1
    fix = fixes[0]
    assert fix.fix_type == "rate_cap"
    assert fix.estimated_reduction_pct > 0
    assert fix.estimated_reduction_pct <= 99.0


def test_recommend_fixes_cooldown() -> None:
    """Exploit with gain_ratio between 1.0 and 2.0 returns a 'cooldown' fix."""
    exploit = _make_exploit(["A", "B", "C", "A"], gain_ratio=1.5)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert len(fixes) == 1
    fix = fixes[0]
    assert fix.fix_type == "cooldown"
    assert fix.suggested_value == pytest.approx(1.5 * 10)
    assert fix.estimated_reduction_pct == pytest.approx(50.0)


def test_recommend_fixes_fields() -> None:
    """All BalanceFix fields are properly populated."""
    exploit = _make_exploit(["gold", "gem", "gold"], gain_ratio=5.0)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert len(fixes) == 1
    fix = fixes[0]

    assert isinstance(fix, BalanceFix)
    assert isinstance(fix.exploit_path, list)
    assert len(fix.exploit_path) >= 1
    assert isinstance(fix.fix_type, str)
    assert isinstance(fix.description, str)
    assert len(fix.description) > 0
    assert 0.0 <= fix.estimated_reduction_pct <= 100.0
    # target_edge should be set for a path with >= 2 elements
    assert fix.target_edge == ("gold", "gem")


def test_recommend_fixes_multiple() -> None:
    """Three exploits return three fixes, one per exploit."""
    exploits = [
        _make_exploit(["A", "B", "A"], gain_ratio=3.0),
        _make_exploit(["X", "Y", "Z", "X"], gain_ratio=1.5),
        _make_exploit(["P", "Q", "P"], gain_ratio=4.0),
    ]
    report = _make_report(exploits)
    fixes = recommend_fixes(report)

    assert len(fixes) == 3
    fix_types = [f.fix_type for f in fixes]
    assert "rate_cap" in fix_types
    assert "cooldown" in fix_types


def test_recommend_fixes_daily_limit() -> None:
    """A path with exactly 2 nodes triggers a daily_limit fix."""
    # path has 2 elements => single edge, 2-node path
    exploit = _make_exploit(["A", "B"], gain_ratio=1.8)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert len(fixes) == 1
    assert fixes[0].fix_type == "daily_limit"
    assert fixes[0].estimated_reduction_pct == pytest.approx(75.0)
    # suggested_value is None for daily_limit
    assert fixes[0].suggested_value is None


def test_recommend_fixes_no_target_edge_single_node() -> None:
    """A single-node path has no target_edge."""
    exploit = _make_exploit(["A"], gain_ratio=1.5)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert len(fixes) == 1
    assert fixes[0].target_edge is None


def test_recommend_fixes_rate_cap_value() -> None:
    """rate_cap fix suggested_value is the geometric neutralization cap per edge."""
    # 3-node path: A->B->C->A => 3 edges (3 pairs in the path nodes A,B,C,A)
    exploit = _make_exploit(["A", "B", "C", "A"], gain_ratio=3.0)
    report = _make_report([exploit])
    fixes = recommend_fixes(report)

    assert fixes[0].fix_type == "rate_cap"
    # n_edges = len(path) - 1 = 3, gain_ratio = 3.0
    # suggested_value = (1 / gain_ratio) ^ (1 / n_edges) = (1/3)^(1/3)
    expected = (1.0 / max(3.0, 1.001)) ** (1.0 / 3)
    assert fixes[0].suggested_value == pytest.approx(expected)
