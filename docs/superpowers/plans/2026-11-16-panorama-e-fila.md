# Panorama e fila de candidaturas: plano de implementação

> Cada tarefa roda num worktree próprio, tirado da branch indicada na "Ordem", e passa por revisão de outra pessoa ou sessão, diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido. Erro de import, de coleta, `TypeError`, `KeyError`, `IndexError`, `OperationalError` de tabela que falta, `DID NOT RAISE` ou zero testes não valem como vermelho. Por isso cada tarefa começa por "Primeiro, valor errado": a interface nasce com um valor de retorno errado, o teste falha na asserção, e só então vem a implementação. Recusa (CHECK, gatilho, exceção esperada) se testa pelo ajudante `_recusa`, que devolve `bool`, e nunca por `pytest.raises` sozinho. Teste que nasce verde é guarda e diz qual mutante ele pega. O código é citado pelo símbolo, nunca pelo número da linha.

**Objetivo:** a versão 0.3.0. O painel ganha a tela Panorama: o primeiro item da lateral, com quatro grupos (Hoje, Candidaturas, A busca, O que aparece). Os números da tela são os mesmos de Vagas, e as barras são desenhadas no servidor. A fila de candidaturas fica completa:
- o clique em "Candidatar-se" registra a abertura;
- quando a pessoa volta à janela, a faixa "Você se candidatou?" responde com Sim ou Ainda não, e o Sim tem Desfazer;
- o detalhe ganha a linha do tempo com a data de cada passo;
- a aba Candidatei mostra "{status} desde {data}";
- o botão "Candidatar-se por e-mail" usa o endereço achado na descrição.

O joBot nunca envia nada. O plano termina com a 0.3.0 na `main`, por PR da `dev`, com o CHANGELOG em pt e en.

**Arquitetura:** o painel continua FastAPI + Jinja2 + HTMX 2.0.11, sem dependência nova.
- **Núcleo.** A regra do endereço de e-mail fica pura em `nucleo/candidatura.py`.
- **Banco.** Ganha a migração `0011_candidatura.sql` (uma tabela e um gatilho) e cinco funções novas em `banco/acoes.py` e `banco/leitura.py`. As datas dos passos saem de `evento`, sem esquema novo.
- **Consultas entre telas.** As consultas que Fontes e a faixa de Contas já fazem mudam para módulos de `painel/` sem cópia: os cartões de saúde, a próxima busca e as contas em queda.
- **Rotas.** São três módulos novos: `rotas/candidatura.py` (as ações sob `/vagas/`, antes de `detalhe.py`), `rotas/aviso_candidatura.py` (a faixa) e `rotas/panorama.py`.
- **Navegador.** O `app.js` ganha dois ouvintes por delegação: o registro do clique, por `fetch` com `keepalive`, e o "Copiar endereço".

**Base:** `dev` com o lote Contas. A migração precisa da T270 (`0010_sessao_site.sql`) e, por ela, da T246 (`0009_andamento.sql`). As telas esperam:
- o portão T258 do visual de Mac (`docs/superpowers/plans/2026-11-16-visual-mac.md`);
- a T253, a T254, a T255, a T256, a T261, a T264 e a T265;
- a T276, a faixa de Contas (`docs/superpowers/plans/2026-11-16-contas.md`).

Quem constrói confere na base os nomes citados aqui, que essas tarefas criam ou mudam: `painel/consultas.py`, `painel/lateral.py`, o trecho de template do detalhe, o template da linha da lista, `contas_em_queda` e o registro dos ícones. Se um nome mudou, vale o da base, e o resumo da tarefa diz isso.

**Desenho:** `docs/superpowers/specs/2026-11-16-panorama-e-fila-design.md`. Onde está cada parte:

| Parte | Seção |
|---|---|
| Onde o Panorama fica | 5.1 |
| Os grupos | 5.2 |
| As barras | 5.3 |
| Datas dos passos | 5.4 |
| Registro da abertura | 5.5 |
| A pergunta | 5.6 |
| E-mail | 5.7 |
| Textos | 5.8 |
| Documentos | 5.9 |
| Estados | 5.10 |
| Testes | 7 |
| O que fica para o construtor | 8 |
| Perguntas | 10 |

As decisões da sessão estão na D147 (itens 1 a 28), e as escolhas deste plano na D148. As perguntas P1 a P5 do desenho seguem a recomendação de cada uma até o dono responder:
- P1 (a): a tabela `candidatura`;
- P2 (a): o `mailto:` da fonte fica fora;
- P3 (a): `/` continua em Vagas;
- P4 (a): a data do passo Candidatei é a da resposta;
- P5 (a): `fetch` com `keepalive`.

Mudar uma delas muda a tarefa responsável antes de ela começar.

## Restrições globais

- **Lições.** Ler `registros/padroes.md` antes de cada tarefa. As que mais pesam aqui:
  - banco: «Esquema», «Teste de migração», «Transação», «Exceção do banco», «Dia de calendário» e «Plano de consulta»;
  - painel: «Painel», «Painel e ADRs», «Tela com HTMX», «JS do painel», «CSS e template», «Formulário» e «Serve»;
  - textos: «i18n» e «Texto de tela trocado»;
  - testes: «Teste que nasce verde», «Nome de teste» e «Fixtures»;
  - entrega: «Junção do lote», «Troca de versão», «Camadas e AST» e «Doc».
- **Camadas.** `tests/unidade/test_camadas.py` prende estas regras e roda em toda tarefa:
  - `nucleo` é puro (`nucleo/candidatura.py` usa só `re` e `typing`);
  - `banco` importa só `nucleo`;
  - o `painel` não importa `httpx`.

  O `test_camadas.py` não proíbe um módulo de `painel/` de importar `jobot.painel.rotas`, e o `painel/cliente.py` já importa `relogio_do_painel` de `rotas/vagas.py`. Neste lote, só o teste de AST da T283 (`test_saude_nao_importa_rotas`) prende essa regra, e só para `saude_das_fontes.py` e `consultas.py`. Uma regra geral para todo `painel/` fica fora deste plano (ver "Fora deste plano").
- **Testes sem rede nem tempo real.** Nenhum teste usa rede nem espera tempo real. O relógio entra por `relogio_do_painel` e pelo argumento `agora`. Nos testes de tela, o link de candidatura aponta para um servidor local de teste, nunca para a rede.
- **Gravação no banco:**
  - sempre `INSERT ... ON CONFLICT(vaga_id) DO UPDATE`; nunca `INSERT OR REPLACE`, `REPLACE` nem `DROP TABLE`;
  - nada é apagado: a tabela `candidatura` tem gatilho contra `DELETE`;
  - `evento` só recebe acréscimo, pelas ações que já existem (`mudou_status` e `desfez`), sempre pelo `_trocar_status` de `banco/acoes.py`;
  - nenhuma ação nova em `evento`.
- **E-mail da descrição:**
  - o endereço não é guardado em lugar nenhum;
  - ele só aparece na tela da vaga, montado num `href` pelo joBot a partir de um endereço que passou pela lista fechada de caracteres (desenho 5.7);
  - o resto da descrição continua texto puro;
  - dado da vaga entra em `t()` ou é escapado pelo Jinja, nunca com `|safe`.
- **Textos do painel.** Texto novo entra nos catálogos `pt` e `en` com os mesmos parâmetros:
  - pt-BR só com a primeira letra maiúscula;
  - en em Title Case em botão e título.

  Texto de tela trocado: procurar a frase velha em `tests/`, inclusive as negações `not in`, antes de fechar a tarefa.
- **Recursos externos.** O painel escuta só em `127.0.0.1` e não carrega recurso externo. O `mailto:` é navegação da pessoa, não um pedido do painel. A CSP já cobre o `fetch` (`connect-src 'self'`) e continua recusando o atributo `style`, por isso as barras são SVG com `<rect width="{pct}%">`.
- **O que roda nesta máquina:** só o arquivo de teste da tarefa, `tests/unidade/test_camadas.py` e `uv run ruff check && uv run ruff format --check`. A suíte inteira, `-m tela` e `uv run mypy` rodam no CI de uma branch `lote/<nome>`. O teste de tela fica no repositório e entra na bateria. Nunca `uv run jobot`.
- **Desvios:**
  - R1 a R3: quem implementa resolve e lista no resumo;
  - R4 (arquitetura, dependência, esquema além da `0011` desta lista, contrato público): vai ao `duvidas.md` com opções e recomendação, e o resto da tarefa segue.

## Escolhas deste plano (D148, para confirmar)

| # | Escolha | Teste |
|---|---|---|
| E1 | O lote tem doze tarefas, de T280 a T291. O lado de trás (T280, T281, T282) pode entrar na `dev` antes do portão T258, num `lote/panorama-dados`, porque não muda tela. A T283 é uma mudança de lugar no painel e espera a T261 e a T276, para não brigar com as branches do visual e de Contas que mexem em `rotas/fontes.py` e `rotas/aviso_contas.py`. As telas (T284 a T289) entram juntas num `lote/panorama-tela`. Os documentos (T290) e a versão (T291) vêm por último. | (ordem) |
| E2 | Os testes que precisam de banco ficam em `tests/integracao/`, como `test_acoes.py` e `test_leitura.py`, e não em `tests/unidade/`, como a seção 7 do desenho listava. São eles `test_candidatura.py`, `test_datas_dos_passos.py` e `test_salvas_que_fecham.py`. O teste da migração fica num arquivo próprio, `test_migracao_0011.py`, que lê só a `0011` («Teste de migração»), como os de 0005 a 0010; o `test_migracoes.py` continua conferindo a versão pela contagem dos `.sql`. | `test_candidatura_sem_delete`, `test_perguntar_so_0_ou_1` |
| E3 | Número da migração: `0011` vale com a 0009 (T246) e a 0010 (T270) já na `dev`. Se a ordem mudar, vale a regra da D144.E3: quem junta depois renomeia o `.sql` e o `test_migracao_NNNN.py`. | `test_migracoes.py` |
| E4 | O que o Panorama usa de outras telas muda de lugar, sem cópia («Painel»: utilitário entre rotas vai num módulo de `painel/`, travado por AST). Os cartões de saúde vão de `rotas/fontes.py` para `painel/saude_das_fontes.py`: `Reporte`, `Escopo`, `Cartao`, `EXECUCOES`, `estado_dos_escopos`, `motivo_mais_grave`, os ajudantes privados e `_cartoes`, que vira `cartoes`. A próxima busca sai do meio de `_cartoes` e vira `proxima_busca(con, agora)`, no mesmo módulo. `contas_em_queda` vai de `rotas/aviso_contas.py` para `painel/consultas.py`. | `test_definidos_uma_vez`, `test_proxima_igual_a_de_fontes` |
| E5 | O `_DEGRAU` de `banco/acoes.py` vira `DEGRAU`, público, e `datas_dos_passos` o importa, sem copiar o caminho dos passos. Se aparecer import circular entre `acoes.py` e `leitura.py`, o `DEGRAU` muda para `leitura.py` e `acoes.py` passa a importar de lá (R1). | `test_degrau_definido_uma_vez` |
| E6 | Três funções do banco devolvem o que a tela precisa, sem uma segunda consulta. `responder_candidatura` devolve o status de antes (`"nova"` ou `"salva"`) quando o Sim trocou o status, e `None` nos outros casos; a confirmação com Desfazer só aparece quando o valor não é `None`. O Desfazer não leva o status de antes no formulário (E18). `perguntas_pendentes(con, limite)` devolve `(lista, total)`, com `Pergunta(vaga_id, titulo, empresa, abriu_em, status)`. A linha do tempo lê a abertura por `abertura_da_candidatura(con, vaga_id) -> str \| None`. | `test_responder_sim_devolve_o_status_de_antes`, `test_abertura_da_candidatura` |
| E7 | As ações sob `/vagas/` moram em `rotas/candidatura.py`: `POST /vagas/{id}/candidatura`, `/candidatura/resposta` e `/candidatura/desfazer`. Na ordem alfabética, o módulo vem antes de `detalhe.py`, então `/vagas/{vaga_id}` não pega esses caminhos («Painel»). A faixa (`GET /aviso-candidatura`) mora em `rotas/aviso_candidatura.py`. O Panorama e o fragmento `GET /panorama/para-responder` moram em `rotas/panorama.py`. | `test_rotas_de_candidatura_casam_antes_do_detalhe` |
| E8 | O trecho da pergunta, que a faixa e "Para responder" compartilham, é a macro `pergunta(p, prefixo, total)` em `templates/candidatura/_pergunta.html`, importada `with context`. Todo `id` dela é `{prefixo}-pergunta-{vaga_id}` e todo `aria-labelledby` aponta para ele. O prefixo é `faixa` ou `responder`. | `test_ids_unicos_com_faixa_e_para_responder` |
| E9 | Sem JavaScript, as respostas, o Desfazer e o registro da abertura voltam pelo `de_volta(voltar)` de `painel/seguranca.py`; nunca pelo `Referer`, que a `Referrer-Policy: no-referrer` tira. O campo `voltar` sai de onde a página é montada: em "Para responder", que o servidor renderiza na carga do Panorama, é `/panorama`; no fragmento da faixa, que chega por `hx-get`, é o caminho e a consulta do cabeçalho `HX-Current-URL`, passados pela mesma regra do `de_volta` (E21). Sem JavaScript a faixa não aparece, o que é esperado (desenho 5.6, D147.31). | `test_resposta_sem_js_303`, `test_desfazer_sem_js_303`, `test_voltar_sai_do_hx_current_url` |
| E10 | O registro do clique escuta só o `click` por delegação no `document`, como o desenho 5.5 diz. O botão do meio do mouse (`auxclick`) e o "abrir em nova aba" do menu do navegador não registram: nesses casos a pessoa usa "Me candidatei", como hoje. | `test_tela_clique_registra` (CI) |
| E11 | O cálculo da largura das barras é uma função pequena em `rotas/panorama.py`: `pct(n, maior) -> int`, arredondado, com piso de 2 quando `n > 0` e 0 quando `n == 0` ou `maior == 0`. Fica perto de quem usa, porque nenhuma outra tela desenha barra. | `test_pct_das_barras` |
| E12 | Medidas propostas para o CSS, conferidas no `test_contraste.py` e na tela, que quem constrói pode ajustar na grade de 4px: número grande de 28px, barra de 8px de altura com cantos de 4px, 24px entre grupos e 12px entre blocos. Os ícones são `layout-dashboard` (lateral) e `circle-help` (faixa), da versão do Lucide fixada pela T249; se um não existir nessa versão, vale `gauge` para o Panorama e `help-circle` para a faixa, e o resumo diz qual entrou. | `test_estaticos.py` |
| E13 | A medição dos 300 ms (desenho 6, "Custo do Panorama") é feita à mão e uma vez só. Quem constrói a T288 mede o `GET /panorama` contra o banco que `scripts/medir_filtros.py` monta e anota o tempo no resumo; se passar de 300 ms, abre uma `Tn`, sem cache neste lote. A medição não vira teste, porque o tempo no CI depende da máquina. | (resumo da T288) |
| E14 | A 0.3.0 segue a ADR 0017: "depois da fase 2 sai a versão 0.3.0". A T291 só começa com a fase 2 concluída na `dev`. Concluída quer dizer que os planos da fase 2 que o dono der como da fase estão na `dev`, com o CI verde, inclusive o resto do lote do primeiro site, que o plano do LinkedIn diz ser condição da 0.3.0 (`2026-11-15-fase-2-login-linkedin.md`, "Fora deste plano": o botão "Baixar o navegador", o passo do assistente, o `CLAUDE.md` do projeto, as notas nas ADRs 0006 e 0022 e a ADR 0017). Isso é a T240, a T241 e os itens 1, 2, 4, 6 e 7 de "Espera o dono" de `2026-11-15-fase-2-primeiro-site-resto.md`, cada item com o ok do dono. Na ADR 0017, a T291 aplica o texto do item 7 (Status da fase 2 e linha "Atualizada") e, pela «Troca de versão», atualiza também a frase de histórico do Contexto, que hoje para na 0.2.1 e diz "Hoje a fase 1 está concluída". Texto proposto para essa frase (para confirmar, no mesmo ok do item 7): "Hoje as fases 1 e 2 estão concluídas, as versões 0.1.0, 0.1.1, 0.2.0, 0.2.1 e 0.3.0 já saíram (a 0.2.0 traz filtros novos e deixa o 2Captcha preparado para a fase 2; a 0.2.1 deixa a lista de vagas mais rápida e faz o aviso «Salvo.» sumir sozinho; a 0.3.0 traz o navegador com login, o LinkedIn, o visual novo do painel, a aba Contas, o Panorama e a fila de candidaturas) e as outras fases estão planejadas." Nenhuma versão antiga sai da frase, e o resto do Contexto (a decisão da D138) não muda. Os outros documentos de estado vivo (Roteiro, README, CONTRIBUTING) acompanham. A seção da 0.3.0 no CHANGELOG resume tudo o que está em "Não lançado": a fase 2 com o LinkedIn, o visual novo, Contas, o Panorama e a fila. Se o dono quiser a 0.3.0 antes do fim da fase 2, a ADR 0017 muda primeiro, e a T291 deixa a fase 2 como "em andamento". | `test_changelog_fecha_a_0_3_0` |
| E15 | Na faixa, "e mais {n} para responder" leva a `/panorama#para-responder`. O Panorama só existe depois da T288, por isso a T285 e a T288 entram juntas no `lote/panorama-tela`, e o lote só vai para a `dev` com as duas. O link nunca dá 404 na `dev`. | `test_e_mais_n_leva_ao_panorama` |
| E16 | Datas do painel no dia local. `data_curta` e `data_completa` (`painel/formatos.py`) fazem só `fromisoformat` e `strftime`, sem converter o fuso, e o relógio grava em UTC (`status_em`, `evento.criado_em`, `abriu_em`). Uma ação às 22:30 de Brasília sairia com o dia seguinte. A correção é uma só, na função compartilhada, na T283: um instante com fuso passa por `.astimezone()` antes do `strftime`; data sem hora (prazo, início) não muda. Isso também acerta o dia que hoje sai em UTC nas telas de Sites, Sugeridas e Programas; em Fontes nada muda, porque lá a data já chega local (`_local` de `rotas/fontes.py`). A alternativa, converter em cada chamador como o `_faixa` de `rotas/detalhe.py` faz, deixa o erro voltar no próximo chamador. | `test_instante_vira_dia_local` |
| E17 | Vaga oculta. `perguntas_pendentes` deixa fora a vaga ocultada à mão (`v.oculta_manual <> 1`): quem escondeu a vaga não quer a pergunta sobre ela. `oculta_manual` tem três valores (`0001_inicial.sql`: 0 regras, 1 à mão, -1 mostrar mesmo assim), e o `_OCULTA` de `banco/leitura.py` só trata o 1 como oculta à mão; por isso o filtro é `<> 1`, nunca `= 0`, que tiraria também a vaga que a pessoa mandou mostrar (`mostrar` de `banco/acoes.py`). As vagas que só uma regra da busca escondeu continuam, porque a regra depende da busca e a pergunta não. `salvas_que_fecham` segue a aba Salvas, que mostra a salva oculta (`ABAS["salvas"]` de `banco/leitura.py`): salvar é um ato da pessoa. | `test_pendentes_sem_oculta_a_mao` |
| E18 | O Desfazer da faixa decide no servidor para onde volta. `desfazer_candidatura(con, vaga_id, agora)` não recebe o status de antes do formulário: lê o último evento de status da vaga e só age se ele for `mudou_status` com `para = 'candidatei'` e `de` em `nova` ou `salva`, voltando para esse `de`. "Evento de status" é `acao IN ('salvou', 'mudou_status', 'desfez') AND para IS NOT NULL`: o `desfez` que `trazer_de_volta` grava (a vaga ocultada à mão volta à lista) não tem `de` nem `para` e não é troca de status. Assim uma confirmação velha ou um formulário mexido não levam a vaga a um status que ela não teve. | `test_desfazer_volta_ao_de_do_ultimo_evento`, `test_desfazer_depois_de_desfez_nao_muda`, `test_desfazer_ignora_desfez_da_ocultacao` |
| E19 | A próxima busca no Panorama. A chave `panorama.busca.proxima` do desenho 5.8 só tem `{hora}` ("por volta das {hora}"), e a busca roda a cada 3 horas (`INTERVALOS["busca"]` de `agenda/agendador.py`), então a próxima pode cair no dia seguinte. No mesmo dia local, a T288 usa a chave do desenho só com a hora; em outro dia, uma chave nova, `panorama.busca.proxima_dia`, com `{dia}` e `{hora}`. Mandar o dia e a hora juntos em `{hora}` sairia "por volta das 17/11 01:00". A alternativa, uma chave só com `{dia}` e `{hora}` sempre, troca o texto do desenho também no caso comum. | `test_ultima_e_proxima_busca`, `test_proxima_no_mesmo_dia_so_hora` |
| E20 | A vaga na tela depois da faixa (desenho 5.6, D147.29). As rotas de resposta e de Desfazer mandam `HX-Trigger: candidatura-mudou, vaga-mudou-{vaga_id}`. No detalhe, o `#estado-da-vaga` (T286) pede de novo o próprio `GET /vagas/{id}` com `hx-select`; na lista, o `<article id="vaga-{id}">` (T285) pede `GET /vagas/{vaga_id}/cartao`, rota nova em `rotas/vagas.py` que usa o mesmo `_resposta`, com o parâmetro novo `foco: bool = True` valendo `False`, para não tirar o foco da faixa. O evento é por vaga porque o painel roda com `allowEval: false`, sem filtro de evento, e um evento só faria até 50 cartões se pedirem de novo. Não há corrida com o `HX-Trigger` disparado antes da troca: a gravação já foi feita, e esses blocos não usam a chave `mostrando`. Alternativa: `hx-swap-oob` na resposta da faixa, decidindo pela `HX-Current-URL`; mais código, contexto do detalhe em outro módulo e `htmx:oobErrorNoTarget` sem o bloco. Recomendo o evento por vaga. | `test_resposta_sim_troca_status_e_dispara_evento`, `test_cartao_escuta_a_vaga`, `test_cartao_get_devolve_corpo_sem_foco`, `test_detalhe_estado_escuta_a_vaga`, `test_tela_detalhe_atualiza_depois_da_faixa`, `test_tela_cartao_atualiza_depois_da_faixa` |
| E21 | O `voltar` da faixa (desenho 5.6, D147.31). A regra do `de_volta` sai para `caminho_do_painel(voltar) -> str` em `painel/seguranca.py`, sem mudar, e o `de_volta` passa a usá-la. A rota da faixa tira esquema e host do `HX-Current-URL` e passa o resto pela mesma função; sem o cabeçalho, `/`. Alternativa: `voltar=/` fixo na faixa, já que a faixa só existe com JavaScript e as respostas com `HX-Request` nunca usam o `voltar`; é menos código, mas manda a pessoa para o início se um dia o POST sair sem HTMX. Recomendo o `HX-Current-URL`, como a revisão pediu. | `test_voltar_sai_do_hx_current_url`, `test_acao_sem_htmx_volta_para_a_pagina` |

## Foco da revisão

| # | Entrada ou condição | O que a pessoa espera | Teste | Tarefa |
|---|---|---|---|---|
| RF1 | A pessoa clica em "Candidatar-se", se candidata na aba nova e volta à janela do joBot | A faixa "Você se candidatou a {titulo} ({empresa})?" com Sim e Ainda não | `test_tela_volta_a_janela_mostra_a_faixa` (CI) | T284, T285 |
| RF2 | "Sim, me candidatei" e depois "Desfazer" | O status vai a Candidatei e volta ao de antes. A pergunta não volta, e os eventos são `mudou_status` e `desfez` | `test_resposta_sim_troca_status_e_dispara_evento`, `test_desfazer_volta_ao_status_anterior_sem_reabrir`, `test_desfazer_ignora_desfez_da_ocultacao`, `test_tela_detalhe_atualiza_depois_da_faixa` | T281, T285, T286 |
| RF3 | A pessoa responde Sim e troca de janela antes de clicar em Desfazer | Ao voltar, o Desfazer continua à vista e o leitor de tela não anuncia de novo | `test_confirmacao_fica_com_mesmo_total_204`, `test_mesmo_estado_responde_204` | T285 |
| RF4 | A descrição traz `rh@example.com?cc=outro@example.org` ou `%0A` encostado no endereço | Nenhum botão de e-mail. O `href` nunca leva parâmetro além do `subject` | `test_mailto_sem_parametro_injetado`, `test_recusa_caracteres_de_query_no_local` | T280, T286 |
| RF5 | A vaga tem link próprio de candidatura e um e-mail na descrição | O link continua o botão principal, e o e-mail é secundário | `test_email_vira_secundario_com_link_http` | T286 |
| RF6 | Prazo de uma vaga salva "hoje" visto às 23:30 de Brasília (02:30 do dia seguinte em UTC) | A vaga entra em "Salvas que fecham", com o dia local | `test_prazo_hoje_ate_7_dias_dia_local` | T282 |
| RF7 | Uma vaga foi de Oferta para Recusada | A linha do tempo mostra só "Recusada em {data}" | `test_oferta_depois_recusada` | T282 |
| RF8 | Duas aberturas gravadas com fusos diferentes (UTC e `-03:00`) | A faixa mostra a mais recente pelo instante, não pela ordem do texto | `test_pendentes_mais_recente_primeiro` | T281 |
| RF9 | O relógio do computador voltou para antes da última busca | A linha "Próxima busca" some no Panorama e em Fontes, do mesmo jeito | `test_proxima_com_relogio_que_voltou`, `test_proxima_igual_a_de_fontes` | T283, T288 |
| RF10 | Banco só com vagas fechadas, uma Candidatei e uma Salva com pergunta pendente | O Panorama não mostra o estado vazio; Hoje, Candidaturas e "Para responder" aparecem com os zeros | `test_so_vagas_fechadas_com_candidatura_nao_e_vazio` | T288 |
| RF11 | Uma pergunta pendente com o Panorama aberto | A faixa e "Para responder" na mesma página, sem `id` repetido | `test_ids_unicos_com_faixa_e_para_responder` | T285, T288 |
| RF12 | `POST /vagas/{id}/candidatura` sem o cabeçalho CSRF | Recusado, nada gravado | `test_post_sem_csrf_recusado` | T284 |
| RF13 | O `GET /aviso-candidatura` dá erro 500 | A página continua; a faixa fica como estava | `test_erro_nao_quebra_a_pagina` | T285 |
| RF14 | Leitor de tela no Panorama | Lê "Remoto, 120" pelo texto do link; a barra é `aria-hidden` | `test_barra_aria_hidden_e_numero_no_texto` | T288 |

## Ordem

| Onda | Tarefas | Branch | Por quê |
|---|---|---|---|
| 1 | T280, T282 | cada uma numa `feat/` própria tirada da `dev`, juntas num `lote/panorama-dados` | função pura e consultas: não mudam tela e podem entrar na `dev` com o CI verde antes do portão T258 |
| 2 | T281 | da `dev` com a T270, no mesmo `lote/panorama-dados` se ele ainda estiver aberto | a `0011` vem depois da `0010_sessao_site.sql` (o teste de versão conta os `.sql`) |
| 3 | — | — | espera: o portão T258 do visual, a branch longa na `dev`, a T261, a T264, a T265 e o `lote/contas-tela` (T275 a T278) na `dev` |
| 4 | T283 | da `dev` com a T261 e a T276 | muda de lugar os cartões de Fontes e `contas_em_queda`, por cima do que o visual e Contas deixaram, e põe o dia local em `data_curta` e `data_completa` (E16) antes das telas que mostram datas |
| 5 | T284; depois T285, T286 e T287 | a T284 da `dev` com a onda 4; as outras da branch do `lote/panorama-tela` com a T284; todas juntas no `lote/panorama-tela` | a T285 e a T286 usam a rota e o `data-candidatura` da T284. A T285, a T286 e a T287 mexem em `test_i18n.py` e nos catálogos: juntar uma depois da outra, unindo à mão («Junção do lote») |
| 6 | T288; depois T289 | da branch do `lote/panorama-tela` com a onda 5 | o Panorama usa a macro da pergunta (T285) e as consultas (T282, T283); a lateral e a paleta vêm depois da página. O lote só vai para a `dev` com a T288 (E15) |
| 7 | T290 | da `dev` com o `lote/panorama-tela` | documentos de quem usa |
| 8 | T291 | da `dev`, por último, com a fase 2 concluída (E14) | a 0.3.0: versão, CHANGELOG, PR da `dev` para a `main` |

---

### T280: endereço de candidatura no texto da vaga
`depende_de: —` · desenho 5.7 (Achar o endereço), D147.22

**Arquivos:**
- criar `src/jobot/nucleo/candidatura.py`, `tests/unidade/test_email_de_candidatura.py`.

**Interfaces:**
- `GATILHOS: Final[tuple[str, ...]]`: as palavras-gatilho em pt, en e es do desenho 5.7. Os prefixos `candidat` e `postula` casam o começo da palavra. A comparação é por `casefold`, com e sem acento ("currículo" e "curriculo"). A lista final é de quem constrói, mantendo os três idiomas.
- `email_de_candidatura(texto: str) -> str | None`:
  - acha os candidatos no texto cru, com uma expressão compilada com `re.ASCII`;
  - parte local de 1 a 64 caracteres de `A-Za-z0-9._+-`;
  - domínio de dois ou mais rótulos, cada um de 1 a 63 caracteres de `A-Za-z0-9-`, sem `-` na ponta;
  - endereço inteiro com até 254 caracteres;
  - antes e depois do endereço, só começo ou fim do texto, espaço, quebra de linha, `(`, `)`, `<`, `>`, `,`, `;`, `:` ou o ponto de fim de frase;
  - qualquer outro caractere encostado recusa o candidato inteiro, sem cortar o endereço para ele caber, e a busca segue para o próximo;
  - recusa `noreply` e `no-reply` na parte local;
  - o candidato só vale com uma palavra de `GATILHOS` na mesma linha ou na mesma frase (o trecho entre `.`, `!` ou `?` seguidos de espaço ou fim de linha);
  - devolve o primeiro que passar, sem o ponto de fim e com o domínio em minúsculas;
  - texto vazio devolve `None`.
- Fixtures e testes só com `example.com` e `example.org`, sem nome de pessoa («Fixtures»).

- [ ] **Primeiro, valor errado:** `email_de_candidatura` devolve `None` sempre.
- [ ] **Testes que falham** em `tests/unidade/test_email_de_candidatura.py`:
  - **Um teste por idioma:**
    - `test_acha_email_com_gatilho_pt`: "Envie seu currículo para rh@example.com." dá `"rh@example.com"`.
    - `test_acha_email_com_gatilho_en`: "Send your resume to jobs@Example.ORG" dá `"jobs@example.org"`.
    - `test_acha_email_com_gatilho_es`: "Postulaciones: talento@example.com" dá o endereço.
  - **Recusas.** Cada uma tem controle positivo na mesma montagem: o mesmo endereço, separado direito e com gatilho, é achado. Como o valor errado devolve `None`, o teste nasce vermelho.
    - `test_ignora_email_sem_gatilho`: o endereço numa frase sem gatilho dá `None`.
    - `test_ignora_noreply`: `noreply@` e `no-reply@` dão `None`.
    - `test_recusa_endereco_longo`: parte local de 65 caracteres e endereço de 255 dão `None`.
    - `test_recusa_caracteres_de_query_no_local` e `test_recusa_caracteres_de_query_no_dominio` (parametrizados): `?cc=`, `&bcc=`, `=`, `%0A`, `#` e `/` encostados no endereço dão `None`.
    - `test_recusa_fora_de_ascii`: letra acentuada encostada ou dentro dá `None`.
    - `test_recusa_rotulo_com_hifen_na_ponta`: `rh@-example.com` e `rh@example-.com` dão `None`.
  - **Resto:**
    - `test_tira_pontuacao_do_fim`: "... para rh@example.com." dá o endereço sem o ponto.
    - `test_segue_para_o_proximo`: o primeiro candidato recusado e o segundo válido na mesma frase de gatilho dão o segundo.
    - `test_texto_vazio_devolve_none`: é guarda e nasce verde, porque o valor errado já devolve `None`. Mutante: devolver `""`.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_email_de_candidatura.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** o mesmo arquivo e `tests/unidade/test_camadas.py`; ruff; mypy no CI.

### T281: migração 0011 e gravação da candidatura
`depende_de: T270` · desenho 5.5, 5.6 (Respostas, Regras), P1 (a), E2, E3, E6

**Arquivos:**
- criar `src/jobot/banco/migracoes/0011_candidatura.sql`, `tests/integracao/test_migracao_0011.py`, `tests/integracao/test_candidatura.py`;
- modificar `src/jobot/banco/acoes.py`, `src/jobot/banco/leitura.py`;
- modificar `wiki/Arquitetura.md` e `wiki/Architecture.md`. O `erDiagram` ganha a entidade `candidatura`, com as colunas, e a relação `vaga ||--o| candidatura : "vaga_id"`, porque `tests/unidade/test_arquitetura.py` exige no diagrama toda tabela e toda chave estrangeira dos `.sql`.

**Interfaces:**
- `0011_candidatura.sql`, só `CREATE`, sem `DROP` nem reconstrução:

  ```sql
  -- Quando a pessoa abriu a candidatura de cada vaga pelo painel (D147.15): uma linha por vaga, atualizada no lugar.
  CREATE TABLE candidatura (
    vaga_id   INTEGER PRIMARY KEY REFERENCES vaga(id),
    abriu_em  TEXT NOT NULL,
    perguntar INTEGER NOT NULL DEFAULT 1 CHECK (perguntar IN (0, 1))
  );
  CREATE TRIGGER candidatura_sem_delete BEFORE DELETE ON candidatura
  BEGIN SELECT RAISE(ABORT, 'candidatura não é apagada'); END;
  ```

- `banco/acoes.py`: as três funções abaixo correm sob `_transacao` (`BEGIN IMMEDIATE`). Vaga que não existe dá `LookupError`, o contrato de `acoes.py` que a rota transforma em 404.
  - `abriu_candidatura(con, vaga_id: int, agora: datetime) -> bool`. Só com o status `nova` ou `salva`, grava `INSERT ... ON CONFLICT(vaga_id) DO UPDATE SET abriu_em = excluded.abriu_em, perguntar = 1` e devolve `True`. Com outro status, não grava e devolve `False`.
  - `responder_candidatura(con, vaga_id: int, sim: bool, agora: datetime) -> str | None`. Só age com `perguntar = 1` e o status `nova` ou `salva`:
    - `sim`: troca para `candidatei` pelo `_trocar_status` com a ação `mudou_status`, grava `perguntar = 0` e devolve o status de antes;
    - não `sim`: grava só `perguntar = 0` e devolve `None`;
    - fora dessas condições (já respondida, ou vaga em Candidatei ou acima): não muda nada e devolve `None`.
  - `desfazer_candidatura(con, vaga_id: int, agora: datetime) -> bool` (E18). Lê o último evento de status da vaga (`acao IN ('salvou', 'mudou_status', 'desfez') AND para IS NOT NULL`, por `id DESC`, a ordem real de gravação; o instante erra quando o relógio volta, D151; o `para IS NOT NULL` deixa fora o `desfez` de `trazer_de_volta`, que não tem `de` nem `para`). Só com o status atual `candidatei` e esse evento sendo `mudou_status` com `para = 'candidatei'` e `de` em `nova` ou `salva`, troca para esse `de` pelo `_trocar_status` com a ação `desfez` e devolve `True`. Nos outros casos, não grava e devolve `False`. Nunca mexe em `perguntar`.
- `banco/leitura.py`:
  - `@dataclass(frozen=True) class Pergunta`, com `vaga_id: int`, `titulo: str`, `empresa: str`, `abriu_em: str` e `status: str`.
  - `perguntas_pendentes(con, limite: int) -> tuple[list[Pergunta], int]`: junta `candidatura` e `vaga` com `perguntar = 1 AND v.status IN ('nova','salva') AND v.oculta_manual <> 1` (E17), ordenadas por `julianday(c.abriu_em) DESC, c.vaga_id DESC`, até `limite`. O segundo item é o total das pendentes.
  - `abertura_da_candidatura(con, vaga_id: int) -> str | None`: o `abriu_em` da linha, ou `None`.

- [ ] **Primeiro, valor errado.** Pelo mutante do «Teste de migração», o vermelho sem a migração não vale. Por isso o primeiro passo cria as peças com defeito:
  - a `0011` sem o `CHECK` de `perguntar` e sem o gatilho;
  - `abriu_candidatura` devolve `False` sem gravar;
  - `responder_candidatura` devolve `None` sem gravar;
  - `desfazer_candidatura` devolve `False` sem gravar;
  - `perguntas_pendentes` devolve `([], 0)`;
  - `abertura_da_candidatura` devolve `None`.
- [ ] **Testes que falham** em `tests/integracao/test_migracao_0011.py`, que lê só o arquivo `0011`:
  - `test_candidatura_sem_delete`: pelo `_recusa`, o `DELETE` de uma linha dá `True`.
  - `test_perguntar_so_0_ou_1`: pelo `_recusa`, gravar `perguntar = 2` dá `True`; controle positivo: `0` e `1` passam.
  - `test_vaga_id_referencia_vaga`: com `foreign_keys` ligado, pelo `_recusa`, uma linha para uma vaga que não existe dá `True`. É guarda e nasce verde, porque o valor errado já tem a `REFERENCES`. Mutante: tirar a `REFERENCES`.
  - `test_antes_nada_se_perde`: as migrações `[:10]` num banco em `tmp_path`, com vagas e eventos gravados; depois de aplicar a `0011`, as linhas de `vaga` e `evento` são as mesmas e a versão é `ULTIMA`. É guarda; mutante: a `0011` com `UPDATE vaga SET status = 'nova'`.
- [ ] **Testes que falham** em `tests/integracao/test_candidatura.py` (relógio fixo, `TZ` fixado como o «Dia de calendário» pede):
  - **Abertura:**
    - `test_abriu_grava_e_reabre_pergunta`: grava, `perguntar` vai a 0 por `responder_candidatura(..., sim=False, ...)`, e abrir de novo atualiza `abriu_em` e volta `perguntar` a 1.
    - `test_abriu_com_candidatei_nao_grava`: devolve `False` e nenhuma linha. Controle positivo na mesma montagem: com outra vaga `salva`, devolve `True`.
    - `test_abriu_vaga_inexistente_lookuperror`: pelo `_recusa`.
  - **Respostas:**
    - `test_responder_sim_muda_status_e_fecha_pergunta`.
    - `test_responder_sim_grava_evento_mudou_status`: com `de = 'salva'` e `para = 'candidatei'`.
    - `test_responder_sim_devolve_o_status_de_antes` (E6): `"nova"` e `"salva"`.
    - `test_responder_ainda_nao_so_fecha`: o status não muda e nenhum evento novo.
    - `test_responder_duas_vezes_nao_muda_nada`: o segundo Sim devolve `None` e não grava evento. Controle: o primeiro devolve o status.
  - **Pendentes:**
    - `test_pendentes_so_nova_e_salva`: na mesma montagem, uma `salva` aberta e uma `candidatei` com `perguntar = 1` (marcada por `mudar_status` depois da abertura). A lista é só a `salva` e o total é 1. O vermelho vem do controle positivo: o valor errado devolve `([], 0)` e a `salva` falta. A parte "a `candidatei` não entra" prende a regra; mutante: tirar o filtro de status.
    - `test_pendentes_sem_oculta_a_mao` (E17): três vagas abertas: uma ocultada por `ocultar` (1), uma com `mostrar` chamado direto, sem `ocultar` antes (-1, "mostrar mesmo assim"; de 0, o `mostrar` grava -1 e o evento `mostrou`, e de 1 ele lança `ValueError`, por isso nunca depois de `ocultar`) e uma sem nada (0). A lista traz a de -1 e a de 0, e o total é 2. O vermelho vem do controle (as vagas à vista faltam no valor errado). Mutantes: tirar o filtro (a de 1 entra) e trocar `<> 1` por `= 0` (a de -1 some).
    - `test_pendentes_mais_recente_primeiro`: `abriu_em` de `2026-11-16T10:00:00-03:00` (13:00 em UTC) e `2026-11-16T12:30:00+00:00`. A primeira vem antes, ao contrário da ordem do texto. O total é 2.
    - `test_abertura_da_candidatura`.
  - **Desfazer:**
    - `test_desfazer_volta_e_grava_desfez`: uma `salva` aberta, Sim e depois `desfazer_candidatura`. Devolve `True`, o status volta a `salva` e há um evento `desfez` de `candidatei` para `salva`.
    - `test_desfazer_volta_ao_de_do_ultimo_evento` (E18): uma `nova` aberta, Sim e desfazer. O status volta a `nova`, e não a `salva`, que é o anterior do fluxo em `_ANTERIOR`. Mutante: usar `_ANTERIOR`.
    - `test_desfazer_so_com_status_candidatei`: depois do Sim, a vaga vai a `entrevista` por `mudar_status`; desfazer devolve `False` e não grava. Controle: outra vaga, só com o Sim, devolve `True`.
    - `test_desfazer_depois_de_desfez_nao_muda` (E18): uma `salva` aberta, Sim (`mudou_status` de `salva` para `candidatei`), `mudar_status` para `entrevista` e `desfazer_status`, que volta a `candidatei` com um evento `desfez`. `desfazer_candidatura` devolve `False`, e o status continua `candidatei`. É guarda e nasce verde, porque o valor errado devolve `False`. Mutante: procurar o último `mudou_status` com `para = 'candidatei'` em vez do último evento de status; com ele, a vaga voltaria a `salva`, e o teste exige `candidatei`. (Ler o `de` sem olhar a `acao` não serve de mutante: o `desfez` tem `de = 'entrevista'`, que a regra já recusa.)
    - `test_desfazer_com_relogio_que_volta` (E18, D151): uma `salva` aberta, Sim às T+5h (`mudou_status` de `salva` para `candidatei`), `mudar_status` para `entrevista` às T+1h e `desfazer_status` às T+2h, que volta a `candidatei` com `desfez`. `desfazer_candidatura` devolve `False`, o status continua `candidatei` e nenhum evento novo é gravado. Falha no vermelho pelo valor errado (`True`, e a vaga iria a `salva`). Mutante: voltar a ordenar por `julianday(criado_em) DESC, id DESC`.
    - `test_desfazer_ignora_desfez_da_ocultacao` (E18): uma `salva` aberta, Sim, `ocultar` e `trazer_de_volta` (que grava `desfez` com `de` e `para` nulos) e depois `desfazer_candidatura`. Devolve `True`, o status volta a `salva` e o último evento é um `desfez` de `candidatei` para `salva`. Falha no vermelho pelo valor errado (`False`). Mutante: tirar o `para IS NOT NULL`; com ele, o `desfez` da ocultação vira o último evento de status, e a função devolve `False` sem gravar.
    - `test_desfazer_nao_reabre_pergunta`: uma `salva` aberta, Sim e desfazer. A primeira asserção é a do status igual a `salva`, e é ela que falha no vermelho (o valor errado deixa a vaga em `candidatei`). Depois, `perguntas_pendentes(con, 10)` dá `([], 0)` e a linha de `candidatura` tem `perguntar = 0`; essa parte prende a regra, com o mutante "desfazer grava `perguntar = 1`".
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_migracao_0011.py tests/integracao/test_candidatura.py -q`.
- [ ] **Implementar** os itens de Interfaces e o `erDiagram` das duas páginas da wiki.
- [ ] **Ver passar:** os mesmos arquivos, `tests/integracao/test_migracoes.py`, `tests/unidade/test_arquitetura.py` e `tests/unidade/test_camadas.py`; ruff; mypy no CI do `lote/panorama-dados`.

### T282: datas dos passos, salvas que fecham e `status_em` na lista
`depende_de: —` · desenho 5.2 (Salvas que fecham, estado vazio), 5.4, E5

**Arquivos:**
- modificar `src/jobot/banco/leitura.py` e `src/jobot/banco/acoes.py` (`_DEGRAU` vira `DEGRAU`);
- modificar quem monta `Item` ou `Detalhe` à mão (conferir com `rtk grep -rn "Item(\|Detalhe(" src tests`);
- criar `tests/integracao/test_datas_dos_passos.py`, `tests/integracao/test_salvas_que_fecham.py`;
- modificar `tests/integracao/test_leitura.py`.

**Interfaces:**
- `DEGRAU` público em `banco/acoes.py`, com o valor de hoje. `datas_dos_passos` o importa (E5).
- `PASSOS: Final = ("salva", "candidatei", "entrevista", "oferta", "recusada")`.
- `datas_dos_passos(con, vaga_id: int) -> dict[str, str]`. Ordem dos passos: a de `PASSOS`. A regra:
  - para cada passo com degrau até o do status atual, vale o `criado_em` do evento mais novo, por `julianday(criado_em) DESC, id DESC`, com `para` igual ao passo e `acao IN ('salvou', 'mudou_status')`;
  - de `oferta` e `recusada`, só entra o que é o status atual;
  - passo sem evento não entra.
- `@dataclass(frozen=True) class Fechando`, com `vaga_id: int`, `titulo: str`, `empresa: str` e `prazo: str`.
- `salvas_que_fecham(con, agora: datetime, limite: int) -> list[Fechando]`: `v.status = 'salva' AND v.fechada_em IS NULL AND {_FECHA_LOGO}`, com o mesmo `:hoje` de `_hoje(agora)`, por `date(v.prazo), v.id`, até `limite`. A expressão `_FECHA_LOGO` é usada, nunca copiada. A salva oculta entra, como na aba Salvas (E17).
- `tem_vaga(con) -> bool`: `SELECT EXISTS(SELECT 1 FROM vaga)`.
- `Item` ganha `status_em: str | None`, e `Detalhe` herda. `_COLUNAS` ganha `v.status_em`, e `_item` o preenche.

- [ ] **Primeiro, valor errado:**
  - `datas_dos_passos` devolve `{}`;
  - `salvas_que_fecham` devolve `[]`;
  - `tem_vaga` devolve `False`;
  - `_item` põe `status_em=None`, com a coluna já na consulta.
- [ ] **Testes que falham** em `tests/integracao/test_datas_dos_passos.py`. Os eventos são gravados por `mudar_status` e `desfazer_status`, com o relógio avançando:
  - `test_passos_em_ordem`: Salva, Candidatei e Entrevista com as três datas, nessa ordem.
  - `test_passo_pulado_sem_data`: de Nova direto para Candidatei, só `candidatei`.
  - `test_desfeito_fica_fora`: Candidatei desfeito volta a Salva, e só `salva` entra.
  - `test_desfeito_e_refeito_vale_o_mais_novo`.
  - `test_salva_por_salvou`: a data do evento `salvou`.
  - `test_oferta_e_recusada_depois_de_entrevista`: com status Oferta, entram os quatro passos até Oferta.
  - `test_oferta_depois_recusada`: de Oferta para Recusada, entra `recusada` com a sua data e não entra `oferta`.
- [ ] **Testes que falham** em `tests/integracao/test_salvas_que_fecham.py` (`TZ` fixado em `America/Sao_Paulo`, «Dia de calendário»):
  - `test_prazo_hoje_ate_7_dias_dia_local`: `agora = 2026-11-16T23:30:00-03:00`. Entram os prazos `2026-11-16` e `2026-11-23`; ficam fora `2026-11-15` e `2026-11-24`.
  - `test_so_salvas`: uma `nova` com o mesmo prazo fica fora. Controle: a `salva` entra.
  - `test_limite_e_ordem`: sete salvas, `limite=5`, da que fecha primeiro.
  - `test_salva_fechada_na_fonte_fica_fora`: com `fechada_em` preenchido. Controle: a mesma vaga com `fechada_em` nulo entra.
- [ ] **Testes que falham** em `tests/integracao/test_leitura.py`:
  - `test_status_em_na_listagem`: `listar` traz o `status_em` gravado por `mudar_status`.
  - `test_tem_vaga`: banco vazio dá falso; com uma vaga oculta e fechada, verdadeiro. A parte do vazio é guarda.
  - `test_degrau_definido_uma_vez`: pelo AST, `DEGRAU` é atribuído num módulo só de `banco/`, e nenhum define `_DEGRAU`.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_datas_dos_passos.py tests/integracao/test_salvas_que_fecham.py tests/integracao/test_leitura.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos, `tests/integracao/test_acoes.py` e `tests/unidade/test_camadas.py`; ruff; mypy no CI do `lote/panorama-dados`.

### T283: consultas da busca e das contas fora das rotas, e o dia local nas datas
`depende_de: T261, T276` · desenho 5.2 (A busca), 8, E4, E16

**Nota da execução:** a E16 já tinha entrado pela T276. O `_ler_data` de `painel/formatos.py` já faz `.astimezone()` em instante com fuso, coberto por `test_instante_em_utc_mostra_o_dia_local`. Por isso `formatos.py` não mudou nesta tarefa. O `test_instante_vira_dia_local` entrou como guarda verde: caso de fronteira 01:30Z de 17/11 em pt e en, com o controle sem hora. O mutante sem `.astimezone()` reprova. O `test_proxima_igual_a_de_fontes` fica para a T288.

**Arquivos:**
- criar `src/jobot/painel/saude_das_fontes.py`, `tests/unidade/test_saude_das_fontes.py`;
- modificar `src/jobot/painel/rotas/fontes.py`, `src/jobot/painel/rotas/aviso_contas.py` e `src/jobot/painel/consultas.py`;
- modificar `src/jobot/painel/formatos.py` e `tests/unidade/test_formatos.py` (E16);
- modificar os testes que importam os nomes movidos. Conferir com `rtk grep -rn "rotas.fontes import\|rotas import fontes\|contas_em_queda\|_cartoes" tests src`, olhando também os `setattr` e os `monkeypatch` («Junção do lote»).

**Interfaces:**
- `painel/saude_das_fontes.py` recebe de `rotas/fontes.py`, sem cópia e com as assinaturas de hoje:
  - `EXECUCOES`, `Reporte`, `Escopo`, `Cartao`, `estado_dos_escopos` e `motivo_mais_grave`;
  - os ajudantes privados e as constantes de que `_cartoes` precisa;
  - o próprio `_cartoes`, como `cartoes(con, agora, historico) -> list[Cartao]`.

  O módulo importa `nucleo`, `banco` e `agenda` (para `INTERVALOS`), nunca `jobot.painel.rotas`. `rotas/fontes.py` fica só com as rotas e importa de lá.
- `proxima_busca(con, agora: datetime) -> datetime | None`, no mesmo módulo: `inicio_da_ultima_completa(con, "busca") + INTERVALOS["busca"]`. Devolve `None` sem busca completa e quando o início é depois de `agora` (o relógio voltou). O instante sai no fuso local (`.astimezone()`), como o `_local` de `rotas/fontes.py` faz com o resultado de hoje. `cartoes` passa a chamá-la no lugar do cálculo em linha.
- `contas_em_queda(con, leitores)` muda de `rotas/aviso_contas.py` para `painel/consultas.py`, com a assinatura de hoje, e `aviso_contas.py` importa de lá.
- `painel/formatos.py` (E16): em `data_curta` e `data_completa`, um instante com fuso passa por `.astimezone()` antes do `strftime`, no ajudante `_ler_data` que as duas já usam. Data sem hora (prazo, início) não muda. As duas continuam recebendo texto; quem tem um `datetime` passa `.isoformat()`, como os templates de Sites e Sugeridas já fazem.

- [x] **Primeiro, valor errado:** `proxima_busca` existe no módulo novo e devolve `None` sempre; nada mudou de lugar ainda. Em `formatos.py`, nenhum: o código de hoje é o valor errado do teste de dia local.
- [x] **Testes que falham** em `tests/unidade/test_saude_das_fontes.py`, com o banco em memória pelo `migrar` e o relógio fixo:
  - `test_proxima_busca_tres_horas_depois`: com uma busca completa às 9h, `proxima_busca` às 10h dá 12h.
  - `test_proxima_com_relogio_que_voltou`: o início depois de `agora` dá `None`. Controle: com `agora` depois do início, dá a hora.
  - `test_sem_busca_completa_none`: é guarda e nasce verde. Mutante: devolver `agora + INTERVALOS["busca"]` sem busca.
  - `test_definidos_uma_vez`: pelo AST, `cartoes`, `proxima_busca` e `contas_em_queda` são definidos uma vez só em `src/jobot/painel/`, fora de `rotas/`; nenhum arquivo de `rotas/` define `_cartoes`. Nasce vermelho, porque `_cartoes` ainda está em `rotas/fontes.py`.
  - `test_saude_nao_importa_rotas`: pelo AST, nenhum `import` de `jobot.painel.rotas` em `saude_das_fontes.py` nem em `consultas.py`. É guarda e nasce verde, porque o módulo novo do valor errado não importa `rotas/`. O `consultas.py` vem de um plano anterior e não foi conferido aqui: se ele importar `rotas/`, o teste nasce vermelho e a T283 corrige junto (R1). Mutante: um `from jobot.painel.rotas.vagas import relogio_do_painel` em `saude_das_fontes.py` faz o teste falhar. Ele cobre só esses dois módulos (o `painel/cliente.py` já importa de `rotas/vagas.py`).
- [x] **Teste que falha** em `tests/unidade/test_formatos.py` (E16), com o `TZ` fixado em `<-03>3` por `tzset` e desfeito no fim, como a fixture `fuso_local` de `tests/integracao/test_execucao.py` («Dia de calendário»):
  - `test_instante_vira_dia_local`: `"2026-11-17T01:30:00+00:00"` dá `16/11` e `16/11/2026` em pt, e `11/16` em en. O vermelho é a asserção do dia: o código de hoje dá `17/11`. Controle na mesma montagem: `"2026-11-17"`, sem hora, continua `17/11`.
  - O caso `"2026-11-13T12:00:00+00:00"` do `test_datas` continua valendo.
- [x] **Ver falhar:** `uv run pytest tests/unidade/test_saude_das_fontes.py tests/unidade/test_formatos.py -q`.
- [x] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:**
  - os mesmos arquivos, mais `tests/integracao/test_rota_fontes.py`, `tests/integracao/test_aviso_contas.py`, `tests/integracao/test_rota_preferencias.py` (registra os dois nomes como globais do Jinja), `tests/unidade/test_rotas_sem_copias.py`, `tests/unidade/test_consultas.py` e `tests/unidade/test_camadas.py`;
  - ruff;
  - a suíte inteira e mypy no CI do `lote/panorama-tela`.

### T284: registro da abertura da candidatura
`depende_de: T281, T283, T264` · desenho 5.5 (Rota, Clique), P5 (a), E7, E10

**Arquivos:**
- criar `src/jobot/painel/rotas/candidatura.py`, `tests/integracao/test_rota_candidatura.py`, `tests/tela/test_tela_pergunta_candidatura.py` (só a parte do clique; a T285 completa o arquivo);
- modificar o trecho de template do detalhe que a T255 e a T264 deixaram compartilhado (o link de candidatura), `src/jobot/painel/static/js/app.js` e `tests/integracao/test_rota_detalhe.py`.

**Interfaces:**
- `rotas/candidatura.py`, `POST /vagas/{vaga_id}/candidatura`:
  - chama `abriu_candidatura` com a hora de `relogio_do_painel`;
  - responde 204 sem corpo, gravando ou não;
  - `LookupError` dá 404;
  - o CSRF vem pelo cabeçalho `X-CSRF-Token`, que o middleware de hoje confere.
- O link de candidatura do detalhe ganha `data-candidatura="/vagas/{{ vaga.id }}/candidatura"` e continua um link normal, com `target="_blank"` e `rel="noopener noreferrer"`.
- `app.js`: um ouvinte de `click` por delegação no `document`. Em `event.target.closest("a[data-candidatura]")`, chama `fetch(url, {method: "POST", keepalive: true, headers: {"X-CSRF-Token": token}})`, com o token da `meta` que o `app.js` já lê. Não chama `preventDefault`, e erro do `fetch` é engolido com `.catch(() => {})`: o registro é melhor esforço. O ouvinte fica no `document`, nunca no nó, porque o `hx-push-url` troca o `body` («JS do painel»).

- [ ] **Primeiro, valor errado:** a rota responde 204 sem chamar `abriu_candidatura`, e o template ainda não tem `data-candidatura`.
- [ ] **Testes que falham** em `tests/integracao/test_rota_candidatura.py`:
  - `test_post_204`: responde 204, sem corpo, e `abertura_da_candidatura` traz a hora do relógio injetado.
  - `test_post_com_candidatei_204_sem_gravar`: 204 e nenhuma linha. Controle: uma `salva` grava.
  - `test_post_vaga_inexistente_404`.
  - `test_post_sem_csrf_recusado`: o mesmo POST sem o cabeçalho é recusado e nada é gravado. Controle: com o cabeçalho, grava.
  - `test_rotas_de_candidatura_casam_antes_do_detalhe` (E7): para cada rota de `candidatura.router`, a primeira rota de `criar_app(...).routes` cujo `matches` dá `Match.FULL` para o caminho e o método dela é a própria rota.
- [ ] **Teste que falha** em `tests/integracao/test_rota_detalhe.py`: `test_link_de_candidatura_tem_data_candidatura`.
- [ ] **Teste de tela** (CI) em `tests/tela/test_tela_pergunta_candidatura.py`: `test_tela_clique_registra`. A vaga semeada aponta para um servidor local de teste; clicar em "Candidatar-se" abre a aba nova (`context.expect_page`), e o teste espera a resposta 204 do `POST` (`page.expect_response`, nunca `sleep`). Depois a linha existe no banco.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_candidatura.py tests/integracao/test_rota_detalhe.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos, `tests/unidade/test_rotas_sem_copias.py`, `tests/unidade/test_estaticos.py` e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI do `lote/panorama-tela`.

### T285: a faixa "Você se candidatou?"
`depende_de: T284, T256, T276` · desenho 5.6, E6, E8, E9, E15, E16, E18, E20, E21

**Arquivos:**
- criar `src/jobot/painel/rotas/aviso_candidatura.py`, `src/jobot/painel/templates/candidatura/_pergunta.html`, `src/jobot/painel/templates/aviso_candidatura/faixa.html`, `tests/integracao/test_rota_aviso_candidatura.py`;
- modificar `src/jobot/painel/rotas/candidatura.py` (resposta e desfazer), `src/jobot/painel/seguranca.py` (`caminho_do_painel`, E21), `src/jobot/painel/rotas/vagas.py` (`GET /vagas/{vaga_id}/cartao` e o parâmetro `foco` de `_resposta`, E20), `src/jobot/painel/templates/vagas/cartao.html`, `src/jobot/painel/templates/base.html`, `src/jobot/painel/static/css/casca.css`, o registro de ícones da T249 (`circle-help`, E12), `src/jobot/painel/i18n/{pt,en}/casca.json`, `tests/integracao/test_rota_vagas.py`, `tests/unidade/test_i18n.py`, `tests/unidade/test_estaticos.py` e `tests/tela/test_tela_pergunta_candidatura.py`.

**Interfaces:**
- `base.html`, depois do `#aviso-contas` e antes do `#faixa-desfazer`:

  ```html
  <div id="aviso-candidatura" role="status" hx-get="/aviso-candidatura" hx-trigger="load, focus from:window" hx-include="find input[name=mostrando]" hx-swap="innerHTML"></div>
  ```

  Sem `candidatura-mudou` no `hx-trigger` (desenho 5.6).
- `aviso_candidatura.py`, no molde de `aviso_versao.py`:
  - **Rota.** `GET /aviso-candidatura` lê `perguntas_pendentes(con, 1)` e o total.
  - **Chave.** `chave_mostrando(fragmento) -> str` monta `p{id}-{total}`, `c{id}-{total}` ou `v-0`.
  - **Quando responde 204, sem corpo.** O total de pendentes é o da chave recebida e:
    - a chave é `p` com a mesma vaga no topo; ou
    - a chave é `c` ou `v`.
  - **Quando renderiza a faixa.** Nos outros casos, inclusive sem a chave.
  - **Corpo da faixa.** Todo fragmento leva `<input type="hidden" name="mostrando" value="...">`. Sem pendente, o fragmento vazio só tem esse campo.
  - **`voltar` do fragmento** (E9, E21). A página de verdade não é `/aviso-candidatura`, então o `url_de_volta` da casca não serve. A rota lê o cabeçalho `HX-Current-URL` e passa por `caminho_do_painel`; sem o cabeçalho, `/`.
- `seguranca.py` (E21): `caminho_do_painel(voltar: str) -> str` é a regra de hoje do `de_volta`, tirada para fora sem mudar: devolve caminho e consulta quando `voltar` não tem esquema nem host, começa com `/`, não começa com `//` e não tem `\`; senão, `/`. O `de_volta(voltar)` passa a ser `RedirectResponse(caminho_do_painel(voltar), status_code=303)`. A rota da faixa tira antes o esquema e o host do `HX-Current-URL` (`urlsplit`, só `path` e `query`) e passa o resto por `caminho_do_painel`. Uma regra só, sem cópia («Painel»). Os testes de hoje do `de_volta` (`test_acao_sem_htmx_volta_para_a_pagina` e o `voltar` de fora em `test_rota_execucao.py`) seguem verdes: um `voltar` com host continua indo para `/`.
- `rotas/candidatura.py` ganha duas rotas. As duas fazem o mesmo depois de gravar:
  - com `HX-Request`, devolvem o fragmento da faixa e `HX-Trigger: candidatura-mudou, vaga-mudou-{vaga_id}` (E20; também quando nada mudou, porque o `GET` de quem escuta só relê o banco);
  - sem ele, devolvem `de_volta(voltar)`;
  - `LookupError` dá 404.

  As duas rotas:
  - `POST /vagas/{vaga_id}/candidatura/resposta`, com `resposta` em `sim` ou `ainda_nao` (outro valor dá 422) e `voltar`. Chama `responder_candidatura`.
    - Sim com troca: o fragmento é a confirmação "{titulo} marcada como Candidatei.", com o Desfazer (`hx-post` para a rota abaixo, `hx-target="#aviso-candidatura"`, só com o CSRF e o `voltar`) e a chave `c{id}-{total}`.
    - Nos outros casos: a próxima pendente ou a faixa vazia.
  - `POST /vagas/{vaga_id}/candidatura/desfazer`, só com `voltar`. Chama `desfazer_candidatura`, que decide no servidor para onde a vaga volta (E18). Devolve a próxima pendente ou a faixa vazia, tenha desfeito ou não.
- **A vaga na tela, na lista** (E20, desenho 5.6 "A vaga na tela"). O `<article id="vaga-{id}">` de `vagas/cartao.html` ganha `hx-get="/vagas/{id}/cartao?busca={busca_id}&voltar={retorno codificado}" hx-trigger="vaga-mudou-{id} from:body" hx-swap="innerHTML"`. A rota `GET /vagas/{vaga_id}/cartao` fica em `rotas/vagas.py` (dois segmentos depois de `/vagas/`, como `/vagas/{vaga_id}/status`, então a ordem dos módulos não importa) e devolve `_resposta(request, con, vaga_id, voltar, busca, foco=False)`. O `_resposta` ganha `foco: bool = True`, e os chamadores de hoje não mudam. Sem `HX-Request`, a rota volta pelo `de_volta`, como as outras. O detalhe fica com a T286.
- `_pergunta.html` (E8), macro `pergunta(p, prefixo, total)`:
  - a frase `casca.aviso_candidatura.pergunta` e, embaixo, `casca.aviso_candidatura.quando`, com `data_completa(p.abriu_em, idioma)`, que dá o dia local (E16);
  - dois `<form method="post">` com o campo CSRF, `voltar` e `resposta`, com `hx-post` e `hx-target="#aviso-candidatura"`;
  - com `total > 1`, o link `casca.aviso_candidatura.mais` (`n = total - 1`) para `/panorama#para-responder`;
  - ids `{prefixo}-pergunta-{vaga_id}`;
  - título e empresa entram por `t()`, escapados.
- Faixa opaca no estilo do `#aviso-versao`, com o ícone `circle-help`, texto de 13px e os tokens da T248. Sem botão de fechar. O `div` vazio não ocupa espaço (`:empty`, e `{%- -%}` no fragmento, «CSS e template»). O campo escondido não conta como conteúdo visível, então o seletor de vazio é de quem constrói e é conferido na tela.
- i18n (pt e en): as seis chaves `casca.aviso_candidatura.*` do desenho 5.8, com os mesmos parâmetros.

- [ ] **Primeiro, valor errado:**
  - `GET /aviso-candidatura` devolve sempre o fragmento vazio com `v-0`;
  - as duas rotas POST respondem o fragmento vazio sem gravar, com `HX-Trigger: candidatura-mudou` só;
  - o `voltar` do fragmento é sempre `/`;
  - `GET /vagas/{vaga_id}/cartao` devolve `_resposta` com o `foco` de hoje (`True`).
- [ ] **Testes que falham** em `tests/integracao/test_rota_aviso_candidatura.py` (relógio injetado, linhas por `abriu_candidatura`):
  - **Fragmento:**
    - `test_sem_pendente_fragmento_vazio`: só o campo `mostrando` com `v-0`. Controle: depois de uma abertura, a pergunta aparece.
    - `test_mostra_a_mais_recente`.
    - `test_e_mais_n_leva_ao_panorama` (E15): com três pendentes, "e mais 2 para responder" e `href="/panorama#para-responder"`.
  - **Resposta:**
    - `test_resposta_sim_troca_status_e_dispara_evento`: os nomes do `HX-Trigger`, separados por vírgula e sem espaços, são exatamente `{"candidatura-mudou", f"vaga-mudou-{id}"}`, e a confirmação com Desfazer vem sem campo `para` no formulário (E18, E20).
    - `test_voltar_sai_do_hx_current_url` (E21): com `HX-Current-URL: http://127.0.0.1/vagas/{id}?busca=3`, o `voltar` dos formulários do fragmento é `/vagas/{id}?busca=3`. Parametrizado com `http://127.0.0.1//fora.test/x`, um caminho com `\` e sem o cabeçalho: `/`. O controle é o primeiro caso, que falha no valor errado.
    - `test_resposta_invalida_422`.
    - `test_resposta_sem_js_303`: o `Location` é o `voltar`.
    - `test_post_sem_csrf_recusado`.
  - **Desfazer:**
    - `test_desfazer_volta_ao_status_anterior_sem_reabrir`.
    - `test_desfazer_devolve_fragmento_da_faixa`: com `HX-Request`, o fragmento da faixa, e não `vagas/corpo.html`, com os nomes do `HX-Trigger` exatamente `candidatura-mudou` e `vaga-mudou-{id}`.
    - `test_desfazer_ignora_campo_para` (E18): uma `nova` aberta e Sim; o POST do Desfazer leva `para=salva` à mão, e a vaga volta a `nova`. É guarda e nasce verde depois da T281. Mutante: a rota ler `para` do formulário.
    - `test_desfazer_sem_sim_nao_muda`: uma vaga que foi a `candidatei` pelo `desfazer_status` de `entrevista` recebe o POST; o status não muda, e a resposta é a faixa. É guarda e nasce verde, porque o valor errado não grava. Mutante: a rota chamar `desfazer_status`.
    - `test_desfazer_sem_js_303`.
  - **Regra do 204:**
    - `test_mesmo_estado_responde_204`: `mostrando=p{id}-1` com a mesma pendente no topo dá 204. Controle: sem `mostrando`, 200 com a faixa.
    - `test_confirmacao_fica_com_mesmo_total_204`: `c{id}-0` com zero pendentes dá 204.
    - `test_pendente_nova_troca_a_faixa`: `p{id}-1` com uma segunda abertura (total 2) dá 200 com a nova no topo.
  - **Erro e casca:**
    - `test_erro_nao_quebra_a_pagina`: com o banco quebrado e `raise_server_exceptions=False`, a rota responde 500 com os cabeçalhos de segurança; `/vagas` continua 200 («Painel»).
    - `test_casca_tem_o_aviso_candidatura`: `/vagas` traz `#aviso-candidatura` com `role="status"` e os quatro atributos `hx-*` acima, sem `candidatura-mudou` no `hx-trigger`, depois do `#aviso-contas` e antes do `#faixa-desfazer`.
  - **Cartão da lista** (em `tests/integracao/test_rota_vagas.py`, E20):
    - `test_cartao_escuta_a_vaga`: em `/vagas?busca={id}`, o `<article id="vaga-{id}">` tem `hx-get` para `/vagas/{id}/cartao` com `busca` e `voltar`, `hx-trigger="vaga-mudou-{id} from:body"` e `hx-swap="innerHTML"`.
    - `test_cartao_get_devolve_corpo_sem_foco`: com `HX-Request`, `GET /vagas/{id}/cartao` devolve o corpo do cartão com o status atual e sem `data-foco`. Controle: o `POST /vagas/{id}/status` com `HX-Request` continua com `data-foco`.
- [ ] **Teste que falha** em `tests/unidade/test_i18n.py`: `test_aviso_candidatura_tem_texto`, com as seis chaves em pt e en, `{titulo}` e `{empresa}` em `pergunta`, `{quando}` em `quando`, `{n}` em `mais` e `{titulo}` em `marcada`.
- [ ] **Testes de tela** (CI) em `tests/tela/test_tela_pergunta_candidatura.py`:
  - `test_tela_volta_a_janela_mostra_a_faixa`: depois do clique da T284, o foco volta à página do painel (`page.bring_to_front()`), e a faixa aparece com a resposta real do `GET` (`page.expect_response`).
  - `test_tela_sim_e_desfazer`: "Sim, me candidatei" muda o status, e "Desfazer" volta.
  - `test_tela_cartao_atualiza_depois_da_faixa` (E20): em `/vagas`, com a vaga Salva pendente na lista, "Sim" na faixa e a espera pelo `GET /vagas/{id}/cartao` (`page.expect_response`); a `.situacao` do cartão diz Candidatei, e o foco continua na faixa. Depois, "Desfazer" volta o cartão a Salva.
  - `test_tela_desfazer_fica_com_a_rede_parada`: depois do Sim, com `page.route` abortando o `GET /aviso-candidatura`, um novo foco da janela não tira o Desfazer, que continua visível e focável.
  - `test_tela_pelo_teclado`: os botões da faixa pelo teclado.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_aviso_candidatura.py tests/integracao/test_rota_vagas.py tests/unidade/test_i18n.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos, `tests/integracao/test_rota_candidatura.py`, `tests/unidade/test_estaticos.py`, `tests/unidade/test_contraste.py` e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI do `lote/panorama-tela`.

### T286: linha do tempo e candidatura por e-mail no detalhe
`depende_de: T280, T282, T284, T285` · desenho 5.4 (Linha do tempo), 5.6 (A vaga na tela), 5.7 (Botões), P2 (a), E20

**Arquivos:**
- modificar `src/jobot/painel/rotas/detalhe.py`, o trecho de template do detalhe (T255 e T264), o CSS do detalhe que a T264 deixou, `src/jobot/painel/static/js/app.js`, `src/jobot/painel/i18n/{pt,en}/detalhe.json`, `tests/integracao/test_rota_detalhe.py`, `tests/unidade/test_i18n.py` e `tests/tela/test_tela_pergunta_candidatura.py` (da T285);
- criar `tests/tela/test_tela_copiar_email.py`.

**Interfaces:**
- `detalhe.py` acrescenta ao contexto:
  - **`passos`**: uma lista de `(chave_i18n, data)` na ordem de exibição:
    - `vista`, pela `primeira_vista_em`;
    - `abriu`, por `abertura_da_candidatura`, quando há registro;
    - um item por passo de `datas_dos_passos`.
  - **`email`**: `email_de_candidatura(vaga.descricao_texto)`.
  - **`principal`**: `"http"` com link http próprio de candidatura; `"email"` sem link próprio e com `email`; `"fonte"` nos outros casos.

  O cálculo de hoje do link (`url_candidatura` http, senão a vaga na fonte) continua. No caso `"email"`, a vaga na fonte continua na lista de fontes do detalhe.
- **Linha do tempo.** Seção `detalhe.passos.titulo`, logo abaixo dos botões de status, numa lista ordenada com `data_curta`, que dá o dia local (E16), uma chave `detalhe.passos.*` por item.
- **A vaga na tela** (E20, desenho 5.6). O grupo `.acoes` e a Linha do tempo ficam dentro de:

  ```html
  <div id="estado-da-vaga" hx-get="{{ retorno }}" hx-trigger="vaga-mudou-{{ vaga.id }} from:body" hx-select="#estado-da-vaga" hx-swap="outerHTML">
  ```

  Depois de "Sim" ou "Desfazer" na faixa (T285), o bloco pede de novo o próprio `GET /vagas/{id}` e fica só com ele mesmo. Sem rota nova e sem `data-foco`: o foco fica na faixa. Os forms de status do detalhe continuam POST com 303, sem `hx-*`; filho que ganhar `hx-*` precisa de `hx-select="unset"`, porque o `hx-select` é herdado.
- **Botão de e-mail.** É `<a href="mailto:{{ email }}?subject={{ vaga.titulo|urlencode }}" data-candidatura="/vagas/{{ vaga.id }}/candidatura" aria-label="{{ t('detalhe.candidatar_email_rotulo') }}">`, sem `target` nem corpo:
  - principal quando `principal == "email"`;
  - secundário, ao lado do principal, quando `principal == "http"` e há `email`.

  Embaixo vêm:
  - `detalhe.email.endereco`, com o texto selecionável;
  - `<button type="button" hidden data-copiar="{{ email }}" data-copiado="..." data-nao-copiou="...">` com `detalhe.email.copiar`, e uma região `role="status"` ao lado;
  - a linha `detalhe.email.aviso`.
- **`app.js`.** Tira o `hidden` dos `button[data-copiar]` no carregamento e depois de cada troca do HTMX (`htmx:afterSettle`). Por delegação no `document`, chama `navigator.clipboard.writeText(data-copiar)` e escreve `data-copiado` ou `data-nao-copiou` na região por `textContent`.
- **Notas do desenho 5.7.** O `href` é montado só com o endereço validado e o título codificado. Nenhum outro texto da descrição vira link, e nenhum outro esquema é aceito.
- **i18n (pt e en).** As chaves `detalhe.passos.*`, `detalhe.candidatar_email`, `detalhe.candidatar_email_rotulo` e `detalhe.email.*` do desenho 5.8.

- [ ] **Primeiro, valor errado:** o contexto traz `passos = []`, `email = None` e `principal = "http"` sempre, e o `#estado-da-vaga` vem sem os atributos `hx-*`.
- [ ] **Testes que falham** em `tests/integracao/test_rota_detalhe.py`:
  - `test_linha_do_tempo`: vista, abriu, salva e candidatei, nessa ordem, com as datas curtas. Com o `TZ` em `<-03>3`, o Sim gravado às 01:30 UTC de 17/11 aparece como 16/11 (E16).
  - `test_email_vira_secundario_com_link_http`: o principal é o link http, e há o `mailto:` secundário.
  - `test_email_vira_principal_sem_link_http`.
  - `test_mailto_com_assunto_codificado`: um título com espaço, `&` e acento sai codificado no `subject`.
  - `test_mailto_sem_parametro_injetado`: descrições com `rh@example.com?cc=outro@example.org`, `rh@example.com&bcc=outro@example.org` e `%0A` não geram nenhum `mailto:`. Controle positivo na mesma montagem: com um endereço válido e gatilho, o `href` tem só `subject` como parâmetro (`urllib.parse`).
  - `test_sem_email_fica_como_hoje`: é guarda e nasce verde. Mutante: mostrar o bloco de e-mail com `email` vazio.
  - `test_copiar_vem_hidden`.
  - `test_email_tem_data_candidatura`.
  - `test_detalhe_estado_escuta_a_vaga` (E20): o `#estado-da-vaga` tem `hx-get` igual ao `retorno` da página, `hx-trigger="vaga-mudou-{id} from:body"`, `hx-select="#estado-da-vaga"` e `hx-swap="outerHTML"`, e contém a `.situacao`, os forms de status e a Linha do tempo. Controle: o `id` aparece uma vez só na página.
- [ ] **Teste que falha** em `tests/unidade/test_i18n.py`: `test_detalhe_passos_e_email_tem_texto`, com as chaves em pt e en e `{data}` e `{email}` onde o desenho põe.
- [ ] **Testes de tela** (CI) em `tests/tela/test_tela_copiar_email.py`:
  - `test_copiar_aparece_com_js_e_copia`: com a permissão de área de transferência concedida ao contexto, o botão aparece e a região diz "Endereço copiado.".
  - `test_copiar_que_falha_avisa`: sem a permissão, a região diz "Não deu para copiar. Selecione o endereço e copie.".
- [ ] **Teste de tela** (CI) em `tests/tela/test_tela_pergunta_candidatura.py`: `test_tela_detalhe_atualiza_depois_da_faixa` (E20). No detalhe de uma vaga Salva com a pergunta pendente, "Sim, me candidatei" na faixa e a espera pelo `GET /vagas/{id}` (`page.expect_response`). A `.situacao` diz Candidatei, o botão de status com `value="nova"` some e aparece o de `value="entrevista"`; a Linha do tempo tem Candidatei. Depois, "Desfazer" na faixa volta a `.situacao` a Salva, e o botão com `value="nova"` volta.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_detalhe.py tests/unidade/test_i18n.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI do `lote/panorama-tela`.

### T287: "desde" na aba Candidatei
`depende_de: T282, T283, T254` · desenho 5.4 (último item), E16

**Arquivos:**
- modificar o template da linha da lista que a T254 deixou, `src/jobot/painel/i18n/{pt,en}/vagas.json`, `tests/integracao/test_rota_vagas.py` e `tests/unidade/test_i18n.py`.

**Interfaces:**
- Só na aba Candidatei, o selo de status da linha vira `t("vagas.linha.desde", status=<rótulo de vagas.status.*>, data=data_curta(item.status_em))`. Com `status_em` nulo, fica o selo de hoje, só com o status. As outras abas não mudam.

- [x] **Primeiro, valor errado:** o template ainda não usa `status_em`.
- [x] **Testes que falham** em `tests/integracao/test_rota_vagas.py`:
  - `test_candidatei_mostra_desde`: "Candidatei desde 16/11" em pt e "Applied since 11/16" em en. O `status_em` é `2026-11-17T01:30:00+00:00`, com o `TZ` em `<-03>3`: o dia mostrado é o local (E16).
  - `test_status_em_nulo_sem_desde`: uma vaga antiga com `status_em` nulo mostra só o status. Controle: a vaga com `status_em` mostra "desde".
  - `test_outras_abas_sem_desde`: é guarda e nasce verde. Mutante: mostrar "desde" em toda aba.
- [x] **Ver falhar:** `uv run pytest tests/integracao/test_rota_vagas.py tests/unidade/test_i18n.py -q`.
- [x] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI do `lote/panorama-tela`.

### T288: a tela Panorama
`depende_de: T282, T283, T285, T253` · desenho 5.1, 5.2, 5.3, 5.10, E11, E12, E13, E19

**Arquivos:**
- criar `src/jobot/painel/rotas/panorama.py`, `src/jobot/painel/templates/panorama/pagina.html`, `src/jobot/painel/templates/panorama/_para_responder.html`, `src/jobot/painel/static/css/panorama.css`, `src/jobot/painel/i18n/pt/panorama.json`, `src/jobot/painel/i18n/en/panorama.json`, `tests/integracao/test_rota_panorama.py` e `tests/tela/test_tela_panorama.py`;
- modificar `src/jobot/painel/static/css/base.css` (só se faltar token), `tests/unidade/test_contraste.py` e `tests/unidade/test_i18n.py`.

**Interfaces:**
- **`GET /panorama`.**
  - Antes da primeira execução, responde 303 para `/primeira-execucao/1`, pela mesma condição de `raiz`.
  - A hora vem de `relogio_do_painel`, e a busca de `busca_efetiva`, com a busca da URL (`inteiro_da_url`) na frente, como em Vagas (D143.50).
  - Na barra vai o mesmo menu de busca que a T253 deixou em Vagas, pelo mesmo trecho de template, sem cópia.
  - Sem busca ativa, o menu some e a frase `panorama.sem_busca` toma o lugar de `panorama.busca_contada`.
- **Hoje.** `contar_abas(con, busca_id, agora)`. Cinco números, nesta ordem: Novas, Fecham logo, Salvas, Candidatei e Todas. Os rótulos são `vagas.aba.*`, e cada número é um link para `/vagas?aba=<chave>&busca=<id>`. Zero aparece como "0".
- **Candidaturas:**
  - o grupo "status" de `contar_chips(con, Filtros(aba="candidatei"), agora)`, com Candidatei, Entrevista, Oferta e Recusada em texto, zero aparecendo, e o link `panorama.candidaturas.ver`;
  - "Para responder": o `<div id="para-responder" hx-get="/panorama/para-responder" hx-trigger="candidatura-mudou from:body">` com `_para_responder.html`, renderizado pelo servidor já na carga da página (o `hx-get` só o refaz depois do evento), com `voltar=/panorama` nos formulários (E9). Esse trecho chama a macro `pergunta(p, "responder", total)` da T285 para cada pendente (`perguntas_pendentes(con, 50)`) ou mostra `panorama.responder.vazio`;
  - "Salvas que fecham": `salvas_que_fecham(con, agora, 5)`, cada uma com link para `/vagas/{id}` e `panorama.fecham.prazo` com `data_curta`, ou `panorama.fecham.vazio`, e o link `panorama.fecham.ver`.
- **`GET /panorama/para-responder`.** Devolve só `_para_responder.html`.
- **A busca:**
  - `inicio_da_ultima_completa` devolve `datetime | None`: com `None`, `panorama.busca.nunca`; senão, `data_completa(inicio.isoformat(), idioma)`, porque a função recebe texto, e o dia sai local (E16);
  - `proxima_busca`, que já vem no fuso local (T283), arredondada ao minuto, com a hora por `p.strftime("%H:%M")` (E19): no mesmo dia local de `agora`, em `panorama.busca.proxima`, só com `{hora}`, como no desenho 5.8; em outro dia, em `panorama.busca.proxima_dia`, com `{dia}` por `data_curta(p.isoformat(), idioma)` e `{hora}`. A linha some com `None`, com a hora já passada ou com `execucao_atual` rodando; nesse último caso aparece `panorama.busca.rodando`;
  - a linha das fontes, pelos `cartoes(...)` das fontes ligadas (desenho 5.2, D147.30): com alguma em `falhou` ou `parcial`, `panorama.busca.fontes_problema` com o número e "Ver fontes"; senão, `panorama.busca.fontes_ok` só quando `inicio_da_ultima_completa` não é `None` e toda ligada está em `ok` ou `sem_mudanca`; nos outros casos (`no_limite`, `sem_execucao`, sem busca completa), a linha some. O texto de `fontes_ok` é o novo do desenho 5.8 ("…da última vez que rodaram."), porque o estado do cartão vem da última execução de qualquer tipo;
  - `contas_em_queda(con, leitores_do_painel(request))`: com mais de zero, `panorama.busca.contas` com "Ver contas" (`/configuracoes/contas`); com zero, a linha some.
- **O que aparece:**
  - o `Estado` sai de `ler_estado` com os parâmetros `aba=todas` e `busca=<id>`, como em `vagas`, nunca montado à mão;
  - `grupos_dos_chips(con, estado, agora, idioma)` filtrado para os quatro grupos (Encaixe, Modalidade, Área e Fonte), com os rótulos de grupo que Vagas já usa;
  - Encaixe mostra todos os níveis e some sem busca; os outros mostram os 5 maiores e terminam com `panorama.aparece.ver`;
  - cada linha é um link para a URL do chip, com o rótulo, a barra e o número;
  - cada bloco abre com `panorama.aparece.mais_comum`, cujo `{total}` é a contagem da aba Todas.
- **Barra (E11).** O SVG é `<svg class="barra" aria-hidden="true" focusable="false"><rect width="{pct}%" height="100%"/></svg>`, com `pct(n, maior)`.
- **Estado vazio.** Com `tem_vaga(con)` falso, a página mostra `panorama.vazio` e só o grupo A busca. A frase cita o botão pelo texto da chave `execucao.buscar_agora` («Texto de tela trocado»).
- **Grupos.** Cada grupo é um `<section aria-labelledby>` com um `<h2>`, na ordem fixa.
- **`panorama.css` (E12).** Usa só os tokens de `base.css` e propriedades lógicas:
  - `.barra rect { fill: var(--destaque) }` sobre o fundo `--trilho-progresso`;
  - `@media (forced-colors: active)`: o preenchimento vira `CanvasText`;
  - sem animação.
- **i18n.** `panorama.json` (pt e en) com as chaves `panorama.*` do desenho 5.8, mais `panorama.busca.proxima_dia` (E19): "Próxima busca automática em {dia}, por volta das {hora}." / "Next automatic search on {dia}, around {hora}."
- **Medição (E13).** Antes de fechar a tarefa, o tempo do `GET /panorama` com o banco de `scripts/medir_filtros.py` vai no resumo.

- [ ] **Primeiro, valor errado:** a rota renderiza a página com os quatro grupos, mas com o contexto todo zerado e as listas vazias. `pct` devolve 100 sempre.
- [ ] **Testes que falham** em `tests/integracao/test_rota_panorama.py`:
  - **Hoje:**
    - `test_quatro_grupos_em_ordem`: os `<h2>` Hoje, Candidaturas, A busca e O que aparece, nessa ordem, cada um com o seu `aria-labelledby`.
    - `test_numeros_hoje_batem_com_contar_abas`.
    - `test_numero_e_link_para_a_aba_com_busca`.
  - **Candidaturas:**
    - `test_candidaturas_por_passo`, com zero aparecendo.
    - `test_para_responder_lista_pendentes`.
    - `test_para_responder_fragmento`: só a lista, sem a casca.
    - `test_fecham_ate_5`.
  - **A busca:**
    - `test_ultima_e_proxima_busca`: com o `TZ` em `<-03>3`, uma busca completa às 01:00 UTC de 17/11 e `agora` às 01:30 UTC de 17/11 (22:30 local de 16/11), a última aparece como 16/11/2026 e a próxima (04:00 UTC, 01:00 local de 17/11) cai no dia seguinte, com `panorama.busca.proxima_dia`, o dia 17/11 e a hora 01:00 (E16, E19).
    - `test_proxima_no_mesmo_dia_so_hora` (E19): com o `TZ` em `<-03>3`, a busca às 12:00 UTC e `agora` às 12:30 UTC, a próxima (15:00 UTC, 12:00 local) é do mesmo dia local e sai em `panorama.busca.proxima` só com a hora, sem o dia. O vermelho vem do valor errado (contexto zerado, a linha falta).
    - `test_proxima_some_quando_passou`.
    - `test_proxima_igual_a_de_fontes`: montagem com uma fonte ligada, sem `intervalo_min` e fora de `no_limite`; o Panorama e `/fontes` mostram a mesma hora da próxima busca. Nos outros casos o cartão de Fontes pode mostrar uma hora mais tarde, por desenho: ele toma o `max` da agenda com `ultimo + intervalo_min` e, em `no_limite`, com o `livre` (`rotas/fontes.py`, `_cartoes`), e o Panorama mostra só a agenda da busca.
    - `test_fontes_com_problema_conta_falhou_e_parcial`.
  - **Barras e O que aparece:**
    - `test_pct_das_barras` (E11): `pct(0, 10) == 0`, `pct(1, 1000) == 2`, `pct(5, 10) == 50`, `pct(10, 10) == 100` e `pct(3, 0) == 0`.
    - `test_barras_sem_atributo_style`: nenhum `style=` no HTML.
    - `test_barra_aria_hidden_e_numero_no_texto`.
    - `test_frase_mais_comum`.
  - **Busca escolhida e ids:**
    - `test_busca_escolhida_vale`: com a busca 2 gravada como escolhida, os links levam `busca=2`.
    - `test_ids_unicos_com_faixa_e_para_responder`: com uma pendente, o HTML de `/panorama` mais o do `GET /aviso-candidatura` não repetem nenhum `id`.
  - **Um teste por linha da tabela 5.10:**
    - `test_antes_da_primeira_execucao_redireciona`;
    - `test_banco_vazio_mostra_estado_vazio`;
    - `test_so_vagas_fechadas_com_candidatura_nao_e_vazio`;
    - `test_sem_busca_ativa_esconde_encaixe`;
    - `test_sem_busca_completa`;
    - `test_sem_busca_completa_sem_frase_de_fontes_ok`: com todas as ligadas em `ok` e nenhuma busca completa, nem `fontes_ok` nem `fontes_problema`. Controle na mesma montagem: com uma busca completa gravada, a frase aparece;
    - `test_fonte_no_limite_ou_sem_execucao_sem_frase` (parametrizado em `no_limite` e `sem_execucao`, com busca completa): a linha das fontes some, sem `fontes_ok` e sem `fontes_problema`. Controle: a mesma fonte em `ok` mostra a frase;
    - `test_buscando_agora`;
    - `test_proxima_com_relogio_que_voltou`;
    - `test_fontes_todas_ok` (com busca completa e todas as ligadas em `ok` ou `sem_mudanca`);
    - `test_sem_contas_em_queda_sem_linha`;
    - `test_contas_em_queda`;
    - `test_para_responder_vazio`.

    O de erro da faixa já está na T285. Cada teste de "some" traz o controle positivo na mesma montagem.
- [ ] **Testes que falham** em `tests/unidade/test_contraste.py` e em `tests/unidade/test_i18n.py`:
  - o par `--destaque` sobre `--trilho-progresso`, a 3:1 no teste gráfico, nos dois temas;
  - `test_panorama_tem_texto`, com as chaves em pt e en e os mesmos parâmetros.
- [ ] **Testes de tela** (CI) em `tests/tela/test_tela_panorama.py`:
  - `test_teclado_pelos_numeros_e_barras`: o Tab passa pelos links dos números e das barras, com o foco visível.
  - `test_para_responder_atualiza_com_o_evento`: Sim num botão de "Para responder" mostra a confirmação na faixa, e a lista perde a pergunta sem recarregar.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_rota_panorama.py tests/unidade/test_contraste.py tests/unidade/test_i18n.py -q`.
- [ ] **Implementar** os itens de Interfaces e a medição.
- [ ] **Ver passar:** os mesmos arquivos, `tests/unidade/test_rotas_sem_copias.py`, `tests/unidade/test_estaticos.py` e `tests/unidade/test_camadas.py`; ruff; `-m tela` e mypy no CI do `lote/panorama-tela`.

### T289: Panorama na lateral e na paleta
`depende_de: T288, T265` · desenho 5.1, E12

**Arquivos:**
- modificar `src/jobot/painel/templates/base.html` (a lateral), `src/jobot/painel/lateral.py` (só se a área ativa vier de lá), o registro de comandos da paleta da T265, o registro de ícones da T249 (`layout-dashboard`), `src/jobot/painel/i18n/{pt,en}/casca.json`, `tests/integracao/test_casca_menu.py`, `tests/unidade/test_estaticos.py`, `tests/unidade/test_i18n.py` e `tests/tela/test_casca_menu.py`.

**Interfaces:**
- **Lateral.** "Panorama" é o primeiro item, numa seção sem título acima de "Vagas". O link vai para `/panorama`, com o ícone `layout-dashboard` (ou o da E12) e `aria-current="page"` em `/panorama`. Sem contagem.
- **Paleta.** Ganha o comando "Panorama", como todo item da lateral (T265).
- **`/`.** Continua em Vagas (P3 (a)).
- **i18n.** `casca.lateral.panorama`: "Panorama" em pt, "Overview" em en.

- [ ] **Primeiro, valor errado:** a chave i18n existe, mas a lateral ainda não tem o item.
- [ ] **Testes que falham** em `tests/integracao/test_casca_menu.py`:
  - `test_lateral_tem_panorama_com_aria_current`: em `/panorama`, o item é o primeiro da lateral e tem `aria-current="page"`; em `/vagas`, não tem.
  - `test_paleta_tem_os_comandos`, atualizado com "Panorama".
  - `test_menu_tem_os_itens_da_lateral_pt_e_en`, com o item novo.
  - `test_raiz_continua_em_vagas`: é guarda e nasce verde. Mutante: `raiz` levar a `/panorama`.
- [ ] **Teste que falha** em `tests/unidade/test_estaticos.py`: os dois ícones novos no `lucide.meta.json` e os arquivos no lugar.
- [ ] **Testes de tela** (CI) em `tests/tela/test_casca_menu.py`: o item pelo teclado e a paleta abrindo o Panorama.
- [ ] **Ver falhar:** `uv run pytest tests/integracao/test_casca_menu.py tests/unidade/test_estaticos.py tests/unidade/test_i18n.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** os mesmos arquivos e `tests/unidade/test_camadas.py`; ruff; a suíte inteira, `-m tela` e mypy no CI do `lote/panorama-tela`.

### T290: documentos de quem usa
`depende_de: T284, T285, T286, T287, T288, T289` · desenho 5.9

**Arquivos:**
- modificar `README.md`, `README.en.md`, `wiki/Como-funciona.md`, `wiki/How-it-works.md`, `CHANGELOG.md` e `CHANGELOG.en.md`;
- modificar `docs/decisions/0001-escopo-do-jobot.md`, `docs/decisions/0008-painel-e-visual.md`, `docs/decisions/0014-seguranca-e-privacidade.md` e `docs/superpowers/specs/2026-11-13-fase-1-design.md` (regra 14.3);
- modificar `tests/unidade/test_documentos.py`.

**Interfaces:**
- **README (pt e en):**
  - na descrição do painel, uma linha sobre o Panorama e a fila: a pergunta "Você se candidatou?", as datas de cada passo e o botão de e-mail que só abre o programa da pessoa;
  - na seção de privacidade, uma linha dizendo que o joBot guarda, só no computador da pessoa, quando ela abriu a candidatura de cada vaga.
- **Wiki** `Como-funciona` e `How-it-works`: as mesmas duas linhas.
- **CHANGELOG** (Não lançado / Unreleased, "Adicionado" / "Added"): quatro linhas, uma para cada item:
  - o Panorama;
  - a linha do tempo e o "desde";
  - a pergunta "Você se candidatou?" com Desfazer;
  - a candidatura por e-mail ("o joBot não envia nada").
- **ADRs:**
  - 0008: uma nota com o item Panorama na lateral;
  - 0001: uma nota de que o registro da abertura é local e de que o botão de e-mail só abre o programa da pessoa;
  - 0014 e regra 14.3 da fase 1: uma nota com a exceção do botão de e-mail (desenho 5.7). Só `mailto:`, só um endereço que passou pela lista fechada, montado pelo joBot, com o título como único parâmetro. Link da descrição continua não clicável.
- **Sem mudança.** O Roteiro não muda (já promete os dois). Nenhuma rede nova, então os textos de telemetria e privacidade de rede não mudam («Painel e ADRs»).

- [ ] **Primeiro, valor errado:** nenhum; o teste nasce vermelho porque o texto ainda não existe.
- [ ] **Testes que falham** em `tests/unidade/test_documentos.py`:
  - `test_changelog_cita_o_panorama`: pt e en, na seção "Não lançado" / "Unreleased", citam "Panorama"/"Overview" e "Você se candidatou?"/"Did you apply". Antes do `.index()`, o teste confere `assert marcador in conteudo` («Troca de versão»).
  - `test_privacidade_cita_a_abertura`: os dois README citam o registro local da abertura na seção de privacidade.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_documentos.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** `tests/unidade/test_documentos.py` e `tests/unidade/test_wiki.py`; ruff.

### T291: versão 0.3.0
`depende_de: T290, T279, T268`, o resto do lote do primeiro site, que `2026-11-15-fase-2-login-linkedin.md` ("Fora deste plano") põe como condição da 0.3.0: T240, T241 e os itens 1, 2 (`CLAUDE.md` do projeto), 4 (ADR 0006), 6 (ADR 0022) e 7 (ADR 0017) de "Espera o dono" de `2026-11-15-fase-2-primeiro-site-resto.md`, cada item com o ok do dono; e a fase 2 concluída na `dev` (E14) · ADR 0017, «Troca de versão»

**Arquivos:**
- modificar `pyproject.toml`, `uv.lock`, `CHANGELOG.md`, `CHANGELOG.en.md`, `tests/unidade/test_documentos.py`, `.github/SECURITY.md`, `.github/SECURITY.en.md`, `.github/CONTRIBUTING.md`, `.github/CONTRIBUTING.en.md`, `README.md`, `README.en.md`, `wiki/A-ideia-e-a-historia.md`, `wiki/Home.md`, `wiki/Home-en.md`, `wiki/Roteiro.md`, `wiki/Roadmap.md` e `docs/decisions/0017-fases.md`;
- e toda outra linha que o `grep` abaixo achar.

**Interfaces:**
- `version = "0.3.0"` no `pyproject.toml`; depois, `uv lock` e `uv sync --locked`.
- **CHANGELOG (pt e en).**
  - O conteúdo de "Não lançado" / "Unreleased" vai para `## [0.3.0] - <dia da troca>`, com uma linha de resumo que cobre tudo o que está nele, não só este lote: a fase 2 (navegador com login e o LinkedIn), o visual novo do painel, a aba Contas, o Panorama e a fila de candidaturas. Antes de escrever, quem constrói lê a seção "Não lançado" inteira e confere se algum lote ficou fora do resumo.
  - A seção "Não lançado" volta vazia no topo.
  - A frase do roteiro passa ao passado: "a versão 0.3.0 saiu".
- **Documentos de estado vivo** («Troca de versão»: mudam juntos):
  - ADR 0017: o texto do item 7 de "Espera o dono" de `2026-11-15-fase-2-primeiro-site-resto.md` (Status da fase 2 e linha "Atualizada") e a frase de histórico do Contexto com a 0.3.0 e a fase 2 concluída, no texto proposto na E14, sem apagar as versões antigas. As duas mudanças mexem em ADR aceita e só entram com o ok do dono (D148.14); sem o ok, a T291 para e a pergunta vai ao `duvidas.md`. Depois disso, o `grep` abaixo não acha mais a 0.2.1 no Contexto como versão mais nova;
  - Roteiro e Roadmap: a fase 2 com ✅ e a frase da 0.3.0 no passado;
  - README pt e en: a linha do topo e a da instalação passam a citar a 0.3.0, e a frase da 0.3.0 vai ao passado;
  - SECURITY e CONTRIBUTING (pt e en): "hoje a 0.3.0";
  - as páginas de história e início da wiki.

  A frase de histórico ganha a 0.3.0 sem apagar as versões antigas.
- **`test_documentos.py`:**
  - o literal da versão vira `"0.3.0"`;
  - `test_changelog_fecha_a_0_3_0`: a primeira seção numerada do CHANGELOG, pt e en, é a 0.3.0, e a linha de resumo dela (o texto entre o título `## [0.3.0]` e o primeiro `###`) cita "Panorama"/"Overview" e "LinkedIn". O teste olha só o resumo, porque os itens movidos de "Não lançado" já trazem "LinkedIn" e deixariam passar um resumo só deste lote (o mutante);
  - entra no lugar do teste de primeira seção da 0.2.1, e o teste dos itens da 0.2.1 continua valendo para a seção dela.
- **Antes de fechar.** `rtk grep -rn "0\.2\.1" .`, fora de `tests/`, `.venv`, `duvidas.md`, `registros/`, planos e desenhos, e fora das seções de histórico do CHANGELOG. Só pode sobrar histórico.

- [ ] **Primeiro, valor errado:** nenhum; o literal novo no teste nasce vermelho contra `__version__ == "0.2.1"`.
- [ ] **Testes que falham** em `tests/unidade/test_documentos.py`: o literal `"0.3.0"` e `test_changelog_fecha_a_0_3_0`.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_documentos.py -q`.
- [ ] **Implementar** os itens de Interfaces.
- [ ] **Ver passar:** `tests/unidade/test_documentos.py`, `tests/unidade/test_wiki.py` e `tests/unidade/test_versao.py`; o `grep` acima sem sobra; ruff.
- [ ] **Publicar (sessão principal, que roda o git na `fedora-dev`):**
  - commit `chore(versao): sobe a versão para 0.3.0`, na `dev`, depois do CI verde do lote dela;
  - PR da `dev` para a `main` com título e corpo da skill `pr-curto`;
  - o CI do PR verde, merge com merge commit;
  - a `origin/main` volta para a `dev`;
  - release `v0.3.0` com as notas do CHANGELOG, como na `v0.2.0`;
  - a wiki sai pelo CI da `main`.

  Nunca contornar a proteção de branch (ADR 0016).

## Espera o dono

1. **Nada de acesso.** Para construir e testar este lote, o joBot não precisa de conta, senha, chave nem acesso do dono:
   - os testes rodam com a rede bloqueada;
   - o link de candidatura dos testes de tela aponta para um servidor local;
   - o CI roda no Actions do repositório público;
   - o PR da `dev` para a `main` já foi autorizado em 2026-11-15.
2. **As escolhas E1 a E21** (D148), em especial:
   - E1: o lado de trás antes do portão;
   - E4: as consultas de Fontes e de Contas mudam de lugar;
   - E10: o botão do meio do mouse não registra a abertura;
   - E13: a medição à mão;
   - E14: a 0.3.0 espera a fase 2 concluída, como a ADR 0017 diz, com o resto do lote do primeiro site (T240, T241 e os itens 1, 2, 4, 6 e 7 de "Espera o dono" daquele plano); na ADR 0017 usa o texto do item 7 e atualiza a frase de histórico do Contexto, no texto proposto na E14;
   - E16: as datas do painel passam a sair no dia local, o que também acerta o dia em Sites, Sugeridas e Programas;
   - E17: a vaga ocultada à mão não entra em "Para responder"; a que a pessoa mandou mostrar entra;
   - E19: a próxima busca em outro dia ganha uma chave nova de texto, com o dia;
   - E20: depois de responder na faixa, o detalhe e o cartão da vaga se atualizam sozinhos, por um evento por vaga e uma rota nova pequena para o cartão;
   - E21: o `voltar` da faixa sai do endereço da página, pela mesma regra do `de_volta`.
3. **As perguntas P1 a P5 do desenho** e os itens da D147, todos "para confirmar". O plano segue a recomendação de cada um. Os de mais peso:
   - P1: a tabela `candidatura`, R4 de esquema;
   - P2: o `mailto:` da fonte fica fora;
   - D147.22 e D147.24: a exceção à regra 14.3 para o botão de e-mail;
   - D147.29 a D147.31: a vaga na tela se atualiza depois da faixa, a frase das fontes só com busca completa e tudo em `ok`, e o `voltar` da faixa.
4. **O portão T258 do visual.** As telas deste lote (T283 a T289) só começam depois que a branch longa entra na `dev` com o ok do dono, e depois do `lote/contas-tela`. É o mesmo ok que já libera as telas de Contas.
5. **Conferência à mão, opcional, com o `lote/panorama-tela` na `dev`.** No próprio computador, o dono:
   - abre uma vaga, clica em "Candidatar-se", volta ao painel e responde a pergunta;
   - olha o Panorama com os dados reais dele.

   Nada disso sai do computador dele.

## Tarefa e dificuldade

| Tarefa | Dificuldade | Por quê |
|---|---|---|
| T280 | média | função pura, mas com borda de segurança: lista fechada, separadores e testes de injeção |
| T281 | média | migração com gatilho e as lições de esquema e de teste de migração; três gravações com regras de status |
| T282 | média | regra dos passos com Oferta e Recusada no mesmo degrau, dia local no prazo e o campo novo em `Item` |
| T283 | média | mudança de lugar sem cópia, com os testes que importam os nomes velhos, e o dia local nas datas, que muda telas que já existem |
| T284 | baixa | rota de 204 e um ouvinte no `app.js` |
| T285 | alta | a regra do 204 por chave, o HTMX que dispara antes da troca, o foco e o leitor de tela, o sem-JS e a tela com a rede parada |
| T286 | média | dois botões com prioridade, `mailto:` sem injeção e a área de transferência no teste de tela |
| T287 | baixa | um selo com data |
| T288 | alta | muitas consultas, onze estados com teste, as barras em SVG com contraste e a medição |
| T289 | baixa | um item na lateral e na paleta |
| T290 | baixa | texto, com os testes de documento |
| T291 | média | troca de versão em muitos documentos e a publicação na `main` |

## Fora deste plano

- O `mailto:` que a própria fonte manda no campo de candidatura (P2): continua descartado; um campo `email_candidatura` em `VagaColetada` pode vir numa `Tn` depois.
- Registrar a abertura pelo botão do meio do mouse ou pelo menu do navegador (E10).
- Editar as datas da linha do tempo (D147.14).
- O Panorama como tela inicial (P3).
- Cache das consultas do Panorama: só se a medição da T288 passar de 300 ms, numa `Tn` própria (E13).
- Uma regra geral de AST para todo `painel/` não importar `jobot.painel.rotas`: hoje o `painel/cliente.py` importa `relogio_do_painel` de `rotas/vagas.py`. Pode virar uma `Tn` depois da T251 do plano do visual, que tira `relogio_do_painel` de `rotas/vagas.py`.
- HTMX no formulário de status do detalhe (desenho 5.4): a troca continua um POST com 303. Só o bloco `#estado-da-vaga` se pede de novo quando a resposta vem da faixa (E20).
- Candidatura automática (D138, item 1): recusada.
