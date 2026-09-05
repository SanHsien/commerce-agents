English | [中文版](CHANGELOG.md)

# Changelog

This file records only the maintenance history of **this fork**
(`SanHsien/commerce-agents`), not changes in the `anthropics/commerce-agents` upstream —
upstream changes are tracked through `tools/check_upstream_updates.py` and
[`docs/DECISIONS.md`](docs/DECISIONS.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-09-05

Policy reversal: this fork no longer keeps declared dependencies behind upstream or
routes around a red test just to hold zero diff against an upstream-owned file.
Dependencies now track upstream's latest release directly, a red test gets its test
condition fixed rather than deselected, and every divergence from upstream is recorded
in a new `docs/DIVERGENCE.md`, machine-enforced for consistency. See the second entry
dated this day in [`docs/DECISIONS.md`](docs/DECISIONS.md).

### Added

- `docs/DIVERGENCE.md`: a per-file registry of this fork's changes to upstream-owned
  files, with an actionable rule for each row for handling it at the next upstream sync.
- `tools/check_divergence.py`: compares "upstream-owned files actually changed since
  the baseline commit" against what `docs/DIVERGENCE.md` registers, and exits non-zero
  on any mismatch; wired into `tools/dev_check.ps1` and
  `.github/workflows/upstream-check.yml`. `tests/test_fork_divergence.py` is its
  contract test suite.
- `tools/check_pin_bounds.py` and `.github/workflows/pin-bounds.yml`: check every exact
  pin in the requirements files against every range the `pyproject.toml` files declare,
  on each pull request and in the local gate. `scripts/check.py` never reads the
  requirements files, so this is the only check covering that coupling.
  `tests/test_fork_pin_bounds.py` is its contract test suite.

### Changed

- `requirements-dev.txt` (upstream-owned, now edited directly): `ruff` raised to
  `0.16.6`; added a `tzdata==2026.3` line gated by a `sys_platform == "win32"`
  environment marker.
- `.github/workflows/ci.yml` (upstream-owned, now edited directly): all three Actions
  (`checkout` x3, `setup-python` x2, `setup-node` x1) repinned from a floating tag to a
  commit SHA with a `# vX.Y.Z` comment.
- `commerce-common/tests/test_memory_stores.py` (upstream-owned, now edited directly):
  the POSIX `0o600` permission assertion is now platform-conditional
  (`if os.name != "nt":`) instead of being deselected wholesale.
- `tools/dev_check.ps1`: removed `--deselect` from the `pytest` step; added the
  `check_divergence.py` and `check_pin_bounds.py` steps.
- `.github/dependabot.yml`: `pip` and `npm` raised from `open-pull-requests-limit: 0` to
  `5`, so all three ecosystems now open pull requests; `groups` collapses a run into one
  pull request and `ignore` excludes the seven in-repo packages. This also corrects an
  earlier claim that a single-package pull request would break `scripts/check.py` — that
  script never reads `requirements.txt`.
- `tools/check_dependency_freshness.py`: `REQUIREMENT_FILES` reverted to just
  `requirements-dev.txt`.
- `.github/dependency-deferrals.json`: cleared the four "waiting on upstream"
  deferrals.

### Removed

- `requirements-dev-windows.txt`: `tzdata` is now folded into `requirements-dev.txt`
  itself.

## [0.1.0] - 2026-09-05

### Added

- Established the fork development scaffold: a Traditional Chinese `README.md` (the
  original English file kept as `README.en.md`), `AGENTS.md`, `NOTICE.md`, `FORK.md`,
  `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.
- Windows development environment: `.venv` + `requirements-dev-windows.txt` (upstream's
  `requirements-dev.txt` plus `tzdata`, the IANA time zone database Windows CPython does
  not ship), `tools/dev_check.ps1` as the one-command local gate (it preflights the time
  zone database and deselects one upstream test that asserts POSIX file permissions
  Windows has no equivalent for).
- Maintenance tooling: `tools/check_dependency_freshness.py` (checks
  `requirements-dev.txt` against PyPI and pinned Actions in `.github/workflows/*.yml`
  against the GitHub Releases API), `tools/check_upstream_updates.py` (tracks unreviewed
  upstream commits, pull requests, and issues), `tools/check_links.py` (checks relative
  links between maintenance documents), each with `tests/test_fork_*.py` contract tests.
- GitHub Actions: `dependency-freshness.yml` (monthly), `upstream-check.yml` (weekly),
  `codeql.yml` (`python` and `javascript-typescript`, scheduled scans included).
- `.github/dependabot.yml`: the `github-actions` ecosystem opens pull requests normally;
  `pip` (root) and `npm` (`examples/`) are pin files owned by upstream, so
  `open-pull-requests-limit: 0`.
- `.cursor/rules/no-upstream-pr.mdc`: a machine-readable rule that all PRs/pushes/releases
  target `origin` only.
- `.editorconfig`, `.gitattributes`: consistent indentation (2 spaces; 4 for `.py`/`.ps1`)
  and line endings (LF).

### Changed

- `CLAUDE.md`: inserted a fork-boundary block at the top; the rest of the upstream
  content is untouched.
- `.gitignore`: appended a fork section ignoring the two generated reports,
  `upstream-review-report.md` and `dependency-freshness-report.md`.
- `ruff.toml`: appended `"tools"` to the `src` array.

[0.2.0]: https://github.com/SanHsien/commerce-agents/releases/tag/v0.2.0
[0.1.0]: https://github.com/SanHsien/commerce-agents/releases/tag/v0.1.0
