# balancelab — Session Anchor

**One-liner:** Adversarial game economy red-team — detect arbitrage exploits via graph-based analysis
**Phase:** v0.1.0 shipped
**Stack:** Python 3.10+, click, rich, sqlite3, fastapi

## Key decisions

- Bellman-Ford on log-weight graph (weight = -log(exchange_rate)) detects negative cycles = exploits
- Content-addressed IDs (SHA-256[:16]) for deduplication
- SQLite-only backend — no network dependencies
- Pure Python — no NetworkX or external graph libraries

## Module map

```
src/balancelab/
├── economy.py     # EconomyRule, EconomyGraph, ExploitFinder (Bellman-Ford)
├── store.py       # EconomyStore (SQLite CRUD)
├── report.py      # print_report, to_json, to_markdown
├── cli.py         # add, scan, report, log, status
├── api.py         # FastAPI REST server
└── mcp_server.py  # MCP server (optional dependency)
```

## Next step
Extend with severity scoring: classify exploits as critical/high/medium based on gain_ratio thresholds.

## Code conventions
- Python 3.10+, fully type-annotated, mypy strict
- Ruff rules: E F I N UP S B RUF
- No `print()` in library code — use `rich.console.Console`
- All public functions and classes require docstrings
