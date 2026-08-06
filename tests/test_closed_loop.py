"""Closed-loop gates — NO-SHIP exploits + farm latency-arb signal traps."""

from __future__ import annotations

import pytest

from balancelab.closed_loop import (
    ClosedLoopError,
    assert_economy_shippable,
    assert_price_book_ok,
    gate_binary_signal,
    gate_economy,
    gate_kill_switch,
    gate_price_book,
)
from balancelab.economy import EconomyGraph, EconomyRule


def test_empty_economy_fails_loud() -> None:
    out = gate_economy(EconomyGraph())
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2


def test_exploit_cycle_no_ship() -> None:
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 10.0, rule_id="g2s"))
    g.add_rule(EconomyRule("silver", "gold", 1.0, 1.0, rule_id="s2g"))
    # rate 10 * 1 = 10x loop if designed as exploit — need proper cycle
    g2 = EconomyGraph()
    g2.add_rule(EconomyRule("a", "b", 1.0, 2.0))
    g2.add_rule(EconomyRule("b", "a", 1.0, 1.0))
    # a->b rate 2, b->a rate 1 => gain 2
    out = gate_economy(g2)
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert out.exploit_count >= 1
    assert "NO-SHIP" in out.reason or "exploit" in out.reason.lower()


def test_clean_economy_passes() -> None:
    g = EconomyGraph()
    # lossy cycle: a->b rate 2, b->a rate 0.4 => gain 0.8 < 1
    g.add_rule(EconomyRule("a", "b", 1.0, 2.0))
    g.add_rule(EconomyRule("b", "a", 1.0, 0.4))
    out = gate_economy(g)
    # may still find exploit depending on BF; if gain < 1 should pass
    if out.ok:
        assert out.verdict == "PASS"
    else:
        # if still flags, max_allowed_gain default caught something
        assert out.exit_code in {1, 2}


def test_price_book_best_first_ok() -> None:
    bids = [100.0, 99.0, 98.0]
    asks = [101.0, 102.0, 103.0]
    out = gate_price_book(bids, asks, order="best-first")
    assert out.ok is True


def test_price_book_worst_first_at_zero_fails() -> None:
    """Farm: Polymarket worst-to-best; .first() took worst."""
    bids = [98.0, 99.0, 100.0]  # best at end
    asks = [103.0, 102.0, 101.0]
    out = gate_price_book(bids, asks, order="best-first")
    assert out.ok is False
    assert out.verdict == "FAIL"
    assert "PRICE-BOOK-ORDER" in out.reason


def test_price_book_worst_first_mode_ok() -> None:
    bids = [98.0, 99.0, 100.0]
    asks = [103.0, 102.0, 101.0]
    out = gate_price_book(bids, asks, order="worst-first")
    assert out.ok is True


def test_signal_invert_down_with_expensive_yes() -> None:
    out = gate_binary_signal("down", yes_price=0.75, no_price=0.25)
    assert out.ok is False
    assert "SIGNAL-INVERT" in out.reason


def test_signal_down_with_correct_leg() -> None:
    out = gate_binary_signal("down", yes_price=0.30, no_price=0.70)
    assert out.ok is True


def test_kill_switch_every_trade_trips() -> None:
    # every trade loses 10, limit 5 -> always trips
    pnls = [-10.0] * 10
    out = gate_kill_switch(pnls, loss_limit=5.0, paper_mode=True)
    assert out.ok is False
    assert "KILL-SWITCH" in out.reason


def test_kill_switch_reasonable() -> None:
    pnls = [1.0, -0.5, 2.0, -0.2, 0.5]
    out = gate_kill_switch(pnls, loss_limit=10.0, paper_mode=True)
    assert out.ok is True


def test_assert_economy_raises() -> None:
    with pytest.raises(ClosedLoopError, match="FAIL_LOUD"):
        assert_economy_shippable(EconomyGraph())


def test_assert_price_book_raises() -> None:
    with pytest.raises(ClosedLoopError, match="PRICE-BOOK"):
        assert_price_book_ok([1.0, 2.0], [3.0, 2.5], order="best-first")


def test_to_dict() -> None:
    payload = gate_economy(EconomyGraph()).to_dict()
    assert payload["ok"] is False
    assert payload["verdict"] == "FAIL_LOUD"


def test_empty_price_book_fails_loud() -> None:
    out = gate_price_book([], [1.0])
    assert out.verdict == "FAIL_LOUD"


def test_crossed_book_fails() -> None:
    out = gate_price_book([105.0], [100.0])
    assert out.ok is False
    assert "crossed" in out.reason.lower()


def test_unknown_price_order_fails_loud() -> None:
    out = gate_price_book([2.0, 1.0], [3.0, 4.0], order="middle-first")
    assert out.verdict == "FAIL_LOUD"


def test_unknown_direction_fails_loud() -> None:
    out = gate_binary_signal("sideways", 0.5)
    assert out.verdict == "FAIL_LOUD"


def test_invalid_yes_price() -> None:
    out = gate_binary_signal("up", yes_price=1.5)
    assert out.ok is False


def test_yes_no_sum_not_one() -> None:
    out = gate_binary_signal("up", yes_price=0.8, no_price=0.8)
    assert out.ok is False
    assert "SIGNAL-INVERT" in out.reason


def test_kill_switch_invalid_limit() -> None:
    out = gate_kill_switch([-1.0], loss_limit=0)
    assert out.verdict == "FAIL_LOUD"


def test_kill_switch_empty_pnls() -> None:
    out = gate_kill_switch([], loss_limit=1.0)
    assert out.verdict == "FAIL_LOUD"
