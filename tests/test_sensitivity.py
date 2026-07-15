"""Tests for balancelab.sensitivity."""

from __future__ import annotations

from balancelab.economy import EconomyGraph, EconomyRule, ExploitPath, ExploitReport
from balancelab.sensitivity import SensitivityResult, critical_path, sensitivity_analysis


def _make_report(exploits: list[ExploitPath] | None = None) -> ExploitReport:
    if exploits is None:
        exploits = []
    return ExploitReport(
        graph_item_count=3,
        graph_rule_count=3,
        exploits=exploits,
        total_found=len(exploits),
    )


def _make_exploit(path: list[str], gain_ratio: float = 2.0) -> ExploitPath:
    return ExploitPath(path=path, rules_used=[], gain_ratio=gain_ratio)


def _make_three_node_graph() -> EconomyGraph:
    """Graph: A->B at 1:2, B->C at 1:1, C->A at 1:1."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule("A", "B", 1.0, 2.0))
    graph.add_rule(EconomyRule("B", "C", 1.0, 1.0))
    graph.add_rule(EconomyRule("C", "A", 1.0, 1.0))
    return graph


def test_sensitivity_basic() -> None:
    """sensitivity_analysis returns a list of SensitivityResult sorted by impact_score desc."""
    graph = _make_three_node_graph()
    report = _make_report()
    results = sensitivity_analysis(graph, report)

    assert isinstance(results, list)
    assert len(results) == 3  # A, B, C
    for r in results:
        assert isinstance(r, SensitivityResult)
        assert 0.0 <= r.impact_score <= 1.0

    # Verify descending order
    scores = [r.impact_score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_sensitivity_impact_score() -> None:
    """A hub node (appears as both source and target) scores higher than a leaf."""
    graph = EconomyGraph()
    # gold is a hub: source in rule 1, target in rule 2
    # leaf is only a target
    graph.add_rule(EconomyRule("gold", "silver", 1.0, 2.0))
    graph.add_rule(EconomyRule("silver", "gold", 1.0, 1.5))
    graph.add_rule(EconomyRule("gold", "gem", 1.0, 0.5))
    # gem only appears as target

    report = _make_report()
    results = sensitivity_analysis(graph, report)

    node_map = {r.node_id: r for r in results}
    assert node_map["gold"].node_type == "hub"
    assert node_map["gold"].impact_score >= node_map["gem"].impact_score


def test_critical_path_basic() -> None:
    """critical_path returns a list of node name strings."""
    graph = _make_three_node_graph()
    path = critical_path(graph)

    assert isinstance(path, list)
    assert all(isinstance(n, str) for n in path)
    assert len(path) >= 1


def test_critical_path_no_cycles() -> None:
    """critical_path stops when it would revisit a node."""
    graph = EconomyGraph()
    # linear chain: A->B->C (no cycle)
    graph.add_rule(EconomyRule("A", "B", 1.0, 2.0))
    graph.add_rule(EconomyRule("B", "C", 1.0, 3.0))

    path = critical_path(graph)

    # No node should appear twice
    assert len(path) == len(set(path)), "critical_path should not revisit nodes"


def test_sensitivity_exploit_involvement() -> None:
    """A node that participates in exploit paths has exploit_involvement > 0."""
    graph = _make_three_node_graph()
    exploit = _make_exploit(["A", "B", "A"], gain_ratio=2.5)
    report = _make_report([exploit])

    results = sensitivity_analysis(graph, report)
    node_map = {r.node_id: r for r in results}

    # A and B are in the exploit path
    assert node_map["A"].exploit_involvement >= 1
    assert node_map["B"].exploit_involvement >= 1
    # C is not in the exploit path
    assert node_map["C"].exploit_involvement == 0


def test_critical_path_empty_graph() -> None:
    """critical_path on an empty graph returns an empty list."""
    graph = EconomyGraph()
    path = critical_path(graph)
    assert path == []


def test_sensitivity_gate_recommendation() -> None:
    """A node with exploit_involvement >= 2 gets 'gate' recommendation."""
    graph = _make_three_node_graph()
    exploits = [
        _make_exploit(["A", "B", "A"], gain_ratio=2.5),
        _make_exploit(["A", "C", "A"], gain_ratio=2.0),
    ]
    report = _make_report(exploits)

    results = sensitivity_analysis(graph, report)
    node_map = {r.node_id: r for r in results}

    # A appears in both exploit paths
    assert node_map["A"].exploit_involvement >= 2
    assert node_map["A"].recommendation == "gate"


def test_sensitivity_source_only_and_target_only() -> None:
    """Correctly identifies source_only and target_only node types."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule("producer", "consumer", 1.0, 1.0))
    report = _make_report()

    results = sensitivity_analysis(graph, report)
    node_map = {r.node_id: r for r in results}

    assert node_map["producer"].node_type == "source_only"
    assert node_map["consumer"].node_type == "target_only"
