"""balancelab - adversarial game economy red-team library."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("balancelab")
except PackageNotFoundError:
    __version__ = "0.0.0"

from balancelab.av_aivat import (
    DEFAULT_TARGET_PRECISION,
    DEFAULT_Z,
    ConfidenceSequenceState,
    EvalObservation,
    assert_eval_stopping_ok,
    gate_eval_stopping,
    summarize_confidence_sequence,
)
from balancelab.closed_loop import (
    ClosedLoopError,
    GateOutcome,
    assert_economy_shippable,
    assert_price_book_ok,
    gate_binary_signal,
    gate_economy,
    gate_kill_switch,
    gate_price_book,
)
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
    "DEFAULT_TARGET_PRECISION",
    "DEFAULT_Z",
    "BalanceFix",
    "ClosedLoopError",
    "ConfidenceSequenceState",
    "EconomyGraph",
    "EconomyRule",
    "EvalObservation",
    "ExploitFinder",
    "ExploitPath",
    "ExploitReport",
    "GateOutcome",
    "SensitivityResult",
    "SimulationResult",
    "SimulationStep",
    "__version__",
    "assert_economy_shippable",
    "assert_eval_stopping_ok",
    "assert_price_book_ok",
    "critical_path",
    "gate_binary_signal",
    "gate_economy",
    "gate_eval_stopping",
    "gate_kill_switch",
    "gate_price_book",
    "recommend_fixes",
    "sensitivity_analysis",
    "simulate",
    "summarize_confidence_sequence",
]
