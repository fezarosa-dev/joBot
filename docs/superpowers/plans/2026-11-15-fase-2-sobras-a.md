# Fase 2, sobras da Parte A (T222 a T231): plano de implementação

> Cada tarefa roda num worktree próprio, tirado da `dev`, e passa por um revisor diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido. Erro de import, de coleta ou zero testes não vale como vermelho. Nome novo que o teste importa nasce como stub: aceita o parâmetro novo e o ignora, ou devolve o valor velho. Teste que nasce verde (guarda) só vale com o mutante descrito na tarefa, rodado numa cópia (`registros/padroes.md:27`).

**Objetivo:** fechar as dez tarefas que a execução da Parte A deixou na D134, sem mexer no que a pessoa já vê, antes do plano da Parte B. São três provas e correções na janela parada (T222, T224, T225), o falso negativo do `achar_widget` (T223), o cofre (T226), a mensagem do `serve` (T227), os limites espalhados (T228), o aviso no idioma da pessoa (T229) e o contexto do navegador (T230, T231).

**Arquitetura:** nenhum pacote, import entre pacotes, migração ou dependência novo. As mudanças ficam em `navegador/` (`execucao.py`, `captcha.py`, `pagina.py`, `abrir.py`, `limites.py`), em `painel/rotas/servicos.py` (só passa a ler `limites.PRAZO_COFRE_S`; a seta `painel --> navegador` já existe em `wiki/Arquitetura.md:59`) e em `cli/servir.py`. Os testes ficam em `tests/navegador/`, em `tests/unidade/test_navegador_abrir.py`, em `tests/integracao/` e no `tests/apoio/site_falso.py`.

**Base:** `dev` 840f43a.

**Desenho:** D132 (desenho da fase 2) e D134 (escolhas da execução da Parte A, itens 21, 27, 31, 36, 37 e 48). As escolhas deste plano estão na D135 (`duvidas.md`).

## Restrições globais

- Ler `registros/padroes.md` antes de cada tarefa. Valem principalmente as linhas 18, 24, 27, 31, 40, 41 e 43.
- Camadas: `navegador` importa `nucleo`, `banco` e `sistema`, nunca `painel`, `agenda` ou `cli`. O `painel` já importa `jobot.navegador.limites` (`painel/rotas/configuracoes.py:37`).
- Limites e prazos, inclusive os técnicos, moram em `navegador/limites.py` e se leem como `limites.X`. O `monkeypatch` vai no módulo `limites` (`registros/padroes.md:40`).
- Lista permitida do Playwright (`tests/unidade/test_navegador_ast.py:28-53`): fora de `js.py`, só as chamadas de `PERMITIDOS` e os eventos `response`, `request` e `close`. `is_closed` e `clear` não estão na lista. A aba fechada se descobre pelo evento `close`.
- Fechar o contexto se prova pelo evento `close`, nunca por `pages == []` (`registros/padroes.md:43`).
- Comportamento trocado atualiza a D de origem na mesma entrega (`registros/padroes.md:18`). A tarefa acrescenta "(trocada pela Tn, D135.m)" ao item da D134 que ela troca, e corrige a lição de `registros/padroes.md` que deixou de valer.
- Texto novo para quem usa sai em `pt` e `en`. A frase do aviso não leva endereço, chave nem token.
- Nenhum teste espera tempo real: o relógio vem injetado (`RelogioDoNavegador`, `tests/apoio/site_falso.py:591`) e a janela usa `limites.JANELA_PARADA_S = 60` nos testes.
- Sem dependência nova, sem migração. Playwright continua `==1.65.1`.
- Nesta máquina rodam só o arquivo de teste da tarefa e `uv run ruff check && uv run ruff format --check`. A suíte inteira, o `-m tela` e o `uv run mypy` rodam no CI da branch `lote/<nome>`. Antes do push: mypy nos `.py` mexidos e `uv run pytest tests/unidade` (`registros/padroes.md:25`).
- Desvios: R1 a R3, quem implementa resolve e lista. R4 (arquitetura, dependência, esquema, contrato público) vai ao `duvidas.md` com opções e recomendação, e o resto da tarefa segue.

## Escolhas deste plano (D135, para confirmar)

| # | Escolha | Teste |
|---|---|---|
| E1 | Estouro do `get_attribute` vira `Widget("nao_aceito", "", False, None, None)`. A página para como `captcha`, a não ser que seja página logada com 200 (`pagina.py:225-230`). Página que troca no meio continua dando `None`. Um estouro passageiro na olhada da janela faz o site ler a página de novo uma vez; é aceito. | `test_estouro_ao_ler_atributo_vira_desafio_nao_aceito`, `test_pagina_trocando_no_meio_continua_sem_widget` |
| E2 | Parada no detalhe grava a linha de saúde do site com escopo `''`, pelo `estado_do_escopo`. Troca a D134.27. | `test_parada_no_detalhe_grava_a_saude_do_site` |
| E3 | Aba parada que a pessoa fecha encerra a espera dela. O site grava `captcha` logo, as outras abas seguem no prazo e a execução fecha `concluida`. Antes de decidir que foi só a aba, a espera aguarda até `limites.ESPERA_FECHAR_S` pelo fechamento do navegador; se ele vier, a execução para como `fechado`. | `test_fechar_a_aba_parada_encerra_a_espera`, `test_fechar_uma_aba_nao_encerra_a_espera_da_outra`, `test_fechar_o_navegador_com_a_janela_parada_interrompe` |
| E4 | `PRAZO_COFRE_S` fica só em `navegador/limites.py`; `painel/rotas/servicos.py` lê `limites.PRAZO_COFRE_S` na hora da chamada. | `test_prazo_do_cofre_definido_uma_vez` |
| E5 | A chave do 2Captcha é lida do cofre uma vez por execução (`ChaveDoCofre`), e todas as abas usam essa leitura. O prazo estourado também fica guardado, então custa um prazo por execução. | `test_chave_lida_do_cofre_uma_vez_por_execucao`, `test_cofre_que_nao_responde_custa_um_prazo_por_execucao`, `test_duas_leituras_ao_mesmo_tempo_leem_o_cofre_uma_vez` |
| E6 | `serve` com captura no ar imprime o `AVISO_CAPTURA` que já existe (`sistema/instancia.py:97-100`). É só em português, como as outras mensagens do terminal. | `test_serve_com_captura_no_ar_diz_qual_e` |
| E7 | Três nomes novos em `limites`: `ESPERA_ASSENTAR_MS = 10_000`, `PASSOS_DEPOIS_DE_ROLAR = 5` (público, porque `pagina.py` o lê de outro módulo e o `test_nomes_publicos` recusa nome com `_` importado de outro módulo, `registros/padroes.md:25`) e `ESPERA_429_S = ESPERAS_LIMITE[0]` (um número só, o de `nucleo/http.py:21`). | `test_limites_da_pagina_moram_em_limites`, `test_429_sem_retry_after_espera_o_padrao`, `test_passos_depois_de_rolar_vem_de_limites` |
| E8 | O idioma do aviso vem da config `idioma` no banco, lida no começo da execução, e não por `Dependencias` (troca a forma da D134.37). Sem idioma salvo ou com valor estranho, sai em `pt`. As duas frases ficam em `navegador/execucao.py`, porque `navegador` não importa `painel`. | `test_aviso_sai_no_idioma_da_pessoa` |
| E9 | `accept_downloads=False` e `service_workers="block"` vão nas duas chamadas de `abrir_contexto`. Assim o site falso também roda com eles e prova que as respostas continuam sendo lidas. | `test_contexto_sem_downloads_nem_service_workers` |
| E10 | O `env` do Chrome leva só `PATH`, `HOME`, `USER`, `LOGNAME`, `LANG`, `LC_ALL`, `LANGUAGE`, `TMPDIR`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_DATA_DIRS`, `XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE` e `DBUS_SESSION_BUS_ADDRESS` do `os.environ`, mais o ambiente da tela já validado (`DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `XDG_RUNTIME_DIR`, de `sistema/tela.py:13`). Nenhuma delas carrega segredo, e as `XDG_*`, `TMPDIR`, `USER` e `LOGNAME` são as que o Chrome costuma ler para pastas, área de trabalho e usuário. A abertura com tela se confere à mão (T231). | `test_lancador_de_producao_passa_so_o_ambiente_do_navegador` e a verificação manual da T231 |
| E11 | O fechamento do contexto no `test_janela_parada` se prova pelo evento `close`, não por `pages == []`. A linha `pages == []` que sobrava no teste de cancelar sai. | `test_captcha_sem_2captcha_para_a_janela`, `test_duas_abas_dividem_os_15_minutos` |

## Foco da revisão

| # | Entrada ou condição | O que a pessoa espera | Teste | Tarefa |
|---|---|---|---|---|
| RF1 | A pessoa fecha a aba do desafio em vez de resolver | O joBot não fica 15 minutos esperando por nada. O site aparece com "captcha" e os outros sites seguem | `test_fechar_a_aba_parada_encerra_a_espera` | T225 |
| RF2 | Desafio aparece só na página de uma vaga | A página de saúde mostra o site como parcial por CAPTCHA, não como "ok" | `test_parada_no_detalhe_grava_a_saude_do_site` | T224 |
| RF3 | Cofre do sistema travado esperando senha, com três sites com desafio | Espera de no máximo um prazo (15 s), não um por site | `test_cofre_que_nao_responde_custa_um_prazo_por_execucao` | T226 |
| RF4 | Página que demora a responder ao `get_attribute` do widget | O desafio não passa como página limpa | `test_estouro_ao_ler_atributo_vira_desafio_nao_aceito` | T223 |
| RF5 | Variável com segredo no ambiente do `serve` (token, chave de API) | Ela não chega ao processo do Chrome | `test_lancador_de_producao_passa_so_o_ambiente_do_navegador` | T231 |
| RF6 | Site que manda baixar um arquivo | Nada é baixado para o disco | `test_contexto_sem_downloads_nem_service_workers` | T230 |
| RF7 | Painel em inglês | O aviso do computador sai em inglês | `test_aviso_sai_no_idioma_da_pessoa` | T229 |

## Ordem

| Onda | Tarefas | Por quê |
|---|---|---|
| 1 | T222, T223 | arquivos separados; T222 mexe no `test_janela_parada.py`, que T224, T225, T226 e T229 também mexem |
| 2 | T224, T228 | T224 depois da T222 (mesmo arquivo de teste) |
| 3 | T225, T227 | T225 depois da T224 (`execucao.py`, `test_janela_parada.py`) e da T228 (`limites.py`: a T228 acrescenta nomes, a T225 troca o comentário do `ESPERA_FECHAR_S`) |
| 4 | T226, T230 | T226 depois da T223 (`captcha.py`) e da T225 (`execucao.py`, `test_janela_parada.py`); T230 depois da T228 (`test_navegador_abrir.py`) |
| 5 | T229, T231 | T229 depois da T226 (`execucao.py`); T231 depois da T230 (`abrir.py`, `test_navegador_abrir.py`) |

Em cada onda as duas tarefas não dividem arquivo, fora o `duvidas.md`, que cada tarefa edita em linha própria da D132 ou da D134 (T224 e T228 na onda 2, T225 e T227 na onda 3); quem junta resolve o conflito de borda. `execucao.py` passa por T224, T225, T226 e T229 em sequência: as tarefas citam o símbolo (`_Janela.parar`, `_ler_site`, `executar_login`), não a linha, e quem implementa confere o lugar pelo símbolo (`registros/padroes.md:18`). Junte a onda na `dev` antes de abrir a seguinte. As tarefas que acrescentam teste no fim do mesmo arquivo dariam conflito certo (`registros/padroes.md:23`).

---

### T222: `close` do contexto provado pelo evento
`depende_de: —` · D134 (tarefa nova 1)

**Arquivos:** modificar `tests/navegador/test_janela_parada.py` e `tests/navegador/test_execucao_logada.py`.

**Interfaces:** `Montagem` (`test_janela_parada.py:84-111`) ganha `fechamentos: list[datetime]`. O `lancar` da fixture `montagem` (`:114-146`) registra `contexto.on("close", lambda _: m.fechamentos.append(m.relogio.agora()))`. Não há código de produção.

- [ ] **Teste que falha (mutante):** em `test_captcha_sem_2captcha_para_a_janela` (`:216`), troque `assert montagem.contextos[0].pages == []` (`:247`) por `assert len(montagem.fechamentos) == 1  # o contexto fechou no fim`. Faça o mesmo em `test_duas_abas_dividem_os_15_minutos` (`:341`). Em `test_cancelar_a_leitura_fecha_o_navegador` (`test_execucao_logada.py:686`), apague a linha 705 (`pages == []`): a 704 (`fechou.is_set()`) já prova o fechamento.
- [ ] **Ver falhar com o mutante:** numa cópia, tire o `await contexto.close()` do `finally` de `executar_login` (`navegador/execucao.py:170-174`). `uv run pytest tests/navegador/test_janela_parada.py -q` reprova os dois testes, e com `pages == []` eles passavam.
- [ ] **Implementar:** nada além do teste.
- [ ] **Ver passar** sem o mutante, com `uv run pytest tests/navegador/test_janela_parada.py tests/navegador/test_execucao_logada.py -q`, e depois `uv run ruff check && uv run ruff format --check`.

### T223: estouro do `get_attribute` não passa como página limpa
`depende_de: —` · D134 (tarefa nova 2), D135.1

**Arquivos:** modificar `src/jobot/navegador/captcha.py`, `tests/navegador/test_captcha_logado.py` e `registros/padroes.md:41` (a frase "devolve `None` também por timeout" deixa de valer).

**Interfaces:** `achar_widget(page) -> Widget | None` (`captcha.py:67-85`) ganha `except EstouroDoPlaywright: return Widget("nao_aceito", "", False, None, None)` antes do `except ErroDoPlaywright: return None` (`:83`). O import é `from playwright.async_api import TimeoutError as EstouroDoPlaywright`, o mesmo alias de `pagina.py:17`. O `_atributo` (`:55-56`) não muda.

**Recarga aceita:** na olhada da janela, um estouro passageiro troca o widget da marca por `nao_aceito`, a parada conta como saída e o site lê a mesma página de novo uma vez (`_Site.ir`, `execucao.py:320-322`). Se o desafio continua, a página para de novo e volta à janela no mesmo prazo. Custa uma leitura a mais, não o prazo, e o `None` de antes fazia o mesmo. Fica assim.

- [ ] **Teste que falha:** com uma página falsa (`locator(...).all()` devolve um alvo cujo `get_attribute` levanta `playwright.async_api.TimeoutError("estourou")`):
  - `test_estouro_ao_ler_atributo_vira_desafio_nao_aceito`: `assert await achar_widget(pagina) == Widget("nao_aceito", "", False, None, None)`.
  - `test_pagina_trocando_no_meio_continua_sem_widget` (guarda): o mesmo alvo levanta `ErroDoPlaywright("Execution context was destroyed")`, e `assert await achar_widget(pagina) is None`. O mutante que troca `EstouroDoPlaywright` por `ErroDoPlaywright` (ou por `Exception`) na nova cláusula precisa reprovar `test_pagina_trocando_no_meio_continua_sem_widget`.
- [ ] **Ver falhar:** `uv run pytest tests/navegador/test_captcha_logado.py -q -k "estouro or trocando"`. O primeiro falha com `None == Widget(...)`.
- [ ] **Implementar** a cláusula e atualizar a docstring: "`None` sem widget ou com a página trocando no meio; estouro de prazo é desafio não aceito".
- [ ] **Ver passar:** `uv run pytest tests/navegador/test_captcha_logado.py -q`, depois o portão de ruff.

### T224: desafio no detalhe grava `saude.captcha`
`depende_de: T222` · D134.27 (trocada), D135.2

**Arquivos:** modificar `src/jobot/navegador/execucao.py`, `tests/apoio/site_falso.py`, `tests/navegador/test_janela_parada.py` e `duvidas.md` (só o sufixo no item 27 da D134).

**Interfaces:**
- No `_detalhar_site`, o ramo `if not isinstance(visita, Captura)` passa a fazer `desfecho = estado_do_escopo((), parada=visita, cortada=False, tres_ok_com_vagas=False)` e `site.saude(desfecho.estado, desfecho.motivo)` antes do `return`. É o mesmo par do `_ler_paginas`. O log continua. Vale para toda parada no detalhe (`precisa_login`, `bloqueio`, `captcha`, `no_limite`).
- No site falso, a rota `/lista-desafio-na-vaga` devolve `_pagina("Vagas", _lista_html([77]))`, e a `/lista-bloqueio-na-vaga` devolve `_pagina("Vagas", _lista_html([78]))`. Os `case "/vaga/77"` e `case "/vaga/78"` vêm antes do genérico (`site_falso.py:500`): o 77 devolve o widget de `/recaptcha-v2` (`:413-415`) e o 78 devolve 403, como o `/403` (`:359-360`).

- [ ] **Teste que falha:** `test_parada_no_detalhe_grava_a_saude_do_site`, parametrizado com `("/lista-desafio-na-vaga", ("falhou", "saude.captcha"), 1)` e `("/lista-bloqueio-na-vaga", ("falhou", "saude.bloqueio"), 0)` (caminho, saúde do site, avisos). Monte `captcha_ligado` `False` e `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)`. O leitor é `LeitorFixo(base=..., urls=(("python", caminho),), lista_tem_descricao=False)`.
  - `assert _saude(con, execucao_id) == {("falso_logado", "python"): ("ok", None), ("falso_logado", ""): saude}`
  - `assert len(montagem.avisos) == avisos` (o 403 não abre a janela parada)
  - `assert estado_da_fonte([estado for (fonte, _), (estado, _) in _saude(con, execucao_id).items() if fonte == "falso_logado"]) == "parcial"`, com `from jobot.nucleo.coletores.executor import estado_da_fonte` (`executor.py:134-143`). Vale nos dois casos: um escopo `ok` e a linha do site `falhou`. No caso do captcha, o motivo do site é `saude.captcha`, que a primeira asserção já prende, e é o que `motivo_mais_grave` (`painel/rotas/fontes.py:87-92`) mostra.
- [ ] **Ver falhar:** `uv run pytest tests/navegador/test_janela_parada.py -q -k detalhe`. Hoje falta a chave `("falso_logado", "")` nos dois casos.
- [ ] **Implementar** as duas linhas e a rota. Na D134, item 27, acrescente "(trocada pela T224, D135.2)".
- [ ] **Ver passar:** `uv run pytest tests/navegador/test_janela_parada.py tests/navegador/test_detalhe_logado.py -q`, depois o portão de ruff.

### T225: fechar a aba parada encerra a espera dela
`depende_de: T224, T228` · D134 (tarefa nova 4), D135.3

**Arquivos:** modificar `src/jobot/navegador/execucao.py`, `src/jobot/navegador/limites.py` (só o comentário do `ESPERA_FECHAR_S`), `tests/navegador/test_janela_parada.py`, `duvidas.md` (sufixo no item 6 de "Para confirmar" da D132) e `docs/superpowers/specs/2026-11-15-fase-2-design.md` (uma frase no item "Janela parada (D132.26)").

**Interfaces:**
- `_Parada` ganha `fechada: asyncio.Event`.
- `_Janela.parar` registra o ouvinte na primeira linha útil, antes do `_marca` e do `await asyncio.to_thread(self._avisar, ...)`: `fechada = asyncio.Event()` e `aba.on("close", lambda _: fechada.set())`. Depois passa `fechada` ao `_Parada`. Registrar só ao criar a `_Parada` deixa uma corrida: a pessoa fecha a aba logo ao ver o aviso, o `close` chega antes do ouvinte e a espera vai ao prazo inteiro. `on` e `close` estão na lista permitida.
- `_Janela.esperar`, em cada olhada, depois do `if self.fechado.is_set(): raise NavegadorFechado` que já existe e antes do `_marca`, trata a parada cuja `fechada.is_set()`:
  - Primeiro espera até `limites.ESPERA_FECHAR_S` pelo `self.fechado`, com o mesmo `asyncio.timeout` sobre `fechado.wait()` do `_fechou` (D134.24). Quem implementa pode separar essa espera numa função que os dois usam. Motivo: quando o navegador inteiro fecha, o `close` da aba pode chegar antes do `close` do contexto, e sem a espera o fechamento do navegador passaria por fechamento só da aba.
  - Se o `fechado` vier, levanta `NavegadorFechado`, e a execução para como `fechado`, como hoje.
  - Se não vier, tira a parada de `_paradas` e chama `await self._seguir(parada, False)`. O site recebe `captcha` na hora. A soma do prazo e as outras abas não mudam.
- `ESPERA_FECHAR_S` já existe (`limites.py:22`) e não muda de valor. O comentário acima dele (`:20-21`) diz "só nesse caminho de erro" e passa a citar também a aba parada que fechou.
- O `finally` de `_ler_site` já engole o `close` de uma aba fechada.

- [ ] **Teste que falha:** `test_fechar_a_aba_parada_encerra_a_espera`, parametrizado com `"logo"` e `"depois"`. Monte `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)` e `monkeypatch.setattr(limites, "ESPERA_FECHAR_S", 0.05)` (como `test_execucao_logada.py:512`: aqui o navegador não fecha, e a espera iria ao fim). Um site parado em `/recaptcha-v2`, sem 2Captcha.
  - `"logo"`: a pessoa fecha a aba enquanto o aviso aparece. A aba fecha de dentro do aviso falso, então a ordem é fixa e não depende de corrida.
    - Antes de `montagem.deps(...)`, pegue `loop = asyncio.get_running_loop()` e troque o aviso com `monkeypatch.setattr(montagem, "avisar", avisar_e_fechar)`. O `deps` lê `self.avisar` na hora (`test_janela_parada.py:107`), então pega o novo.
    - `avisar_e_fechar(titulo, frase)` grava em `montagem.avisos` como o `Montagem.avisar` e roda `asyncio.run_coroutine_threadsafe(fechar_aba(), loop).result()`. `fechar_aba` é `async def` e faz `await montagem.aba("/recaptcha-v2").close()` e depois `assert "/recaptcha-v2" in dict(montagem.fechadas)`.
    - O aviso roda numa thread (`asyncio.to_thread` em `_Janela.parar`), e o `.result()` só solta depois que o `close()` voltou. A aba fecha antes do `to_thread` voltar e antes da parada entrar em `_paradas`.
    - O `assert` dentro do `fechar_aba` prova que o evento `close` da aba chegou antes de o `close()` voltar: o ouvinte da `montagem` (`ao_abrir`) já gravou. Se essa ordem não valer na versão do Playwright, o teste quebra ali, e não passa por acaso.
  - `"depois"`: trave o relógio com o mesmo truque do `resolvido` de `test_duas_abas_dividem_os_15_minutos` (`:296-302`). Depois do aviso, `await montagem.aba("/recaptcha-v2").close()` e `resolvido.set()`.
  - Nos dois: `assert sum(montagem.relogio.dormidas) <= limites.OLHAR_S`. Hoje dá `== limites.JANELA_PARADA_S` (60).
  - `assert _saude(...) == {("falso_logado", "python"): ("falhou", "saude.captcha")}`
  - `assert con.execute("SELECT estado FROM execucao WHERE id = ?", (execucao_id,)).fetchone() == ("concluida",)`
  - **Mutante do caso `"logo"`:** numa cópia, em `_Janela.parar`, mova o `aba.on("close", ...)` para depois do `await asyncio.to_thread(self._avisar, ...)`. Rode `uv run pytest tests/navegador/test_janela_parada.py -q -k "fechar_a_aba_parada and logo"`. Tem de falhar em `assert sum(montagem.relogio.dormidas) <= limites.OLHAR_S`, com 60: o `close` chegou antes do ouvinte, e a espera vai ao prazo inteiro.
- [ ] **Guarda:** `test_fechar_o_navegador_com_a_janela_parada_interrompe`. Hoje ele passa: a olhada acha o `fechado` e levanta `NavegadorFechado`. Só vale com o mutante abaixo, rodado numa cópia depois de implementar. É um nome novo, que não repete nenhum `def` do arquivo. Monte `captcha_ligado` `False`, `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)` e o mesmo truque do `resolvido`. O `ESPERA_FECHAR_S` fica no valor de produção, porque aqui o `close` do contexto chega. Um site parado em `/recaptcha-v2`.
  - Depois do aviso, `await montagem.aba("/recaptcha-v2").close()` (o navegador fecha as abas antes de fechar a si). Em seguida `resolvido.set()` e logo `await montagem.contextos[0].close()`, sem outro `await` entre os dois. A olhada acorda com a aba fechada e o contexto ainda fechando.
  - `assert con.execute("SELECT estado, parada FROM execucao WHERE id = ?", (execucao_id,)).fetchone() == ("interrompida", "fechado")`
  - Mutante: no caminho da aba fechada, tire a espera pelo `fechado` e o `raise`, e siga direto com `_seguir(parada, False)`. Rode `uv run pytest tests/navegador/test_janela_parada.py -q -k fechar_o_navegador`. Tem de falhar na asserção do estado, com `("concluida", None)`, porque o `executar_login` não olha o `fechado` depois do `esperar`.
  - Lacuna: com o navegador de verdade, a janela estreita (o `close` da aba entregue numa olhada e o do contexto só depois) não se força de jeito determinístico. Este teste cobre o caso em que o contexto ainda está fechando quando a olhada acorda, e o código segue o mesmo molde do `_fechou`.
- [ ] **Guarda:** `test_fechar_uma_aba_nao_encerra_a_espera_da_outra`. Monte `captcha_ligado` `False` e `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)`. Dois sites parados em caminhos diferentes com widget aceito, `/recaptcha-v2` e `/turnstile`, para `montagem.aba(caminho)` achar abas distintas; a pessoa fecha só a de `/recaptcha-v2`.
  - `sum(dormidas) == 60` e as duas saúdes ficam `captcha`.
  - O mutante que, quando uma aba fecha, segue todas as paradas com `False` precisa reprovar.
- [ ] **Ver falhar:** `uv run pytest tests/navegador/test_janela_parada.py -q -k fechar`.
- [ ] **Implementar.** Na D132, item 6 de "Para confirmar", acrescente "(complementada pela T225, D135.3)". No desenho, no item "Janela parada (D132.26)", acrescente: "Aba parada que a pessoa fecha encerra a espera daquele site: ele fica com `captcha` na hora, e as outras abas seguem no mesmo prazo."
- [ ] **Ver passar:** `uv run pytest tests/navegador/test_janela_parada.py -q`, depois o portão de ruff.

### T226: `PRAZO_COFRE_S` num lugar só e a chave lida uma vez por execução
`depende_de: T223, T225` · D134.36 (trocada), D135.4, D135.5

**Arquivos:**
- modificar `src/jobot/navegador/captcha.py`, `src/jobot/navegador/execucao.py` e `src/jobot/painel/rotas/servicos.py` (o `limites.PRAZO_COFRE_S` de `limites.py:25` fica como está);
- modificar `tests/navegador/test_captcha_logado.py`, `tests/navegador/test_janela_parada.py` e `tests/integracao/test_rota_servicos.py`;
- modificar `duvidas.md` (sufixo no item 36 da D134).

**Interfaces:**
- `servicos.py:31` perde `PRAZO_COFRE_S`. O `no_cofre` (`:38-47`) passa a usar `limites.PRAZO_COFRE_S` (com `from jobot.navegador import limites`). Os `monkeypatch.setattr(servicos, "PRAZO_COFRE_S", 0.05)` de `test_rota_servicos.py:358` e `:439` passam para `limites`.
- `captcha.py` ganha esta classe:
  `class ChaveDoCofre: def __init__(self, cofre: Cofre) -> None; async def ler(self) -> tuple[str, OndeGuardou] | None`
  - A primeira chamada faz o que hoje está em `resolver_na_pagina:104-112`: `asyncio.timeout(limites.PRAZO_COFRE_S)` sobre `asyncio.to_thread(cofre.ler, NOME_NO_COFRE)`, com o mesmo log no estouro.
  - Ela guarda o resultado, e o estouro fica guardado como `None`. As seguintes devolvem o guardado.
  - Um `asyncio.Lock` cobre a leitura.
- `resolver_na_pagina(..., chave: ChaveDoCofre, ...)` troca `cofre` por `chave`. `captcha_ligado` continua lido antes (`:102`).
- `Cola.__init__(page, *, con, cliente, relogio, chave: ChaveDoCofre)` (`:146-153`).
- `executar_login` cria `chave = ChaveDoCofre(deps.cofre)` uma vez e a passa ao `_ler_site`, que monta a `Cola`. `Dependencias.cofre` não muda.
- O helper `_cola` de `test_captcha_logado.py:134-137` passa a usar `chave=ChaveDoCofre(cofre)`.

- [ ] **Stub:** em `captcha.py`, `ChaveDoCofre.ler` com o comportamento de hoje, sem guardar nada: `asyncio.timeout(limites.PRAZO_COFRE_S)` sobre `asyncio.to_thread(cofre.ler, NOME_NO_COFRE)`, com o log no estouro, a cada chamada. `Cola` e `resolver_na_pagina` já aceitam `chave=` no lugar de `cofre=`, e o `executar_login` já cria a `ChaveDoCofre`. É o que deixa a coleta de `test_captcha_logado.py` passar (o helper `_cola` e o import de `ChaveDoCofre` a derrubariam) e faz o vermelho cair na asserção de leituras. O stub precisa do `asyncio.timeout`: sem ele, a thread presa no cofre travado nunca solta e o `finally` com `trava.set()` não chega a rodar.
- [ ] **Teste que falha:**
  - `test_prazo_do_cofre_definido_uma_vez` em `test_captcha_logado.py`. É o mesmo laço AST de `test_nome_no_cofre_definido_uma_vez` (`:574`): `assert achados == [("jobot/navegador/limites.py", "PRAZO_COFRE_S")]`. Hoje acha também `servicos.py`.
  - `test_chave_lida_do_cofre_uma_vez_por_execucao` em `test_janela_parada.py`. Use dois `LeitorFixo` (`falso_logado`, `outro_logado`) em `/recaptcha-passa`. O contador de leituras se define no próprio `test_janela_parada.py`, no molde da classe local `CofreContado` de `test_captcha_logado.py:551` ou do `_CofreContado` de `test_rota_servicos.py:342`; a de `test_captcha_logado.py` mora dentro de um teste e não se importa.
    - `assert lidos == [NOME_NO_COFRE]`. Com o stub dá `[NOME_NO_COFRE, NOME_NO_COFRE]`.
    - `assert api.pedidos.count("/createTask") == 2`. O `Api2Captcha` de `test_janela_parada.py:48-64` só tem `pedidos: list[str]`; o `tarefas()` é do outro arquivo.
  - `test_cofre_que_nao_responde_custa_um_prazo_por_execucao`. Monte o mesmo contador sobre `CofreFalso(trava=threading.Event())`, `monkeypatch.setattr(limites, "PRAZO_COFRE_S", 0.05)`, `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)` e dois sites em caminhos diferentes com widget aceito, `/recaptcha-v2` e `/turnstile`:
    - `assert lidos == [NOME_NO_COFRE]`. Com o stub dá duas leituras.
    - as duas saúdes ficam `captcha`
    - o `trava.set()` vai no `finally` (`registros/padroes.md:31`).
  - `test_duas_leituras_ao_mesmo_tempo_leem_o_cofre_uma_vez` em `test_captcha_logado.py`, para o `asyncio.Lock`. O cofre é um contador definido no próprio teste, no molde do `CofreContado` de `:551`. O `ler` dele grava o nome em `lidos` e conta as entradas simultâneas (`dentro` e `maximo`, sob um `threading.Lock`).
    - `chave = ChaveDoCofre(cofre)` e `a, b = await asyncio.gather(chave.ler(), chave.ler())`.
    - `assert lidos == [NOME_NO_COFRE]`, `assert a == b` e `assert maximo == 1`. Com o stub dá duas leituras.
    - Mutante: numa cópia, tire o `async with` do `asyncio.Lock` em `ChaveDoCofre.ler` e mantenha o guardado. As duas chamadas passam pela checagem do guardado antes de qualquer `to_thread` voltar, e o cofre é lido duas vezes. Rode `uv run pytest tests/navegador/test_captcha_logado.py -q -k ao_mesmo_tempo`. Tem de falhar em `assert lidos == [NOME_NO_COFRE]`. Essa é a asserção que mata o mutante. A do `maximo` fica junto, mas sozinha não é determinística, porque as duas threads podem não se sobrepor.
- [ ] **Ver falhar:** `uv run pytest tests/navegador/test_janela_parada.py tests/navegador/test_captcha_logado.py -q -k "cofre"`. O AST falha porque `servicos.py` ainda define o nome; os dois de execução e o das duas leituras ao mesmo tempo falham na asserção de leituras.
- [ ] **Implementar.** Na D134, item 36, acrescente "(trocada pela T226, D135.4 e D135.5)".
- [ ] **Ver passar:** `uv run pytest tests/navegador/test_captcha_logado.py tests/navegador/test_janela_parada.py tests/integracao/test_rota_servicos.py -q`, depois o portão de ruff.

### T227: `serve` diz que a captura está no ar
`depende_de: —` · D134.31 (trocada), D135.6

**Arquivos:** modificar `src/jobot/cli/servir.py`, `tests/integracao/test_servir.py` e `duvidas.md` (sufixo no item 31 da D134).

**Interfaces:** em `executar` (`cli/servir.py:243-245`), quando `_pegar(trava)` falha:
`print(AVISO_CAPTURA if captura_em_andamento(dados) else "O joBot já está aberto.", file=sys.stderr)`.
Os dois nomes vêm de `jobot.sistema.instancia` (`:97-106`), como em `sistema/abrir.py:110`.

- [ ] **Teste que falha:** `test_serve_com_captura_no_ar_diz_qual_e`. É o mesmo arranjo de `test_serve_com_outro_jobot_aberto_avisa_e_sai_com_1` (`test_servir.py:514`), mas com `Trava(isolado, 0)`, que é o que o `capturar_logado.py:408` prende.
  - `assert servir.executar(...) == 1`
  - `assert AVISO_CAPTURA in capsys.readouterr().err`
  - O teste antigo segue como controle.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_servir.py -q -k captura`.
- [ ] **Implementar.** Na D134, item 31, acrescente "(feita na T227, D135.6)".
- [ ] **Ver passar:** `uv run pytest tests/integracao/test_servir.py -q`, depois o portão de ruff.

### T228: limites da página em `limites.py`
`depende_de: —` · D134.21 (trocada), D135.7

**Arquivos:** modificar `src/jobot/navegador/limites.py`, `src/jobot/navegador/pagina.py`, `scripts/capturar_logado.py`, `tests/navegador/test_navegacao_logada.py`, `tests/unidade/test_navegador_abrir.py` e `duvidas.md` (sufixo no item 21 da D134).

**Interfaces:**
- `limites.py` ganha, na seção dos técnicos:
  - `ESPERA_ASSENTAR_MS: Final = 10_000`;
  - `PASSOS_DEPOIS_DE_ROLAR: Final = 5`;
  - `ESPERA_429_S: Final = ESPERAS_LIMITE[0]`, com `from jobot.nucleo.http import ESPERAS_LIMITE`.
- `pagina.py` perde as linhas 30 e 31 e o `ESPERAS_LIMITE` do import (`:23`). Ela passa a ler `limites.ESPERA_ASSENTAR_MS` (`:148`), `limites.PASSOS_DEPOIS_DE_ROLAR` (`:157`) e `limites.ESPERA_429_S` (`:288`). O comentário `shortcut:` da linha 31 vai junto para `limites`.
- `capturar_logado.py:54` e `:290` passam a ler `limites.ESPERA_ASSENTAR_MS`.

- [ ] **Stub:** crie em `limites.py` os três nomes (`ESPERA_ASSENTAR_MS = 10_000`, `PASSOS_DEPOIS_DE_ROLAR = 5`, `ESPERA_429_S = ESPERAS_LIMITE[0]`), com `pagina.py` e o script ainda lendo as constantes velhas. Sem isso, o `monkeypatch.setattr(limites, ...)` dos testes levanta `AttributeError`, que não é vermelho.
- [ ] **Teste que falha:**
  - `test_limites_da_pagina_moram_em_limites` (AST, em `test_navegador_abrir.py`). Em `src/jobot/navegador/*.py` e `scripts/capturar_logado.py`, nenhum `ast.Name` ou alias de import chamado `ESPERA_ASSENTAR_MS`, `_PASSOS_DEPOIS_DE_ROLAR`, `PASSOS_DEPOIS_DE_ROLAR`, `ESPERA_429_S` ou `ESPERAS_LIMITE` fora de `limites.py`. Hoje acha `pagina.py`, que ainda define os nomes.
  - `test_429_sem_retry_after_espera_o_padrao` (`test_navegacao_logada.py:325-334`) com `monkeypatch.setattr(limites, "ESPERA_429_S", 11.0)` e `assert relogio.dormidas == [11.0]`. Com o stub dá `[30.0] != [11.0]`. O import de `ESPERAS_LIMITE` (`:14`) sai.
  - `test_passos_depois_de_rolar_vem_de_limites`, em `tests/navegador/test_navegacao_logada.py`: `monkeypatch.setattr(limites, "PASSOS_DEPOIS_DE_ROLAR", 2)` e `visitar(page, site.url("/lista-html"), LeitorFalso.para(site, rolar=True), politica_local, relogio)`. A rota `/lista-html` já existe (`tests/apoio/site_falso.py:314-315`): é HTML estático, sem `fetch`, então não pede nada ao rolar. Nenhuma rota nova. Meça antes, com o valor 5, quantas dormidas de 1 s a mesma página dá, e prenda `relogio.dormidas.count(1) == 2`. Com o stub dá 5.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_abrir.py tests/navegador/test_navegacao_logada.py -q -k "limites or 429 or passos"`. Os três falham em asserção.
- [ ] **Implementar.** Na D134, item 21, acrescente "(feita na T228, D135.7)".
- [ ] **Ver passar:** os mesmos dois arquivos inteiros, depois o portão de ruff e `MYPYPATH=src uv run mypy scripts/capturar_logado.py`.

### T229: aviso no idioma da pessoa
`depende_de: T225, T226` · D134.37 (trocada), D135.8

**Arquivos:** modificar `src/jobot/navegador/execucao.py`, `tests/navegador/test_janela_parada.py` e `duvidas.md` (sufixo no item 37 e no item 1 de "Para confirmar" da D134).

**Interfaces:**
- `_FRASE_AVISO` (no topo de `execucao.py`) vira `_FRASES_AVISO: Final = {"pt": ..., "en": ...}`. O pt é o de hoje. O en é "A site with login stopped at a challenge. Finish it in the browser window within {} minutes.". O `_TITULO_AVISO = "joBot"` serve aos dois.
- `def _idioma(con: sqlite3.Connection) -> Literal["pt", "en"]` devolve `"en"` se `ler_config(con, "idioma", "pt") == "en"`, senão `"pt"`. É a mesma leitura e a mesma validação de `painel/seguranca.py:68-82`, sem o `Accept-Language`, que a execução não tem.
- `_Janela.__init__(relogio, avisar, fechado, idioma)`. O `executar_login` passa `_idioma(con)` ao criar a `_Janela`, e o `_Janela.parar` usa `_FRASES_AVISO[self._idioma]`.
- `Dependencias` não muda, para não mexer nas cinco montagens (`registros/padroes.md:43`).

- [ ] **Teste que falha:** `test_aviso_sai_no_idioma_da_pessoa`, parametrizado com `(None, "Um site com login parou")`, `("en", "A site with login stopped")` e `("xx", "Um site com login parou")`. Grave `idioma` quando não for `None`, com uma parada em `/recaptcha-v2` sem 2Captcha e `monkeypatch.setattr(limites, "JANELA_PARADA_S", 60)`.
  - `assert montagem.avisos[0][1].startswith(esperado)`
  - `assert _sem_endereco(montagem.avisos)`
  - O caso `en` falha hoje.
- [ ] **Ver falhar:** `uv run pytest tests/navegador/test_janela_parada.py -q -k idioma`.
- [ ] **Implementar.** Na D134, item 37 e item 1 de "Para confirmar", acrescente "(trocada pela T229, D135.8)".
- [ ] **Ver passar:** `uv run pytest tests/navegador/test_janela_parada.py -q`, depois o portão de ruff.

### T230: contexto sem downloads e sem service workers
`depende_de: T228` · D134.48 (parte), D135.9

**Arquivos:** modificar `src/jobot/navegador/abrir.py`, `tests/unidade/test_navegador_abrir.py` e `duvidas.md` (sufixo no item 48 da D134).

**Interfaces:** `abrir_contexto` (`abrir.py:30-47`) passa `accept_downloads=False, service_workers="block"` nas duas chamadas de `lancar` (`:39` e `:43`).
- O padrão do Playwright 1.65.1 é `accept_downloads` verdadeiro e `service_workers="allow"` (docstring de `launch_persistent_context` em `playwright/async_api/_generated.py`).
- `"block"` impede o registro de service workers. Com isso a resposta vem da rede e continua disparando o evento `response` (o `Response.from_service_worker` só existe para a que o service worker atende).
- Como o `contexto_de_teste` do site falso (`tests/apoio/site_falso.py:614-636`) e o da janela também passam por `abrir_contexto`, a bateria de navegação inteira prova que `ouvir_respostas` segue lendo.

- [ ] **Teste que falha:** `test_contexto_sem_downloads_nem_service_workers`. Com `_Lancador(falham=(1,))` (`test_navegador_abrir.py:24-36`), as duas chamadas trazem `accept_downloads is False` e `service_workers == "block"`. Hoje `get` dá `None`.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_abrir.py -q -k downloads`.
- [ ] **Implementar.** Na D134, item 48, acrescente "(downloads e service workers: T230, D135.9)".
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_navegador_abrir.py -q`, depois o portão de ruff. O `tests/navegador/test_navegacao_logada.py` é `tela` e não roda aqui: roda no CI da branch `lote/<nome>`, com a bateria de navegação inteira, e é ele que prova que as respostas seguem lidas com as duas opções.

### T231: só o ambiente que o navegador precisa
`depende_de: T230` · D134.48 (parte), D135.10

**Arquivos:** modificar `src/jobot/navegador/abrir.py`, `tests/unidade/test_navegador_abrir.py`, `duvidas.md` (sufixo no item 48 da D134 e, se a verificação manual não for feita, o registro na D135) e `registros/padroes.md:40` (a frase "junte com `os.environ`" vira "a lista de `abrir.VARIAVEIS_DO_NAVEGADOR` mais o ambiente da tela").

**Interfaces:**
- `abrir.py` ganha `VARIAVEIS_DO_NAVEGADOR: Final = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LANGUAGE", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_DATA_DIRS", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "DBUS_SESSION_BUS_ADDRESS")`. As `XDG_*`, `TMPDIR`, `USER` e `LOGNAME` entram porque o Chrome costuma lê-las para pastas, área de trabalho e usuário e nenhuma carrega segredo; deixá-las de fora arrisca um `SemNavegador` que nenhum teste acusaria (D135.10).
- `lancador_de_producao` (`:50-58`) passa `env={**{n: os.environ[n] for n in VARIAVEIS_DO_NAVEGADOR if n in os.environ}, **ambiente}`. As quatro variáveis da tela vêm só do `ambiente`, que `ambiente_da_tela` validou (`sistema/tela.py:13`, `:36`).
- A docstring deixa de dizer "troca o ambiente inteiro" e passa a dizer o que vai.

- [ ] **Teste que falha:** `test_lancador_de_producao_passa_so_o_ambiente_do_navegador`. Esvazie o ambiente com `monkeypatch.delenv(chave, raising=False)` sobre uma lista literal no teste: os quinze nomes da lista, os quatro da tela e `SEGREDO_DO_TESTE`. Não itere `abrir.VARIAVEIS_DO_NAVEGADOR`: hoje o nome não existe e o vermelho viraria `AttributeError`. Defina `HOME`, `PATH`, `LANG`, `SEGREDO_DO_TESTE=x` e `DISPLAY=:99`. O `ambiente` é `{"DISPLAY": ":7"}`.
  - `assert "SEGREDO_DO_TESTE" not in env`. É esta asserção que falha hoje.
  - `assert env == {"HOME": ..., "PATH": ..., "LANG": ..., "DISPLAY": ":7"}`
  - `test_lancador_de_producao_mantem_home_e_path` (`:76`) segue como controle.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_navegador_abrir.py -q -k ambiente`.
- [ ] **Implementar.** Na D134, item 48, acrescente "(ambiente do `serve`: T231, D135.10)".
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_navegador_abrir.py -q`, depois o portão de ruff.
- [ ] **Verificação manual:** os testes usam lançador falso, então nada prova que o navegador abre com o `env` restrito. Quem faz é o dono, ou a sessão principal na máquina do dono, com tela; o agente da tarefa e o CI não fazem. Sem tela (o `ambiente_da_tela` volta vazio), não tente: registre na D135, em "Para confirmar com o dono", "verificação manual da T231 não conferida", e a tarefa fecha com os testes. Com tela, abra um Chromium do Playwright com `headless=False` pelo `lancador_de_producao` (com o `ambiente_da_tela` de verdade), carregue uma página e feche. Se houver Chrome instalado, repita com `channel="chrome"`. Registre no resumo da tarefa o comando, o navegador e o resultado. Se não abrir, a variável que faltou entra na lista e o caso vai à D135.10.

## Fora deste plano

- "Com fixture real: `div` invisível ou dentro de `<form>` tratada como desafio" fica para a Parte B. Precisa de página real capturada.
- As variáveis de proxy no ambiente do Chrome estão na D135, item 1 de "Para confirmar com o dono". A T231 sai sem elas até o dono responder.
