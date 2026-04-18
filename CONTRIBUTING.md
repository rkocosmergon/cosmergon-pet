# Contributing

Pull requests are welcome — the Pet is explicitly designed to be forked,
modded and extended. A few things to know before you open a PR.

## Before you start

- **Open an issue first** for anything bigger than a typo fix or a
  one-line bug fix. Saves you from building something that conflicts
  with work in progress.
- **Check the existing issues** — someone may already have run into
  the same wiring problem, encoder quirk or OS-version oddity.
- **Join the discussion** in GitHub Discussions if you want to float
  an idea before committing code.

## What we welcome

- Hardware variants (M5Stack Dial port, MaTouch SmartKnob, other
  displays, ESP32 ports)
- Better wiring diagrams (Fritzing files, annotated photos)
- 3D-printable case designs
- Translations of the build guide (English, other languages)
- Troubleshooting entries (bring your real-world pain)
- New info-screens, menu actions, face variants
- Test improvements (pytest, mock-GPIO harness)

## What we push back on

- **Anything that pulls in business-logic from Cosmergon's backend.**
  The Pet is a client of the public API — it must not grow into a
  proxy, admin tool or commercial feature channel.
- **Depending on private/proprietary services or APIs.** The Pet
  should work against any OpenAI-compatible LLM, any instance of the
  Cosmergon API.
- **"Improvements" that break headless install.** Maker users don't
  want a Desktop environment just to run the Pet.

## Style

- **Python**: Ruff + PEP 8, 100-char lines. `cosmergon-pet --simulate`
  must still work without OLED/GPIO hardware — keep the simulate path
  intact when you touch `face.py`.
- **Commit messages**: conventional prefixes (`feat:`, `fix:`,
  `docs:`, `hw:`, `test:`). Imperative mood. Explain *why* in the
  body for anything non-obvious.
- **Build guide** is generated from `scripts/generate-pet-guide.py`.
  Edit the generator, not the PDF.

## PR checklist

- [ ] Change is described in the PR body (what + why)
- [ ] Docs updated where it matters (README, build guide, CHANGELOG)
- [ ] `ruff check src/ scripts/` is clean
- [ ] Tests added / updated if you touched behaviour
- [ ] Commit history is tidy (rebase-squash if you wandered around)
- [ ] You're OK with your contribution being released under the
      dual license (`LICENSE`) — MIT for code, CC-BY-SA-4.0 for docs

## Whitelist / repo hygiene

This repo has a strict file whitelist (see
`scripts/check-whitelist.sh`). The CI workflow blocks any PR that
adds files outside the allowed paths or contains banned keywords
(server IPs, internal URLs, proprietary business terms).

If your PR needs a new path or file type, open an issue first — the
whitelist is expanded only with maintainer review, not per PR.

## Trademark

"Cosmergon" is a trademark. If you fork for your own product, please
read `NOTICE` and name your fork something that isn't
`Cosmergon-*`. Contributing back upstream is, of course, welcome and
requires no name change.

## Questions?

- Technical discussions → GitHub Discussions
- Private matters → contact@cosmergon.de
- Security issues → security@cosmergon.de (see `SECURITY.md`)
