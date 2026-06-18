# GitHub Copilot Instructions — balancelab

balancelab: Adversarial game economy red-team — detect arbitrage exploits via graph-based analysis.

## Module map

```
src/balancelab/
├── economy.py     # EconomyRule, EconomyGraph, ExploitPath, ExploitReport, ExploitFinder
├── store.py       # EconomyStore — SQLite persistence for rules and reports
├── report.py      # print_report(), to_json(), to_markdown() formatters
├── cli.py         # Click CLI: add, scan, report, log, status
├── api.py         # FastAPI server: /rule, /rules, /scan, /reports, /health
└── mcp_server.py  # MCP server: add_rule, scan_economy, list_reports
```

## Key invariants

- `EconomyRule.id` = SHA-256[:16] of `source_item|target_item|source_qty|target_qty`
- `ExploitFinder` uses `weight = -log(exchange_rate)`; negative cycle = positive gain
- No `print()` in library code — use `rich.console.Console`

## Code style

- Python 3.10+, type-annotated, mypy strict mode
- Ruff lint rules: E F I N UP S B RUF; ignore S101 in tests
- All public classes and functions must have docstrings
- Tests use `pytest`; CLI tests use `click.testing.CliRunner`

## Adding a new output format

1. Add `to_<format>(result) -> str` in `report.py`
2. Add format name to `--format` choices in `cli.py`
3. Add tests

## Adding a new integration

1. Create `src/balancelab/<integration>.py`
2. Export from `__init__.py`, add to `__all__` alphabetically
3. Add tests
