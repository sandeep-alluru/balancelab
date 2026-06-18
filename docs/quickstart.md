# Quick Start

## Install

```bash
pip install balancelab
```

For the REST API:

```bash
pip install "balancelab[api]"
```

For MCP integration:

```bash
pip install "balancelab[mcp]"
```

## Step 1: Define Exchange Rules

Add exchange rules to the economy store:

```bash
balancelab add gold silver 1.0 3.0 --rule-id mint
balancelab add silver gems 1.0 2.0 --rule-id jeweler
balancelab add gems gold 1.0 4.0 --rule-id trader
```

## Step 2: Scan for Exploits

```bash
balancelab scan
```

Output:
```
Exploit Report (id: a3f8b2c1)
  Items: 3  Rules: 3
  Exploits found: 1
┌──────────────┬─────────────────────────────┬────────────┐
│ ID           │ Path                        │ Gain Ratio │
├──────────────┼─────────────────────────────┼────────────┤
│ 4d7e9c2a     │ gold → silver → gems → gold │ 24.00x     │
└──────────────┴─────────────────────────────┴────────────┘
```

## Python API

```python
from balancelab.economy import EconomyRule, EconomyGraph, ExploitFinder
from balancelab.report import print_report

graph = EconomyGraph()
graph.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
graph.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
graph.add_rule(EconomyRule("gems", "gold", 1.0, 4.0))

finder = ExploitFinder()
report = finder.find_exploits(graph)
print_report(report)
```

## CI Integration

Add to your CI pipeline:

```yaml
- name: Check economy balance
  run: |
    pip install balancelab
    balancelab scan --format json
```
