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

__all__ = [
    "EconomyGraph",
    "EconomyRule",
    "ExploitFinder",
    "ExploitPath",
    "ExploitReport",
    "__version__",
]
