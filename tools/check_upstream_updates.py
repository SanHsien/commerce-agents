"""Report upstream commits, pull requests, and issues this fork has not reviewed.

Commits are only one of the places upstream work shows up. A pull request can sit
open for months with a fix in it, and an issue can describe a defect this fork also
has -- neither reaches the commit log until somebody merges it. Each axis therefore
carries its own watermark, and the report only lists what is above it.

Tickets are queried with ``--state all`` on purpose: an item opened and closed
between two scheduled runs is still an item this fork never triaged, and a pull
request closed without merging never arrives on the commit axis at all.

`anthropics/commerce-agents` has GitHub Issues disabled, so the issue axis always
reports "not checked" here rather than "no new items" -- the report distinguishes the
two on purpose (see ``render_ticket_section``); do not read a "not checked" issue
section as a clean bill of health.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "tools" / "upstream_baseline.json"
UPSTREAM_REF_PREFIX = "refs/upstream-check"
DEFAULT_DECISION_LOG = "docs/DECISIONS.md"


class UpstreamCheckError(RuntimeError):
    """Raised when the baseline or upstream Git history cannot be inspected."""


def load_baseline(path: Path = BASELINE_PATH) -> dict:
    if not path.is_file():
        raise UpstreamCheckError(f"missing baseline file: {path}")
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UpstreamCheckError(f"invalid baseline file: {path}: {exc}") from exc
    required = {"repo", "branch", "reviewed_through", "reviewed_date"}
    missing = sorted(required - baseline.keys())
    if missing:
        raise UpstreamCheckError(f"baseline missing fields: {', '.join(missing)}")
    if len(baseline["reviewed_through"]) != 40:
        raise UpstreamCheckError("reviewed_through must be a full 40-character SHA")
    return baseline


def run_git(args: list[str], repo_dir: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise UpstreamCheckError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def fetch_upstream(baseline: dict, repo_dir: Path) -> str:
    branch = baseline["branch"]
    ref = f"{UPSTREAM_REF_PREFIX}/{branch}"
    run_git(
        [
            "fetch",
            "--quiet",
            baseline["repo"],
            f"+refs/heads/{branch}:{ref}",
        ],
        repo_dir,
    )
    return ref


def collect_new_commits(baseline: dict, repo_dir: Path, ref: str) -> list[dict]:
    reviewed = baseline["reviewed_through"]
    raw = run_git(
        [
            "log",
            "--reverse",
            "--date=short",
            "--format=%H%x1f%ad%x1f%s",
            f"{reviewed}..{ref}",
        ],
        repo_dir,
    )
    commits = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        sha, date, subject = line.split("\x1f", 2)
        files = [
            item
            for item in run_git(["show", "--name-only", "--format=", sha], repo_dir).splitlines()
            if item.strip()
        ]
        commits.append(
            {
                "sha": sha,
                "short": sha[:7],
                "date": date,
                "subject": subject,
                "files": files,
            }
        )
    return commits


def upstream_slug(repo_url: str) -> str | None:
    """`https://github.com/owner/name.git` -> `owner/name`, or None if not GitHub."""
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?$", repo_url)
    return f"{match['owner']}/{match['name']}" if match else None


DISABLED = "disabled"  # sentinel: the ticket type is turned off on the upstream repo itself
UNDECLARED = "undeclared"  # sentinel: the baseline itself never declared a branch list


def collect_new_branches(baseline: dict, repo_dir: Path) -> list[str] | None | str:
    """Upstream branch names absent from the baseline's `branches` list.

    This axis exists because the commit axis only ever looks at `baseline["branch"]`
    (`main`). A fork that reads only that ref cannot see a branch upstream pushed
    beside it -- a release branch, a security backport, a Dependabot branch carrying
    a fix this fork also needs. The baseline recorded a `branches` list from the
    start and nothing compared it to reality, so the list aged into decoration: a
    check that cannot fail is not a check.

    Returns ``None`` when `git ls-remote` could not answer (network, a repo URL git
    will not take), and the ``UNDECLARED`` sentinel when the baseline carries no
    usable `branches` list. Both fail closed: unlike ``DISABLED`` on the ticket
    axes, neither is a standing fact about upstream that should be tolerated
    forever -- one is a broken check and the other is a baseline waiting to be
    filled in, and both are the maintainer's to fix.
    """
    declared = baseline.get("branches")
    if not isinstance(declared, list) or not all(isinstance(name, str) for name in declared):
        return UNDECLARED
    result = subprocess.run(
        ["git", "ls-remote", "--heads", str(baseline["repo"])],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        # Branch names are written by strangers, same argument as the ticket axis.
        errors="replace",
    )
    if result.returncode != 0:
        return None
    seen: set[str] = set()
    for line in result.stdout.splitlines():
        _, _, ref = line.partition("\t")
        if ref.startswith("refs/heads/"):
            seen.add(ref[len("refs/heads/") :].strip())
    if not seen:
        # A public repo always has at least one head; an empty parse means the
        # output shape was not what this reader assumed, not that upstream has
        # no branches. Do not report that as "nothing new".
        return None
    return sorted(seen - set(declared))


def collect_new_tickets(baseline: dict, kind: str) -> list[dict] | None | str:
    """All PRs or issues numbered above the watermark, closed ones included.

    Returns ``None`` -- not an empty list -- when ``gh`` cannot answer for a reason
    that might be transient (missing auth, network, an unparsable baseline repo
    URL), and the report says so. "Not checked" and "nothing to review" look
    identical in a green report, and only one of them is true; conflating them is
    how a fork stops noticing upstream without anybody deciding to.

    Returns the sentinel ``DISABLED`` -- a third state, not ``None`` -- when the
    upstream repository has turned the ticket type off entirely (`gh` reports
    "repository has disabled issues"). `anthropics/commerce-agents` does exactly
    this for issues. That is a permanent, structural fact about the upstream repo,
    not a transient check failure: treating it as an error (as a bare ``None``
    would) would make the scheduled workflow fail on every single run forever,
    which trains people to ignore red instead of reading it. ``DISABLED`` is
    still reported as "not checked" in the Markdown (never as "no new items"),
    it just does not fail the check on its own.
    """
    slug = upstream_slug(str(baseline["repo"]))
    if not slug:
        return None
    watermark = int(baseline.get(f"reviewed_{kind}_through", 0) or 0)
    result = subprocess.run(
        [
            "gh",
            kind,
            "list",
            "--repo",
            slug,
            "--state",
            "all",
            "--limit",
            "1000",
            "--json",
            "number,title",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        # `errors` is not optional here. Ticket titles are written by strangers
        # and the console this runs on is not always UTF-8; without it a single
        # undecodable byte raises UnicodeDecodeError and the whole upstream
        # check dies instead of reporting the tickets it did read.
        errors="replace",
    )
    if result.returncode != 0:
        if (
            "disabled issues" in result.stderr.lower()
            or "disabled pull requests" in result.stderr.lower()
        ):
            return DISABLED
        return None
    try:
        items = json.loads(result.stdout)
    except ValueError:
        return None
    return sorted(
        (item for item in items if item["number"] > watermark),
        key=lambda item: item["number"],
    )


def render_ticket_section(
    title: str,
    watermark: int,
    tickets: list[dict] | None | str,
    kind: str,
    decision_log: str,
) -> list[str]:
    lines = [f"## {title}", "", f"Triaged through `#{watermark}`.", ""]
    if tickets is DISABLED:
        lines.extend(
            [
                "Not checked: the upstream repository has this ticket type disabled",
                "(`gh` reports it as such). This is a standing fact about the upstream",
                'repository, not a failed check, and is reported as "not checked"',
                'rather than as "no new items" -- the difference matters.',
                "",
            ]
        )
        return lines
    if tickets is None:
        lines.extend(
            [
                "Not checked: `gh` was unavailable, unauthenticated, or the baseline",
                "does not name a GitHub repository. Reported as such rather than as",
                '"nothing to review" -- the difference matters.',
                "",
            ]
        )
        return lines
    if not tickets:
        lines.extend(["No new items above that number.", ""])
        return lines
    lines.extend(
        [
            f"{len(tickets)} new item(s) to triage.",
            "",
            "| Item | Title |",
            "| --- | --- |",
        ]
    )
    for ticket in tickets:
        # The escape is computed outside the f-string: a backslash inside an
        # f-string expression is a SyntaxError before Python 3.12.
        item_title = ticket["title"].replace("|", "\\|")
        lines.append(f"| #{ticket['number']} | {item_title} |")
    lines.extend(
        [
            "",
            f"Record the verdict in `{decision_log}`, then raise",
            f"`reviewed_{kind}_through` so the same item is never re-triaged.",
            "",
        ]
    )
    return lines


def render_branch_section(
    declared: object, branches: list[str] | None | str, decision_log: str
) -> list[str]:
    known = ", ".join(f"`{name}`" for name in declared) if isinstance(declared, list) else "(none)"
    lines = ["## Upstream branches", "", f"Registered: {known}.", ""]
    if branches is UNDECLARED:
        lines.extend(
            [
                "Not checked: the baseline carries no `branches` list, so there is",
                "nothing to compare upstream against. Declare the branches upstream",
                "currently carries and this axis starts reporting.",
                "",
            ]
        )
        return lines
    if branches is None:
        lines.extend(
            [
                "Not checked: `git ls-remote` could not enumerate upstream branches.",
                'Reported as such rather than as "nothing to review" -- the',
                "difference matters.",
                "",
            ]
        )
        return lines
    if not branches:
        lines.extend(["No branches beyond the registered ones.", ""])
        return lines
    lines.extend([f"{len(branches)} new branch(es) to triage.", "", "| Branch |", "| --- |"])
    for name in branches:
        lines.append(f"| `{name.replace('|', chr(92) + '|')}` |")
    lines.extend(
        [
            "",
            f"Record the verdict in `{decision_log}`, then add the branch to",
            "`branches` in `tools/upstream_baseline.json` so it is never re-triaged.",
            "",
        ]
    )
    return lines


def render_markdown(
    baseline: dict,
    commits: list[dict],
    prs: list[dict] | None | str = None,
    issues: list[dict] | None | str = None,
    branches: list[str] | None | str = UNDECLARED,
    error: str | None = None,
) -> str:
    decision_log = baseline.get("decision_log", DEFAULT_DECISION_LOG)
    lines = [
        "# Upstream review report",
        "",
        f"- Upstream: `{baseline['repo']}` (`{baseline['branch']}`)",
        f"- Reviewed through: `{baseline['reviewed_through'][:7]}`",
        f"- Last review date: {baseline['reviewed_date']}",
        "",
    ]
    if error:
        lines.extend(["## Check failed", "", f"```text\n{error}\n```", ""])
        return "\n".join(lines)

    def with_tickets(body: list[str]) -> str:
        body = body + render_ticket_section(
            "Upstream pull requests",
            int(baseline.get("reviewed_pr_through", 0) or 0),
            prs,
            "pr",
            decision_log,
        )
        body += render_ticket_section(
            "Upstream issues",
            int(baseline.get("reviewed_issue_through", 0) or 0),
            issues,
            "issue",
            decision_log,
        )
        body += render_branch_section(baseline.get("branches"), branches, decision_log)
        return "\n".join(body)

    if not commits:
        lines.extend(["## Commits", "", "No new upstream commits. Nothing to review.", ""])
        return with_tickets(lines)

    lines.extend(
        [
            "## Commits",
            "",
            f"{len(commits)} upstream commit(s) require review.",
            "",
            "| Commit | Date | Subject | Files |",
            "| --- | --- | --- | --- |",
        ]
    )
    for commit in commits:
        subject = commit["subject"].replace("|", "\\|")
        files = "<br>".join(item.replace("|", "\\|") for item in commit["files"][:8])
        if len(commit["files"]) > 8:
            files += f"<br>… +{len(commit['files']) - 8} more"
        lines.append(
            f"| `{commit['short']}` | {commit['date']} | {subject} | {files or '(none)'} |"
        )
    lines.extend(
        [
            "",
            f"Review each commit, record adopt/skip decisions in `{decision_log}`, ",
            "then advance `tools/upstream_baseline.json` only after verification.",
            "",
        ]
    )
    return with_tickets(lines)


def render_json(
    baseline: dict,
    commits: list[dict],
    prs: list[dict] | None | str,
    issues: list[dict] | None | str,
    branches: list[str] | None | str = UNDECLARED,
    error: str | None = None,
) -> str:
    """A machine-readable mirror of the Markdown report.

    ``prs`` / ``issues`` are one of a list, ``None`` (genuinely unavailable), or
    the ``DISABLED`` sentinel (a plain string, already JSON-safe) -- all three
    round-trip through ``json.dumps`` without translation.
    """
    payload = {
        "error": error,
        "repo": baseline.get("repo"),
        "branch": baseline.get("branch"),
        "registered_branches": baseline.get("branches"),
        "new_branches": branches,
        "reviewed_through": baseline.get("reviewed_through"),
        "reviewed_date": baseline.get("reviewed_date"),
        "commits": commits,
        "pull_requests": prs,
        "issues": issues,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="upstream-review-report.md")
    parser.add_argument("--repo-dir", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON mirror of the report to stdout instead of Markdown "
        "(the Markdown file at --output is still written).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero when new commits, pull requests, issues, or branches need review.",
    )
    args = parser.parse_args()

    baseline: dict
    commits: list[dict] = []
    prs: list[dict] | None | str = None
    issues: list[dict] | None | str = None
    branches: list[str] | None | str = UNDECLARED
    error: str | None = None
    try:
        baseline = load_baseline()
        ref = fetch_upstream(baseline, args.repo_dir)
        commits = collect_new_commits(baseline, args.repo_dir, ref)
        prs = collect_new_tickets(baseline, "pr")
        issues = collect_new_tickets(baseline, "issue")
        branches = collect_new_branches(baseline, args.repo_dir)
    except UpstreamCheckError as exc:
        error = str(exc)
        baseline = {
            "repo": "unknown",
            "branch": "unknown",
            "reviewed_through": "0" * 40,
            "reviewed_date": "unknown",
        }

    report = render_markdown(baseline, commits, prs, issues, branches, error)
    output = Path(args.output)
    output.write_text(report, encoding="utf-8")
    print(render_json(baseline, commits, prs, issues, branches, error) if args.json else report)

    if error:
        return 2
    # Fail closed only on a genuinely unavailable axis (auth, network, an
    # unparsable repo URL) -- `value is None`. DISABLED is a standing, structural
    # fact about the upstream repo (e.g. anthropics/commerce-agents has issues
    # turned off) and must not make every scheduled run fail forever.
    # The branch axis fails closed on BOTH of its non-list states: `None` (ls-remote
    # could not answer) and `UNDECLARED` (the baseline never declared a branch list).
    # An undeclared list is the state this axis was added to end, so letting it pass
    # would reproduce the original bug with extra steps.
    unavailable = [
        name for name, value in (("pull requests", prs), ("issues", issues)) if value is None
    ]
    if branches is None:
        unavailable.append("branches")
    elif branches is UNDECLARED:
        print(
            "ERROR: tools/upstream_baseline.json declares no `branches` list, so upstream "
            "branches are not being compared against anything."
        )
        return 2
    if unavailable:
        # Fail closed. A report that could not enumerate tickets must not be
        # allowed to read as a clean bill of health.
        print(f"ERROR: gh could not enumerate upstream {' and '.join(unavailable)}.")
        return 2
    new_prs = prs if isinstance(prs, list) else []
    new_issues = issues if isinstance(issues, list) else []
    new_branches = branches if isinstance(branches, list) else []
    if args.strict and (commits or new_prs or new_issues or new_branches):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
