# How to contribute to joBot

[Português](CONTRIBUTING.md) · **English**

Thanks for your interest! This guide explains how to help with joBot, now and after the release.

## Project status

Phases 1, 2 and 3 (foundation, browser with login and installer) are complete: joBot 0.4.0 can already be installed and used ([how to install](../README.en.md#requirements-and-installation)). Phase 4 (local AI) is being built, toward 0.5.0; phases 5 to 9 are planned. The decisions made so far are in [`docs/decisions/`](../docs/decisions/README.md) (Portuguese only for now). To learn what the project is and where it is going, read the [README](../README.en.md).

## How to help now

- **Suggestions and job sources** are welcome right away. Open an issue using the forms: Bug, Feature request or Job source.
- **Did a job source break?** The guide [How to fix a source that broke](../docs/consertar-fonte.en.md) shows how to find what changed and fix it. For now it helps you understand the path and report what you found in an issue; the PR with the fix follows the rule below.
- **Want to add a new job site?** The guide [How to add a new site](../docs/site-novo.en.md) takes you from the site to the PR, with a template that already runs for a public site and another for a site with login. For now it helps you get ready and open the "Job source" issue; the PR follows the rule below.
- **Code pull requests** will only be accepted after the release (phase 9). Until then, the code is still changing a lot.
- Issues and PRs can be written in **Portuguese or English**.
- Found a security flaw? **Do not open a public issue.** See the [Security Policy](SECURITY.en.md).
- Need help or have a question? See [Support](SUPPORT.en.md).
- By taking part, you accept the [Code of Conduct](CODE_OF_CONDUCT.en.md).

## Project rules

- **TDD for all code.** Write the test first, watch it fail, write the code and watch the test pass.
- **Commits in Portuguese**, in the format `type(scope): description`. The types are: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style` and `revert`.
- **Branches:** start the name with `feat/`, `fix/`, `docs/` or `ci/`, branching from `dev`. `main` only receives PRs coming from `dev`.
- **Quality:** `ruff` handles style, `mypy` in strict mode (`--strict`) handles types and `pytest` runs the tests.
- **New dependencies** only with a reason and a license compatible with MIT.

## Building the window (shell)

The joBot window is a Tauri 2 app, in Rust, in the `desktop/` folder ([ADR 0025](../docs/decisions/0025-app-de-desktop-e-instalador.md), in Portuguese). It stays outside the Python package: it only talks HTTP to the dashboard and calls `jobot` and `uv`. To work on it:

1. Install Rust with [rustup](https://rustup.rs/). The version is pinned in `desktop/rust-toolchain.toml`, and rustup picks it by itself inside `desktop/`.
2. On Linux, install the WebKitGTK libraries. On Debian and Ubuntu: `sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf`. On other distros the names change; see the [Tauri](https://v2.tauri.app/start/prerequisites/) prerequisites.
3. Install the Tauri CLI at the same version as the release build: `cargo install tauri-cli --version =2.12.4 --locked`.
4. Inside `desktop/`, `cargo tauri dev` opens the window in development mode. Before the PR, run `cargo fmt --check`, `cargo clippy --locked --all-targets -- -D warnings` and `cargo test --locked` there, the same as CI ([`casca.yml`](workflows/casca.yml)).

**Resources.** On build, `desktop/build.rs` copies the dashboard's CSS, fonts and icon into `desktop/ui/painel/` and creates an empty `desktop/recursos/`; both folders are ignored by git. With empty resources, the window says the installer is incomplete: in development, that is expected. If joBot is already installed through the window, it goes straight to the dashboard; to see the install screen without touching your data, point `JOBOT_DADOS` at an empty folder.

The real resources (`uv`, Python, the wheels, joBot and `manifesto.json`; the browser is not in the resources, it comes from `playwright install`) come from `scripts/montar_recursos.py recursos`, which checks the sha256 of every download and prints the manifest's; that value goes into the build through the `JOBOT_MANIFESTO_SHA256` variable. The whole recipe, step by step, is the `casca` job in [`pacotes.yml`](workflows/pacotes.yml), which the release runs and which `casca.yml` runs by hand with the `pacotes` input. Each installer weighs about 100 to 200 MB: to prove a change to the package, prefer CI.

## Code workflow (after phase 9)

1. Fork the repository.
2. Create a branch from the up-to-date `dev`, with the right prefix (`feat/`, `fix/`, `docs/` or `ci/`).
3. Write the test, watch it fail, implement and watch it pass (TDD).
4. Check that `ruff`, `mypy --strict` and `pytest` pass.
5. Make small commits, in Portuguese, in the format `type(scope): description`.
6. Open a PR to `dev` using the [PR template](pull_request_template.md).
7. Wait: the tests of your PR only run after the project maintainer allows them, and the PR is only merged with the maintainer's approval.

## Wiki

- The wiki text lives in the [`wiki/`](../wiki/) folder of the repository.
- A change to the wiki is made by a PR on that folder, like any other file.
- When the PR reaches `main`, a bot copies the folder to the GitHub wiki.
- Editing directly on the GitHub wiki is left to the project maintainers only. Direct edits are overwritten on the next copy, so every change goes through the `wiki/` folder.
- A new page needs a version in both languages (Portuguese and English). The test checks this.

## Clean room

You may use public ideas and facts from other projects. Never copy third-party code or test data.

## License

joBot uses the [MIT license](../LICENSE). By contributing, you agree that your contribution enters the project under the same license.
