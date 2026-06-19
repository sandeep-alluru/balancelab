# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `simulate()` — run economy forward N steps with greedy/balanced/exploit strategies
- `SimulationStep` and `SimulationResult` dataclasses for step-by-step economy tracking
- `recommend_fixes()` — generate minimum fix recommendations for each exploit (rate_cap, cooldown, daily_limit, require_prerequisite)
- `BalanceFix` dataclass with estimated_reduction_pct
- `sensitivity_analysis()` — rank all economy nodes by impact score
- `critical_path()` — find highest-throughput node sequence
- `SensitivityResult` dataclass with recommendation field
- CLI: `balancelab simulate <graph_file>` and `balancelab fixes` commands

## [0.1.0] - 2026-06-18

### Added
- Content-addressed `EconomyRule` and `EconomyGraph` data model backed by SQLite
- `ExploitFinder` — Bellman-Ford arbitrage detection on log-weight directed graph
- `ExploitPath` and `ExploitReport` with full serialization
- `EconomyStore` — SQLite persistence for rules and reports with upsert support
- Rich terminal output, JSON, and Markdown report formatters
- Click CLI: `add`, `scan`, `report`, `log`, `status` subcommands
- FastAPI REST server: `/rule`, `/rules`, `/scan`, `/reports`, `/health` endpoints
- MCP server (`balancelab-mcp`) for native Claude tool integration
- OpenAI function calling spec in `tools/openai-tools.json`
- Full OpenAPI 3.1 spec in `openapi.yaml`
- GitHub Action for economy scanning in CI
- 45 tests across 6 test modules, 85%+ branch coverage

[Unreleased]: https://github.com/sandeep-alluru/balancelab/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/balancelab/releases/tag/v0.1.0
