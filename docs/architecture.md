# Architecture

balancelab is a pure-Python library for detecting arbitrage exploits in game economies.

## Module map

| File | Responsibility |
|------|---------------|
| `economy.py` | Core data model: `EconomyRule`, `EconomyGraph`, `ExploitPath`, `ExploitReport`, `ExploitFinder` |
| `store.py` | SQLite persistence: `EconomyStore` owns database connection, upserts rules and reports |
| `report.py` | Output formatters: `print_report()` (Rich terminal), `to_json()`, `to_markdown()` |
| `cli.py` | Click CLI: `add`, `scan`, `report`, `log`, `status` subcommands |
| `api.py` | FastAPI REST server: `/rule`, `/rules`, `/scan`, `/reports`, `/health` |
| `mcp_server.py` | MCP server: `add_rule`, `scan_economy`, `list_reports` tools |

## Data Flow

```
┌─────────────┐    add_rule()    ┌──────────────┐
│  User/CLI   │ ───────────────► │  EconomyStore│
│  /API/MCP   │                  │  (SQLite)    │
└─────────────┘                  └──────────────┘
                                        │
                                  list_rules()
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │ EconomyGraph │
                                 │ (in-memory)  │
                                 └──────────────┘
                                        │
                                 ExploitFinder
                                 .find_exploits()
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │ ExploitReport│
                                 │ exploits[]   │
                                 │ gain_ratio   │
                                 └──────────────┘
                                        │
                                  save_report()
                                        │
                                        ▼
                                 ┌──────────────┐
                                 │  EconomyStore│
                                 │  (SQLite)    │
                                 └──────────────┘
```

## Algorithm: Bellman-Ford on Log-Weight Graph

The key insight is:

1. Convert each exchange rate to a log-weight: `weight = -log(exchange_rate)`
2. A cycle with product of exchange rates > 1 becomes a negative-weight cycle
3. Bellman-Ford detects negative cycles in O(V·E) time

Example:
- gold → silver: rate = 3.0, weight = -log(3.0) = -1.099
- silver → gems: rate = 2.0, weight = -log(2.0) = -0.693
- gems → gold: rate = 4.0, weight = -log(4.0) = -1.386
- Cycle weight = -1.099 + (-0.693) + (-1.386) = -3.178 (negative = exploit!)
- Gain ratio = exp(3.178) = 24.0x

## Key Design Decisions

- **Pure Python, no NetworkX** — avoids external graph dependency, keeps install small
- **Content-addressed IDs** — SHA-256[:16] of rule parameters ensures idempotent storage
- **SQLite only** — zero setup, works offline, single file
- **Deduplicated exploits** — frozenset of path nodes prevents reporting the same cycle multiple times
