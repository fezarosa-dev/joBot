# Manutenção do CI e dos testes: plano de implementação

> Cada tarefa roda num worktree próprio e passa por revisão de outra pessoa ou sessão, diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido; erro de import, de coleta ou zero testes não valem como vermelho.

**Objetivo:** deixar a bateria de testes de tela rápida e estável no CI em paralelo (D149), sem esconder falha com repetição automática.

**Regra de medida:** aqui a RAM é curta, então a medida é o CI. Nesta máquina rodam só o arquivo de teste da tarefa e o `ruff`; as medições de tempo vêm de uma branch `lote/manutencao` no Actions. Nenhum teste espera tempo real (`CLAUDE.md` do projeto), e não entra dependência nova (ADR 0021).

**Base:** `dev` atual. Escolhas em aberto, se aparecerem, vão para o `duvidas.md`.

### T292: testes de tela lentos e instáveis
`depende_de: —` · D149

O sintoma: `tests/tela/test_buscar_agora.py::test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento` já falhou de vez em quando no CI por setup lento (o `painel` de `tests/tela/conftest.py` sobe um servidor a cada teste e espera até 10 s). A causa de cada teste lento ou instável tem de ser achada e corrigida; repetir o teste até passar não vale.

Outro caso, em 2026-11-16: `tests/navegador/test_navegacao_logada.py::test_cloudflare_que_leva_a_url_com_fragmento_segue` falhou uma vez no CI (a visita voltou `bloqueio` em vez de `Captura`) num lote que só mexia em CSS. Entra na lista para investigar.

**Arquivos:**
- modificar `tests/tela/conftest.py` e os arquivos de `tests/tela/` que a medição apontar;
- modificar `.github/workflows/ci.yml` só para medir (`--durations=25`, depois volta ao valor de hoje);
- modificar `registros/padroes.md` (ou `registros/padroes-tela.md`) com a lição, se sair uma.

- [ ] **Medir antes:** numa branch `lote/manutencao`, rodar `uv run pytest -m tela --durations=25` em cada parte (`JOBOT_PARTE=i/16`) e anotar, no fim desta tarefa, os 25 mais lentos de cada parte (setup, chamada e fim separados), o tempo de cada job `tela` e as falhas da rodada.
- [ ] **Achar a causa** de cada lento: fixture que sobe servidor ou banco a cada teste sem precisar, espera fixa (`time.sleep`, `wait_for_timeout`), `expect` sem condição clara, semeadura repetida, pedido que espera o tempo limite. Uma linha por causa, com `arquivo:linha`.
- [ ] **Teste que falha antes:** para cada causa que dá para provar sem relógio, um teste em `tests/unidade/` ou `tests/tela/` que falha numa asserção (por exemplo, a fixture não pode esperar mais do que o necessário depois de `started`; nenhum teste de tela chama `wait_for_timeout` nem `time.sleep`, conferido por varredura do texto). Causa que só aparece na máquina do CI fica com a medição como prova: o tempo antes e depois.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/<arquivo>.py -q` (e o teste de tela da causa, no CI).
- [ ] **Corrigir a causa**, sem tocar no que não foi medido: fixture por escopo certo, espera por condição (`expect`, `wait_for`) no lugar de tempo, semente menor. Sem plugin de repetição e sem dependência nova.
- [ ] **Ver passar:** o arquivo do teste novo e `uv run ruff check && uv run ruff format --check` aqui; `-m tela` no CI.
- [ ] **Critério de pronto:** 3 rodadas seguidas do CI verdes, sem nenhuma falha de tela, na mesma branch. Anotar no fim desta tarefa os tempos antes e depois (por parte e total da rodada).

**Tempos (preencher ao fechar):**

| Medida | Antes | Depois |
|---|---|---|
| Job `tela` mais lento | 86 a 98 s nas 6 rodadas verdes (passo do pytest até 64 s, sempre na parte com `test_teto_de_20_vagas...`) | |
| Rodada inteira | 93 a 104 s (do primeiro job ao último) | |
| Falhas de tela em 3 rodadas | 0 nas 6 verdes; no histórico, 1 instável (`test_cloudflare_que_leva_a_url_com_fragmento_segue`, rodada 43822440143) | |

**Medição antes** (2026-11-16, rodadas 43839282579, 43834463738, 43834328032, 43832531326, 43831596113, 43829811010 e a que falhou, 43829257858). Medida com `--durations=5`, não 25: só os 5 mais lentos de cada parte.

- Cada parte roda 17 ou 18 testes; o passo do pytest leva de 29 a 64 s (mediana 38 s), dos quais 5 a 9 s são a coleta dos 5714 testes. O passo `playwright install --with-deps chromium` leva 18 s na mediana e até 66 s: é o resto do job.
- Os mais lentos (chamada): `test_detalhe_logado.py::test_teto_de_20_vagas_e_o_resto_volta_depois` 16,5 s; `test_janela_parada.py::test_duas_abas_dividem_os_15_minutos` 12 s; `test_detalhe_logado.py::test_site_que_parou_no_meio_nao_abre_vaga` e `::test_lista_com_descricao_nao_abre_vaga` 6,3 a 6,8 s; `test_navegacao_logada.py::test_navegacao_nao_faz_post` 6,3 a 6,7 s; `test_execucao_logada.py::test_teto_de_10_paginas_de_lista_por_site` 5,7 a 6 s; `test_captcha_logado.py::test_login_com_captcha_nao_chama_resolver` 2,9 a 6,3 s. Em `tests/tela`, nenhum passa de 5,3 s.
- Preparação de 1,3 a 7,6 s só aparece no primeiro teste de cada parte (`test_captcha_logado.py` na pasta `navegador`, `test_apoie.py` na `tela`): é a subida do Playwright e do Chromium.
- As 3 falhas da 43829257858 (`test_configuracoes.py` duas vezes, `test_casca.py` com o CSP) eram regressões do lote, fixas, corrigidas na rodada seguinte. Nas 40 últimas rodadas que falharam, nenhuma traz `test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento`.

**Causas achadas:**

- `src/jobot/navegador/pagina.py:255` (instável): o status só era relido quando a primeira olhada (`_e_cloudflare`) ainda via o desafio. Na máquina lenta, o desafio do site falso sai em 50 ms, antes dessa olhada; a página já era `/lista`, mas o status seguia o 403 do desafio e a visita voltava `bloqueio`. Correção: o status e as checagens de host e login são refeitos também quando o documento trocou sozinho (a última resposta da URL atual não é a do `goto`). Prova sem relógio: `test_navegacao_logada.py::test_cloudflare_que_sai_antes_da_primeira_olhada_vale_a_pagina_nova`, que segura a primeira olhada até a página nova carregar.
- `tests/navegador/test_detalhe_logado.py:181` (lento): 27 navegações reais, e cada uma custa uns 0,6 s (o `networkidle` de `_assentar` espera 500 ms de rede parada). Correção: `MAX_VAGA` 3 e lista de 5 vagas (`/lista-5`); o 20 já se prende em `tests/unidade/test_navegador_abrir.py`.
- `tests/navegador/test_janela_parada.py:324` (lento): a janela de 900 s são 180 olhadas, cada uma com 0,05 s reais do `RelogioDoNavegador`. Correção: `JANELA_PARADA_S` 60, como os outros testes do arquivo.
- `tests/navegador/test_detalhe_logado.py:236` e `:272` (lentos): o controle lia `/quatro?q=a`, 4 páginas de lista e 4 de vaga. Correção: `/quatro?q=a&p=4`, uma lista e uma vaga.
- `tests/navegador/test_execucao_logada.py:394` (lento): 10 páginas de lista. Correção: `MAX_LISTA` 6 com três escopos; o 10 se prende em `tests/unidade/test_navegador_abrir.py`.
- Não corrigidas: `test_navegacao_nao_faz_post` visita todas as páginas do site falso de propósito; `test_login_com_captcha_nao_chama_resolver` abre o Chromium duas vezes. As fixtures `montagem`, `lancar` e `contexto_de_teste` sobem o Playwright a cada teste (0,5 a 0,9 s só na saída); dividi-las por sessão pede fixture assíncrona de sessão no anyio (fica para a T295). Os testes de `test_buscar_agora.py` esperam a pergunta de 2 em 2 s do painel (cerca de 2,5 s cada; T295). O passo `playwright install` do CI, de 18 s na mediana, fica para a T294.

### T293: config estragada não derruba a lista de Vagas
`depende_de: T254, T255, T256, T257` (o lote do visual que mexe em `src/jobot/painel/rotas/vagas.py` já na `dev`, para não dar conflito)

Hoje `rotas/vagas.py` lê a config com `config_ou_padrao` (definida em `painel/consultas.py`) em três lugares: `ler_estado` (`destaques_ligados`) e `raiz` (`primeira_execucao_concluida` e `destaques_ligados`). Ela faz `json.loads` sem `try`: um valor estragado em `destaques_ligados` levanta `ValueError` e dá 500 em `/` e em `/vagas`. `banco.cadastros.ler_config` já devolve o padrão quando o valor não presta.

**Arquivos:**
- modificar `src/jobot/painel/rotas/vagas.py` (as três chamadas passam a `ler_config`);
- modificar `src/jobot/painel/consultas.py` (apagar `config_ou_padrao` se ninguém mais usar; conferir com `rtk grep -rn config_ou_padrao src tests`);
- modificar `tests/integracao/test_rota_vagas.py` e, se citar o nome apagado, o texto de `tests/unidade/test_lateral.py`.

- [ ] **Teste que falha antes:** gravar `destaques_ligados` com JSON estragado (`INSERT` direto na tabela `config`, com `{`) e pedir `/` e `/vagas`; esperar 200 em `/vagas` e, em `/`, o redirecionamento para `/vagas?aba=destaques` (o padrão `True`). O teste afirma o valor de reserva (a aba de destaques ligada), não só o 200.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py -q -k estragad`; o vermelho é a asserção, não um erro de import.
- [ ] **Corrigir:** trocar `config_ou_padrao(con, chave, padrao)` por `ler_config(con, chave, padrao)` nos três lugares e apagar a função e o import que sobrar.
- [ ] **Ver passar:** o arquivo do teste e `uv run ruff check && uv run ruff format --check`.

### T294: Chromium do Playwright em cache no CI
`depende_de: —`

O passo `uv run playwright install --with-deps chromium` leva 18 s na mediana e até 66 s no job `tela` (medição da T292), repetido nas 16 partes.

**Arquivos:**
- modificar `.github/workflows/ci.yml` (job `tela`; olhar também se o job `comuns` instala o Chromium).

- [ ] **Cache:** guardar `~/.cache/ms-playwright` com a chave pela versão do `playwright` no `uv.lock` (hoje 1.65.1). Com cache encontrado, rodar só `uv run playwright install-deps chromium`; sem cache, o `install --with-deps` de hoje.
- [ ] **Action fixada** pelo hash do commit, com a versão em comentário, do mesmo jeito que as outras do `ci.yml` (`actions/cache`).
- [ ] **Sem dependência nova** e sem teste de unidade (é `ci.yml`).
- [ ] **Prova:** tempo do passo antes e depois em 2 rodadas na branch `lote/manutencao` (a primeira enche o cache, a segunda o usa). Anotar na tabela abaixo.

| Medida | Antes | Depois |
|---|---|---|
| Passo de instalação do Chromium (mediana, máximo) | 18 s, 66 s | |

### T295: navegador e tela mais rápidos nos testes
`depende_de: T292`

Três causas que a T292 deixou de fora.

**Arquivos:**
- modificar `tests/navegador/test_execucao_logada.py`, `tests/navegador/test_captcha_logado.py`, `tests/navegador/apoio/site_falso.py` e o `conftest.py` da pasta, se houver;
- modificar `tests/tela/test_buscar_agora.py` e `tests/tela/conftest.py`;
- modificar `registros/padroes.md` com a lição, se sair uma.

- [ ] **(a) Playwright por sessão:** `async_playwright` sobe a cada teste em `tests/navegador` (`test_execucao_logada.py:100`, `test_captcha_logado.py:158`, `apoio/site_falso.py:654`), com 0,5 a 0,9 s só na desmontagem. Trocar por fixture de sessão por parte (`anyio_backend` de escopo de sessão), mantendo o contexto de cada teste isolado.
- [ ] **(b) Relógio do navegador:** `tests/tela/test_buscar_agora.py:83` e `:119` esperam a pergunta de 2 em 2 s do painel. Usar `page.clock` (`install` e `fast_forward`) no lugar da espera real.
- [ ] **(c) Corrida de porta (hipótese, não provada):** a falha antiga de "setup lento" do `test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento` pode ser a fixture `porta` de `tests/tela/conftest.py`, que fecha o socket antes de o uvicorn ligar (outro processo pode pegar a porta). Provar com teste ou descartar com medição; descartada, anotar aqui a medição.
- [ ] **Ver falhar:** o que der para provar sem relógio, em `tests/unidade/` ou na própria tela (por exemplo, nenhum teste de `tests/tela` espera tempo real; conferido por varredura do texto). O resto fica com a medição do CI.
- [ ] **Ver passar:** o arquivo de cada teste mexido e `uv run ruff check && uv run ruff format --check` aqui; o resto no CI.
- [ ] **Critério:** tempos antes e depois, por parte, no CI (`--durations`), e 3 rodadas verdes seguidas.
