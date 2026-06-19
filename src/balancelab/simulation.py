"""Economy simulation: run the economy forward N time steps."""
from __future__ import annotations

from dataclasses import dataclass

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder


@dataclass
class SimulationStep:
    step: int
    resource_levels: dict[str, float]   # resource_name -> current_level
    activity_counts: dict[str, int]     # activity -> times performed this step
    rule_violations: list[str]          # which rules were violated (rule IDs)


@dataclass
class SimulationResult:
    steps: list[SimulationStep]
    final_levels: dict[str, float]
    violated_rules: list[str]           # all rules violated during simulation (deduplicated)
    inflation_detected: bool
    inflation_resource: str | None
    summary: str


def simulate(
    graph: EconomyGraph,
    initial_levels: dict[str, float],
    n_steps: int = 100,
    agent_strategy: str = "greedy",  # "greedy" | "balanced" | "exploit"
) -> SimulationResult:
    """Run economy simulation. 'exploit' strategy finds and uses exploits."""
    resource_levels: dict[str, float] = dict(initial_levels)
    steps: list[SimulationStep] = []
    all_violated: set[str] = set()
    inflation_detected = False
    inflation_resource: str | None = None

    # Pre-compute exploit paths if using exploit strategy
    exploit_cycles: list[list[str]] = []
    if agent_strategy == "exploit":
        finder = ExploitFinder()
        report = finder.find_exploits(graph)
        for exploit in report.exploits:
            exploit_cycles.append(exploit.path)

    for step_num in range(1, n_steps + 1):
        activity_counts: dict[str, int] = {}
        rule_violations: list[str] = []

        if agent_strategy == "greedy":
            for rule in graph.rules:
                if resource_levels.get(rule.source_item, 0.0) >= rule.source_qty:
                    resource_levels[rule.source_item] = (
                        resource_levels.get(rule.source_item, 0.0) - rule.source_qty
                    )
                    resource_levels[rule.target_item] = (
                        resource_levels.get(rule.target_item, 0.0) + rule.target_qty
                    )
                    activity_key = f"{rule.source_item}->{rule.target_item}"
                    activity_counts[activity_key] = activity_counts.get(activity_key, 0) + 1
                else:
                    rule_violations.append(rule.id)

        elif agent_strategy == "balanced":
            # At most 1 rule per source item per step — pick the best exchange rate
            best_rules: dict[str, EconomyRule] = {}
            for rule in graph.rules:
                src = rule.source_item
                if src not in best_rules or rule.exchange_rate() > best_rules[src].exchange_rate():
                    best_rules[src] = rule

            for _src, rule in best_rules.items():
                if resource_levels.get(rule.source_item, 0.0) >= rule.source_qty:
                    resource_levels[rule.source_item] = (
                        resource_levels.get(rule.source_item, 0.0) - rule.source_qty
                    )
                    resource_levels[rule.target_item] = (
                        resource_levels.get(rule.target_item, 0.0) + rule.target_qty
                    )
                    activity_key = f"{rule.source_item}->{rule.target_item}"
                    activity_counts[activity_key] = activity_counts.get(activity_key, 0) + 1
                else:
                    rule_violations.append(rule.id)

        elif agent_strategy == "exploit":
            # Try to execute each exploit cycle once per step
            for cycle_path in exploit_cycles:
                if len(cycle_path) < 2:
                    continue
                # Find rules that form the cycle path
                can_execute = True
                cycle_rules: list[EconomyRule] = []
                for i in range(len(cycle_path) - 1):
                    src = cycle_path[i]
                    tgt = cycle_path[i + 1]
                    rule_found = None
                    for rule in graph.rules:
                        if rule.source_item == src and rule.target_item == tgt:
                            rule_found = rule
                            break
                    if rule_found is None or resource_levels.get(src, 0.0) < rule_found.source_qty:
                        can_execute = False
                        if rule_found is not None:
                            rule_violations.append(rule_found.id)
                        break
                    cycle_rules.append(rule_found)

                if can_execute:
                    for rule in cycle_rules:
                        resource_levels[rule.source_item] = (
                            resource_levels.get(rule.source_item, 0.0) - rule.source_qty
                        )
                        resource_levels[rule.target_item] = (
                            resource_levels.get(rule.target_item, 0.0) + rule.target_qty
                        )
                        activity_key = f"{rule.source_item}->{rule.target_item}"
                        activity_counts[activity_key] = activity_counts.get(activity_key, 0) + 1

            # Skip greedy pass — exploit cycles were already applied
            # (applying greedy rules again would double-count rules used in exploit cycles)

        # Check for inflation: any resource > 10x its initial level
        if not inflation_detected:
            for item, level in resource_levels.items():
                init = initial_levels.get(item, 0.0)
                if init > 0 and level > 10.0 * init:
                    inflation_detected = True
                    inflation_resource = item
                    break

        # Track all violations
        all_violated.update(rule_violations)

        steps.append(SimulationStep(
            step=step_num,
            resource_levels=dict(resource_levels),
            activity_counts=dict(activity_counts),
            rule_violations=list(rule_violations),
        ))

    final_levels = dict(resource_levels)
    violated_rules = sorted(all_violated)

    inflation_str = "yes" if inflation_detected else "no"
    summary = (
        f"Ran {n_steps} steps. "
        f"Final levels: {final_levels}. "
        f"Inflation: {inflation_str}."
    )

    return SimulationResult(
        steps=steps,
        final_levels=final_levels,
        violated_rules=violated_rules,
        inflation_detected=inflation_detected,
        inflation_resource=inflation_resource,
        summary=summary,
    )
