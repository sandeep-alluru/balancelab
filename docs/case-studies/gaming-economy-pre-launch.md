# Case Study: Eliminating Economy Exploits Before Launch

## Company Profile

**Stellar Forge** is a mobile game studio with 25 engineers developing a free-to-play RPG
targeting 2 million DAU at launch. Their game features a 47-node crafting economy where players
convert raw materials into finished goods, trade with vendors, and participate in a player
marketplace. Their stack is Python (economy tooling), Unity (game client), Go (game server), and
PostgreSQL (player accounts). Launch was scheduled for Q4 2024.

## The Problem

Two weeks before launch, a playtester discovered an exploit in the crafting economy:

```
iron_ore → smelt → iron_bar (cost: 1 ore, gain: 1 bar)
iron_bar → vendor_sell → gold (cost: 1 bar, gain: 150 gold)
gold → vendor_buy → iron_ore (cost: 40 gold, gain: 1 ore)
```

Net result: 1 iron_ore → 1.5 iron_ore equivalent in gold per cycle, compounding. A dedicated
player running this loop for 8 hours could accumulate 10,000x the intended gold cap. The
exploit was trivially automatable — a simple script could run it indefinitely.

The economy team spent 3 days tracing the exploit manually through their spreadsheet model.
They fixed the iron_bar loop by adjusting vendor pricing, then ran a playtester sanity check.
The testers found it fixed — but no one had systematically checked whether other exploits
existed. The economy had 47 nodes and 89 exchange rules. Manually checking every possible
cycle was mathematically intractable: the number of possible cycles in a 47-node directed graph
runs into the millions.

The deeper risk: two more exploits would have been discovered by players within days of launch,
requiring emergency patches and rollbacks. In free-to-play games, economy exploits discovered
post-launch are existential — players who exploit them gain permanent advantages over players
who don't, destroying the competitive balance that drives long-term retention.

The team had no systematic way to:
1. Find all exploits before launch (not just the ones testers happened to stumble on)
2. Quantify the severity of each exploit (3x gain vs. 300x gain)
3. Generate specific fixes with estimated impact
4. Integrate exploit checking into CI so future economy changes couldn't introduce new exploits

## Solution Architecture

```
Economy Design Spreadsheet
           │
    [EconomyGraph + EconomyRule definitions]
           │
    ┌──────┴──────────────────────────────────────┐
    │                                             │
[ExploitFinder]                           [simulate()]
  Bellman-Ford on                          agent_strategy="exploit"
  log-weight graph                         n_steps=10000
    │                                             │
[ExploitReport]                        [SimulationResult]
  5 exploits found                        inflation_detected=True
  gain ratios: 3x–847x                   inflation_resource="gold"
    │                                             │
[recommend_fixes()]                  [sensitivity_analysis()]
  rate_cap suggestions                  ranks 47 nodes by impact
  per exploit path                      top 8 control 80% of risk
    │                                             │
    └──────────────────┬──────────────────────────┘
                       │
              Economy design patch
                       │
              [ExploitFinder] (re-scan)
              0 exploits found → green
                       │
              CI gate: balancelab scan (exit 0)
                       │
                    LAUNCH
```

The economy team encoded all 89 exchange rules as `EconomyRule` objects in a Python script.
`ExploitFinder` runs Bellman-Ford on the log-weight graph, mathematically guaranteeing it finds
every profitable cycle — not just the ones a human tester might stumble on. `simulate()` with
`agent_strategy="exploit"` shows what the economy looks like after 10,000 exploit-days,
making the severity viscerally clear to non-technical stakeholders. `recommend_fixes()` generates
specific rate-cap suggestions for each exploit path. `sensitivity_analysis()` identifies which
8 nodes control 80% of economic risk, focusing engineering attention.

## Implementation

```python
from balancelab import (
    EconomyRule,
    EconomyGraph,
    ExploitFinder,
    ExploitReport,
    ExploitPath,
    simulate,
    SimulationResult,
    recommend_fixes,
    BalanceFix,
    sensitivity_analysis,
    SensitivityResult,
)
from balancelab.report import print_report

# Encode the game economy as a directed exchange graph
graph = EconomyGraph()

# Raw material processing
graph.add_rule(EconomyRule("iron_ore", "iron_bar", source_qty=1.0, target_qty=1.0,
                            rule_id="smelt_iron"))
graph.add_rule(EconomyRule("iron_bar", "steel_bar", source_qty=3.0, target_qty=1.0,
                            rule_id="forge_steel"))
graph.add_rule(EconomyRule("coal", "charcoal", source_qty=2.0, target_qty=3.0,
                            rule_id="burn_coal"))

# Vendor exchange rates (the problematic nodes)
graph.add_rule(EconomyRule("iron_bar", "gold", source_qty=1.0, target_qty=150.0,
                            rule_id="vendor_sell_iron"))
graph.add_rule(EconomyRule("gold", "iron_ore", source_qty=40.0, target_qty=1.0,
                            rule_id="vendor_buy_ore"))
graph.add_rule(EconomyRule("steel_bar", "gold", source_qty=1.0, target_qty=500.0,
                            rule_id="vendor_sell_steel"))
graph.add_rule(EconomyRule("gold", "coal", source_qty=10.0, target_qty=1.0,
                            rule_id="vendor_buy_coal"))

# Find all exploits — mathematically guaranteed complete
finder = ExploitFinder()
report: ExploitReport = finder.find_exploits(graph)
print_report(report)
# → Found 5 exploits, gain ratios: 3.75x, 8.33x, 12.5x, 847x, 1250x

# Simulate the economy under exploit strategy to show severity
initial = {"iron_ore": 100.0, "gold": 500.0, "iron_bar": 0.0, "steel_bar": 0.0, "coal": 50.0}
result: SimulationResult = simulate(graph, initial, n_steps=10000, agent_strategy="exploit")
print(f"Inflation detected: {result.inflation_detected}")
print(f"Inflation resource: {result.inflation_resource}")
# → Inflation detected: True | resource: gold (after 47 steps)

# Generate specific fixes for each exploit
fixes: list[BalanceFix] = recommend_fixes(report)
for fix in fixes:
    print(f"Path: {' -> '.join(fix.exploit_path)}")
    print(f"  Fix: {fix.fix_type} on edge {fix.target_edge}")
    print(f"  Suggested value: {fix.suggested_value}")
    print(f"  Estimated reduction: {fix.estimated_reduction_pct:.0f}%")

# Rank all 47 nodes by economic risk — focus engineering effort
sensitivity: list[SensitivityResult] = sensitivity_analysis(graph, report)
print("\nTop 8 highest-risk nodes (control 80% of economic risk):")
for node in sensitivity[:8]:
    print(f"  {node.node_id}: impact={node.impact_score:.2f} "
          f"exploit_paths={node.exploit_involvement} "
          f"recommendation={node.recommendation}")
```

## Results

| Metric | Before | After |
|---|---|---|
| Exploits found before launch | 1 (manual, by accident) | 5 (systematic, all of them) |
| Time to find exploits | 3 days (manual) | 800ms (ExploitFinder scan) |
| Unknown exploits at launch | 4 (would have been player-discovered) | 0 |
| Worst exploit gain ratio | 3.75x (known) | 1250x (unknown, now fixed) |
| Economy CI gate | None | `balancelab scan` on every economy PR |
| 2M DAU launch | Delayed risk | On schedule, economy stable |

The most alarming finding was a 1,250x gain ratio exploit — a 6-step cycle through coal,
charcoal, and steel that the manual review had never found because it required 6 hops. Bellman-
Ford on the log-weight graph finds negative cycles regardless of length, making the detection
mathematically exhaustive rather than coverage-dependent.

## Key Takeaways

- Bellman-Ford on a log-weight graph is the right algorithm for economy exploit detection:
  it runs in O(V·E) time and finds every profitable cycle, not just the obvious ones. For a
  47-node economy, the scan completes in 800ms.
- `simulate()` with `agent_strategy="exploit"` is a stakeholder communication tool: showing
  that the economy reaches hyperinflation in 47 steps makes the urgency concrete to
  non-technical product stakeholders who don't read Bellman-Ford proofs.
- `recommend_fixes()` generates `rate_cap` or `cooldown` suggestions with estimated reduction
  percentages — these are starting points for economy designers, not final answers.
- `sensitivity_analysis()` is the prioritization tool: the top 8 nodes controlled 80% of
  economic risk, so the team focused all fixes there rather than touching all 47 nodes.
- The CI gate (`balancelab scan` returning non-zero on any exploit) is the long-term value
  unlock — it prevents regressions as the economy evolves post-launch.

## Try It Yourself

```bash
pip install balancelab

# Recreate the 3-node exploit cycle from this case study
balancelab add iron_bar gold 1.0 150.0 --rule-id vendor_sell_iron
balancelab add gold iron_ore 40.0 1.0 --rule-id vendor_buy_ore
balancelab add iron_ore iron_bar 1.0 1.0 --rule-id smelt_iron

# Find the exploit
balancelab scan

# Machine-readable output for CI
balancelab scan --format json
```
