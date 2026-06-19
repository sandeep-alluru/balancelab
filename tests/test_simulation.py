"""Tests for balancelab.simulation."""
from __future__ import annotations

import pytest

from balancelab.economy import EconomyGraph, EconomyRule
from balancelab.simulation import SimulationResult, SimulationStep, simulate


def _make_graph_gold_silver() -> EconomyGraph:
    """Simple graph: gold->silver at 1:2, silver->gold at 1:1."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule(source_item="gold", target_item="silver", source_qty=1.0, target_qty=2.0))
    graph.add_rule(EconomyRule(source_item="silver", target_item="gold", source_qty=1.0, target_qty=1.0))
    return graph


def _make_exploit_graph() -> EconomyGraph:
    """Graph with exploit cycle: gold->silver at 1:3, silver->gold at 1:2 (gain 6x)."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule(source_item="gold", target_item="silver", source_qty=1.0, target_qty=3.0))
    graph.add_rule(EconomyRule(source_item="silver", target_item="gold", source_qty=1.0, target_qty=2.0))
    return graph


def _make_inflation_graph() -> EconomyGraph:
    """Graph where gold inflates rapidly: gold->gem at 1:1000."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule(source_item="gold", target_item="gem", source_qty=1.0, target_qty=1000.0))
    return graph


def test_simulate_greedy_basic() -> None:
    """Greedy strategy produces exactly n_steps SimulationSteps."""
    graph = _make_graph_gold_silver()
    initial = {"gold": 100.0, "silver": 100.0}
    result = simulate(graph, initial, n_steps=5, agent_strategy="greedy")

    assert isinstance(result, SimulationResult)
    assert len(result.steps) == 5
    for i, step in enumerate(result.steps, 1):
        assert isinstance(step, SimulationStep)
        assert step.step == i


def test_simulate_result_fields() -> None:
    """final_levels and summary are populated after simulation."""
    graph = _make_graph_gold_silver()
    initial = {"gold": 50.0, "silver": 50.0}
    result = simulate(graph, initial, n_steps=3, agent_strategy="greedy")

    assert isinstance(result.final_levels, dict)
    assert "gold" in result.final_levels or "silver" in result.final_levels
    assert isinstance(result.summary, str)
    assert "Ran 3 steps" in result.summary
    assert "Inflation" in result.summary


def test_simulate_inflation_detection() -> None:
    """A 1:1000 rule produces gems far beyond 10x initial level on step 1."""
    graph = _make_inflation_graph()
    # gem starts at 10; after 1 rule application it becomes 1000 (100x initial)
    initial = {"gold": 100.0, "gem": 10.0}
    result = simulate(graph, initial, n_steps=5, agent_strategy="greedy")

    assert result.inflation_detected is True
    assert result.inflation_resource == "gem"


def test_simulate_balanced_strategy() -> None:
    """Balanced strategy returns exactly n_steps steps."""
    graph = _make_graph_gold_silver()
    initial = {"gold": 200.0, "silver": 200.0}
    result = simulate(graph, initial, n_steps=10, agent_strategy="balanced")

    assert len(result.steps) == 10
    assert isinstance(result.final_levels, dict)


def test_simulate_exploit_strategy() -> None:
    """Exploit strategy runs on a graph with an exploit cycle without error."""
    graph = _make_exploit_graph()
    initial = {"gold": 100.0, "silver": 100.0}
    result = simulate(graph, initial, n_steps=5, agent_strategy="exploit")

    assert len(result.steps) == 5
    assert isinstance(result.final_levels, dict)
    # With an exploit cycle, resources should grow
    total_initial = sum(initial.values())
    total_final = sum(result.final_levels.values())
    assert total_final >= total_initial


def test_simulate_rule_violations_tracked() -> None:
    """Rules that cannot fire due to insufficient resources are tracked as violations."""
    graph = EconomyGraph()
    # rule needs 1000 gold but we only have 1
    graph.add_rule(EconomyRule(source_item="gold", target_item="gem", source_qty=1000.0, target_qty=1.0))
    initial = {"gold": 1.0}
    result = simulate(graph, initial, n_steps=3, agent_strategy="greedy")

    assert len(result.violated_rules) > 0


def test_simulate_no_inflation_when_stable() -> None:
    """A stable economy (1:1 exchange) does not trigger inflation."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule(source_item="gold", target_item="silver", source_qty=1.0, target_qty=1.0))
    initial = {"gold": 100.0, "silver": 0.0}
    result = simulate(graph, initial, n_steps=10, agent_strategy="greedy")

    assert result.inflation_detected is False
    assert result.inflation_resource is None


def test_simulate_balanced_insufficient_resources() -> None:
    """Balanced strategy tracks violations when resources are depleted."""
    graph = EconomyGraph()
    graph.add_rule(EconomyRule(source_item="gold", target_item="gem", source_qty=50.0, target_qty=1.0))
    # gold starts at 0 so rule can never fire
    initial = {"gold": 0.0, "gem": 0.0}
    result = simulate(graph, initial, n_steps=3, agent_strategy="balanced")

    assert len(result.steps) == 3
    # violations should be recorded for the rule that couldn't fire
    assert len(result.violated_rules) > 0
