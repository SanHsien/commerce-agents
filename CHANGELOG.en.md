English | [中文版](CHANGELOG.md)

# Changelog

This file records only the maintenance history of **this fork**
(`SanHsien/commerce-agents`), not changes in the `anthropics/commerce-agents` upstream —
upstream changes are tracked through `tools/check_upstream_updates.py` and
[`docs/DECISIONS.md`](docs/DECISIONS.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-09-05

### Added

- Established the fork development scaffold: a Traditional Chinese `README.md` (the
  original English file kept as `README.en.md`), `AGENTS.md`, `NOTICE.md`, `FORK.md`,
  `SECURITY.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`.
- Windows development environment: `.venv` + `requirements-dev.txt`,
  `tools/dev_check.ps1` as the one-command local gate.
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

[0.1.0]: https://github.com/SanHsien/commerce-agents/releases/tag/v0.1.0
