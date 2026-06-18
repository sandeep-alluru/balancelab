"""Core data model for balancelab — economy rules, graphs, exploits."""
from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EconomyRule:
    """A single exchange rule in the economy."""

    source_item: str
    target_item: str
    source_qty: float
    target_qty: float
    rule_id: str = ""
    tags: list[str] = field(default_factory=list)
    id: str = field(init=False)

    def __post_init__(self) -> None:
        payload = f"{self.source_item}|{self.target_item}|{self.source_qty}|{self.target_qty}"
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def exchange_rate(self) -> float:
        """Return target_qty / source_qty."""
        return self.target_qty / self.source_qty if self.source_qty > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "source_item": self.source_item,
            "target_item": self.target_item,
            "source_qty": self.source_qty,
            "target_qty": self.target_qty,
            "rule_id": self.rule_id,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EconomyRule:
        """Deserialize from dict."""
        r = cls(
            source_item=d["source_item"],
            target_item=d["target_item"],
            source_qty=d["source_qty"],
            target_qty=d["target_qty"],
            rule_id=d.get("rule_id", ""),
            tags=d.get("tags", []),
        )
        return r


@dataclass
class EconomyGraph:
    """A directed exchange graph of EconomyRules."""

    rules: list[EconomyRule] = field(default_factory=list)

    def add_rule(self, rule: EconomyRule) -> None:
        """Add a rule to the graph."""
        self.rules.append(rule)

    def neighbors(self, item: str) -> list[tuple[str, EconomyRule]]:
        """Return [(target_item, rule)] for all rules from item."""
        return [(r.target_item, r) for r in self.rules if r.source_item == item]

    def items(self) -> set[str]:
        """All item names in the graph."""
        result: set[str] = set()
        for r in self.rules:
            result.add(r.source_item)
            result.add(r.target_item)
        return result

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "rules": [r.to_dict() for r in self.rules],
        }


@dataclass
class ExploitPath:
    """A circular path that yields net gain."""

    path: list[str]
    rules_used: list[str]
    gain_ratio: float
    id: str = field(init=False)

    def __post_init__(self) -> None:
        payload = json.dumps(
            {"path": self.path, "rules": self.rules_used, "gain_ratio": round(self.gain_ratio, 10)},
            sort_keys=True,
        )
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "path": self.path,
            "rules_used": self.rules_used,
            "gain_ratio": self.gain_ratio,
        }


@dataclass
class ExploitReport:
    """Report of all exploits found in an economy."""

    graph_item_count: int
    graph_rule_count: int
    exploits: list[ExploitPath]
    total_found: int
    timestamp: float = field(default_factory=lambda: time.time())
    id: str = field(init=False)

    def __post_init__(self) -> None:
        exploit_ids = "|".join(sorted(e.id for e in self.exploits))
        payload = (
            f"{self.graph_item_count}|{self.graph_rule_count}"
            f"|{self.total_found}|{exploit_ids}"
        )
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "graph_item_count": self.graph_item_count,
            "graph_rule_count": self.graph_rule_count,
            "exploits": [e.to_dict() for e in self.exploits],
            "total_found": self.total_found,
            "timestamp": self.timestamp,
        }


class ExploitFinder:
    """Find arbitrage exploits using Bellman-Ford on log-weight graph."""

    def find_exploits(self, graph: EconomyGraph) -> ExploitReport:
        """
        Convert exchange rates to log-weights: weight = -log(rate).
        Negative cycles in the log-weight graph = positive gain cycles.
        Use Bellman-Ford to detect negative cycles.
        Return ExploitReport with all found cycles.
        """
        items = list(graph.items())
        n = len(items)
        if n == 0:
            return ExploitReport(
                graph_item_count=0,
                graph_rule_count=len(graph.rules),
                exploits=[],
                total_found=0,
            )

        item_idx = {item: i for i, item in enumerate(items)}

        # Build log-weight adjacency: weight = -log(exchange_rate)
        # Negative cycle = positive gain cycle
        edges = []
        for rule in graph.rules:
            rate = rule.exchange_rate()
            if rate > 0:
                weight = -math.log(rate)
                edges.append((item_idx[rule.source_item], item_idx[rule.target_item], weight, rule))

        exploits = []
        # Try Bellman-Ford from each source to find negative cycles
        for start in range(n):
            dist = [float("inf")] * n
            pred: list[int] = [-1] * n
            pred_rule: list[EconomyRule | None] = [None] * n
            dist[start] = 0.0

            for _ in range(n - 1):
                for u, v, w, rule in edges:
                    if dist[u] != float("inf") and dist[u] + w < dist[v]:
                        dist[v] = dist[u] + w
                        pred[v] = u
                        pred_rule[v] = rule

            # Check for negative cycles
            for u, v, w, _rule in edges:
                if dist[u] != float("inf") and dist[u] + w < dist[v]:
                    # Found negative cycle - trace it back
                    cycle_nodes: list[str] = []
                    cycle_rules: list[str] = []
                    visited: set[int] = set()
                    curr = v
                    # advance enough steps to ensure we're in the cycle
                    for _ in range(n):
                        curr = pred[curr]
                    # now trace the cycle
                    cycle_start = curr
                    curr = cycle_start
                    while True:
                        visited.add(curr)
                        cycle_nodes.append(items[curr])
                        if pred_rule[curr] is not None:
                            cycle_rules.append(pred_rule[curr].id)  # type: ignore[union-attr]
                        curr = pred[curr]
                        if curr == cycle_start:
                            break

                    # close the cycle
                    cycle_nodes.append(items[cycle_start])

                    # Compute gain ratio - multiply exchange rates around the cycle
                    gain = 1.0
                    for node_idx in visited:
                        if pred_rule[node_idx] is not None:
                            gain *= pred_rule[node_idx].exchange_rate()  # type: ignore[union-attr]

                    if gain > 1.0:
                        exploit = ExploitPath(
                            path=cycle_nodes,
                            rules_used=cycle_rules,
                            gain_ratio=gain,
                        )
                        exploits.append(exploit)
                    break

        # Deduplicate exploits by path set
        seen: set[frozenset[str]] = set()
        unique: list[ExploitPath] = []
        for e in exploits:
            key = frozenset(e.path)
            if key not in seen:
                seen.add(key)
                unique.append(e)

        return ExploitReport(
            graph_item_count=len(items),
            graph_rule_count=len(graph.rules),
            exploits=unique,
            total_found=len(unique),
        )
