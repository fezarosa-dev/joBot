# Changelog

[Português](CHANGELOG.md) · **English**

All notable changes to the project are recorded in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-11-14

Phase 1: the foundation of joBot. You can already install and use it.

### Added

- Dashboard in the browser, at `http://127.0.0.1:47615`, with Jobs, Searches, Sources, Companies, Suggested, Sites and Settings.
- Job search in dozens of public sources, every 3 hours or on demand, with the "Search now" button.
- Job cleanup: removes duplicates and reads salary, field, level, work mode, region and contract type.
- Match score with your search (good, medium, weak), by rules and with the reasons. No AI.
- A status for each job, from "new" to "offer", and the tabs Highlights, All, New, Closing soon, Saved, Applied, Programs and Hidden.
- Tracking of program pages, such as trainee and summer school, in the Sites screen.
- Own company list and weekly discovery of new job boards, which go to Suggested until you approve them.
- Commands `jobot abrir`, `jobot sair`, `jobot serve`, `jobot buscar`, `jobot segundo-plano`, `jobot atualizar` and `jobot avaliar-rotulos`.
- Background service on Linux, through the user's systemd, including from a distrobox container.
- New-version notice, off by default. When on, it only asks `api.github.com` for the newest version, and the request carries the fixed user agent and the IP.
- Eureca, Abler and Gupy, each with its own on/off switch. All come on by default; Eureca's terms ask for prior consent, and anyone who prefers to respect that can turn Eureca off in Settings.
- Dashboard in Portuguese and English, with light and dark themes.
- In the search progress bar, the list of the sources that are still running.
- A "Saved." notice after saving in Settings.
- Project decisions (ADRs 0001 to 0021) and `duvidas.md`.
- README with badges, diagram, tables and a FAQ, and the English version.
- Star history chart in the README.
- Preview image for social networks (`docs/imagens/previa-social.png`).
- MIT license, Code of Conduct, security policy, contributing guide, support, issue and PR templates, and CODEOWNERS, also in English.
- `CITATION.cff`, `.editorconfig` and `.gitattributes`.

### Changed

- Code of Conduct reports go to the project email.
- The README is no longer only a plan: it describes the phase 1 installation.

### Fixed

- The weekly Common Crawl discovery no longer fails because of huge blocks from other sites, which joBot never downloads.
- Greenhouse accepts very large job boards, such as Stripe's.
- The schedule only starts searching after the first-run wizard is finished.
- In Sources, a source that hit its limit shows the last round it actually ran.
