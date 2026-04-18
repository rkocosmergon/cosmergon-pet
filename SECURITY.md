# Security Policy

## Reporting a vulnerability

If you find a security issue in Cosmergon Pet — whether in the Pet software,
the installer, or anything that could put a user's Raspberry Pi, network or
Cosmergon account at risk — **do not open a public issue**.

Instead, email: **security@cosmergon.de**

Please include:

- A description of the issue
- Steps to reproduce (code, commands, screenshots)
- The version of Cosmergon Pet and Raspberry Pi OS you tested on
- Your assessment of the impact

You will receive an acknowledgement within **5 working days**.

## Scope

In scope:

- `src/cosmergon_pet/*` — the Pet software itself
- `install/*` — the installer and systemd unit
- `scripts/*` — build-guide generator and repo tooling
- The build guide, if the documented steps would create a security problem
  (e.g. a command with `sudo` that shouldn't need it)

Out of scope:

- Issues in `cosmergon-agent` (the SDK) — report there:
  https://github.com/rkocosmergon/cosmergon-agent/security
- Issues in the Cosmergon backend, API or cosmergon.com — report via
  cosmergon.com's security contact
- Issues in third-party libraries (`luma.oled`, `RPi.GPIO`, Raspberry Pi OS)
  — please report upstream

## Disclosure

We practice coordinated disclosure. Once a fix is available and deployed,
we will publicly credit the reporter (unless requested otherwise) in the
CHANGELOG and the release notes. We do not run a bug bounty programme.

## Trademark

"Cosmergon" is a registered trademark — see `NOTICE`.
