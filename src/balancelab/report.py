"""Report formatters for ExploitReport."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from balancelab.economy import ExploitReport


def print_report(report: ExploitReport, console: Console | None = None) -> None:
    """Print an ExploitReport to the console using rich."""
    if console is None:
        console = Console()

    console.print(f"\n[bold]Exploit Report[/bold] [dim](id: {report.id})[/dim]")
    console.print(f"  Items: {report.graph_item_count}  Rules: {report.graph_rule_count}")
    console.print(f"  Exploits found: [bold red]{report.total_found}[/bold red]")

    if not report.exploits:
        console.print("  [green]No exploits detected — economy is balanced.[/green]")
        return

    table = Table(title="Exploit Paths")
    table.add_column("ID", style="dim")
    table.add_column("Path")
    table.add_column("Gain Ratio", style="red")

    for exploit in report.exploits:
        path_str = " → ".join(exploit.path)
        table.add_row(exploit.id, path_str, f"{exploit.gain_ratio:.2f}x")

    console.print(table)


def to_json(report: ExploitReport) -> str:
    """Serialize report to JSON string."""
    return json.dumps(report.to_dict(), indent=2)


def to_markdown(reports: ExploitReport | list[ExploitReport]) -> str:
    """Format one or more ExploitReports as a Markdown table.

    Accepts either a single ExploitReport or a list of ExploitReport objects.
    """
    if isinstance(reports, ExploitReport):
        reports = [reports]
    lines = ["# balancelab Exploit Reports", ""]
    lines.append("| Report ID | Items | Rules | Exploits | Top Gain |")
    lines.append("|-----------|-------|-------|----------|----------|")
    for r in reports:
        top_gain = max((e.gain_ratio for e in r.exploits), default=0.0)
        lines.append(
            f"| {r.id} | {r.graph_item_count} | {r.graph_rule_count} | "
            f"{r.total_found} | {top_gain:.2f}x |"
        )
    return "\n".join(lines)
