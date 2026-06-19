"""balancelab — adversarial game economy red-team library."""
from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("balancelab")
except PackageNotFoundError:
    __version__ = "0.0.0"

from balancelab.economy import (
    EconomyGraph,
    EconomyRule,
    ExploitFinder,
    ExploitPath,
    ExploitReport,
)
from balancelab.fixes import BalanceFix, recommend_fixes
from balancelab.sensitivity import SensitivityResult, critical_path, sensitivity_analysis
from balancelab.simulation import SimulationResult, SimulationStep, simulate

__all__ = [
    "BalanceFix",
    "EconomyGraph",
    "EconomyRule",
    "ExploitFinder",
    "ExploitPath",
    "ExploitReport",
    "SensitivityResult",
    "SimulationResult",
    "SimulationStep",
    "__version__",
    "critical_path",
    "recommend_fixes",
    "sensitivity_analysis",
    "simulate",
]
