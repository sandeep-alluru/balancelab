"""Tests for EconomyRule, EconomyGraph content-addressing."""
from __future__ import annotations

from balancelab.economy import EconomyGraph, EconomyRule, ExploitPath, ExploitReport


class TestEconomyRule:
    def test_content_addressing_same_inputs(self) -> None:
        r1 = EconomyRule("gold", "silver", 1.0, 3.0)
        r2 = EconomyRule("gold", "silver", 1.0, 3.0)
        assert r1.id == r2.id

    def test_content_addressing_different_inputs(self) -> None:
        r1 = EconomyRule("gold", "silver", 1.0, 3.0)
        r2 = EconomyRule("gold", "silver", 1.0, 4.0)
        assert r1.id != r2.id

    def test_id_length(self) -> None:
        r = EconomyRule("a", "b", 1.0, 2.0)
        assert len(r.id) == 16

    def test_exchange_rate(self) -> None:
        r = EconomyRule("gold", "silver", 2.0, 6.0)
        assert r.exchange_rate() == 3.0

    def test_exchange_rate_zero_source(self) -> None:
        r = EconomyRule("gold", "silver", 0.0, 6.0)
        assert r.exchange_rate() == 0.0

    def test_to_dict(self) -> None:
        r = EconomyRule("gold", "silver", 1.0, 3.0, rule_id="mint", tags=["trade"])
        d = r.to_dict()
        assert d["source_item"] == "gold"
        assert d["target_item"] == "silver"
        assert d["source_qty"] == 1.0
        assert d["target_qty"] == 3.0
        assert d["rule_id"] == "mint"
        assert d["tags"] == ["trade"]
        assert "id" in d

    def test_from_dict_round_trip(self) -> None:
        r = EconomyRule("gold", "silver", 1.0, 3.0, rule_id="mint")
        d = r.to_dict()
        r2 = EconomyRule.from_dict(d)
        assert r2.id == r.id
        assert r2.source_item == r.source_item

    def test_default_tags(self) -> None:
        r = EconomyRule("a", "b", 1.0, 2.0)
        assert r.tags == []

    def test_default_rule_id(self) -> None:
        r = EconomyRule("a", "b", 1.0, 2.0)
        assert r.rule_id == ""


class TestEconomyGraph:
    def test_add_rule_and_items(self) -> None:
        g = EconomyGraph()
        r = EconomyRule("gold", "silver", 1.0, 3.0)
        g.add_rule(r)
        assert "gold" in g.items()
        assert "silver" in g.items()

    def test_neighbors(self) -> None:
        g = EconomyGraph()
        r = EconomyRule("gold", "silver", 1.0, 3.0)
        g.add_rule(r)
        neighbors = g.neighbors("gold")
        assert len(neighbors) == 1
        assert neighbors[0][0] == "silver"

    def test_neighbors_empty(self) -> None:
        g = EconomyGraph()
        assert g.neighbors("nonexistent") == []

    def test_items_empty_graph(self) -> None:
        g = EconomyGraph()
        assert g.items() == set()

    def test_to_dict(self) -> None:
        g = EconomyGraph()
        r = EconomyRule("gold", "silver", 1.0, 3.0)
        g.add_rule(r)
        d = g.to_dict()
        assert "rules" in d
        assert len(d["rules"]) == 1

    def test_multiple_neighbors(self) -> None:
        g = EconomyGraph()
        g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
        g.add_rule(EconomyRule("gold", "gems", 1.0, 1.0))
        neighbors = g.neighbors("gold")
        assert len(neighbors) == 2


class TestExploitPath:
    def test_content_addressing(self) -> None:
        e1 = ExploitPath(["a", "b", "a"], ["rule1", "rule2"], 1.5)
        e2 = ExploitPath(["a", "b", "a"], ["rule1", "rule2"], 1.5)
        assert e1.id == e2.id

    def test_different_paths_different_ids(self) -> None:
        e1 = ExploitPath(["a", "b", "a"], ["rule1"], 1.5)
        e2 = ExploitPath(["a", "c", "a"], ["rule1"], 1.5)
        assert e1.id != e2.id

    def test_to_dict(self) -> None:
        e = ExploitPath(["a", "b", "a"], ["rule1"], 2.0)
        d = e.to_dict()
        assert d["gain_ratio"] == 2.0
        assert d["path"] == ["a", "b", "a"]


class TestExploitReport:
    def test_content_addressing(self) -> None:
        r1 = ExploitReport(3, 3, [], 0)
        r2 = ExploitReport(3, 3, [], 0)
        assert r1.id == r2.id

    def test_to_dict(self) -> None:
        r = ExploitReport(3, 3, [], 0)
        d = r.to_dict()
        assert d["graph_item_count"] == 3
        assert d["total_found"] == 0
        assert "timestamp" in d
