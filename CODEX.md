# balancelab — Codex Developer Guide

> Read by OpenAI Codex CLI. Supplements AGENTS.md with Codex-specific conventions.

## What this project does

Adversarial game economy red-team — detect arbitrage exploits in game economies via Bellman-Ford graph analysis.

## Module map

```
src/balancelab/
├── economy.py     # EconomyRule, EconomyGraph, ExploitPath, ExploitReport, ExploitFinder
├── store.py       # EconomyStore — SQLite persistence for rules and reports
├── report.py      # print_report(), to_json(), to_markdown() formatters
├── cli.py         # Click CLI: add, scan, report, log, status
├── api.py         # FastAPI server: /rule, /rules, /scan, /reports, /health
└── mcp_server.py  # MCP server: add_rule, scan_economy, list_reports tools
```

## Build and test commands

```bash
make all        # lint + typecheck + test
make test       # pytest with coverage
make lint       # ruff check + ruff format --check
make typecheck  # mypy
make fmt        # ruff format (auto-fix)
make smoke      # end-to-end smoke test
```

## Key invariants — never change without tests

- `EconomyRule.id` = SHA-256[:16] of `source_item|target_item|source_qty|target_qty`
- `ExploitFinder` uses `weight = -log(exchange_rate)`; negative cycle = exploit
- `EconomyStore` uses `INSERT OR REPLACE` for upserts

## Code conventions

- Python 3.10+, fully type-annotated, mypy strict
- Ruff rules: E F I N UP S B RUF; ignore S101 in tests
- No `print()` in library code — use `rich.console.Console`
- All public functions and classes require docstrings

## What NOT to do

- Do not commit `coverage.xml` — it is in `.gitignore`
- Do not push without running `make all` first
- Do not bump `pyproject.toml` version — releases are cut by the maintainer from CHANGELOG
