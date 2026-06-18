"""Tests for FastAPI server."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from balancelab.api import app, _DEFAULT_DB


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class TestAPI:
    def test_health(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert "version" in r.json()

    def test_add_rule(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        r = client.post("/rule", json={
            "source_item": "gold",
            "target_item": "silver",
            "source_qty": 1.0,
            "target_qty": 3.0,
            "db": db,
        })
        assert r.status_code == 200
        assert "id" in r.json()

    def test_list_rules(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        client.post("/rule", json={
            "source_item": "gold", "target_item": "silver",
            "source_qty": 1.0, "target_qty": 3.0, "db": db,
        })
        r = client.get("/rules", params={"db": db})
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_scan_no_rules(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        r = client.post("/scan", json={"db": db})
        assert r.status_code == 200
        assert r.json()["total_found"] == 0

    def test_scan_with_exploit(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        for src, tgt, sq, tq in [
            ("gold", "silver", 1.0, 3.0),
            ("silver", "gems", 1.0, 2.0),
            ("gems", "gold", 1.0, 4.0),
        ]:
            client.post("/rule", json={
                "source_item": src, "target_item": tgt,
                "source_qty": sq, "target_qty": tq, "db": db,
            })
        r = client.post("/scan", json={"db": db})
        assert r.status_code == 200
        assert r.json()["total_found"] > 0

    def test_list_reports(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        client.post("/scan", json={"db": db})
        r = client.get("/reports", params={"db": db})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_rule_with_tags(self, client: TestClient, tmp_path: Path) -> None:
        db = str(tmp_path / "test.db")
        r = client.post("/rule", json={
            "source_item": "gold", "target_item": "silver",
            "source_qty": 1.0, "target_qty": 3.0,
            "tags": ["trade", "shop"], "db": db,
        })
        assert r.status_code == 200
