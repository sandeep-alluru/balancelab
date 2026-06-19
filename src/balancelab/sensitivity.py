"""Sensitivity analysis for economy nodes."""

from __future__ import annotations

from dataclasses import dataclass

from balancelab.economy import EconomyGraph, ExploitReport


@dataclass
class SensitivityResult:
    node_id: str
    node_type: str  # "source_only", "target_only", "hub" (appears as both)
    impact_score: float  # 0-1, how much changing this node affects the economy
    connected_rules: int  # how many rules reference this node
    exploit_involvement: int  # how many exploit paths pass through this node
    recommendation: str  # "monitor", "rate-limit", "gate"


def sensitivity_analysis(graph: EconomyGraph, report: ExploitReport) -> list[SensitivityResult]:
    """Rank all nodes by how much they impact the economy balance, descending by impact_score."""
    total_rules = max(1, len(graph.rules))
    results: list[SensitivityResult] = []

    for node in graph.items():
        # Count how many rules reference this node as source vs target
        as_source = sum(1 for r in graph.rules if r.source_item == node)
        as_target = sum(1 for r in graph.rules if r.target_item == node)
        connected_rules = as_source + as_target

        # Determine node_type
        if as_source > 0 and as_target > 0:
            node_type = "hub"
        elif as_source > 0:
            node_type = "source_only"
        else:
            node_type = "target_only"

        # Count exploit involvement
        exploit_involvement = sum(1 for exploit in report.exploits if node in exploit.path)

        # Compute impact_score
        impact_score = min(
            1.0,
            (connected_rules * 0.3 + exploit_involvement * 0.5) / total_rules,
        )

        # Recommendation
        if exploit_involvement >= 2:
            recommendation = "gate"
        elif exploit_involvement >= 1:
            recommendation = "rate-limit"
        else:
            recommendation = "monitor"

        results.append(
            SensitivityResult(
                node_id=node,
                node_type=node_type,
                impact_score=impact_score,
                connected_rules=connected_rules,
                exploit_involvement=exploit_involvement,
                recommendation=recommendation,
            )
        )

    # Sort by impact_score descending
    results.sort(key=lambda r: r.impact_score, reverse=True)
    return results


def critical_path(graph: EconomyGraph) -> list[str]:
    """Find the sequence of nodes with highest economic throughput (most rules flow through)."""
    if not graph.rules:
        return []

    # Build outgoing throughput per node: sum of exchange_rates for all rules where node is source
    throughput: dict[str, float] = {}
    for node in graph.items():
        throughput[node] = sum(r.exchange_rate() for r in graph.rules if r.source_item == node)

    # Start from the node with highest outgoing throughput
    if not throughput:
        return []

    start = max(throughput, key=lambda n: throughput[n])

    path: list[str] = [start]
    visited: set[str] = {start}
    current = start

    for _ in range(49):  # max 50 steps total (including start)
        neighbors = graph.neighbors(current)
        if not neighbors:
            break

        # Pick neighbor with highest exchange_rate rule
        best_target: str | None = None
        best_rate = -1.0
        for target, rule in neighbors:
            if rule.exchange_rate() > best_rate:
                best_rate = rule.exchange_rate()
                best_target = target

        if best_target is None or best_target in visited:
            break

        path.append(best_target)
        visited.add(best_target)
        current = best_target

    return path
