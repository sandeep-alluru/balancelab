"""SQLite store for EconomyRules and ExploitReports."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from balancelab.economy import EconomyRule, ExploitPath, ExploitReport


class EconomyStore:
    """Persist economy rules and exploit reports in SQLite."""

    def __init__(self, db_path: str = ".balancelab/economy.db") -> None:
        """Initialize the store with a SQLite database path."""
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS economy_rules (
                    id TEXT PRIMARY KEY,
                    source_item TEXT NOT NULL,
                    target_item TEXT NOT NULL,
                    source_qty REAL NOT NULL,
                    target_qty REAL NOT NULL,
                    rule_id TEXT,
                    tags TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS exploit_reports (
                    id TEXT PRIMARY KEY,
                    graph_item_count INTEGER NOT NULL,
                    graph_rule_count INTEGER NOT NULL,
                    total_found INTEGER NOT NULL,
                    timestamp REAL NOT NULL,
                    exploits TEXT NOT NULL
                )
                """
            )

    def save_rule(self, rule: EconomyRule) -> None:
        """Persist a rule (upsert)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO economy_rules
                    (id, source_item, target_item, source_qty, target_qty, rule_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    rule.id,
                    rule.source_item,
                    rule.target_item,
                    rule.source_qty,
                    rule.target_qty,
                    rule.rule_id,
                    json.dumps(rule.tags),
                ),
            )

    def get_rule(self, rule_id: str) -> Optional[EconomyRule]:
        """Retrieve a rule by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM economy_rules WHERE id = ?", (rule_id,)
            ).fetchone()
            if row is None:
                return None
            return EconomyRule(
                source_item=row["source_item"],
                target_item=row["target_item"],
                source_qty=row["source_qty"],
                target_qty=row["target_qty"],
                rule_id=row["rule_id"] or "",
                tags=json.loads(row["tags"]),
            )

    def list_rules(self) -> list[EconomyRule]:
        """List all stored rules."""
        with self._conn() as conn:
            rows = conn.execute("SELECT * FROM economy_rules").fetchall()
            return [
                EconomyRule(
                    source_item=row["source_item"],
                    target_item=row["target_item"],
                    source_qty=row["source_qty"],
                    target_qty=row["target_qty"],
                    rule_id=row["rule_id"] or "",
                    tags=json.loads(row["tags"]),
                )
                for row in rows
            ]

    def save_report(self, report: ExploitReport) -> None:
        """Persist an exploit report."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO exploit_reports
                    (id, graph_item_count, graph_rule_count, total_found, timestamp, exploits)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.graph_item_count,
                    report.graph_rule_count,
                    report.total_found,
                    report.timestamp,
                    json.dumps([e.to_dict() for e in report.exploits]),
                ),
            )

    def get_report(self, report_id: str) -> Optional[ExploitReport]:
        """Retrieve a report by ID."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM exploit_reports WHERE id = ?", (report_id,)
            ).fetchone()
            if row is None:
                return None
            exploits_data = json.loads(row["exploits"])
            exploits = [
                ExploitPath(
                    path=e["path"],
                    rules_used=e["rules_used"],
                    gain_ratio=e["gain_ratio"],
                )
                for e in exploits_data
            ]
            r = ExploitReport(
                graph_item_count=row["graph_item_count"],
                graph_rule_count=row["graph_rule_count"],
                exploits=exploits,
                total_found=row["total_found"],
                timestamp=row["timestamp"],
            )
            return r

    def list_reports(self) -> list[ExploitReport]:
        """List all stored reports (metadata only, no exploit details)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM exploit_reports ORDER BY timestamp DESC"
            ).fetchall()
            result = []
            for row in rows:
                exploits_data = json.loads(row["exploits"])
                exploits = [
                    ExploitPath(
                        path=e["path"],
                        rules_used=e["rules_used"],
                        gain_ratio=e["gain_ratio"],
                    )
                    for e in exploits_data
                ]
                r = ExploitReport(
                    graph_item_count=row["graph_item_count"],
                    graph_rule_count=row["graph_rule_count"],
                    exploits=exploits,
                    total_found=row["total_found"],
                    timestamp=row["timestamp"],
                )
                result.append(r)
            return result
