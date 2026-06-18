"""CLI for balancelab."""
from __future__ import annotations

import click
from rich.console import Console

from balancelab import __version__
from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.report import print_report, to_json
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


if __name__ == "__main__":
    main()
