"""
AetherRealm Economy Integrity Suite
====================================
Demonstrates balancelab + normsync + worldoracle working together to detect,
police, and reconcile problems in a live RPG crafting economy.

Three-part scenario:
  1. balancelab  -- Exploit detection: Bellman-Ford finds the iron_ore -> sword
                    -> gold -> iron_ore arbitrage loop (2x gain per cycle) and
                    recommend_fixes proposes a cooldown to neutralise it.
  2. normsync    -- Norm enforcement: a WorldNorm bans "exploit" actions in the
                    economy zone; NormMonitor fires a NormViolation when an AI
                    trading agent tries to run the loop.
  3. worldoracle -- Belief repair: blacksmith_anna and merchant_bob hold
                    contradictory beliefs about the sword market price
                    (50g vs 25g); ContradictionDetector surfaces the conflict and
                    BeliefRepairer resolves it by preferring the higher-confidence
                    source.

Run:
    pip install balancelab normsync worldoracle
    python 04_economy_integrity_suite.py
"""

from __future__ import annotations

import tempfile
import time

# ── balancelab ────────────────────────────────────────────────────────────────
from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.fixes import recommend_fixes

# ── normsync ──────────────────────────────────────────────────────────────────
from normsync.monitor import NormMonitor
from normsync.norm import AgentAction, WorldNorm
from normsync.store import NormStore

# ── worldoracle ───────────────────────────────────────────────────────────────
from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    WorldPredicate,
)
from worldoracle.store import WorldOracleStore

# ─────────────────────────────────────────────────────────────────────────────
SECTION = "=" * 60


def section(title: str) -> None:
    print(f"\n{SECTION}")
    print(f"  {title}")
    print(SECTION)


# ─────────────────────────────────────────────────────────────────────────────
# PART 1 — balancelab: exploit detection
# ─────────────────────────────────────────────────────────────────────────────

def run_balancelab() -> None:
    section("PART 1 — balancelab: AetherRealm economy exploit detection")

    # Build the crafting economy graph
    #   iron_ore --(smelt)--> iron_bar  : 2 ore -> 1 bar
    #   iron_bar --(forge)--> sword     : 3 bars -> 1 sword
    #   sword    --(sell) --> gold      : 1 sword -> 50 gold
    #   gold     --(buy)  --> iron_ore  : 10 gold -> 3 ore
    #
    # Cycle gain: (1/2) * (1/3) * 50 * (3/10) = 50/60 ≈ 0.83 -- no exploit yet.
    # Adjust sell rule to 1 sword -> 60 gold to create a profitable loop:
    # (1/2) * (1/3) * 60 * (3/10) = 60/60 = 1.0 -- still flat.
    # Set sell to 1 sword -> 80 gold so the loop yields > 1x gain:
    # (1/2) * (1/3) * 80 * (3/10) = 80/60 ≈ 1.33x -- exploit!
    graph = EconomyGraph()
    graph.add_rule(EconomyRule("iron_ore", "iron_bar", 2.0, 1.0, rule_id="smelt"))
    graph.add_rule(EconomyRule("iron_bar", "sword",    3.0, 1.0, rule_id="forge"))
    graph.add_rule(EconomyRule("sword",    "gold",     1.0, 80.0, rule_id="sell"))
    graph.add_rule(EconomyRule("gold",     "iron_ore", 10.0, 3.0, rule_id="buy"))

    print("\nEconomy rules loaded:")
    for rule in graph.rules:
        print(
            f"  [{rule.rule_id:6s}]  {rule.source_item:10s} -> {rule.target_item:10s}"
            f"  ({rule.source_qty}:{rule.target_qty}, rate={rule.exchange_rate():.3f}x)"
        )

    # Detect exploits via Bellman-Ford on log-weight graph
    finder = ExploitFinder()
    report = finder.find_exploits(graph)

    print(f"\nExploit scan complete — {report.graph_item_count} items, "
          f"{report.graph_rule_count} rules.")
    print(f"Exploits found: {report.total_found}")

    if report.total_found == 0:
        print("  Economy is balanced — no arbitrage cycles detected.")
        return

    for i, exploit in enumerate(report.exploits, 1):
        path_str = " -> ".join(exploit.path)
        print(f"\n  Exploit #{i}:")
        print(f"    Path:       {path_str}")
        print(f"    Gain ratio: {exploit.gain_ratio:.4f}x per cycle")
        print(f"    Rules used: {exploit.rules_used}")

    # Recommend fixes
    fixes = recommend_fixes(report)
    print(f"\nFix recommendations ({len(fixes)} fix(es)):")
    for fix in fixes:
        edge = f"{fix.target_edge[0]} -> {fix.target_edge[1]}" if fix.target_edge else "N/A"
        print(f"  Type:              {fix.fix_type}")
        print(f"  Target edge:       {edge}")
        if fix.suggested_value is not None:
            print(f"  Suggested value:   {fix.suggested_value:.4f}")
        print(f"  Est. reduction:    {fix.estimated_reduction_pct:.1f}%")
        print(f"  Description:       {fix.description}")


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — normsync: norm enforcement on AI trading agent
# ─────────────────────────────────────────────────────────────────────────────

def run_normsync() -> None:
    section("PART 2 — normsync: norm enforcement in the economy zone")

    # The economy zone has a norm prohibiting exploit actions
    no_exploit_norm = WorldNorm(
        name="no-economy-exploit",
        description="AI trading agents must not exploit arbitrage loops in the economy zone.",
        condition="economy_zone",
        prohibited="exploit",
        scope="economy_zone",
        priority=10,
    )

    # Also prohibit price manipulation
    no_manipulation_norm = WorldNorm(
        name="no-price-manipulation",
        description="Artificially manipulating market prices is forbidden.",
        condition="economy_zone",
        prohibited="manipulate",
        scope="economy_zone",
        priority=8,
    )

    # Wire up the monitor and in-memory store
    monitor = NormMonitor()
    monitor.add_norm(no_exploit_norm)
    monitor.add_norm(no_manipulation_norm)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = tmp_dir + "/normsync.db"
        store = NormStore(db_path)
        try:
            store.save_norm(no_exploit_norm)
            store.save_norm(no_manipulation_norm)

            print(f"\nActive norms loaded: {len(monitor.active_norms())}")
            for norm in monitor.active_norms():
                print(f"  [{norm.priority:2d}] {norm.name} — condition='{norm.condition}', "
                      f"prohibited='{norm.prohibited}'")

            # Simulate an AI trading bot attempting the arbitrage loop three times,
            # plus a legitimate trade action, plus a price manipulation attempt.
            actions = [
                AgentAction(
                    agent_id="trading_bot_alpha",
                    action="exploit",
                    location="economy_zone",
                    target="iron_ore->sword->gold loop",
                    metadata={"cycle": 1, "loop": "iron_ore->sword->gold->iron_ore"},
                    timestamp=time.time(),
                ),
                AgentAction(
                    agent_id="trading_bot_alpha",
                    action="exploit",
                    location="economy_zone",
                    target="iron_ore->sword->gold loop",
                    metadata={"cycle": 2, "loop": "iron_ore->sword->gold->iron_ore"},
                    timestamp=time.time() + 1.0,
                ),
                AgentAction(
                    agent_id="player_merchant_7",
                    action="trade",
                    location="economy_zone",
                    target="iron_bar",
                    metadata={"qty": 5, "price": 12},
                    timestamp=time.time() + 2.0,
                ),
                AgentAction(
                    agent_id="trading_bot_beta",
                    action="manipulate",
                    location="economy_zone",
                    target="sword_market_price",
                    metadata={"manipulation": "flood_sell_orders"},
                    timestamp=time.time() + 3.0,
                ),
                AgentAction(
                    agent_id="trading_bot_alpha",
                    action="exploit",
                    location="economy_zone",
                    target="iron_ore->sword->gold loop",
                    metadata={"cycle": 3, "loop": "iron_ore->sword->gold->iron_ore"},
                    timestamp=time.time() + 4.0,
                ),
            ]

            print("\nChecking agent actions against active norms:")
            all_violations = []
            for action in actions:
                violations = monitor.check(action)
                tag = "[!!]" if violations else "[ ok]"
                print(f"  {tag}  agent={action.agent_id:25s}  action={action.action:12s}  "
                      f"location={action.location}")
                for v in violations:
                    print(f"         -> Norm violated: '{v.norm_name}' (severity={v.severity})")
                    store.save_violation(v)
                    all_violations.append(v)

            print(f"\nTotal violations recorded: {len(all_violations)}")
            print(f"  trading_bot_alpha flagged "
                  f"{sum(1 for v in all_violations if v.agent_id == 'trading_bot_alpha')} time(s).")
            print(f"  trading_bot_beta  flagged "
                  f"{sum(1 for v in all_violations if v.agent_id == 'trading_bot_beta')} time(s).")
        finally:
            store.close()


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 — worldoracle: belief contradiction detection and repair
# ─────────────────────────────────────────────────────────────────────────────

def run_worldoracle() -> None:
    section("PART 3 — worldoracle: NPC belief contradiction detection and repair")

    # blacksmith_anna heard the sword price is 50g (from a traveling merchant,
    # earlier timestamp, moderate confidence).
    # merchant_bob saw the current order board and believes it is 25g
    # (direct observation, newer timestamp, higher confidence).
    #
    # We merge both beliefs into a shared "market_state" belief state to surface
    # the contradiction — this simulates a game system that aggregates NPC
    # knowledge for consistency checking.

    anna_belief = WorldPredicate(
        subject="sword_market_price",
        attribute="gold_value",
        value=50,
        source="hearsay",
        confidence=0.6,
        timestamp=1000.0,
    )

    bob_belief = WorldPredicate(
        subject="sword_market_price",
        attribute="gold_value",
        value=25,
        source="observation",
        confidence=0.95,
        timestamp=1500.0,
    )

    # Additional consistent beliefs both NPCs share
    iron_ore_price = WorldPredicate(
        subject="iron_ore_price",
        attribute="gold_value",
        value=3,
        source="observation",
        confidence=1.0,
        timestamp=900.0,
    )

    market_open = WorldPredicate(
        subject="economy_zone_market",
        attribute="is_open",
        value=True,
        source="observation",
        confidence=1.0,
        timestamp=800.0,
    )

    print("\nNPC beliefs before reconciliation:")
    print(f"  blacksmith_anna: sword_market_price.gold_value = {anna_belief.value}g "
          f"(source={anna_belief.source}, confidence={anna_belief.confidence}, "
          f"ts={anna_belief.timestamp})")
    print(f"  merchant_bob:    sword_market_price.gold_value = {bob_belief.value}g "
          f"(source={bob_belief.source}, confidence={bob_belief.confidence}, "
          f"ts={bob_belief.timestamp})")

    # Build individual belief states
    anna_state = BeliefState(npc_id="blacksmith_anna")
    anna_state.add(anna_belief)
    anna_state.add(iron_ore_price)
    anna_state.add(market_open)

    bob_state = BeliefState(npc_id="merchant_bob")
    bob_state.add(bob_belief)
    bob_state.add(iron_ore_price)   # shared consistent belief
    bob_state.add(market_open)      # shared consistent belief

    # Build a merged "market_state" belief state for contradiction detection
    market_state = BeliefState(npc_id="market_state")
    for pred in anna_state.predicates:
        market_state.add(pred)
    for pred in bob_state.predicates:
        market_state.add(pred)   # duplicate-safe: BeliefState.add deduplicates by id

    print(f"\nMerged market_state belief count: {len(market_state.predicates)} predicate(s)")

    # Detect contradictions
    detector = ContradictionDetector()
    contradictions = detector.detect(market_state)

    print(f"Contradictions detected: {len(contradictions)}")
    if not contradictions:
        print("  No contradictions found — market beliefs are consistent.")
    else:
        for a, b in contradictions:
            print(f"\n  CONFLICT on '{a.subject}.{a.attribute}':")
            print(f"    Belief A: value={a.value!r}, source={a.source}, "
                  f"confidence={a.confidence}, ts={a.timestamp}")
            print(f"    Belief B: value={b.value!r}, source={b.source}, "
                  f"confidence={b.confidence}, ts={b.timestamp}")

    # Repair contradictions
    repairer = BeliefRepairer()
    repairs = []
    for a, b in contradictions:
        frame = repairer.repair(a, b)
        repairs.append(frame)
        print(f"\n  Repair strategy:   {frame.strategy}")
        print(f"  Resolved value:    {frame.resolved_value!r}g")
        print(f"  Reason:            {frame.reason}")

    # Persist to SQLite (temp file cleaned up on exit)
    with tempfile.TemporaryDirectory() as tmp_dir:
        oracle_db = tmp_dir + "/worldoracle.db"
        store = WorldOracleStore(oracle_db)
        try:
            for pred in market_state.predicates:
                store.save_predicate("market_state", pred)
            for repair in repairs:
                store.save_repair(repair)

            loaded = store.get_belief_state("market_state")
            print(f"\nPersisted and reloaded: {len(loaded.predicates)} predicate(s) from SQLite.")
        finally:
            store.close()

    # Summary
    if repairs:
        resolved = repairs[0].resolved_value
        print(f"\nFinal canonical sword_market_price: {resolved}g")
        print("  (merchant_bob's direct observation overrides anna's hearsay.)")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    print(SECTION)
    print("  AetherRealm Economy Integrity Suite")
    print("  balancelab + normsync + worldoracle")
    print(SECTION)

    run_balancelab()
    run_normsync()
    run_worldoracle()

    print(f"\n{SECTION}")
    print("  All three integrity checks complete.")
    print("  AetherRealm economy is now monitored, policed, and consistent.")
    print(SECTION)


if __name__ == "__main__":
    main()
