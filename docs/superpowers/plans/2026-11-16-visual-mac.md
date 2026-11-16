# Visual de app do Mac: plano de implementação

> Cada tarefa roda num worktree próprio, tirado da branch indicada na "Ordem", e passa por revisão de outra pessoa ou sessão, diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido. Erro de import, de coleta, `TypeError`, `KeyError`, `IndexError`, `DID NOT RAISE` ou zero testes não valem como vermelho. Nome novo nasce devolvendo valor errado, para o teste falhar por asserção. Teste que nasce verde é guarda e diz o seu mutante. O código se cita por símbolo, nunca por número de linha.

**Objetivo:** dar ao painel a cara e o comportamento de um app do Mac, como o desenho pede: tokens novos (cor, tipo, raio, vidro, movimento), ícones Lucide embutidos, casca com barra lateral e barra de ferramentas, Vagas em lista com detalhe ao lado, Desfazer, menu de contexto, paleta de comandos, o componente único de progresso com etapas, o assistente de três passos e a janela do modo app.

**Arquitetura:** o painel continua FastAPI + Jinja2 + HTMX, com HTML do servidor e o `app.js` de hoje. Nenhuma dependência nova: a Inter já está embutida, e o Lucide entra do mesmo jeito, como arquivos SVG com licença e `lucide.meta.json`. O progresso ganha dados no banco (uma migração com duas tabelas novas), chamáveis novos no núcleo (cliente HTTP e executor) e uma função pura da curva em `nucleo/andamento.py`; o painel só lê e mostra. A janela do modo app é outro abridor para o `abrir_painel` de hoje, com a busca do navegador em `sistema` e o Chromium do joBot por um chamável vindo do `cli`.

**Base:** `dev` atual. A T263 (primeira execução) precisa da T241 (`2026-11-15-fase-2-primeiro-site-resto.md`). Quem constrói confere na base os nomes citados aqui (`busca_efetiva`, `_ids_destaques`, `relogio_do_painel`, `utc_do_banco`, `_config`, `inteiro_da_url`, `contar_abas`, `execucao_atual`, `renderizar`, `GRUPOS`, `_PARCIAIS`, `abrir_painel`, `caminho_do_navegador`) antes de começar.

**Desenho:** `docs/superpowers/specs/2026-11-15-visual-mac-design.md` (seções 5.1 a 5.9, testes na 7, ordem na 8). As decisões do dono estão na D140 a D143 do `duvidas.md`; as escolhas deste plano estão abaixo e na D144 do `duvidas.md`, para confirmar (quem muda uma muda as duas). As regras da HIG citadas no desenho valem com as URLs públicas dele; nenhum texto da Apple é copiado.

## Restrições globais

- Ler `registros/padroes.md` antes de cada tarefa. As lições de «Esquema», «Teste de migração», «CSS e template», «Tela com HTMX», «JS do painel», «i18n», «Formulário» e «Doc» valem para as tarefas que mexem nessas partes.
- Camadas: `nucleo` puro (a curva fica nele, sem relógio próprio); `banco` importa só `nucleo`; `agenda` importa `nucleo` e `banco`; `sistema` não importa `navegador`; o `painel` não importa `httpx`. `tests/unidade/test_camadas.py` prende isso.
- O painel escuta só em `127.0.0.1` e não carrega recurso externo; a CSP de hoje fica igual (`img-src 'self'` já aceita os ícones por `mask-image`).
- Texto novo do painel entra nos catálogos `pt` e `en`, com os mesmos parâmetros. pt-BR só com a primeira letra maiúscula; en em Title Case em botão, item de menu, título e item da lateral (desenho 5.6). Texto de tela trocado: procurar a frase velha em `tests/` antes de fechar a tarefa.
- Cor nova é token em `base.css` dentro de `light-dark(#claro, #escuro)`, com hex de seis dígitos. Par de texto entra no comentário `/* contraste: ... */` (4,5:1); par de objeto gráfico, no `/* contraste-grafico: ... */` (3:1, E11). Se um par de texto reprovar, o tom do texto muda, nunca o fundo; se o par `destaque/trilho-progresso` reprovar, o trilho muda e o `--destaque` não (desenho 6).
- `backdrop-filter` só em `.vidro` e `.vidro-grande`. Movimento reduzido: sem `transform`, transições de até 150ms, bloco no fim do `base.css`. Todo `appearance: none` e todo fundo que carrega informação têm bloco `forced-colors`.
- Gravação no banco: `INSERT ... ON CONFLICT DO UPDATE`; nunca `INSERT OR REPLACE`, `REPLACE` nem `DROP TABLE`. Nada é apagado.
- Nenhum teste espera tempo real nem usa rede: relógio e cliente entram por injeção.
- Nesta máquina rodam só o arquivo de teste da tarefa e `uv run ruff check && uv run ruff format --check`. Suíte inteira, `-m tela` e `uv run mypy` rodam no CI de uma branch `lote/<nome>`. Teste de tela fica no repositório e entra na bateria.
- Desvios: R1 a R3, quem implementa resolve e lista. R4 (arquitetura, dependência, esquema além do desta lista, contrato público) vai ao `duvidas.md` com opções e recomendação, e o resto da tarefa segue.

## Escolhas deste plano (D144, para confirmar)

| # | Escolha | Teste |
|---|---|---|
| E1 | A curva e os pesos ficam em `nucleo/andamento.py`, puros. O valor mostrado é função de `p`, da partida e dos segundos desde a última mudança de `p`; a partida nova é calculada por quem grava (a agenda), com a mesma função, no instante da mudança. Com a etapa parada, o valor chega ao limite `curva(fim da etapa)` e para nele (depois de uns 690 s o arredondamento do `float` o iguala); abaixo do limite, estritamente, só até 600 s, o maior `Retry-After` aceito (`MAX_RETRY_AFTER_S`). | `test_valor_nunca_desce`, `test_partida_nova_nunca_menor`, `test_avanco_lento_nunca_passa_do_limite` |
| E2 | Esquema do progresso: tabela `andamento` (uma linha por execução: etapas fixadas, etapa, feitas, total, total planejado, partida, mudou_em) e `andamento_fonte` (uma linha por fonte: estado, feitas, total, fim e motivo da espera). As tabelas de hoje não mudam; `execucao_fonte` continua com começo e fim. | `test_migracao_andamento_*` |
| E3 | Número da migração: o primeiro livre na base da T246. Se a `0009_sessao_site.sql` do lote Contas ainda não estiver na `dev`, a do progresso é a `0009_andamento.sql` e o lote Contas passa a usar o número seguinte; quem entra depois troca o número do arquivo e do teste antes de juntar (o teste de versão conta os `.sql`). O desenho de Contas leva a mesma nota. | `test_migracoes.py` |
| E4 | Contagens da lateral num global do Jinja (`lateral(request)`, em `painel/lateral.py`, registrado em `painel/globais.py`), com conexão própria, como o `_tema` de hoje. O global não pode importar `rotas/vagas.py`, que importa `seguranca`, que importa `globais` (import circular). Por isso `relogio_do_painel`, `busca_efetiva`, `utc_do_banco`, `_ids_destaques` (vira `ids_destaques`), `_config` (vira `config_ou_padrao`), `_DESTAQUES_N` e `_ANTES_DESTAQUES` saem de `rotas/vagas.py` para `painel/consultas.py`, que não importa `rotas`, `seguranca` nem `globais`; quem os importa hoje passa a importar de lá, sem cópia (T251). | `test_consultas_nao_importa_o_painel_de_cima`, `test_lateral_conta_fora_de_vagas` |
| E5 | A paleta de comandos entra depois do ok do dono, com as outras telas, como o pedido deste plano; o desenho (seção 8) a punha em Vagas, antes do ok. | (ordem) |
| E6 | O ⌘? abre a página inicial da wiki do joBot (`Home` em pt, `Home-en` em en), numa aba nova; a página de atalhos entra na wiki pela T268 e é ligada a partir da inicial. | `test_atalho_de_ajuda_abre_a_wiki` |
| E7 | A espera do cliente HTTP é avisada só nas esperas de 429, 503 e nas novas tentativas (desenho 5.9); o intervalo normal entre pedidos ao mesmo host não conta como espera. | `test_espera_avisada_*` |
| E8 | Estado por fonte: "esperando" com o fim já passado aparece como "Lendo"; a fonte sai de "esperando" na próxima consulta pronta ou no fim dela. | `test_espera_vencida_mostra_lendo` |
| E9 | A janela do modo app abre por um lançador que não espera o navegador (`subprocess.Popen` com `start_new_session=True`, entrada e saídas em `DEVNULL`; deu certo = o processo nasceu), no molde do `subir_servidor`. O `_rodar` de hoje espera o processo sair e o mataria em 10 s. O `open -na` do Mac passa pelo mesmo lançador. O comando `abrir` passa a morar em `cli/abrir.py`, que monta o abridor. | `test_lancador_nao_espera_o_navegador` |
| E10 | A linha de vaga é o próprio link: `<a role="option" href="/vagas/{id}">`, sem controle dentro. Sem JavaScript, o link abre a página própria. | `test_linha_e_link_sem_js` |
| E11 | Par de objeto gráfico (o `destaque/trilho-progresso`) fica num segundo comentário, `/* contraste-grafico: ... */`, conferido a 3:1 por um teste próprio; o de texto continua a 4,5:1. | `test_contraste_grafico_minimo`, `test_pares_novos_presentes` |
| E12 | A região viva `#andamento-etapa` fica fixa na casca; a resposta troca só o conteúdo dela (`hx-swap-oob="innerHTML:#andamento-etapa"`, texto num filho), para o leitor de tela anunciar a troca. | `test_regiao_viva_so_com_etapa_nova`, `test_regiao_viva_e_o_mesmo_no` |
| E13 | O alerta abre com o foco no próprio `<dialog>` (`autofocus` nele), nunca num botão: Return logo depois de abrir não faz nada. | `test_apagar_tem_alerta`, `test_return_ao_abrir_nao_apaga` |
| E14 | Atalho escrito: o servidor manda as duas formas, cada uma num `<kbd data-sistema="mac">` ou `<kbd data-sistema="outro">`; o `app.js` põe `data-sistema` no `<html>` pelo sistema, e o CSS esconde a outra forma. Sem JavaScript não há paleta. | `test_paleta_tem_as_duas_formas_do_atalho` |
| E15 | O componente do "Esquecer logins" já vem no HTML do grupo, como `hx-indicator` do formulário: só aparece com `.htmx-request`, com o atraso de 1 s no CSS. | `test_esquecer_mostra_o_componente_indeterminado` |
| E16 | Só um id válido de busca ativa grava a `busca_escolhida`; `busca=abc`, id que não existe ou busca desligada não gravam. A busca da URL continua valendo na página só por existir, como hoje e como o desenho 5.2. | `test_busca_invalida_nao_grava`, `test_busca_desligada_na_url_continua_valendo` |
| E17 | Botões de ação presos no pé (assistente, sheet de correção, alerta); só o conteúdo rola (`overflow: auto`, `min-height: 0`), sem altura fixa. | `test_botoes_visiveis_com_janela_baixa`, `test_sheet_correcao_botoes_visiveis` |

## Foco da revisão

| # | Entrada ou condição | O que a pessoa espera | Teste | Tarefa |
|---|---|---|---|---|
| RF1 | A busca roda com o painel aberto em duas abas, e a pessoa troca de página | A barra mostra o mesmo valor nas duas e nunca volta | `test_duas_paginas_no_mesmo_instante_mesmo_valor`, `test_valor_da_pergunta_nunca_desce` | T252 |
| RF2 | Um site pede `Retry-After` de 10 min e só ele falta | A barra avança devagar sem chegar à etapa seguinte; a linha diz "Esperando o {site} liberar, 10 min" | `test_avanco_lento_nunca_passa_do_limite`, `test_espera_longa_vira_minutos` | T244, T252 |
| RF3 | O banco está travado quando a agenda grava uma marca do progresso | A busca segue e termina; só a marca se perde | `test_marca_que_falha_nao_derruba_a_busca` | T247 |
| RF4 | A pessoa aperta ⌘Z enquanto digita na busca | O texto do campo desfaz; a vaga ocultada não volta | `test_cmd_z_no_campo_nao_desfaz_a_faixa` (tela) | T256 |
| RF5 | Uma busca começou antes de a pessoa atualizar o joBot (execução rodando sem linha de `andamento`) | Barra indeterminada e "Preparando as consultas", sem erro 500 | `test_execucao_sem_andamento_fica_indeterminada` | T252 |
| RF6 | Texto "Maior" numa janela de 360px, ou zoom de 200% | Nada cortado, sem rolagem lateral, a navegação vira faixa no alto | `test_360px_sem_rolagem_lateral` (tela) | T251 |
| RF7 | Navegador sem JavaScript | Tema, idioma e tamanho salvam pelo botão dentro de `<noscript>`; a lateral e a lista funcionam por link (cada linha é um `<a role="option">`, E10); a vaga abre na página própria | `test_preferencias_sem_js`, `test_linha_e_link_sem_js` | T250, T254 |

## Ordem

| Onda | Tarefas | Branch | Por quê |
|---|---|---|---|
| 1 | T244, T245, T246 | cada uma da `dev`, juntas num `lote/progresso-dados` | lado de trás do progresso: não muda tela e entra na `dev` sozinho, com o CI verde (D143.70); a tela de andamento de hoje continua igual |
| 2 | T247 | da `dev` com a onda 1 | liga os chamáveis e o banco na agenda |
| 3 | T267 | da `dev`, em qualquer momento | modo app: não muda tela, entra na `dev` sozinho (D143.54 e desenho 8, item 6) |
| 4 | T248, T249, T250, T251, T252 | branch longa `feat/visual-mac`, tirada da `dev` com a onda 2 | Base: tokens, ícones, Geral, casca e o componente de progresso; CI por `lote/visual-base` |
| 5 | T253, T254, T255, T256, T257 | `feat/visual-mac` | Vagas; CI por `lote/visual-vagas` |
| 6 | T258 | — | portão: a branch longa não entra na `dev` antes do ok do dono (D140.8, D143.54) |
| 7 | T259 a T266 | da `dev`, depois de juntar a branch longa | as outras telas; a T263 também depois da T241 |
| 8 | T268 | da `dev`, por último | documentos de quem usa, quando o visual chega |

A T250 vem antes da T251 porque a casca nova tira tema e idioma da barra, e os testes de hoje (`test_casca.py`) precisam do grupo Geral para trocar o tema.

---

### T244: curva e pesos do progresso
`depende_de: —` · desenho 5.9 (Ritmo, Garantias), E1

**Arquivos:**
- criar `src/jobot/nucleo/andamento.py`, `tests/unidade/test_andamento.py`.

**Interfaces:**
- `PESOS: Mapping[str, int] = {"coleta": 80, "detalhes": 12, "cotacoes": 3, "encaixe": 5}` (proposta), nessa ordem; `EXPOENTE = 1.25`, `TETO = 0.99`, `PARADA_S = 3.0`, `PASSO_S = 2.0`, `RESTO = 0.9` (proposta).
- `pesos_da_execucao(etapas: Sequence[str]) -> dict[str, float]`: só as etapas pedidas, na ordem de `PESOS`, somando 1,0; lista vazia ou etapa desconhecida levanta `ValueError`.
- `fracao(pesos: Mapping[str, float], etapa: str, feitas: int | None, total: int | None) -> tuple[float, float]`: devolve `(p, B)`, com `B` o fim da etapa atual em `p`. `etapa` é uma chave de `pesos`, `"preparando"` (`p = 0`, `B` = fim da primeira etapa), `"regras"` (conta como o começo da etapa que roda depois de `detalhes`) ou `"fim"` (`(1.0, 1.0)`). Etapa sem contagem, ou com `total` zero ou `None`, fica no começo dela.
- `curva(p: float) -> float`: `p ** EXPOENTE`.
- `valor_mostrado(p: float, fim_da_etapa: float, partida: float, parado_s: float, *, fechada: bool) -> float`: `1.0` se `fechada`; senão `L = curva(fim_da_etapa)`, `n = max(0, floor((parado_s - PARADA_S) / PASSO_S))` quando `parado_s >= PARADA_S` (zero antes), `v = max(curva(p), partida, L - (L - partida) * RESTO ** n)`, devolvido como `min(v, L, TETO)`.
- `partida_nova(valor_antes: float, p_novo: float) -> float`: `max(curva(p_novo), valor_antes)`.

- [ ] **Primeiro, valor errado:** `curva` devolve `p`; `valor_mostrado` devolve `curva(p)`; `pesos_da_execucao` devolve os pesos crus; `fracao` devolve `(0.0, 1.0)`; `partida_nova` devolve `valor_antes`.
- [ ] **Testes que falham** em `tests/unidade/test_andamento.py`:
  - `test_curva_nas_pontas` (guarda, nasce verde com `curva = p`): `curva(0) == 0` e `curva(1) == 1`. Mutante: `curva = p ** 1.25 + 1e-3`.
  - `test_curva_cresce_e_fica_abaixo_de_p`: numa grade de 101 pontos, `curva` cresce sempre e `curva(p) < p` em `0 < p < 1`.
  - `test_pesos_somam_um_sem_uma_etapa`: `pesos_da_execucao(["coleta", "encaixe"])` soma 1,0 e guarda a proporção 80:5; sem `detalhes` e `cotacoes`, `fracao(..., "encaixe", None, None)[0] == pytest.approx(80/85)`.
  - `test_regras_contam_na_etapa_seguinte`: com as quatro etapas, `fracao(pesos, "regras", None, None) == fracao(pesos, "cotacoes", None, None)`; sem cotações, igual ao de `"encaixe"`.
  - `test_valor_nunca_desce`: simula 60 perguntas de 2 s com `p` subindo em degraus e parando, recalculando a partida com `partida_nova` a cada mudança; cada valor é maior ou igual ao anterior, inclusive quando `p` muda logo depois de um avanço lento.
  - `test_avanco_lento_nunca_passa_do_limite`: `p = 0.6`, `B = 0.8`, partida `curva(0.6)`. Em toda a faixa de `parado_s` de 0 a 3600, o valor fica `<= curva(0.8)`; de 5 a 600 s (`MAX_RETRY_AFTER_S`), estritamente `<` que `curva(0.8)` e `>` que `curva(0.6)`; antes de 3 s, igual a `max(curva(p), partida)`. Depois de uns 690 s o `float` arredonda o valor para o próprio limite, e por isso o `<` estrito para em 600 s (E1).
  - `test_teto_ate_fechar`: `valor_mostrado(1.0, 1.0, 0.99, 999, fechada=False) <= 0.99` e `valor_mostrado(..., fechada=True) == 1.0`.
  - `test_partida_nova_nunca_menor`: `partida_nova(0.7, 0.5) == 0.7` e `partida_nova(0.1, 0.5) == curva(0.5)`.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_andamento.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_camadas.py`; ruff; mypy no CI.

### T245: chamáveis de espera e de total planejado no núcleo
`depende_de: —` · desenho 5.9 ("O que o lado de trás precisa guardar"), E7

**Arquivos:**
- modificar `src/jobot/nucleo/http.py`, `src/jobot/nucleo/coletores/executor.py`;
- modificar `tests/unidade/test_http.py`, `tests/unidade/test_executor.py`.

**Interfaces:**
- `http.py`: `MotivoEspera = Literal["limite", "erro"]`; `AoEsperar = Callable[[datetime, MotivoEspera], Awaitable[None]]`. `ClienteEducado.escopo(..., ao_esperar: AoEsperar | None = None)` repassa ao `HttpDoEscopo`, que chama `await ao_esperar(relogio.agora() + timedelta(seconds=espera), motivo)` logo antes de cada `relogio.dormir(espera)` do laço de envio: `"limite"` no 429 e no 503 (com `Retry-After` ou com as esperas padrão), `"erro"` na nova tentativa depois de erro de transporte ou 5xx. Sem `ao_esperar`, nada muda.
- `executor.py`: `rodar(..., ao_planejar: Callable[[Mapping[str, int]], Awaitable[None]] = _nada_planejado, ao_esperar: Callable[[str, datetime, MotivoEspera], Awaitable[None]] = _nada_esperado)`. Antes de criar as tarefas, `rodar` chama `escopos()` de cada fonte ligada (a mesma chamada que `_Fonte.rodar` faz hoje), guarda a lista ou o erro, e chama `ao_planejar({chave: n})` uma vez, com `n = len(escopos)` ou `1` para a fonte cujo `escopos()` falhou. `_Fonte` recebe a lista (ou o erro) pronta, sem chamar `escopos()` de novo, e grava a linha de escopo vazio da falha como hoje. `_Fonte` passa ao `cliente.escopo(...)` um `ao_esperar` que leva a chave da fonte.

- [ ] **Primeiro, valor errado:** `escopo` aceita `ao_esperar` e não o chama; `rodar` aceita `ao_planejar` e não o chama.
- [ ] **Testes que falham** em `tests/unidade/test_http.py` (relógio e transporte falsos de hoje):
  - `test_espera_avisada_no_429_com_retry_after`: `Retry-After: 7` → um aviso com `fim == agora + 7 s` e motivo `"limite"`, antes do `dormir(7)` (a ordem fica na lista de chamadas do relógio falso).
  - `test_espera_avisada_no_503_sem_retry_after`: avisos de 30 e 60 s, motivo `"limite"`.
  - `test_espera_avisada_na_nova_tentativa`: erro de transporte e depois 502 → avisos de 2 e 4 s, motivo `"erro"`.
  - `test_sem_espera_sem_aviso` (guarda): 200 direto e o intervalo normal entre pedidos não chamam `ao_esperar`. Mutante: avisar no `_enviar`.
- [ ] **Testes que falham** em `tests/unidade/test_executor.py`:
  - `test_total_planejado_antes_da_primeira_consulta`: duas fontes com 3 e 2 escopos e uma cujo `escopos()` levanta; `ao_planejar` é chamado uma vez com `{"a": 3, "b": 2, "c": 1}`, antes do primeiro pedido e do primeiro `ao_terminar_escopo`.
  - `test_escopos_chamados_uma_vez_por_fonte`: um coletor falso conta as chamadas de `escopos()`; o total é 1 por fonte.
  - `test_total_bate_com_as_linhas`: o número de `SaidaEscopo` recebidas é igual à soma planejada, com um escopo fora do orçamento (linha "no_limite") e a fonte que falhou.
  - `test_espera_da_fonte_leva_a_chave`: o transporte responde 429 com `Retry-After: 5` na fonte `"a"`; `ao_esperar` recebe `("a", agora + 5 s, "limite")`.
  - `test_fontes_desligadas_fora_do_plano`: fonte fora de `ligadas` não aparece no dicionário.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_http.py tests/unidade/test_executor.py -q`.
- [ ] **Implementar** os itens de Interfaces. O semáforo `MAX_FONTES_JUNTAS` continua só em volta do `_Fonte.rodar`.
- [ ] **Ver passar:** os mesmos arquivos, mais `tests/unidade/test_executor_log.py`; ruff; mypy no CI.

### T246: dados do progresso no banco
`depende_de: —` · desenho 5.9, E2, E3, `registros/padroes.md` («Esquema», «Teste de migração», «Transação»)

**Arquivos:**
- criar `src/jobot/banco/migracoes/NNNN_andamento.sql` (E3), `src/jobot/banco/andamento.py`, `tests/integracao/test_migracao_NNNN.py`, `tests/integracao/test_andamento_banco.py`;
- modificar `src/jobot/banco/execucoes.py` (`execucao_atual`), `tests/integracao/test_execucoes.py`, `tests/integracao/test_migracoes.py` (versão `ULTIMA`).

**Interfaces:**
- Migração:
  ```sql
  CREATE TABLE andamento (
    execucao_id     INTEGER PRIMARY KEY REFERENCES execucao(id) ON DELETE CASCADE,
    etapas          TEXT NOT NULL,   -- JSON: as etapas que rodam, fixadas no começo
    etapa           TEXT NOT NULL CHECK (etapa IN
                      ('preparando','coleta','detalhes','regras','cotacoes','encaixe','fim')),
    feitas          INTEGER,
    total           INTEGER,
    total_planejado INTEGER,
    partida         REAL NOT NULL DEFAULT 0,
    mudou_em        TEXT NOT NULL
  );
  CREATE TABLE andamento_fonte (
    execucao_id   INTEGER NOT NULL REFERENCES execucao(id) ON DELETE CASCADE,
    fonte         TEXT NOT NULL REFERENCES fonte(chave),
    estado        TEXT NOT NULL CHECK (estado IN ('fila','lendo','pronto','falhou','esperando')),
    feitas        INTEGER NOT NULL DEFAULT 0,
    total         INTEGER NOT NULL,
    espera_ate    TEXT,
    espera_motivo TEXT CHECK (espera_motivo IS NULL OR espera_motivo IN ('limite','erro')),
    PRIMARY KEY (execucao_id, fonte)
  );
  ```
- `banco/andamento.py`:
  - `@dataclass(frozen=True) class Etapa`: `etapas: tuple[str, ...]`, `etapa: str`, `feitas: int | None`, `total: int | None`, `total_planejado: int | None`, `partida: float`, `mudou_em: datetime`.
  - `@dataclass(frozen=True) class FonteAndamento`: `fonte: str`, `estado: str`, `feitas: int`, `total: int`, `espera_ate: datetime | None`, `espera_motivo: str | None`.
  - `abrir_andamento(con, execucao_id: int, etapas: Sequence[str], agora: datetime) -> None` (etapa `preparando`, partida 0).
  - `planejar(con, execucao_id: int, totais: Mapping[str, int], agora: datetime) -> None`: grava `total_planejado = sum(totais)`, `etapa = 'coleta'`, `feitas = 0`, `total = total_planejado`, e uma linha `fila` por fonte.
  - `mudar_etapa(con, execucao_id: int, etapa: str, feitas: int | None, total: int | None, partida: float, agora: datetime) -> None`.
  - `marcar_fonte(con, execucao_id: int, fonte: str, estado: str, *, feitas: int | None = None, espera_ate: datetime | None = None, espera_motivo: str | None = None) -> None`: um `UPDATE` da linha que o `planejar` criou (`total` vem de lá); `feitas=None` mantém o valor; estado diferente de `esperando` limpa a espera. Sem a linha, não grava nada e escreve no log.
  - `ler_andamento(con, execucao_id: int) -> tuple[Etapa | None, tuple[FonteAndamento, ...]]`.
  - As outras gravações por `INSERT ... ON CONFLICT DO UPDATE`; todas com a regra de transação do `_marcar_fonte` de hoje (quem abriu a transação confirma).
- `execucao_atual`: `escopos_prontos` passa a contar só as linhas de `saude` com `estado <> 'desligada'`.

- [ ] **Primeiro, valor errado:** `ler_andamento` devolve `(None, ())`; as gravações não gravam; `execucao_atual` como hoje.
- [ ] **Testes que falham** em `tests/integracao/test_migracao_NNNN.py` (lê só o seu arquivo, pelo ajudante que confere `exists()`): `test_migracao_andamento_cria_as_tabelas` (colunas e `CHECK`, por `PRAGMA table_info` e por um `INSERT` com etapa fora da lista que levanta `IntegrityError`); `test_migracao_andamento_sobre_banco_antigo` (migrações `[:N]` num banco em `tmp_path` com uma execução e uma `saude`, depois a nova; nada some). Vermelho por mutante: a migração sem o `CHECK` de `estado`.
- [ ] **Testes que falham** em `tests/integracao/test_andamento_banco.py`:
  - `test_planejar_grava_total_e_fila`: `{"a": 3, "b": 2}` → `total_planejado == 5`, etapa `coleta`, duas fontes em `fila`.
  - `test_marcar_fonte_muda_a_propria_linha`: `fila` → `lendo` → `esperando` (com fim e motivo) → `lendo`; uma linha só, e a espera limpa no fim.
  - `test_marcar_fonte_feitas_none_mantem`: `feitas=2`, depois `marcar_fonte(..., "lendo")` sem `feitas` → continua 2; `total` continua o do `planejar`.
  - `test_marcar_fonte_sem_planejar_nao_cria_linha`: sem `planejar`, `marcar_fonte` não grava linha nenhuma e não levanta.
  - `test_mudar_etapa_guarda_partida_e_instante`.
  - `test_nada_apagado`: depois de `fim`, as linhas continuam.
  - `test_gravacao_dentro_de_transacao_aberta_nao_confirma` (molde do `gravar_saude`).
- [ ] **Teste que falha** em `tests/integracao/test_execucoes.py`: `test_desligada_fora_das_prontas`: duas linhas `ok` e uma `desligada` → `escopos_prontos == 2`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_migracao_NNNN.py tests/integracao/test_andamento_banco.py tests/integracao/test_execucoes.py -q`.
- [ ] **Implementar** os itens de Interfaces. Conferir os gatilhos de hoje (`evento`, `BEFORE DELETE` de `vaga`, FTS5): nenhum toca nas tabelas novas.
- [ ] **Ver passar:** os mesmos arquivos e `tests/integracao/test_migracoes.py`; ruff; mypy no CI.

### T247: a agenda grava o progresso
`depende_de: T244, T245, T246` · desenho 5.9, E1, E8

**Arquivos:**
- criar `src/jobot/agenda/andamento.py`;
- modificar `src/jobot/agenda/execucao.py` (`executar_busca`, `_coletar`, `_enriquecer`, `_cotacoes`, o encaixe e a chamada de `reprocessar_se_regras_mudaram`), `tests/integracao/test_execucao.py`.

**Interfaces:**
- `agenda/andamento.py` importa `from jobot.banco import andamento` e chama as gravações pelo módulo. `class Marcas` com `con`, `execucao_id` e `relogio`; métodos `async`: `comecar(etapas: Sequence[str])`, `planejado(totais: Mapping[str, int])`, `fonte_comecou(fonte)`, `consulta_pronta(fonte)`, `fonte_terminou(fonte, falhou: bool)`, `esperando(fonte, fim: datetime, motivo: MotivoEspera)`, `etapa(etapa: str, feitas: int | None, total: int | None)`.
- Toda mudança de `p` lê a `Etapa` gravada, calcula o valor de antes com `valor_mostrado` (relógio injetado) e grava `partida_nova(valor_antes, p_novo)` e `mudou_em = agora`.
- Cada método é de melhor esforço, como as marcas de começo e fim de fonte de hoje: `sqlite3.Error` vai ao log e a busca segue.
- Etapas fixadas no começo: `coleta` e `encaixe` sempre; `detalhes` com `enriquecimento_ligado`; `cotacoes` com `conversao_moeda_ligada`. `reprocessar_se_regras_mudaram` marca a etapa `regras` antes de rodar, só quando há o que tratar.
- `rodar` recebe `ao_planejar=marcas.planejado`, `ao_esperar=marcas.esperando` e os avisos de fonte de hoje ligados também às `Marcas`. O fim da consulta (`ao_terminar_escopo`) chama `consulta_pronta`. A fonte termina como `falhou` quando `estado_da_fonte` dos estados dela der falha.

- [ ] **Primeiro, valor errado:** `Marcas` sem gravar nada.
- [ ] **Testes que falham** em `tests/integracao/test_execucao.py` (coletores, cliente e relógio falsos de hoje):
  - `test_busca_grava_etapas_na_ordem`: com `monkeypatch`, `abrir_andamento`, `planejar` e `mudar_etapa` de `jobot.banco.andamento` são embrulhadas por funções que anotam a etapa gravada e chamam a original (a agenda as chama pelo módulo, `andamento.mudar_etapa(...)`, para o embrulho valer). A sequência anotada, sem repetições seguidas, é `preparando`, `coleta`, `detalhes`, `cotacoes`, `encaixe`, `fim`.
  - `test_regras_mudadas_marcam_regras_antes_de_cotacoes`: com as regras trocadas antes da busca e vagas para reprocessar, a sequência anotada tem `regras` logo depois de `detalhes` e antes de `cotacoes`; sem regras trocadas, `regras` não aparece.
  - `test_sem_enriquecimento_sem_etapa_de_detalhes`: `etapas` gravadas sem `detalhes`.
  - `test_feitas_batem_com_o_total`: no fim da coleta, `feitas == total_planejado` e cada fonte com `feitas == total`.
  - `test_espera_marca_a_fonte`: um 429 com `Retry-After: 5` deixa a fonte `esperando` com `espera_ate == agora + 5 s`.
  - `test_partida_nunca_desce`: as partidas gravadas formam sequência não decrescente.
  - `test_marca_que_falha_nao_derruba_a_busca`: `banco.andamento.marcar_fonte` trocada por uma que levanta `sqlite3.OperationalError`; a execução fecha como `concluida` e as vagas foram gravadas.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_execucao.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo, `tests/integracao/test_execucao_log.py`, `tests/integracao/test_motivo_da_parada.py` e `tests/unidade/test_camadas.py`; ruff; mypy no CI. A tela de andamento de hoje não muda.

### T248: tokens do visual
`depende_de: —` · desenho 5.1 e 5.7

**Arquivos:**
- modificar `src/jobot/painel/static/css/base.css`, `buscas.css`, `configuracoes.css` e `execucao.css` (controles, `cursor`, `scale`) e os outros CSS onde houver `letter-spacing`, `backdrop-filter` ou cor solta; `src/jobot/painel/templates/base.html` (`header` com `class="topo vidro"`);
- criar `tests/unidade/test_css.py`; modificar `tests/unidade/test_contraste.py`, `tests/tela/test_casca.py` (`test_painel_e_translucido`, `test_reduced_motion_desliga_animacao`).

**Interfaces:**
- Tipo: `html { font-size: 100% }`; os tokens `--t-large` a `--t-cap2` da tabela do desenho 5.1, no formato `peso tamanho/entrelinha` em `rem`; o `body` passa de `1.0625rem` a `font: var(--t-body)` (13/16); descrição de vaga em 15px, entrelinha 1,5, até 70ch; pesos 400, 500, 600 e 700; nada abaixo de 10px; nenhum `letter-spacing`. Medidas na grade de 4px e propriedades lógicas (`margin-inline`, `padding-block`, `inset-inline-start`) no CSS novo.
- Cores: todos os tokens da tabela do desenho 5.1 (`--texto`, `--texto-2`, `--texto-3`, `--fundo`, `--superficie`, `--sob-pagina`, `--solido-barra`, `--solido-elevado`, `--destaque`, `--trilho`, `--trilho-progresso`, `--segmento`, `--separador`, `--hover`, `--pressionado`, `--selecao-inativa`, `--veu`, `--fundo-controle`, `--borda-controle`) com os valores de lá. Cada par de texto novo leva o comentário `/* contraste: ... */`; o par `destaque/trilho-progresso`, o comentário `/* contraste-grafico: ... */` (E11).
- Vidro: `--vidro-blur: 24px`, `--vidro-blur-grande: 40px`, `--vidro-sat: 1.4`, `--vidro-fundo` (72% de `--solido-barra`), `--vidro-fundo-grande` (85%), `--vidro-borda`; classes `.vidro` e `.vidro-grande`. Caminho sólido (fundo `--solido-barra`, sem filtro) com `prefers-reduced-transparency: reduce`, `prefers-contrast: more` (com borda de 1px `--texto`), `@supports not (backdrop-filter: blur(1px))` e `:root[data-janela="inativa"]`; no caminho sólido os menus e a paleta usam `--solido-elevado`. `.painel` passa a `--superficie`, sem vidro. `.topo` perde o `backdrop-filter` próprio e ganha a classe `vidro` no `base.html`. O `body` fica com `--fundo` opaco; o vidro tem borda de 1px `--separador` do lado que encosta no conteúdo. A lista e o detalhe rolam no próprio contêiner, nunca o `body` por baixo do vidro (desenho 5.1).
- Controles (desenho 5.3): botão com 28px (`1.75rem`) de altura; variantes principal (fundo `--destaque`), comum (`--fundo-controle` com borda `--borda-controle`), simples (sem fundo) e destrutivo; `cursor: default` em botão, interruptor e item de lista (`pointer` só em link); desativado com `opacity: .45` e o motivo escrito ao lado; campo de texto com 28px, raio `--raio-controle` e fundo `--superficie`; interruptor 38×22px (mini 30×18px), no lugar da `.chave` de hoje.
- Raios: `--raio-controle: 6px`, `--raio-grande: 10px` (`--raio` passa de 14 para 10px), `--raio-sheet: 18px`, pílula 999px. Sombras: `--sombra-cor`, `--sombra-cor-forte`, `--borda-elevada` e as três sombras do desenho.
- Movimento: `--mola-suave` e `--mola-leve` em `linear()` com pelo menos 20 pontos e o `cubic-bezier(0.22, 1, 0.36, 1)` de reserva; `--mola: var(--mola-suave)`; `--duracao: 190ms`; sem `scale` no `:active`; nunca animar `backdrop-filter`. O bloco de movimento reduzido vai para o fim do arquivo, no lugar do de hoje: sem `transform`, transições de até 150ms.

- [ ] **Testes que falham** em `tests/unidade/test_css.py` (lê os `.css` de `static/css/`):
  - `test_backdrop_filter_so_no_vidro`: toda regra com `backdrop-filter` tem seletor `.vidro` ou `.vidro-grande`.
  - `test_sem_letter_spacing` e `test_nada_abaixo_de_10px` (nenhum `font-size` menor que `0.625rem` ou `10px`).
  - `test_movimento_reduzido_por_ultimo_e_sem_transform`: o último `@media (prefers-reduced-motion: reduce)` do `base.css` vem depois de toda outra regra e zera `transform`.
  - `test_mola_tem_vinte_pontos`: `--mola-suave` e `--mola-leve` têm `linear(` com 20 ou mais valores.
  - `test_caminho_solido_completo`: há bloco para `prefers-reduced-transparency`, `prefers-contrast: more`, `@supports not (backdrop-filter` e `[data-janela="inativa"]`, cada um tirando o `backdrop-filter` de `.vidro`.
  - `test_molas_sem_rebote_alem_do_previsto`: nenhum valor de `--mola-suave` passa de 1; o maior de `--mola-leve` fica entre 1 e 1,006.
  - `test_cursor_pointer_so_em_link`: toda regra com `cursor: pointer` tem só seletores de `a` ou `[href]`. Hoje há `pointer` em botões de `base.css`, `buscas.css` e `configuracoes.css`.
  - `test_sem_scale_no_active`: nenhuma regra com `:active` tem `scale(` (hoje há em `base.css`, `configuracoes.css` e `execucao.css`).
  - `test_botoes_com_1_75rem`: a regra de `button` do `base.css` tem `min-block-size: 1.75rem`, e o campo de texto também.
  - `test_body_no_tamanho_do_corpo`: a regra de `body` usa `var(--t-body)` e não tem `1.0625rem`.
- [ ] **Testes que falham** em `tests/unidade/test_contraste.py`:
  - `test_pares_novos_presentes`: os pares de texto do desenho 5.1 (`texto-2/fundo`, `texto-2/sob-pagina`, `texto-2/superficie`, `texto/solido-barra`, `texto-2/solido-barra`, `texto/solido-elevado`, `texto-2/solido-elevado`, `texto/segmento`) estão todos nos comentários `contraste`, e `destaque/trilho-progresso` no `contraste-grafico`. A regex de hoje (`contraste:`) não pega `contraste-grafico:`, e cada par é conferido uma vez só.
  - `test_contraste_minimo` (de hoje) passa a cobrir os pares de texto novos a 4,5:1, nos dois temas.
  - `test_contraste_grafico_minimo`: os pares de `contraste-grafico` a 3:1, nos dois temas. Mutante para o vermelho: um `--trilho-progresso` igual ao `--destaque`.
- [ ] **Testes de tela** (`tela`, rodam no CI): `test_painel_e_translucido` passa a pedir `.painel` opaco e, com `reduced_transparency="reduce"` ou `forced_colors`/`contrast: more` emulados, nenhum `backdrop-filter` ativo; `test_reduced_motion_desliga_animacao` passa a pedir nenhuma transição de `transform` e as outras com até 150ms.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_css.py tests/unidade/test_contraste.py -q`.
- [ ] **Implementar** os itens de Interfaces. Se um par de texto reprovar, escurecer (claro) ou clarear (escuro) o texto até passar e anotar o valor novo no resumo. Se `destaque/trilho-progresso` reprovar, o `--trilho-progresso` escurece (claro) ou clareia (escuro) e o `--destaque` não muda (desenho 6).
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_estaticos.py`; ruff; `-m tela` no CI.

### T249: ícones Lucide embutidos
`depende_de: —` · desenho 5.3 (Ícones) e 5.9 (Ver detalhes)

**Arquivos:**
- criar `src/jobot/painel/static/icones/*.svg`, `src/jobot/painel/static/icones/LICENSE` (a licença do projeto Lucide, inteira), `src/jobot/painel/static/icones/lucide.meta.json`;
- modificar `tests/unidade/test_estaticos.py`, `README.md` e `README.en.md` (a linha de créditos onde a Inter está).

**Interfaces:**
- Uma versão publicada do Lucide, fixada em `lucide.meta.json` com `versao`, `licenca`, `origem` (a URL pública do pacote dessa versão) e `arquivos: {nome: sha256}`, no molde do `inter.meta.json`.
- Só os ícones usados: os 22 do mapa do desenho 5.3, os 5 de estado da 5.9 (`circle-dashed`, `book-open`, `circle-check`, `circle-x`, `clock`) e 8 que o mapa não cobre (proposta): nos grupos de Configurações, Geral `sliders-horizontal`, Funções `toggle-right`, Segundo plano `timer`, Privacidade `shield`, Serviços `plug` e Sites com login `key-round` (o grupo Fontes usa o `rss` da lateral); no estado vazio da lista, `search-x`; na página Saiu, `log-out` (a página de Erro usa o `triangle-alert` do mapa). São 35 nomes, numa constante `ICONES` do teste. Traço de 1,5px (`stroke-width="1.5"` no SVG). Nome que não existir na versão fixada é trocado por outro do mesmo sentido, anotado no resumo e na D144.

- [ ] **Testes que falham** em `tests/unidade/test_estaticos.py`:
  - `test_icones_batem_com_o_meta`: cada arquivo de `icones/*.svg` está no `lucide.meta.json` com o mesmo sha256, e o contrário. O meta é lido por um ajudante que confere `exists()` antes de abrir, para a falta dele dar falha de asserção e não `FileNotFoundError`.
  - `test_icones_tem_licenca`: `LICENSE` existe e cita Lucide.
  - `test_icones_do_mapa_existem`: todos os nomes de `ICONES` estão em `icones/`.
  - `test_icones_sem_recurso_externo`: nenhum SVG tem `href` nem `url(` para fora.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_estaticos.py -q`.
- [ ] **Implementar:** baixar os SVG da versão fixada (pelo pacote publicado), ajustar o traço e gravar o meta.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_documentos.py`; ruff.

### T250: Configurações > Geral, com tamanho do texto
`depende_de: T248` · desenho 5.1 (tamanho do texto) e 5.4 (Configurações), D143.4, D143.22, D143.43

**Arquivos:**
- criar `src/jobot/painel/templates/configuracoes/geral.html` (sai de `aparencia.html`, que deixa de existir como grupo);
- modificar `src/jobot/painel/rotas/configuracoes.py` (`GRUPOS`, `_PARCIAIS`, contexto e gravação), `src/jobot/painel/rotas/preferencias.py`, `src/jobot/painel/seguranca.py` (`_tema` passa a ler também `tamanho_texto`), `src/jobot/painel/erros.py` (`_idioma_e_tema` leva o tamanho, lido dentro do mesmo `try`), `src/jobot/painel/templates/base.html` (`data-texto`), `src/jobot/painel/static/css/base.css`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/i18n/{pt,en}/configuracoes.json`, `src/jobot/painel/i18n/en/casca.json` (`casca.tema`);
- modificar `tests/integracao/test_rota_configuracoes.py`, `tests/integracao/test_rota_preferencias.py`, `tests/integracao/test_erros.py`, `tests/unidade/test_i18n.py`, `tests/tela/test_configuracoes.py`.

**Interfaces:**
- `GRUPOS` começa por `"geral"`; `"aparencia"` sai. `GET /configuracoes/aparencia` responde 303 para `/configuracoes/geral` (só o GET; o POST de país e moeda vai para `/configuracoes/geral`, sem cópia no endereço velho, como na D139.25). `GET /configuracoes` passa a mandar para `/configuracoes/geral`.
- `POST /preferencias/texto` com `tamanho: Literal["padrao", "grande", "maior"]` e `voltar`; grava a chave `tamanho_texto` como `tema` e `idioma` (`ON CONFLICT`); valor fora da lista dá 422.
- `<html lang data-tema data-texto>`; `html[data-texto="grande"] { font-size: 115.4% }`, `html[data-texto="maior"] { font-size: 130.8% }`; sem chave, `padrao`.
- `geral.html`: tema, idioma e tamanho do texto como `<select>` (menu pop-up), cada um num formulário para a sua rota de `/preferencias/*`, salvando ao mudar (`change` → `requestSubmit()` no `app.js`) e com o botão de enviar dentro de `<noscript>`; país e moeda com o botão Salvar, como hoje.
- i18n: tema e idioma reaproveitam as chaves de hoje (`casca.tema`, `casca.tema.sistema|claro|escuro`, `casca.idioma`, `casca.idioma.pt|en`), sem cópia. Em en, `casca.tema` passa de "Theme" a "Appearance" (procurar "Theme" em `tests/` antes de fechar). Chaves novas, pt e en: `configuracoes.grupo.geral` "Geral"/"General"; `configuracoes.geral.texto` "Tamanho do texto"/"Text Size"; `configuracoes.geral.texto.padrao|grande|maior` "Padrão"/"Default", "Grande"/"Large", "Maior"/"Larger"; `configuracoes.geral.salvar_escolha` "Salvar"/"Save" (o botão do `<noscript>`). Sai `configuracoes.grupo.aparencia`; as chaves de `configuracoes.aparencia.*` que mantêm o sentido (país e moeda) ficam.
- `erros.py`: a página de erro leva `data-texto` como leva `data-tema`; banco ausente ou com defeito dá `padrao`, sem levantar.

- [ ] **Primeiro, valor errado:** `/preferencias/texto` responde 303 sem gravar.
- [ ] **Testes que falham** em `tests/integracao/test_rota_preferencias.py`: `test_texto_grava_e_vai_ao_html` (grava `"maior"` e a página seguinte traz `data-texto="maior"`); `test_texto_fora_da_lista_da_422`; `test_preferencias_sem_js` (o HTML de `/configuracoes/geral` traz os três `<select>` com `name` certo e um `<noscript>` com botão de enviar em cada formulário).
- [ ] **Testes que falham** em `tests/integracao/test_rota_configuracoes.py`: `test_aparencia_vai_para_geral` (303, `location == "/configuracoes/geral"`); `test_pais_e_moeda_gravam_por_geral`; `test_geral_e_o_primeiro_grupo`. Os testes que voltam para `/configuracoes/aparencia` passam a `/configuracoes/geral`.
- [ ] **Teste que falha** em `tests/integracao/test_erros.py`: `test_erro_leva_o_tamanho_do_texto` (com `tamanho_texto = "grande"`, a página de erro traz `data-texto="grande"`; com o banco quebrado, `padrao`).
- [ ] **Teste que falha** em `tests/unidade/test_i18n.py`: `test_grupo_aparencia_saiu` (`configuracoes.grupo.aparencia` não existe em pt nem em en).
- [ ] **Testes de tela** em `tests/tela/test_configuracoes.py`: o tema e o idioma trocados pelo menu de Geral ficam depois de recarregar; `test_tamanho_do_texto_no_corpo`: o `font-size` calculado do `body` é 13px em "Padrão", 15px em "Grande" e 17px em "Maior" (tolerância de 0,1px).
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_preferencias.py tests/integracao/test_rota_configuracoes.py tests/integracao/test_erros.py tests/unidade/test_i18n.py -q`.
- [ ] **Implementar** os itens de Interfaces. Os botões de tema e idioma da barra ficam até a T251.
- [ ] **Ver passar:** os mesmos arquivos; ruff; `-m tela` e mypy no CI.

### T251: casca nova (lateral, barra de ferramentas, faixas)
`depende_de: T248, T249, T250` · desenho 5.2, 5.5 (`/`), 5.7, 5.8 (Casca, Erro e Saiu), D143.3, D143.42

**Arquivos:**
- criar `src/jobot/painel/consultas.py` (E4), `src/jobot/painel/lateral.py`, `src/jobot/painel/static/css/casca.css`, `tests/unidade/test_consultas.py`;
- modificar `src/jobot/painel/rotas/vagas.py` (perde os nomes que vão para `consultas.py`) e quem os importa hoje: `rotas/empresas.py`, `cliente.py`, `rotas/chips.py`, `rotas/fontes.py`, `rotas/detalhe.py`, `rotas/primeira_execucao.py`, `rotas/buscas.py`, `rotas/execucao.py`, `rotas/configuracoes.py` (conferir na base com `rtk grep -rn "relogio_do_painel\|busca_efetiva\|inteiro_da_url\|utc_do_banco" src`);
- modificar `src/jobot/painel/templates/base.html`, `src/jobot/painel/templates/vagas/miolo.html` (`id="busca"` no formulário), `src/jobot/painel/templates/execucao/barra.html`, `src/jobot/painel/globais.py`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/static/css/base.css`, `src/jobot/painel/static/css/execucao.css`, `src/jobot/painel/i18n/{pt,en}/casca.json` e o mínimo das telas de hoje para caberem na coluna de conteúdo;
- modificar `tests/unidade/test_rotas_sem_copias.py`, `tests/unidade/test_i18n.py`, `tests/integracao/test_casca_menu.py`, `tests/integracao/test_erros.py`, `tests/integracao/test_rota_aviso_erro.py`, `tests/tela/test_casca.py`, `tests/tela/test_casca_menu.py`, `tests/tela/test_aviso_erro.py`, `tests/tela/test_aviso_versao.py`, `tests/tela/test_buscar_agora.py`, `tests/tela/test_vagas.py`.

**Interfaces:**
- `painel/consultas.py` (E4): recebe de `rotas/vagas.py`, sem cópia, `relogio_do_painel(request) -> Relogio`, `busca_efetiva(con, pedida)`, `utc_do_banco(texto)`, `ids_destaques(con, busca_id, agora)` (ex-`_ids_destaques`), `config_ou_padrao(con, chave, padrao)` (ex-`_config`), `_DESTAQUES_N` e `_ANTES_DESTAQUES`, com as assinaturas de hoje. Importa `nucleo`, `banco` e `starlette`; nunca `jobot.painel.rotas`, `jobot.painel.seguranca` nem `jobot.painel.globais`. `inteiro_da_url` fica em `rotas/vagas.py`. Em `tests/unidade/test_rotas_sem_copias.py`, `USAM_A_HORA` passa a pedir `("jobot.painel.consultas", "relogio_do_painel")`, e a exceção de `vagas.py` na leitura de `app.state.relogio` sai (a leitura mora em `consultas.py`, fora de `rotas/`). Antes de fechar, procurar em `tests/` os nomes que mudaram de módulo (`setattr`, `monkeypatch`, `ImportFrom` lido por AST).
- `painel/lateral.py`: `@dataclass(frozen=True) class Lateral`: `destaques_ligados: bool`, `sugeridas_pendentes: int`, `busca_id: int | None`, `contagens: Mapping[str, int]` (vazio nesta tarefa). `lateral(request: Request) -> Lateral`, global do Jinja registrado em `globais.registrar`, com conexão própria e sem criar banco (molde do `_tema`). Importa de `painel/consultas.py`, nunca de `rotas/`.
- `base.html`: `aside.lateral.vidro` antes do `header.topo`; dentro, `a.marca` e o `nav` de nome `casca.menu`, com as seções "Vagas" (os itens das abas de `ABAS`, Destaques de hoje só com `destaques_ligados`; cada um `/vagas?aba=<chave>`), "Onde buscar" (Buscas, Empresas, Sugeridas como segundo nível só com `sugeridas_pendentes > 0`, Fontes, Sites) e Configurações numa seção sem título, apontando para `/configuracoes/geral`. Cada `<a>` só com texto; ícone por `::before` com `mask-image`. `aria-current="page"` no item da rota; em Vagas, no da aba.
- Divisor `role="separator"` com os atributos do desenho 5.2; o `app.js` guarda a largura em `localStorage` com `try/catch`, setas de 10px, Home, End, Enter recolhe, duplo clique volta a 240px. Botão de recolher (`panel-left`) com "Recolher barra lateral"/"Mostrar barra lateral" e `aria-expanded`.
- `header.topo.vidro`, filho direto do `body`, com 52px: recolher, título da seção, e no fim a busca, "Buscar agora", "Sair" e `#andamento`. A busca (`<input type="search" form="busca">`, rótulo `casca.busca.campo`, dica `casca.busca.dica`) só aparece quando o contexto da página traz `tem_busca`, que só as rotas de Vagas põem; o formulário `id="busca"` é o de hoje do `vagas/miolo.html`, que ganha o `id` (a T254 o leva para a barra da lista). Tema, idioma e o grupo `casca.preferencias` saem da barra. O botão da paleta entra na T265.
- Faixas logo abaixo da barra, nesta ordem: `#aviso-erro` (sai do rodapé, mantém `role='alert'` com aspas simples e os `data-*` de hoje), `#aviso-versao`, o lugar da faixa de Contas (vazio até o lote Contas) e `#faixa-desfazer` (vazio até a T256, `role="status"`).
- Larguras por `@media` da janela: 900px ou mais, lateral visível; de 640 a 900px, recolhida e sobreposta ao abrir (Esc, clique fora ou escolher item fecha); abaixo de 640px, a navegação vira faixa no alto, sem JavaScript, na mesma ordem de Tab.
- `app.js` põe `data-janela="inativa"` no `<html>` no `blur` da janela e tira no `focus`.
- A coluna de conteúdo rola no próprio contêiner (`overflow: auto`, altura da janela menos a barra); o `body` não rola por baixo do vidro. `casca.css` só com propriedades lógicas e medidas na grade de 4px (desenho 5.1). Teste de tela `test_conteudo_rola_no_proprio_conteiner`: com a lista longa, rolar muda o `scrollTop` da coluna, e o do `document.scrollingElement` fica 0.
- Páginas sem lateral: a despedida do Sair (o `sem_barra` de hoje) e as do assistente (`sem_lateral`).
- i18n (`casca.lateral.*`, pt e en): `vagas` "Vagas"/"Jobs"; `onde_buscar` "Onde buscar"/"Where to Look"; `destaques` "Destaques de hoje"/"Today's Highlights"; `recolher` "Recolher barra lateral"/"Hide Sidebar"; `mostrar` "Mostrar barra lateral"/"Show Sidebar"; `divisor` "Largura da barra lateral"/"Sidebar Width". `casca.busca.campo` "Buscar em Vagas"/"Search Jobs" e `casca.busca.dica` "Focar a busca (/)"/"Focus Search (/)" (proposta, desenho 5.6). Os nomes das abas e das áreas reaproveitam as chaves de hoje. `casca.preferencias` sai dos dois catálogos.

- [ ] **Primeiro, valor errado:** `lateral` devolve `Lateral(False, 0, None, {})` sempre; `consultas.py` nasce com os nomes movidos, e `test_consultas_nao_importa_o_painel_de_cima` é guarda (mutante: `from jobot.painel.rotas import vagas` em `consultas.py`).
- [ ] **Testes** em `tests/unidade/test_consultas.py`: `test_consultas_nao_importa_o_painel_de_cima` (pelo AST, nenhum `import` de `jobot.painel.rotas`, `jobot.painel.seguranca` ou `jobot.painel.globais`); `test_lateral_nao_importa_rotas` (o mesmo para `lateral.py`); `test_nomes_movidos_sem_copia` (nenhum arquivo de `painel/` define `relogio_do_painel`, `busca_efetiva`, `utc_do_banco`, `ids_destaques` ou `_ids_destaques` fora de `consultas.py`).
- [ ] **Teste que falha** em `tests/unidade/test_i18n.py`: `test_preferencias_da_barra_saiu` (`casca.preferencias` não existe em pt nem em en).
- [ ] **Teste que falha** em `tests/integracao/test_casca_menu.py`: `test_busca_na_barra_so_em_vagas` (`/vagas` traz `input[form="busca"]` no `header` e um `form#busca`; `/buscas` não traz o campo).
- [ ] **Testes que falham** em `tests/integracao/test_casca_menu.py`: `test_menu_tem_os_itens_da_lateral_pt_e_en` (no lugar do `test_menu_tem_sete_links_pt_e_en`: os itens da 5.2, texto direto no `<a>`; com Destaques ligados, 8 de Vagas; Sugeridas só com sugestão pendente); `test_aria_current_so_no_item_da_area` (em Vagas, no item da aba); `test_lateral_antes_do_banner` (o `aside` vem antes do `header`, e o `header` é filho do `body`); `test_sem_tema_nem_idioma_na_barra`; `test_assistente_sem_lateral`.
- [ ] **Testes que falham** em `tests/integracao/test_erros.py` e `tests/integracao/test_rota_aviso_erro.py`: as páginas de erro com a lateral; o `#aviso-erro` logo depois do `header`, fora do rodapé, com `role='alert'` em aspas simples.
- [ ] **Testes de tela** (`tela`, CI): em `test_casca.py`, `test_tema_e_idioma_ficam_depois_de_recarregar` e `test_nenhum_pedido_sai_de_127` trocam o tema em Configurações > Geral; `test_lateral_e_barra_com_vidro`; `test_360px_sem_rolagem_lateral` (também com `data-texto="maior"`); `test_abaixo_de_900_a_lateral_recolhe`; `test_janela_inativa_tira_o_vidro`; `test_divisor_pelo_teclado` (setas mudam `aria-valuenow` em 10, Home e End vão a 180 e 320). Em `test_casca_menu.py`, a ordem de Tab (pular, marca, itens) e o contraste de cada item sobre a lateral. Em `test_buscar_agora.py`, "Buscar agora" e "Sair" continuam no `role=banner`. Em `test_aviso_versao.py`, o `#aviso-versao` aparece logo abaixo da barra, com `role="status"`. Em `test_vagas.py`, digitar na busca da barra e apertar Return filtra a lista como hoje.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_consultas.py tests/unidade/test_i18n.py tests/integracao/test_casca_menu.py tests/integracao/test_erros.py tests/integracao/test_rota_aviso_erro.py -q`.
- [ ] **Implementar** os itens de Interfaces e o ajuste mínimo das telas de hoje (Vagas, Buscas, Empresas, Sugeridas, Fontes, Sites, Configurações, Detalhe, Erro, Saiu, assistente) para funcionarem dentro da coluna de conteúdo, sem redesenho.
- [ ] **Ver passar:** os mesmos arquivos, `tests/unidade/test_rotas_sem_copias.py`, `tests/unidade/test_sugeridas_nomes.py`, `tests/unidade/test_camadas.py`, `tests/unidade/test_css.py` e `tests/unidade/test_contraste.py`; ruff; a suíte inteira, `-m tela` e mypy no CI do `lote/visual-base`.

### T252: componente de progresso
`depende_de: T247, T249, T251` · desenho 5.9, 5.3 (Progresso), D143.55 a D143.70

**Arquivos:**
- criar `src/jobot/painel/progresso.py`, `src/jobot/painel/templates/execucao/_progresso.html` (macro do componente, para a barra e para o corpo de uma tela);
- modificar `src/jobot/painel/rotas/execucao.py` (`_andamento`, `buscar_agora`), `src/jobot/painel/templates/execucao/andamento.html`, `src/jobot/painel/templates/execucao/barra.html`, `src/jobot/painel/static/css/execucao.css`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/i18n/{pt,en}/execucao.json`;
- modificar `tests/integracao/test_rota_execucao.py`, `tests/tela/test_buscar_agora.py`; criar `tests/tela/test_progresso.py`.

**Interfaces:**
- `painel/progresso.py`: `@dataclass(frozen=True) class Progresso`: `indeterminado: bool`, `valor: float` (0 a 100, uma casa), `etapa: str`, `feitas: int | None`, `total: int | None`, `lendo: tuple[str, ...]`, `espera: tuple[str, int, str] | None` (fonte, segundos, motivo; só quando nada mais lê), `fontes: tuple[FonteAndamento, ...]` na ordem lendo e esperando, fila, falhou, pronto. `montar_progresso(etapa: Etapa | None, fontes: Sequence[FonteAndamento], agora: datetime, *, fechada: bool) -> Progresso`: sem `Etapa`, ou sem total, indeterminado e etapa `preparando`; com total, `valor = 100 * valor_mostrado(...)` com `parado_s = agora - mudou_em` (relógio do painel).
- A marca do 204 passa a juntar etapa, valor, contagem, espera e estados das fontes; o `visto` continua o único parâmetro da pergunta.
- Barra: trilho `role="progressbar"` com `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuenow` e `aria-valuetext` (a contagem) quando determinada, sem `aria-valuenow` quando indeterminada, nome `execucao.andamento`; preenchimento com `id="andamento-preenchimento"` e a largura em `style`; 6px, pílula, 240px na barra e 320px no corpo; transição linear de 2s na largura; laço de 1,5s na indeterminada; com movimento reduzido, sem transição, e a indeterminada parada com o trilho cheio a 40%; bloco `forced-colors` (preenchimento `Highlight`, borda `CanvasText`) e borda de 1px `--texto` com mais contraste.
- Região viva (E12): `<span id="andamento-etapa" role="status" aria-live="polite">` fixo na casca, fora do `#andamento`, que perde o `role="status"`. A resposta da pergunta só traz, quando a etapa mudou, um elemento com `hx-swap-oob="innerHTML:#andamento-etapa"` e o texto num filho (`<span>`). Com `innerHTML`, o HTMX joga fora o elemento da resposta e os atributos dele e põe só os filhos dentro do nó fixo (`registros/padroes.md`, «Tela, mais»); o nó com `role="status"` nunca é trocado, e o leitor de tela anuncia a mudança.
- Limiar de 1s: só a resposta do `POST /buscar-agora` leva a classe de entrada no envoltório sem `id` (`opacity: 0`, `pointer-events: none`, atraso de 1s); a pergunta de 2s troca só o elemento de dentro, por `outerHTML`.
- "Ver detalhes": o componente na barra é um botão ("Ver detalhes do andamento") que abre um elemento `popover` `.vidro` com uma linha por fonte (nome, ícone e texto do estado, feitas de total, motivo `saude.*` em "Falhou"); Esc e clique fora fecham, e o foco volta ao botão.
- i18n `execucao.etapa.*`, pt e en: os textos da tabela do desenho 5.9, com a chave no singular para o total 1 (`coleta_um`, `detalhes_um`), até 2 nomes e "mais {n}" (`sites_mais`), espera acima de 60s em minutos (`minutos` "{n} min"), estados `fila`, `lendo`, `pronto`, `falhou`, `esperando`, e `ver_detalhes`/`ocultar_detalhes`. `execucao.terminou` passa a "Pronto. Vagas novas: {n}."/"Done. New jobs: {n}."; as chaves `execucao.parada.*` ficam.

- [ ] **Primeiro, valor errado:** `montar_progresso` devolve sempre indeterminado.
- [ ] **Testes que falham** em `tests/integracao/test_rota_execucao.py` (relógio do painel injetado; os `test_execucao_atual_*` de hoje mudam como a tabela do desenho 7 diz):
  - `test_execucao_sem_andamento_fica_indeterminada`: execução `rodando` sem linha de `andamento` → `role="progressbar"` sem `aria-valuenow` e "Preparando as consultas", status 200.
  - `test_com_total_mostra_a_curva`: `planejar` 40, 12 consultas prontas → `aria-valuenow` igual a `round(100 * valor_mostrado(...), 1)`, a largura igual no `style` e "12 de 40 consultas".
  - `test_total_um_no_singular`: "1 de 1 consulta".
  - `test_ate_dois_nomes_e_mais`: cinco fontes lendo → dois nomes e "e mais 3".
  - `test_so_espera_mostra_contagem`: uma fonte `esperando` até `agora + 7 s`, nenhuma lendo → "Esperando o {site} liberar, 7 s"; com motivo `erro`, "Tentando o {site} de novo, 7 s"; com outra lendo, a espera só aparece nos detalhes.
  - `test_espera_longa_vira_minutos`: 600s → "10 min".
  - `test_espera_vencida_mostra_lendo` (E8).
  - `test_duas_paginas_no_mesmo_instante_mesmo_valor`: a casca de `/vagas` e a de `/buscas`, no mesmo instante, trazem o mesmo `aria-valuenow`.
  - `test_valor_da_pergunta_nunca_desce`: perguntas a cada 2s com o relógio avançando e `p` mudando; cada `aria-valuenow` maior ou igual ao anterior.
  - `test_regiao_viva_so_com_etapa_nova`: duas perguntas na mesma etapa → a segunda sem `hx-swap-oob="innerHTML:#andamento-etapa"`; mudando a etapa, com, e o texto da etapa num filho do elemento OOB.
  - `test_204_quando_nada_muda` (guarda): mesmo `visto`, mesmo instante → 204. Mutante: marca sem o valor.
  - `test_entrada_so_na_resposta_do_clique`: o `POST /buscar-agora` traz a classe de entrada; a pergunta de 2s não.
  - `test_fim_diz_pronto`: "Pronto. Vagas novas: {n}." e os motivos de parada de hoje.
  - `test_casca_tem_buscar_agora_sair_e_regiao_aria_live` passa a pedir a região viva só no `#andamento-etapa`.
- [ ] **Teste de tela, antes do resto** (`tests/tela/test_progresso.py`, CI): `test_largura_anda_entre_perguntas`: entre duas respostas, a largura do preenchimento passa por um valor intermediário (o assentamento do HTMX copia o `style` pelo `id`). Se o CI mostrar que não, quem implementa aplica a largura no `htmx:afterSettle` a partir de um `data-valor` (R3) e anota no resumo.
- [ ] **Testes de tela** (CI): `test_regiao_viva_e_o_mesmo_no`: marca o nó `#andamento-etapa` por `page.evaluate` (`window.__no = document.getElementById("andamento-etapa")`), deixa a etapa mudar e confere que `document.getElementById("andamento-etapa") === window.__no`, com `role="status"` e o texto novo; `test_ver_detalhes_abre_e_esc_fecha` (foco volta ao botão; estado com ícone e texto); `test_espera_curta_nao_mostra`; `test_barra_continua_entre_perguntas`; `test_movimento_reduzido_sem_transicao`. Em `test_buscar_agora.py`, a barra e a linha aparecem e terminam em "Pronto".
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_execucao.py -q`.
- [ ] **Implementar** os itens de Interfaces. Procurar em `tests/` "consultas prontas", "Busca concluída" e "ainda rodando".
- [ ] **Ver passar:** o mesmo arquivo, `tests/unidade/test_i18n.py`, `tests/unidade/test_contraste.py` e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI.

### T253: contagens da lateral e busca escolhida
`depende_de: T251` · desenho 5.2 (Barra lateral, Busca escolhida), D143.50, E4

**Arquivos:**
- modificar `src/jobot/painel/lateral.py`, `src/jobot/painel/consultas.py` (`busca_efetiva`), `src/jobot/painel/rotas/vagas.py` (gravar a escolha, as respostas HTMX), `src/jobot/painel/templates/base.html`;
- modificar `tests/integracao/test_rota_vagas.py`, `tests/integracao/test_casca_menu.py`.

**Interfaces:**
- `ids_destaques(con, busca_id: int | None, agora: datetime) -> list[int]` já está em `painel/consultas.py` (T251); a lateral o importa de lá.
- `Lateral.contagens`: as de `contar_abas(con, busca_id, agora)` e, com Destaques ligados, `"destaques": len(ids_destaques(...))`; hora por `relogio_do_painel`. Contagem em texto simples à direita, some quando é zero.
- `busca_efetiva(con, pedida)`: a da URL, se existe (ativa ou não, como hoje e como o desenho 5.2: quem abre um link velho vê a busca dele); senão a gravada em `busca_escolhida`, se ainda existe e está ativa; senão a primeira ativa (E16). Escolher busca em Vagas grava `busca_escolhida` (`gravar_config`, `ON CONFLICT`) só quando o `busca` da URL passa por `inteiro_da_url` e aponta para uma busca que existe e está ativa; texto, id que não existe ou busca desligada não gravam nada. Os links da lateral levam `&busca=<id>` quando há busca.
- Nas respostas HTMX de Vagas (aba, busca, filtro, ocultar, mudar estado), a seção "Vagas" da lateral volta por `hx-swap-oob`, com o `aria-current` certo.

- [ ] **Primeiro, valor errado:** `contagens` vazio.
- [ ] **Testes que falham** em `tests/integracao/test_rota_vagas.py` e `test_casca_menu.py`:
  - `test_lateral_conta_fora_de_vagas`: em `/buscas`, a lateral traz as contagens das abas e a de Destaques, e esconde a que é zero.
  - `test_busca_escolhida_vale_sem_busca_na_url`: escolher a busca 2 em Vagas; `/fontes` traz os links com `busca=2`, e `/vagas?aba=novas` usa a 2.
  - `test_busca_escolhida_apagada_cai_na_primeira_ativa`.
  - `test_busca_invalida_nao_grava`: com `busca=abc`, com um id que não existe e com o id de uma busca desligada, o conteúdo da tabela `config` (hash de todas as linhas) fica igual ao de antes; controle positivo: com o id de uma busca ativa, `busca_escolhida` muda.
  - `test_busca_desligada_na_url_continua_valendo`: `/vagas?busca=<id desligada>` mostra as vagas dessa busca, como hoje, e não grava a escolha. A primeira parte é guarda; mutante: `busca_efetiva` aceitar só busca ativa.
  - `test_ocultar_atualiza_a_contagem_por_oob`: a resposta do ocultar traz a seção com `hx-swap-oob` e a contagem de Ocultas mais um.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py tests/integracao/test_casca_menu.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_camadas.py`; ruff; mypy no CI.

### T254: lista de Vagas em linhas, com teclado
`depende_de: T253` · desenho 5.2 (Lista, Busca), 5.5, 5.8 (Vagas, Linha da vaga), D143.52, D143.53, D143.59

**Arquivos:**
- modificar `src/jobot/painel/templates/vagas/*.html` (`corpo.html`, a página e o miolo), `src/jobot/painel/static/css/vagas.css`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/rotas/vagas.py` (só o contexto), `src/jobot/painel/i18n/{pt,en}/vagas.json`;
- modificar `tests/integracao/test_rota_vagas.py`, `tests/tela/test_vagas.py`.

**Interfaces:**
- Linha de vaga com três linhas de texto, cerca de 64px: título (13px, peso 500) com o encaixe (●◐○); empresa e local (12px, `--texto-2`); salário convertido e selos de estado com ícone e texto (12px) e a data à direita (11px; a da coleta sem publicação). Texto cortado com reticências e o inteiro em `title`. Fontes, motivo do encaixe e botões saem da linha (vão ao detalhe, T255, e ao menu, T257).
- `role="listbox"` de seleção única; cada linha é `<a role="option" href="/vagas/{id}">` (E10), sem botão nem link dentro, com tabindex móvel; setas, Home, End, J e K (fora de campo de texto) movem; Return abre. Sem JavaScript, o clique segue o `href` e abre a página própria.
- Barra da lista acima das linhas: menu pop-up de busca (só com 2 buscas ou mais), menu pop-up de ordem, chips com `aria-pressed`, "Mais filtros" num `<details>` com os campos de hoje, e os avisos ("sem critério", filtros) logo abaixo, no estilo das faixas, sem fechar. O `<form id="busca">` fica nela; o campo da barra de ferramentas e o menu de ordem entram por `form="busca"`. "/" foca a busca e Esc a limpa.
- Na aba Programas, as páginas acompanhadas numa seção abaixo, fora do `listbox`, como links.
- Estado vazio: ícone `search-x` em 20px, título, uma linha e o botão "Buscar vagas". A linha reaproveita `vagas.vazio` (e `vagas.vazio_destaques` em Destaques). Chaves novas, pt e en: `vagas.vazio.titulo` "Nenhuma vaga"/"No Jobs" e `vagas.vazio.buscar` "Buscar vagas"/"Search for Jobs" (proposta; o botão faz o mesmo que "Buscar agora").

- [ ] **Testes que falham** em `tests/integracao/test_rota_vagas.py`:
  - `test_lista_e_listbox_com_options`: um `role="listbox"` e uma `role="option"` por vaga, sem `<button>` nem `<a>` descendente de `option`.
  - `test_linha_tem_tres_linhas`: título, empresa e local, salário e data, nessa ordem, cada um com `title`.
  - `test_linha_e_link_sem_js`: cada `role="option"` é um `<a>` com `href="/vagas/{id}"` da própria vaga, e não tem `<a>` nem `<button>` dentro.
  - `test_abas_saem_do_topo`: sem `nav.abas`; o seletor de busca e a ordem como `<select>`.
  - `test_programas_fora_do_listbox`.
  - `test_vazio_tem_buscar_vagas`: o título, a linha de `vagas.vazio` e o botão "Buscar vagas"/"Search for Jobs", em pt e en.
- [ ] **Testes de tela** (CI): em `test_vagas.py`, J, K, setas, Home e End movem o foco; Return abre; "/" continua focando a busca, agora na barra; com 2 buscas, o menu pop-up troca a busca; o formulário `#busca` está na barra da lista.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos, `tests/unidade/test_i18n.py` e `tests/unidade/test_css.py`; ruff; `-m tela` no CI.

### T255: detalhe ao lado da lista
`depende_de: T254` · desenho 5.2 (Detalhe, Endereço da vaga escolhida, Seleção e foco de coluna, Larguras), D143.35, D143.51

**Arquivos:**
- modificar `src/jobot/painel/rotas/vagas.py` (parâmetro `vaga`), `src/jobot/painel/templates/vagas/*.html`, `src/jobot/painel/templates/detalhe/*.html` (o corpo vira trecho reaproveitado pela página própria e pela coluna), `src/jobot/painel/static/css/vagas.css`, `src/jobot/painel/static/css/detalhe.css`, `src/jobot/painel/static/js/app.js`;
- modificar `tests/integracao/test_rota_vagas.py`, `tests/integracao/test_rota_detalhe.py`, `tests/tela/test_vagas.py`, `tests/tela/test_detalhe.py`.

**Interfaces:**
- `/vagas?...&vaga=<id>`: o servidor manda o detalhe junto. O `vaga` passa por `inteiro_da_url`; id inválido ou que não existe dá a lista sem detalhe, sem erro. Escolher uma linha pede o detalhe por HTMX com `hx-push-url` mantendo aba, busca e ordem.
- Container query na coluna de conteúdo: 860px ou mais, detalhe em coluna à direita (320 a 380px); de 640 a 860px, `<dialog>` não modal sobreposto (`min(420px, 60%)`), que fecha com Esc ou clique na lista; abaixo de 640px, a linha leva à `/vagas/{id}`.
- A linha aberta fica marcada (`aria-selected`). A coluna com o foco (`:focus-within`) mostra a seleção em `--destaque`; as outras, em `--selecao-inativa`.
- O detalhe traz as fontes, o motivo do encaixe e os botões que saíram da linha (Abrir no site, Salvar, Candidatei, Ocultar).

- [ ] **Testes que falham** em `tests/integracao/test_rota_vagas.py`: `test_vaga_na_url_traz_o_detalhe`; `test_vaga_invalida_na_url_sem_detalhe` (`vaga=abc`, id que não existe, um número de 5000 dígitos e `2**63`: 200 sem detalhe, nunca 500); `test_detalhe_tem_os_botoes_da_linha`.
- [ ] **Testes de tela** (CI): `test_coluna_entre_640_e_860_abre_sobreposto`; `test_coluna_larga_abre_ao_lado`; `test_recarregar_abre_a_mesma_vaga`; `test_esc_fecha_o_sobreposto`; `test_janela_inativa_selecao_cinza` (com `data-janela="inativa"` no `<html>`, o fundo calculado da linha marcada é o de `--selecao-inativa`, mesmo com o foco na lista; desenho 7).
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py tests/integracao/test_rota_detalhe.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos; ruff; `-m tela` e mypy no CI.

### T256: Desfazer e Refazer do Ocultar
`depende_de: T255` · desenho 5.4 (Desfazer), 5.5, D143.16, D143.17, D143.36

**Arquivos:**
- criar `src/jobot/painel/templates/_faixa_desfazer.html` (macro: texto, ação, rota e id);
- modificar `src/jobot/painel/rotas/vagas.py` (`ocultar`, `mostrar`), `src/jobot/painel/static/js/app.js`, `src/jobot/painel/static/css/casca.css`, `src/jobot/painel/i18n/{pt,en}/casca.json`;
- modificar `tests/integracao/test_rota_vagas.py`, `tests/tela/test_vagas.py`.

**Interfaces:**
- `POST /vagas/{id}/ocultar` (HTMX) tira a linha e traz, por `hx-swap-oob` no `#faixa-desfazer`, a faixa "Vaga ocultada" com "Desfazer", um formulário para `POST /vagas/{id}/mostrar`. O `mostrar` devolve a linha ao lugar (destacada por 1s, fundo que se apaga) e a faixa "Vaga mostrada de novo" com "Refazer", um formulário para `POST /vagas/{id}/ocultar`. Nenhuma rota nova.
- Uma faixa por vez; ela fica até a pessoa fechar, até outra ação desfazível tomar o lugar ou até uma página nova carregada inteira. Trocas HTMX dentro de Vagas não a tiram.
- ⌘Z (Ctrl+Z fora do Mac) aciona o botão da faixa visível só quando o foco não está em campo de texto; ⇧⌘Z (Ctrl+Shift+Z) aciona o Refazer. Sem faixa, nada. Sistema por `navigator.userAgentData?.platform ?? navigator.platform`.
- i18n `casca.desfazer.*`: `ocultada` "Vaga ocultada"/"Job hidden"; `mostrada` "Vaga mostrada de novo"/"Job shown again"; `desfazer` "Desfazer"/"Undo"; `refazer` "Refazer"/"Redo"; `fechar` "Fechar"/"Close"; `descartada` "Sugestão descartada"/"Suggestion discarded"; `removida` "Empresa removida"/"Company removed" (as duas últimas, usadas na T260).

- [ ] **Testes que falham** em `tests/integracao/test_rota_vagas.py`: `test_ocultar_traz_a_faixa_com_mostrar` (`hx-swap-oob`, `role="status"`, formulário com `action="/vagas/{id}/mostrar"` e `csrf_token`); `test_desfazer_traz_a_faixa_com_ocultar`; `test_refazer_oculta_de_novo` (o status da vaga volta a oculta).
- [ ] **Testes de tela** (CI): `test_cmd_z_desfaz_fora_do_campo`; `test_cmd_z_no_campo_nao_desfaz_a_faixa`; `test_shift_cmd_z_refaz`; `test_faixa_fica_ao_trocar_de_aba`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_i18n.py`; ruff; `-m tela` no CI.

### T257: menu de contexto da vaga
`depende_de: T256` · desenho 5.4 (Menu de contexto), D143.39

**Arquivos:**
- criar `src/jobot/painel/templates/_menu_contexto.html` (macro, reaproveitada na T259 a T261);
- modificar `src/jobot/painel/templates/vagas/*.html`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/static/css/base.css`, `src/jobot/painel/i18n/{pt,en}/vagas.json`;
- modificar `tests/integracao/test_rota_vagas.py`; criar `tests/tela/test_menu_contexto.py`.

**Interfaces:**
- Itens: Abrir, Abrir no site da vaga, Salvar, Ocultar, Copiar link; até três grupos; sem atalhos escritos; item indisponível escondido. Cada item é um link ou formulário que já existe no detalhe.
- Abre com o botão direito, a tecla de menu ou Shift+F10, no ponteiro (ou na linha, pelo teclado); elemento com `popover` ou `<dialog>` não modal, raio 10px, itens de 24px, item destacado em `--destaque`. Setas movem, Esc fecha e o foco volta à linha. Sem JavaScript, não há menu.
- "Copiar link" copia o endereço da vaga no site de origem pela API de área de transferência, com aviso curto em `role="status"`.

- [ ] **Teste que falha** em `tests/integracao/test_rota_vagas.py`: `test_menu_de_contexto_vem_renderizado` (o menu está na página, escondido, com as cinco ações e os formulários com `csrf_token`).
- [ ] **Testes de tela** (CI): `test_botao_direito_abre`; `test_shift_f10_abre`; `test_esc_fecha_e_foco_volta`; `test_ocultar_pelo_menu_traz_a_faixa`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_i18n.py`; ruff; `-m tela` no CI.

### T258: conferência com o dono (portão)
`depende_de: T248 a T257, CI verde no lote/visual-vagas` · D140.8, D143.54

Não é código. A branch `feat/visual-mac` só entra na `dev` depois do ok do dono; sem ok, descartar a branch desfaz tudo.

- [ ] **Preparar:** o CI verde do `lote/visual-vagas`; uma pasta de dados de teste com pelo menos 2 buscas, vagas nas abas, uma sugestão pendente e Destaques ligados.
- [ ] **Mostrar ao dono**, com o painel aberto:
  1. Vagas em três larguras de janela (1280px, 800px e 600px): lateral, lista em linhas, detalhe em coluna, sobreposto e em página própria.
  2. Claro e escuro; o vidro da lateral e da barra; com "Reduzir transparência" e "Aumentar contraste" do sistema, o caminho sólido.
  3. Tamanho do texto em Padrão, Grande e Maior (Configurações > Geral), e a decisão de manter 13px como padrão (desenho 6, "Texto menor").
  4. Contagens da lateral e a busca escolhida valendo nas outras telas.
  5. Ocultar, a faixa, Desfazer e Refazer pelo botão e por ⌘Z e ⇧⌘Z.
  6. O teclado na lista (J, K, setas, Return, "/") e o menu de contexto.
  7. "Buscar agora": a barra indeterminada, depois determinada, a linha da etapa, uma espera de site e "Ver detalhes".
- [ ] **Registrar** a resposta no `duvidas.md` como decisão nova, com cada pedido de mudança; cada pedido vira tarefa na branch longa antes de juntar.
- [ ] **Com o ok:** juntar a `feat/visual-mac` na `dev` do jeito de sempre e seguir para a onda 7.

### T259: Buscas, com o alerta
`depende_de: T258` · desenho 5.3, 5.4 (Alerta, Menu de contexto), 5.8 (Buscas), D143.37

**Arquivos:**
- criar `src/jobot/painel/templates/_alerta.html` (macro do alerta: título, texto, ação, formulário);
- modificar `src/jobot/painel/templates/buscas/*.html`, `src/jobot/painel/static/css/buscas.css`, `src/jobot/painel/static/css/base.css`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/i18n/{pt,en}/buscas.json` e `comum.json`;
- modificar `tests/integracao/test_rota_buscas.py`, `tests/tela/test_buscas.py`.

**Interfaces:**
- Lista agrupada opaca sobre `--superficie`; interruptor mini (30x18px) por linha para ligar e desligar; menu de contexto com as ações da linha (macro da T257).
- Alerta: `<dialog>` modal de 260px, `.vidro .vidro-grande`, raio 18px, véu `--veu`; título 13px peso 600 terminado em "?", texto 11px `--texto-2`; botões em pilha, a ação em cima e "Cancelar" embaixo, nenhum padrão, a ação sem estilo destrutivo; ao abrir, o foco fica no próprio `<dialog>` (`autofocus` nele, `tabindex="-1"`), nunca num botão, e Return logo depois de abrir não faz nada (E13); Esc e ⌘. cancelam; clique no véu não fecha; foco preso dentro e de volta ao botão que abriu. Entra com fade e `scale(.96)` em 200ms; com movimento reduzido, só o fade. Botões presos no pé (E17). Sem JavaScript, o botão "Apagar" da linha envia o formulário de hoje.
- i18n: `buscas.apagar_titulo` "Apagar a busca «{nome}»?"/"Delete the Search \"{nome}\"?"; `buscas.apagar_texto` "As vagas que ela trouxe continuam."/"Jobs it brought in stay."; `comum.apagar` "Apagar"/"Delete"; `comum.remover` "Remover"/"Remove"; `comum.esquecer` "Esquecer"/"Forget"; `comum.cancelar` "Cancelar"/"Cancel".

- [ ] **Testes que falham** em `tests/integracao/test_rota_buscas.py`: `test_apagar_tem_alerta` (o `<dialog>` com o título com o nome escapado, o formulário para `/buscas/{id}/apagar` com `csrf_token`, o `autofocus` no `<dialog>`, nenhum botão com `autofocus` e o "Cancelar" com `type="button"`); `test_apagar_sem_js_continua` (o `POST` de hoje apaga como antes).
- [ ] **Testes de tela** (CI): `test_apagar_abre_o_alerta_e_cancelar_nao_apaga`; `test_return_ao_abrir_nao_apaga` (abre o alerta, aperta Return, o alerta continua aberto e a busca continua na lista depois de recarregar); `test_esc_cancela`; `test_interruptor_mini_pelo_teclado`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_buscas.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo, `tests/unidade/test_i18n.py` e `tests/unidade/test_css.py`; ruff; `-m tela` no CI.

### T260: Empresas e Sugeridas, com Desfazer
`depende_de: T259` · desenho 5.4 (Desfazer), 5.8 (Empresas e Sugeridas), D143.16

**Arquivos:**
- modificar `src/jobot/banco/sugeridas.py`, `src/jobot/banco/cadastros.py`, `src/jobot/painel/rotas/sugeridas.py`, `src/jobot/painel/rotas/empresas.py`, `src/jobot/painel/templates/empresas/lista.html`, `src/jobot/painel/templates/sugeridas/lista.html`, `src/jobot/painel/static/css/empresas.css`;
- modificar `tests/integracao/test_rota_sugeridas.py`, `tests/integracao/test_rota_empresas.py`, `tests/integracao/test_cadastros.py`, `tests/tela/test_sugeridas.py`, `tests/tela/test_empresas.py`.

**Interfaces:**
- `banco/sugeridas.py`: `restaurar(con, id: int) -> None` volta `estado` a `pendente` por `UPDATE` da mesma linha.
- `banco/cadastros.py`: `restaurar_empresa(con, id: int) -> None` limpa `removida_em` por `UPDATE`.
- Rotas: `POST /empresas/sugeridas/{id}/restaurar` e `POST /empresas/{id}/restaurar`, com CSRF, registradas antes de qualquer rota com parâmetro que as engula; id que não existe dá 404.
- Descartar e remover rodam sem pergunta e trazem a faixa da T256 ("Sugestão descartada" e "Empresa removida") com "Desfazer" para a rota de restaurar; o Refazer é a própria ação de hoje (`/descartar`, `/remover`).
- Lista agrupada; menu de contexto com as ações da linha.

- [ ] **Primeiro, valor errado:** `restaurar` e `restaurar_empresa` não fazem nada; as rotas respondem 303 sem chamar.
- [ ] **Testes que falham** em `tests/integracao/test_cadastros.py`: `test_restaurar_sugerida_volta_a_pendente`; `test_restaurar_empresa_limpa_removida_em`; os dois sem mudar o número de linhas da tabela.
- [ ] **Testes que falham** em `tests/integracao/test_rota_sugeridas.py` e `test_rota_empresas.py`: `test_descartar_traz_a_faixa_com_restaurar`; `test_remover_traz_a_faixa_com_restaurar`; `test_restaurar_sem_csrf_da_403`; `test_restaurar_id_que_nao_existe_da_404`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_cadastros.py tests/integracao/test_rota_sugeridas.py tests/integracao/test_rota_empresas.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_rotas_sem_copias.py`; ruff; `-m tela` e mypy no CI.

### T261: Fontes e Sites
`depende_de: T259` · desenho 5.8 (Fontes, Sites), 5.3 (caixa de marcar)

**Arquivos:**
- modificar `src/jobot/painel/templates/fontes/pagina.html`, `src/jobot/painel/templates/sites/lista.html`, `src/jobot/painel/static/css/fontes.css`, `src/jobot/painel/static/css/sites.css`, `src/jobot/painel/i18n/{pt,en}/sites.json`;
- modificar `tests/integracao/test_rota_fontes.py`, `tests/integracao/test_rota_sites.py`, `tests/tela/test_fontes.py`, `tests/tela/test_sites.py`.

**Interfaces:**
- Fontes: lista agrupada; estado com ícone e texto; caixa de marcar (14px, raio 4px, visto branco sobre `--destaque`, bloco `forced-colors`) para ligar.
- Sites: lista agrupada; "Remover" abre o alerta da T259 ("Remover o site «{nome}»?"/"Remove the Site \"{nome}\"?", "As vagas que ele trouxe continuam."/"Jobs it brought in stay."); desativar continua sem pergunta; menu de contexto com as ações da linha.

- [ ] **Testes que falham**: em `test_rota_fontes.py`, `test_fonte_liga_por_caixa_de_marcar` (um `input type="checkbox"` por fonte, com o rótulo ligado); em `test_rota_sites.py`, `test_remover_tem_alerta`.
- [ ] **Testes de tela** (CI): `test_remover_site_abre_o_alerta_e_cancelar_nao_remove`; `test_caixa_de_marcar_pelo_teclado`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_fontes.py tests/integracao/test_rota_sites.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_i18n.py`; ruff; `-m tela` no CI.

### T262: Configurações no jeito dos Ajustes
`depende_de: T259` · desenho 5.4 (Configurações), 5.3, 5.8 (Configurações), D143.28, D143.43

**Arquivos:**
- modificar `src/jobot/painel/templates/configuracoes/*.html`, `src/jobot/painel/static/css/configuracoes.css`, `src/jobot/painel/static/js/app.js`;
- modificar `tests/integracao/test_rota_configuracoes.py`, `tests/tela/test_configuracoes.py`, `tests/integracao/test_rota_sites_com_login.py` (o alerta de esquecer).

**Interfaces:**
- Lista de grupos à esquerda (ícone de 20px, texto de 13px, seleção em `--destaque`), grupo à direita; `nav.config-grupos` e `/configuracoes/{grupo}` continuam. Os ícones dos grupos são os da T249: `sliders-horizontal`, `rss`, `toggle-right`, `timer`, `shield`, `plug` e `key-round`, na ordem de `GRUPOS`.
- Caixa de marcar na maior parte; o interruptor `.chave` fica só onde a opção comanda um grupo.
- O item Configurações da lateral e o ⌘, (Ctrl+, fora do Mac) abrem o último grupo visto, guardado em `localStorage` com `try/catch`; sem registro ou sem JavaScript, `/configuracoes/geral`.
- "Esquecer logins": o fragmento de dois cliques de hoje (no grupo onde ele estiver na base) vira o alerta da T259, com "Esquecer" e "Cancelar"; a rota de confirmar não muda.

- [ ] **Testes que falham** em `tests/integracao/test_rota_configuracoes.py`: `test_grupos_com_icone_e_aria_current` (cada link de grupo com o `data-icone` do seu nome, e o arquivo em `static/icones/`); `test_opcoes_por_caixa_de_marcar` (as opções de Funções como `checkbox`). Em `test_rota_sites_com_login.py`: `test_esquecer_tem_alerta`.
- [ ] **Testes de tela** (CI): `test_item_configuracoes_abre_o_ultimo_grupo`; `test_esquecer_abre_o_alerta_e_cancelar_nao_apaga`; em `test_configuracoes.py`, a caixa de marcar pelo teclado onde o interruptor saiu.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_configuracoes.py tests/integracao/test_rota_sites_com_login.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos; ruff; `-m tela` no CI.

### T263: primeira execução em três passos, com Pular
`depende_de: T258, T241` · desenho 5.4 (Primeira execução), D143.18, D143.40, D143.69

**Arquivos:**
- modificar `src/jobot/painel/rotas/primeira_execucao.py`, `src/jobot/painel/templates/primeira_execucao/*.html`, `src/jobot/painel/static/css/primeira_execucao.css`, `src/jobot/painel/i18n/{pt,en}/primeira_execucao.json`;
- modificar `tests/integracao/test_rota_primeira_execucao.py`, `tests/tela/test_primeira_execucao.py`.

**Interfaces:**
- `POST /primeira-execucao/pular`, registrada antes de `@router.post("/{passo}")`: grava `meu_pais` (como o pular de hoje do passo 1), `segundo_plano` falso e `primeira_execucao_concluida`; cria o atalho do menu como o passo 2 faz com "desligar", sem prender em falha; nenhum site com login ligado; manda para `/vagas`.
- "Pular" (botão simples) em todos os passos; "Continuar" e, no último, "Concluir", presos no pé; só o conteúdo rola (E17). O assistente sem lateral nem botões da barra; "Tudo pronto" mostra "Buscar agora" e o componente da T252 na barra.
- i18n: `primeira_execucao.pular` "Pular"/"Skip"; `primeira_execucao.continuar` "Continuar"/"Continue"; `primeira_execucao.concluir` "Concluir"/"Finish".

- [ ] **Testes que falham** em `tests/integracao/test_rota_primeira_execucao.py`: `test_pular_grava_os_padroes` (`meu_pais`, `segundo_plano` falso, `primeira_execucao_concluida`; destino `/vagas`); `test_pular_responde_em_qualquer_passo` (não cai no 404 de `/{passo}`); `test_pular_com_atalho_que_falha_segue` (o criador do atalho injetado levanta; destino `/vagas`); `test_pular_nao_liga_site_com_login`; `test_pular_em_todo_passo` (o botão aparece nos três).
- [ ] **Testes de tela** (CI): em `test_primeira_execucao.py`, o fluxo com "Continuar" e "Concluir"; "Pular" em qualquer passo cai em Vagas; `test_botoes_visiveis_com_janela_baixa`: janela de 1024×560, texto Maior, passo com mais conteúdo; o botão Continuar está inteiro dentro da janela (`bounding_box` dentro do viewport) e o conteúdo rola (E17).
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_primeira_execucao.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo, `tests/integracao/test_passo2_nao_prende.py` e `tests/unidade/test_i18n.py`; ruff; `-m tela` e mypy no CI.

### T264: detalhe em página, correção, erro e Saiu
`depende_de: T258` · desenho 5.8 (Detalhe e correção, Erro e Saiu)

**Arquivos:**
- modificar `src/jobot/painel/templates/detalhe/*.html`, `src/jobot/painel/templates/erro/pagina.html`, `src/jobot/painel/templates/execucao/saiu.html`, `src/jobot/painel/static/css/detalhe.css`, `src/jobot/painel/static/js/app.js`;
- modificar `tests/integracao/test_rota_detalhe.py`, `tests/integracao/test_erros.py`, `tests/tela/test_detalhe.py`.

**Interfaces:**
- A página própria `/vagas/{id}` com o mesmo trecho do detalhe da T255, texto de leitura até 680px.
- A correção abre num sheet: `<dialog>` modal de 520px no alto, raio 18px, `.vidro .vidro-grande`, Esc fecha; sem JavaScript, o formulário de hoje na página.
- Erro e Saiu: estado vazio com ícone de 20px (`triangle-alert` no Erro, `log-out` no Saiu, da T249), título curto e o que fazer; Saiu sem lateral e sem botões.

- [ ] **Testes que falham**: em `test_rota_detalhe.py`, `test_correcao_em_dialog_com_formulario_de_hoje`; em `test_erros.py`, `test_erro_diz_o_que_fazer` (título, uma linha e o link de volta).
- [ ] **Testes de tela** (CI): `test_correcao_abre_e_esc_fecha`; `test_sheet_correcao_botoes_visiveis`: janela de 1024×560, sheet de correção aberto; os botões do sheet estão inteiros dentro da janela e o corpo do sheet rola (E17).
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_detalhe.py tests/integracao/test_erros.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos; ruff; `-m tela` no CI.

### T265: paleta de comandos e atalhos globais
`depende_de: T262` · desenho 5.4 (Paleta de comandos), 5.5, D143.15, D143.38, E5, E6

**Arquivos:**
- criar `src/jobot/painel/templates/_paleta.html`;
- modificar `src/jobot/painel/templates/base.html`, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/static/css/base.css`, `src/jobot/painel/i18n/{pt,en}/casca.json`;
- modificar `tests/integracao/test_casca_menu.py`; criar `tests/tela/test_paleta.py`.

**Interfaces:**
- Botão na barra (ícone `command`, "Comandos"/"Commands") e ⌘K/Ctrl+K abrem um `<dialog>` modal no alto, 560px, `.vidro .vidro-grande`, raio 10px, com um campo ("Buscar comando"/"Search Commands") e uma `role="listbox"` filtrada enquanto digita; setas movem, Return executa, Esc fecha.
- Comandos renderizados no servidor, no idioma da página: cada item da lateral, cada grupo de Configurações, "Buscar agora", "Sair", tema, idioma e tamanho do texto. Cada um é um link ou formulário que já existe, com o atalho escrito em `--texto-2` quando houver. A paleta não cria ação nova.
- Atalho escrito (E14): o servidor não sabe o sistema de quem vê, então manda as duas formas, `<kbd data-sistema="mac">⌘K</kbd>` e `<kbd data-sistema="outro">Ctrl+K</kbd>`; o `app.js` põe `data-sistema="mac"` ou `"outro"` no `<html>` (pelo mesmo teste de sistema da T256), e o CSS esconde a forma que não vale.
- ⌘? (Ctrl+? fora do Mac) abre a wiki (E6) numa aba nova, com `rel="noopener"`. Esc e ⌘. fecham menu, paleta, sheet e alerta.
- i18n `casca.paleta.*`: `titulo` "Comandos"/"Commands"; `buscar` "Buscar comando"/"Search Commands"; `casca.ajuda.url` com a página da wiki em cada idioma.

- [ ] **Testes que falham** em `tests/integracao/test_casca_menu.py`: `test_paleta_tem_os_comandos` (um item por link da lateral e por grupo de Configurações, e os formulários de "Buscar agora", "Sair", tema, idioma e tamanho com `csrf_token`); `test_atalho_de_ajuda_abre_a_wiki` (o link de ajuda aponta para `Home` em pt e `Home-en` em en); `test_paleta_tem_as_duas_formas_do_atalho` (cada atalho escrito com um `kbd[data-sistema="mac"]` e um `kbd[data-sistema="outro"]`).
- [ ] **Testes de tela** (CI): `test_cmd_k_e_ctrl_k_abrem`; `test_esc_fecha`; `test_return_executa`; `test_filtra_enquanto_digita`; `test_so_uma_forma_do_atalho_visivel` (com o `<html>` em `data-sistema="outro"`, o `kbd` do Mac não é visível).
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_casca_menu.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_i18n.py`; ruff; `-m tela` no CI.

### T266: progresso nas outras esperas
`depende_de: T262, T263` · desenho 5.9 (Um componente só), D143.56, D143.69

**Arquivos:**
- modificar `src/jobot/painel/rotas/configuracoes.py` (o esquecer logins), o template do fragmento de esquecer, `src/jobot/painel/templates/primeira_execucao/pronto.html`, `src/jobot/painel/i18n/{pt,en}/execucao.json`;
- modificar `tests/integracao/test_rota_sites_com_login.py`, `tests/integracao/test_rota_primeira_execucao.py`, `tests/tela/test_configuracoes.py`.

**Interfaces:**
- "Esquecer logins" (E15): o componente da T252, indeterminado, com "Apagando os logins guardados"/"Deleting saved sign-ins" (`execucao.etapa.esquecer`), já vem no HTML do `GET` do grupo, como `hx-indicator` do formulário de esquecer. O CSS o deixa invisível e só o mostra com `.htmx-request`, com atraso de 1s (o mesmo limiar); a resposta do `POST` não traz o componente.
- "Tudo pronto": a primeira busca usa o componente da barra, sem cópia na página.

- [ ] **Testes que falham**: em `test_rota_sites_com_login.py`, `test_esquecer_mostra_o_componente_indeterminado` (no HTML do `GET` do grupo, o formulário de esquecer tem `hx-indicator` apontando para um elemento `role="progressbar"` sem `aria-valuenow` e com o texto da etapa); em `test_rota_primeira_execucao.py`, `test_pronto_usa_o_componente_da_barra` (um só `role="progressbar"` na página).
- [ ] **Teste de tela** (CI, em `tests/tela/test_configuracoes.py`): `test_esquecer_mostra_o_progresso_depois_de_1s`: `page.route` segura o `POST` de esquecer; com `page.clock`, antes de 1s o componente não é visível; depois de `page.clock.fast_forward(1000)`, é; ao soltar a resposta, some.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_sites_com_login.py tests/integracao/test_rota_primeira_execucao.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_i18n.py`; ruff; mypy no CI.

### T267: janela do modo app
`depende_de: —` · desenho 5.4 (Janela do modo app), D143.6, D143.11, D143.41

**Arquivos:**
- criar `src/jobot/cli/abrir.py`, `tests/unidade/test_cli_abrir.py`;
- modificar `src/jobot/sistema/abrir.py` (perde `executar`, que vai para `cli/abrir.py` sem cópia), `src/jobot/navegador/abrir.py`, `src/jobot/cli/__init__.py` (`COMANDOS`: `"abrir"` e `"sair"` passam a `"jobot.cli.abrir"`);
- modificar `tests/unidade/test_abrir.py` (os testes de `executar` vão para `test_cli_abrir.py`, com o `setattr` apontando para `jobot.cli.abrir`), `tests/unidade/test_navegador_abrir.py`, `tests/unidade/test_repositorio.py` (o mapa de `COMANDOS` e o `_falso(..., "jobot.sistema.abrir")`). Antes de fechar, procurar `jobot.sistema.abrir` e `COMANDOS` em `tests/`.

**Interfaces:**
- `navegador/abrir.py`: `async def chromium_do_jobot() -> Path | None`: só `playwright.chromium.executable_path`, se o arquivo existe; não olha o Chrome do sistema. `caminho_do_navegador` passa a chamar `chromium_do_jobot` depois de olhar o `CAMINHO_CHROME`, sem cópia; o teste dele de hoje continua passando.
- `sistema/abrir.py` (E9): `def _lancar(comando: Sequence[str]) -> bool`: `subprocess.Popen(comando, start_new_session=True, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL)` sem esperar; `True` se o processo nasceu, `False` com `OSError`. O `_rodar` de hoje (que espera até 10 s) fica só para `xdg-open` e para o `which`.
- `sistema/abrir.py`: `def achar_navegador_do_sistema(endereco: str, sistema: str, existe: Callable[[str], bool], prefixo: Sequence[str]) -> list[str] | None`: o comando inteiro que abre `--app=<endereço>`, na ordem do desenho (Linux: `google-chrome`, `google-chrome-stable`, `microsoft-edge`, `chromium`, `chromium-browser`, com o `prefixo` de `prefixo_host(env)` na distrobox; Mac: `open -na <app> --args --app=<endereço>` para Google Chrome, Microsoft Edge e Chromium; Windows: `chrome.exe` e `msedge.exe` nas pastas de programas). `existe` padrão: sem prefixo, `shutil.which(nome) is not None`; com prefixo, `_rodar((*prefixo, "which", nome))`.
- `sistema/abrir.py`: `def abrir_janela(endereco: str, env: Mapping[str, str], *, sistema: str, existe: Callable[[str], bool], chromium: Callable[[], Path | None], pasta_dados: Path, lancar: Callable[[Sequence[str]], bool] = _lancar) -> bool`: tenta o navegador do sistema pelo `lancar`; senão chama `chromium()` e lança com `--app=<endereço>` e `--user-data-dir=<pasta_dados>/janela`; senão `abrir_navegador(endereco, env)`. A pasta `<dados>/janela/` nunca é a do login.
- `cli/abrir.py`: `def executar(args: argparse.Namespace) -> int`, o mesmo de hoje (`abrir` e `sair`, `OSError` numa linha e código 1), mas montando o abridor com `functools.partial(abrir_janela, sistema=sys.platform, existe=..., chromium=lambda: asyncio.run(chromium_do_jobot()), pasta_dados=dados)` e passando-o como `navegador` ao `abrir_painel`. `sistema` não importa `navegador`; o `cli` pode importar os dois.

- [ ] **Primeiro, valor errado:** `abrir_janela` chama sempre `abrir_navegador`; `achar_navegador_do_sistema` devolve `None`; `chromium_do_jobot` devolve um `Path` fixo; `_lancar` delega a `_rodar`.
- [ ] **Testes que falham** em `tests/unidade/test_abrir.py` (lançador, `existe` e `chromium` injetados): `test_chrome_do_sistema_abre_com_app`; `test_so_chromium_do_jobot_usa_perfil_da_janela` (`--user-data-dir` termina em `janela`, nunca na pasta do login); `test_nada_achado_cai_na_aba`; `test_chromium_nao_e_chamado_quando_o_sistema_tem_navegador`; `test_mac_usa_open_na` (pelo mesmo lançador); `test_distrobox_usa_o_prefixo` (com `CONTAINER_ID`, o comando começa pelo prefixo do host); `test_lancador_nao_espera_o_navegador`: um `Popen` falso (aceita `with`; `wait` e `communicate` marcam `esperou`) trocado por `monkeypatch`; `_lancar(["chrome"]) is True`, `esperou is False`, e o falso recebeu `start_new_session=True` e `DEVNULL` nas três saídas; com `OSError` no `Popen`, `False`.
- [ ] **Testes que falham** em `tests/unidade/test_navegador_abrir.py`: `test_chromium_do_jobot_sem_arquivo_da_none`; `test_chromium_do_jobot_ignora_o_chrome_do_sistema`.
- [ ] **Testes que falham** em `tests/unidade/test_cli_abrir.py`: os três testes de `executar` que saem de `test_abrir.py`, e `test_abrir_passa_a_janela_ao_painel` (com `abrir_painel` trocado, o `navegador` recebido é um `partial` de `abrir_janela`).
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_abrir.py tests/unidade/test_navegador_abrir.py tests/unidade/test_cli_abrir.py tests/unidade/test_repositorio.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos, `tests/unidade/test_camadas.py`, `tests/unidade/test_navegador_ast.py`, `tests/unidade/test_cli_erros.py`, `tests/unidade/test_atualizar.py` e `tests/integracao/test_servir.py`; ruff; mypy no CI.
- [ ] **Verificação manual** (dono): `jobot` abre a janela sem abas nem barra de endereço; sem Chrome nem Chromium, cai na aba.

### T268: documentos de quem usa
`depende_de: T259 a T267` · `registros/padroes.md` («Doc»)

**Arquivos:**
- modificar `README.md`, `README.en.md`, `CHANGELOG.md`, `CHANGELOG.en.md`, `wiki/Home.md`, `wiki/Home-en.md`, `wiki/Como-funciona.md`, `wiki/How-it-works.md`, `wiki/_Sidebar.md`, `tests/unidade/test_wiki.py` (`PARES`);
- criar `wiki/Atalhos-de-teclado.md`, `wiki/Keyboard-shortcuts.md`.

**Interfaces:**
- README pt e en, seção "O painel": a janela do modo app, a barra lateral, a lista com detalhe, o Desfazer, o tamanho do texto em Configurações > Geral e o link para a página de atalhos; seção de instalação: o `jobot` abre uma janela própria quando acha Chrome, Edge ou Chromium.
- CHANGELOG pt e en, em "Não lançado"/"Unreleased": "Mudado"/"Changed" (o visual novo) e "Adicionado"/"Added" (atalhos, Desfazer, paleta, tamanho do texto, progresso com etapas, modo app). Sem número de dúvida.
- Wiki: o par novo em `PARES` e nas duas listas do `_Sidebar.md`, com a tabela do desenho 5.5 em palavras nossas; `Home` e `Home-en` ligam a página; `Como-funciona` e `How-it-works` descrevem o painel novo.

- [ ] **Testes que falham**: em `tests/unidade/test_wiki.py`, o par novo em `PARES` (falha até as páginas existirem); em `tests/unidade/test_documentos.py`, as seções iguais nas duas línguas continuam passando.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_wiki.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_documentos.py tests/unidade/test_wiki.py -q`; ruff.

## Espera o dono

1. **O portão da T258.** A branch longa só entra na `dev` com o ok; os pedidos de mudança viram tarefas antes de juntar.
2. **As escolhas E1 a E16** (D144), em especial E3 (número da migração e o lote Contas), E4 (`painel/consultas.py`) e E5 (paleta depois do ok), e os nomes propostos de ícones e de textos marcados "proposta".
3. **As decisões da sessão marcadas "para confirmar" no desenho:** um nível só de Desfazer (D143.36), Geral como primeiro grupo (era a P1), Desfazer em Sugeridas e Empresas sem pergunta (era a P3), os pesos e o expoente da curva (proposta).

## Tarefa e dificuldade

| Tarefa | Dificuldade | Por quê |
|---|---|---|
| T244 | média | função pura, mas as garantias (nunca volta, nunca passa da etapa) precisam de teste por propriedade |
| T245 | alta | muda o executor (escopos antes do semáforo) e o laço de envio do cliente HTTP, com relógio injetado |
| T246 | média | migração nova com as lições de esquema e de teste de migração |
| T247 | alta | liga núcleo, banco e agenda, com gravação de melhor esforço e a partida que nunca desce |
| T248 | média | muitos tokens, pares de contraste e os controles da 5.3 em quatro CSS; o teste guia |
| T249 | baixa | arquivos e meta, no molde da Inter |
| T250 | média | grupo novo, 303, rota nova e salvar ao mudar sem JavaScript |
| T251 | alta | a casca inteira, o módulo `consultas.py` com os importadores, o divisor acessível, as larguras e os testes de tela e de integração que mudam |
| T252 | alta | componente com limiar, região viva, 204, curva e a transição que depende do assentamento do HTMX |
| T253 | média | ajudante único, busca escolhida e `hx-swap-oob` |
| T254 | alta | lista nova com `listbox`, teclado e a barra da lista |
| T255 | alta | container queries, `hx-push-url` e três formas do detalhe |
| T256 | média | faixa por `hx-swap-oob` e atalhos fora de campo de texto |
| T257 | média | menu no ponteiro e pelo teclado |
| T258 | baixa | conferência, sem código |
| T259 | média | o alerta acessível reaproveitado depois |
| T260 | média | duas rotas novas e duas funções de banco |
| T261 | baixa | telas especificadas, usando o alerta |
| T262 | média | jeito dos Ajustes, último grupo e o alerta de esquecer |
| T263 | média | rota antes do `/{passo}` e os padrões de quem pula |
| T264 | baixa | estado vazio e sheet |
| T265 | média | paleta filtrada, renderizada no servidor |
| T266 | baixa | reaproveita o componente |
| T267 | média | caminhos por sistema, o lançador que não espera, o `executar` que muda para o `cli` e a fronteira entre `sistema` e `navegador` |
| T268 | baixa | texto, com os testes de documento |

## Fora deste plano

- A tela e a faixa de Contas (D139.15): entram sobre a base nova, no lote Contas; "Conferir agora" usa o componente da T252 por lá.
- A fase 3: janela própria em Tauri, moldura e botões de janela desenhados pelo painel (D143.11) e o semáforo; o instalador em Tauri segue as regras do componente da T252.
- Vários níveis de Desfazer.
- Flatpak e Snap no modo app: caem na aba comum (desenho 6).
- Os não objetivos do desenho, seção 2: notificações do navegador e "desconectar um site só" (D143.60); parar uma busca no meio pelo progresso (D143.71); seleção de várias vagas e ações em lote (D143.27; ⌘A fica com o navegador); cor de destaque escolhida pela pessoa, tamanhos pequeno e grande da lateral e reordenar itens (D143.48).
