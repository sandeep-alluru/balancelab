# balancelab — Agent Context

This file describes the project architecture for AI coding assistants (Claude Code, Cursor, Copilot).

## What this project does

Adversarial game economy red-team — detect arbitrage exploits in game economies via graph-based analysis.

## Module map

```
src/balancelab/
├── __init__.py       # Public API exports: EconomyRule, EconomyGraph, ExploitFinder, ExploitPath, ExploitReport
├── economy.py        # Core data model: EconomyRule, EconomyGraph, ExploitPath, ExploitReport, ExploitFinder
├── store.py          # SQLite persistence: EconomyStore (save/get/list for rules and reports)
├── report.py         # Output formatters: print_report(), to_json(), to_markdown()
├── cli.py            # Click CLI: add, scan, report, log, status subcommands
├── api.py            # FastAPI server: /rule, /rules, /scan, /reports, /health endpoints
└── mcp_server.py     # MCP server: add_rule, scan_economy, list_reports tools
```

## Key invariants

- `EconomyRule.id` is SHA-256[:16] of `source_item|target_item|source_qty|target_qty` — same rule always same ID
- `ExploitFinder` uses Bellman-Ford on log-weight graph: negative cycle = positive gain cycle
- `ExploitFinder.find_exploits()` deduplicates by frozenset of path nodes
- All library code uses `rich.console.Console` — never `print()`
- `EconomyStore` uses SQLite with upsert (INSERT OR REPLACE)

## Testing

```bash
make test       # full test suite
make lint       # ruff check + format
make typecheck  # mypy
make smoke      # end-to-end smoke test
make all        # everything
```

## What NOT to change without careful thought

- `EconomyRule.id` computation — changing it breaks all stored rules
- `ExploitFinder` algorithm — must correctly detect negative cycles
- `EconomyStore` schema — requires migration if changed
