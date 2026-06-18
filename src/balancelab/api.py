"""FastAPI server for balancelab."""
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI
from pydantic import BaseModel

from balancelab import __version__
from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.store import EconomyStore

app = FastAPI(title="balancelab API", version=__version__)

_DEFAULT_DB = ".balancelab/economy.db"


def _store(db: Optional[str] = None) -> EconomyStore:
    return EconomyStore(db or _DEFAULT_DB)


class RuleRequest(BaseModel):
    """Request body for creating an exchange rule."""

    source_item: str
    target_item: str
    source_qty: float
    target_qty: float
    rule_id: str = ""
    tags: list[str] = []
    db: Optional[str] = None


class ScanRequest(BaseModel):
    """Request body for scanning economy."""

    db: Optional[str] = None


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": __version__}


@app.post("/rule")
def add_rule(req: RuleRequest) -> dict[str, str]:
    """Add an exchange rule to the economy."""
    store = _store(req.db)
    rule = EconomyRule(
        source_item=req.source_item,
        target_item=req.target_item,
        source_qty=req.source_qty,
        target_qty=req.target_qty,
        rule_id=req.rule_id,
        tags=req.tags,
    )
    store.save_rule(rule)
    return {"id": rule.id, "status": "saved"}


@app.get("/rules")
def list_rules(db: Optional[str] = None) -> list[dict]:  # type: ignore[type-arg]
    """List all exchange rules."""
    store = _store(db)
    return [r.to_dict() for r in store.list_rules()]


@app.post("/scan")
def scan_economy(req: ScanRequest) -> dict:  # type: ignore[type-arg]
    """Scan stored rules for exploits."""
    store = _store(req.db)
    rules = store.list_rules()
    if not rules:
        return {"total_found": 0, "exploits": [], "message": "No rules found"}
    graph = EconomyGraph()
    for r in rules:
        graph.add_rule(r)
    finder = ExploitFinder()
    report = finder.find_exploits(graph)
    store.save_report(report)
    return report.to_dict()


@app.get("/reports")
def list_reports(db: Optional[str] = None) -> list[dict]:  # type: ignore[type-arg]
    """List all exploit reports."""
    store = _store(db)
    return [r.to_dict() for r in store.list_reports()]
