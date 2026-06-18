"""
End-to-end smoke test for balancelab.

Simulates a user who just cloned the repo and wants to verify everything works.
No mocking, no fixtures — real behaviour, real CLI, real HTTP server.

Run from repo root:
    python smoke_test.py
    python smoke_test.py --verbose

Exit 0 = all passed. Exit 1 = at least one failure.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

# ── Colours ───────────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

VERBOSE = "--verbose" in sys.argv or "-v" in sys.argv
REPO_ROOT = Path(__file__).parent
PYTHON = sys.executable

passed: list[str] = []
failed: list[tuple[str, str]] = []


def ok(name: str) -> None:
    passed.append(name)
    print(f"  {GREEN}✓{RESET} {name}")


def fail(name: str, reason: str) -> None:
    failed.append((name, reason))
    print(f"  {RED}✗{RESET} {name}")
    if VERBOSE:
        print(f"    {YELLOW}{reason}{RESET}")


def section(title: str) -> None:
    print(f"\n{BOLD}{title}{RESET}")


def run(name: str, fn):  # noqa: ANN001
    try:
        fn()
        ok(name)
    except Exception as exc:
        reason = str(exc) if not VERBOSE else traceback.format_exc().strip()
        fail(name, reason)


# ── 1. Package import ─────────────────────────────────────────────────────────

section("1. Package import")


def _test_import_version() -> None:
    import balancelab
    assert balancelab.__version__, "__version__ is empty"
    assert balancelab.__version__ != "0.0.0"


def _test_import_public_api() -> None:
    from balancelab import EconomyRule, EconomyGraph, ExploitFinder, ExploitPath, ExploitReport
    assert callable(ExploitFinder)
    assert callable(EconomyGraph)


run("balancelab package imports", _test_import_version)
run("Public API (EconomyRule, EconomyGraph, ExploitFinder, ExploitPath, ExploitReport)", _test_import_public_api)


# ── 2. Core data model ────────────────────────────────────────────────────────

section("2. Core data model (EconomyRule, ExploitPath, ExploitReport)")


def _test_rule_content_addressed() -> None:
    from balancelab.economy import EconomyRule
    r1 = EconomyRule("gold", "silver", 1.0, 3.0)
    r2 = EconomyRule("gold", "silver", 1.0, 3.0)
    assert r1.id == r2.id, "Same rule must produce same ID"
    r3 = EconomyRule("gold", "silver", 1.0, 4.0)
    assert r1.id != r3.id


def _test_rule_exchange_rate() -> None:
    from balancelab.economy import EconomyRule
    r = EconomyRule("gold", "silver", 2.0, 6.0)
    assert r.exchange_rate() == 3.0


def _test_rule_serialization() -> None:
    from balancelab.economy import EconomyRule
    r = EconomyRule("gold", "silver", 1.0, 3.0, rule_id="mint", tags=["trade"])
    d = r.to_dict()
    r2 = EconomyRule.from_dict(d)
    assert r2.id == r.id
    assert r2.source_item == "gold"


def _test_exploit_path_content_addressed() -> None:
    from balancelab.economy import ExploitPath
    e1 = ExploitPath(["gold", "silver", "gold"], ["r1", "r2"], 3.0)
    e2 = ExploitPath(["gold", "silver", "gold"], ["r1", "r2"], 3.0)
    assert e1.id == e2.id


def _test_exploit_report_to_dict() -> None:
    from balancelab.economy import ExploitReport
    r = ExploitReport(3, 3, [], 0)
    d = r.to_dict()
    assert "exploits" in d
    assert "timestamp" in d
    assert d["total_found"] == 0


run("EconomyRule content-addressing (same triple = same ID)", _test_rule_content_addressed)
run("EconomyRule.exchange_rate() = target_qty / source_qty", _test_rule_exchange_rate)
run("EconomyRule serializes and loads correctly", _test_rule_serialization)
run("ExploitPath content-addressing", _test_exploit_path_content_addressed)
run("ExploitReport.to_dict() returns expected structure", _test_exploit_report_to_dict)


# ── 3. ExploitFinder ─────────────────────────────────────────────────────────

section("3. ExploitFinder (Bellman-Ford arbitrage detection)")


def _test_finds_exploit() -> None:
    from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
    g.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
    g.add_rule(EconomyRule("gems", "gold", 1.0, 4.0))
    finder = ExploitFinder()
    report = finder.find_exploits(g)
    assert report.total_found > 0
    assert report.exploits[0].gain_ratio > 20.0, f"Expected gain > 20x, got {report.exploits[0].gain_ratio}"


def _test_no_exploit_balanced() -> None:
    from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
    g.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
    g.add_rule(EconomyRule("gems", "gold", 6.0, 1.0))
    finder = ExploitFinder()
    report = finder.find_exploits(g)
    assert report.total_found == 0, f"Expected 0 exploits, got {report.total_found}"


def _test_empty_graph() -> None:
    from balancelab.economy import EconomyGraph, ExploitFinder
    finder = ExploitFinder()
    report = finder.find_exploits(EconomyGraph())
    assert report.total_found == 0
    assert report.graph_item_count == 0


run("ExploitFinder finds gold→silver→gems→gold exploit (24x)", _test_finds_exploit)
run("ExploitFinder returns 0 exploits on balanced graph", _test_no_exploit_balanced)
run("ExploitFinder handles empty graph", _test_empty_graph)


# ── 4. Output formatters ─────────────────────────────────────────────────────

section("4. Output formatters (to_json, to_markdown, print_report)")


def _test_to_json() -> None:
    from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
    from balancelab.report import to_json
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
    g.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
    g.add_rule(EconomyRule("gems", "gold", 1.0, 4.0))
    report = ExploitFinder().find_exploits(g)
    result = to_json(report)
    parsed = json.loads(result)
    assert "total_found" in parsed
    assert parsed["total_found"] > 0


def _test_to_markdown() -> None:
    from balancelab.economy import ExploitReport
    from balancelab.report import to_markdown
    r = ExploitReport(3, 3, [], 0)
    md = to_markdown([r])
    assert "|" in md
    assert "balancelab" in md


def _test_print_report() -> None:
    import io
    from rich.console import Console
    from balancelab.economy import ExploitReport
    from balancelab.report import print_report
    buf = io.StringIO()
    console = Console(file=buf, highlight=False)
    print_report(ExploitReport(3, 3, [], 0), console=console)
    assert len(buf.getvalue()) > 0


run("to_json() returns valid JSON with total_found > 0", _test_to_json)
run("to_markdown() produces Markdown with table", _test_to_markdown)
run("print_report() outputs report to console", _test_print_report)


# ── 5. CLI ────────────────────────────────────────────────────────────────────

section("5. CLI (balancelab)")


def _test_cli_help() -> None:
    r = subprocess.run(
        [PYTHON, "-m", "balancelab.cli", "--help"],
        capture_output=True, text=True
    )
    assert r.returncode == 0
    assert len(r.stdout) > 20, "Help output is empty"


run("balancelab --help returns 0", _test_cli_help)


# ── 6. FastAPI server ─────────────────────────────────────────────────────────

section("6. FastAPI server (balancelab[api])")


def _test_api_import() -> None:
    from balancelab.api import app
    assert app.title == "balancelab API"


def _test_api_health() -> None:
    from fastapi.testclient import TestClient
    from balancelab.api import app
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "version" in r.json()


run("balancelab.api imports and app.title is correct", _test_api_import)
run("GET /health returns {status: ok, version: ...}", _test_api_health)


# ── 7. MCP server ─────────────────────────────────────────────────────────────

section("7. MCP server (balancelab[mcp])")


def _test_mcp_server_importable() -> None:
    import balancelab.mcp_server as m
    assert hasattr(m, "run_server")


def _test_mcp_server_loads_cleanly() -> None:
    import balancelab.mcp_server  # noqa: F401


run("mcp_server.py imports without error", _test_mcp_server_importable)
run("mcp_server module loads cleanly (no import-time crash)", _test_mcp_server_loads_cleanly)


# ── 8. Agent config files ─────────────────────────────────────────────────────

section("8. Agent config files (what a clone gives you)")


def _check_file_nonempty(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    assert p.stat().st_size > 50, f"File too small (likely empty): {rel}"


def _check_json_valid(rel: str) -> None:
    p = REPO_ROOT / rel
    assert p.exists(), f"Missing: {rel}"
    json.loads(p.read_text())


def _check_yaml_parseable(rel: str) -> None:
    try:
        import yaml  # type: ignore[import-untyped]
        p = REPO_ROOT / rel
        assert p.exists(), f"Missing: {rel}"
        yaml.safe_load(p.read_text())
    except ImportError:
        content = (REPO_ROOT / rel).read_text()
        assert len(content) > 20, f"File appears empty: {rel}"


def _test_claude_commands() -> None:
    commands = list((REPO_ROOT / ".claude/commands").glob("*.md"))
    assert len(commands) >= 4, f"Expected >=4 slash commands, found {len(commands)}"


def _test_openai_tools_valid() -> None:
    _check_json_valid("tools/openai-tools.json")
    tools = json.loads((REPO_ROOT / "tools/openai-tools.json").read_text())
    assert len(tools) >= 3
    assert all("function" in t for t in tools)


def _test_openapi_yaml_parseable() -> None:
    _check_yaml_parseable("openapi.yaml")


def _test_cursor_rules() -> None:
    mdc_files = list((REPO_ROOT / ".cursor/rules").glob("*.mdc"))
    assert len(mdc_files) >= 1, f"Expected >=1 .mdc file in .cursor/rules/, found none"


run("AGENTS.md exists and non-empty", lambda: _check_file_nonempty("AGENTS.md"))
run("CLAUDE.md exists and non-empty", lambda: _check_file_nonempty("CLAUDE.md"))
run("CODEX.md exists and non-empty", lambda: _check_file_nonempty("CODEX.md"))
run(".github/copilot-instructions.md exists", lambda: _check_file_nonempty(".github/copilot-instructions.md"))
run(".cursor/rules/ has at least one .mdc file", _test_cursor_rules)
run(".windsurfrules exists", lambda: _check_file_nonempty(".windsurfrules"))
run(".aider.conf.yml exists", lambda: _check_file_nonempty(".aider.conf.yml"))
run(".continue/config.json is valid JSON", lambda: _check_json_valid(".continue/config.json"))
run(".claude/commands/ has >=4 slash commands", _test_claude_commands)
run("tools/openai-tools.json is valid JSON with >=3 tools", _test_openai_tools_valid)
run("openapi.yaml is parseable YAML", _test_openapi_yaml_parseable)


# ── 9. Docs site ──────────────────────────────────────────────────────────────

section("9. MkDocs documentation site")


def _test_mkdocs_yml() -> None:
    _check_file_nonempty("mkdocs.yml")
    content = (REPO_ROOT / "mkdocs.yml").read_text()
    assert "site_name" in content
    assert "material" in content


def _test_docs_pages() -> None:
    docs = list((REPO_ROOT / "docs").glob("*.md"))
    assert len(docs) >= 8, f"Expected >=8 doc pages, found {len(docs)}"
    names = {p.name for p in docs}
    for required in ("index.md", "quickstart.md", "architecture.md", "api-reference.md"):
        assert required in names, f"Missing docs/{required}"


run("mkdocs.yml exists with site_name and material theme", _test_mkdocs_yml)
run("docs/ has >=8 pages including index, quickstart, architecture, api-reference", _test_docs_pages)


# ── 10. examples/demo.py ─────────────────────────────────────────────────────

section("10. examples/demo.py end-to-end")


def _test_demo_runs() -> None:
    demo = REPO_ROOT / "examples" / "demo.py"
    assert demo.exists(), "examples/demo.py not found"
    r = subprocess.run(
        [PYTHON, str(demo)],
        capture_output=True, text=True,
        cwd=str(REPO_ROOT)
    )
    if r.returncode != 0:
        raise AssertionError(f"demo.py exited {r.returncode}:\n{r.stderr[-500:]}")


run("examples/demo.py runs end-to-end without error", _test_demo_runs)


# ── Summary ───────────────────────────────────────────────────────────────────

total = len(passed) + len(failed)
print(f"\n{'═'*60}")
print(f"{BOLD}Results: {len(passed)}/{total} passed{RESET}")

if failed:
    print(f"{RED}Failed ({len(failed)}):{RESET}")
    for name, reason in failed:
        print(f"  {RED}✗{RESET} {name}")
        short = reason.split("\n")[0][:120]
        print(f"    {YELLOW}→ {short}{RESET}")
    print(f"\n{YELLOW}Tip: run with --verbose for full tracebacks{RESET}")
else:
    print(f"{GREEN}All {total} checks passed — balancelab is ready to ship{RESET}")

print(f"{'═'*60}\n")
sys.exit(0 if not failed else 1)
