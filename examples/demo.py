"""
balancelab demo — standalone example showing exploit detection.

Run from repo root:
    python examples/demo.py
"""
from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.report import print_report, to_json

console = Console()


def demo_exploitable_economy() -> None:
    """Demo: gold → silver → gems → gold creates a 24x exploit."""
    console.print(Panel("[bold red]Demo: Exploitable Economy[/bold red]"))

    graph = EconomyGraph()
    graph.add_rule(EconomyRule("gold", "silver", 1.0, 3.0, rule_id="mint"))
    graph.add_rule(EconomyRule("silver", "gems", 1.0, 2.0, rule_id="jeweler"))
    graph.add_rule(EconomyRule("gems", "gold", 1.0, 4.0, rule_id="trader"))

    console.print(f"\nRules defined: {len(graph.rules)}")
    for rule in graph.rules:
        console.print(
            f"  [cyan]{rule.source_item}[/cyan] → [cyan]{rule.target_item}[/cyan] "
            f"@ {rule.source_qty}:{rule.target_qty} "
            f"(rate: {rule.exchange_rate():.1f}x)"
        )

    finder = ExploitFinder()
    report = finder.find_exploits(graph)

    console.print()
    print_report(report, console=console)

    if report.total_found > 0:
        console.print(
            f"\n[bold red]CRITICAL:[/bold red] {report.total_found} exploit(s) found! "
            "Top gain ratio: "
            f"[bold red]{report.exploits[0].gain_ratio:.2f}x[/bold red]"
        )


def demo_balanced_economy() -> None:
    """Demo: a balanced economy with no exploits."""
    console.print(Panel("[bold green]Demo: Balanced Economy[/bold green]"))

    graph = EconomyGraph()
    # Rates multiply to exactly 1.0: 3 * 2 * (1/6) = 1.0
    graph.add_rule(EconomyRule("gold", "silver", 1.0, 3.0, rule_id="mint"))
    graph.add_rule(EconomyRule("silver", "gems", 1.0, 2.0, rule_id="jeweler"))
    graph.add_rule(EconomyRule("gems", "gold", 6.0, 1.0, rule_id="melter"))

    console.print(f"\nRules defined: {len(graph.rules)}")
    for rule in graph.rules:
        console.print(
            f"  [cyan]{rule.source_item}[/cyan] → [cyan]{rule.target_item}[/cyan] "
            f"@ {rule.source_qty}:{rule.target_qty} "
            f"(rate: {rule.exchange_rate():.3f}x)"
        )

    finder = ExploitFinder()
    report = finder.find_exploits(graph)

    console.print()
    print_report(report, console=console)

    if report.total_found == 0:
        console.print("[bold green]Economy is balanced — no exploits detected.[/bold green]")


def demo_json_output() -> None:
    """Demo: JSON output for machine consumption."""
    console.print(Panel("[bold blue]Demo: JSON Output[/bold blue]"))

    graph = EconomyGraph()
    graph.add_rule(EconomyRule("A", "B", 1.0, 2.0))
    graph.add_rule(EconomyRule("B", "A", 1.0, 2.0))

    finder = ExploitFinder()
    report = finder.find_exploits(graph)

    json_str = to_json(report)
    console.print(f"\nJSON report ({len(json_str)} chars):")
    console.print(json_str[:200] + "..." if len(json_str) > 200 else json_str)


if __name__ == "__main__":
    console.print("[bold]balancelab Demo[/bold]\n")

    demo_exploitable_economy()
    console.print()
    demo_balanced_economy()
    console.print()
    demo_json_output()

    console.print("\n[bold green]Demo complete.[/bold green]")
