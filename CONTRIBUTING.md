# Contributing

This repository is a single-maintainer fork (`SanHsien/commerce-agents`) of
[`anthropics/commerce-agents`](https://github.com/anthropics/commerce-agents). Upstream
states plainly that it is a reference implementation, is not maintained, and does not
accept contributions — so there is no upstream contribution flow to route pull requests
into, and this fork does not open one of its own either.

## What this means in practice

- There is no branch/PR workflow here: the maintainer verifies changes locally with
  [`tools/dev_check.ps1`](tools/dev_check.ps1) and pushes directly to `origin/main`.
- External pull requests against this fork are welcome as a courtesy, but are merged at
  the maintainer's discretion after reading the diff and running the verification steps
  in [`AGENTS.md`](AGENTS.md); there is no service-level expectation attached.
- Nothing here is ever opened as a pull request against `anthropics/commerce-agents`
  unless the maintainer explicitly decides, in a given conversation, to contribute a fix
  upstream. See [`FORK.md`](FORK.md) for the criterion.

## Reporting a problem

- A bug in the **product** (the agents, skills, examples, or plugin) most likely also
  exists upstream; consider it may need reporting there too, though upstream does not
  take contributions.
- A bug in **this fork's own maintenance tooling** (`tools/`, the fork-only GitHub Actions
  workflows, or the fork-only documentation) is this repository's own responsibility —
  open an issue or a pull request here.

## Before changing fork-owned files

1. Read [`AGENTS.md`](AGENTS.md) and [`FORK.md`](FORK.md).
2. Run `pwsh -NoProfile -File tools\dev_check.ps1` and make sure it stays green.
3. Do not modify product directories (`commerce-common/`, `shopping-agent/`,
   `merchant-agent/`, `examples/`, `plugins/`, `.claude-plugin/`,
   `docs/{safety,backends,deployment}.md`, `scripts/`) as part of a fork-maintenance
   change; those track upstream.
