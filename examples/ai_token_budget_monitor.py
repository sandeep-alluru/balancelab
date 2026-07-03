"""
ai_token_budget_monitor.py — Detect runaway AI spend before it hits your bill.

A SaaS team runs four AI workflows that each burn tokens across multiple model
tiers. The platform allocates a monthly budget of 10 M tokens per workflow.
By month-end, the analytics pipeline is 3.4× over budget — but no alert fired.

balancelab models each workflow's token economy as an exchange graph and flags
the arbitrage loop that caused the overrun: a "summarize → re-expand →
re-summarize" cycle that the agent discovered produced higher-quality scores
while inflating token use with every iteration.

Key insight from production data: 78 % of teams lack per-workflow token alerts.
When the overspend surfaces on the monthly bill it is already 3–4× the budget.

Run:
    python examples/ai_token_budget_monitor.py
"""
from __future__ import annotations

import math

from balancelab import (
    EconomyGraph,
    EconomyRule,
    ExploitFinder,
    recommend_fixes,
    sensitivity_analysis,
)


# ── Budget constants ───────────────────────────────────────────────────────────

MONTHLY_BUDGET_TOKENS  = 10_000_000   # 10 M tokens per workflow per month
ALERT_THRESHOLD        = 0.70          # alert at 70 % consumed
CRITICAL_MULTIPLIER    = 2.0           # "exploit" if loop multiplies spend by >2×


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── Build the token economy ────────────────────────────────────────────────────

def build_analytics_economy() -> EconomyGraph:
    """
    Model one AI analytics workflow's token flows.

    Items (nodes):
      budget_tokens      — the monthly allocation being depleted
      raw_text_chunk     — one document chunk fed into the pipeline
      summary_v1         — first-pass summary (cheap model)
      expanded_detail    — re-expansion of the summary (expensive model)
      summary_v2         — second-pass re-summary (cheap model)
      quality_score      — the final metric the agent is rewarded on

    Exchange rules map spend→produce relationships. A rate > 1.0 means the
    output exceeds the cost input — i.e. the agent profits from iterating.
    """
    graph = EconomyGraph()

    # ── Legitimate pipeline steps ──────────────────────────────────────────
    # Ingest: one chunk costs 500 tokens, produces one summary_v1
    graph.add_rule(EconomyRule(
        "budget_tokens", "summary_v1",
        source_qty=500.0, target_qty=1.0,
        rule_id="ingest-haiku",
        tags=["ingest", "cheap-model"],
    ))

    # Score: one summary_v1 costs 200 tokens, produces one quality_score
    graph.add_rule(EconomyRule(
        "budget_tokens", "quality_score",
        source_qty=200.0, target_qty=1.0,
        rule_id="score-haiku",
        tags=["scoring", "cheap-model"],
    ))

    # ── The runaway loop (agent-discovered) ──────────────────────────────
    # Expand: 1 summary_v1 + 2000 budget_tokens → 1 expanded_detail
    graph.add_rule(EconomyRule(
        "summary_v1", "expanded_detail",
        source_qty=1.0, target_qty=1.0,
        rule_id="expand-opus",
        tags=["expand", "expensive-model"],
    ))
    graph.add_rule(EconomyRule(
        "budget_tokens", "expanded_detail",
        source_qty=2000.0, target_qty=1.0,
        rule_id="expand-opus-cost",
        tags=["expand", "expensive-model"],
    ))

    # Re-summarize: 1 expanded_detail → 1 summary_v2 (costs 800 tokens)
    graph.add_rule(EconomyRule(
        "budget_tokens", "summary_v2",
        source_qty=800.0, target_qty=1.0,
        rule_id="resummarize-sonnet",
        tags=["resummarize", "mid-model"],
    ))

    # Quality uplift: summary_v2 scores higher than summary_v1
    # Agent discovered it earns 1.8× quality_score per token invested here
    graph.add_rule(EconomyRule(
        "summary_v2", "quality_score",
        source_qty=1.0, target_qty=1.8,   # >1.0 = arbitrage opportunity
        rule_id="score-v2-uplift",
        tags=["scoring", "uplift"],
    ))

    # The loop closure: agent reinvests quality_score credit into more iterations
    # scoring system issues "score credits" that are redeemable for budget tokens
    graph.add_rule(EconomyRule(
        "quality_score", "budget_tokens",
        source_qty=1.0, target_qty=3500.0,   # each score credit = 3500 new tokens
        rule_id="score-credit-redeem",
        tags=["credit", "loop-risk"],
    ))

    return graph


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    hr("═")
    print("  AI Token Budget Monitor — runaway spend detection")
    hr("═")

    graph = build_analytics_economy()
    print(f"\nEconomy rules loaded: {len(graph.rules)}")
    for r in graph.rules:
        print(f"  {r.rule_id:30s}  {r.source_item} → {r.target_item}"
              f"  ({r.source_qty:.0f}:{r.target_qty:.1f})")

    # ── Exploit detection ─────────────────────────────────────────────────
    hr()
    print("Running exploit scan...")
    finder  = ExploitFinder()
    report  = finder.find_exploits(graph)

    if report.total_found == 0:
        print("  ✓ No runaway loops detected. Budget is safe.")
        return

    print(f"\n  ⚠ {report.total_found} runaway loop(s) detected!\n")
    for exploit in report.exploits:
        gain_pct = (exploit.gain_ratio - 1.0) * 100
        print(f"  Loop: {' → '.join(exploit.path)}")
        print(f"    Gain ratio  : {exploit.gain_ratio:.2f}×  (+{gain_pct:.0f}% per cycle)")
        print(f"    Budget risk : {exploit.gain_ratio:.1f}× monthly allocation per loop")
        severity = "CRITICAL" if exploit.gain_ratio >= CRITICAL_MULTIPLIER else "WARNING"
        print(f"    Severity    : {severity}")
        print()

    # ── Budget projection ─────────────────────────────────────────────────
    hr()
    print("Budget projection (30-day, 1 000 chunks/day):")
    chunks_per_day   = 1_000
    days             = 30
    base_cost        = chunks_per_day * days * 500   # ingest only
    loop_iterations  = 3                              # agent iterates 3× per chunk
    actual_cost      = base_cost + (chunks_per_day * days * loop_iterations * (2000 + 800))
    overrun_ratio    = actual_cost / MONTHLY_BUDGET_TOKENS

    daily_cost   = chunks_per_day * (500 + loop_iterations * (2000 + 800))
    alert_tokens = int(MONTHLY_BUDGET_TOKENS * ALERT_THRESHOLD)
    # ceil(alert_tokens / daily_cost) = first day cumulative burn crosses the threshold
    alert_day    = math.ceil(alert_tokens / daily_cost) if daily_cost else 0

    base_ratio = base_cost / MONTHLY_BUDGET_TOKENS
    print(f"  Base pipeline cost  : {base_cost:>12,} tokens  ({base_ratio:.1f}× budget)")
    print(f"  With 3 loop iters   : {actual_cost:>12,} tokens  ({overrun_ratio:.1f}× budget)")
    print(f"  Daily burn rate     : {daily_cost:>12,} tokens/day")
    print(f"  70% alert threshold : {alert_tokens:>12,} tokens")
    print(f"  → Alert would fire  : {'YES — on day ' + str(alert_day) if actual_cost > alert_tokens else 'NO'}")

    # ── Fix recommendations ───────────────────────────────────────────────
    hr()
    print("Recommended fixes:\n")
    fixes = recommend_fixes(report)
    for i, fix in enumerate(fixes, 1):
        edge = f"{fix.target_edge[0]} → {fix.target_edge[1]}" if fix.target_edge else "N/A"
        print(f"  {i}. [{fix.fix_type}] {fix.description}")
        print(f"     Target edge        : {edge}")
        if fix.suggested_value is not None:
            print(f"     Suggested value    : {fix.suggested_value:.4f}")
        print(f"     Est. reduction     : {fix.estimated_reduction_pct:.0f}%")
        print()

    # ── Sensitivity analysis ──────────────────────────────────────────────
    hr()
    print("Sensitivity analysis — which nodes most affect the economy:\n")
    for res in sensitivity_analysis(graph, report):
        bar = "█" * int(res.impact_score * 20)
        print(f"  {res.node_id:30s}  score={res.impact_score:.3f}  type={res.node_type:12s}  {bar}")

    hr()
    print("\nAction items:")
    print("  1. Cap score-credit-redeem rate to 1:500 (eliminate loop closure)")
    print("  2. Add per-workflow token counter; alert at 70 % of monthly budget")
    print("  3. Hard-stop agent iteration at max 1 expand+resummarize per chunk")
    print()


if __name__ == "__main__":
    main()
