from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_upstream_updates as checker  # noqa: E402


def test_baseline_file_is_valid_and_complete() -> None:
    baseline = checker.load_baseline()

    assert baseline["repo"].endswith("commerce-agents.git")
    assert baseline["branch"] == "main"
    assert len(baseline["reviewed_through"]) == 40
    assert baseline["reviewed_date"]


def test_baseline_reads_pr_and_issue_watermarks() -> None:
    baseline = checker.load_baseline()

    assert isinstance(baseline["reviewed_pr_through"], int)
    assert isinstance(baseline["reviewed_issue_through"], int)
    assert baseline["reviewed_pr_through"] > 0


def test_baseline_records_the_known_upstream_branch_list() -> None:
    """anthropics/commerce-agents carries a single branch at baseline time."""
    baseline = checker.load_baseline()

    assert baseline.get("branches") == ["main"]


def test_workflow_is_scheduled_and_fails_on_unreviewed_commits() -> None:
    workflow = (
        Path(__file__).parents[1] / ".github" / "workflows" / "upstream-check.yml"
    ).read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "cron:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "tools/check_upstream_updates.py" in workflow
    assert "fetch-depth: 0" in workflow
    assert "exit 1" in workflow


def test_render_markdown_reports_no_new_commits() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
    }

    report = checker.render_markdown(baseline, [])

    assert "No new upstream commits" in report


def test_render_markdown_surfaces_check_failure() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
    }

    report = checker.render_markdown(baseline, [], error="git fetch failed")

    assert "Check failed" in report
    assert "git fetch failed" in report


def test_render_markdown_reports_ticket_watermarks() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
        "reviewed_pr_through": 4,
        "reviewed_issue_through": 0,
    }

    report = checker.render_markdown(baseline, [], prs=[], issues=None)

    assert "Triaged through `#4`" in report
    assert "Triaged through `#0`" in report
    assert "No new items above that number." in report
    assert "Not checked" in report


def test_render_markdown_distinguishes_disabled_from_unavailable() -> None:
    """anthropics/commerce-agents has GitHub Issues disabled: DISABLED must read
    differently from a genuine check failure (None), and must not claim "no new items"."""
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
        "reviewed_pr_through": 4,
        "reviewed_issue_through": 0,
    }

    report = checker.render_markdown(baseline, [], prs=[], issues=checker.DISABLED)

    assert "has this ticket type disabled" in report
    assert "No new items above that number." not in report.split("Upstream issues")[1]


def test_collect_new_tickets_treats_disabled_as_not_an_error(monkeypatch: object) -> None:
    """The upstream repo can turn off issues/PRs entirely; that is not `gh` failing."""
    import subprocess

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "the 'anthropics/commerce-agents' repository has disabled issues"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    baseline = {"repo": "https://github.com/anthropics/commerce-agents.git"}
    result = checker.collect_new_tickets(baseline, "issue")

    assert result is checker.DISABLED
    assert result is not None


def test_collect_new_tickets_returns_none_on_a_genuine_failure(monkeypatch: object) -> None:
    import subprocess

    class FakeResult:
        returncode = 1
        stdout = ""
        stderr = "gh: authentication required"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    baseline = {"repo": "https://github.com/anthropics/commerce-agents.git"}
    result = checker.collect_new_tickets(baseline, "pr")

    assert result is None


def test_load_baseline_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(checker.UpstreamCheckError):
        checker.load_baseline(tmp_path / "nope.json")


def test_json_output_round_trips_the_disabled_sentinel() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
    }

    payload = json.loads(
        checker.render_json(baseline, [], prs=[], issues=checker.DISABLED, error=None)
    )

    assert payload["issues"] == "disabled"
    assert payload["pull_requests"] == []
    assert payload["repo"] == baseline["repo"]


def test_json_output_surfaces_the_check_error() -> None:
    payload = json.loads(
        checker.render_json({}, [], prs=None, issues=None, error="git fetch failed")
    )

    assert payload["error"] == "git fetch failed"


def test_baseline_matches_decisions_record() -> None:
    decisions = (Path(__file__).parents[1] / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    baseline = json.loads(
        (Path(__file__).parents[1] / "tools" / "upstream_baseline.json").read_text(encoding="utf-8")
    )

    assert baseline["reviewed_date"] in decisions
    assert baseline["reviewed_through"][:7] in decisions
