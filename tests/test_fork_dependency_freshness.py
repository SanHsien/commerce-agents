"""Contract tests for the dependency freshness check.

The check is only useful if a red line means "someone has to look". Two things
can make that false: a false alarm that fires every month until people stop
reading the report, and a silencing move that hides a real gap. These tests pin
both edges -- the declared-precision comparison, and the two documented exits
(hold and deferral) with the deferral expiring by itself -- across both
declaration sources this fork actually checks: `requirements-dev.txt` and
pinned GitHub Actions. `requirements.txt` (upstream's exact runtime pins) and
`examples/package-lock.json` (upstream's npm lockfile) are out of scope by
design; see docs/DECISIONS.md.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_dependency_freshness as checker  # noqa: E402


def test_comparison_uses_the_precision_the_declaration_states() -> None:
    # `>=7` says nothing about the minor, so 7.4.0 must not be a monthly alarm.
    assert not checker.is_newer_version("7.4.0", "7")
    assert checker.is_newer_version("8.0.0", "7")
    assert checker.is_newer_version("7.4.0", "7.3")
    assert not checker.is_newer_version("7.3.2", "7.3")


def test_prerelease_suffix_does_not_count_as_newer() -> None:
    assert not checker.is_newer_version("7.0.0rc1", "7.0.0")


def test_leading_v_is_stripped_for_github_action_tags() -> None:
    assert checker.is_newer_version("v7.1.0", "7.0.1")
    assert not checker.is_newer_version("v7.0.1", "7.0.1")


def test_hold_marker_is_read_off_the_declaring_line() -> None:
    packages = checker.parse_requirements(
        "pytest>=8.3  # freshness-hold: pinned for a documented reason\nruff>=0.16\n",
        "requirements-dev.txt",
    )

    holds = {package["name"]: package["hold"] for package in packages}
    assert holds["ruff"] == ""
    assert holds["pytest"].startswith("pinned for a documented reason")


def test_every_fork_owned_requirements_file_is_checked() -> None:
    """`requirements-dev.txt` is the only declaration file this fork checks now.

    The Windows-only `tzdata` pin used to live in a fork-only sibling file so upstream's
    `requirements-dev.txt` stayed at zero diff; that policy was retired (see
    docs/DIVERGENCE.md), and `tzdata` was folded into `requirements-dev.txt` itself behind
    an environment marker. `REQUIREMENT_FILES` must therefore be exactly this one file, and
    `tzdata` must still be read out of it (with the marker stripped) so its pin does not
    age with nothing watching it.
    """
    assert checker.REQUIREMENT_FILES == ("requirements-dev.txt",)
    for name in checker.REQUIREMENT_FILES:
        assert (checker.REPO_ROOT / name).is_file(), f"{name} is checked but missing"

    packages = checker.load_direct_dependencies()
    by_name = {package["name"]: package for package in packages}
    assert by_name["tzdata"]["source"] == "requirements-dev.txt"
    assert by_name["tzdata"]["minimum"] == "2026.3"


def test_a_requirements_include_line_is_not_expanded() -> None:
    """`-r requirements.txt` must not pull upstream's exact pins into this check."""
    packages = checker.parse_requirements(
        "-r requirements.txt\npytest==9.1.1\nruff==0.16.3\n",
        "requirements-dev.txt",
    )
    names = {package["name"] for package in packages}
    assert names == {"pytest", "ruff"}


def test_workflow_actions_are_parsed_with_their_declared_version() -> None:
    text = (
        "jobs:\n"
        "  test:\n"
        "    steps:\n"
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1\n"
        "      - uses: actions/setup-node@820762786026740c76f36085b0efc47a31fe5020 # v7.0.0\n"
    )

    packages = checker.parse_workflow_actions(text, "ci.yml")

    by_name = {p["name"]: p for p in packages}
    assert by_name["actions/checkout"]["minimum"] == "7.0.1"
    assert by_name["actions/checkout"]["source"] == "ci.yml"
    assert by_name["actions/checkout"]["hold"] == ""


def test_workflow_action_hold_marker_is_read_off_the_uses_line() -> None:
    text = (
        "      - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
        " # freshness-hold: pinned for a documented reason\n"
    )

    packages = checker.parse_workflow_actions(text, "ci.yml")

    assert packages[0]["hold"] == "pinned for a documented reason"
    assert packages[0]["minimum"] == ""


def test_real_workflows_declare_at_least_one_pinned_action() -> None:
    actions = checker.load_workflow_actions()

    assert len(actions) >= 3
    assert all(a["minimum"] or a["hold"] for a in actions)


def test_real_requirements_dev_declares_pytest_and_ruff() -> None:
    packages = checker.load_direct_dependencies()
    names = {package["name"].lower() for package in packages}
    assert {"pytest", "ruff"} <= names


def test_a_held_floor_is_reported_but_does_not_ask_for_work() -> None:
    packages = checker.parse_requirements(
        "pytest>=8.3  # freshness-hold: CI still tests an older Python\n",
        "requirements-dev.txt",
    )

    rows = checker.collect_status(packages, lambda _name: "9.1.0", deferrals={})

    assert rows[0]["outdated"] is True
    assert checker.needs_review(rows[0]) is False
    assert "HELD: CI still tests an older Python" in checker.render_markdown(rows)


def test_a_live_deferral_covers_the_row_and_says_what_it_was_reviewed_against() -> None:
    packages = checker.parse_requirements("pytest>=8.3\n", "requirements-dev.txt")

    rows = checker.collect_status(
        packages,
        lambda _name: "9.1.0",
        deferrals={"pytest": ("9.1", "reviewed 2026-08; wait for the 9.x line to settle")},
    )

    assert checker.needs_review(rows[0]) is False
    assert "DEFERRED at 9.1.0" in checker.render_markdown(rows)


def test_a_deferral_expires_once_the_upstream_source_moves_past_the_reviewed_release() -> None:
    """This is the whole point of `deferredLatest`: it cannot become a mute button."""
    packages = checker.parse_requirements("pytest>=8.3\n", "requirements-dev.txt")

    rows = checker.collect_status(
        packages, lambda _name: "10.0.0", deferrals={"pytest": ("9.1", "not this month")}
    )

    assert checker.needs_review(rows[0]) is True
    assert "REVIEW UPDATE" in checker.render_markdown(rows)


def test_deferral_without_a_reviewed_release_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "dependency-deferrals.json"
    path.write_text(
        json.dumps(
            {
                "deferrals": {
                    "kept": {"deferredLatest": "9.1", "reason": "reviewed, not now"},
                    "no-release": {"reason": "reviewed, not now"},
                    "no-reason": {"deferredLatest": "9.1"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert checker.load_deferrals(path) == {"kept": ("9.1", "reviewed, not now")}


def test_missing_deferrals_file_is_not_an_error(tmp_path: Path) -> None:
    assert checker.load_deferrals(tmp_path / "nope.json") == {}


def test_the_repos_own_deferrals_file_parses() -> None:
    """This fork now raises its own declared floors directly instead of waiting on
    upstream's pace (see docs/DIVERGENCE.md), so `.github/dependency-deferrals.json`
    starts empty; a deferral is reserved for a floor that would genuinely break
    something if raised right now, not for "waiting on upstream"."""
    assert checker.load_deferrals() == {}


def test_an_action_published_from_a_subdirectory_is_parsed_and_resolved() -> None:
    """`github/codeql-action/init` is a real declaration; an owner/repo-only pattern
    matched nothing on those lines, so codeql.yml's two pins were invisible to the
    report -- silently, which is the worst way for a check to be wrong."""
    text = (
        "      - uses: github/codeql-action/init"
        "@a35ac6e6798d72df5475948b28efb89edc2e19ca # v4.37.9\n"
    )
    parsed = checker.parse_workflow_actions(text, "codeql.yml")

    assert [p["name"] for p in parsed] == ["github/codeql-action/init"]
    assert parsed[0]["minimum"] == "4.37.9"
    # Releases live on the publishing repository, not the sub-path.
    assert checker.action_repository("github/codeql-action/init") == "github/codeql-action"
    assert checker.action_repository("actions/checkout") == "actions/checkout"


def test_a_latest_that_cannot_be_compared_is_a_failed_check_not_an_ok_row() -> None:
    """The false green this whole fix exists to remove.

    `github/codeql-action` tags its latest *release* `codeql-bundle-v2.27.0`. Compared
    against a `v4.37.9` pin that parses to nothing, scores as "not newer", and reports
    OK -- forever, no matter how far behind the pin drifts. A check that cannot fail is
    not a check, so an unresolvable latest has to land in `check_failed`.
    """
    rows = checker.collect_status(
        [{"name": "github/codeql-action/init", "minimum": "4.37.9", "hold": ""}],
        lambda _name: None,
        deferrals={},
    )

    assert rows[0]["latest"] == "unknown"
    assert rows[0]["check_failed"] is True
    assert rows[0]["outdated"] is False


def test_a_bundle_style_release_tag_falls_back_to_the_version_tags() -> None:
    """`fetch_github_release` must return a comparable version or None -- never a tag
    whose text happens to parse to nothing. The fallback reads `/tags` for the newest
    `vX.Y.Z`, which is where the action's own version actually lives."""
    calls: list[str] = []

    def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
        calls.append(request.full_url)
        body = (
            b'{"tag_name": "codeql-bundle-v2.27.0"}'
            if "releases/latest" in request.full_url
            else b'[{"name": "codeql-bundle-v2.27.0"}, {"name": "v4.37.9"}, {"name": "v4.37.8"}]'
        )

        class _Response:
            def read(self) -> bytes:
                return body

            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_: object) -> None:
                return None

        return _Response()

    original = checker.urllib.request.urlopen
    checker.urllib.request.urlopen = fake_urlopen
    try:
        latest = checker.fetch_github_release("github/codeql-action/init")
    finally:
        checker.urllib.request.urlopen = original

    assert latest == "4.37.9"
    # The sub-path never reaches the API: releases and tags live on the repository.
    assert all("codeql-action/init" not in url for url in calls)


def test_a_token_is_sent_when_the_environment_has_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anonymous api.github.com allows 60 requests an hour, and hosted runners share
    that pool; past it every Action row reads "unknown" and the check goes quiet."""
    seen: dict[str, str] = {}

    def fake_urlopen(request, timeout):  # noqa: ANN001, ARG001
        seen.update(request.headers)

        class _Response:
            def read(self) -> bytes:
                return b'{"tag_name": "v7.0.1"}'

            def __enter__(self) -> _Response:
                return self

            def __exit__(self, *_: object) -> None:
                return None

        return _Response()

    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr(checker.urllib.request, "urlopen", fake_urlopen)

    assert checker.fetch_github_release("actions/checkout") == "7.0.1"
    assert seen.get("Authorization") == "Bearer secret-token"


def test_the_repos_own_codeql_pins_reach_the_report() -> None:
    """The live contract: both codeql.yml declarations must be collected."""
    names = {action["name"] for action in checker.load_workflow_actions()}

    assert "github/codeql-action/init" in names
    assert "github/codeql-action/analyze" in names


def test_report_puts_raising_the_declaration_first_and_still_names_both_escape_hatches() -> None:
    """The report is where the policy is actually read, so the order encodes it.

    Under the 2026-09-05 reversal the default answer to a red line is to raise the
    declaration; a hold or a deferral is the exception, for something that would
    genuinely break now. A report that led with the escape hatches would teach the
    opposite -- so this asserts the ordering, not just that the words appear.
    """
    report = checker.render_markdown([], [])

    assert "raise the declaration" in report
    assert "docs/DIVERGENCE.md" in report
    assert "freshness-hold:" in report
    assert "dependency-deferrals.json" in report
    assert "waiting for upstream to move first" in report
    assert report.index("raise the declaration") < report.index("freshness-hold:")


def test_report_has_a_section_for_each_declaration_source() -> None:
    report = checker.render_markdown([], [])

    assert "Python dev dependencies" in report
    assert "GitHub Actions" in report


def test_report_documents_the_npm_and_exact_pin_exclusion() -> None:
    report = checker.render_markdown([], [])

    assert "package-lock.json" in report


def test_json_output_round_trips_and_flags_review_items() -> None:
    packages = checker.parse_requirements("pytest>=8.3\n", "requirements-dev.txt")
    rows = checker.collect_status(packages, lambda _name: "9.1.0", deferrals={})

    payload = json.loads(checker.render_json(rows, [], None))

    assert payload["error"] is None
    assert payload["needs_review"] == ["pytest"]
    assert payload["python_dependencies"][0]["name"] == "pytest"


def test_json_output_surfaces_the_check_error() -> None:
    payload = json.loads(checker.render_json([], [], "missing requirements file: nope.txt"))

    assert payload["error"] == "missing requirements file: nope.txt"
