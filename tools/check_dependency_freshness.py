"""Compare declared dependency floors against their current upstream releases.

This fork's *own* declared dependencies are the dev tools in `requirements-dev.txt`
(pytest, ruff, and the Windows-only `tzdata` line this maintenance line added directly to
that file -- see docs/DIVERGENCE.md for why it lives there now instead of a fork-only
sibling file; everything else that file pulls in comes from `-r requirements.txt`, which
upstream owns and pins exactly, not with a floor -- see the exclusion note below), and the
pinned GitHub Actions used by `.github/workflows/*.yml`. Dependabot proposes upgrades one
pull request at a time, which answers "is there a newer release?" but never "how far
behind is what we declare, across every declaration in the repo?". This reads both
sources, asks PyPI (for the Python tools) and the GitHub Releases API (for the Actions)
for the current release, and writes a Markdown report.

`examples/package-lock.json` (the npm workspace lockfile for the eight example web apps)
is deliberately excluded: it is upstream product content with its own release cadence,
tracked separately by the `npm` Dependabot ecosystem in `.github/dependabot.yml` (limited
to security updates only, same as `pip`), not by this script. Likewise `requirements.txt`
itself is excluded: every entry there is an exact `==` pin upstream tested a release
against, not a floor this fork declares -- there is nothing to compare against "the
precision the declaration commits to" the way `>=` floors below are.

It compares declarations only. Nothing here inspects the installed environment and
nothing here edits a requirements file or a workflow: a newer release is a prompt to read
the changelog and run the suite, not a merge.

    python tools/check_dependency_freshness.py --output report.md --github-output
"""

from __future__ import annotations

import argparse
import json
import os
import re
import urllib.parse
import urllib.request
from collections.abc import Callable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "commerce-agents-dependency-freshness"

# The declaration files this fork checks. `requirements-dev.txt` is upstream's own file,
# but this fork now edits it directly (ruff kept current, `tzdata` added for Windows; see
# docs/DIVERGENCE.md) rather than keeping a separate Windows-only sibling. requirements.txt
# is not in this list: see the module docstring for why exact upstream pins are excluded.
REQUIREMENT_FILES = ("requirements-dev.txt",)

_REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^\]]+\])?\s*(.*)$")
_MINIMUM_RE = re.compile(r"(>=|>|==|~=)\s*([0-9][0-9A-Za-z.!+_-]*)")
_RELEASE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*")
# `owner/repo`, optionally followed by a sub-path: `github/codeql-action/init` is one
# action published from a directory of `github/codeql-action`. An `owner/repo`-only
# pattern silently matched nothing on those lines, so codeql.yml's two pins never
# reached the report at all -- a check that is blind to a declaration is worse than one
# that reports it stale.
_USES_RE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*([\w.\-]+/[\w.\-]+(?:/[\w.\-]+)*)@([0-9a-fA-F]{40}|\S+)"
    r"(?:\s*#\s*(.*))?\s*$",
    re.MULTILINE,
)
HOLD_MARKER = "freshness-hold:"
DEFERRALS_PATH = REPO_ROOT / ".github" / "dependency-deferrals.json"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


class DependencyCheckError(RuntimeError):
    """Raised when a requirements file or the workflows directory cannot be read."""


def release_key(version: str) -> tuple[int, ...] | None:
    """Return the numeric release segment of a version, or None if unparsable.

    Pre-release and local suffixes are dropped, so 7.0.0rc1 and 7.0.0 rank the
    same. That is precise enough to answer "has the declared floor aged?"
    without adding a PEP 440 or semver parser to a repo whose declared
    dependencies are two dev tools and a handful of pinned GitHub Actions.
    """
    match = _RELEASE_RE.match(version.strip().lstrip("vV"))
    if not match:
        return None
    return tuple(int(part) for part in match.group(0).split("."))


def is_newer_version(latest: str, declared: str) -> bool:
    """Is `latest` newer than `declared` at the precision `declared` states?

    A floor of `Pillow>=10` says nothing about the minor, so reporting 10.4.0
    against it would be a standing false alarm -- and a monthly report that
    cries wolf gets ignored. The comparison therefore happens at the depth the
    declaration commits to: `>=10` on the major alone, `>=1.26` on major.minor,
    and `v7.0.1` on all three segments for a pinned Action.
    """
    latest_key = release_key(latest)
    declared_key = release_key(declared)
    if latest_key is None or declared_key is None:
        return False
    depth = len(declared_key)
    padded = latest_key + (0,) * (depth - len(latest_key))
    return padded[:depth] > declared_key


def load_deferrals(path: Path = DEFERRALS_PATH) -> dict[str, tuple[str, str]]:
    """Read reviewed-but-not-now decisions: package -> (reviewed release, reason).

    A hold says "this floor is the floor we want" and never expires. A deferral
    says "we looked, and not this month", which is a different claim and must
    not outlive the release it was made against. `deferredLatest` is what makes
    it expire by itself: once the upstream source moves past that release the
    report asks again, so a deferral cannot quietly become a permanently
    silenced check. An entry without it is ignored for exactly that reason.
    """
    try:
        entries = json.loads(path.read_text(encoding="utf-8")).get("deferrals", {})
    except (OSError, ValueError):
        return {}
    deferrals: dict[str, tuple[str, str]] = {}
    for name, entry in (entries or {}).items():
        if not isinstance(entry, dict):
            continue
        latest = str(entry.get("deferredLatest", "")).strip()
        reason = str(entry.get("reason", "")).strip()
        if latest and reason:
            deferrals[name.lower()] = (latest, reason)
    return deferrals


def parse_requirements(text: str, source: str) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    for raw_line in text.splitlines():
        comment = raw_line.split("#", 1)[1].strip() if "#" in raw_line else ""
        line = raw_line.split("#", 1)[0].strip()
        # A "-r other.txt" include is followed separately; expanding it here
        # would list the same package twice (and, for this fork, would pull in
        # upstream's exact pins -- see the module docstring).
        if not line or line.startswith("-"):
            continue
        hold = comment[len(HOLD_MARKER) :].strip() if comment.startswith(HOLD_MARKER) else ""
        head = line.split(";", 1)[0].strip()
        match = _REQUIREMENT_RE.match(head)
        if not match:
            continue
        name, specifiers = match.groups()
        minimum = _MINIMUM_RE.search(specifiers)
        packages.append(
            {
                "name": name,
                "minimum": minimum.group(2) if minimum else "",
                "requirement": line,
                "source": source,
                "hold": hold,
                "kind": "pypi",
            }
        )
    return packages


def parse_workflow_actions(text: str, source: str) -> list[dict[str, str]]:
    """Every `uses: owner/repo@<ref> # vX.Y.Z` declaration in a workflow file."""
    packages: list[dict[str, str]] = []
    for match in _USES_RE.finditer(text):
        action, ref, comment = match.group(1), match.group(2), (match.group(3) or "").strip()
        hold = comment[len(HOLD_MARKER) :].strip() if comment.startswith(HOLD_MARKER) else ""
        # A pinned SHA carries its declared version in the trailing comment
        # (`# v7.0.1`); an unpinned floating tag (`@v6`) carries it in the ref
        # itself. Either is a real declaration worth tracking -- only a hold
        # or a comment/ref with no parseable number leaves `minimum` empty.
        version_source = comment if comment else ref
        version_match = _RELEASE_RE.match(version_source.lstrip("vV")) if not hold else None
        minimum = version_match.group(0) if version_match else ""
        packages.append(
            {
                "name": action,
                "minimum": minimum,
                "requirement": f"{action}@{comment or ref[:12]}",
                "source": source,
                "hold": hold,
                "kind": "github-action",
            }
        )
    return packages


def load_direct_dependencies(root: Path = REPO_ROOT) -> list[dict[str, str]]:
    packages: list[dict[str, str]] = []
    seen: set[str] = set()
    for name in REQUIREMENT_FILES:
        path = root / name
        if not path.is_file():
            raise DependencyCheckError(f"missing requirements file: {name}")
        for package in parse_requirements(path.read_text(encoding="utf-8"), name):
            key = package["name"].lower().replace("_", "-")
            if key in seen:
                continue
            seen.add(key)
            packages.append(package)
    return packages


def load_workflow_actions(root: Path = REPO_ROOT) -> list[dict[str, str]]:
    """Every pinned Action across `.github/workflows/*.yml`, deduplicated.

    The same action pinned to the same declared version in two files is one
    row with both sources listed; pinned to two *different* declared versions
    it is two rows, because that split is itself drift worth seeing.
    """
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        raise DependencyCheckError("missing .github/workflows directory")
    merged: dict[tuple[str, str], dict[str, str]] = {}
    for path in sorted(workflows_dir.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        for package in parse_workflow_actions(text, path.name):
            key = (package["name"].lower(), package["minimum"] or package["requirement"])
            existing = merged.get(key)
            if existing is None:
                merged[key] = package
                continue
            sources = existing["source"].split(", ")
            if path.name not in sources:
                sources.append(path.name)
                existing["source"] = ", ".join(sources)
    return sorted(merged.values(), key=lambda p: (p["name"], p["minimum"]))


def fetch_pypi_version(package_name: str, timeout: float = 10.0) -> str | None:
    quoted_name = urllib.parse.quote(package_name, safe="")
    request = urllib.request.Request(
        f"https://pypi.org/pypi/{quoted_name}/json",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    version = payload.get("info", {}).get("version")
    return str(version) if version else None


def action_repository(action_name: str) -> str:
    """The `owner/repo` that publishes an action, dropping any sub-path.

    `github/codeql-action/init` and `github/codeql-action/analyze` ship from directories
    of one repository and share its releases; asking the API for `repos/github/
    codeql-action/init/releases/latest` 404s, which the caller would read as "could not
    check" rather than as the parsing bug it is.
    """
    owner, _, rest = action_name.partition("/")
    return f"{owner}/{rest.split('/', 1)[0]}" if rest else action_name


def fetch_github_release(action_name: str, timeout: float = 10.0) -> str | None:
    """The latest release tag for an action, or None when it cannot be read.

    The token matters: unauthenticated api.github.com allows 60 requests an hour per
    address, and past it every lookup here returns 403. That reads as "latest unknown"
    on every Action row at once -- a whole half of the report going quiet without
    saying why -- so `GITHUB_TOKEN` (or `GH_TOKEN`) is sent when the environment has
    one. Absent a token this still works, just against the anonymous limit.
    """
    quoted_name = urllib.parse.quote(action_repository(action_name), safe="/")
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    token = (os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"https://api.github.com/repos/{quoted_name}/releases/latest",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        payload = {}
    tag = str(payload.get("tag_name") or "")
    if release_key(tag) is not None:
        return tag.lstrip("vV")
    # Some repositories tag their latest *release* with something that is not the
    # action's version: `github/codeql-action` names it `codeql-bundle-v2.27.0`, the
    # CodeQL bundle, while the action itself moves on `v4.37.9` tags. Comparing a
    # `v4.37.9` pin against a bundle tag yields an unparsable "latest" that scores as
    # not-outdated -- a false green. Fall back to the version tags themselves.
    return _fetch_latest_version_tag(quoted_name, headers, timeout)


def _fetch_latest_version_tag(
    quoted_name: str, headers: dict[str, str], timeout: float
) -> str | None:
    """The highest `vX.Y.Z` tag on a repository, ignoring tags that are not versions."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{quoted_name}/tags?per_page=100", headers=headers
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            tags = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(tags, list):
        return None
    best: tuple[tuple[int, ...], str] | None = None
    for entry in tags:
        name = str((entry or {}).get("name") or "") if isinstance(entry, dict) else ""
        key = release_key(name)
        if key is None or not name.lstrip("vV")[:1].isdigit():
            continue
        if best is None or key > best[0]:
            best = (key, name.lstrip("vV"))
    return best[1] if best else None


def collect_status(
    packages: list[dict[str, str]],
    fetch: Callable[[str], str | None],
    deferrals: dict[str, tuple[str, str]] | None = None,
) -> list[dict[str, object]]:
    deferrals = deferrals if deferrals is not None else load_deferrals()
    rows: list[dict[str, object]] = []
    for package in packages:
        minimum = package["minimum"]
        latest = fetch(package["name"])
        reviewed, reason = deferrals.get(package["name"].lower(), ("", ""))
        deferred = bool(reviewed and latest and not is_newer_version(latest, reviewed))
        rows.append(
            {
                **package,
                "latest": latest or "unknown",
                "outdated": bool(minimum and latest and is_newer_version(latest, minimum)),
                "check_failed": not minimum or latest is None,
                "deferred_reason": reason if deferred else "",
            }
        )
    return rows


def needs_review(row: dict[str, object]) -> bool:
    """An aged floor still counts unless a hold or a live deferral covers it."""
    return bool(row["outdated"]) and not row.get("hold") and not row.get("deferred_reason")


def _render_table(rows: list[dict[str, object]]) -> list[str]:
    lines = [
        "| Package | Declared in | Requirement | Latest | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        if row["check_failed"]:
            status = "CHECK FAILED"
        elif row.get("hold") and row["outdated"]:
            status = f"HELD: {row['hold']}"
        elif row.get("deferred_reason") and row["outdated"]:
            status = f"DEFERRED at {row['latest']}: {row['deferred_reason']}"
        elif row["outdated"]:
            status = "REVIEW UPDATE"
        else:
            status = "OK"
        lines.append(
            f"| `{row['name']}` | `{row['source']}` | `{row['requirement']}` | "
            f"`{row['latest']}` | {status} |"
        )
    if not rows:
        lines.append("| - | - | - | - | CHECK FAILED |")
    return lines


def render_markdown(
    rows_python: list[dict[str, object]],
    rows_actions: list[dict[str, object]] | None = None,
    error: str | None = None,
) -> str:
    rows_actions = rows_actions if rows_actions is not None else []
    lines = ["# Dependency freshness report", ""]
    if error:
        lines.extend(["## Check failed", "", f"```text\n{error}\n```", ""])
        return "\n".join(lines)

    lines.extend(["## Python dev dependencies (PyPI)", ""])
    lines.extend(_render_table(rows_python))
    lines.append("")
    lines.extend(["## GitHub Actions (pinned in .github/workflows/)", ""])
    lines.extend(_render_table(rows_actions))
    lines.extend(
        [
            "",
            "Declared ranges are compared against PyPI (Python dev dependencies) and",
            "the GitHub Releases API (pinned Actions). The installed environment is",
            "not inspected and no file is edited by this check. `requirements.txt` and",
            "`examples/package-lock.json` are out of scope here (see the module",
            "docstring); they are tracked by the `pip` and `npm` Dependabot ecosystems,",
            "with `tools/check_pin_bounds.py` guarding the pins against what the",
            "`pyproject.toml` files declare.",
            "",
            "## Review policy",
            "",
            "0. The default answer to a red line is to raise the declaration. This fork",
            "   tracks upstream releases directly and does not hold a version back to",
            "   keep an upstream-owned file at zero diff; if raising it means editing an",
            "   upstream-owned file, add the row to `docs/DIVERGENCE.md` in the same",
            "   change. See the 2026-09-05 policy decisions in `docs/DECISIONS.md`.",
            "1. Read the release notes, and check the supported Python versions.",
            "2. Run `python -m pytest` and `ruff check` before raising anything, and",
            "   `tools/check_pin_bounds.py` if the new version could leave a range some",
            "   `pyproject.toml` declares.",
            "3. Repin a GitHub Action by its new commit SHA with a `# vX.Y.Z` comment; do",
            "   not switch a pinned SHA back to a floating tag.",
            "4. Only when raising it would genuinely break something now, record why and",
            "   leave the reason behind: `# freshness-hold: <why>` on the declaring line",
            "   for a standing policy, or an entry in",
            '   `.github/dependency-deferrals.json` with `deferredLatest` for "reviewed,',
            '   not now" -- that one expires by itself once the upstream source moves',
            "   past the release it was reviewed against. Neither is a place to park",
            '   "waiting for upstream to move first".',
            "",
        ]
    )
    return "\n".join(lines)


def write_github_output(
    rows_python: list[dict[str, object]],
    rows_actions: list[dict[str, object]],
    report_path: Path,
) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    rows = rows_python + rows_actions
    outdated = any(needs_review(row) for row in rows)
    check_failed = not rows or any(bool(row["check_failed"]) for row in rows)
    with open(output_path, "a", encoding="utf-8") as output:
        output.write(f"outdated={'true' if outdated else 'false'}\n")
        output.write(f"check_failed={'true' if check_failed else 'false'}\n")
        output.write(f"needs_attention={'true' if outdated or check_failed else 'false'}\n")
        output.write(f"report_path={report_path.as_posix()}\n")


def render_json(
    rows_python: list[dict[str, object]],
    rows_actions: list[dict[str, object]],
    error: str | None,
) -> str:
    """A machine-readable mirror of the Markdown report.

    Every row already round-trips through ``json.dumps`` (strings and bools
    only), so this is a thin wrapper, not a second source of truth: the same
    ``rows_python`` / ``rows_actions`` feed both `render_markdown` and this.
    """
    payload = {
        "error": error,
        "python_dependencies": rows_python,
        "github_actions": rows_actions,
        "needs_review": [row["name"] for row in rows_python + rows_actions if needs_review(row)],
        "check_failed": any(bool(row["check_failed"]) for row in rows_python + rows_actions),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="dependency-freshness-report.md")
    parser.add_argument(
        "--github-output",
        action="store_true",
        help="Write status fields to GITHUB_OUTPUT",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON mirror of the report to stdout instead of Markdown "
        "(the Markdown file at --output is still written).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when a declared range has aged.",
    )
    args = parser.parse_args()

    rows_python: list[dict[str, object]] = []
    rows_actions: list[dict[str, object]] = []
    error: str | None = None
    try:
        deferrals = load_deferrals()
        rows_python = collect_status(load_direct_dependencies(), fetch_pypi_version, deferrals)
        rows_actions = collect_status(load_workflow_actions(), fetch_github_release, deferrals)
    except DependencyCheckError as exc:
        error = str(exc)

    report = render_markdown(rows_python, rows_actions, error)
    output_path = Path(args.output)
    output_path.write_text(report, encoding="utf-8")
    print(render_json(rows_python, rows_actions, error) if args.json else report)

    if args.github_output:
        write_github_output(rows_python, rows_actions, output_path)
    if error:
        return 2
    if args.strict and any(
        needs_review(row) or bool(row["check_failed"]) for row in rows_python + rows_actions
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
