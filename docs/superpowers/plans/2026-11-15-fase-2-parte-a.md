# Fase 2, Parte A (navegação com login, sem site real): plano de implementação

> Cada tarefa roda em worktree próprio, com um revisor diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido (erro de import, de coleta ou zero testes não vale). Regra única de stub para módulo novo: a função existe com a assinatura final e devolve um valor errado, sem efeito (`estado_do_escopo` → `Desfecho("ok", None, ())`; predicados → `False`; consultas → `None` ou `[]`; `ambiente_da_tela` → `{}`; `executar_login` → `None` sem abrir execução). Teste que espera exceção falha com `DID NOT RAISE`. Quem implementa não roda `git`: commits e junção ficam com a sessão. Leia `registros/padroes.md` antes de cada tarefa. Os passos usam caixas (`- [ ]`).

**Objetivo:** pôr na `dev` toda a infraestrutura da leitura de sites com login (navegador visível com perfil próprio, contrato do leitor, execução `login` nos horários, cola com o 2Captcha, grupo "Sites com login" e ferramenta de captura), testada só contra sites falsos em `127.0.0.1`, sem nenhum leitor registrado e, por isso, sem nada visível para quem usa (D132.23).

**Arquitetura:** a leitura das páginas é pura, em `nucleo/leitores/` (um protocolo, dataclasses e a precedência do estado do escopo). O pacote novo `navegador/` é o único que importa `playwright`: abre o Chrome (ou o Chromium do Playwright) com o perfil `<dados>/navegador/`, navega com política e tetos, e grava pelas funções de `banco` que a busca já usa. A agenda só decide a hora (`login_vencido`); o `cli/servir.py` injeta a tarefa `login` no laço pela entrada de produção do `navegador`, e o painel mostra o grupo só quando há leitor.

**Stack:** Python ≥ 3.14, Playwright 1.65.1 (API assíncrona, `playwright.async_api`), FastAPI + Jinja2 + HTMX, SQLite, pytest com `RelogioFalso`, `httpx.MockTransport` e marcador `tela` para tudo que abre navegador.

**Desenho:** `docs/superpowers/specs/2026-11-15-fase-2-design.md`, seções 5 (A1 a A11), 8, 9 e 12. Decisões: D132.1 a D132.57; as escolhas deste plano estão na D133 (`duvidas.md`).

## Restrições globais

- Playwright `==1.65.1` passa para `[project] dependencies`; `pytest-playwright==0.10.0` fica no `dev`. Nenhum pacote novo.
- O joBot não baixa navegador na Parte A: Chrome instalado (`channel="chrome"`) ou o Chromium que o Playwright já tem; sem os dois, `saude.sem_navegador`.
- Camadas: `navegador` importa `nucleo`, `banco`, `sistema`; nunca `painel`, `agenda`, `cli`. Só `navegador` importa `playwright` (em `src/` e em `scripts/`); `cli` e `painel` chegam ao navegador só por `jobot.navegador`. `jobot.nucleo.captcha` só em `navegador`, `painel` e no próprio módulo. `nucleo`, `banco`, `agenda`, `sistema` não importam `jobot.navegador`.
- Diagrama de camadas: `tests/unidade/test_arquitetura.py:176-190` exige um nó por pacote e uma seta por import entre pacotes no flowchart `%% camadas` de `wiki/Arquitetura.md:43-65` e `wiki/Architecture.md`. A T196 põe o nó `navegador`; cada tarefa que cria um import novo entre pacotes põe a sua seta nas duas páginas e as lista em **Arquivos**.
- Nunca digitar senha, preencher formulário, clicar, enviar, nem mexer na conta. Única escrita na página: o token no campo de resposta do widget e a chamada do `data-callback` declarado, só em página de desafio que não é login.
- Lista permitida do Playwright conferida por AST (seção A7 do desenho) em `src/jobot/navegador/` e em `scripts/capturar_logado.py`: fora de `navegador/js.py`, nada além de `launch_persistent_context`, `new_page`, `pages`, `goto`, `wait_for_load_state`, `content`, `url`, `title`, `close`, `frames`, `on`/`once` (só `response`, `request`, `close`), `locator`, `get_attribute`, `inner_text`, `count`, `all`, `headers`, `status`, `text`, `body`. Só `js.py` chama `evaluate`, com três scripts literais.
- Sem `headless` em produção, sem argumento extra de linha de comando, sem `--remote-debugging-port`, sem `connect_over_cdp`, sem stealth, sem trocar user agent.
- Perfil `<dados>/navegador/`, 0700, nunca no log, em exportação nem na cópia antes de migrar.
- Testes de navegador só com sites falsos em `127.0.0.1` e `::1`, lançador injetado sem tela e rota do teste que recusa o resto e conta os recusados; `route` e `fulfill` só em `tests/`.
- Migrações novas: `0007_execucao_login.sql` e `0008_fonte_com_login.sql`, sobre a `dev` que já tem a 0006. Migração aplicada nunca é editada. O `migrar` desliga `foreign_keys` (`banco/migrar.py:71`), então o `DROP TABLE execucao` da 0007 não apaga filhos.
- Gravação por `INSERT ... ON CONFLICT DO UPDATE`; nada apagado; `ligada` só no `INSERT`.
- Texto novo do painel em `i18n/pt` e `i18n/en`; ADRs e `duvidas.md` só em português. README, privacidade, CHANGELOG e `CLAUDE.md` não mudam na Parte A (D132.13); a wiki muda só em `Arquitetura.md` e `Architecture.md`, por causa do teste do diagrama (exceção registrada na D133).
- Hora local por `agora.astimezone()`; testes com `TZ` fixo fora de UTC.
- Nesta máquina: só o arquivo de teste da tarefa e `uv run ruff check && uv run ruff format --check`. Arquivo `tela` da tarefa roda com o Chromium já instalado; suíte inteira, `-m tela` inteiro e `uv run mypy` no CI da branch `lote/<nome>`.
- Desvios: R1 a R3 quem implementa resolve e lista; R4 (arquitetura, dependência, esquema ou contrato público fora do desenho) vai ao `duvidas.md` com opções e recomendação.

## Valores para confirmar, num lugar só

Os números que dependem de D132 "pergunta ao dono" moram em dois módulos e em nenhum outro lugar; os testes os leem de lá.

- `src/jobot/navegador/limites.py`: `MAX_LISTA = 10`, `MAX_VAGA = 20` (D132.19, D132.32; a `url_entrada` conta no `MAX_LISTA`, E16); `ESPERA_MIN_S = 3.0`, `ESPERA_MAX_S = 8.0` (D132.19); `ESPERA_CLOUDFLARE_S = 30` (D132.30, D132.44); `ESPERA_TOKEN_S = 30` (D132.31); `JANELA_PARADA_S = 900` (D132.26); `PRAZO_LOGIN_MANUAL_S = 600` (D132.52); `MAX_RESPOSTA_BYTES = 5 * 1024 * 1024`, `MAX_RESPOSTAS = 50` (D132.54).
- `src/jobot/agenda/login.py`: `JANELA_HORARIO = timedelta(minutes=15)`, `INTERVALO_MINIMO = timedelta(hours=4)` (D132.6, D132.25).

## Escolhas deste plano (D133, para confirmar)

| # | Escolha | Teste |
|---|---|---|
| E1 | API assíncrona do Playwright: o `serve` é asyncio e a tarefa `login` roda no laço. | `test_lancador_de_producao_abre_visivel` |
| E2 | Registro de leitores explícito: `LEITORES: tuple[LeitorComLogin, ...] = ()` em `nucleo/leitores/registro.py` e `leitores()`; a Parte B acrescenta. Painel lê `getattr(app.state, "leitores", leitores())`; testes põem o leitor falso ali. | `test_registro_comeca_vazio`, `test_sem_leitor_a_aba_nao_aparece` |
| E3 | `respostas` são regex casadas por `re.fullmatch` com `host + caminho` (sem query); `prefixos_login` casam por `startswith` com `host + caminho`. | `test_captura_so_respostas_que_casam` |
| E4 | `estado_do_escopo` devolve `Desfecho(estado, motivo, vagas)`: as vagas a gravar saem junto, e `motivo` é `None` no `ok`. | `test_parada_com_formato_mudou_nao_grava_vaga` |
| E5 | O batimento assíncrono movido chama-se `manter_batimento`; a consulta extraída, `candidatas_a_detalhe`; a da última leitura, `inicio_da_ultima_leitura_login`. | testes da T199, T200, T204 |
| E6 | `Estado` do agendador ganha `login() -> Login | None` (`None` = nenhum site ligado); `o_que_roda` ganha `login: Login | None = None`, só por nome, e põe `"login"` por último. `_EstadoDoBanco.login()` nasce junto (T206). | `test_o_que_roda_sem_login_fica_igual` |
| E7 | `login_horarios` validado por `horarios_validos(valor) -> tuple[time, ...]` em `nucleo/horarios.py`; valor torto no banco vale o padrão, com log. Campo do painel: texto `09:00, 18:00`. | `test_horarios_tortos_no_banco_valem_o_padrao` |
| E8 | Chrome achado por `/opt/google/chrome/chrome` (o caminho do canal `chrome` no Linux; conferir na 1.65.1); Chromium por `chromium.executable_path` existir, o que sobe o driver: o `serve` calcula uma vez ao subir, só com leitor registrado, e guarda em `app.state.navegador_instalado`. | `test_navegador_instalado`, `test_aba_nao_sobe_o_driver` |
| E9 | Desafio gerenciado do Cloudflare: título começa com `Just a moment` ou há `script[src*="/cdn-cgi/challenge-platform/"]`. Heurística conferida só no site falso; rever na Parte B com página real. | `test_cloudflare_que_sai_sozinho_segue` |
| E10 | "Mesmo desafio que voltou" = mesmo tipo e mesma `sitekey`, no mesmo site, depois de um token aceito na mesma execução. | `test_desafio_que_volta_e_bloqueio` |
| E11 | Página assentou: `wait_for_load_state("load")` e depois `"networkidle"` com `timeout=10_000`, ignorando o estouro deste último. | `test_lista_carregada_pela_pagina_e_capturada` |
| E12 | Pessoa fechou o navegador: o evento `close` do contexto marca `NavegadorFechado(Exception)`; `executar_login` o pega, desfaz a transação e chama `interromper_execucao(..., parada="fechado")`, sem relançar: é ação normal da pessoa, e o `rodar` do agendador (`agenda/agendador.py:81-87`) a gravaria no log como traceback. Cancelamento (Ctrl+C, fim do `serve`) fecha o contexto no `finally` e sobe. | `test_fechar_o_navegador_interrompe_com_fechado`, `test_cancelar_a_leitura_fecha_o_navegador` |
| E13 | A constante `NOME = "2captcha"` (`painel/rotas/servicos.py:31`, importada em `painel/rotas/configuracoes.py:34` e usada em `:267`) passa para `banco/captcha.py` com o nome `NOME_NO_COFRE`; o painel importa de lá (o `navegador` não importa `painel`). | `test_nome_no_cofre_definido_uma_vez` |
| E14 | `_segundos_retry_after` de `nucleo/http.py` vira público (`segundos_retry_after`), com o chamador `http.py:424` atualizado; o navegador aplica o mesmo `MAX_RETRY_AFTER_S` (`http.py:20`). | `test_429_espera_o_retry_after`, `test_retry_after_acima_do_teto_e_no_limite` |
| E15 | Testes de navegador ficam em `tests/navegador/` com `pytestmark = pytest.mark.tela`; servidor e leitor falsos em `tests/apoio/site_falso.py`. | toda a pasta |
| E16 | A `url_entrada` conta como uma das `MAX_LISTA` navegações de lista: o total por site fica em 30 (D132.19). A espera de 3 a 8 s vale antes de toda navegação depois da primeira, inclusive as de vaga. | `test_teto_de_10_paginas_de_lista_por_site`, `test_espera_antes_das_paginas_de_vaga` |
| E17 | O `navegador` expõe a entrada de produção `dependencias_de_producao(dados, env)`, gerenciador de contexto assíncrono que abre e fecha o `async_playwright()` sozinho; `cli`, `painel` e o script de captura só a usam. | `test_so_navegador_importa_playwright` |

## Foco da revisão

| # | Entrada ou condição | O que a pessoa espera | Teste | Tarefa |
|---|---|---|---|---|
| RF1 | `<dados>/navegador` é um symlink (cópia de outra máquina, link feito à mão) | `preparar_pasta` não muda o alvo; "Esquecer logins" não apaga nada fora da pasta de dados | `test_preparar_pasta_nao_segue_navegador_symlink`, `test_esquecer_com_navegador_symlink_nao_apaga_o_alvo` | T198, T219 |
| RF2 | `Default/Preferences` é symlink, não é UTF-8 ou é JSON que não é objeto | Não segue o link; reescreve só as três chaves; nunca quebra a abertura | `test_preferencias_symlink_e_recusado`, `test_preferencias_nao_utf8_ou_lista_reescreve` | T208 |
| RF3 | `login_horarios` torto gravado no banco (edição manual, versão futura) | O laço segue com 09:00 e 18:00 e loga; nada de agenda parada | `test_horarios_tortos_no_banco_valem_o_padrao` | T206 |
| RF4 | Clique duplo em "Buscar agora" | Uma leitura com login só | `test_buscar_agora_duas_vezes_dispara_uma_leitura` | T215 |
| RF5 | O `serve` fecha (Ctrl+C) no meio de uma leitura | O Chrome fecha, a execução fica `interrompida` com `fechado`, nenhum processo do navegador sobra | `test_cancelar_a_leitura_fecha_o_navegador` | T213 |

## Ordem

| Onda | Tarefas | Por quê |
|---|---|---|
| 1 | T196, T198, T205, T210 | arquivos separados (T196 e T210 não se cruzam na wiki: T210 não cria import entre pacotes) |
| 2 | T197, T199, T201, T207 | T199 e T201 mexem em `banco/execucoes.py` em pontos diferentes (junte T199 antes) |
| 3 | T200, T202, T204, T208, T209 | T200 depois da T199; T202 e T204 depois da T201; T208 e T209 põem setas na wiki (junte T208 antes) |
| 4 | T203, T206, T211 | |
| 5 | T212 | site falso, base das seguintes |
| 6 | T213 | |
| 7 | T214, T215, T220 | T215 põe a seta `cli --> navegador` |
| 8 | T216, T218 | T216 depois da T214 (mesmo `navegador/execucao.py`); T216 e T218 tocam `configuracoes.py` (a T216 só no import): junte T216 antes |
| 9 | T217, T219 | |
| 10 | REG24 | |

A A11 do desenho põe o `serve` antes do navegador; aqui a T215 vem depois da T213, porque a tarefa `login` do mapa chama `executar_login`. A parte pura da agenda e o `_EstadoDoBanco.login()` (T206) continuam na onda 4.

---

### T196: Playwright para execução, pacote `navegador` e regras de camadas
`depende_de: —` · D132.1, D132.4

**Arquivos:** modificar `pyproject.toml`, `uv.lock`, `tests/unidade/test_camadas.py`, `wiki/Arquitetura.md` e `wiki/Architecture.md` (nó `navegador["navegador<br/>navegador com login (Playwright)"]` no flowchart `%% camadas`, sem seta ainda). Criar `src/jobot/navegador/__init__.py` (docstring só).

**Interfaces:** produz `PROIBIDOS_NO_NUCLEO` com `playwright` e `jobot.navegador`; o detector `_ruins` não muda.

- [x] **Teste que falha** (`tests/unidade/test_camadas.py`):
  - `test_playwright_e_dependencia_de_execucao` (o vermelho da tarefa): `tomllib` do `pyproject.toml`; `"playwright==1.65.1" in project.dependencies` e fora de `dependency-groups.dev`; `"pytest-playwright==0.10.0"` segue no `dev`.
  - Guardas, verdes desde o início (ninguém importa `playwright` ainda); quem prova que elas pegam o erro são os detectores abaixo: `test_so_navegador_importa_playwright` (todo `src/jobot/*` menos `navegador`, e todo `scripts/*.py`, com `_ruins(..., ("playwright",)) == []`); `test_captcha_so_em_navegador_e_painel` (troca o `test_captcha_so_fora_das_fontes_publicas` por lista permitida; hoje só `painel/rotas/configuracoes.py` e `servicos.py` importam); `test_camadas_de_baixo_nao_importam_navegador` (`nucleo`, `banco`, `agenda`, `sistema`); `test_navegador_nao_importa_painel_agenda_cli`.
  - Um teste do detector por regra, com pasta temporária: `test_detector_acha_playwright_fora_do_navegador` (um em `src`, um em `scripts`), `test_detector_acha_captcha_fora_da_lista`, `test_detector_acha_navegador_em_banco`, `test_detector_acha_painel_no_navegador`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_camadas.py::test_playwright_e_dependencia_de_execucao -q`.
- [x] **Implementar:** mover a linha no `pyproject.toml`, `uv lock`, `uv sync --locked`; regras novas no teste; nó na wiki.
- [x] **Ver passar:** `uv run pytest tests/unidade/test_camadas.py tests/unidade/test_arquitetura.py -q` e ruff.

**Pronto quando:** `uv sync --locked` limpo, as regras com detector e `test_camadas_tem_todos_os_pacotes` verde nas duas línguas.

### T197: Contrato do leitor e estado do escopo
`depende_de: —` · D132.4, D132.5, D132.20, D132.33, D132.34, D132.36, D132.53

**Arquivos:** criar `src/jobot/nucleo/leitores/__init__.py`, `base.py`, `estado.py`, `registro.py`; `tests/unidade/test_leitores_estado.py`.

**Interfaces (produz):**
- `base.py`: `@dataclass(frozen=True)` `RespostaCapturada(url: str, status: int, tipo: str, texto: str)`, `Captura(url: str, status: int, html: str, respostas: tuple[RespostaCapturada, ...])`, `EscopoLogado(id: str, url: str)`, `Leitura(vagas: tuple[VagaColetada, ...], pulados: int, formato_mudou: bool)`; `ParadaLogin = Literal["precisa_login", "bloqueio", "captcha", "no_limite"]`; `class LeitorComLogin(Protocol)` com `chave`, `nome`, `hosts`, `url_login`, `url_entrada`, `prefixos_login`, `respostas`, `campos_conta`, `rolar: bool`, `lista_tem_descricao: bool`, `escopos(ctx: ContextoColeta) -> Sequence[EscopoLogado]`, `e_login(captura: Captura) -> bool`, `pagina_logada(html: str, url: str) -> bool`, `pagina_bloqueada(html: str, url: str) -> bool`, `proxima(captura: Captura) -> str | None`, `ler(captura: Captura, escopo: EscopoLogado) -> Leitura`, `detalhar(captura: Captura, vaga: VagaColetada) -> VagaColetada | None`.
- `estado.py`: `ORDEM_DAS_PARADAS = ("precisa_login", "bloqueio", "captcha", "no_limite")`; `parada_mais_forte(a: ParadaLogin | None, b: ParadaLogin | None) -> ParadaLogin | None`; `Desfecho(estado: Estado, motivo: str | None, vagas: tuple[VagaColetada, ...])` (`Estado` de `nucleo/coletores/base.py`); `estado_do_escopo(leituras: Sequence[Leitura], *, parada: ParadaLogin | None, cortada: bool, tres_ok_com_vagas: bool) -> Desfecho`.
- `registro.py`: `LEITORES: tuple[LeitorComLogin, ...] = ()`, `leitores() -> tuple[LeitorComLogin, ...]` (recusa chave repetida e chave sem o sufixo `_logado` com `ValueError`).

- [x] **Teste que falha**, um por caso da precedência (A4), com `v1` de `VagaColetada` de teste:
  - `test_parada_sozinha_da_falhou_com_a_chave_dela[precisa_login|bloqueio|captcha]` → `("falhou", "saude.<parada>", (v1,))`; `test_no_limite_da_no_limite_com_parou_429` → `("no_limite", "saude.parou_429", (v1,))`.
  - `test_parada_mais_forte[...]`: os três pares vizinhos da ordem e `None` com qualquer uma.
  - `test_parada_com_formato_mudou_nao_grava_vaga`: estado da parada, `vagas == ()`.
  - `test_formato_mudou_numa_pagina_e_outra_boa` → `("falhou", "saude.formato_mudou", ())`.
  - `test_so_itens_tortos_e_formato_mudou`: `Leitura((), 3, True)` → `falhou`.
  - `test_cortada_com_pagina_lida_e_parcial` (com `pulados=1`) → `("parcial", "saude.listagem_incompleta", (v1,))`.
  - `test_cortada_sem_pagina_lida_e_falhou`: `leituras=()` → `("falhou", "saude.listagem_incompleta", ())`.
  - `test_item_torto_ate_o_fim_e_parcial` → `("parcial", "saude.formato_mudou", (v1,))`.
  - `test_vazia_com_historico_e_zero_inesperado` → `("parcial", "saude.zero_inesperado", ())`; `test_vazia_sem_historico_e_ok` → `("ok", None, ())`; `test_lista_com_vagas_e_ok`.
  - `test_registro_comeca_vazio`: `leitores() == ()`; `test_registro_recusa_chave_sem_sufixo`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_leitores_estado.py -q` sobre o stub.
- [x] **Implementar** `estado_do_escopo` na ordem da A4, `parada_mais_forte` e o registro.
- [x] **Ver passar** e ruff.

**Pronto quando:** os casos passam e `nucleo/leitores` não importa nada de fora do `nucleo` (T196 prende).

### T198: `preparar_pasta` não desce em `navegador/`
`depende_de: —` · D132.3, D132.22

**Arquivos:** modificar `src/jobot/sistema/pastas.py` (`preparar_pasta`); teste em `tests/unidade/test_pastas.py`.

**Interfaces:** produz `PASTA_NAVEGADOR = "navegador"` em `sistema/pastas.py`; `preparar_pasta(p: Path) -> None` sem mudança de assinatura.

- [x] **Teste que falha:**
  - `test_preparar_pasta_nao_desce_em_navegador`: `navegador/Default/Cookies` com 0644 e `navegador/` com 0755; depois, o arquivo segue 0644 e a pasta vira 0700.
  - `test_preparar_pasta_nao_segue_navegador_symlink` (RF1): `navegador` é symlink para uma pasta fora com 0755; depois, o alvo segue 0755.
  - Controle: um arquivo 0644 em `outra/` vira 0600.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_pastas.py::test_preparar_pasta_nao_desce_em_navegador -q`.
- [x] **Implementar:** no `os.walk`, fechar `navegador` em 0700 por `_fechar` e tirá-lo de `pastas` (só no primeiro nível).
- [x] **Ver passar** os três e ruff.

### T199: Ajudantes de execução passam para `banco`
`depende_de: —` · D132.39

**Arquivos:** modificar `src/jobot/banco/execucoes.py` (recebe), `src/jobot/agenda/execucao.py` (perde e importa), `src/jobot/agenda/descoberta.py`, `src/jobot/agenda/paginas.py`, `src/jobot/cli/buscar.py`, `tests/integracao/test_motivo_da_parada.py` e `tests/unidade/test_descoberta.py:455` (o `monkeypatch.setattr(descoberta, "bater", ...)` passa a `"manter_batimento"`). Antes, `grep -rn "parada_de\|interromper\|bater" src tests scripts` para achar outro alvo de `monkeypatch` por nome.

**Interfaces (produz, em `banco/execucoes.py`):** `parada_de(erro: BaseException) -> Parada`; `interromper(con, execucao_id: int, erro: BaseException, agora: datetime) -> None`; `async def manter_batimento(con, execucao_id: int, relogio: Relogio) -> None` (o `bater` síncrono fica com o nome dele).

- [x] **Teste que falha** (`tests/integracao/test_ajudantes_de_execucao.py`):
  - `test_ajudantes_moram_no_banco[parada_de|interromper|manter_batimento]`: `assert hasattr(execucoes, nome)` (o vermelho; sem import no topo, que daria erro de coleta).
  - `test_parada_de_no_banco`: `execucoes.parada_de(asyncio.CancelledError()) == "fechado"`, `sqlite3.OperationalError()` → `"banco"`, `ValueError()` → `"erro"`.
  - `test_agenda_nao_tem_copia_dos_ajudantes`: AST de `src/jobot/agenda/*.py` sem `def parada_de`, `def interromper`, `def bater`, `def manter_batimento`.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_ajudantes_de_execucao.py -q`.
- [x] **Implementar:** mover sem mudar corpo nem log; a agenda e o `cli` importam de `banco`.
- [x] **Ver passar:** o arquivo novo, `tests/integracao/test_motivo_da_parada.py`, `tests/integracao/test_execucao.py` e `tests/unidade/test_descoberta.py`.

### T200: Candidatas a detalhe passam para `banco`
`depende_de: T199` · D132.32, D132.39 (para confirmar: D132.32)

**Arquivos:** modificar `src/jobot/banco/execucoes.py`, `src/jobot/agenda/execucao.py` (`_enriquecer`); teste em `tests/integracao/test_candidatas_a_detalhe.py`.

**Interfaces (produz):** `Candidata(ocorrencia_id: int, fonte: str, escopo: str, vaga: VagaColetada)` (frozen); `candidatas_a_detalhe(con, fontes: Sequence[str], inicio: datetime, relogio: Relogio) -> list[Candidata]`: o SQL de hoje (ocorrência aberta, vaga vista desde `inicio - JANELA_DETALHE`, descrição vazia na ocorrência, mais novas primeiro, `o.id` de desempate), o `strip()` da descrição e o corte por `HistoricoDoBanco.detalhe_recente` por fonte. A busca continua aplicando `rodaram`, `ja_detalhadas` e os tetos dela por cima.

- [x] **Teste que falha:**
  - `test_candidatas_devolvem_ocorrencia_id_e_mais_novas_primeiro`.
  - `test_candidatas_sem_vaga_com_descricao_na_ocorrencia`.
  - `test_candidatas_sem_url_com_detalhe_recente_de_outra_fonte`: `enriquecimento` da mesma URL por outra fonte há 10 dias → fora; há 31 dias → dentro.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_candidatas_a_detalhe.py -q`.
- [x] **Implementar** e trocar o laço de `_enriquecer` pela chamada.
- [x] **Ver passar:** o arquivo novo e `tests/integracao/test_execucao.py` (os testes de hoje do passo de detalhes passam sem mudança).

### T201: Migração 0007, tipo de execução `login`
`depende_de: —` · D132.6, D132.47

**Arquivos:** criar `src/jobot/banco/migracoes/0007_execucao_login.sql`, `tests/integracao/test_migracao_0007.py`; modificar `src/jobot/banco/execucoes.py` (`Tipo = Literal["busca", "descoberta", "paginas", "login"]`) e `tests/unidade/test_arquitetura.py` (`_tabelas_de`, `:49-60`). O `TIPOS` do `cli/servir.py` muda na T215.

**SQL (ordem fixa):** `CREATE TABLE execucao_nova` com todas as colunas de `0001_inicial.sql:36-44` mais `parada` com o `CHECK` de `0004_motivo_da_parada.sql:4-5`, e `tipo IN ('busca','descoberta','paginas','login')`; `INSERT INTO execucao_nova (colunas) SELECT colunas FROM execucao`; `DROP TABLE execucao`; `ALTER TABLE execucao_nova RENAME TO execucao`; `CREATE UNIQUE INDEX execucao_uma_por_tipo ON execucao(tipo) WHERE estado = 'rodando'`. Sem `IF NOT EXISTS`; `execucao` não tem gatilho (os gatilhos são de `vaga` e `evento`).

**Leitor do esquema da wiki:** hoje `_tabelas_de` junta criadas menos apagadas em conjuntos, e com a 0007 sumiria `execucao` e sobraria `execucao_nova` (`test_er_tem_todas_as_tabelas` e `test_er_nao_tem_tabela_que_nao_existe`, `:128-141`). Passa a ler os comandos em ordem: `CREATE` acrescenta, `DROP` tira, `ALTER TABLE x RENAME TO y` tira `x` e acrescenta `y`.

- [x] **Teste que falha** (lê só o arquivo da 0007 por helper que afirma `exists()`; banco antes montado com as 0001 a 0006):
  - `test_0007_migra_sem_perder_linha`: três execuções com `saude` e `execucao_fonte`; mesmas contagens e mesmos `id` depois.
  - `test_0007_aceita_login`: `INSERT ... tipo='login'` passa; `tipo='outro'` levanta `IntegrityError`.
  - `test_0007_parada_continua_valendo`: `parada='xyz'` levanta; `parada=NULL` passa.
  - `test_0007_indice_unico_continua`: segunda `rodando` do mesmo tipo levanta.
  - `test_0007_chaves_estrangeiras_apontam_para_execucao`: `PRAGMA foreign_key_list(saude)` e de `execucao_fonte` apontam para `execucao`, não `execucao_nova`.
  - Em `test_arquitetura.py`, caso novo em `test_leitor_do_esquema_tira_tabela_apagada_e_comentario`: `CREATE TABLE e (x); CREATE TABLE e_nova (x); DROP TABLE e; ALTER TABLE e_nova RENAME TO e;` → `e` presente, `e_nova` ausente.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_migracao_0007.py tests/unidade/test_arquitetura.py::test_leitor_do_esquema_tira_tabela_apagada_e_comentario -q`.
- [x] **Implementar** o `.sql`, o `Tipo` e o leitor em ordem.
- [x] **Ver passar:** os dois arquivos inteiros (`tests/unidade/test_arquitetura.py` todo, para os testes do ER) e ruff.

### T202: Migração 0008 e semeadura das fontes com login
`depende_de: T197, T201` · D132.8, D132.20, D132.46

**Arquivos:** criar `src/jobot/banco/migracoes/0008_fonte_com_login.sql`, `tests/integracao/test_migracao_0008.py`; modificar `src/jobot/banco/cadastros.py` (`FonteCadastrada`, `fontes`, `semear`); teste em `tests/integracao/test_cadastros.py`.

**SQL:** `ALTER TABLE fonte ADD COLUMN com_login INTEGER NOT NULL DEFAULT 0 CHECK (com_login IN (0,1));`

**Interfaces (produz):** `FonteCadastrada.com_login: bool = False`; `semear_leitores(con, leitores: Sequence[LeitorComLogin]) -> None` com `INSERT INTO fonte (chave, leva, intervalo_min, ligada, com_login) VALUES (?, 'A', NULL, 0, 1) ON CONFLICT(chave) DO UPDATE SET com_login = 1`; `semear(con)` chama `semear_leitores(con, leitores())`; `fontes_com_login_ligadas(con) -> list[str]`.

- [x] **Teste que falha:**
  - `test_0008_da_com_login_zero_nas_antigas` e `test_0008_recusa_valor_fora` (`com_login=2` levanta).
  - `test_semear_leitores_nasce_desligada_e_com_login`; `test_semear_leitores_nao_troca_ligada` (liga, semeia de novo, segue ligada; mutar o `DO UPDATE` para tocar `ligada` reprova).
  - `test_fontes_com_login_ligadas_so_as_ligadas`.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_migracao_0008.py tests/integracao/test_cadastros.py -k "0008 or leitores or com_login" -q`.
- [x] **Implementar.**
- [x] **Ver passar** e ruff.

### T203: `coleta_acabou` e aba "Fontes" sem fontes com login
`depende_de: T202` · D132.46

**Arquivos:** modificar `src/jobot/banco/execucoes.py` (`execucao_atual`, `AND f.com_login = 0` no `NOT EXISTS`), `src/jobot/painel/rotas/configuracoes.py` (contexto de `fontes` filtra `not f.com_login`; `_gravar_fontes`, `:160-168`, passa a ter como conhecidas só as fontes sem login); testes em `tests/integracao/test_execucoes.py` e `tests/integracao/test_rota_configuracoes.py`.

Hoje `_gravar_fontes` liga ou desliga toda fonte conhecida conforme o formulário: com as fontes com login fora da aba, salvar a aba desligaria todas. Com as conhecidas restritas, uma chave com login marcada no formulário dá 422 pela regra que já existe.

- [x] **Teste que falha:**
  - `test_coleta_acaba_com_fonte_com_login_ligada`: uma fonte pública e uma `_logado` ligadas; linha em `execucao_fonte` só da pública; `execucao_atual(con).coleta_acabou is True`.
  - `test_aba_fontes_nao_lista_fonte_com_login`: `semear_leitores` com um leitor de teste e ligado; `GET /configuracoes/fontes` não traz a chave dele.
  - `test_salvar_aba_fontes_nao_desliga_site_com_login`: o site com login ligado; POST da aba com as públicas; o site segue ligado.
  - `test_salvar_aba_fontes_com_chave_com_login_da_422`.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_execucoes.py::test_coleta_acaba_com_fonte_com_login_ligada tests/integracao/test_rota_configuracoes.py -k "com_login" -q`.
- [x] **Implementar.**
- [x] **Ver passar** e ruff.

### T204: Última leitura com login e `login_horarios`
`depende_de: T201` · D132.6, D132.25, D132.48 (para confirmar: D132.6, D132.25)

**Arquivos:** modificar `src/jobot/banco/execucoes.py`, `src/jobot/banco/cadastros.py` (`PADROES`); criar `src/jobot/nucleo/horarios.py`, `tests/unidade/test_horarios.py`; testes em `tests/integracao/test_execucoes.py` e `tests/integracao/test_cadastros.py` (`test_padroes_de_config`, `:422`).

**Interfaces (produz):** `inicio_da_ultima_leitura_login(con) -> datetime | None` (`MAX(iniciada_em)` de `tipo='login'` com `estado IN ('concluida','interrompida')`); `PADROES["login_horarios"] = ["09:00", "18:00"]`; `horarios_validos(valor: object) -> tuple[time, ...]`, que levanta `ValueError` com uma de `configuracoes.sites_com_login.horarios.{formato,repetido,muitos,perto}` como `args[0]` e devolve os horários em ordem.

- [x] **Teste que falha:**
  - `test_ultima_leitura_conta_concluida_e_interrompida`; `test_ultima_leitura_ignora_rodando_e_outros_tipos`.
  - `test_horarios_validos_aceita_o_padrao` (`(time(9), time(18))`), `test_horarios_validos_ordena`, e `test_horarios_tortos_recusados[...]` com `["9:00"]`, `["25:00"]`, `"09:00"`, `[]`, `["09:00","09:00"]`, cinco horários, `["09:00","12:00"]` (menos de 4 h), `["22:00","01:00"]` (3 h passando a meia-noite), conferindo a chave no `match`. Controle: `["22:00","02:00"]` passa.
  - `test_padroes_de_config` atualizado com `login_horarios`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_horarios.py -q` e o `-k ultima_leitura` de `test_execucoes.py`.
- [x] **Implementar.**
- [x] **Ver passar** e ruff.

### T205: Quatro motivos novos da saúde
`depende_de: —` · D132.7, D132.45

**Arquivos:** modificar `src/jobot/painel/i18n/pt/comum.json`, `src/jobot/painel/i18n/en/comum.json`, `tests/unidade/test_i18n.py` (`MOTIVOS` ganha `precisa_login captcha sem_tela sem_navegador`).

Textos: `precisa_login` "Precisa entrar de novo no site: use Fazer login agora" / "You need to sign in to the site again: use Sign in now"; `captcha` "O site pediu um CAPTCHA que não foi resolvido" / "The site asked for a CAPTCHA that was not solved"; `sem_tela` "Sem tela para abrir o navegador" / "No display to open the browser"; `sem_navegador` "Nenhum navegador pôde abrir: instale o Chrome ou as bibliotecas do sistema" / "No browser could open: install Chrome or the system libraries".

- [x] **Teste que falha:** `test_motivos_fixos_existem[pt|en]` com a lista nova; `test_textos_pt_e_en_diferem_nos_motivos`.
- [x] **Implementar** e **ver passar:** `uv run pytest tests/unidade/test_i18n.py -q`.

### T206: `login_vencido`, o tipo `login` no `o_que_roda` e o estado do banco
`depende_de: T197, T202, T204` · D132.6, D132.25 (para confirmar: D132.6)

**Arquivos:** criar `src/jobot/agenda/login.py`, `tests/unidade/test_agenda_login.py`; modificar `src/jobot/agenda/agendador.py` (`Estado`, `o_que_roda`, `laco`), `src/jobot/cli/servir.py` (`_EstadoDoBanco.login()` e `interruptores()`), `tests/unidade/test_agendador.py` (o `_Estado` ganha `login()` que devolve `None`) e `tests/integracao/test_servir.py`.

O `laco` passa a chamar `estado.login()`; se o `_EstadoDoBanco` não o tivesse, o `except Exception` de `agendador.py:118-121` engoliria o `AttributeError` a cada volta e nada mais rodaria. Por isso `_EstadoDoBanco.login()` nasce nesta tarefa.

**Interfaces (produz):** `JANELA_HORARIO`, `INTERVALO_MINIMO`; `@dataclass(frozen=True) Login(horarios: tuple[time, ...], ultima: datetime | None)`; `login_vencido(agora: datetime, horarios: Sequence[time], ultima: datetime | None) -> bool`; `pode_ler_agora(agora: datetime, ultima: datetime | None) -> bool` (`ultima` nula, no futuro ou `agora - ultima >= INTERVALO_MINIMO`); `Estado.login() -> Login | None`; `o_que_roda(..., pagina_nova=False, login: Login | None = None)`, com `"login"` por último quando `interruptores.get("login", True)`, `login` não é `None` e `login_vencido(...)`. `_EstadoDoBanco.login() -> Login | None`: `None` se nenhuma chave de `fontes_com_login_ligadas(con)` está em `leitores()`; senão `Login(horarios, inicio_da_ultima_leitura_login(con))`, com `horarios = horarios_validos(ler_config(con, "login_horarios"))` e, em `ValueError`, o padrão de `PADROES` e um `log.warning` só com a chave do erro. `interruptores()` antes da primeira execução devolve também `login: False`.

Regra (A6): `H` = ocorrência mais recente de um horário que não passa de `agora`, hoje ou ontem no dia local (`agora.astimezone()`); vence se `agora - H < JANELA_HORARIO`, `ultima is None or ultima < H` e, havendo `ultima`, `H - ultima >= INTERVALO_MINIMO`. `ultima > agora` conta como `None`.

- [x] **Teste que falha** (fixture `TZ=America/Sao_Paulo` com `tzset`, desfeita no `yield`; datas com `-03:00`; ontem = 14/11):
  - `test_vence_as_9h` e `test_nao_vence_as_9h05_com_leitura_as_9h01`.
  - `test_vence_as_9h14` e `test_nao_vence_as_9h16_sem_leitura_desde_ontem`.
  - `test_fechou_o_navegador_as_9h02_nao_reabre_as_9h03` e `test_erro_as_9h01_nao_repete_na_janela`.
  - `test_perdeu_as_9h_ligou_as_15h`: às 15h00 não; às 18h00 com `ultima=14:00` sim; com `ultima=15:30` não; às 09:00 de 16/11 com `ultima=15:30` sim.
  - `test_buscar_agora_as_16h_pula_as_18h`.
  - `test_ligou_as_20h_depois_de_perder_as_duas`: não; às 09:00 seguintes sim.
  - `test_ultima_no_futuro_nao_trava`; `test_fora_de_utc_usa_o_dia_local`: horário `23:00`, vence às 23:10 de 15/11 locais (02:10 UTC de 16/11) e não às 00:30 de 16/11.
  - `test_pode_ler_agora[...]`: `None`, futuro, 3h59 (não), 4h00 (sim).
  - `test_o_que_roda_sem_login_fica_igual`, `test_o_que_roda_com_login_vencido_poe_login_por_ultimo`, `test_login_nao_roda_nos_primeiros_60_s`, `test_login_desligado_pelo_interruptor` e `test_sem_site_ligado_nao_roda` (`login=None`).
  - Em `test_servir.py`: `test_horarios_tortos_no_banco_valem_o_padrao` (RF3: `login_horarios = "x"` gravado e um leitor de teste em `registro.LEITORES` por `monkeypatch`; `login().horarios == (time(9), time(18))` e `caplog` com a chave); `test_estado_login_none_sem_site_ligado`; `test_login_parado_antes_da_primeira_execucao`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_agenda_login.py -q` e `uv run pytest tests/integracao/test_servir.py -k "login or horarios" -q`.
- [x] **Implementar** e passar `login=estado.login()` no `laco`.
- [x] **Ver passar:** os dois arquivos, `tests/unidade/test_agendador.py` e ruff.

### T207: `js.py` e a lista permitida do Playwright
`depende_de: T196` · D132.16, D132.31, D132.38 (para confirmar: D132.31)

**Arquivos:** criar `src/jobot/navegador/js.py`, `tests/unidade/test_navegador_ast.py`, `tests/unidade/test_navegador_js.py`.

**Interfaces (produz, `js.py`):** `ROLAR: Final = "() => window.scrollBy(0, document.body.scrollHeight)"`; `ENTREGAR_TOKEN: Final` (recebe `[campo, token, nome_retorno]`; escreve `token` no `textarea`/`input` de nome `campo` do widget; se `nome_retorno` não é nulo, resolve parte por parte a partir de `window` e chama só se for função; devolve `true` se chamou); `USER_AGENT: Final = "() => navigator.userAgent"` (só usado se o cabeçalho não servir); `NOME_RETORNO = re.compile(r"[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*")`; `nome_de_retorno_valido(nome: str) -> bool` (`fullmatch`, ASCII); `async def rolar(page) -> None`; `async def entregar_token(page, campo: str, token: str, nome_retorno: str | None) -> bool`.

**Regra dos homônimos:** o teste não sabe o tipo do objeto pelo AST, então todo nome público de `Page`, `Frame`, `Locator`, `BrowserContext`, `Browser`, `Request` ou `Response` (por `dir()` na 1.65.1) fora de `PERMITIDOS` reprova, mesmo em `dict` ou `Path`; o código do `navegador` evita esses nomes (ex.: nada de `dict.clear()`). `APIRequestContext` e `APIResponse` ficam fora do `dir()` conferido, porque chegar a eles exige `.request`, que sempre reprova. Exceção nomeada: `TOLERADOS = {"name"}` (só leitura em `Frame`). Para não esbarrar em homônimo, o código do pacote usa `asyncio.timeout` no lugar de `asyncio.wait_for` e `json.loads(await resposta.text())` no lugar de `.json()`.

- [x] **Teste que falha:**
  - `test_nome_de_retorno_valido`: `a.b.c`, `_x`, `$cb` aceitos; `alert(1)`, `a..b`, `1a`, `a b`, `` e `a.` recusados.
  - `test_scripts_de_js_sao_literais_e_so_os_tres`: AST de `js.py`: toda chamada `*.evaluate(...)` tem como 1º argumento um `Name` que aponta para `ROLAR`, `ENTREGAR_TOKEN` ou `USER_AGENT`, e esses três são `Constant` de `str`; nenhum outro `Constant` com `=>` ou `function`. Detector numa pasta temporária pega uma f-string e uma concatenação.
  - `test_lista_permitida_do_navegador`: em `src/jobot/navegador/` (menos `js.py`) e em `scripts/capturar_logado.py` quando existir, todo `ast.Attribute.attr` que é nome público dos objetos acima está em `PERMITIDOS | TOLERADOS` (`wait_for` e `json` reprovam); `request` e `all_headers` sempre reprovam; `on`/`once` só com 1º argumento `Constant` em `{"response", "request", "close"}`; `evaluate` fora de `js.py` reprova.
  - `test_tolerados_sao_so_name`: `TOLERADOS == {"name"}`.
  - `test_detector_da_lista_permitida_acha_o_ruim` e `test_detector_da_lista_permitida_aceita_o_bom`: pasta temporária com um arquivo por exemplo ruim (`page.click()`, `page.evaluate("x")`, `page.route("**", f)`, `context.request.get(u)`, `pedido.all_headers()`, `page.on("dialog", f)`, `page.get_by_role("x")`, `d.clear()`) → cada um achado; exemplo bom (`page.goto(u)`, `page.locator("x").get_attribute("y")`, `page.on("response", f)`, `pedido.headers`, `frame.name`) → nada.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_ast.py tests/unidade/test_navegador_js.py -q`.
- [x] **Implementar** `js.py`, `PERMITIDOS` e `TOLERADOS` no teste (conferir cada nome com `dir()` na 1.65.1).
- [x] **Ver passar** e ruff.

**Pronto quando:** o detector pega as oito categorias e a pasta `navegador/` real passa.

### T208: Preferências do perfil
`depende_de: T196, T198` · D132.3, D132.43

**Arquivos:** criar `src/jobot/navegador/perfil.py`, `tests/unidade/test_navegador_perfil.py`; modificar `wiki/Arquitetura.md` e `wiki/Architecture.md` (seta `navegador --> sistema`).

**Interfaces (produz):** `PREFERENCIAS = {"credentials_enable_service": False, "profile": {"password_manager_enabled": False}, "autofill": {"profile_enabled": False}}`; `pasta_do_perfil(dados: Path) -> Path` (`dados / PASTA_NAVEGADOR`, criada 0700, recusa symlink com `OSError`); `preparar_preferencias(perfil: Path) -> None` (lê `Default/Preferences`, junta as três chaves sem perder as outras, grava em `.tmp` no mesmo diretório com `O_EXCL` e 0600, `fsync`, `os.replace`); `apagar_perfil(dados: Path) -> None` (recusa symlink; `shutil.rmtree` da pasta).

- [x] **Teste que falha:**
  - `test_preferencias_em_perfil_vazio`: três chaves gravadas, arquivo 0600.
  - `test_preferencias_preservam_outras_chaves`: `{"profile": {"name": "x"}, "outra": 1}` mantém `name` e `outra`.
  - `test_preferencias_arquivo_torto_reescreve`: `"{quebrado"` → só as três chaves; `caplog` com "reescrito" e sem o conteúdo.
  - `test_preferencias_nao_utf8_ou_lista_reescreve` (RF2): bytes `b"\xff\xfe"` e `[1, 2]`.
  - `test_preferencias_symlink_e_recusado` (RF2): `Preferences` é symlink para fora; levanta `OSError` e o alvo não muda.
  - `test_apagar_perfil` e `test_apagar_perfil_symlink_nao_apaga_o_alvo`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_perfil.py -q`.
- [x] **Implementar.** Conferir os nomes das chaves na documentação pública do Chromium da versão que vem com o Playwright 1.65.1.
- [x] **Ver passar**, `tests/unidade/test_arquitetura.py` e ruff.

### T209: Política de navegação
`depende_de: T197` · D132.42

**Arquivos:** criar `src/jobot/navegador/politica.py`, `tests/unidade/test_navegador_politica.py`; modificar `wiki/Arquitetura.md` e `wiki/Architecture.md` (seta `navegador --> nucleo`).

**Interfaces (produz):** `Politica = Callable[[str], bool]`; `politica_de_producao(hosts: Sequence[str]) -> Politica` (só `https`, `urlsplit(url).hostname` em `hosts`, nunca `host_local`); `dentro_dos_hosts(url: str, hosts: Sequence[str]) -> bool`; `casa_login(url: str, prefixos: Sequence[str]) -> bool` (`host + caminho` com `startswith`).

- [x] **Teste que falha:** `test_producao_recusa_http`, `test_producao_recusa_127_0_0_1` (mesmo com `"127.0.0.1"` em `hosts`), `test_producao_recusa_host_fora`, `test_producao_aceita_https_do_leitor`, `test_producao_recusa_host_parecido` (`site.com.mal.io`), `test_casa_login_por_host_e_caminho`.
- [x] **Ver falhar**, **implementar**, **ver passar:** `uv run pytest tests/unidade/test_navegador_politica.py tests/unidade/test_arquitetura.py -q`.

### T210: Tela pelo ambiente do systemd
`depende_de: —` · D132.9, D132.50

**Arquivos:** criar `src/jobot/sistema/tela.py`, `tests/unidade/test_tela.py`.

**Interfaces (produz):** `VARIAVEIS = ("DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR")`; `ambiente_da_tela(env: Mapping[str, str], rodar: Rodar) -> dict[str, str]` (vazio = sem tela). Com `DISPLAY` ou `WAYLAND_DISPLAY` válido no `env`, devolve as quatro que forem válidas no `env` sem rodar nada; senão roda `[*prefixo_host(env), "systemctl", "--user", "show-environment"]` e pega só as quatro, validadas: `DISPLAY` casa `[A-Za-z0-9.-]*:\d+(\.\d+)?`; `WAYLAND_DISPLAY` nome sem `/` ou caminho absoluto; `XAUTHORITY` e `XDG_RUNTIME_DIR` absolutos que existem. Log: só os nomes aceitos. `Rodar` e `Resultado` vêm de `sistema/segundo_plano_linux.py`.

- [x] **Teste que falha:**
  - `test_tela_do_proprio_ambiente_nao_roda_comando` (executor que levanta `AssertionError`).
  - `test_sem_tela_le_o_systemd` e `test_no_container_usa_distrobox_host_exec` (`CONTAINER_ID` presente → comando começa com `distrobox-host-exec`).
  - `test_valores_fora_do_formato_sao_ignorados` (`DISPLAY=;rm`, `WAYLAND_DISPLAY=a/b`, `XAUTHORITY=relativo`).
  - `test_segredo_da_saida_nao_vai_ao_log_nem_ao_ambiente`: saída com `SEGREDO=xyz` e `TOKEN=SEGREDO`; `"SEGREDO" not in caplog.text` e fora do dicionário.
  - `test_sem_nada_devolve_vazio` (código 1 e saída vazia).
- [x] **Ver falhar**, **implementar**, **ver passar:** `uv run pytest tests/unidade/test_tela.py -q`.

### T211: Abrir o navegador
`depende_de: T207, T208, T210` · D132.2, D132.3, D132.15, D132.17, D132.24, D132.55 (para confirmar: D132.15, D132.24)

**Arquivos:** criar `src/jobot/navegador/abrir.py`, `src/jobot/navegador/limites.py` (os valores da seção "num lugar só"), `tests/unidade/test_navegador_abrir.py`.

**Interfaces (produz):** `class SemNavegador(Exception)`, `class SemTela(Exception)`; `Lancar = Callable[..., Awaitable[BrowserContext]]` (recebe os mesmos argumentos de nome de `launch_persistent_context`); `async def abrir_contexto(dados: Path, ambiente: Mapping[str, str], lancar: Lancar) -> BrowserContext` (`ambiente` vazio → `SemTela` sem chamar `lancar`; `preparar_preferencias`; tenta `channel="chrome"`, depois sem canal; os dois falhando → `SemNavegador`, com a mensagem do Playwright só no log por `exc_info`); `def lancador_de_producao(playwright, ambiente: Mapping[str, str]) -> Lancar` (fixa `headless=False`, `user_data_dir`, `env={**os.environ, **ambiente}` porque o `env` do Playwright substitui o ambiente inteiro, sem `args`); `async def navegador_instalado() -> Literal["chrome", "chromium"] | None` (E8).

- [x] **Teste que falha** (lançador falso que guarda os argumentos):
  - `test_lancador_de_producao_abre_visivel`: os argumentos não têm `headless=True`, `args`, `ignore_default_args` nem `--remote-debugging-port` em lugar nenhum; `user_data_dir` é `<dados>/navegador`.
  - `test_lancador_de_producao_mantem_home_e_path`: `env` tem `HOME` e `PATH` do `os.environ` e o `DISPLAY` do ambiente da tela.
  - `test_chrome_primeiro_depois_chromium`: o falso falha com `channel="chrome"` e passa sem canal; duas chamadas, nessa ordem.
  - `test_os_dois_falhando_e_sem_navegador`: `SemNavegador`; o texto do erro (com `SEGREDO`) só uma vez no log e fora de `str(exceção)`.
  - `test_sem_tela_nem_chama_o_lancador`.
  - `test_preferencias_gravadas_antes_de_abrir`.
  - `test_navegador_instalado` com `monkeypatch` do caminho do Chrome e do `executable_path`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_abrir.py -q`.
- [x] **Implementar.**
- [x] **Ver passar** e ruff; `test_navegador_ast.py` continua verde.

### T212: Site falso e uma navegação com as checagens
`depende_de: T209, T211` · D132.11, D132.30, D132.37, D132.42, D132.54 (para confirmar: D132.30)

**Arquivos:** criar `tests/apoio/site_falso.py`, `tests/navegador/conftest.py`, `tests/navegador/test_navegacao_logada.py`, `src/jobot/navegador/pagina.py`; modificar `src/jobot/nucleo/http.py` (E14) e o teste dele que cite o nome antigo.

**Interfaces:**
- Produz (`tests/apoio/site_falso.py`): servidor `ThreadingHTTPServer` em `127.0.0.1` e `::1`, com as páginas da seção 8 do desenho (login, login com reCAPTCHA invisível, lista em JSON pedida pela página e em HTML, rolar, paginação, segunda página sem formato, lista vazia, `proxima` fora, escopo fora, vagas, sem lista, item torto, só tortos, bloqueio, 403, 429 com `Retry-After`, salto para SSO em `::1` e para host qualquer em `::1`, "Just a moment" que sai e que não sai, reCAPTCHA v2, Turnstile avulso, 403 com Turnstile, 429 com reCAPTCHA, desafio que volta, v3, `data-callback="alert(1)"`), contadores `posts`, `visitas[caminho]` e `campos_mudados`; `LeitorFalso` com `chave = "falso_logado"`, `hosts = ("127.0.0.1",)`, `prefixos_login = ("::1/sso",)` e `ler` simples; fixtures `site`, `contexto_de_teste` (lança sem tela pelo `lancar` injetado e instala a rota que recusa fora de `127.0.0.1`/`::1`, conferindo no fim `recusados == []`), `politica_local`, `RelogioDoNavegador` (guarda as dormidas e dorme de verdade no máximo 0,05 s, para os timers da página andarem).
- Produz (`navegador/pagina.py`): `@dataclass(frozen=True) Recusada(url_host: str)`; `Visita = Captura | ParadaLogin | Recusada` (a T216 acrescenta o `Widget`); `def ouvir_respostas(page, hosts: Sequence[str], padroes: Sequence[str] | None) -> list[RespostaCapturada]` (liga o `page.on("response")` e devolve a lista que vai enchendo: só dos `hosts`, tipo `application/json` ou `text/html`, `content-length` e corpo até `MAX_RESPOSTA_BYTES`, até `MAX_RESPOSTAS`, casando `padroes` por E3, ou tudo quando `None`; texto com `errors="replace"`); `async def visitar(page, url: str, leitor: LeitorComLogin, politica: Politica, relogio: Relogio) -> Visita`, na ordem: política → `goto` → host de `page.url` (fora: `casa_login` → `"precisa_login"`, senão `"bloqueio"`) → login (`input[type=password]`, `e_login`, `casa_login`) → Cloudflare (E9, até `ESPERA_CLOUDFLARE_S` olhando a cada 1 s pelo relógio) → 401/403/`pagina_bloqueada` → 429 (`segundos_retry_after` acima de `MAX_RETRY_AFTER_S` → `"no_limite"` direto; senão uma espera do pedido ou de 30 s; repetiu → `"no_limite"`) → assentar (E11) → rolar se `leitor.rolar` → `Captura`. Log: só host e caminho.

- [x] **Teste que falha** (`tests/navegador/test_navegacao_logada.py`):
  - `test_lista_carregada_pela_pagina_e_capturada` e `test_captura_so_respostas_que_casam` (resposta de outro caminho fica de fora).
  - `test_resposta_acima_de_5_mb_e_ignorada`, com e sem `content-length`.
  - `test_rolar_traz_mais_itens`.
  - `test_url_fora_da_politica_nao_e_visitada`: `Recusada`, `visitas` sem o caminho.
  - `test_salto_para_sso_e_precisa_login` e `test_salto_para_outro_host_e_bloqueio`; nada capturado de `::1`.
  - `test_pagina_de_login_e_precisa_login` (por `input[type=password]`) e `test_prefixo_de_login_e_precisa_login`.
  - `test_cloudflare_que_sai_sozinho_segue`.
  - `test_403_e_pagina_de_bloqueio_sao_bloqueio`.
  - `test_429_espera_o_retry_after` (dormida de 7 s pelo relógio), `test_retry_after_acima_do_teto_e_no_limite` (`Retry-After: 601`, sem dormida) e `test_429_repetido_e_no_limite`.
  - `test_navegacao_nao_faz_post` (`site.posts == 0`, `campos_mudados == 0` em todas as acima).
- [x] **Ver falhar:** `uv run pytest tests/navegador/test_navegacao_logada.py -q`.
- [x] **Implementar** `visitar`, `ouvir_respostas` e o nome público no `http.py` (chamador `:424`).
- [x] **Ver passar**, `tests/unidade/test_http.py`, `test_navegador_ast.py` e ruff.

### T213: A execução `login`
`depende_de: T199, T202, T205, T212` · D132.16, D132.18, D132.19, D132.33, D132.34, D132.36, D132.40, D132.49, D132.51 (para confirmar: D132.19)

**Arquivos:** criar `src/jobot/navegador/execucao.py`, `tests/navegador/test_execucao_logada.py`; modificar `wiki/Arquitetura.md` e `wiki/Architecture.md` (seta `navegador --> banco`).

**Interfaces:**
- Consome: `abrir_execucao`, `fechar_execucao`, `interromper`, `interromper_execucao`, `manter_batimento`, `gravar_saude`, `HistoricoDoBanco` (`banco/execucoes.py`); `gravar_escopo`, `fechar_escopos_extintos` (`banco/gravacao.py`); `tratar`; `estado_do_escopo`, `parada_mais_forte`; `visitar`; `abrir_contexto`, `lancador_de_producao`; `ambiente_da_tela`, `rodar_comando`; `fontes`, `termos_das_buscas`, `paises_das_buscas`, `empresas_da_coleta`.
- Produz: `@dataclass(frozen=True) Dependencias(dados: Path, lancar: Lancar, ambiente: Callable[[], Mapping[str, str]], politica: Callable[[LeitorComLogin], Politica], sortear: Callable[[], float])` (a T216 acrescenta `cofre`, a T217 `avisar`, cada uma com a sua ligação de produção); `@asynccontextmanager async def dependencias_de_producao(dados: Path, env: Mapping[str, str]) -> AsyncIterator[Dependencias]` (E17: abre o `async_playwright()`, liga `lancador_de_producao`, `ambiente = lambda: ambiente_da_tela(env, rodar_comando)`, `politica_de_producao(leitor.hosts)`, `sortear = lambda: random.uniform(ESPERA_MIN_S, ESPERA_MAX_S)`; fecha o Playwright na saída); `class NavegadorFechado(Exception)`; `async def executar_login(con, cliente: ClienteEducado, relogio: Relogio, motivo: Motivo, *, leitores: Sequence[LeitorComLogin], deps: Dependencias) -> int | None` (devolve o id da execução; `None` sem site ligado).

Fluxo (A7, "Uma execução `login`"): sites desligados gravam `desligada` com escopo `''`; sem tela ou sem navegador, `saude.sem_tela`/`saude.sem_navegador` em cada site ligado com escopo `''` e a execução conclui; por site ligado, numa aba nova: entrada (conta 1 no `MAX_LISTA`, E16; `pagina_logada` falsa ou parada → linha `''`); `escopos(ctx)` (quebrou → `falhou` `''`, log com `exc_info`); rodízio por `ultima_coleta` (`None` primeiro); por escopo, visitas até `MAX_LISTA` no site, `proxima` pela política (recusada → `cortada`), espera `relogio.dormir(deps.sortear())` antes de toda navegação menos a primeira; parada encerra o site; `Desfecho` → `SaidaEscopo(fonte, escopo.id, ResultadoEscopo(vagas, estado, motivo, pedidos=navegações), duracao_ms, validadores={}, urls_vistas=URLs de lista, urls_sem_detalhe=(), detalhes=0)` → `gravar_escopo` com `tratar`; sem parada na entrada e sem quebra de `escopos`, `fechar_escopos_extintos(con, chave, {todos os ids}, agora)`. Erro num site não para os outros. E12 para fechar e cancelar.

- [x] **Teste que falha:**
  - `test_execucao_grava_vaga_com_fonte_e_escopo`: `ocorrencia.fonte == "falso_logado"`, `escopo` do escopo lido; vaga com a mesma URL de uma vaga da fonte pública já gravada vira uma linha em `vaga`.
  - `test_uma_gravacao_por_escopo_sem_cache_http`: espião em `gravar_escopo` chamado uma vez por escopo com as vagas de duas páginas, `validadores == {}`, `urls_sem_detalhe == ()`; `cache_http` com o mesmo número de linhas.
  - `test_sem_login_e_precisa_login_e_o_outro_site_segue` (dois leitores falsos; o segundo grava vagas).
  - `test_estado_do_escopo_de_ponta_a_ponta[...]`: sem lista → `falhou`/`formato_mudou` e nenhuma ocorrência fecha; segunda página sem formato → nenhuma vaga da primeira; `proxima` fora → `parcial`/`listagem_incompleta`; URL inicial fora → `falhou`/`listagem_incompleta`, não visitada, nada fecha; login no meio → `falhou`/`precisa_login`, vagas da primeira gravadas, nada fecha.
  - `test_403_para_o_site_e_o_proximo_segue` e `test_429_repetido_para_o_site_sem_gravar_os_seguintes`: escopos seguintes não visitados e a linha de saúde anterior deles igual.
  - `test_teto_de_10_paginas_de_lista_por_site` (entrada mais três escopos com quatro páginas: 10 visitas de lista contando a entrada) e `test_espera_entre_3_e_8_s_em_toda_navegacao` (`sortear` falso; `RelogioDoNavegador.dormidas` com um valor por navegação depois da primeira).
  - `test_rodizio_vai_nos_mais_antigos`: três escopos, teto para dois; o terceiro sem linha nova.
  - `test_escopos_extintos[...]`: busca removida fecha; escopo pulado pelo teto não; site que parou na entrada não fecha nada.
  - `test_execucao_sem_captcha_nao_faz_post`.
  - `test_site_desligado_grava_desligada`.
  - `test_sem_tela_grava_sem_tela_e_nao_lanca` e `test_sem_navegador_grava_sem_navegador` (lançador falso que levanta).
  - `test_fechar_o_navegador_interrompe_com_fechado`: o servidor falso fecha o contexto na segunda página; execução `interrompida`, `parada='fechado'`, escopo já gravado fica, nenhum traceback no `caplog`.
  - `test_cancelar_a_leitura_fecha_o_navegador` (RF5): cancela a tarefa durante a espera; `contexto.pages == []` depois, execução `interrompida` com `fechado`, `CancelledError` sobe.
  - `test_dependencias_de_producao_fecham_o_playwright` (com `async_playwright` trocado por um falso que conta `__aexit__`).
- [x] **Ver falhar:** `uv run pytest tests/navegador/test_execucao_logada.py -q`.
- [x] **Implementar.**
- [x] **Ver passar**, `test_navegador_ast.py`, `tests/unidade/test_arquitetura.py` e ruff.

### T214: Detalhe com cache
`depende_de: T200, T213` · D132.19, D132.32 (para confirmar: D132.19, D132.32)

**Arquivos:** modificar `src/jobot/navegador/execucao.py`; criar `tests/navegador/test_detalhe_logado.py`.

**Interfaces:** consome `candidatas_a_detalhe(con, [chave], inicio, relogio)` e `gravar_cache_detalhe(con, ocorrencia_id, url, detalhe, agora)`; produz `async def _detalhar_site(...)`, chamado depois de gravar os escopos do site, só se `not leitor.lista_tem_descricao` e o site não parou; filtra as candidatas da fonte e dos escopos visitados; até `MAX_VAGA`; cada URL passa por `visitar` e por `leitor.detalhar`, com a mesma espera de `deps.sortear()` antes de cada uma.

- [x] **Teste que falha:**
  - `test_so_abre_vaga_sem_descricao_e_sem_detalhe_recente_mais_novas_primeiro` (ordem de `visitas`).
  - `test_nao_abre_url_detalhada_por_outra_fonte_ha_menos_de_30_dias`.
  - `test_cada_pagina_aberta_grava_enriquecimento` (com detalhe e com `detalhar` → `None`, conteúdo vazio).
  - `test_teto_de_20_vagas_e_o_resto_volta_depois`: 25 candidatas; 20 linhas em `enriquecimento`; segunda execução (relógio +4 h) abre as 5.
  - `test_espera_antes_das_paginas_de_vaga`: uma dormida de `sortear()` antes de cada página de vaga.
  - `test_descricao_antiga_fica_depois_de_nova_leitura_da_lista`.
  - `test_lista_com_descricao_nao_abre_vaga`.
- [x] **Ver falhar**, **implementar**, **ver passar:** `uv run pytest tests/navegador/test_detalhe_logado.py -q`.

### T215: `serve` e "Buscar agora"
`depende_de: T206, T213` · D132.18, D132.24, D132.25, D132.41, D132.49 (para confirmar: D132.25)

**Arquivos:** modificar `src/jobot/cli/servir.py` (`TIPOS` com `"login"`, `travas["login"]`, tarefa `login` no mapa, `app.state.tarefa_login`, `app.state.navegador_instalado`), `src/jobot/painel/rotas/execucao.py` (`buscar_agora`), `wiki/Arquitetura.md` e `wiki/Architecture.md` (seta `cli --> navegador`); testes em `tests/integracao/test_servir.py` e `tests/integracao/test_rota_execucao.py`.

**Interfaces:** tarefa `async def login(motivo: Motivo = "agenda")` no `vida`: abre a sua conexão e faz `async with dependencias_de_producao(dados, env) as deps: await executar_login(con, cliente, relogio, motivo, leitores=leitores(), deps=deps)`; o `servir` só importa `jobot.navegador`. O `vida` guarda a tarefa em `app.state.tarefa_login` e, só com leitor registrado, `app.state.navegador_instalado = await navegador_instalado()` uma vez (E8), com o comentário `# shortcut: navegador_instalado é calculado ao subir o serve; instalar o Chrome com o serve no ar só aparece depois de reiniciar; atualizar app.state quando o botão Baixar da Parte B existir`. Rota: depois de disparar a busca, `tarefa = getattr(request.app.state, "tarefa_login", None)`; sem tarefa não dispara; com tarefa, site com login ligado, `pode_ler_agora(agora, inicio_da_ultima_leitura_login(con))` e `not travas["login"].locked()`, `await travas["login"].acquire()` antes de qualquer outro `await` e dispara `tarefa("agora")` em `app.state.tarefas`, soltando a trava no fim; não espera. O painel importa `pode_ler_agora` de `jobot.agenda.login` (seta já existe). `jobot buscar` não muda.

- [x] **Teste que falha:**
  - `test_travas_tem_login_e_e_o_mesmo_objeto_do_laco`.
  - `test_buscar_agora[...]` com `app.state.tarefa_login` trocado por espião: sem atributo não dispara; sem site ligado não dispara; `ultima` há 3 h não dispara; trava presa não dispara outra; senão dispara com motivo `agora` e a resposta volta antes do espião terminar (`threading.Event`).
  - `test_buscar_agora_duas_vezes_dispara_uma_leitura` (RF4).
  - `test_andamento_nao_mostra_a_leitura_com_login`: execução `login` rodando; `GET /execucao` sem ela.
  - `test_servir_so_sobe_o_driver_com_leitor`: sem leitor, `navegador_instalado` não é chamado.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_execucao.py -k "buscar_agora or andamento_nao" -q` e o `-k "travas or driver"` de `test_servir.py`.
- [x] **Implementar.**
- [x] **Ver passar**, `tests/unidade/test_arquitetura.py` e ruff.

### T216: Cola do CAPTCHA
`depende_de: T214` · D132.10, D132.14, D132.15, D132.30, D132.31, D132.37, D132.38, D132.56, D132.57 (para confirmar: D132.15, D132.30, D132.31)

**Arquivos:** criar `src/jobot/navegador/captcha.py`, `tests/navegador/test_captcha_logado.py`; modificar `src/jobot/navegador/pagina.py`, `src/jobot/navegador/execucao.py`, `src/jobot/banco/captcha.py`, `src/jobot/painel/rotas/servicos.py` e `src/jobot/painel/rotas/configuracoes.py` (E13: import em `:34`, uso em `:267`).

**Interfaces:**
- Consome: `captcha_pronto(con, chave)`, `reservar_resolucao(con, dia)`, `Desafio` e `resolver(cliente, chave, desafio, relogio, *, reservar)` de `nucleo/captcha.py`, `ErroCaptcha`, `Cofre.ler(NOME_NO_COFRE)`, `entregar_token`, `nome_de_retorno_valido`.
- Produz: `@dataclass(frozen=True) Widget(tipo: Literal["recaptcha_v2", "turnstile", "nao_aceito"], sitekey: str, invisivel: bool, retorno: str | None, acao: str | None)` (nome que não colide com o `Desafio` do `nucleo`); `Visita` ganha `Widget`; a `visitar` ganha a checagem 4 (widget reconhecido, mesmo com 403 ou 429) entre o Cloudflare e o 401/403; `async def achar_widget(page) -> Widget | None` (`.g-recaptcha[data-sitekey]`, `data-size="invisible"`; `.cf-turnstile[data-sitekey]`, `data-action`; `script[src*="recaptcha/api.js?render="]` sem `render=explicit` → `nao_aceito`; `data-callback` que falha em `nome_de_retorno_valido` → `nao_aceito`, antes de qualquer pedido ao 2Captcha); `user_agent` lido de `request.headers["user-agent"]` pelo evento `request`; `async def resolver_na_pagina(page, widget, *, con, cliente, relogio, cofre, user_agent) -> bool` (uma tentativa por página; `Desafio` com `page.url`; espera até `ESPERA_TOKEN_S` a página sair do desafio). `Dependencias.cofre: Cofre`, ligado em `dependencias_de_producao` por `Cofre(dados)` de `sistema/cofre.py` (o mesmo que `painel/ambiente.py:32` monta quando o `app.state` não traz um). Se o mesmo desafio volta (E10), a parada é `"bloqueio"`.

- [x] **Teste que falha** (`resolver` com `httpx.MockTransport` do 2Captcha, chave inventada no `CofreFalso`, `captcha_ligado` verdadeiro):
  - `test_login_com_captcha_nao_chama_resolver`: página de login com reCAPTCHA invisível → `saude.precisa_login`, `MockTransport` com zero pedidos, `site.posts == 0`, `campos_mudados == 0`.
  - `test_captcha_resolvido_com_2captcha_pronto`: o `createTask` recebe tipo, `websiteKey` e o `userAgent` igual ao cabeçalho visto pelo servidor falso; o token chega à função de retorno; o único pedido depois do token é o que ela faz; nenhum campo além do de resposta muda.
  - `test_uma_tentativa_por_pagina`.
  - `test_403_com_turnstile_e_429_com_recaptcha_vao_ao_captcha` (não viram `bloqueio`).
  - `test_desafio_que_volta_e_bloqueio`.
  - `test_recaptcha_v3_nao_chama_resolver` → `"captcha"`.
  - `test_callback_de_nome_torto_nao_resolve_nem_chama_nada`: `alert(1)`; `MockTransport` com zero pedidos e `window.__alertas == 0` no site falso.
  - `test_turnstile_com_user_agent_diferente_nao_troca_o_do_navegador` (D132.56): o `getTask` devolve outro `userAgent`; o cabeçalho visto pelo servidor falso não muda; o token é tentado; a página não sai → `"captcha"`.
  - `test_log_sem_cookie_token_nem_query`: cookie `SEGREDO-COOKIE`, token `SEGREDO-TOKEN` e URL com `?q=SEGREDO-QUERY`; nenhum dos três em `caplog.text`.
  - `test_nome_no_cofre_definido_uma_vez`: AST de `src/` (os testes têm `NOME = "2captcha"` próprio e ficam de fora); uma atribuição só, em `banco/captcha.py`.
- [x] **Ver falhar:** `uv run pytest tests/navegador/test_captcha_logado.py -q`.
- [x] **Implementar.**
- [x] **Ver passar**, `tests/integracao/test_rota_servicos.py`, `tests/integracao/test_rota_configuracoes.py`, `test_navegador_ast.py` e ruff.

### T217: Janela parada e aviso no computador
`depende_de: T216` · D132.10, D132.26, D132.44 (para confirmar: D132.26, D132.44)

**Arquivos:** criar `src/jobot/sistema/aviso.py`, `tests/unidade/test_aviso.py`, `tests/navegador/test_janela_parada.py`; modificar `src/jobot/navegador/execucao.py`.

**Interfaces (produz):** `avisar(titulo: str, frase: str, env: Mapping[str, str], rodar: Rodar) -> None` (`[*prefixo_host(env), "notify-send", titulo, frase]`; código 127 é silêncio; outro código só no log); `Dependencias.avisar: Callable[[str, str], None]`, ligado em `dependencias_de_producao` por `lambda t, f: avisar(t, f, env, rodar_comando)`; na execução, abas paradas ficam numa lista; depois do último site, espera até `JANELA_PARADA_S` no total, olhando cada aba a cada 5 s pelo relógio; aba fora do desafio segue aquele site no mesmo prazo; no fim, as restantes gravam `falhou`/`saude.captcha` e o contexto fecha. O aviso sai uma vez por execução, sem URL.

- [x] **Teste que falha:**
  - `test_aviso_usa_notify_send` e `test_aviso_no_container_passa_pelo_host`; `test_sem_notify_send_fica_quieto` (código 127, nada no log de erro).
  - `test_captcha_sem_2captcha_para_a_janela[...]`: interruptor desligado, sem chave, `nao_aceito`, `ErroCaptcha(SEM_SALDO)`, teto (`reservar` falso devolve `False`), página que não sai em 30 s → `saude.captcha`, `avisar` chamado uma vez, a aba aberta até o fim do prazo.
  - `test_cloudflare_que_nao_sai_vai_para_a_janela_sem_resolver` (com iframe de Turnstile; `MockTransport` sem pedidos).
  - `test_duas_abas_dividem_os_15_minutos`: soma das dormidas da janela `<= 900`; a aba resolvida pelo teste grava vagas; a outra grava `saude.captcha`.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_aviso.py tests/navegador/test_janela_parada.py -q`.
- [x] **Implementar.**
- [x] **Ver passar** e ruff.

### T218: Grupo "Sites com login"
`depende_de: T203, T204, T211, T215` · D132.8, D132.23, D132.41, D132.48

**Arquivos:** modificar `src/jobot/painel/rotas/configuracoes.py` (`GRUPOS`, `_PARCIAIS`, `_CONTEXTOS`, `_GRAVADORES`, abas filtradas), `src/jobot/painel/i18n/{pt,en}/configuracoes.json`; criar `src/jobot/painel/templates/configuracoes/sites_com_login.html`; testes em `tests/integracao/test_rota_sites_com_login.py` e `tests/tela/test_sites_com_login.py`.

**Interfaces (produz):** `"sites-com-login"` no fim de `GRUPOS`; `grupos_visiveis(leitores: Sequence[LeitorComLogin]) -> tuple[str, ...]`; rota do grupo dá 404 sem leitor (GET e POST); contexto com a frase de risco, `getattr(app.state, "navegador_instalado", None)` (a rota nunca sobe o driver, E8), um cartão por leitor (`nome`, interruptor `.chave` com `role="switch"` ligado a `ligada`, última linha de saúde com motivo por `t()`, `rodando` = execução `login` em `rodando`), horários num `.campo-texto` e o botão "Esquecer logins" (o fluxo é da T219). Nesta tarefa o painel não importa `jobot.navegador`: lê só o `app.state`. O interruptor grava na hora por `ligar_fonte` (POST com CSRF); horários tortos voltam 422 com a mensagem da chave de `horarios_validos`, sem gravar.

- [x] **Teste que falha:**
  - `test_sem_leitor_a_aba_nao_aparece` e `test_sem_leitor_rota_da_404[GET|POST]`.
  - `test_com_leitor_interruptor_nasce_desligado_e_grava`.
  - `test_cartao_mostra_leitura_rodando` e `test_cartao_mostra_o_motivo_da_ultima` (`saude.precisa_login` nos dois idiomas).
  - `test_horarios_tortos_voltam_422_sem_gravar` (parametrizado com os quatro casos da T204) e `test_horarios_validos_gravam`.
  - `test_estado_do_navegador[chrome|chromium|nenhum]` (pelo `app.state`).
  - `test_aba_nao_sobe_o_driver`: `navegador.abrir.async_playwright` trocado por um falso que levanta; `GET` da aba dá 200.
  - `test_textos_do_grupo_em_pt_e_en` e `test_nenhum_checkbox_sem_chave`.
  - Tela: `test_interruptor_do_site_grava_na_hora` (espera a resposta real; o estado vem do `checked`).
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_sites_com_login.py -q`.
- [x] **Implementar.** Cor nova só com par em `test_contraste_minimo`.
- [x] **Ver passar**, o arquivo de tela da tarefa e ruff.

### T219: "Fazer login agora" e "Esquecer logins"
`depende_de: T218` · D132.18, D132.21, D132.22, D132.52

**Arquivos:** criar `src/jobot/navegador/login_manual.py`, `tests/navegador/test_login_manual.py`; modificar `configuracoes.py` (rotas do grupo), o template e os catálogos da T218, `wiki/Arquitetura.md` e `wiki/Architecture.md` (seta `painel --> navegador`, o primeiro import do painel no pacote); testes em `tests/integracao/test_rota_sites_com_login.py` e `tests/tela/test_sites_com_login.py`.

**Interfaces (produz):** `async def fazer_login(leitor, deps: Dependencias, relogio: Relogio) -> Literal["pronto", "tempo_esgotado", "sem_tela", "sem_navegador", "fechado"]` (abre na `url_login`, só `content()`/`url` a cada 5 s, até `PRAZO_LOGIN_MANUAL_S`; `pagina_logada` verdadeira → fecha e `"pronto"`); a rota a chama dentro de `async with dependencias_de_producao(dados, env) as deps`. Rotas, todas 404 sem leitor: `POST /configuracoes/sites-com-login/{chave}/login` (trava presa → fragmento "Uma leitura está em andamento; tente de novo quando terminar."; livre → pega a trava antes de qualquer `await`, dispara em `app.state.tarefas`, guarda o estado em `app.state.login_manual[chave]`), `GET .../{chave}/login` (fragmento do estado, para o HTMX), `POST /configuracoes/sites-com-login/esquecer` (fragmento de confirmação "Apagar os logins de todos os sites?" com "Apagar" e "Cancelar") e `POST .../esquecer/confirmar` (trava presa → "em andamento"; livre → `apagar_perfil(dados)` e "Logins apagados"). Chave desconhecida: 404.

- [x] **Teste que falha:**
  - `test_fazer_login_espera_e_fecha_quando_logado` (o teste preenche o formulário do site falso; o joBot não: `campos_mudados` só os do teste) e `test_fazer_login_desiste_em_10_minutos`.
  - `test_sem_leitor_rotas_de_login_e_esquecer_dao_404` (as quatro rotas).
  - `test_login_agora_com_trava_presa_responde_em_andamento`.
  - `test_esquecer_pede_confirmacao_e_so_apaga_no_segundo_post`: depois do primeiro POST a pasta existe; depois do segundo não; contagem de `vaga` e `ocorrencia` igual.
  - `test_esquecer_com_leitura_rodando_nao_apaga`.
  - `test_esquecer_com_navegador_symlink_nao_apaga_o_alvo` (RF1).
  - Tela: `test_esquecer_logins_confirma_na_pagina` (sem `page.on("dialog")`).
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_sites_com_login.py -k "login_agora or esquecer or 404" -q` e `uv run pytest tests/navegador/test_login_manual.py -q`.
- [x] **Implementar.**
- [x] **Ver passar**, `test_navegador_ast.py`, `tests/unidade/test_arquitetura.py` e ruff.

### T220: `scripts/capturar_logado.py`
`depende_de: T211, T212, T213` · D132.12, D132.22, D132.53, D132.54

**Arquivos:** criar `scripts/capturar_logado.py`, `tests/unidade/test_capturar_logado.py`, `tests/navegador/test_capturar_logado_site.py`; modificar a docstring de `scripts/capturar.py:1`, `src/jobot/sistema/instancia.py`, `src/jobot/sistema/abrir.py` e `src/jobot/sistema/atualizar.py`; testes em `tests/unidade/test_abrir.py` e `tests/unidade/test_atualizar.py` (`sair_do_servidor` e `abrir_painel` em `abrir.py:130` e `:91`; `atualizar` em `atualizar.py:197`).

O script não importa `playwright`: usa `dependencias_de_producao`, `abrir_contexto` e `ouvir_respostas` de `jobot.navegador`, e as chamadas que faz ao contexto e à página (`new_page`, `goto`, `content`, `close`) passam pela lista permitida (`test_lista_permitida_do_navegador` já o inclui, T207; `test_so_navegador_importa_playwright` já olha `scripts/`, T196).

**Interfaces (produz):** `MARCADOR = "<limpo>"`; `limpar_logado(texto: str, tipo: str, campos: Sequence[str]) -> tuple[str, frozenset[str]]` (troca valores de campos JSON com `csrf`/`xsrf` no nome, JWT `eyJ...` de três partes, `JSESSIONID=...`, e cada posição de `campos` (nome de campo JSON ou seletor CSS pelo `selectolax`); devolve o texto e os valores trocados, só em memória); `conferir_logado(texto: str, trocados: frozenset[str]) -> list[str]` (achados por posição ou tipo, nunca o valor: JWT, `JSESSIONID`, `csrf`/`xsrf` fora do marcador, valor trocado em qualquer lugar, e `achar_pessoais`); `meta_logado(url: str, status: int, tipo: str) -> dict[str, object]` (os `CAMPOS_META` de `capturar.py:82`; `url` com a query só com os nomes e sem fragmento; `cabecalhos = {}`, sem nenhum cabeçalho, logo sem `Set-Cookie`); o meta serializado passa por `limpar_logado` e por `conferir_logado` como os corpos. `main(argv) -> int`: `[<leitor>] --caso <nome> [--host H]... [--campo C]...`; com leitor, captura as respostas dos `hosts` dele que casam com `respostas` e abre na `url_entrada`; sem leitor (A10), `--host` é obrigatório (sem ele, código 2), grava todo JSON e o HTML final desses hosts e abre no primeiro; segura `Trava(dados, 0)` (`sistema/instancia.py:18`: porta 0 porque o script não serve nada, e `porta_do_servidor` fica `None`; trava presa → 1 com mensagem), espera o Enter no terminal, limpa, `limpar_pessoais`, `reduzir`, confere, grava em `tests/fixtures/<chave ou caso>/` só se tudo passa e roda `problemas` na pasta.

**Trava sem porta:** todo servidor grava porta de 1 a 65535 (`instancia.py:89-94`, `cli/servir.py:192-193`); trava presa com porta `None` é a captura. Hoje três lugares a tratariam como servidor: `jobot sair` (`abrir.py:134-139`) daria SIGTERM na captura; `jobot atualizar` (`atualizar.py:224`, `:139`, `:163`) mataria o script e subiria um servidor; `abrir_painel` (`abrir.py:23-35`, `:82-88`, `:115-121`) esperaria 15 s com mensagem enganosa. Produz `captura_em_andamento(dados: Path) -> bool` em `sistema/instancia.py` (`pid` presente e porta `None`, numa leitura só por `pid_e_porta_do_servidor`); os três lugares a consultam primeiro e saem com código 1 e a mensagem fixa "Uma captura de exemplos com login está em andamento. Encerre-a no terminal dela e tente de novo.", sem SIGTERM, sem subir e sem esperar. Texto em português direto no código, como as mensagens vizinhas de `abrir.py` e `atualizar.py` (o `sistema` não usa catálogo).

- [x] **Teste que falha** (nome inventado `Fulana Exemplo`, id `u-998877`):
  - `test_limpa_e_passa`: corpo com `csrf_token`, `xsrfToken`, JWT, `JSESSIONID`, `$.conta.id` e `$.conta.nome` em `campos` → tudo `<limpo>` e `conferir_logado == []`.
  - `test_residuo_recusado_sem_mostrar_o_valor`: `u-998877` repetido numa URL do corpo, e um `csrf` não declarado fora do marcador → achados não vazios e nenhum traz `u-998877`.
  - `test_limpeza_acha_pela_posicao`: `Fulana Exemplo` numa posição não declarada fica no texto.
  - `test_email_e_telefone_saem_ou_recusam`.
  - `test_meta_sem_cookie_cabecalho_nem_valor_de_query` (com `?id=u-998877` na URL: o meta traz `id` e não o valor; `cabecalhos == {}`).
  - `test_sem_leitor_exige_host`.
  - `test_com_jobot_lock_preso_recusa` e `test_segura_o_jobot_lock_sem_porta` (`porta_do_servidor(dados) is None` enquanto roda).
  - Com uma `Trava(dados, 0)` presa pelo teste: `test_sair_nao_mata_a_captura` (`os.kill` trocado por espião sem chamada; código 1 e a mensagem), `test_atualizar_com_captura_recusa_e_nao_sobe_servidor` (`parar` e `subir` falsos sem chamada; código 1), `test_abrir_com_captura_avisa_na_hora` (`subir` sem chamada, `e_o_jobot` sem chamada, código 1).
  - Tela (`tests/navegador/test_capturar_logado_site.py`): `test_captura_do_site_falso_grava_limpa` com o Enter simulado e o lançador de teste.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_capturar_logado.py -q` e os três testes da trava sem porta pelo nome (`-k "captura"` nos arquivos de `abrir` e `atualizar`).
- [x] **Implementar.**
- [x] **Ver passar**, o teste de tela da tarefa, `tests/unidade/test_camadas.py`, `test_navegador_ast.py` e ruff (`MYPYPATH=src` para o mypy dos scripts no CI).

### T221: Correções da rodada de segurança da Parte A

A T221 corrigiu os 2 achados de gravidade baixa da rodada de segurança da Parte A (D134).

### REG24: Registros da Parte A
`depende_de: T196 a T220`

Só documentos: a D133 do `duvidas.md` (já criada com este plano) ganha o que mudar na execução; D132 marcada com o que foi entregue; lições novas em `registros/padroes.md` (teto de 64 linhas); este plano com a frase "como foi testado" de cada tarefa conferida por `grep` de `def <nome>`. Sem CHANGELOG, README nem ADR (D132.13, D132.23).

**Como conferir:** `uv run pytest tests/unidade/test_documentos.py -q` e ruff.

## R4: para o `duvidas.md` (na D133)

1. **Página logada com campo de senha escondido** (D132.37). O desenho trata como login toda página com `input[type=password]`; sites logados às vezes trazem um formulário de login escondido, e o site viraria `precisa_login` para sempre. Opções: (a) qualquer campo de senha, como no desenho; (b) só campo visível; (c) (a) mais um `e_login` do leitor que pode dizer "não é login". Recomendação: (a) na Parte A, que é a mais segura para nunca injetar em login, e rever com a fixture real do primeiro site; (c) só se a fixture mostrar o problema, porque muda o contrato do leitor.
2. **Cidades no `ContextoColeta`** (D132.35). Opções: (a) termos × países, como no desenho; (b) levar `busca.cidades` ao `ContextoColeta`, o que muda o contrato de todos os coletores. Recomendação: (a) e decidir (b) na Parte B, site por site, se a busca do site pedir cidade.
3. **Leitores falsos fora de `src/`.** O desenho fala de "um leitor de exemplo do site falso" sem dizer onde mora. Opções: (a) `tests/apoio/site_falso.py`, sem nada no pacote publicado; (b) um leitor de exemplo em `src/jobot/nucleo/leitores/`, que apareceria no registro. Recomendação: (a), que mantém a D132.23 (nada visível); este plano segue (a).

## Para a Parte B

- Cartão da fonte com login na página de saúde (`painel/rotas/fontes.py:146`): hoje a "próxima" sai da agenda da busca pública (`inicio_da_ultima_completa(con, "busca")`); para uma fonte com login precisa vir do próximo horário de `login_horarios`. Sem leitor registrado o cartão não aparece na Parte A; vira tarefa nova no plano da Parte B.
- `app.state.navegador_instalado` calculado só ao subir o `serve` (shortcut da T215): o botão "Baixar o navegador" atualiza esse valor quando terminar, e a aba deixa de pedir reinício.

Tarefas novas que a execução da Parte A deixou (D134):

- Provar o `close` do contexto no `test_janela_parada` pelo evento `close`, não por `pages == []` (fechar a aba já esvazia a lista). (T222, plano das sobras)
- Falso positivo do `achar_widget`: ele devolve `None` também por timeout no `get_attribute`, e `None` não prova "sem desafio". (T223, plano das sobras)
- Desafio no detalhe parado na janela sem gravar `saude.captcha`. (T224, plano das sobras)
- A pessoa fecha só a aba parada e a execução espera o prazo inteiro da janela. (T225, plano das sobras)
- `PRAZO_COFRE_S` em dois lugares (`navegador/limites.py` e `painel/rotas/servicos.py`): um lugar só, e cache do cofre na Cola. (T226, plano das sobras)
- Mensagem do `serve` quando há uma captura no ar. (T227, plano das sobras)
- Mover `ESPERA_ASSENTAR_MS`, `_PASSOS_DEPOIS_DE_ROLAR` e `ESPERAS_LIMITE[0]` de `navegador/pagina.py` para `navegador/limites.py`. (T228, plano das sobras)
- Aviso no computador no idioma da pessoa (na Parte A sai só em português; o idioma entra por `Dependencias`). (T229, plano das sobras)
- Com fixture real: `div` invisível ou dentro de `<form>` tratada como desafio (rodada de segurança, T221).
- Downloads e service workers no contexto persistente: conferir os padrões do Playwright (rodada de segurança, T221). (T230, plano das sobras)
- O ambiente inteiro do `serve` passado ao Chrome (rodada de segurança, T221). (T231, plano das sobras)

## Autoconferência

- **Requisitos da Parte A com tarefa:** A1 (T196, T211), A2 (T196, T199, T200, T215), A3 (T198, T208, T219), A4 (T197), A5 (T201, T202, T203, T205, T213), A6 (T204, T206, T215), A7 (T207, T209, T210, T211, T212, T213, T214), A8 (T216, T217), A9 (T218, T219), A10 (T220), A11 (ordem acima, com a troca justificada da T215).
- **Nomes entre tarefas:** `LeitorComLogin`, `Captura`, `Leitura`, `EscopoLogado`, `ParadaLogin`, `Desfecho`, `parada_mais_forte` (T197) usados em T202, T209, T212, T213; `Login`, `pode_ler_agora` (T206) em T215; `inicio_da_ultima_leitura_login` (T204) em T206 e T215; `fontes_com_login_ligadas` (T202) em T206; `candidatas_a_detalhe` (T200) em T214; `Dependencias` e `dependencias_de_producao` (T213) em T215, T216, T217, T219, T220; `abrir_contexto`, `lancador_de_producao`, `navegador_instalado` (T211) em T213, T215, T218, T220; `ouvir_respostas` (T212) em T220; `Widget` (T216); `limites.py` criado na T211 e lido em T212 a T219; `NOME_NO_COFRE` (T216). Setas do diagrama: `navegador --> sistema` (T208), `navegador --> nucleo` (T209), `navegador --> banco` (T213), `cli --> navegador` (T215), `painel --> navegador` (T219).
- **Seção 8 do desenho:** 43 itens da Parte A, todos com teste nomeado numa tarefa (sites falsos em T212, T213, T214, T216, T217; unidade em T196, T197, T198, T199, T200, T204, T206, T207, T208, T209, T210, T211, T220; integração e painel em T203, T205, T206, T215, T218, T219). Fora: os leitores reais e o botão "Baixar o navegador" com o teste de privacidade, que são da Parte B.
