# balancelab Architecture

This document describes the internals of balancelab: data flow, module responsibilities, SQLite schema, and the exploit detection algorithm.

---

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
                              ExploitFinder.find_exploits()
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

---

## Module Map

| File | Responsibility |
|------|---------------|
| `economy.py` | Core data model and algorithm: `EconomyRule`, `EconomyGraph`, `ExploitPath`, `ExploitReport`, `ExploitFinder` |
| `store.py` | SQLite persistence: `EconomyStore` owns the database connection |
| `report.py` | Output formatters: `print_report()` (Rich), `to_json()`, `to_markdown()` |
| `cli.py` | Click CLI: `add`, `scan`, `report`, `log`, `status` |
| `api.py` | FastAPI REST server |
| `mcp_server.py` | MCP server (optional, requires `mcp` package) |

---

## SQLite Schema

```sql
CREATE TABLE economy_rules (
    id TEXT PRIMARY KEY,          -- SHA-256[:16] of rule parameters
    source_item TEXT NOT NULL,
    target_item TEXT NOT NULL,
    source_qty REAL NOT NULL,
    target_qty REAL NOT NULL,
    rule_id TEXT,                 -- human-readable label
    tags TEXT                     -- JSON array
);

CREATE TABLE exploit_reports (
    id TEXT PRIMARY KEY,          -- SHA-256[:16] of report metadata
    graph_item_count INTEGER NOT NULL,
    graph_rule_count INTEGER NOT NULL,
    total_found INTEGER NOT NULL,
    timestamp REAL NOT NULL,
    exploits TEXT NOT NULL        -- JSON array of ExploitPath dicts
);
```

---

## Exploit Detection Algorithm

### Overview

The key insight is that game economy arbitrage can be expressed as a shortest-path problem. By converting exchange rates to log-weights and negating them, a profitable trade cycle becomes a negative-weight cycle in a directed graph.

### Steps

1. **Build log-weight graph**: For each `EconomyRule`, compute `weight = -log(exchange_rate)` where `exchange_rate = target_qty / source_qty`.

2. **Bellman-Ford relaxation**: For each possible starting node, run V-1 relaxation steps. Each step updates `dist[v] = min(dist[v], dist[u] + weight(u, v))`.

3. **Negative cycle detection**: On the V-th iteration, if any distance can still be improved (`dist[u] + w < dist[v]`), a negative cycle exists.

4. **Cycle tracing**: Follow the predecessor chain back to identify the cycle nodes.

5. **Gain ratio computation**: `gain_ratio = exp(-cycle_weight) = product of exchange_rates around the cycle`.

### Example

For gold → silver (3x) → gems (2x) → gold (4x):
- Cycle weight = -log(3) + (-log(2)) + (-log(4)) = -log(24) ≈ -3.178
- Gain ratio = exp(3.178) ≈ 24.0x

### Complexity

- Time: O(V · E) per starting node, O(V²E) total (typically fast for small economies)
- Space: O(V + E)
