"""Tests for report formatters."""
from __future__ import annotations

import io
import json

from rich.console import Console

from balancelab.economy import EconomyGraph, EconomyRule, ExploitFinder, ExploitReport
from balancelab.report import print_report, to_json, to_markdown


def make_report_with_exploit() -> ExploitReport:
    g = EconomyGraph()
    g.add_rule(EconomyRule("gold", "silver", 1.0, 3.0))
    g.add_rule(EconomyRule("silver", "gems", 1.0, 2.0))
    g.add_rule(EconomyRule("gems", "gold", 1.0, 4.0))
    finder = ExploitFinder()
    return finder.find_exploits(g)


def make_empty_report() -> ExploitReport:
    return ExploitReport(3, 3, [], 0)


class TestToJson:
    def test_valid_json(self) -> None:
        report = make_empty_report()
        result = to_json(report)
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_json_has_exploits_key(self) -> None:
        report = make_empty_report()
        parsed = json.loads(to_json(report))
        assert "exploits" in parsed

    def test_json_with_exploit(self) -> None:
        report = make_report_with_exploit()
        parsed = json.loads(to_json(report))
        assert parsed["total_found"] > 0

    def test_json_has_id(self) -> None:
        report = make_empty_report()
        parsed = json.loads(to_json(report))
        assert "id" in parsed


class TestToMarkdown:
    def test_returns_string(self) -> None:
        result = to_markdown([make_empty_report()])
        assert isinstance(result, str)

    def test_has_table(self) -> None:
        result = to_markdown([make_empty_report()])
        assert "|" in result

    def test_has_header(self) -> None:
        result = to_markdown([make_empty_report()])
        assert "balancelab" in result

    def test_empty_list(self) -> None:
        result = to_markdown([])
        assert isinstance(result, str)

    def test_multiple_reports(self) -> None:
        reports = [make_empty_report(), make_empty_report()]
        result = to_markdown(reports)
        assert result.count("|") > 5


class TestPrintReport:
    def test_prints_to_console(self) -> None:
        buf = io.StringIO()
        console = Console(file=buf, highlight=False)
        report = make_empty_report()
        print_report(report, console=console)
        output = buf.getvalue()
        assert len(output) > 0

    def test_prints_exploit_count(self) -> None:
        buf = io.StringIO()
        console = Console(file=buf, highlight=False)
        report = make_report_with_exploit()
        print_report(report, console=console)
        output = buf.getvalue()
        assert len(output) > 0

    def test_no_console_arg(self) -> None:
        report = make_empty_report()
        print_report(report)  # should not raise
