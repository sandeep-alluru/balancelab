"""CLI tests using CliRunner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from balancelab.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


class TestCLI:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "balancelab" in result.output

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_add_rule(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(main, ["add", "gold", "silver", "1.0", "3.0", "--db", db_path])
        assert result.exit_code == 0
        assert "Added rule" in result.output

    def test_scan_no_rules(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(main, ["scan", "--db", db_path])
        assert result.exit_code == 0
        assert "No rules" in result.output

    def test_scan_with_exploit(self, runner: CliRunner, db_path: str) -> None:
        runner.invoke(main, ["add", "gold", "silver", "1.0", "3.0", "--db", db_path])
        runner.invoke(main, ["add", "silver", "gems", "1.0", "2.0", "--db", db_path])
        runner.invoke(main, ["add", "gems", "gold", "1.0", "4.0", "--db", db_path])
        result = runner.invoke(main, ["scan", "--db", db_path])
        assert result.exit_code == 0

    def test_scan_json_format(self, runner: CliRunner, db_path: str) -> None:
        runner.invoke(main, ["add", "gold", "silver", "1.0", "3.0", "--db", db_path])
        runner.invoke(main, ["add", "silver", "gems", "1.0", "2.0", "--db", db_path])
        runner.invoke(main, ["add", "gems", "gold", "1.0", "4.0", "--db", db_path])
        result = runner.invoke(main, ["scan", "--format", "json", "--db", db_path])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "total_found" in data

    def test_log_no_reports(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(main, ["log", "--db", db_path])
        assert result.exit_code == 0
        assert "No reports" in result.output

    def test_status(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(main, ["status", "--db", db_path])
        assert result.exit_code == 0
        assert "status" in result.output.lower()

    def test_report_not_found(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(main, ["report", "nonexistent", "--db", db_path])
        assert result.exit_code != 0

    def test_add_with_rule_id(self, runner: CliRunner, db_path: str) -> None:
        result = runner.invoke(
            main, ["add", "gold", "silver", "1.0", "3.0", "--db", db_path, "--rule-id", "mint"]
        )
        assert result.exit_code == 0

    def test_report_json_format(self, runner: CliRunner, db_path: str) -> None:
        runner.invoke(main, ["add", "gold", "silver", "1.0", "3.0", "--db", db_path])
        result = runner.invoke(main, ["scan", "--format", "json", "--db", db_path])
        assert result.exit_code == 0
        data = json.loads(result.output)
        report_id = data["id"]
        result2 = runner.invoke(main, ["report", report_id, "--format", "json", "--db", db_path])
        assert result2.exit_code == 0
