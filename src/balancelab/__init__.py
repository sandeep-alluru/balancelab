"""balancelab — adversarial game economy red-team library."""
from __future__ import annotations

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("balancelab")
except PackageNotFoundError:
    __version__ = "0.0.0"

from balancelab.economy import (
    EconomyRule,
    EconomyGraph,
    ExploitPath,
    ExploitReport,
    ExploitFinder,
)

__all__ = [
    "__version__",
    "EconomyRule",
    "EconomyGraph",
    "ExploitPath",
    "ExploitReport",
    "ExploitFinder",
]
