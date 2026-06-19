"""
defi_protocol_audit.py — Pre-launch DeFi protocol economy audit.

A DeFi team is about to deploy "AetherFi" — an Ethereum-based DEX with
yield farming and governance.  Before launch, they run balancelab to detect
arbitrage loops, flash-loan attack vectors, and compounding exploits that
could drain the protocol's TVL (Total Value Locked).

This script models the protocol's token economy, plants three known exploit
patterns, runs the exploit detector, and prints a risk-graded audit report
suitable for sharing with auditors and the security council.

Run:
    python examples/defi_protocol_audit.py
"""
from __future__ import annotations

import time

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder, ExploitReport


# ── Protocol constants ─────────────────────────────────────────────────────────

# Intended protocol yields / exchange parameters
INTENDED_APY_PCT = 120.0          # 120 % APY on staking (generous but intended)
SWAP_FEE_RATE = 0.003             # 0.3 % per swap (Uniswap-style)

# Exposure caps used in the narrative
FLASH_LOAN_EXPOSURE_USD = 2_300_000
GOV_YIELD_OVERSHOOT_USD = 450_000   # value extractable from GOV loop in 30 days
LP_ARB_PCT_PER_CYCLE = 0.08         # 8 % per arbitrage cycle


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


def severity(gain: float) -> str:
    if gain >= 5.0:
        return "CRITICAL"
    if gain >= 2.5:
        return "HIGH"
    if gain >= 1.3:
        return "MEDIUM"
    return "LOW"


def build_defi_economy() -> EconomyGraph:
    """
    Build the AetherFi token economy graph.

    Assets:    ETH, USDC, GOV (governance token), LP_ETH_USDC, LP_GOV_ETH,
               borrowed_ETH (flash loan), yield_reward, liquidation_profit
    Actions:   swap, provide_liquidity, stake_lp, earn_gov, vote_yield_boost,
               borrow_flash, repay_flash, liquidate, sell_gov, buy_eth_cheap
    """
    graph = EconomyGraph()

    # ── Legitimate protocol flows ──────────────────────────────────────────

    # Swap ETH → USDC: 1 ETH = 2000 USDC, minus 0.3 % fee
    # 1 ETH → 1994 USDC (net)
    graph.add_rule(EconomyRule("ETH", "USDC",
                               source_qty=1.0, target_qty=1994.0,
                               rule_id="swap-eth-usdc",
                               tags=["dex", "swap"]))

    # Swap USDC → ETH: 1994 USDC → 0.994 ETH (round-trip loses to fees, balanced)
    graph.add_rule(EconomyRule("USDC", "ETH",
                               source_qty=1994.0, target_qty=0.994,
                               rule_id="swap-usdc-eth",
                               tags=["dex", "swap"]))

    # Provide ETH+USDC liquidity → receive LP_ETH_USDC tokens
    # 1 ETH + 2000 USDC → 1 LP_ETH_USDC
    graph.add_rule(EconomyRule("ETH", "LP_ETH_USDC",
                               source_qty=1.0, target_qty=1.0,
                               rule_id="add-liq-eth",
                               tags=["liquidity"]))

    # Stake LP tokens → earn yield_reward (intended: 0.12 GOV/hour per LP)
    graph.add_rule(EconomyRule("LP_ETH_USDC", "yield_reward",
                               source_qty=1.0, target_qty=0.12,
                               rule_id="stake-lp-earn",
                               tags=["staking", "yield"]))

    # yield_reward (GOV) → can be sold for ETH: 1 GOV = 5 ETH (intended market price)
    graph.add_rule(EconomyRule("yield_reward", "ETH",
                               source_qty=1.0, target_qty=5.0,
                               rule_id="sell-gov-eth",
                               tags=["dex", "governance"]))

    # GOV staking → vote for yield boost (1 GOV → 1 vote, vote boosts yield 1.5x)
    # Modelled as: 1 GOV → 1.5 yield_reward (the boosted output)
    graph.add_rule(EconomyRule("GOV", "yield_reward",
                               source_qty=1.0, target_qty=1.5,
                               rule_id="vote-yield-boost",
                               tags=["governance", "staking"]))

    # Earn GOV from protocol fees: 0.05 % of each swap allocated to GOV stakers
    graph.add_rule(EconomyRule("USDC", "GOV",
                               source_qty=2000.0, target_qty=0.5,
                               rule_id="fee-to-gov",
                               tags=["fee", "governance"]))

    # LP_GOV_ETH pool (separate pool for GOV/ETH): 1 GOV + 5 ETH → 1 LP_GOV_ETH
    graph.add_rule(EconomyRule("GOV", "LP_GOV_ETH",
                               source_qty=1.0, target_qty=1.0,
                               rule_id="add-liq-gov",
                               tags=["liquidity", "governance"]))

    # Remove ETH+USDC liquidity: 1 LP_ETH_USDC → 1 ETH (simplified: just ETH leg)
    graph.add_rule(EconomyRule("LP_ETH_USDC", "ETH",
                               source_qty=1.0, target_qty=0.998,
                               rule_id="remove-liq-eth",
                               tags=["liquidity"]))

    # ── EXPLOIT A: Flash loan sandwich attack ─────────────────────────────
    # 1. Borrow 1000 ETH via flash loan (cost = 0 upfront, 0.09% fee on repay)
    # 2. Buy ETH cheap by dumping USDC → moves price
    # 3. Liquidate undercollateralised positions at below-market prices
    # 4. Sell liquidated collateral at market price
    # 5. Repay flash loan
    # Net: liquidation_profit - flash_fee
    #
    # Model: borrowed_ETH (1 unit) → liquidation_profit (1.18 units ETH-equiv)
    #        via the price manipulation step (net 18% after fee)
    graph.add_rule(EconomyRule("borrowed_ETH", "buy_eth_cheap",
                               source_qty=1.0, target_qty=1.3,   # price impact: buy 30% below market
                               rule_id="flash-price-impact",
                               tags=["flash-loan", "EXPLOIT_A"]))

    graph.add_rule(EconomyRule("buy_eth_cheap", "liquidation_profit",
                               source_qty=1.0, target_qty=1.2,   # liquidation bonus 20%
                               rule_id="flash-liquidate",
                               tags=["flash-loan", "EXPLOIT_A"]))

    # Repay flash loan (0.09% fee): liquidation_profit → borrowed_ETH at cost
    # 1.56 liquidation_profit → 1.0 borrowed_ETH (repay), net keeps 0.56 ETH
    graph.add_rule(EconomyRule("liquidation_profit", "borrowed_ETH",
                               source_qty=1.56, target_qty=1.0,
                               rule_id="flash-repay",
                               tags=["flash-loan", "EXPLOIT_A"]))

    # ── EXPLOIT B: GOV token infinite compounding loop ────────────────────
    # 1. Stake GOV → vote for 2x yield boost (existing vote-yield-boost rule)
    # 2. Boosted yield (1.5x GOV/LP) → immediately re-staked as more GOV
    # 3. More GOV → more votes → higher boost → higher yield
    # 4. Compound: 120% APY becomes 340% with self-reinforcing boost
    #
    # Model: compound GOV → boosted yield_reward → more GOV via sell path
    # yield_reward → GOV conversion (buy back with proceeds):
    # 1 yield_reward (GOV) → 5 ETH → 2.5 GOV (at 2 GOV/ETH ratio when GOV price drops)
    graph.add_rule(EconomyRule("yield_reward", "GOV",
                               source_qty=1.0, target_qty=2.5,
                               rule_id="reinvest-gov",
                               tags=["governance", "EXPLOIT_B"]))

    # ── EXPLOIT C: LP token arbitrage between pools ───────────────────────
    # LP_ETH_USDC is priced differently on the protocol's DEX vs an external AMM.
    # Bot notices an 8% price gap: buy LP cheap internally, redeem for underlying,
    # sell underlying at external market price.
    # Model: LP_ETH_USDC (internal) → ETH (redeem) → LP_ETH_USDC (re-mint external)
    # at a 1.08x ratio (8% per cycle).
    graph.add_rule(EconomyRule("LP_GOV_ETH", "ETH",
                               source_qty=1.0, target_qty=5.5,   # 10% premium on external AMM
                               rule_id="arb-remove-gov-lp",
                               tags=["arbitrage", "EXPLOIT_C"]))

    # Re-mint LP_GOV_ETH internally at standard price (1 GOV + 5 ETH → 1 LP)
    graph.add_rule(EconomyRule("ETH", "LP_GOV_ETH",
                               source_qty=5.0, target_qty=1.0,
                               rule_id="arb-remint-gov-lp",
                               tags=["liquidity", "EXPLOIT_C"]))

    return graph


def print_audit_report(report: ExploitReport) -> None:
    hr("═")
    print()
    print("  AETHERFI PROTOCOL — PRE-LAUNCH ECONOMY AUDIT")
    print(f"  Auditor: balancelab | Items: {report.graph_item_count} | Rules: {report.graph_rule_count}")
    print()

    if report.total_found == 0:
        print("  RESULT: No exploit loops detected. Protocol cleared for launch.")
        hr("═")
        return

    # Categorise
    criticals = [e for e in report.exploits if severity(e.gain_ratio) == "CRITICAL"]
    highs     = [e for e in report.exploits if severity(e.gain_ratio) == "HIGH"]
    mediums   = [e for e in report.exploits if severity(e.gain_ratio) == "MEDIUM"]
    lows      = [e for e in report.exploits if severity(e.gain_ratio) == "LOW"]

    print(
        f"  DeFi PROTOCOL AUDIT: {report.total_found} exploit(s) found before launch."
    )
    print()

    # ── EXPLOIT A details ──────────────────────────────────────────────────
    flash_exploits = [e for e in report.exploits if any("borrowed_ETH" in e.path or
                      "liquidation_profit" in e.path for _ in [1])]
    if flash_exploits:
        e = flash_exploits[0]
        path_str = " → ".join(e.path)
        print(f"  [CRITICAL] Flash loan attack:")
        print(f"  Path:     {path_str}")
        print(f"  Gain:     {e.gain_ratio:.2f}x per loan cycle")
        print(f"  Exposure: ${FLASH_LOAN_EXPOSURE_USD:,.0f} (at 1000-ETH loan size)")
        print(f"  Impact:   Drains undercollateralised positions in a single block.")
        print()

    # ── EXPLOIT B details ──────────────────────────────────────────────────
    gov_exploits = [e for e in report.exploits if "GOV" in e.path and
                    "yield_reward" in e.path]
    if gov_exploits:
        e = gov_exploits[0]
        path_str = " → ".join(e.path)
        effective_apy = INTENDED_APY_PCT * e.gain_ratio
        print(f"  [HIGH] GOV token compounding loop:")
        print(f"  Path:     {path_str}")
        print(f"  Gain:     {e.gain_ratio:.2f}x  →  effective APY: {effective_apy:.0f}%  (intended: {INTENDED_APY_PCT:.0f}%)")
        print(f"  Exposure: ${GOV_YIELD_OVERSHOOT_USD:,.0f} extractable in 30 days")
        print(f"  Impact:   {(effective_apy/INTENDED_APY_PCT - 1)*100:.0f}% above intended yield. "
              f"GOV inflation crashes token price.")
        print()

    # ── EXPLOIT C details ──────────────────────────────────────────────────
    lp_exploits = [e for e in report.exploits if "LP_GOV_ETH" in e.path]
    if lp_exploits:
        e = lp_exploits[0]
        path_str = " → ".join(e.path)
        print(f"  [MEDIUM] LP token price arbitrage:")
        print(f"  Path:     {path_str}")
        print(f"  Gain:     {e.gain_ratio:.2f}x per cycle  ({LP_ARB_PCT_PER_CYCLE*100:.0f}% per cycle)")
        print(f"  Exposure: Bounded by LP_GOV_ETH pool size (currently ~$180k TVL)")
        print(f"  Impact:   Continuous extraction until pool is drained.  Bounded but reliable.")
        print()

    hr()
    print()
    print("  REMEDIATION PLAN:")
    print()
    print("  [A] Flash loan guard (CRITICAL — block deployment until fixed)")
    print("      Add re-entrancy guard + oracle price check before liquidation.")
    print("      Require price delta < 2% vs TWAP for any liquidation to proceed.")
    print("      Flash loans that move price >1% in a single block are reverted.")
    print()
    print("  [B] GOV yield cap (HIGH — fix in next governance vote)")
    print("      Cap boosted yield at 1.2x base rate regardless of vote count.")
    print("      Add 14-day time-lock on yield parameter changes via governance.")
    print("      Mint GOV only against verified external liquidity (not self-loops).")
    print()
    print("  [C] LP token price oracle (MEDIUM — fix before month 2)")
    print("      Use TWAP (time-weighted average price) for LP token valuation.")
    print("      Add mint/redeem delay of 1 block to prevent same-block arb.")
    print()

    hr("═")
    print()
    summary_lines = []
    if flash_exploits:
        summary_lines.append(
            f"Flash loan attack: CRITICAL (${FLASH_LOAN_EXPOSURE_USD/1e6:.1f}M exposure)"
        )
    if gov_exploits:
        e = gov_exploits[0]
        summary_lines.append(
            f"GOV loop: HIGH ({(e.gain_ratio * INTENDED_APY_PCT - INTENDED_APY_PCT):.0f}% above intended yield)"
        )
    if lp_exploits:
        summary_lines.append(
            f"LP arb: MEDIUM (bounded by pool size)"
        )

    print("  FINAL VERDICT: DO NOT DEPLOY — critical exploit present.")
    for line in summary_lines:
        print(f"  • {line}")
    print()
    print(f"  Total: {len(criticals)} CRITICAL, {len(highs)} HIGH, "
          f"{len(mediums)} MEDIUM, {len(lows)} LOW")
    hr("═")


def main() -> None:
    print()
    print("  AetherFi Protocol — Economy Audit")
    print(f"  Running at {time.strftime('%Y-%m-%d %H:%M UTC')}")
    print()

    print("  Building protocol economy graph …")
    graph = build_defi_economy()
    print(f"  Graph: {len(graph.items())} items, {len(graph.rules)} rules")

    print("  Scanning for arbitrage loops …")
    t0 = time.perf_counter()
    finder = ExploitFinder()
    report = finder.find_exploits(graph)
    elapsed = (time.perf_counter() - t0) * 1000
    print(f"  Scan complete: {elapsed:.1f} ms, {report.total_found} exploit(s) found")
    print()

    print_audit_report(report)


if __name__ == "__main__":
    main()
