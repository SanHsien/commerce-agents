"""Contract tests for the divergence registry check.

`docs/DIVERGENCE.md` is only trustworthy if it is exactly the set of upstream-owned
files this fork has actually changed -- not a superset (stale rows nobody removed) and
not a subset (a silent edit nobody wrote down). These tests pin the parsing, the
comparison in both directions, the README.en.md rename special case (and why an
ordinary added file does *not* count), and the two ways this can legitimately not run
at all: a missing/unreachable base commit (shallow clone) degrades to a warning and
exit 0, never a false pass or a false failure.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import check_divergence as checker  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8"
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.fixture
def tiny_repo(tmp_path: Path) -> tuple[Path, str]:
    """A throwaway git repo shaped like a fork point: one base commit, then a fork
    commit that modifies one upstream file, deletes another, and adds a new one."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["init", "--initial-branch=main"], repo)
    _run(["config", "user.email", "test@example.invalid"], repo)
    _run(["config", "user.name", "Test"], repo)
    (repo / "UPSTREAM.md").write_text("original\n", encoding="utf-8")
    (repo / "KEEP.md").write_text("keep\n", encoding="utf-8")
    _run(["add", "."], repo)
    _run(["commit", "-m", "base"], repo)
    base_sha = _run(["rev-parse", "HEAD"], repo).strip()

    (repo / "UPSTREAM.md").write_text("forked\n", encoding="utf-8")
    (repo / "KEEP.md").unlink()
    (repo / "NEW.md").write_text("new\n", encoding="utf-8")
    _run(["add", "-A"], repo)
    _run(["commit", "-m", "fork changes"], repo)

    return repo, base_sha


def test_owned_files_at_base_lists_only_what_existed_at_that_commit(
    tiny_repo: tuple[Path, str],
) -> None:
    repo, base_sha = tiny_repo
    assert checker.owned_files_at_base(base_sha, repo) == {"UPSTREAM.md", "KEEP.md"}


def test_changed_since_base_reports_modify_delete_and_add(
    tiny_repo: tuple[Path, str],
) -> None:
    repo, base_sha = tiny_repo
    statuses = dict((path, status) for status, path in checker.changed_since_base(base_sha, repo))
    assert statuses == {"UPSTREAM.md": "M", "KEEP.md": "D", "NEW.md": "A"}


def test_compute_divergent_files_excludes_a_newly_added_file(
    tiny_repo: tuple[Path, str],
) -> None:
    repo, base_sha = tiny_repo
    owned = checker.owned_files_at_base(base_sha, repo)
    pairs = checker.changed_since_base(base_sha, repo)
    divergent = checker.compute_divergent_files(pairs, owned)
    assert divergent == {"UPSTREAM.md", "KEEP.md"}
    assert "NEW.md" not in divergent


def test_base_commit_available_distinguishes_real_from_bogus_sha(
    tiny_repo: tuple[Path, str],
) -> None:
    repo, base_sha = tiny_repo
    assert checker.base_commit_available(base_sha, repo) is True
    assert checker.base_commit_available("f" * 40, repo) is False


def test_readme_en_alias_counts_as_divergent_for_the_upstream_file_it_stands_in_for() -> None:
    """git cannot detect this as a rename (README.md is modified, not deleted, at
    HEAD), which is why the alias is hardcoded rather than left to `-M`."""
    owned = {"README.md"}
    pairs = [("M", "README.md"), ("A", "README.en.md")]
    assert checker.compute_divergent_files(pairs, owned) == {"README.md", "README.en.md"}


def test_an_added_file_without_a_registered_alias_is_not_a_divergence() -> None:
    owned = {"README.md"}
    pairs = [("A", "NOTICE.md")]
    assert checker.compute_divergent_files(pairs, owned) == set()


def test_parse_registered_paths_skips_header_and_separator_rows() -> None:
    text = (
        "| 上游檔案 | 上游原狀 |\n"
        "|---|---|\n"
        "| `README.md` | something |\n"
        "| `requirements-dev.txt` | something else |\n"
    )
    assert checker.parse_registered_paths(text) == {"README.md", "requirements-dev.txt"}


def test_the_repos_own_divergence_doc_registers_exactly_the_documented_files() -> None:
    text = (REPO_ROOT / "docs" / "DIVERGENCE.md").read_text(encoding="utf-8")
    assert checker.parse_registered_paths(text) == {
        "README.md",
        "README.en.md",
        "CLAUDE.md",
        ".gitignore",
        "ruff.toml",
        "requirements-dev.txt",
        ".github/workflows/ci.yml",
        "commerce-common/commerce_common/agent_sdk.py",
        "commerce-common/tests/test_agent_sdk.py",
        "commerce-common/tests/test_memory_stores.py",
        "examples/package.json",
        "examples/package-lock.json",
        "examples/retail/storefront-web/package.json",
        "examples/retail/merchant-web/package.json",
        "examples/travel/storefront-web/package.json",
        "examples/travel/merchant-web/package.json",
        "examples/telecom/storefront-web/package.json",
        "examples/telecom/merchant-web/package.json",
        "examples/entertainment/storefront-web/package.json",
        "examples/entertainment/merchant-web/package.json",
        "examples/web-shared/storefront/orders.tsx",
        "plugins/commerce-builder/commands/scaffold-commerce-agent.md",
        "shopping-agent/core/shopping_agent/enrichment.py",
        "shopping-agent/core/tests/test_executor.py",
        "examples/retail/api/mock_merchant.py",
        "examples/retail/api/tests/test_retail_merchant_backend.py",
        "merchant-agent/core/merchant_agent/backend.py",
        "shopping-agent/core/shopping_agent/executor.py",
        "shopping-agent/core/shopping_agent/types.py",
        "merchant-agent/core/merchant_agent/changes.py",
        "merchant-agent/core/tests/test_changes.py",
        "examples/demo_common/storefront_fixtures.py",
        "examples/retail/api/mock_retail.py",
        "examples/retail/api/tests/test_mock_retail.py",
        "examples/demo_common/merchant_fixtures.py",
        "examples/demo_common/tests/test_merchant_fixtures.py",
        "examples/travel/api/mock_travel.py",
        "examples/travel/api/tests/test_mock_travel.py",
        "examples/entertainment/api/ticketing.py",
        "examples/entertainment/api/tests/test_holds.py",
        "commerce-common/commerce_common/config.py",
        "commerce-common/tests/test_config.py",
        "commerce-common/commerce_common/memory.py",
        "commerce-common/commerce_common/skills.py",
        "commerce-common/tests/test_skills.py",
        "commerce-common/commerce_common/grounding.py",
        "commerce-common/tests/test_grounding.py",
        "tests/test_turn_loop.py",
        "examples/demo_common/host.py",
        "examples/demo_common/tests/test_host.py",
        "examples/demo_common/storefront.py",
        "examples/demo_common/merchant.py",
        "examples/demo_common/tests/contract.py",
        "shopping-agent/core/shopping_agent/config.py",
        "shopping-agent/core/shopping_agent/prompt.py",
        "shopping-agent/core/tests/test_prompt.py",
        "shopping-agent/core/shopping_agent/backend.py",
    }


def test_compare_reports_both_mismatch_directions() -> None:
    changed_not_registered, registered_not_changed = checker.compare({"a", "b"}, {"b", "c"})
    assert changed_not_registered == {"a"}
    assert registered_not_changed == {"c"}


def test_render_report_says_ok_when_everything_matches() -> None:
    report = checker.render_report("a" * 40, {"x"}, {"x"}, set(), set())
    assert "OK" in report


def test_render_report_lists_both_mismatch_directions() -> None:
    report = checker.render_report("a" * 40, {"x"}, {"y"}, {"x"}, {"y"})
    assert "NOT registered" in report
    assert "NOT actually changed" in report


def test_render_json_round_trips() -> None:
    payload = json.loads(checker.render_json("a" * 40, {"x"}, {"x"}, set(), set()))
    assert payload["base_commit"] == "a" * 40
    assert payload["changed_upstream_files"] == ["x"]
    assert payload["warning"] is None


def test_load_baseline_rejects_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(checker.DivergenceCheckError):
        checker.load_baseline(tmp_path / "nope.json")


def test_load_baseline_rejects_a_short_reviewed_through(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"reviewed_through": "abc"}), encoding="utf-8")
    with pytest.raises(checker.DivergenceCheckError):
        checker.load_baseline(path)


def test_the_repos_own_baseline_is_readable_by_this_checker() -> None:
    baseline = checker.load_baseline()
    assert len(baseline["reviewed_through"]) == 40


def test_main_degrades_to_a_warning_and_exit_zero_when_the_base_commit_is_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Simulates a shallow clone: the baseline names a commit this local repo does
    not have. There is no way to compute a real answer, so this must not fail the
    check -- it must say so and exit 0."""
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": "f" * 40})
    monkeypatch.setattr(sys, "argv", ["check_divergence.py", "--repo-dir", str(REPO_ROOT)])

    exit_code = checker.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "WARNING" in captured.out


def _registry(*paths: str) -> str:
    """A fixture registry with the real table's five columns.

    These fixtures used to carry two columns, which `parse_registered_paths` accepted
    because it only ever reads the first cell. Once `malformed_rows` enforces the shape,
    a two-column fixture would make every `main()` test red for the wrong reason, so the
    fixtures now look like the document they stand in for.
    """
    header = "| 上游檔案 | 上游原狀 | 本 fork 狀態 | 為什麼分岔 | 跟進上游時怎麼處理 |\n"
    header += "|---|---|---|---|---|\n"
    rows = "".join(f"| `{path}` | was | is | why | how |\n" for path in paths)
    return header + rows


def test_malformed_rows_names_every_row_whose_column_count_is_wrong() -> None:
    """16 real rows were missing 為什麼分岔 and 2 were split by an unescaped `|` in a type
    union, for weeks, because the parser only ever read the first cell."""
    text = (
        "| 上游檔案 | 上游原狀 | 本 fork 狀態 | 為什麼分岔 | 跟進上游時怎麼處理 |\n"
        "|---|---|---|---|---|\n"
        "| `ok.py` | was | is | why | how |\n"
        "| `short.py` | was | is | how |\n"
        "| `wide.py` | was | `X | None` | why | how |\n"
        "| `escaped.py` | was | `X \\| None` | why | how |\n"
    )

    bad = checker.malformed_rows(text)

    assert [(cols, path) for _, cols, path in bad] == [(4, "short.py"), (6, "wide.py")]
    # The correctly escaped pipe is NOT a finding: `\|` is how GFM writes a literal pipe.
    assert "escaped.py" not in {path for _, _, path in bad}


def test_column_count_resolves_backslash_runs_the_way_gfm_does() -> None:
    """GFM escapes "the punctuation after a backslash", so in `b\\\\|` the first backslash
    escapes the second and the pipe IS a separator. A `(?<!\\\\)\\|` lookbehind got this
    wrong in both directions -- including reading a genuinely six-column row as five,
    which is a false pass. The trailing `|` is optional in GFM, so a row without one is
    not malformed either.
    """
    bs = "\\"

    assert checker._column_count(f"| `a.py` | b {bs}| c | d | e | f |") == 5  # literal pipe
    assert checker._column_count(f"| `a.py` | b{bs}{bs}| c | d | e |") == 5  # real separator
    assert checker._column_count(f"| `a.py` | b | c{bs}{bs}| d | e | f |") == 6  # was a false pass
    assert checker._column_count("| `a.py` | b | c | d | e") == 5  # no trailing pipe
    assert checker._column_count("| `a.py` | b | c | d | e |") == 5


def test_the_real_registry_has_no_malformed_rows() -> None:
    text = (REPO_ROOT / "docs" / "DIVERGENCE.md").read_text(encoding="utf-8")

    assert checker.malformed_rows(text) == []


def test_main_returns_one_for_a_malformed_row_even_when_every_path_matches(
    tiny_repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The path comparison passing is not enough: a row missing a column registers its
    path just fine and would otherwise read as a clean bill of health."""
    repo, base_sha = tiny_repo
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": base_sha})
    doc = repo / "DIVERGENCE.md"
    doc.write_text(
        _registry("UPSTREAM.md").replace(
            "| `UPSTREAM.md` | was | is | why | how |", "| `UPSTREAM.md` | was | is | how |"
        )
        + "| `KEEP.md` | was | is | why | how |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys, "argv", ["check_divergence.py", "--repo-dir", str(repo), "--divergence-doc", str(doc)]
    )

    assert checker.main() == 1


def test_json_output_stays_parseable_and_carries_malformed_rows(
    tiny_repo: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`--json` promises JSON on stdout. Printing the human-readable malformed-row block
    after the document broke every parser, and the payload itself could not express the
    failure at all: four empty lists and a null warning beside exit code 1 reads as a
    clean bill of health."""
    repo, base_sha = tiny_repo
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": base_sha})
    doc = repo / "DIVERGENCE.md"
    doc.write_text(
        _registry("UPSTREAM.md").replace(
            "| `UPSTREAM.md` | was | is | why | how |", "| `UPSTREAM.md` | was | is | how |"
        )
        + "| `KEEP.md` | was | is | why | how |\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["check_divergence.py", "--repo-dir", str(repo), "--divergence-doc", str(doc), "--json"],
    )

    exit_code = checker.main()
    out = capsys.readouterr().out

    assert exit_code == 1
    payload = json.loads(out)  # the whole of stdout, not a prefix of it
    assert [row["path"] for row in payload["malformed_rows"]] == ["UPSTREAM.md"]
    assert payload["malformed_rows"][0]["columns"] == 4
    assert "Rows with the wrong number of columns" not in out


def test_main_reports_ok_when_the_registry_matches_real_changes(
    tiny_repo: tuple[Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo, base_sha = tiny_repo
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": base_sha})
    doc = repo / "DIVERGENCE.md"
    doc.write_text(_registry("UPSTREAM.md", "KEEP.md"), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["check_divergence.py", "--repo-dir", str(repo), "--divergence-doc", str(doc)]
    )

    exit_code = checker.main()

    assert exit_code == 0
    assert "OK" in capsys.readouterr().out


def test_main_returns_one_when_a_real_change_is_not_registered(
    tiny_repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base_sha = tiny_repo
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": base_sha})
    doc = repo / "DIVERGENCE.md"
    # KEEP.md's deletion is real but not registered here: this must go red.
    doc.write_text(_registry("UPSTREAM.md"), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["check_divergence.py", "--repo-dir", str(repo), "--divergence-doc", str(doc)]
    )

    assert checker.main() == 1


def test_main_returns_one_when_a_registered_row_was_not_actually_changed(
    tiny_repo: tuple[Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    repo, base_sha = tiny_repo
    monkeypatch.setattr(checker, "load_baseline", lambda: {"reviewed_through": base_sha})
    doc = repo / "DIVERGENCE.md"
    # UNTOUCHED.md is not a real change; registering it anyway must go red too.
    doc.write_text(_registry("UPSTREAM.md", "KEEP.md", "UNTOUCHED.md"), encoding="utf-8")
    monkeypatch.setattr(
        sys, "argv", ["check_divergence.py", "--repo-dir", str(repo), "--divergence-doc", str(doc)]
    )

    assert checker.main() == 1
