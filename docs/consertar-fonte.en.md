# How to fix a source that broke

[Português](consertar-fonte.md) · **English**

A source is a job site that joBot reads. Each source has a **collector**: a code file that knows how to ask the site for jobs and understand the answer. When the site changes its format without warning, the collector stops understanding it and the source "breaks". This guide shows, step by step, how to find what changed and fix it. The example is Greenhouse, the project's first collector (`src/jobot/nucleo/coletores/greenhouse.py`).

> [!IMPORTANT]
> joBot is still in development. To work on the code, clone the repository and run `uv sync` inside it ([`uv`](https://docs.astral.sh/uv/) installs Python 3.14 and the dependencies). Code pull requests are only accepted after the release (phase 8), and the workflow in section 7 applies from then on; see the [contributing guide](../.github/CONTRIBUTING.en.md). Until then, a fix can become an issue with what you found.

<a id="saber-qual"></a>
## 1. How to tell which source broke

There are three ways. The first two tell you the **source** and the **reason**; the third warns you even when nobody looked at the panel.

- **The Sources screen of the panel.** Open the panel (`jobot abrir`) and go to "Sources". Each source shows how its last search went. The ones marked "Failed" or "Partial" show the reason, for example "The source format changed" (`saude.formato_mudou`).
- **The "Report a problem" link.** Next to the reason, the link opens the "Source broke" form on GitHub with the source and the reason already filled in. You can see and edit everything before sending. joBot sends nothing by itself: only your click opens the link, and GitHub learns the source and the reason at that moment. For a per-company source, the source shows up as `greenhouse/<company>`.
- **The watcher issue.** Every Monday the watcher (`.github/workflows/vigia.yml` and `scripts/vigia.py`) really tests one scope of each public source and opens an issue with the `fonte-quebrada` label and the title "Fonte quebrada / broken source: <source>". It updates the issue every week and closes it when the source comes back. Eureca, Abler and Gupy are left out, because their terms are restrictive. An IP block does not count as a break for the watcher, because it runs from a GitHub server.

The reasons worth fixing are: `saude.formato_mudou`, `saude.zero_inesperado`, `saude.empresa_nao_encontrada`, `saude.bloqueio`, `saude.tempo_esgotado`, `saude.erro_de_rede`, `saude.resposta_grande` and `saude.listagem_incompleta`. The rate limit notices (quota, interval, 429, limit reached, budget) are not defects: joBot only stopped to be polite to the site, and waiting is enough.

Before touching the code, wait for a search or two and open the site in your browser. Many "breaks" are just the site being down for a while (`saude.erro_de_rede`, `saude.tempo_esgotado`). `saude.empresa_nao_encontrada` is usually a company that changed its identifier: check the identifier on the company's site before blaming the collector.

<a id="capturar"></a>
## 2. Capture the page again

The `scripts/capturar.py` script makes **one** live request, the same way joBot does (same user agent, same politeness toward the site), and saves the answer as an example. Before saving, it removes personal data, cuts the list to 5 items and checks the 50 KB limit.

```
uv run python scripts/capturar.py greenhouse --escopo vitta --caso novo
```

- `greenhouse` is the source key, the same one shown on the Sources screen.
- `--escopo` is the company identifier, for per-company sources (here `vitta`). Leave it out for a source with no companies.
- `--caso novo` is the name of the example. Use a new name: that way the old example stays there for you to compare.

The script writes `tests/fixtures/<fonte>/<caso>.json` (or `.html`, or `.xml`, depending on the source) and `tests/fixtures/<fonte>/<caso>.meta.json`, with the address, the date, the HTTP status and the file's `sha256`. Run it once and stop: do not repeat it in a loop, nor against a site that is blocking you.

If it refuses, the message says why. "nada capturado" means the site did not answer with the page (blocked, down). "dado pessoal que a limpeza não pegou" means nothing was saved, because an e-mail, phone number or ID was left over: do not put that content in the repository by hand, describe the case in an issue. The detector only finds people's names in known fields, so **read the saved file** looking for loose names in free text and replace them with `Pessoa Exemplo`; then redo the `sha256` in the `.meta.json`.

Never use a login, a cookie, a CAPTCHA or any trick to get past a block. If the site asks for any of them, the source is "failed" and that is it.

<a id="comparar"></a>
## 3. Find what changed

Compare the old example (`normal`) with the new one:

```
git diff --no-index tests/fixtures/<fonte>/normal.json tests/fixtures/<fonte>/<caso>.json
```

Jobs change all the time, so the **values** will always differ. Look at the **field names** and the **shape** of the answer: a field that disappeared, another with a new name, a number that became text, a list that now comes inside another object, an HTML page with a different structure.

In the Greenhouse example, the collector reads `title`, `company_name`, `absolute_url`, `content`, `location`, `departments`, `first_published` and `application_deadline` from each item of the `jobs` list. If the site started sending `name` instead of `title` and `url` instead of `absolute_url`, the job would be skipped and the source would be "Partial" with `saude.formato_mudou`. The example `tests/fixtures/greenhouse/formato_mudou.json` shows exactly an answer broken like that.

What each source returns under normal conditions is described in the [sources appendix](superpowers/specs/2026-11-13-fase-1-fontes.md) (Greenhouse is in section 2.4; Portuguese only). If the site changed, the appendix is out of date too: say so in the PR description.

<a id="ajustar"></a>
## 4. Adjust the collector

Before touching the code, do the first step of section 5 (replace the `normal` example with the new one) and run the collector's test: it must fail. That proves the test catches the break. Only then fix the code, which is the project's TDD: test first, it fails, fix, it passes.

Every collector's contract is in `src/jobot/nucleo/coletores/base.py`. Each collector offers:

- `escopos`: the list of what to search (per company, per country, or just one).
- `coletar`: makes the request and returns the jobs, the state (`ok`, `sem_mudanca`, `parcial`, `falhou` or `no_limite`) and the reason.
- `detalhar`: only for sources whose list does not carry the description; it opens each job.
- `resolver`: only for per-company sources; it understands the address a person pasted.

In Greenhouse, the fix for a renamed field lives in `_vaga`, which reads one job from the list. Rules of the template that the fix must not break:

- A job with no title, company or valid address is **skipped**, and the state becomes `parcial`, never `ok`. An `ok` would wrongly close the job that was skipped.
- An answer without the expected shape becomes `falhou` with `saude.formato_mudou`, never an exception.
- Do not invent new reasons in the collector: use the `saude.*` keys that exist in `src/jobot/painel/i18n/en/comum.json`. If one is missing, say so in the PR description.
- The collector does not touch `src/jobot/nucleo/coletores/registro.py` or `src/jobot/nucleo/dados/fontes.json`. The registry finds the file by itself; pacing limits and intervals live in the latter.
- Code written from scratch. You may use public ideas and facts, never copy code from another project (clean room).

<a id="atualizar-exemplo"></a>
## 5. Update the example and the tests

1. Replace the `normal` example with the new one: replace `tests/fixtures/<fonte>/normal.json` and `tests/fixtures/<fonte>/normal.meta.json` with the files of the new case, and delete the leftover `novo` case. If you prefer, run the capture again with `--caso normal`.
2. Redo the **hand-assembled** cases from the new `normal`. Their `.meta.json` has the `montado_a_mao` field, which says where they came from. In Greenhouse they are `formato_mudou`, `nao_encontrado` and `prazo`; `normal` and `vazio` do not have that field, but check `vazio` too, since its shape may have changed. After editing a file, update the `sha256` in the `.meta.json` (on Linux, `sha256sum <file>` gives the value): the `tests/unidade/test_fixtures.py` test checks it.
3. If the broken format is a case that had no test yet, add an example and a test in `tests/unidade/coletores/test_<fonte>.py`, in the same style as the existing ones.
4. Adjust whatever the test asserts about the example's values (number of jobs, titles), which change with the new example.

Collector tests never use the network: they use the examples and a fake answer. The example is the only bridge between the real site and the tests.

<a id="testar"></a>
## 6. Run the tests, lint and types

First only the source's test, which is quick:

```
uv run pytest tests/unidade/coletores/test_<fonte>.py -q
```

Then the four checks that CI will run:

```
uv run pytest -m "not tela" -q
uv run ruff check
uv run ruff format --check
uv run mypy
```

`pytest` runs every test except the screen ones (which need the browser and only run in CI). `ruff check` and `ruff format --check` handle style and `mypy` handles types, in strict mode. All four must pass. If `ruff format --check` complains, `uv run ruff format` fixes it.

<a id="abrir-pr"></a>
## 7. Open the PR

The workflow is the one in the [contributing guide](../.github/CONTRIBUTING.en.md):

1. Fork the repository and create a branch from `dev`, with a name starting with `fix/` (for example `fix/greenhouse-fields`).
2. Make small commits, in Portuguese, in the format `type(scope): description`, such as `fix(coletor): lê o título novo do Greenhouse`.
3. Open the PR to `dev` using the [PR template](../.github/pull_request_template.md). Say which source broke, the reason the screen or the watcher showed, what changed on the site and how you tested. If it came from a watcher issue, mention its number.
4. A fix PR must carry the **new captured example** and the **test**. Without them, it does not get in.

The first PR from someone who has never contributed may wait for the maintainer to release the test run on GitHub. It is a guard against abuse, not a judgment of your fix.
