"""Enforce that `docs/DIVERGENCE.md` lists exactly the upstream files this fork has

changed or deleted since the reviewed baseline -- no more, no less.

This fork's stated policy (see docs/DIVERGENCE.md and the 2026-09-05 entry in
docs/DECISIONS.md) is: track upstream directly, accept divergence as the expected
outcome, and write every divergence down clearly enough that a future sync does not
need to re-derive the judgment call. A registry nobody checks drifts the moment
someone edits an upstream-owned file without adding a row, or deletes a row without
reverting the edit; this script is the machine check that keeps the two in sync.

It compares two sets:

- Every upstream-owned file (present in the repo at the reviewed baseline commit,
  `reviewed_through` in `tools/upstream_baseline.json`) that is modified or deleted
  between that commit and the current working tree (`git diff --name-status
  <base>`, which folds in both committed and uncommitted changes).
- Every file path registered in `docs/DIVERGENCE.md`'s table.

A file this fork only *adds* (never existed upstream) is not a divergence and is not
expected to be registered -- there is no upstream version to diverge from.

`README.en.md` is a special case: it holds upstream's original README.md content
(moved there so this fork's own README.md could be rewritten in Traditional Chinese),
but git cannot discover that by rename detection. Rename detection (`git diff -M`)
only pairs a *deleted* path with an *added* one; README.md is not deleted here, it is
modified in place with unrelated new content, so it is never eligible to be paired
with README.en.md no matter how similarity detection is tuned. This script therefore
hardcodes the association instead (see `RENAME_ALIASES` below) rather than attempting
content-similarity rename detection that git's own plumbing cannot perform here.

Git history has to actually contain the baseline commit for any of this to work. A
shallow clone (the default for many CI checkouts) or a machine that has never fetched
that commit cannot answer "what changed since then", so this degrades gracefully: it
prints a warning and exits 0 rather than failing a check that has no way to succeed.

    python tools/check_divergence.py [--json] [--repo-dir PATH] [--divergence-doc PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tools" / "upstream_baseline.json"
DIVERGENCE_DOC_PATH = REPO_ROOT / "docs" / "DIVERGENCE.md"

# README.en.md carries upstream's original README.md verbatim (plus one added language
# line); see the module docstring for why git's rename detection cannot discover this
# pairing on its own. Mapping: added path -> the upstream-owned path it stands in for.
RENAME_ALIASES = {"README.en.md": "README.md"}

_TABLE_ROW_RE = re.compile(r"^\|\s*`([^`]+)`")


class DivergenceCheckError(RuntimeError):
    """Raised when the baseline or the divergence document cannot be read."""


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    if not path.is_file():
        raise DivergenceCheckError(f"missing baseline file: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DivergenceCheckError(f"invalid baseline file: {path}: {exc}") from exc
    reviewed_through = baseline.get("reviewed_through")
    if not reviewed_through or len(reviewed_through) != 40:
        raise DivergenceCheckError(f"{path} is missing a full 40-character reviewed_through")
    return baseline


def run_git(args: list[str], repo_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def base_commit_available(base_sha: str, repo_dir: Path) -> bool:
    """Is the base commit object present in this local repository?

    A shallow clone (common in CI) or a fresh checkout that never fetched the
    fork point will not have it; there is no way to answer "what changed since
    then" without it, so callers must treat a False result as "skip, do not fail".
    """
    result = run_git(["cat-file", "-e", f"{base_sha}^{{commit}}"], repo_dir)
    return result.returncode == 0


def owned_files_at_base(base_sha: str, repo_dir: Path) -> set[str]:
    """Every path that existed in the repo at the reviewed baseline commit.

    A file outside this set was added by this fork; it has no upstream version to
    diverge from, so a later change to it is not a divergence.
    """
    result = run_git(["ls-tree", "-r", "--name-only", base_sha], repo_dir)
    if result.returncode != 0:
        raise DivergenceCheckError(f"git ls-tree failed: {result.stderr.strip()}")
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def changed_since_base(base_sha: str, repo_dir: Path) -> list[tuple[str, str]]:
    """`(status, path)` pairs for every difference between the base commit and now.

    `git diff <commit>` (one ref, no second one) compares the base commit against
    the working tree -- index and unstaged changes both -- so an uncommitted edit
    is caught here too, not only a committed one. Renames are intentionally not
    requested (`-M`): see the module docstring for why README.en.md could not be
    discovered that way regardless, and no other renames are expected in this repo.
    """
    result = run_git(["diff", "--name-status", base_sha, "--"], repo_dir)
    if result.returncode != 0:
        raise DivergenceCheckError(f"git diff failed: {result.stderr.strip()}")
    pairs = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        status, path = parts[0][0], parts[-1]
        pairs.append((status, path))
    return pairs


def compute_divergent_files(pairs: list[tuple[str, str]], owned: set[str]) -> set[str]:
    """Which of `pairs` count as a fork divergence from an upstream-owned file.

    Modified or deleted upstream-owned paths always count. An *added* path counts
    only through `RENAME_ALIASES`, when it stands in for an upstream-owned path that
    was itself changed (README.en.md for README.md) -- an ordinary new file this
    fork introduced is not a divergence, because there is no upstream file it
    diverges from.
    """
    divergent: set[str] = set()
    for status, path in pairs:
        modified_or_deleted_upstream_file = status in ("M", "D") and path in owned
        aliased_addition_for_a_changed_upstream_file = (
            status == "A" and path in RENAME_ALIASES and RENAME_ALIASES[path] in owned
        )
        if modified_or_deleted_upstream_file or aliased_addition_for_a_changed_upstream_file:
            divergent.add(path)
    return divergent


REGISTRY_COLUMNS = 5  # 上游檔案 | 上游原狀 | 本 fork 狀態 | 為什麼分岔 | 跟進上游時怎麼處理
# GFM's rule is "a backslash escapes the punctuation character after it", not "a pipe
# preceded by a backslash is literal". The two differ on a run of backslashes: in `b\\|`
# the first backslash escapes the second, so the pipe is a real cell separator. A
# `(?<!\\)\|` lookbehind gets that backwards in both directions -- it reads a real
# separator as literal (a malformed row passing as fine) and, with `\|`, a literal pipe
# as a separator. So resolve every escape pair away first, then count what is left.
_ESCAPE_PAIR_RE = re.compile(r"\\.", re.DOTALL)


def _column_count(row: str) -> int:
    """Cells in a GFM table row, counting the way GFM counts them."""
    without_escapes = _ESCAPE_PAIR_RE.sub("", row.strip())
    # The leading pipe is required; the trailing one is optional in GFM.
    if without_escapes.startswith("|"):
        without_escapes = without_escapes[1:]
    if without_escapes.endswith("|"):
        without_escapes = without_escapes[:-1]
    return len(without_escapes.split("|"))


def malformed_rows(text: str) -> list[tuple[int, int, str]]:
    """Registry rows whose cell count is not `REGISTRY_COLUMNS`, as `(line, cols, path)`.

    `parse_registered_paths` only ever reads the FIRST cell, so for a long time a row
    could be missing a column entirely and still register its path and pass the check.
    That is not cosmetic: the last column ("跟進上游時怎麼處理") is what the header calls
    this table's whole point, and in a four-cell row every later cell shifts left, so the
    executable criterion renders under "為什麼分岔" and the real last column comes out
    empty. 16 rows were in that state, plus 2 more split by an unescaped `|` in a type
    union. A registry the checker only half-parses is a registry that can be half-wrong.
    """
    bad: list[tuple[int, int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        match = _TABLE_ROW_RE.match(stripped)
        if not match:
            continue
        columns = _column_count(stripped)
        if columns != REGISTRY_COLUMNS:
            bad.append((number, columns, match.group(1).strip()))
    return bad


def parse_registered_paths(text: str) -> set[str]:
    """Every backtick-quoted path in the first column of `docs/DIVERGENCE.md`'s table.

    The header row (`| 上游檔案 | ...`) and the separator row (`| --- | ... |`) do not
    start their first cell with a backtick, so both are skipped without special-casing.
    """
    paths: set[str] = set()
    for line in text.splitlines():
        match = _TABLE_ROW_RE.match(line.strip())
        if match:
            paths.add(match.group(1).strip())
    return paths


def compare(divergent: set[str], registered: set[str]) -> tuple[set[str], set[str]]:
    """`(changed_but_not_registered, registered_but_not_changed)`."""
    return divergent - registered, registered - divergent


def render_report(
    base_sha: str,
    divergent: set[str],
    registered: set[str],
    changed_not_registered: set[str],
    registered_not_changed: set[str],
) -> str:
    lines = [
        f"Base commit: {base_sha[:7]}",
        f"{len(divergent)} upstream file(s) diverge from the baseline; "
        f"{len(registered)} registered in docs/DIVERGENCE.md.",
    ]
    if changed_not_registered:
        lines.append("")
        lines.append("Changed but NOT registered in docs/DIVERGENCE.md:")
        lines.extend(f"  - {path}" for path in sorted(changed_not_registered))
    if registered_not_changed:
        lines.append("")
        lines.append("Registered in docs/DIVERGENCE.md but NOT actually changed:")
        lines.extend(f"  - {path}" for path in sorted(registered_not_changed))
    if not changed_not_registered and not registered_not_changed:
        lines.append("OK: the divergence registry matches the actual changes.")
    return "\n".join(lines)


def render_json(
    base_sha: str,
    divergent: set[str],
    registered: set[str],
    changed_not_registered: set[str],
    registered_not_changed: set[str],
    warning: str | None = None,
    malformed: list[tuple[int, int, str]] | None = None,
) -> str:
    payload = {
        "base_commit": base_sha,
        "changed_upstream_files": sorted(divergent),
        "registered_files": sorted(registered),
        "changed_but_not_registered": sorted(changed_not_registered),
        "registered_but_not_changed": sorted(registered_not_changed),
        # Without this the JSON mirror cannot express a malformed-row failure at all: all
        # four lists come back empty and `warning` null, which reads as a clean bill of
        # health beside a non-zero exit code. That is the defect this check exists to
        # remove, so the mirror has to carry it too.
        "malformed_rows": [
            {"line": number, "columns": columns, "path": path}
            for number, columns, path in (malformed or [])
        ],
        "warning": warning,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", type=Path, default=REPO_ROOT)
    parser.add_argument("--divergence-doc", type=Path, default=DIVERGENCE_DOC_PATH)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON report instead of plain text.",
    )
    args = parser.parse_args()

    try:
        baseline = load_baseline()
    except DivergenceCheckError as exc:
        print(f"ERROR: {exc}")
        return 2
    base_sha = baseline["reviewed_through"]

    if not base_commit_available(base_sha, args.repo_dir):
        warning = (
            f"WARNING: base commit {base_sha[:7]} is not available in this local "
            "repository (shallow clone, or history never fetched). Cannot compute "
            "divergence against it; skipping the check rather than failing one that "
            "has no way to succeed. Run `git fetch --unshallow` (or fetch the full "
            "history) to get a real answer."
        )
        print(warning)
        if args.json:
            print(render_json(base_sha, set(), set(), set(), set(), warning=warning))
        return 0

    try:
        owned = owned_files_at_base(base_sha, args.repo_dir)
        pairs = changed_since_base(base_sha, args.repo_dir)
        if not args.divergence_doc.is_file():
            raise DivergenceCheckError(f"missing divergence document: {args.divergence_doc}")
        doc_text = args.divergence_doc.read_text(encoding="utf-8")
    except DivergenceCheckError as exc:
        print(f"ERROR: {exc}")
        return 2

    divergent = compute_divergent_files(pairs, owned)
    registered = parse_registered_paths(doc_text)
    changed_not_registered, registered_not_changed = compare(divergent, registered)
    malformed = malformed_rows(doc_text)

    if args.json:
        # Everything goes inside the document: `--json` promises JSON on stdout, so the
        # human-readable block below must not be appended after it.
        print(
            render_json(
                base_sha,
                divergent,
                registered,
                changed_not_registered,
                registered_not_changed,
                malformed=malformed,
            )
        )
    else:
        print(
            render_report(
                base_sha, divergent, registered, changed_not_registered, registered_not_changed
            )
        )
        if malformed:
            print("")
            print(
                f"Rows with the wrong number of columns (need {REGISTRY_COLUMNS}: "
                "上游檔案 | 上游原狀 | 本 fork 狀態 | 為什麼分岔 | 跟進上游時怎麼處理):"
            )
            for number, columns, path in malformed:
                print(f"  - line {number}: {columns} column(s) -> {path}")
            print(
                "A `|` inside a cell (a type union, a bitwise or) must be written `\\|`, "
                "and the row must end with a `|`."
            )

    return 1 if (changed_not_registered or registered_not_changed or malformed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
