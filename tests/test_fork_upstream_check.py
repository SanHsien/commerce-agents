from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_upstream_updates as checker  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


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


MONITORED_BASELINE = {"repo": "https://github.com/anthropics/commerce-agents.git"}


def test_baseline_pins_every_conditional_verdict_recorded_in_decisions() -> None:
    """Every row of `docs/DECISIONS.md`'s PR table whose verdict is 觀察 (monitor) must be
    pinned in `monitored`, and nothing else should be.

    Derived from the decision log rather than hard-coded: a fixed set would catch an
    entry being deleted but not a NEW conditional verdict nobody pinned -- which is the
    very thing this axis exists to prevent, reproduced one level up. The list this
    compares against must have a source, or it is another list nobody checks.
    """
    import re as _re

    decisions = (REPO_ROOT / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    row = _re.compile(r"^\| #(\d+) \|(.*)$", _re.MULTILINE)
    conditional = {
        f"pr#{match.group(1)}" for match in row.finditer(decisions) if "觀察" in match.group(2)
    }
    assert conditional, "parsed no 觀察 rows out of docs/DECISIONS.md -- the parser is wrong"

    baseline = checker.load_baseline()
    pinned = {entry["item"] for entry in baseline["monitored"]}

    assert pinned == conditional
    for entry in baseline["monitored"]:
        assert len(entry["head"]) >= 7
        assert entry["state"] in {"open", "draft", "closed"}


def test_load_baseline_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(checker.UpstreamCheckError):
        checker.load_baseline(tmp_path / "nope.json")


def test_baseline_matches_decisions_record() -> None:
    decisions = (Path(__file__).parents[1] / "docs" / "DECISIONS.md").read_text(encoding="utf-8")
    baseline = json.loads(
        (Path(__file__).parents[1] / "tools" / "upstream_baseline.json").read_text(encoding="utf-8")
    )

    assert baseline["reviewed_date"] in decisions
    assert baseline["reviewed_through"][:7] in decisions


def test_collect_new_commits_survives_unicode_line_separators_in_a_subject(
    monkeypatch: object,
) -> None:
    """`str.splitlines()` also splits on U+2028, U+0085 and form feed, all legal in a
    commit subject a stranger wrote. The fragment after the break has no field separator
    and the unpack raised ValueError, which `main` does not catch."""
    outputs = {
        "log": "a" * 40 + "\x1f2026-01-01\x1fsplit subject\n",
        "show": "README.md\n",
    }

    def fake_run_git(args: list[str], repo_dir: Path) -> str:
        return outputs[args[0]]

    monkeypatch.setattr(checker, "run_git", fake_run_git)

    commits = checker.collect_new_commits(
        {"reviewed_through": "b" * 40}, REPO_ROOT, "refs/upstream-check/main"
    )

    assert [c["subject"] for c in commits] == ["split subject"]


def test_baseline_keeps_the_branch_axis_switched_on() -> None:
    """Dropping `check_branches` would silently turn the branch axis off (exit 0, no error)."""
    baseline = checker.load_baseline()
    assert checker.branch_axis_enabled(baseline)
    assert baseline["branch"] in baseline["branches"]
