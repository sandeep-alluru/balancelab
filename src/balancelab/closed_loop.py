"""Closed-loop gates for balancelab (ship/no-ship economy + farm trading failures).

Who reads the output?
  CI ``balancelab scan``, design review, trading bot pre-flight, eagle-eyes.

What outcome changes?
  Empty economy → FAIL_LOUD (cannot ship a phantom graph).
  Exploits found → FAIL (no-ship).
  Inverted binary signal / inverted price book → FAIL (farm latency-arb class).
  Kill-switch that trips on every paper fill → FAIL (cannot evaluate strategy).

Farm Qdrant cases (Latency Arbitrage):
  * SIGNAL-INVERT - DOWN mid passed as YES price
  * PRICE-BOOK-ORDER - API worst-to-best; ``.first()`` took worst quote
  * KILL-SWITCH - loss-limit trips on every paper trade

Public/product: AI token budget runaway loops (balancelab core) - gate_scan.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from balancelab.economy import EconomyGraph, ExploitFinder, ExploitReport


class ClosedLoopError(ValueError):
    """Raised when the economy/signal gate refuses empty or unsafe state."""


@dataclass(frozen=True)
class GateOutcome:
    """Result of a closed-loop economy or signal gate.

    Attributes:
        ok: True only when ship/run may continue.
        verdict: ``PASS``, ``FAIL``, or ``FAIL_LOUD``.
        reason: Always non-empty.
        exit_code: 0 PASS, 1 FAIL (exploit/signal), 2 FAIL_LOUD (empty).
        rule_count: Economy rules examined.
        exploit_count: Exploits found.
        max_gain_ratio: Largest exploit gain if any.
        human_required: True when design review is required.
    """

    ok: bool
    verdict: str
    reason: str
    exit_code: int
    rule_count: int = 0
    exploit_count: int = 0
    max_gain_ratio: float | None = None
    human_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "rule_count": self.rule_count,
            "exploit_count": self.exploit_count,
            "max_gain_ratio": self.max_gain_ratio,
            "human_required": self.human_required,
        }


def _fail_loud(reason: str, **kwargs: Any) -> GateOutcome:
    kwargs.setdefault("human_required", True)
    return GateOutcome(ok=False, verdict="FAIL_LOUD", reason=reason, exit_code=2, **kwargs)


def _fail(reason: str, **kwargs: Any) -> GateOutcome:
    kwargs.setdefault("human_required", True)
    return GateOutcome(ok=False, verdict="FAIL", reason=reason, exit_code=1, **kwargs)


def gate_economy(
    graph: EconomyGraph,
    *,
    finder: ExploitFinder | None = None,
    max_allowed_gain: float = 1.0,
    min_rules: int = 1,
) -> GateOutcome:
    """Scan economy for exploits - load-bearing ship/no-ship gate.

    * Empty rules → FAIL_LOUD
    * Any exploit with gain_ratio > max_allowed_gain → FAIL (no-ship)
    * Clean graph → PASS

    Args:
        graph: Economy exchange graph.
        finder: Optional ExploitFinder (default new instance).
        max_allowed_gain: Gains strictly above this fail (default 1.0 = any profit).
        min_rules: Minimum rules required.
    """
    n = len(graph.rules)
    if n < min_rules:
        return _fail_loud(
            f"empty economy - {n} rules (<{min_rules}); cannot gate a phantom graph",
            rule_count=n,
            exploit_count=0,
        )

    report = (finder or ExploitFinder()).find_exploits(graph)
    return gate_exploit_report(report, max_allowed_gain=max_allowed_gain)


def gate_exploit_report(
    report: ExploitReport,
    *,
    max_allowed_gain: float = 1.0,
) -> GateOutcome:
    """Gate a precomputed ExploitReport for ship/no-ship."""
    if report.graph_rule_count == 0:
        return _fail_loud(
            "empty exploit report graph_rule_count=0",
            rule_count=0,
            exploit_count=0,
        )

    bad = [e for e in report.exploits if e.gain_ratio > max_allowed_gain]
    if bad:
        top = max(e.gain_ratio for e in bad)
        return _fail(
            f"NO-SHIP: {len(bad)} exploit cycle(s) max_gain={top:.4f} "
            f"(threshold={max_allowed_gain}) - balance red-team failed",
            rule_count=report.graph_rule_count,
            exploit_count=len(bad),
            max_gain_ratio=top,
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"economy clean: rules={report.graph_rule_count} "
            f"exploits={report.total_found} under threshold={max_allowed_gain}"
        ),
        exit_code=0,
        rule_count=report.graph_rule_count,
        exploit_count=report.total_found,
        max_gain_ratio=None,
        human_required=False,
    )


def gate_price_book(
    bids: Sequence[float],
    asks: Sequence[float],
    *,
    order: str = "best-first",
) -> GateOutcome:
    """Gate bid/ask arrays for PRICE-BOOK-ORDER (Polymarket worst-to-best trap).

    Farm failure: API returns worst-to-best; ``.first()`` took worst price.

    Args:
        bids: Bid prices (best bid should be highest).
        asks: Ask prices (best ask should be lowest).
        order: ``best-first`` expects best at index 0; ``worst-first`` documents
            the inverted API (still validates internal consistency).
    """
    if not bids or not asks:
        return _fail_loud(
            "empty price book - no bids or asks",
            rule_count=0,
        )

    best_bid = max(bids)
    best_ask = min(asks)
    if best_bid > best_ask:
        return _fail(
            f"PRICE-BOOK-ORDER: crossed book best_bid={best_bid} > best_ask={best_ask}",
            rule_count=len(bids) + len(asks),
        )

    if order == "best-first":
        if bids[0] != best_bid:
            return _fail(
                f"PRICE-BOOK-ORDER: expected best bid at [0], got {bids[0]} "
                f"(true best={best_bid}) - worst-first API trap "
                f"(farm: Polymarket .first())",
                rule_count=len(bids),
            )
        if asks[0] != best_ask:
            return _fail(
                f"PRICE-BOOK-ORDER: expected best ask at [0], got {asks[0]} "
                f"(true best={best_ask}) - worst-first API trap",
                rule_count=len(asks),
            )
    elif order == "worst-first":
        if bids[-1] != best_bid or asks[-1] != best_ask:
            return _fail(
                "PRICE-BOOK-ORDER: order=worst-first but last element is not best quote",
                rule_count=len(bids) + len(asks),
            )
    else:
        return _fail_loud(f"unknown price book order mode {order!r}")

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"price book ok order={order} best_bid={best_bid} best_ask={best_ask}",
        exit_code=0,
        rule_count=len(bids) + len(asks),
        human_required=False,
    )


def gate_binary_signal(
    direction: str,
    yes_price: float,
    no_price: float | None = None,
    *,
    down_uses_no_token: bool = True,
) -> GateOutcome:
    """Gate binary market signal mapping (SIGNAL-INVERT farm case).

    Farm failure: BTC DOWN used DOWN mid as YES price on the DOWN contract -
    inverted directional signal.

    For a DOWN signal on a market where YES = "price goes down":
      * correct: use YES price of the DOWN contract
      * invert trap: treating "DOWN mid" as if it were the UP/YES without
        checking token polarity

    This gate checks that for ``direction=down``, ``yes_price`` is the
    probability mass for the DOWN outcome (typically lower when market is
    bullish). When both yes and no are provided, they must sum ~1 and
    direction must pick the cheaper/correct side consistently.

    Args:
        direction: ``up`` or ``down`` (case-insensitive).
        yes_price: Price used as YES for the trade decision.
        no_price: Optional NO price for consistency check.
        down_uses_no_token: If True, direction=down must not use a yes_price
            that is mislabeled - when no_price given and direction=down,
            the traded token price should be yes_price only if YES means down;
            we require yes_price + no_price ≈ 1 and 0 < prices < 1.
    """
    d = (direction or "").strip().lower()
    if d not in {"up", "down", "yes", "no"}:
        return _fail_loud(f"SIGNAL-INVERT: unknown direction {direction!r}")

    if not (0.0 < yes_price < 1.0):
        return _fail(
            f"SIGNAL-INVERT: yes_price={yes_price} out of (0,1) - invalid quote",
            rule_count=1,
        )

    if no_price is not None:
        if not (0.0 < no_price < 1.0):
            return _fail(
                f"SIGNAL-INVERT: no_price={no_price} out of (0,1)",
                rule_count=2,
            )
        s = yes_price + no_price
        if abs(s - 1.0) > 0.05:
            return _fail(
                f"SIGNAL-INVERT: yes+no={s:.4f} not ~1.0 - inverted/wrong legs "
                f"(farm: DOWN mid as YES)",
                rule_count=2,
            )
        # Classic invert: using the expensive wrong leg for direction
        if d == "down" and down_uses_no_token and yes_price > no_price + 0.02:
            # When YES is the UP token, DOWN should trade NO (price = no_price).
            # If agent passes yes_price while intending down, flag if yes > no
            # (buying the expensive wrong side for a down view).
            return _fail(
                f"SIGNAL-INVERT: direction=down but yes_price={yes_price:.4f} > "
                f"no_price={no_price:.4f} - likely using UP/YES as DOWN signal "
                f"(farm: BTC DOWN mid as YES)",
                rule_count=2,
            )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=f"binary signal ok direction={d} yes={yes_price}",
        exit_code=0,
        rule_count=1 if no_price is None else 2,
        human_required=False,
    )


def gate_kill_switch(
    trade_pnls: Sequence[float],
    loss_limit: float,
    *,
    paper_mode: bool = False,
    max_trip_rate: float = 0.5,
) -> GateOutcome:
    """Gate kill-switch configuration (KILL-SWITCH farm case).

    Farm failure: loss-limit tripped on every paper fill (worst-case spread
    model) - strategy could not be evaluated.

    Args:
        trade_pnls: Per-trade PnL series (negative = loss).
        loss_limit: Absolute loss that trips the switch (positive number).
        paper_mode: If True, apply stricter trip-rate limits.
        max_trip_rate: Fail if fraction of trades that would trip exceeds this.
    """
    if loss_limit <= 0:
        return _fail_loud(
            f"KILL-SWITCH: invalid loss_limit={loss_limit} (must be > 0)",
        )

    if not trade_pnls:
        return _fail_loud("KILL-SWITCH: empty trade PnL series - nothing to gate")

    # Trip if cumulative or single trade exceeds limit
    trips = 0
    cum = 0.0
    for pnl in trade_pnls:
        cum += pnl
        if pnl <= -loss_limit or cum <= -loss_limit:
            trips += 1
            # reset cum after trip (breaker re-arm)
            cum = 0.0

    rate = trips / len(trade_pnls)
    limit = max_trip_rate
    if paper_mode:
        limit = min(limit, 0.35)

    if rate > limit:
        return _fail(
            f"KILL-SWITCH: trip_rate={rate:.2f} > max={limit:.2f} "
            f"({trips}/{len(trade_pnls)} trades) loss_limit={loss_limit} "
            f"paper_mode={paper_mode} - breaker too tight for evaluation "
            f"(farm: every paper fill tripped)",
            rule_count=len(trade_pnls),
            exploit_count=trips,
        )

    return GateOutcome(
        ok=True,
        verdict="PASS",
        reason=(
            f"kill switch ok trip_rate={rate:.2f} ({trips}/{len(trade_pnls)}) limit={loss_limit}"
        ),
        exit_code=0,
        rule_count=len(trade_pnls),
        exploit_count=trips,
        human_required=False,
    )


def assert_economy_shippable(graph: EconomyGraph, **kwargs: Any) -> GateOutcome:
    outcome = gate_economy(graph, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome


def assert_price_book_ok(
    bids: Sequence[float],
    asks: Sequence[float],
    **kwargs: Any,
) -> GateOutcome:
    outcome = gate_price_book(bids, asks, **kwargs)
    if not outcome.ok:
        raise ClosedLoopError(f"{outcome.verdict}: {outcome.reason}")
    return outcome
