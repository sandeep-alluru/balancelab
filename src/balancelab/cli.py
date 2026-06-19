"""CLI for balancelab."""
from __future__ import annotations

import json as _json
import sys

import click
from rich.console import Console

from balancelab import __version__
from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.fixes import recommend_fixes
from balancelab.report import print_report, to_json
from balancelab.simulation import simulate
from balancelab.store import EconomyStore

console = Console()


def _get_store(db: str) -> EconomyStore:
    return EconomyStore(db)


@click.group()
@click.version_option(version=__version__, prog_name="balancelab")
def main() -> None:
    """balancelab — adversarial game economy red-team tool."""


@main.command("add")
@click.argument("source")
@click.argument("target")
@click.argument("src_qty", type=float)
@click.argument("tgt_qty", type=float)
@click.option("--db", default=".balancelab/economy.db", help="Database path")
@click.option("--rule-id", default="", help="Human-readable rule label")
def add_rule(
    source: str, target: str, src_qty: float, tgt_qty: float, db: str, rule_id: str
) -> None:
    """Add an exchange rule: SOURCE -> TARGET at SRC_QTY:TGT_QTY."""
    store = _get_store(db)
    rule = EconomyRule(
        source_item=source,
        target_item=target,
        source_qty=src_qty,
        target_qty=tgt_qty,
        rule_id=rule_id,
    )
    store.save_rule(rule)
    console.print(f"[green]Added rule[/green] {rule.id}: {source} → {target} @ {src_qty}:{tgt_qty}")


@main.command("scan")
@click.option("--db", default=".balancelab/economy.db", help="Database path")
@click.option("--format", "fmt", default="rich", type=click.Choice(["rich", "json"]))
def scan(db: str, fmt: str) -> None:
    """Find exploits in stored rules."""
    store = _get_store(db)
    rules = store.list_rules()
    if not rules:
        console.print("[yellow]No rules found. Add rules with 'balancelab add'.[/yellow]")
        return

    graph = EconomyGraph()
    for r in rules:
        graph.add_rule(r)

    finder = ExploitFinder()
    report = finder.find_exploits(graph)
    store.save_report(report)

    if fmt == "json":
        click.echo(to_json(report))
    else:
        print_report(report, console=console)

    if report.total_found > 0:
        sys.exit(1)


@main.command("report")
@click.argument("report_id")
@click.option("--db", default=".balancelab/economy.db", help="Database path")
@click.option("--format", "fmt", default="rich", type=click.Choice(["rich", "json"]))
def show_report(report_id: str, db: str, fmt: str) -> None:
    """Show a specific exploit report by REPORT_ID."""
    store = _get_store(db)
    report = store.get_report(report_id)
    if report is None:
        console.print(f"[red]Report not found:[/red] {report_id}")
        raise SystemExit(1)
    if fmt == "json":
        click.echo(to_json(report))
    else:
        print_report(report, console=console)


@main.command("log")
@click.option("--db", default=".balancelab/economy.db", help="Database path")
def log_reports(db: str) -> None:
    """List all exploit reports."""
    store = _get_store(db)
    reports = store.list_reports()
    if not reports:
        console.print("[yellow]No reports yet. Run 'balancelab scan' first.[/yellow]")
        return
    from balancelab.report import to_markdown

    console.print(to_markdown(reports))


@main.command("status")
@click.option("--db", default=".balancelab/economy.db", help="Database path")
def status(db: str) -> None:
    """Show economy status: rule count, last scan."""
    store = _get_store(db)
    rules = store.list_rules()
    reports = store.list_reports()
    console.print("[bold]balancelab status[/bold]")
    console.print(f"  Rules stored: {len(rules)}")
    console.print(f"  Reports stored: {len(reports)}")
    if reports:
        r = reports[0]
        console.print(f"  Last scan: {r.id} — {r.total_found} exploit(s) found")


@main.command("simulate")
@click.argument("graph_file")
@click.option("--steps", default=100, type=int, help="Number of simulation steps")
@click.option("--strategy", default="greedy", type=click.Choice(["greedy", "balanced", "exploit"]))
@click.option("--format", "fmt", default="rich", type=click.Choice(["rich", "json"]))
def simulate_cmd(graph_file: str, steps: int, strategy: str, fmt: str) -> None:
    """Simulate economy from a JSON graph file."""
    try:
        with open(graph_file) as f:
            data = _json.load(f)
    except (OSError, _json.JSONDecodeError) as exc:
        console.print(f"[red]Failed to load graph file:[/red] {exc}")
        raise SystemExit(1) from exc

    graph = EconomyGraph()
    for rule_data in data.get("rules", []):
        graph.add_rule(EconomyRule.from_dict(rule_data))

    if not graph.rules:
        console.print("[yellow]No rules found in graph file.[/yellow]")
        return

    initial_levels = {item: 100.0 for item in graph.items()}
    result = simulate(graph, initial_levels, n_steps=steps, agent_strategy=strategy)

    if fmt == "json":
        output = {
            "steps": len(result.steps),
            "final_levels": result.final_levels,
            "violated_rules": result.violated_rules,
            "inflation_detected": result.inflation_detected,
            "inflation_resource": result.inflation_resource,
            "summary": result.summary,
        }
        click.echo(_json.dumps(output, indent=2))
    else:
        console.print(f"[bold]Simulation complete[/bold] — {strategy} strategy, {steps} steps")
        console.print(result.summary)
        console.print("\n[bold]Final resource levels:[/bold]")
        for item, level in sorted(result.final_levels.items()):
            console.print(f"  {item}: {level:.2f}")
        if result.inflation_detected:
            console.print(
                f"[red bold]Inflation detected![/red bold] Resource: {result.inflation_resource}"
            )
        if result.violated_rules:
            extras = len(result.violated_rules) - 5
            suffix = f" (+{extras} more)" if extras > 0 else ""
            console.print(
                f"[yellow]Rule violations:[/yellow] "
                f"{', '.join(result.violated_rules[:5])}{suffix}"
            )


@main.command("fixes")
@click.option("--db", default=".balancelab/economy.db", help="Database path")
@click.option("--report-id", default="", help="Specific report ID (last report if empty)")
def fixes_cmd(db: str, report_id: str) -> None:
    """Show fix recommendations for the latest exploit report."""
    store = _get_store(db)

    if report_id:
        report = store.get_report(report_id)
        if report is None:
            console.print(f"[red]Report not found:[/red] {report_id}")
            raise SystemExit(1)
    else:
        reports = store.list_reports()
        if not reports:
            console.print(
                "[yellow]No reports found. Run 'balancelab scan' first.[/yellow]"
            )
            return
        report = reports[0]

    fixes = recommend_fixes(report)

    if not fixes:
        console.print("[green]No fixes needed — no exploits found in this report.[/green]")
        return

    n_fixes = len(fixes)
    console.print(
        f"[bold]Fix recommendations for report {report.id}[/bold] ({n_fixes} fix(es))\n"
    )
    for i, fix in enumerate(fixes, 1):
        console.print(f"[bold cyan]Fix {i}:[/bold cyan] {fix.fix_type.upper()}")
        console.print(f"  Path: {' -> '.join(fix.exploit_path)}")
        if fix.target_edge:
            console.print(f"  Target edge: {fix.target_edge[0]} -> {fix.target_edge[1]}")
        if fix.suggested_value is not None:
            console.print(f"  Suggested value: {fix.suggested_value:.4f}")
        console.print(f"  Estimated reduction: {fix.estimated_reduction_pct:.1f}%")
        console.print(f"  Description: {fix.description}")
        console.print()


if __name__ == "__main__":
    main()
