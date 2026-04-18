<!--
Thanks for opening a PR. Before you hit "Create pull request":
- Read CONTRIBUTING.md if you haven't yet
- For anything bigger than a typo fix: an issue should be referenced
-->

## What does this change?

<!-- A few sentences. What, and why. -->

## Linked issue

<!-- Fixes #123 / Refs #456 / or "Trivial, no issue needed" -->

## Type of change

- [ ] Bug fix (non-breaking)
- [ ] New feature (non-breaking)
- [ ] Hardware variant / new port
- [ ] Build-guide update
- [ ] Translation
- [ ] 3D-printable case
- [ ] Breaking change (explain migration path below)
- [ ] Other:

## Checklist

- [ ] `ruff check src/ scripts/` is clean
- [ ] Tests added or updated if behaviour changed
- [ ] `cosmergon-pet --simulate` still runs on a laptop without hardware
- [ ] Documentation updated where relevant (README, build guide, CHANGELOG)
- [ ] If build-guide PDF was regenerated: the change is in
      `scripts/generate-pet-guide.py`, not just in the PDF
- [ ] Commit messages follow the convention (`feat:`, `fix:`, `docs:`, …)

## Whitelist / security

- [ ] I did not add paths outside the repo whitelist
      (`scripts/check-whitelist.sh` — see `CONTRIBUTING.md`)
- [ ] I did not include server IPs, internal URLs, API secrets, or
      business-internal terminology (pricing, tiers, customer-only
      features)
- [ ] I'm OK with my contribution being dual-licensed under MIT (code)
      and CC-BY-SA-4.0 (docs), per `LICENSE`

## For hardware PRs

- [ ] I have physically tested the build on real hardware
- [ ] Wiring diagram or pinout table is included
- [ ] Parts list references purchasable items (not one-off prototypes)

## For fork/rename PRs

- [ ] I have read `NOTICE` regarding trademark use

## Notes for reviewers

<!-- Anything the maintainer should know before reviewing — flaky tests, platform caveats, follow-ups. -->
