"""
mmo_economy_audit.py — Pre-launch balance audit for a fantasy MMO.

A game studio is about to ship "Kingdoms of Aethermoor" and needs a full
economy audit before going live. This script builds the MMO economy graph,
plants three known exploit paths (to validate the detector), then runs the
full exploit scan and prints a production-style balance report.

Run:
    python examples/mmo_economy_audit.py
"""
from __future__ import annotations

import sys
import time

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder, ExploitReport


# ── Helpers ───────────────────────────────────────────────────────────────────

def severity_tag(gain: float) -> str:
    if gain >= 4.0:
        return "CRITICAL"
    if gain >= 2.5:
        return "HIGH"
    if gain >= 1.5:
        return "MEDIUM"
    return "LOW"


def estimated_gold_per_hour(gain: float, base_gph: float) -> float:
    """Estimate gold/hour at exploit rate given a base activity rate."""
    return base_gph * gain


def hr(char: str = "─", width: int = 70) -> None:
    print(char * width)


# ── Economy Definition ────────────────────────────────────────────────────────

def build_mmo_economy() -> EconomyGraph:
    """
    Build the Kingdoms of Aethermoor economy graph.

    Resources:    gold_coins, guild_points, pvp_tokens, iron_ore, coal,
                  charcoal, iron_bars, steel_ingots, wood, herbs,
                  base_potion, super_potion, monster_drops, crafted_items
    Activities:   mining, smelting, crafting, combat, alchemy, trading
    """
    graph = EconomyGraph()

    # ── Standard intended flows ────────────────────────────────────────────
    # Mining/Smelting chain (intended: 10 iron_ore → 5 iron_bars, slow)
    graph.add_rule(EconomyRule("iron_ore", "iron_bars",
                               source_qty=2.0, target_qty=1.0,
                               rule_id="smelt-iron",
                               tags=["smelting", "crafting"]))

    # Iron bars → crafted items
    graph.add_rule(EconomyRule("iron_bars", "crafted_items",
                               source_qty=3.0, target_qty=1.0,
                               rule_id="forge-item",
                               tags=["crafting"]))

    # Crafted items sell for gold (intended: 1 item = 60 gold)
    graph.add_rule(EconomyRule("crafted_items", "gold_coins",
                               source_qty=1.0, target_qty=60.0,
                               rule_id="sell-crafted",
                               tags=["trading"]))

    # Wood → lumber → crafted furniture (alternative crafting path)
    graph.add_rule(EconomyRule("wood", "crafted_items",
                               source_qty=5.0, target_qty=1.0,
                               rule_id="carpenter",
                               tags=["crafting"]))

    # Monster drops → gold (combat loot)
    graph.add_rule(EconomyRule("monster_drops", "gold_coins",
                               source_qty=1.0, target_qty=25.0,
                               rule_id="loot-sell",
                               tags=["combat", "trading"]))

    # Combat awards guild points
    graph.add_rule(EconomyRule("monster_drops", "guild_points",
                               source_qty=1.0, target_qty=5.0,
                               rule_id="combat-guild",
                               tags=["combat", "guild"]))

    # Herbs → base potions (intended: 3 herbs = 1 base_potion)
    graph.add_rule(EconomyRule("herbs", "base_potion",
                               source_qty=3.0, target_qty=1.0,
                               rule_id="brew-base",
                               tags=["alchemy"]))

    # Base potions → gold_coins (sell to NPC vendor)
    graph.add_rule(EconomyRule("base_potion", "gold_coins",
                               source_qty=1.0, target_qty=20.0,
                               rule_id="sell-potion",
                               tags=["trading"]))

    # PvP tokens → guild points exchange (intended: balanced 1:1 ratio)
    graph.add_rule(EconomyRule("pvp_tokens", "guild_points",
                               source_qty=1.0, target_qty=1.0,
                               rule_id="pvp-to-guild",
                               tags=["pvp", "guild"]))

    # Guild points buy consumable items (gold-equivalent sink, 10 gp = 1 item worth 50g)
    graph.add_rule(EconomyRule("guild_points", "crafted_items",
                               source_qty=10.0, target_qty=1.0,
                               rule_id="guild-shop",
                               tags=["guild", "trading"]))

    # ── EXPLOIT A: Coal → charcoal → iron_bars bypass ─────────────────────
    # Design intent: players mine iron_ore and smelt it (2 ore → 1 bar, slow).
    # Bug: coal can be converted to charcoal (1:3), charcoal smelts iron at
    # 3x efficiency (3 charcoal → 3 bars).  Net: 1 coal → 3 bars vs intended
    # 6 ore → 3 bars.  Coal respawns 3x faster than iron ore → effective rate
    # 3x above the intended crafting-to-gold cap.
    graph.add_rule(EconomyRule("coal", "charcoal",
                               source_qty=1.0, target_qty=3.0,
                               rule_id="coal-to-charcoal",
                               tags=["smelting", "EXPLOIT_A"]))

    graph.add_rule(EconomyRule("charcoal", "iron_bars",
                               source_qty=1.0, target_qty=1.0,     # 3x efficient vs intended 2:1
                               rule_id="charcoal-smelt",
                               tags=["smelting", "EXPLOIT_A"]))

    # ── EXPLOIT B: Herb alchemy infinite loop ─────────────────────────────
    # super_potion sells for 4x more than base_potion; buy herbs with gold,
    # craft super_potions, sell → net positive cycle (intended: only NPC herbs
    # at fixed price, but the buy-back rate was set too high).
    graph.add_rule(EconomyRule("base_potion", "super_potion",
                               source_qty=1.0, target_qty=1.0,
                               rule_id="upgrade-potion",
                               tags=["alchemy", "EXPLOIT_B"]))

    graph.add_rule(EconomyRule("super_potion", "gold_coins",
                               source_qty=1.0, target_qty=90.0,    # 90g vs 20g for base potion
                               rule_id="sell-super-potion",
                               tags=["trading", "EXPLOIT_B"]))

    graph.add_rule(EconomyRule("gold_coins", "herbs",
                               source_qty=5.0, target_qty=4.0,     # buy herbs at 5g/4 (too cheap)
                               rule_id="buy-herbs",
                               tags=["trading", "EXPLOIT_B"]))

    # ── EXPLOIT C: Guild-point arbitrage loop ─────────────────────────────
    # gold_coins → pvp_tokens at 2:1 (intended event reward, not purchase).
    # pvp_tokens → guild_points 1:1, guild_points → crafted_items 10:1,
    # crafted_items → gold_coins 1:60.  Net per cycle starting with 20 gold:
    # 20g → 10 pvp_tokens → 10 gp → 1 item → 60g = 15% per cycle (unlimited).
    graph.add_rule(EconomyRule("gold_coins", "pvp_tokens",
                               source_qty=2.0, target_qty=1.0,
                               rule_id="buy-pvp-tokens",
                               tags=["pvp", "EXPLOIT_C"]))

    return graph


# ── Report ────────────────────────────────────────────────────────────────────

INTENDED_GPH = 333.0     # designers' target: ~333 gold/hour at normal play
GOLD_CAP_GPH = 1000.0    # hard rule: no path should yield >1000 gold/hour

# Approximate hourly gold value of 1 unit of each item (for rate estimation)
ITEM_GOLD_VALUE = {
    "gold_coins": 1.0,
    "iron_bars": 10.0,
    "crafted_items": 60.0,
    "super_potion": 90.0,
    "guild_points": 6.0,
}


def classify_exploits(report: ExploitReport) -> dict[str, list]:
    buckets: dict[str, list] = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
    for exploit in report.exploits:
        tag = severity_tag(exploit.gain_ratio)
        buckets[tag].append(exploit)
    return buckets


def print_exploit_detail(exploit, index: int, base_gph: float = INTENDED_GPH) -> None:
    tag = severity_tag(exploit.gain_ratio)
    path_str = " → ".join(exploit.path)
    exploit_gph = estimated_gold_per_hour(exploit.gain_ratio, base_gph)

    print(f"\n  [{index}] [{tag}] Cycle: {path_str}")
    print(f"       Gain ratio:    {exploit.gain_ratio:.2f}x")
    print(f"       Estimated GPH: {exploit_gph:,.0f}  (intended cap: {GOLD_CAP_GPH:,.0f})")
    print(f"       Overshoot:     {((exploit_gph / GOLD_CAP_GPH) - 1) * 100:.0f}% above cap")
    print(f"       Severity:      {tag}")
    print(f"       Rules used:    {len(exploit.rules_used)}")


def main() -> None:
    print()
    hr("═")
    print("  KINGDOMS OF AETHERMOOR — PRE-LAUNCH ECONOMY AUDIT")
    print("  Studio: Ironforge Games  |  Auditor: balancelab v0.1")
    print(f"  Date: {time.strftime('%Y-%m-%d %H:%M UTC')}")
    hr("═")

    print("\n[1/3] Building economy graph …")
    graph = build_mmo_economy()
    items = graph.items()
    print(f"      Items loaded:   {len(items)}")
    print(f"      Rules loaded:   {len(graph.rules)}")
    print(f"      Intent cap:     {GOLD_CAP_GPH:,.0f} gold/hour")

    print("\n[2/3] Running exploit scan (Bellman-Ford on log-weight graph) …")
    t0 = time.perf_counter()
    finder = ExploitFinder()
    report = finder.find_exploits(graph)
    elapsed = (time.perf_counter() - t0) * 1000

    print(f"      Scan complete in {elapsed:.1f} ms")
    print(f"      Items analysed:  {report.graph_item_count}")
    print(f"      Rules analysed:  {report.graph_rule_count}")
    print(f"      Exploits found:  {report.total_found}")

    print("\n[3/3] Generating balance report …")
    hr()

    buckets = classify_exploits(report)
    n_critical = len(buckets["CRITICAL"])
    n_high = len(buckets["HIGH"])
    n_medium = len(buckets["MEDIUM"])
    n_low = len(buckets["LOW"])

    print(
        f"\nBALANCE AUDIT: {report.total_found} exploit(s) found  "
        f"({n_critical} CRITICAL, {n_high} HIGH, {n_medium} MEDIUM, {n_low} LOW). "
        f"Fix before release:"
    )
    hr()

    for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        group = buckets[severity]
        if not group:
            continue
        print(f"\n  ── {severity} ({'fix immediately' if severity == 'CRITICAL' else 'fix before QA'}) ──")
        for i, exploit in enumerate(group, 1):
            print_exploit_detail(exploit, i)

    hr()
    # Exploit-specific narrative (matches the three planted exploits)
    print("\n  DESIGNER NOTES — root-cause analysis:")
    print()
    print("  [A] Coal→Charcoal→Iron bypass")
    print("      coal-to-charcoal rule converts 1 coal → 3 charcoal (3x).")
    print("      charcoal-smelt is 3x more efficient than iron-ore smelting.")
    print("      Combined with coal's faster respawn: effective GPH 3x cap.")
    print("      FIX: set charcoal-smelt to 2:1 (same ratio as iron-ore smelt).")
    print()
    print("  [B] Herb alchemy infinite loop")
    print("      gold → herbs buy-back rate (5g/4 herbs) too generous.")
    print("      super_potion sell price (90g) vs herb cost (3.75g/herb × 9 = 33.75g)")
    print("      creates 2.67x per 3-herb cycle — infinite compounding.")
    print("      FIX: raise buy-herbs cost to 15g/herb or lower super_potion sell to 30g.")
    print()
    print("  [C] Guild-point arbitrage")
    print("      gold → pvp_tokens purchase should not exist (tokens are PvP rewards only).")
    print("      Removing buy-pvp-tokens rule eliminates the loop entirely.")
    print("      FIX: delete rule buy-pvp-tokens (ID: buy-pvp-tokens).")
    hr()

    # Final verdict
    if n_critical > 0:
        print("\n  VERDICT: HOLD RELEASE — critical exploits present.")
        print("           Economy would be destroyed within 48 hours of launch.")
        sys.exit(1)
    elif n_high > 0:
        print("\n  VERDICT: DO NOT RELEASE — high-severity exploits present.")
        sys.exit(1)
    else:
        print("\n  VERDICT: Economy is stable — cleared for release.")


if __name__ == "__main__":
    main()
