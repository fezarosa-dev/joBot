# How to add a new site

[Português](site-novo.md) · **English**

A job site gets into joBot in one of two ways: through a **collector**, if the job list is public, or through a **reader**, if the site asks the person to sign in with their own account. This guide takes you from "I found a site" to the PR. There are two templates that already run and pass the tests: the collector one (`tests/apoio/molde_coletor.py`) and the reader one (`tests/apoio/molde_leitor.py`). You copy what fits, change what differs and let the tests tell you what is missing. The templates live in `tests/apoio/`, outside the code joBot runs, so they never become a source by mistake. To fix a source that already exists, see [How to fix a source that broke](consertar-fonte.en.md).

> [!IMPORTANT]
> joBot is still in development. Code pull requests are only accepted after the release (phase 9); see the [contributing guide](../.github/CONTRIBUTING.en.md). Until then, the way in is a "Job source" issue with the site, what you found and the capture of an example. This guide already applies if you want to get ready.

<a id="antes"></a>
## 1. Before you start

Answer these four questions before opening any file:

- **Is the site public or does it need a login?** If the job list shows up without signing in, it is a collector. If it only shows after signing in, it is a reader (section 6).
- **Do the site's terms forbid robots?** Read the terms of use. A site that forbids automated collection does not enter as a public source (ADR 0004). Meta stays out for this reason.
- **Does it ask for a CAPTCHA, an anti-robot challenge, or block the request?** Then it does not enter as a public source. joBot never works around a login, a CAPTCHA or a block: 401, 403, a login page or a challenge mean "failed", and that is it.
- **Did someone already ask for this site?** Search the issues. If not, first open an issue with the "Job source" form, with the address and the answers to the questions above. Whether it enters, and whether it comes on or off, is the maintainer's call.

<a id="forma"></a>
## 2. Choose the template and the folder

Look at how the site delivers its jobs and start from the closest example:

| The site | Folder (in `src/jobot/nucleo/coletores/`) | Start from |
|---|---|---|
| Search by job title, JSON answer | `portais/` or `agregadores/` | `tests/apoio/molde_coletor.py` |
| Search by job title, HTML answer | `portais/` | the collector template, reading with `selectolax` as in `src/jobot/nucleo/coletores/portais/usp.py` |
| Sitemap and one page per job | `plataformas/` or `portais/` | `src/jobot/nucleo/coletores/portais/super_estagios.py` |
| RSS or XML | `agregadores/` | `src/jobot/nucleo/coletores/agregadores/wwr.py` |
| Recruiting system used by many companies (ATS) | `plataformas/` | `src/jobot/nucleo/coletores/plataformas/lever.py` |
| A company's careers site | `carreiras/` | `src/jobot/nucleo/coletores/carreiras/google.py` |
| Needs a login | `src/jobot/nucleo/leitores/` | `tests/apoio/molde_leitor.py` |

`tests/unidade/test_estrutura.py` requires every collector to live in one of the four type folders and the keys it finds to be exactly the ones in `src/jobot/nucleo/dados/fontes.json`.

<a id="copiar"></a>
## 3. Copy and register the collector

Pick a **key**: lowercase letters and underscores (`minha_fonte`). It is the same everywhere below.

1. Copy `tests/apoio/molde_coletor.py` to `src/jobot/nucleo/coletores/<folder>/<key>.py`.
2. On every line with `# MUDE:`, change the value: `CHAVE`, `NOME`, `_HOST`, `_API`, `_POR_PAGINA` and `_MAX_PAGINAS`. Replace `_LIMITES = LimitesDaFonte()` with `_LIMITES = limites(CHAVE)`, using `from jobot.nucleo.coletores.registro import limites` (as in `src/jobot/nucleo/coletores/plataformas/greenhouse.py`). The registry finds the file by itself, through the `COLETOR` at the end.
3. Copy `tests/unidade/coletores/test_molde_coletor.py` to `tests/unidade/coletores/test_<key>.py` and `tests/fixtures/molde_coletor/` to `tests/fixtures/<key>/`. In the test, change the two lines with `# MUDE:` (the source module and the examples folder).
4. Add the source's entry at the end of `src/jobot/nucleo/dados/fontes.json`: `leva` `"B"`, `intervalo_min` and `max_pedidos` (or `null`), `espera_s`, `credito_obrigatorio` and `por_escopo` (`{}` in most cases), according to the site's terms. Miss any of these fields and the whole `descobrir()` breaks, for every collector. `ligada_padrao` is optional and only the maintainer changes it.
5. Give the source a name, `fonte.<key>`, in both catalogs: `src/jobot/painel/i18n/pt/comum.json` and `src/jobot/painel/i18n/en/comum.json`.
6. If the source is per company (the ATS of many companies), add the key to `ATS_POR_EMPRESA` in `src/jobot/painel/rotas/empresas.py`. If the site's terms are restrictive, add the key to `FONTES_FORA` in `scripts/vigia.py` and say so in the issue, because the README promises every public source comes on.

These lists are written by hand on purpose: they stop a source from vanishing silently. Whoever adds a source updates each one, and the test for each list fails with the key in the message:

- `tests/unidade/test_registro.py`: `LEVA_A` or `LEVA_B` (in the order of `src/jobot/nucleo/dados/fontes.json`), `CREDITO`, `LIMITES` and the total number of sources;
- `tests/unidade/test_i18n.py`: the `FONTES` list;
- `tests/integracao/test_cadastros.py`: the row count of the `fonte` table and the key count of `src/jobot/nucleo/dados/fontes.json`;
- `src/jobot/nucleo/coletores/registro.py`: the docstring that says how many sources there are;
- `README.md` and `README.en.md`, `wiki/Como-funciona.md` and `wiki/How-it-works.md`: the table of sources by type.

The template comes with the tests of a correct collector (`test_normal`, `test_vazio`, `test_formato_mudou`, `test_429_e_erro_de_rede`, `test_304`, `test_bloqueio` and others). Do not delete any: they hold joBot's rules with the site (a job that cannot be read is skipped and the state becomes `parcial`; an answer with the wrong shape becomes `falhou`, never an exception).

<a id="capturar"></a>
## 4. Capture an example

With the file in place and the address in `_API`, capture a real answer. The command makes a single request, with joBot's user agent and politeness:

```
uv run python scripts/capturar.py <key> --escopo <term> --caso normal
```

- `<key>` is the source key; `--escopo` is the search term (a per-term source needs this argument); `--caso` is the example name.
- The script writes `tests/fixtures/<key>/normal.json` (or `.html`, or `.xml`) and the matching `.meta.json`. Before writing, it removes personal data, cuts the list to 5 items and checks the 50 KB limit. Run it once and stop: do not repeat it in a loop.
- The command writes **only the first page**. Page 2 for the pagination tests is built inside the test itself, from the captured `normal`.
- **Read the file it wrote.** The detector only finds people's names in known fields: replace loose names with `Pessoa Exemplo` and redo the `sha256` in the `.meta.json` (`sha256sum <file>`).
- `vazio` and `formato_mudou` are built by hand from the `normal`, with `montado_a_mao` in the `.meta.json`. The template's examples, in `tests/fixtures/molde_coletor/`, show the shape.

Never use a login, a cookie, a CAPTCHA or any trick to get past a block. If the site refuses the request, the source "failed" and the conversation moves to the issue.

<a id="ler"></a>
## 5. Teach the collector to read

This is the project's TDD, with the example standing in for the site:

1. Replace the template's `normal` example with the one you captured. Run `uv run pytest tests/unidade/coletores/test_<key>.py -q`: `test_normal` must **fail** on an assertion. That proves the test catches the new format.
2. Adjust `_ler` and `_vaga` in the source file to understand the site's format (the field names, the shape of the list). Also adjust the part of the test that builds page 2: the site's next-page field.
3. Run again until it passes. The tests that do not depend on the format (429, 304, block) pass with no change.
4. Fix what the test asserts about the example's values (job count, titles, companies).

A collector test never uses the network: it uses the examples and a fake response. Write the code from scratch: public ideas and facts are fine, another project's code never is (clean room).

<a id="login"></a>
## 6. A site with login

A site with login is a **reader**: it makes no request at all, it only reads what joBot's browser brought back after the person signed in. joBot never types the password, and the anti-robot challenge is found by the browser, not by the reader: a login or block page means "failed".

1. **Capture before a reader exists**, with your own account: `uv run python scripts/capturar_logado.py --caso lista --host <host>`. The browser opens, you sign in with your own password, go to the page you want to keep and press Enter. Without a reader, `--host` is required. Use `--campo` for the position of the account data (name, email), which is removed by position, never by value. Repeat for `--caso vaga` and the other cases. Without a reader, each capture lands in `tests/fixtures/<caso>/` (one file and one `.meta.json` per response).
2. **Read each file** written there before committing, looking for loose personal data. After you create the reader (step 4), move the files to `tests/fixtures/<site>_logado/`.
3. Copy `tests/apoio/molde_leitor.py` to `src/jobot/nucleo/leitores/<site>.py` and change every line with `# MUDE:`. The key ends in `_logado`.
4. Copy `tests/unidade/test_leitor_molde.py` to `tests/unidade/test_leitor_<site>.py` and `tests/fixtures/molde_logado/` to `tests/fixtures/<site>_logado/`. Change the module, the folder and the expected values of each example. Do the TDD as in section 5: swap the example, watch it fail, adjust the selectors, watch it pass.
5. Register an instance of the reader in `LEITORES`, in `src/jobot/nucleo/leitores/registro.py`.
6. Give the source its name, `fonte.<site>_logado`, in both catalogs (`src/jobot/painel/i18n/pt/comum.json` and `src/jobot/painel/i18n/en/comum.json`).
7. Update the fixed reader lists: the `FONTES` list in `tests/unidade/test_i18n.py`, the registry test in `tests/unidade/test_leitores_estado.py` and the `fonte` table count in `tests/integracao/test_cadastros.py`.
8. Each prefix in `prefixos_login` is `host` + `path`, with no scheme, the host in lowercase and equal to one of the reader's `hosts` (for example `www.example.com/login`): the browser compares it with the URL's host and path, without the query, and a path-only prefix (`/login`) never matches.

A site with login is born **off**: whoever uses it turns it on in Settings. The reader only says what it read; the scope state comes out of `estado_do_escopo`. Never put a password in the code, never try to get past a CAPTCHA, and never make the reader open another route when the site asks for a login: a PR that does this does not get in.

<a id="conferir"></a>
## 7. Check it

First the source's own test, which is quick:

```
uv run pytest tests/unidade/coletores/test_<key>.py -q
uv run pytest tests/unidade/test_leitor_<site>.py -q
```

(the second only for a site with login). Then the guard and the fixed lists:

```
uv run pytest tests/unidade/test_site_novo.py tests/unidade/test_fixtures.py tests/unidade/test_registro.py tests/unidade/test_i18n.py -q
```

`tests/unidade/test_site_novo.py` is the complete-site guard: every registered collector and reader has its own test, the reader has a valid example and every source has a name in both catalogs. Each gap it finds names the key and the section of this guide that teaches how to fix it.

Last, what the CI will run:

```
uv run pytest -m "not tela" -q
uv run ruff check
uv run ruff format --check
uv run mypy
```

If `ruff format --check` complains, `uv run ruff format` fixes it. `mypy` runs in strict mode: if joBot's contract changed since the template, it points to where.

<a id="pr"></a>
## 8. Open the PR

The workflow is the one in [section 7 of the fix guide](consertar-fonte.en.md#abrir-pr): a fork, a branch from `dev` whose name starts with `feat/` (for example `feat/minha-fonte`), small commits in Portuguese in the format `type(scope): description` and the PR to `dev` using the [PR template](../.github/pull_request_template.md).

For a new site, the PR carries:

- the collector or the reader, with the test and the captured examples;
- the entry in `src/jobot/nucleo/dados/fontes.json` and the name in both catalogs;
- the fixed lists from section 3 (or section 6) updated;
- `README.md` and `README.en.md` (the table of sources) and `CHANGELOG.md` and `CHANGELOG.en.md`, with the same content in both languages;
- in the description: the site, whether it is public or with login, what its terms say about robots and how you tested.

Without the captured example and the test, the PR does not get in. If the source has restrictive terms, whether it comes on or off is the maintainer's call.
