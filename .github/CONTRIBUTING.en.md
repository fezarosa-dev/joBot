# How to contribute to joBot

[Português](CONTRIBUTING.md) · **English**

Thanks for your interest! This guide explains how to help with joBot, now and after the release.

## Project status

joBot has no code yet and there is nothing to install. Phase 1 (foundation) is being designed. The decisions made so far are in [`docs/decisions/`](../docs/decisions/README.md) (Portuguese only for now). To learn what the project is and where it is going, read the [README](../README.en.md).

## How to help now

- **Suggestions and job sources** are welcome right away. Open an issue using the forms: Bug, Feature request or Job source.
- **Code pull requests** will only be accepted after the release (phase 8). Until then, the code is still changing a lot.
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

## Code workflow (after phase 8)

1. Fork the repository.
2. Create a branch from the up-to-date `dev`, with the right prefix (`feat/`, `fix/`, `docs/` or `ci/`).
3. Write the test, watch it fail, implement and watch it pass (TDD).
4. Check that `ruff`, `mypy --strict` and `pytest` pass.
5. Make small commits, in Portuguese, in the format `type(scope): description`.
6. Open a PR to `dev` using the [PR template](pull_request_template.md).

The exact commands to run everything will be documented once the code exists.

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
