"""Fix recommendations for economy exploits."""
from __future__ import annotations

from dataclasses import dataclass

from balancelab.economy import ExploitReport


@dataclass
class BalanceFix:
    exploit_path: list[str]             # the node IDs in the exploit path
    # "rate_cap", "cooldown", "daily_limit", "require_prerequisite"
    fix_type: str
    target_edge: tuple[str, str] | None
    suggested_value: float | None
    description: str
    estimated_reduction_pct: float      # how much this fix reduces the exploit rate (0-100)


def recommend_fixes(report: ExploitReport) -> list[BalanceFix]:
    """For each exploit found, suggest the minimum change to neutralize it."""
    fixes: list[BalanceFix] = []

    for exploit in report.exploits:
        path = exploit.path
        gain_ratio = exploit.gain_ratio
        n_edges = max(1, len(path) - 1)

        # Determine target_edge: first edge in path if path has >= 2 elements
        target_edge: tuple[str, str] | None = None
        if len(path) >= 2:
            target_edge = (path[0], path[1])

        if len(path) == 2:
            # Single edge back and forth (2 nodes, one edge)
            fix_type = "daily_limit"
            suggested_value = None
            description = (
                f"Apply a daily transaction limit on the edge {path[0]} -> {path[1]} "
                f"to prevent repeated exploitation."
            )
            estimated_reduction_pct = 75.0

        elif gain_ratio > 2.0:
            fix_type = "rate_cap"
            # suggested_value: cap each edge rate so the cycle gain becomes 1.0
            # To neutralize: product of rates = 1.0
            # If current gain_ratio = R, cap each edge to (1/R)^(1/n_edges)
            suggested_value = (1.0 / max(gain_ratio, 1.001)) ** (1.0 / n_edges)
            description = (
                f"Cap exchange rate on edge ({path[0]} -> {path[1]}) "
                f"to {suggested_value:.4f} so the cycle gain reduces to 1.0."
            )
            estimated_reduction_pct = min(99.0, (gain_ratio - 1.0) / gain_ratio * 100)

        elif 1.0 <= gain_ratio <= 2.0:
            fix_type = "cooldown"
            suggested_value = gain_ratio * 10
            description = (
                f"Add a cooldown of {suggested_value:.1f} seconds between uses of this exploit "
                f"path to limit abuse (cycle gain: {gain_ratio:.2f}x)."
            )
            estimated_reduction_pct = 50.0

        else:
            fix_type = "require_prerequisite"
            suggested_value = None
            description = (
                f"Require a prerequisite item or condition before the path "
                f"{' -> '.join(path)} can be executed."
            )
            estimated_reduction_pct = 60.0

        fixes.append(BalanceFix(
            exploit_path=list(path),
            fix_type=fix_type,
            target_edge=target_edge,
            suggested_value=suggested_value,
            description=description,
            estimated_reduction_pct=estimated_reduction_pct,
        ))

    return fixes
