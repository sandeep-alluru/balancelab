"""MCP server for balancelab."""
from __future__ import annotations

import json
from typing import Any

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder
from balancelab.store import EconomyStore

try:
    from mcp import types as mcp_types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server

    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False


def _get_store(db: str = ".balancelab/economy.db") -> EconomyStore:
    return EconomyStore(db)


def add_rule(
    source_item: str,
    target_item: str,
    source_qty: float,
    target_qty: float,
    rule_id: str = "",
    db: str = ".balancelab/economy.db",
) -> dict[str, Any]:
    """Add an exchange rule to the economy store."""
    store = _get_store(db)
    rule = EconomyRule(
        source_item=source_item,
        target_item=target_item,
        source_qty=source_qty,
        target_qty=target_qty,
        rule_id=rule_id,
    )
    store.save_rule(rule)
    return {"id": rule.id, "status": "saved"}


def scan_economy(db: str = ".balancelab/economy.db") -> dict[str, Any]:
    """Scan the economy for arbitrage exploits."""
    store = _get_store(db)
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


def list_reports(db: str = ".balancelab/economy.db") -> list[dict[str, Any]]:
    """List all exploit reports."""
    store = _get_store(db)
    return [r.to_dict() for r in store.list_reports()]


def run_server() -> None:
    """Run the MCP server."""
    if not _MCP_AVAILABLE:
        msg = "mcp package not installed. Run: pip install balancelab[mcp]"
        raise RuntimeError(msg)

    import asyncio

    server = Server("balancelab")

    @server.list_tools()  # type: ignore[misc]
    async def handle_list_tools() -> list[mcp_types.Tool]:
        return [
            mcp_types.Tool(
                name="add_rule",
                description="Add an exchange rule to the game economy",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "source_item": {"type": "string"},
                        "target_item": {"type": "string"},
                        "source_qty": {"type": "number"},
                        "target_qty": {"type": "number"},
                        "rule_id": {"type": "string"},
                        "db": {"type": "string"},
                    },
                    "required": ["source_item", "target_item", "source_qty", "target_qty"],
                },
            ),
            mcp_types.Tool(
                name="scan_economy",
                description="Scan the economy for arbitrage exploits",
                inputSchema={
                    "type": "object",
                    "properties": {"db": {"type": "string"}},
                },
            ),
            mcp_types.Tool(
                name="list_reports",
                description="List all exploit scan reports",
                inputSchema={
                    "type": "object",
                    "properties": {"db": {"type": "string"}},
                },
            ),
        ]

    @server.call_tool()  # type: ignore[misc]
    async def handle_call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[mcp_types.TextContent]:
        if name == "add_rule":
            result = add_rule(**arguments)
        elif name == "scan_economy":
            result = scan_economy(**arguments)
        elif name == "list_reports":
            result = list_reports(**arguments)
        else:
            msg = f"Unknown tool: {name}"
            raise ValueError(msg)
        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]

    async def main() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(main())
