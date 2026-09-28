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


def test_baseline_declares_a_branch_list_the_checker_can_compare() -> None:
    """This used to pin the exact list (`== ["main"]`), which was wrong twice over: it
    went stale the moment upstream pushed a branch, and it tested the file instead of
    the behaviour -- nothing compared the list to upstream at all. What the checker
    actually needs from the baseline is a usable list containing the tracked branch;
    whether it matches upstream is `collect_new_branches`' job, at runtime."""
    baseline = checker.load_baseline()
    branches = baseline.get("branches")

    assert isinstance(branches, list) and branches
    assert all(isinstance(name, str) and name for name in branches)
    assert baseline["branch"] in branches
    # The shape the axis requires: anything else makes it report UNDECLARED and fail.
    assert checker.collect_new_branches({"repo": "x", "branches": branches}, Path(".")) is not (
        checker.UNDECLARED
    )


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


def test_collect_new_branches_reports_branches_missing_from_the_baseline(
    monkeypatch: object,
) -> None:
    """The commit axis only reads `baseline["branch"]`, so a branch pushed beside it
    is invisible unless this axis names it."""
    import subprocess

    class FakeResult:
        returncode = 0
        stdout = (
            "aaa\trefs/heads/main\n"
            "bbb\trefs/heads/dependabot/npm_and_yarn/examples/next-16.3.4\n"
            "ccc\trefs/heads/release/1.x\n"
        )
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    baseline = {"repo": "https://github.com/anthropics/commerce-agents.git", "branches": ["main"]}
    result = checker.collect_new_branches(baseline, Path("."))

    assert result == ["dependabot/npm_and_yarn/examples/next-16.3.4", "release/1.x"]


def test_collect_new_branches_is_quiet_once_every_branch_is_registered(
    monkeypatch: object,
) -> None:
    import subprocess

    class FakeResult:
        returncode = 0
        stdout = "aaa\trefs/heads/main\nbbb\trefs/heads/release/1.x\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    baseline = {"repo": "https://example.invalid/u.git", "branches": ["main", "release/1.x"]}

    assert checker.collect_new_branches(baseline, Path(".")) == []


def test_collect_new_branches_separates_undeclared_from_unavailable(monkeypatch: object) -> None:
    """A baseline with no `branches` list and a failed `ls-remote` are different
    problems; neither may read as "nothing new"."""
    import subprocess

    class Failed:
        returncode = 128
        stdout = ""
        stderr = "fatal: repository not found"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())

    assert checker.collect_new_branches({"repo": "x"}, Path(".")) is checker.UNDECLARED
    assert checker.collect_new_branches({"repo": "x", "branches": "main"}, Path(".")) is (
        checker.UNDECLARED
    )
    assert checker.collect_new_branches({"repo": "x", "branches": ["main"]}, Path(".")) is None


def test_collect_new_branches_rejects_an_empty_parse(monkeypatch: object) -> None:
    """`ls-remote` exiting 0 with nothing this reader recognises means the output
    shape changed, not that upstream has no branches."""
    import subprocess

    class FakeResult:
        returncode = 0
        stdout = "aaa\trefs/tags/v1.0.0\n"
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())

    baseline = {"repo": "https://example.invalid/u.git", "branches": ["main"]}

    assert checker.collect_new_branches(baseline, Path(".")) is None


def test_render_markdown_names_new_upstream_branches() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
        "branches": ["main"],
    }

    report = checker.render_markdown(
        baseline, [], prs=[], issues=checker.DISABLED, branches=["release/1.x"]
    )

    assert "## Upstream branches" in report
    assert "release/1.x" in report
    assert "No branches beyond the registered ones." not in report


def _fake_pr_list(monkeypatch: object, rows: list[dict]) -> None:
    import subprocess

    class FakeResult:
        returncode = 0
        stdout = json.dumps(rows)
        stderr = ""

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeResult())


MONITORED_BASELINE = {"repo": "https://github.com/anthropics/commerce-agents.git"}


def test_stale_monitored_reports_a_head_that_moved(monkeypatch: object) -> None:
    """The real case: upstream updated #20 after the verdict was recorded, and because
    `reviewed_pr_through` was already past 20 nothing ever mentioned it again."""
    _fake_pr_list(
        monkeypatch,
        [
            {
                "number": 20,
                "state": "OPEN",
                "isDraft": True,
                "headRefOid": "8b7f9b93e8e1aaaabbbbccccddddeeeeffff0000",
            }
        ],
    )
    baseline = {
        **MONITORED_BASELINE,
        "monitored": [{"item": "pr#20", "head": "b3cfe06", "state": "draft"}],
    }

    stale = checker.collect_stale_monitored(baseline)

    assert [entry["item"] for entry in stale] == ["pr#20"]
    assert "b3cfe06" in stale[0]["was"] and "8b7f9b9" in stale[0]["now"]


def test_stale_monitored_is_quiet_when_head_and_state_both_hold(monkeypatch: object) -> None:
    _fake_pr_list(
        monkeypatch,
        [
            {
                "number": 7,
                "state": "OPEN",
                "isDraft": False,
                "headRefOid": "564922102c484dd79cc93770198dbe93297fd58d",
            }
        ],
    )
    baseline = {
        **MONITORED_BASELINE,
        "monitored": [{"item": "pr#7", "head": "5649221", "state": "open"}],
    }

    assert checker.collect_stale_monitored(baseline) == []


def test_stale_monitored_reports_a_state_change_at_the_same_head(monkeypatch: object) -> None:
    """A draft going non-draft, or an item closing, invalidates a "no code yet" verdict
    just as surely as a new commit does."""
    _fake_pr_list(
        monkeypatch,
        [
            {
                "number": 19,
                "state": "OPEN",
                "isDraft": False,
                "headRefOid": "e49a738000000000000000000000000000000000",
            }
        ],
    )
    baseline = {
        **MONITORED_BASELINE,
        "monitored": [{"item": "pr#19", "head": "e49a738", "state": "draft"}],
    }

    stale = checker.collect_stale_monitored(baseline)

    assert len(stale) == 1
    assert "draft" in stale[0]["was"] and "open" in stale[0]["now"]


def test_stale_monitored_treats_an_unverifiable_pin_as_drift(monkeypatch: object) -> None:
    """`docs/DECISIONS.md` recorded #21 as `7adc548`; upstream's head is `7adc54c`, so
    that pin never matched anything and was never going to. A pin too short to identify
    a commit, or missing outright, is drift rather than a silent pass."""
    _fake_pr_list(
        monkeypatch,
        [
            {
                "number": 21,
                "state": "OPEN",
                "isDraft": True,
                "headRefOid": "7adc54c7837a0000000000000000000000000000",
            }
        ],
    )

    for pin in ("7adc548", "7adc5", ""):
        baseline = {
            **MONITORED_BASELINE,
            "monitored": [{"item": "pr#21", "head": pin, "state": "draft"}],
        }
        assert len(checker.collect_stale_monitored(baseline)) == 1, pin


def test_stale_monitored_reports_an_item_upstream_no_longer_lists(monkeypatch: object) -> None:
    _fake_pr_list(
        monkeypatch, [{"number": 99, "state": "OPEN", "isDraft": False, "headRefOid": "a" * 40}]
    )
    baseline = {
        **MONITORED_BASELINE,
        "monitored": [{"item": "pr#7", "head": "5649221", "state": "open"}],
    }

    stale = checker.collect_stale_monitored(baseline)

    assert stale[0]["now"] == "not found"


def test_stale_monitored_separates_undeclared_from_unavailable(monkeypatch: object) -> None:
    import subprocess

    class Failed:
        returncode = 1
        stdout = ""
        stderr = "gh: authentication required"

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: Failed())

    assert checker.collect_stale_monitored(MONITORED_BASELINE) is checker.UNDECLARED
    assert checker.collect_stale_monitored({**MONITORED_BASELINE, "monitored": "pr#7"}) is (
        checker.UNDECLARED
    )
    # A malformed entry is undeclared, not "nothing moved".
    assert (
        checker.collect_stale_monitored({**MONITORED_BASELINE, "monitored": [{"item": "issue#7"}]})
        is checker.UNDECLARED
    )
    assert (
        checker.collect_stale_monitored(
            {**MONITORED_BASELINE, "monitored": [{"item": "pr#7", "head": "x", "state": "open"}]}
        )
        is None
    )


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


def test_render_markdown_names_stale_monitored_items() -> None:
    baseline = {
        "repo": "https://example.invalid/upstream.git",
        "branch": "main",
        "reviewed_through": "a" * 40,
        "reviewed_date": "2026-09-05",
        "branches": ["main"],
        "monitored": [{"item": "pr#20", "head": "b3cfe06", "state": "draft"}],
    }

    report = checker.render_markdown(
        baseline,
        [],
        prs=[],
        issues=checker.DISABLED,
        branches=[],
        monitored=[{"item": "pr#20", "was": "b3cfe06 / draft", "now": "8b7f9b9 / draft"}],
    )

    assert "Monitored upstream items" in report
    assert "pr#20" in report
    assert "Every pinned item is still at the head" not in report


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
