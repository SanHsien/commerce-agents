# NOTICE

commerce-agents (SanHsien maintenance fork)
Copyright 2026 SanHsien

This project is derived from [`anthropics/commerce-agents`](https://github.com/anthropics/commerce-agents),
originally licensed under the Apache License, Version 2.0.

Original work:

- Project: `commerce-agents`
- Author: Anthropic PBC
- License: Apache License 2.0
- Original copyright notice: `Copyright 2026 Anthropic PBC`
- Upstream: https://github.com/anthropics/commerce-agents

This repository keeps the original Apache License 2.0 text in [`LICENSE`](LICENSE).
Modifications, fork-only documentation, and Windows maintenance tooling added in this
fork are also licensed under Apache License 2.0 unless otherwise noted, and carry their
own `SPDX-License-Identifier: Apache-2.0` header where the upstream convention already
adds one to source files.

## License Notes

The Apache License 2.0 allows use, reproduction, modification, and distribution, in
source or object form, provided that:

- a copy of the license is included with any distribution (kept here as [`LICENSE`](LICENSE));
- modified files carry a notice stating that changes were made;
- this NOTICE file's attribution content is reproduced in any distribution that includes
  a `NOTICE` file, as Section 4(d) of the license requires;
- no trademark rights are granted, and the "Apache" name and any Anthropic trademarks are
  not implied to be endorsed by this fork.

When redistributing this project or substantial parts of it:

- Keep [`LICENSE`](LICENSE) with the original Apache 2.0 text.
- Keep this `NOTICE.md` (or fold its attribution content into a `NOTICE` file) alongside it.
- Keep attribution to `anthropics/commerce-agents`.
- Add separate attribution for new third-party dependencies when their licenses require it.

## Project Scope

This fork exists to run and maintain the reference shopping/merchant agent implementation
on a Windows 11 development machine, with a Traditional Chinese public entry point and a
reproducible local verification gate. It does not change the product's design rules, the
fictional ACME branding, or the safety gates described in [`docs/safety.md`](docs/safety.md).

## AI-Assisted Changes

Fork-only files (documentation, GitHub Actions workflows, and the `tools/` maintenance
scripts) in this repository were drafted with the assistance of an AI coding agent
(Claude Code) under human review and direction. Every change is committed under the
maintainer's own authorship and is reviewed against the verification steps in
[`AGENTS.md`](AGENTS.md) before being pushed. AI assistance carries no warranty beyond
what the Apache License 2.0 already disclaims (Section 7); responsibility for what is
pushed to `origin/main` rests with the maintainer, not with the tool.

## Not Affiliated

This fork is not affiliated with, endorsed by, or sponsored by Anthropic PBC. It is a
personal maintenance line of a published reference implementation.
