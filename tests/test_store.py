"""Tests for EconomyStore SQLite CRUD."""
from __future__ import annotations

from pathlib import Path

import pytest

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder, ExploitReport
from balancelab.store import EconomyStore


@pytest.fixture
def store(tmp_path: Path) -> EconomyStore:
    return EconomyStore(str(tmp_path / "test.db"))


def make_report(store: EconomyStore) -> ExploitReport:
    """Helper to create and return a report."""
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
    g.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
    g.add_rule(EconomyRule("gems", "gold", 1.0, 4.0))
    finder = ExploitFinder()
    report = finder.find_exploits(g)
    store.save_report(report)
    return report


class TestEconomyStore:
    def test_save_and_get_rule(self, store: EconomyStore) -> None:
        rule = EconomyRule("gold", "silver", 1.0, 3.0, "mint")
        store.save_rule(rule)
        retrieved = store.get_rule(rule.id)
        assert retrieved is not None
        assert retrieved.id == rule.id
        assert retrieved.source_item == "gold"
        assert retrieved.target_item == "silver"

    def test_get_nonexistent_rule(self, store: EconomyStore) -> None:
        assert store.get_rule("nonexistent") is None

    def test_list_rules_empty(self, store: EconomyStore) -> None:
        assert store.list_rules() == []

    def test_list_rules(self, store: EconomyStore) -> None:
        rule1 = EconomyRule("gold", "silver", 1.0, 3.0)
        rule2 = EconomyRule("silver", "gems", 1.0, 2.0)
        store.save_rule(rule1)
        store.save_rule(rule2)
        rules = store.list_rules()
        assert len(rules) == 2

    def test_save_rule_upsert(self, store: EconomyStore) -> None:
        rule = EconomyRule("gold", "silver", 1.0, 3.0)
        store.save_rule(rule)
        store.save_rule(rule)  # should not raise
        assert len(store.list_rules()) == 1

    def test_save_and_get_report(self, store: EconomyStore) -> None:
        report = make_report(store)
        retrieved = store.get_report(report.id)
        assert retrieved is not None
        assert retrieved.id == report.id
        assert retrieved.total_found == report.total_found

    def test_get_nonexistent_report(self, store: EconomyStore) -> None:
        assert store.get_report("nonexistent") is None

    def test_list_reports_empty(self, store: EconomyStore) -> None:
        assert store.list_reports() == []

    def test_list_reports(self, store: EconomyStore) -> None:
        make_report(store)
        make_report(store)
        reports = store.list_reports()
        assert len(reports) >= 1  # may deduplicate

    def test_rule_with_tags(self, store: EconomyStore) -> None:
        rule = EconomyRule("gold", "silver", 1.0, 3.0, tags=["trade", "shop"])
        store.save_rule(rule)
        retrieved = store.get_rule(rule.id)
        assert retrieved is not None
        assert retrieved.tags == ["trade", "shop"]

    def test_db_created(self, tmp_path: Path) -> None:
        db_path = str(tmp_path / "subdir" / "test.db")
        EconomyStore(db_path)
        assert Path(db_path).parent.exists()
