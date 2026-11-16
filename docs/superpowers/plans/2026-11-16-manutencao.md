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

- [x] **Medir antes:** numa branch `lote/manutencao`, rodar `uv run pytest -m tela --durations=25` em cada parte (`JOBOT_PARTE=i/16`) e anotar, no fim desta tarefa, os 25 mais lentos de cada parte (setup, chamada e fim separados), o tempo de cada job `tela` e as falhas da rodada.
- [x] **Achar a causa** de cada lento: fixture que sobe servidor ou banco a cada teste sem precisar, espera fixa (`time.sleep`, `wait_for_timeout`), `expect` sem condição clara, semeadura repetida, pedido que espera o tempo limite. Uma linha por causa, com `arquivo:linha`.
- [x] **Teste que falha antes:** para cada causa que dá para provar sem relógio, um teste em `tests/unidade/` ou `tests/tela/` que falha numa asserção (por exemplo, a fixture não pode esperar mais do que o necessário depois de `started`; nenhum teste de tela chama `wait_for_timeout` nem `time.sleep`, conferido por varredura do texto). Causa que só aparece na máquina do CI fica com a medição como prova: o tempo antes e depois.
- [x] **Ver falhar:** `uv run pytest tests/unidade/<arquivo>.py -q` (e o teste de tela da causa, no CI).
- [x] **Corrigir a causa**, sem tocar no que não foi medido: fixture por escopo certo, espera por condição (`expect`, `wait_for`) no lugar de tempo, semente menor. Sem plugin de repetição e sem dependência nova.
- [x] **Ver passar:** o arquivo do teste novo e `uv run ruff check && uv run ruff format --check` aqui; `-m tela` no CI.
- [x] **Critério de pronto:** 3 rodadas seguidas do CI verdes, sem nenhuma falha de tela, na mesma branch. Anotar no fim desta tarefa os tempos antes e depois (por parte e total da rodada).

**Tempos (preencher ao fechar):**

| Medida | Antes | Depois |
|---|---|---|
| Job `tela` mais lento | 86 a 98 s nas 6 rodadas verdes (passo do pytest até 64 s, sempre na parte com `test_teto_de_20_vagas...`) | 79 a 106 s nas 3 rodadas verdes (43842794080, 43843129743, 43843400492) |
| Rodada inteira | 93 a 104 s (do primeiro job ao último) | 89 a 116 s (da criação da rodada ao fim, com a fila) |
| Falhas de tela em 3 rodadas | 0 nas 6 verdes; no histórico, 1 instável (`test_cloudflare_que_leva_a_url_com_fragmento_segue`, rodada 43822440143) | 0 nas 3 rodadas seguidas |

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

- [x] **Cache:** guardar `~/.cache/ms-playwright` com a chave pela versão do `playwright` no `uv.lock` (hoje 1.65.1). Com cache encontrado, nada mais roda: a imagem do runner já traz as bibliotecas do sistema (medido: 16 partes verdes sem `install-deps`). Sem cache, o `install --with-deps` de hoje.
- [x] **Action fixada** pelo hash do commit, com a versão em comentário, do mesmo jeito que as outras do `ci.yml` (`actions/cache`).
- [x] **Sem dependência nova** e sem teste de unidade (é `ci.yml`).
- [x] **Prova:** tempo do passo antes e depois em 2 rodadas na branch `lote/ci-cache` (a primeira enche o cache, a segunda o usa). Anotar na tabela abaixo.

| Medida | Antes | Depois |
|---|---|---|
| Passo de instalação do Chromium (mediana, máximo) | 18 s, 66 s | sem cache: 21 s, 34 s; com cache: 3 s, 5 s |

**Notas.** O cache do Actions vale por ref: um lote ou PR novo só acha o cache se ele estiver no escopo da `main`. Depois do próximo PR da `dev` para a `main`, rodar uma vez `gh workflow run ci.yml --ref main` para semear; cada lote que o lê o mantém vivo (o GitHub apaga cache sem acesso há 7 dias). Se um teste de tela falhar com "Host system is missing dependencies", a imagem do runner mudou: devolver o passo `uv run playwright install-deps chromium` com `if` no cache-hit.

### T295: navegador e tela mais rápidos nos testes
`depende_de: T292`

Três causas que a T292 deixou de fora.

**Arquivos:**
- modificar `tests/navegador/test_execucao_logada.py`, `tests/navegador/test_captcha_logado.py`, `tests/navegador/apoio/site_falso.py` e o `conftest.py` da pasta, se houver;
- modificar `tests/tela/test_buscar_agora.py` e `tests/tela/conftest.py`;
- modificar `registros/padroes.md` com a lição, se sair uma.

- [x] **(a) Playwright por sessão:** `async_playwright` sobe a cada teste em `tests/navegador` (`test_execucao_logada.py:100`, `test_captcha_logado.py:158`, `apoio/site_falso.py:654`), com 0,5 a 0,9 s só na desmontagem. Trocar por fixture de sessão por parte (`anyio_backend` de escopo de sessão), mantendo o contexto de cada teste isolado.
- [x] **(b) Relógio do navegador:** `tests/tela/test_buscar_agora.py:83` e `:119` esperam a pergunta de 2 em 2 s do painel. Usar `page.clock` (`install` e `fast_forward`) no lugar da espera real.
- [x] **(c) Corrida de porta (hipótese, não provada):** a falha antiga de "setup lento" do `test_form_sem_htmx_chega_numa_pagina_que_ja_mostra_o_andamento` pode ser a fixture `porta` de `tests/tela/conftest.py`, que fecha o socket antes de o uvicorn ligar (outro processo pode pegar a porta). Provar com teste ou descartar com medição; descartada, anotar aqui a medição.
- [x] **Ver falhar:** o que der para provar sem relógio, em `tests/unidade/` ou na própria tela (por exemplo, nenhum teste de `tests/tela` espera tempo real; conferido por varredura do texto). O resto fica com a medição do CI.
- [x] **Ver passar:** o arquivo de cada teste mexido e `uv run ruff check && uv run ruff format --check` aqui; o resto no CI.
- [x] **Critério:** tempos antes e depois, por parte, no CI (`--durations`), e 3 rodadas verdes seguidas.

**O que foi feito (2026-11-16):**

- (a) `tests/navegador/conftest.py` ganhou `anyio_backend` de sessão e a fixture `playwright_da_sessao` (um driver por processo, isto é, por parte no CI). `contexto_de_teste`, as `montagem` de `test_execucao_logada`, `test_janela_parada` e `test_login_manual`, o `lancar` de `test_captcha_logado` e `test_marca_de_instalacao` a recebem; cada teste segue com o seu navegador e o seu contexto. Fica de fora `test_capturar_logado_site.py`: é síncrono e o script roda o próprio laço. Os testes que trocam `execucao.async_playwright` ficam como estavam.
- A causa maior da desmontagem lenta não era o driver: era o `SiteFalso` (`tests/apoio/site_falso.py`), cujos dois servidores rodavam `serve_forever` na volta padrão de 0,5 s, e o `shutdown` espera uma volta inteira por servidor (0 a 1 s por teste). Volta de 0,02 s.
- (b) `test_buscar_agora.py`: `page.clock.install()` antes do `goto` (o tempo corre, para os timers do HTMX); depois de soltar a busca, o teste espera ela fechar no banco (`threading.Event`) e faz `page.clock.fast_forward(2000)`, que dispara a pergunta do `hx-trigger="every 2s"` (o HTMX agenda com `setTimeout`). Sem `timeout=10_000`.
- Guarda: `tests/unidade/test_testes_sem_espera.py` varre o texto de `tests/tela` (sem `wait_for_timeout`, dormida acima de 0,1 s nem `timeout=` acima dos 5 s do `expect`), de `tests/navegador` (só o `conftest.py` abre `async_playwright`) e prende a volta curta do `SiteFalso`.
- (c) **Descartada.** Medição nesta máquina (Linux 7.2, faixa 32768 a 60999): 3000 vezes `bind(0)`, fechar, 5 ms e o `bind` de novo com `SO_REUSEADDR` (como o `create_server` do asyncio), com 4 threads abrindo conexões sem parar (215 925 `connect()`): 0 falhas. O kernel escolhe porta ímpar no `bind(0)` (100% nas 3000) e par no `connect()` (95%; só passa às ímpares quando as pares se esgotam em `TIME_WAIT`), então porta de saída e porta da fixture não se cruzam com a carga do CI. E o sintoma não bate: porta tomada faz o uvicorn 0.54 dar `sys.exit` na thread (`server.py`, `except OSError`), e o `painel` falha na hora com "o painel não subiu" (`linha.is_alive()`), não por setup lento. Sem mudança em `tests/tela/conftest.py`.

**Tempos nesta máquina (um arquivo por vez, `--durations=0`, total do pytest):**

| Arquivo | Antes | Depois |
|---|---|---|
| `navegador/test_execucao_logada.py` (37) | 76,3 s (desmontagem 22,9 s) | 47,6 s (0,9 s) |
| `navegador/test_janela_parada.py` (25) | 50,2 s (11,0 s) | 34,4 s (0,7 s) |
| `navegador/test_captcha_logado.py` (29) | 46,2 s (18,3 s) | 23,9 s (1,0 s) |
| `navegador/test_detalhe_logado.py` (12) | 45,2 s (8,9 s) | 34,1 s (0,3 s) |
| `navegador/test_navegacao_logada.py` (26) | 40,5 s (14,6 s) | 20,4 s (0,9 s) |
| `navegador/test_login_manual.py` (5) | 8,7 s | 4,5 s |
| `navegador/test_capturar_logado_site.py` (4) | 6,1 s | 3,9 s |
| `tela/test_buscar_agora.py` (3) | 6,5 s (chamada 5,3 s) | 2,0 s (chamada 0,8 s) |

Só o Playwright de sessão, sem a volta curta do `SiteFalso`, tirava uns 0,15 s de preparação por teste (`test_captcha_logado.py`: 46,2 s para 45,0 s).

**No CI (`lote/testes-rapidos`, 16 partes de tela), 3 rodadas verdes seguidas:**

| Rodada | Tela: mínima / mediana / máxima por parte | Total da rodada |
|---|---|---|
| Antes (T292) | 79 a 106 s | 89 a 116 s |
| 1 (push; branch nova, sem o cache do Chromium) | 51 / 62 / 90 s | 102 s |
| 2 | 34 / 43 / 49 s | 71 s |
| 3 | 35 / 46 / 61 s | 67 s |

### T303: guarda do molde, `prefixos_login` com host e caminho
`depende_de: T298, T302` (T298 cria `tests/unidade/test_site_novo.py`; a T302 corrigiu o `LinkedIn`) · lição da T302

O navegador casa `prefixos_login` com `host + caminho` da URL (`casa_login`, `src/jobot/navegador/politica.py:50-53`: `(partes[1] + partes[2]).startswith(tuple(prefixos))`, com o host em minúsculas). O bug do `LinkedIn` era um prefixo só de caminho (`/login`), que nunca casava. O molde (`tests/apoio/molde_leitor.py:26`, `PREFIXOS_LOGIN`) e o `LinkedIn` (`src/jobot/nucleo/leitores/linkedin.py:132-135`) já seguem a regra; falta uma guarda para o próximo leitor.

**Arquivos:**
- modificar `tests/unidade/test_site_novo.py` (junto das outras guardas de site, perto de `test_todo_site_registrado_esta_completo`);
- modificar `docs/site-novo.md` e `docs/site-novo.en.md`, seção `#login` (uma linha: cada prefixo em `prefixos_login` é `host` + `caminho`, sem esquema, com o host em minúsculas e igual a um dos `hosts` do leitor), com o par bilíngue igual (`tests/unidade/test_documentos.py`).

**Interfaces:**
- `prefixos_fora_do_host(leitores: Iterable[LeitorComLogin]) -> list[str]` no próprio `test_site_novo.py`, no molde de `faltas`: uma linha por problema, com a chave do leitor e o prefixo, apontando para `{GUIA}#login`. Um prefixo está torto se: tem `://`; não tem `/` (falta o caminho); o trecho antes da primeira `/` não está em minúsculas ou não é igual a um dos `hosts` do leitor em minúsculas; ou `casa_login(f"https://{prefixo}?x=1", leitor.prefixos_login)` é falso (o contrato real, com a query ignorada). Leitor sem nenhum prefixo também é problema: o navegador nunca acharia a tela de login.

- [ ] **Testes que falham** em `tests/unidade/test_site_novo.py`:
  - `test_todo_prefixo_de_login_comeca_pelo_host`: `prefixos_fora_do_host(leitores()) == []` (o `LinkedIn` passa) e, com o molde (`MoldeLogado` de `tests/apoio/molde_leitor.py`), também `[]`.
  - `test_prefixo_so_de_caminho_reprova` (prova por mutação): uma cópia do leitor, `class SoCaminho(LinkedIn): prefixos_login = ("/login", "/checkpoint/")`, dá dois achados, cada um com `linkedin_logado` e o prefixo; a asserção é `len(achados) == 2`, não só "não vazio".
  - `test_prefixo_com_esquema_ou_host_de_outro_site_reprova`: `("https://www.linkedin.com/login",)` e `("www.outro.invalid/login",)` dão um achado cada; `("WWW.linkedin.com/login",)` (host em maiúsculas) também.
  - `test_ancora_da_guarda_de_prefixo_existe_no_guia`: a seção `#login` de `docs/site-novo.md` e de `docs/site-novo.en.md` existe e cita `prefixos_login` (a falta aponta para ela).
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_site_novo.py -q -k prefixo`; o vermelho é a asserção (a função recebe um stub que devolve `[]` para a mutação não ser pega), não erro de import.
- [ ] **Implementar** a função e a linha do guia nas duas línguas.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_site_novo.py tests/unidade/test_documentos.py -q`, `uv run ruff check && uv run ruff format --check`.

### T304: testes de tela do progresso sem esperar a pergunta de 2 s
`depende_de: T295`

`tests/tela/test_progresso.py` espera a pergunta de 2 em 2 s do painel em tempo real: `timeout=5_000` em `wait_for_function` e `expect` (linhas 83, 116, 133, 147, 164, 227, 290, 295 e 298), nos testes `test_largura_anda_entre_perguntas`, `test_barra_continua_entre_perguntas`, `test_regiao_viva_e_o_mesmo_no`, `test_espera_curta_nao_mostra` e `test_um_clique_acompanha_ate_o_fim`, dois deles dentro dos ajudantes `_esperar_valor_novo` (linha 75) e `_assentar` (linha 110, que espera a largura de entrada, "de 0 até o valor em 2 s", uma transição CSS). A T295 tirou o mesmo problema de `test_buscar_agora.py` (`_proxima_pergunta`, linha 72, com `page.clock.install()` e `fast_forward`); o guarda `test_tela_nao_espera_tempo_real` (`tests/unidade/test_testes_sem_espera.py:32`) deixa passar `timeout=5_000` porque só recusa o que passa de 5 s.

**Arquivos:**
- modificar `tests/tela/test_progresso.py`;
- modificar `tests/unidade/test_testes_sem_espera.py` e `registros/padroes-tela.md` (a lição, se sair uma).

**Interfaces:**
- Cada teste instala `page.clock.install()` antes do `goto` (o tempo corre, para os timers do HTMX), muda o estado no banco e chama `page.clock.fast_forward(2000)` para disparar a pergunta (`hx-trigger="every 2s"`, agendada com `setTimeout`), como em `test_buscar_agora.py`. Uma função `_proxima_pergunta(page)` no arquivo, sem `timeout=` maior que o padrão do `expect`.
- A transição CSS não obedece ao relógio da página: o teste espera o estado do DOM (atributo `aria-valuenow`, texto da região viva), nunca o fim da animação (lição `padroes-tela`). `test_largura_anda_entre_perguntas` mede a largura, que depende da transição: medir o alvo (`style`/valor final) com `prefers-reduced-motion` ligado ou esperar `transitionend` em vez de largura intermediária.

- [ ] **Teste que falha:** em `tests/unidade/test_testes_sem_espera.py`, `test_tela_nao_espera_a_pergunta_do_progresso`: nenhuma chamada de `tests/tela/test_progresso.py` tem `timeout=` com valor numérico (a asserção lista `arquivo:linha`); falha hoje com as nove linhas acima.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_testes_sem_espera.py -q -k progresso`.
- [ ] **Implementar** a troca nos cinco testes e nos ajudantes.
- [ ] **Ver passar:** o teste acima e `uv run ruff check && uv run ruff format --check`; a tela roda no CI (`lote/<nome>`), com `--durations` antes e depois (a parte do `test_progresso.py` perde os 2 a 5 s por teste).

### T305: acertos baixos do visual
`depende_de: T301, T264` · D157, D161

Resto das fotos da T258 e das revisões da T301 e da T264. Cada item vira um teste que falha antes (ou, onde é só decisão, uma linha no plano ou na D).

**Arquivos:**
- modificar `src/jobot/painel/static/js/app.js`, `src/jobot/painel/static/css/casca.css`, `src/jobot/painel/static/css/execucao.css`, `src/jobot/painel/templates/_encaixe.html`, `src/jobot/painel/templates/vagas/miolo.html`, `src/jobot/painel/templates/vagas/corpo.html`, `src/jobot/painel/templates/vagas/corpo_oob.html`, `src/jobot/painel/rotas/vagas.py`;
- modificar `tests/tela/test_vagas.py`, `tests/tela/test_menu_contexto.py`, `tests/integracao/test_rota_vagas.py`.

**Itens:**
- [x] **(a) Recarregar a lista inteira.** `recarregarLista` (`app.js:417`) pede só o endereço de agora (a página 1): o que veio por "Carregar mais" some e uma linha de lá não volta à vista (o comentário do código já diz). Recarregar até a página já carregada (pedir `pagina` com o número de páginas que o `#vagas-miolo` já mostra; o servidor limita em `_MAX_PAGINA`, `rotas/vagas.py:386`). Teste de tela `test_desfazer_depois_de_carregar_mais_mantem_as_linhas`: carrega a 2ª página, oculta e desfaz uma vaga da 2ª página; a linha volta e a lista continua com as duas páginas. Feito: `#mais-caixa` traz `data-paginas` (`vagas/proximo.html:3`); `recarregarLista` (`app.js:420`) pede `pagina=<data-paginas>` com `HX-Target: vagas-miolo`, e `vagas()` (`rotas/vagas.py:390,419`) monta o miolo juntando as páginas 1 até ela em `_contexto_pagina` (`rotas/vagas.py:277`); integração `test_lista_recarregada_traz_as_paginas_ja_carregadas`.
- [x] ~~**(b) O outro filtro de texto do `app.js` (perto da linha 165).** Conferir o que é: a região ao redor é o atalho `/` (`app.js:175-182`, foca `[data-busca]`) e o Esc que limpa a busca (`app.js:189`); procurar se há um segundo tratador de entrada de texto que repete essa lógica (`rtk grep -n 'data-busca\|campo.matches' src/jobot/painel/static/js/app.js`). Se duplica, juntar num só; se não, riscar o item com a linha da conferência. Teste de tela do que sobrar (Esc limpa a busca uma vez só).~~ Conferido: não há segundo tratador; os únicos de campo de texto são o atalho `/` (`app.js:175-183`) e o Esc da busca (`app.js:189`), que marca `preventDefault`; o Esc do detalhe (`app.js:317`) já ignora evento marcado. Fica o teste de tela `test_esc_limpa_a_busca_uma_vez_so`.
- [x] **(c) `vagas/corpo.html` e `vagas/corpo_oob.html`.** Conferido com `rtk grep`: ainda são renderizados por `_resposta` (`rotas/vagas.py:433-446`), que `mudar_status` (`rotas/vagas.py:506-515`, `POST /vagas/{id}/status`) devolve. Achar quem consome essa resposta no painel novo (o formulário do menu, `vagas/pagina.html:17`, e o `detalhe/corpo.html`, que já trazem o corpo do detalhe): se nenhum `hx-target` a usa, trocar a resposta por `204`/redirecionamento e apagar os dois templates, com `test_corpo_antigo_nao_existe` (arquivos ausentes e `grep` sem `vagas/corpo` em `src/`). Se algum a usa, riscar o item e dizer qual. Feito: nenhum `hx-target` usa a resposta (o form do menu, `vagas/pagina.html:17`, e o de `detalhe/corpo.html` são POST comum); `mudar_status` devolve o redirecionamento `303` para `voltar`, `_resposta` e `_unicas` saíram e os dois templates foram apagados.
- [x] **(d) "Abrir no site" só abre `http`/`https`.** O item do menu (`vagas/pagina.html:14`, `data-modelo-href="{site}"`, `data-requer="site"`) lê `data-site` da linha, que `vagas/linha.html:10` só emite quando `item.url` começa por `http://` ou `https://`; `tests/integracao/test_rota_vagas.py:350-354` prova que `javascript:` não aparece na lista nem no detalhe. Falta o teste do menu: `test_menu_sem_data_site_desabilita_abrir_no_site` (tela, `tests/tela/test_menu_contexto.py`): vaga com URL `javascript:alert(1)` ou `ftp://x` abre o menu com o item "Abrir no Site" desabilitado e sem navegar. Feito: o menu esconde (não desabilita) o item, como a HIG pede e o `data-requer` já faz (`app.js:573`); o teste exige o item ausente, o "Copiar link" também, as setas só nos itens que valem e a URL igual.
- [x] **(e) Menu de contexto sem typeahead.** Letra digitada não pula para o item que começa por ela (padrão do menu nativo do macOS; `app.js:530-690`). Implementar (a tecla é a 1ª letra do `textContent`, acumulando por 500 ms no relógio do navegador, com teste `test_letra_pula_para_o_item` em `tests/tela/test_menu_contexto.py`) ou registrar como fora de escopo numa linha do desenho (5.5), com o motivo. Feito: `itemPelaLetra` (`app.js:539`), chamado pelo keydown do menu; mesma letra de novo percorre os itens que começam por ela.
- [x] **(f) Cópia negada.** `copiarLink` (`app.js:645-660`) tem o ramo `catch` (`navigator.clipboard.writeText` recusado, ou sem `clipboard`) sem teste. `test_copiar_link_negado_mostra_nao_copiou` (tela): no `page.add_init_script`, `navigator.clipboard.writeText = () => Promise.reject(new Error("negado"))`; escolher "Copiar link" e esperar o texto de `data-nao-copiou` (`vagas.menu.nao_copiou`) na região viva, sem erro no console. Feito: teste de tela escrito; o código (`app.js:682`) já tratava.
- [x] **(g) Foco depois de `hidePopover()`.** `acertarCamada` (`app.js:280-287`) chama `no.hidePopover()` quando o detalhe passa de sobreposto para coluna; o navegador devolve o foco ao elemento anterior ao `showPopover`. O foco tem de ficar no detalhe. `test_foco_fica_no_detalhe_ao_alargar_a_janela` (tela): abrir o detalhe a 800 px, focar um controle dele, alargar para 1280 px; `document.activeElement` continua dentro de `#detalhe-vaga`. Feito: `acertarCamada` (`app.js:281-295`) guarda o elemento focado dentro do detalhe aberto antes do `hidePopover()` e o foca de novo (`preventScroll`); teste de tela escrito (roda no CI). Conferir no CI que ele falha na base (`bdfdf01`): popover `manual` talvez não devolva o foco; se passar lá, o trecho novo do `acertarCamada` sai e este item fecha com essa conclusão.
- [x] **(h) Detalhe sobreposto sem JavaScript.** Sem JS, o detalhe sobreposto fica preso ao `#vagas-miolo` (contenção do container; a camada `position: fixed` não escapa dele). Decidir: aceitar e documentar (uma linha na D157 e no plano da T301, item 2) ou corrigir (tirar a contenção do container no caminho sem `popover`). Teste de tela com `java_script_enabled=False` se corrigir. Feito (corrigido): a contenção não pode sair, pois é ela que dá as consultas `@container conteudo` do modo; no lugar, `@media (scripting: none)` deixa o sobreposto `sticky` no alto da coluna que rola, na grade por cima da lista (`vagas.css`, depois do bloco do sobreposto), com a altura da janela. Unidade `test_sobreposto_sem_js_acompanha_a_rolagem` (`tests/unidade/test_css.py`) e tela `test_sobreposto_sem_js_fica_a_vista_ao_rolar` (semeia 40 vagas a mais para a lista passar da janela e confere que rolou; conferir no CI que falha sem o bloco `scripting: none`, senão vale a opção de aceitar e documentar na D157); linha no item 2 da T301 do plano visual.
- [x] **(i) Teste de CSP sem vermelho no CI.** O teste das violações de CSP da T301 (item 10) só teve o vermelho aqui, não no CI. Aceito: registrar a linha no `registros/padroes-tela.md` ("violação de CSP aparece no console do Chromium da máquina; o CI pode não repetir; o teste prende a causa, `attributesToSettle` do `htmx-config`"). Feito: a linha vai para o `registros/padroes-tela.md` pela sessão principal.
- [x] **(j) Animação de entrada do sheet (T264).** Conferir no desenho 5.4 e 5.8 se o sheet de correção entra com animação: se pedir, 280 a 300 ms com `prefers-reduced-motion` respeitado e `test_sheet_sem_movimento_reduzido_nao_anima`; se não pedir, riscar o item com a linha do desenho que diz isso. Feito: o desenho 5.1 pede ("sheet e detalhe sobreposto em 280 a 300ms", `--mola-leve` só no sheet e no sobreposto; 5.4 e 5.8 não falam do movimento do sheet). `.sheet[open]` (`detalhe.css`) entra com opacidade e `translateY` em 280ms na `--mola-leve`, a partir do `@starting-style`; o bloco de movimento reduzido do `base.css` tira o transform e deixa o fundido de 120ms. Unidade `test_sheet_entra_com_a_mola_leve` e tela `test_sheet_sem_movimento_reduzido_nao_anima`.
- [x] **(k) Ícones do encaixe (D161).** `_encaixe.html:5` passa de `{"bom": "circle", "medio": "contrast", "fraco": "circle-dashed"}` para `{"bom": "circle-check", "medio": "contrast", "fraco": "circle"}`; a regra `[data-icone="circle-check"]` sai de `execucao.css:218` para `casca.css`, ao lado das de `circle` e `contrast` (linhas 171 e 172); nenhum SVG novo. Testes que mudam: `tests/integracao/test_rota_vagas.py:1765` (`esperado`) e `tests/tela/test_vagas.py:968` (a lista de ícones), com um teste novo `test_escala_do_encaixe_cresce` que lê o dicionário e exige a ordem fraco, médio, bom. Falha antes por asserção (o bom é `circle`). Se o dono escolher outra opção da D161, troca-se aqui. Feito com a opção recomendada da D161.
- [x] **(l) Programas em linhas, e o texto da T251 sobre `inteiro_da_url`.** Dois pontos achados com `rtk grep`: (1) o desenho (`docs/superpowers/specs/2026-11-15-visual-mac-design.md:202`) manda as páginas acompanhadas da aba Programas "com o mesmo estilo de linha" das vagas, e `vagas/miolo.html:117-135` ainda as mostra como `section.painel` com `ul.lista` (estilo de cartão antigo): trazer para o estilo de linha da lista, fora do `listbox` (`test_programas_fora_do_listbox`, `test_rota_vagas.py:1463`, continua valendo; novo `test_programas_com_estilo_de_linha` confere a classe da linha). (2) O texto da T251 (`docs/superpowers/plans/2026-11-16-visual-mac.md:308`) diz que "`inteiro_da_url` fica em `rotas/vagas.py`", mas ela mora em `painel/consultas.py:28` e `rotas/vagas.py:31` e `rotas/detalhe.py:29` a importam de lá: corrigir a frase na T251 e na T252. O que as fotos mostraram da aba Programas além disso: a localizar (procurei nos planos, no desenho e em `duvidas.md`; não há linha própria). Feito: (1) a seção vira `section.programas` com `ul.lista-linhas`, cada página um `<a class="linha">` para `/sites#site-<id>` (nome na `linha-1`; "mudou em" e a situação na `linha-2`), a diferença num `<details>` logo abaixo; a chave `vagas.programas.ver` ("Ver em Sites") saiu dos dois catálogos, pois a linha é o link; `test_aba_programas_mostra_mudou_em_e_leva_para_sites` (tela) segue a linha. (2) Frase corrigida na T251 (`2026-11-16-visual-mac.md:308`); a T252 (componente de progresso) não cita `inteiro_da_url` (conferido com `rtk grep`), nada a corrigir lá.

- [x] **Ver falhar:** o arquivo de teste de cada item que muda código, com a asserção do item; itens de documento (c quando só risca, h, i, j) conferem por `rtk grep` e anotam a conclusão aqui. Feito: `uv run pytest tests/integracao/test_rota_vagas.py -k "escala_do_encaixe or estilo_de_linha or encaixe_da_linha_e_icone"` saiu 1 com as três por asserção (`'circle-dashed' != 'circle'`, `data-icone="circle-check"` ausente, `section class="painel"` presente); `uv run pytest tests/unidade/test_css.py -k "mola_leve or sem_js_acompanha"` saiu 1 por asserção (`[] == ['opacity', 'transform']`, `0 == 1`). Os de tela (g, h, j) rodam no CI.
- [x] **Ver passar:** os arquivos de teste mexidos e `uv run ruff check && uv run ruff format --check`; a tela roda no CI. Feito: `test_rota_vagas.py`, `test_css.py`, `test_rota_sites.py`, `test_estaticos.py` e os de i18n passam; ruff check, ruff format --check e mypy nos `.py` tocados limpos.

### T306: guarda do sono sem `from time import sleep`, e fixture sombra no teste do Eureca
`depende_de: T295`

Dois buracos pequenos que a T295 deixou.

**Arquivos:**
- modificar `tests/unidade/test_testes_sem_espera.py` (`_nome`, linhas 22-26, e `test_tela_nao_espera_tempo_real`, linhas 32-51);
- modificar `tests/unidade/coletores/test_eureca.py` (linhas 33-39).

**Interfaces:**
- O guarda reconhece `time.sleep` e `asyncio.sleep` só pelo nome pontuado: `from time import sleep` e depois `sleep(5)` vira nome `sleep` e passa batido (idem `from asyncio import sleep` e `anyio.sleep`). Pegar também `sleep`, `anyio.sleep` e o apelido (`from time import sleep as dormir`: ler os `ImportFrom` do arquivo por AST e juntar os apelidos de `time.sleep`, `asyncio.sleep` e `anyio.sleep`).
- A fixture `fuso_de_sao_paulo` do `test_eureca.py` (linha 33, `autouse=True`) tem o mesmo nome da de `tests/conftest.py:84` (sem `autouse`, com a mesma tarefa de `monkeypatch.setenv("TZ", ...)` e `time.tzset()`): uma sombreia a outra e quem ler o arquivo não sabe qual vale. Remover a local e marcar o módulo com `pytestmark = pytest.mark.usefixtures("fuso_de_sao_paulo")`, ou renomear a local (`fuso_do_eureca`); a escolha é a que mantém o teste do Eureca com o fuso fixo em todos os seus testes.

- [ ] **Testes que falham** em `tests/unidade/test_testes_sem_espera.py`: `test_guarda_pega_sleep_importado` (um arquivo de tela sintético em `tmp_path` com `from time import sleep` e `sleep(5)`, passado à função de varredura, dá um achado `sleep`; a varredura vira função que recebe a lista de arquivos, para o teste real e o sintético usarem a mesma) e `test_guarda_pega_sleep_com_apelido`; `test_sem_fixture_sombra`: nenhum arquivo de `tests/unidade/coletores/` define fixture com o nome de uma fixture de `tests/conftest.py` (varredura por AST dos `FunctionDef` com `@pytest.fixture`).
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_testes_sem_espera.py -q -k "sleep or sombra"`; o vermelho é a asserção (achado ausente, ou `fuso_de_sao_paulo` duplicada).
- [ ] **Implementar** os dois ajustes.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_testes_sem_espera.py tests/unidade/coletores/test_eureca.py -q` e `uv run ruff check && uv run ruff format --check`.

### T307: confirmação sem JavaScript para as ações que apagam
`depende_de: T259, T261, T262` · D159, D163

Sem JavaScript (sem `HX-Request`), Apagar busca, Remover site e Esquecer logins agem direto, sem pergunta. Passam a levar a uma página de confirmação: `GET .../confirmar` com o mesmo texto do alerta, um botão que faz o `POST` de hoje e um Cancelar que volta. Com JavaScript nada muda: o alerta da T259 abre e o `POST` segue o mesmo caminho.

**Arquivos:**
- modificar `src/jobot/painel/templates/_alerta.html`, `src/jobot/painel/templates/buscas/lista.html`, `src/jobot/painel/templates/sites/lista.html`, `src/jobot/painel/templates/configuracoes/sites_com_login.html`;
- modificar as rotas de buscas, de sites e de configurações em `src/jobot/painel/rotas/`; novo template da página de confirmação; textos nos catálogos `pt` e `en`;
- modificar `tests/integracao/test_rota_buscas.py`, `tests/integracao/test_rota_sites.py`, `tests/integracao/test_rota_configuracoes.py`, `tests/tela/test_sites.py`.

**Interfaces:**
- O formulário de cada ação, lido sem JavaScript, aponta para a página de confirmação; o `POST` direto continua existindo e funcionando para o caminho com JavaScript (e para o botão da própria página de confirmação).
- Ação com a mesma regra de leitor de hoje: Esquecer logins sem leitor continua dando 404 também na página de confirmação.

- [x] **Testes que falham**, em `tests/integracao`, um por ação: `test_apagar_busca_sem_js_vai_para_confirmar`, `test_remover_site_sem_js_vai_para_confirmar`, `test_esquecer_logins_sem_js_vai_para_confirmar` (o formulário sem JavaScript aponta para `.../confirmar`, a página mostra o texto do alerta, o botão e o Cancelar, e `GET` nada apaga) e, para cada uma, `test_<acao>_post_direto_continua` (o `POST` de hoje apaga como antes). Em `tests/tela`, `test_remover_site_sem_js_pede_confirmacao` com `java_script_enabled=False`: clicar em Remover abre a página de confirmação e só o botão dela remove. O teste `test_apagar_sem_js_continua` (`tests/integracao/test_rota_buscas.py:373`) passa a provar o novo caminho.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_buscas.py tests/integracao/test_rota_sites.py tests/integracao/test_rota_configuracoes.py -q -k "confirmar or post_direto"`; o vermelho é a asserção (o formulário aponta para o `POST`), não erro de import.
- [x] **Implementar** as três páginas de confirmação (uma macro ou um template só), os textos nas duas línguas e a troca do destino do formulário sem JavaScript.
- [x] **Ver passar:** os mesmos arquivos de teste e `uv run ruff check && uv run ruff format --check`; a tela roda no CI (o `test_remover_site_sem_js_pede_confirmacao` foi escrito e não rodou na máquina).

### T308: grupo de Configurações guardado que sumiu
`depende_de: T262` · D164

`GET /configuracoes/{grupo}` de um grupo conhecido que hoje não existe (`sites-com-login` ou `ferramentas` sem leitor) redireciona com 303 para `/configuracoes/geral`, em vez de dar 404; grupo desconhecido continua dando 404. O JavaScript não precisa mudar para isso. Também: `itemConfiguracoes` em `app.js` é buscado uma vez; depois de `htmx:historyRestore` o nó fica solto, então o nó passa a ser buscado na hora do atalho.

**Arquivos:**
- modificar `src/jobot/painel/rotas/configuracoes.py`, `src/jobot/painel/static/js/app.js`;
- modificar `tests/integracao/test_rota_configuracoes.py`, `tests/tela/` (o arquivo do atalho de Configurações).

**Interfaces:**
- A rota distingue "grupo conhecido sem leitor" (303 para `/configuracoes/geral`) de "grupo desconhecido" (404), com a lista de grupos que já existe no código.

- [x] **Testes que falham:** em `tests/integracao/test_rota_configuracoes.py`, `test_grupo_sumido_vai_para_geral` (303 e `Location: /configuracoes/geral`) e `test_grupo_desconhecido_continua_404`; em `tests/tela`, `test_atalho_de_configuracoes_depois_de_voltar_no_historico` (abre Configurações, sai, volta pelo histórico e o atalho ainda leva ao grupo guardado).
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_configuracoes.py -q -k grupo`; o vermelho é a asserção (hoje o grupo sumido dá 404).
- [x] **Implementar** o redirecionamento e a busca do nó na hora do atalho.
- [x] **Ver passar:** os mesmos testes e `uv run ruff check && uv run ruff format --check`; a tela roda no CI.

### T309: lista agrupada única e regras de ícone só no `casca.css`
`depende_de: T260, T261, T262`

`buscas.css` (`.lista-buscas`), `fontes.css` (`.lista-fontes`), `sites.css` (`.lista-sites`) e as listas de Empresas e Sugeridas repetem umas dez linhas da lista agrupada. Criar `.lista-agrupada` em `base.css`, usar nos templates e apagar as cópias. As regras `[data-icone="circle-check"]` e `[data-icone="clock"]` estão em `fontes.css` e em `execucao.css`: ficam só em `casca.css`, ao lado das de `circle` e `contrast` (junto com o item (k) da T305). Na macro `caixa()` de `configuracoes/_interruptor.html`, o parâmetro `valor` não tem chamador: remover.

**Arquivos:**
- modificar `src/jobot/painel/static/css/base.css`, `buscas.css`, `fontes.css`, `sites.css`, `execucao.css`, `casca.css`, e os templates que usam as listas (Buscas, Fontes, Sites, Empresas, Sugeridas);
- modificar `src/jobot/painel/templates/configuracoes/_interruptor.html`;
- modificar `tests/unidade/test_css.py`.

**Interfaces:**
- `.lista-agrupada` é a única definição do bloco repetido; cada lista só traz o que é próprio dela.
- Cada valor de `data-icone` tem regra num arquivo só.

- [x] **Testes que falham** em `tests/unidade/test_css.py`: `test_lista_agrupada_definida_uma_vez` (o seletor da lista agrupada aparece num arquivo só) e `test_regra_de_icone_uma_vez` (cada `data-icone` tem regra num arquivo só; hoje `circle-check` e `clock` aparecem em dois). Feito: o primeiro acha o bloco pela assinatura (`box-shadow: inset 0 0 0 0.5px var(--separador)` com `list-style: none`) e exige só `.lista-agrupada` no `base.css`, e confere a classe nas cinco `<ul>`; o segundo junta, por `data-icone`, os arquivos com regra de `--icone` e exige um só, com `circle`, `contrast`, `circle-check`, `circle-x` e `clock` no `casca.css`. O `circle-x` também estava em dois (`casca.css` e `execucao.css`).
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_css.py -q -k "agrupada or icone"`; o vermelho é a asserção, não erro de coleta. Feito: saiu 1, 2 falhas por asserção (`('buscas.css', '.lista-buscas') != ('base.css', '.lista-agrupada')`; `repetidos` com `circle-check`, `circle-x` e `clock`). O caminho dos templates foi provado por mutação numa cópia (a `<ul>` de Sugeridas de volta a `lista-buscas` falha).
- [x] **Implementar** a junção, a remoção das cópias e a do parâmetro `valor` da macro `caixa()`. Feito: `.lista-agrupada` no `base.css` (depois do `.painel`), as cinco `<ul>` usam a classe e mantêm o `id`; `.lista-buscas`, `.lista-fontes` e `.lista-sites` saíram; as regras de ícone de `fontes.css` e `execucao.css` saíram e o `clock` entrou no `casca.css`, ao lado do `circle-x`; a macro `caixa()` perdeu `valor`. Os quatro testes de integração que liam a classe antiga da `<ul>` passaram a ler `lista-agrupada`.
- [x] **Ver passar:** `uv run pytest tests/unidade/test_css.py -q` e `uv run ruff check && uv run ruff format --check`; as telas de Buscas, Fontes, Sites e Empresas rodam no CI para conferir que nada mudou no visual. Feito: `test_css.py` 43 passaram; `test_rota_{fontes,empresas,sites,sugeridas,configuracoes,buscas}.py` 407 passaram; ruff limpo. As telas rodam no CI.
