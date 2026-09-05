# Security Policy

## Scope

This repository is the SanHsien maintenance fork of
[`anthropics/commerce-agents`](https://github.com/anthropics/commerce-agents). Report
vulnerabilities that affect **this fork** via this repository's Security tab. Issues that
also exist upstream should be reported to Anthropic as well, through their own channel;
this fork has no special relationship with Anthropic's security team.

commerce-agents is a reference implementation, not a production system: it ships no
authentication, its MCP servers bind to loopback only, `checkout` never charges a real
card, and every merchant write is staged until a human approves it (see
[`docs/safety.md`](docs/safety.md)). A deployment built on top of it is responsible for
its own authentication, authorization, and compliance.

## Supported versions

This fork tracks upstream `main` and does not cut its own GitHub Releases unless a
fork-only fix needs an independent version. Please reproduce issues against the current
`main` of this repository.

## Reporting a vulnerability

Please **do not** open a public issue for a security problem. Instead use GitHub's
private vulnerability reporting:

- Go to **this** repository's **Security** tab → **Report a vulnerability**.

Include: affected commit, a minimal reproduction, and the impact you observed.

## Good practices for users

- Read [`docs/safety.md`](docs/safety.md) before deploying: it lists every enforced rule,
  its module, and what a deployment must add on top (real authentication, business rules,
  compliance).
- Never commit a real `ANTHROPIC_API_KEY`; `.env.example` is a template, not a secret.
- The example MCP servers bind to loopback and have no authentication; do not expose them
  on a network interface without adding your own.
