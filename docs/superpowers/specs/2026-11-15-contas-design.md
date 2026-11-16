# Contas, o estado do login de cada site: desenho

Data: 2026-11-15. Decisões de origem: ADR 0005 (sites com login), ADR 0013 (avisos), ADR 0024 (Gmail por senha de app), ADR 0022 (CAPTCHA pelo serviço da pessoa), ADR 0023 (tudo pelo painel), o desenho da fase 2 (`docs/superpowers/specs/2026-11-15-fase-2-design.md`, D132), o login pela janela comum (D136) e as respostas do dono de 2026-11-15. As decisões novas ficam em `duvidas.md` como D139.

Este documento é a especificação para planejar e construir o lote "Contas" sem voltar ao dono. Todo fato sobre o código vem com `arquivo:linha`, conferido na árvore da `dev` em 2026-11-15. As linhas podem andar: quando a linha não bater, procure pelo nome. As lições de `registros/padroes.md` são citadas pelo rótulo, como `padroes.md («Esquema»)`.

Cada decisão leva o número da lista completa da seção 11 (D139.1 a D139.37). As decisões 1 a 11, 34 e 35 são do dono; as outras são da sessão, para confirmar com o dono, menos a 13 e o 401/403 da 18, que o dono confirmou em 2026-11-15.

## 1. Intenção e porquê

Hoje o painel só mostra a saúde da última leitura de cada site com login: "Última leitura: falhou" com o motivo `saude.precisa_login` (`src/jobot/painel/templates/configuracoes/_cartao_site_login.html`). A pessoa não sabe, antes da leitura das 9h ou das 18h, se a sessão ainda vale. Também não sabe se nunca entrou ou se a sessão caiu. O resultado do "Fazer login agora" vive só em `app.state` e some quando o joBot reinicia (`src/jobot/painel/rotas/configuracoes.py:453`).

O dono pediu (D139.4 a D139.8) que cada site mostre o estado da conta, com a hora da última conferência guardada no banco. Quando a sessão cai, o joBot avisa no painel inteiro e no computador, uma vez. Um botão "Conferir agora" confere sem ler vagas. Uma aba única, "Contas", em Configurações, troca a "Sites com login".

Por que agora: a ADR 0005 já promete que, "sem o login manual feito, o site fica parado e o painel avisa" (`docs/decisions/0005-sites-com-login.md:48`). Hoje esse aviso é só o motivo da saúde. O dono quer um lote pequeno ainda na fase 2, antes do Panorama da 0.3.0, só com o LinkedIn (D139.9).

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos

1. Cada site com login mostra um de cinco estados: Conectado, Precisa entrar de novo, Nunca entrou, Não deu para conferir e Desligado. Ao lado vem a hora da última conferência ("conferido hoje às 09:02").
2. O estado fica no banco e sobrevive ao reinício.
3. Três coisas atualizam o estado: a entrada de cada leitura agendada, o fim do "Fazer login agora" e o botão "Conferir agora".
4. Uma queda de sessão (o site já teve login e passou a "Precisa entrar de novo") mostra uma faixa no topo de toda tela do painel, com o botão "Entrar de novo", e manda um aviso no computador (`notify-send`) uma vez por queda. A faixa fica enquanto a queda estiver aberta (seção 5.1).
5. Uma aba "Contas" em Configurações junta os cartões dos sites e a linha do 2Captcha. A rota antiga leva para a nova.

Não objetivos

- Leitura dos e-mails do Gmail: fica na fase 6. O cartão do Gmail na aba Contas, sem a leitura, entra neste lote, com senha de app e IMAP (R2 do dono, ADR 0024, D145).
- Claude Code e Codex na aba Contas: chegam na fase 4, com o estado vindo da própria ferramenta (ADR 0010 e D125).
- Outros sites com login além do LinkedIn: cada um entra pela Parte B da fase 2 (D132). O desenho serve para qualquer leitor de `LEITORES` sem mudança.
- Visitas para manter a sessão viva (D139.7). O perfil persistente guarda a sessão; se ela cai, o aviso da D139.5 dispara.
- Sair de um site só. "Esquecer logins" continua apagando o perfil inteiro (`src/jobot/navegador/perfil.py:101`).
- A parte de IA do instalador: fica no protótipo do Canvas agora e no instalador real na fase 4 (D139.10).

Anti-objetivos

- O joBot nunca digita senha (ADR 0005, `docs/decisions/0005-sites-com-login.md:22`).
- O joBot nunca contorna CAPTCHA nem bloqueio (ADR 0005). O "Conferir agora" não chama o 2Captcha: um desafio vira "Não deu para conferir".
- O painel não carrega recurso externo e só escuta em `127.0.0.1` (ADR 0023, `docs/decisions/0023-tudo-pelo-painel.md:36`).
- Nada vai para fora do computador: o aviso é só o `notify-send` local, o mesmo "aviso no computador" do CAPTCHA (ADR 0005, `docs/decisions/0005-sites-com-login.md:28`). A ADR 0013 (`docs/decisions/0013-gmail-e-avisos.md:20`) proíbe notificação push e ntfy no app, mas não trata do `notify-send`.

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py`): `nucleo` puro; `banco` importa só `nucleo`; `navegador` importa `nucleo`, `banco` e `sistema`, nunca `painel`, `agenda` nem `cli`; só `navegador` importa o Playwright; `painel` não importa `httpx`.
- Gravação no banco com `INSERT ... ON CONFLICT DO UPDATE`, nunca `INSERT OR REPLACE`. Nada é apagado. `evento` só recebe acréscimo.
- Um perfil do Chrome por vez: o Chrome guarda o `SingletonLock` na pasta do perfil (D136). A trava `login` de `app.state.travas` já é dividida pela leitura agendada, pelo "Fazer login agora" e pelo "Esquecer logins" (`src/jobot/cli/servir.py`, função `montar`).
- O relógio entra por injeção: `relogio_do_painel(request)` no painel (`src/jobot/painel/rotas/vagas.py:60`) e `site.relogio` no navegador. Nenhum teste espera tempo real.
- Os testes rodam com a rede bloqueada (`tests/conftest.py`).
- Texto novo do painel entra nos catálogos `pt` e `en`. README, CHANGELOG e wiki são bilíngues.
- Ordem com o visual (D140, decisão 9): o lado de trás (migração 0009, gravação, `conferir_sessao`, rotas, aviso no computador) vai em paralelo ao visual novo. A aba Contas e a faixa do topo (seções 5.5 e 5.7) esperam a base visual nova da D140. Rotas, ids, chaves i18n e textos não mudam com o visual.
- Este lote vem depois da T240 e da T241 (`docs/superpowers/plans/2026-11-15-fase-2-primeiro-site-resto.md:73-218`) e usa os nomes delas (D139.15). Em 2026-11-15 as duas ainda não estão na árvore: `configuracoes.py` ainda tem `_leitores` (`:97`), `_ctx_sites_com_login` (`:199`) e `_trava_de_login` (`:444`). O plano do lote declara `depende_de` T241 (que já depende da T240) e só começa com ela na `dev`.

## 4. Como funciona hoje (fatos conferidos)

Navegador

- `visitar(page, url, leitor, politica, relogio, *, cola=None)` devolve `Captura`, uma `ParadaLogin`, `Recusada` ou `Widget` (`src/jobot/navegador/pagina.py`). A ordem é: política, `goto`, host e política, login, Cloudflare, CAPTCHA, 401/403/bloqueio, 429, assentar, rolar.
- `ParadaLogin = Literal["precisa_login", "bloqueio", "captcha", "no_limite"]`. Página com campo de senha, URL de login ou saída para o host de login dá `precisa_login` (`_fora_ou_login`, `_recusada`). Status 401 ou 403, ou `leitor.pagina_bloqueada(...)`, dá `bloqueio` (`src/jobot/navegador/pagina.py:285`). O 429 sem nova tentativa dá `no_limite`. O Cloudflare que não sai dá `captcha`.
- `_ler_paginas(site)` abre `leitor.url_entrada` e, se a `Captura` não passa em `leitor.pagina_logada`, marca `precisa_login` (`src/jobot/navegador/execucao.py:419-436`). Qualquer parada na entrada vai para `estado_do_escopo` e `site.saude(...)` e encerra o site. É aqui que a leitura agendada sabe o estado da conta.
- Uma exceção na entrada não é pega em `_ler_paginas`: ela sobe até `_ler_site`, que grava `falhou` com `saude.excecao:<nome>` (`src/jobot/navegador/execucao.py:401-410`). Não existe classificador de erro de rede do Playwright; `motivo_do_escopo` só conhece as exceções do `httpx` (`src/jobot/nucleo/coletores/executor.py:163-171`).
- `executar_login` (`src/jobot/navegador/execucao.py:122`) só lê os sites ligados. Sem tela ou sem navegador, grava `falhou` com `saude.sem_tela` ou `saude.sem_navegador` e não abre página.
- `Dependencias` (`src/jobot/navegador/execucao.py:76`) traz `avisar: Callable[[str, str], None]` (`:83`), ligado em produção a `sistema/aviso.py avisar(...)` (`:113`). `_Janela.parar` avisa uma vez por execução com `_FRASES_AVISO` pt/en (`:68`) por `asyncio.to_thread` (`:267-269`).
- `fazer_login` (`src/jobot/navegador/login_manual.py:76-96`) devolve `Resultado = Literal["pronto", "nao_entrou", "tempo_esgotado", "sem_tela", "sem_navegador", "em_uso"]`. `_sessao_aberta(leitor, deps, ambiente)` (`:57-73`) abre o contexto, vai à `url_entrada`, espera o `networkidle` até `limites.ESPERA_ASSENTAR_MS` e chama `pagina_logada`; um `ErroDoPlaywright` vira `False`.
- `perfil_em_uso(perfil)` (`src/jobot/navegador/janela_comum.py:59`) olha o `SingletonLock`.
- `limites.py` já tem `PRAZO_LOGIN_MANUAL_S = 600` (`src/jobot/navegador/limites.py:18`) e `ESPERA_ASSENTAR_MS = 10_000` (`:31`).

Banco

- Migrações `0001` a `0008` em `src/jobot/banco/migracoes/`; a próxima é a `0009`. A `fonte` tem `chave TEXT PRIMARY KEY`, `ligada` (`0001_inicial.sql:4-9`) e `com_login` (`0008`).
- Gatilhos: `vaga_sem_delete` (`0001_inicial.sql:97`), `evento_sem_update` (`:167`), `evento_sem_delete` (`:171`) e os da busca de texto, `vaga_fts_insert` e `vaga_fts_update` (`src/jobot/banco/migrar.py:20-25`). O `evento` só aceita ações de vaga, com `vaga_id NOT NULL`.
- `migrar` desliga `foreign_keys` antes da transação (`src/jobot/banco/migrar.py:71`, `:103`).
- Exemplo de gravação numa instrução só com `ON CONFLICT DO UPDATE`: `src/jobot/banco/captcha.py`.

Painel

- Hoje `GRUPOS` termina em `"sites-com-login"` (`src/jobot/painel/rotas/configuracoes.py:61`, `_COM_LOGIN` em `:70`). A aba só aparece quando há leitor (`:94`). Depois da T240, `GRUPOS` termina em `"ferramentas"`, e `grupos_visiveis` esconde as duas sem leitor (`docs/superpowers/plans/2026-11-15-fase-2-primeiro-site-resto.md:100`).
- Rotas: `POST /configuracoes/sites-com-login/{chave}/interruptor` (`:411`), `POST` e `GET .../{chave}/login` (`:471`, `:499`), `POST .../esquecer` (`:511`) e `POST .../esquecer/confirmar` (`:518`). A rota genérica `GET /configuracoes/{grupo}` (`:400`) mostra cada aba.
- `_trava_de_login` (`:444`) e `_estados_de_login` (`:453`): o resultado do "Fazer login agora" fica só em `app.state.login_manual`. O `GET .../login` devolve 204 enquanto está `aguardando`, e `_login_site.html` repete a pergunta a cada 5 s.
- `base.html:64` carrega o aviso de versão com `hx-get="/aviso-versao" hx-trigger="load"`; a rota (`src/jobot/painel/rotas/aviso_versao.py`) devolve um fragmento vazio quando não há o que mostrar. `#aviso-erro` vem logo depois (`base.html:68`).
- `fontes/pagina.html:73` leva para `/configuracoes/sites-com-login` com a chave `fontes.ligar_em_sites_com_login`.
- A linha do 2Captcha já existe em Configurações › Serviços: `contexto_captcha` (máscara "salva", ligado, teto) e o teste `POST /configuracoes/servicos/captcha/testar`, que devolve o fragmento sempre com 200 (`src/jobot/painel/rotas/servicos.py`, `_cartao_captcha.html`).

O que a T240 e a T241 trazem antes deste lote

- T240: grupo `"ferramentas"` em `GRUPOS`, `_trava(request, nome)` no lugar de `_trava_de_login`, `contexto_ferramenta_navegador`, `_ferramenta_navegador.html` e o link do cartão dos sites para `/configuracoes/ferramentas`.
- T241: `_leitores` vira `leitores_do_painel(request)`, `_ctx_sites_com_login` vira `contexto_sites_com_login(request, con)`, e o miolo dos cartões sai para `_sites_cartoes.html`, usado também pelo passo `/primeira-execucao/sites`.

## 5. O como

### 5.1 Estados e de onde vêm

Estados na tela, nesta ordem de precedência (D139.4, D139.12, D139.19):

| Estado | Quando | Faixa e aviso |
|---|---|---|
| Desligado | `fonte.ligada = 0`. Vem da `fonte`, não é gravado. | Não |
| Nunca entrou | Sem linha em `sessao_site`, ou `estado = 'precisa_entrar'` com `entrou_em` nulo. | Não |
| Conectado | `estado = 'conectado'`. | Não |
| Precisa entrar de novo | `estado = 'precisa_entrar'` com `entrou_em` preenchido. | Sim: faixa e aviso (uma vez por queda) |
| Não deu para conferir | `estado = 'nao_conferiu'`, com o motivo. | Sem aviso novo; a faixa continua se a queda estiver aberta |

"Nunca entrou" e "Precisa entrar de novo" são o mesmo fato (a página pede login) com histórias diferentes: só cai quem já entrou. Por isso a faixa e o aviso valem só para quem já entrou.

Queda aberta (D139.13, D139.34): site ligado, com leitor registrado, com `entrou_em` e `avisado_em` preenchidos. A faixa do topo segue a queda aberta, não o `estado` do momento.

- Abre quando o site passa a "Precisa entrar de novo" já tendo entrado (`entrou_em` preenchido).
- Fecha quando o site volta a "Conectado" (`avisado_em` vira nulo) ou passa pelo "Esquecer logins" (`entrou_em` e `avisado_em` viram nulos). Desligar o site só esconde a faixa; ligar de novo com a queda aberta a traz de volta.
- `nao_conferiu` no meio não abre nem fecha: "Precisa entrar de novo" que vira "Não deu para conferir" (sem rede, em uso, desafio) mantém a faixa, e o cartão mostra o estado real, com o motivo.
- "Nunca entrou" (`entrou_em` nulo) nunca tem queda aberta: nunca mostra faixa nem manda aviso.

Fontes do estado

1. Entrada de cada leitura agendada (`_ler_paginas`, na visita a `url_entrada`). A verificação automática das 9h e das 18h (D139.6) é esta.
2. Fim do "Fazer login agora" (`fazer_login`).
3. "Conferir agora" (seção 5.4).

Leitura agendada, a partir do que `site.ir(leitor.url_entrada)` devolve (D139.18):

| Resultado na entrada | Estado | Motivo |
|---|---|---|
| `Captura` com `pagina_logada` verdadeiro | `conectado`, e `entrou_em` passa a ser agora | nulo |
| `Captura` sem `pagina_logada`, ou `precisa_login` | `precisa_entrar` | nulo |
| `bloqueio` (inclui 401 e 403, `pagina.py:285`) | `nao_conferiu` | `bloqueio` |
| `captcha` ou `Widget` não resolvido | `nao_conferiu` | `desafio` |
| `no_limite` | `nao_conferiu` | `no_limite` |
| `Recusada` | `nao_conferiu` | `bloqueio` |
| `ErroDoPlaywright` vindo de `site.ir(leitor.url_entrada)` que não seja fechamento da janela | `nao_conferiu` | `sem_rede` |
| Qualquer outra `Exception` na entrada | `nao_conferiu` | `erro` |
| `NavegadorFechado` ou `sqlite3.Error` | nada é gravado | — |
| Sem tela ou sem navegador (`executar_login`, antes de abrir página) | `nao_conferiu` | `sem_tela` ou `sem_navegador` |

(decisão da sessão) O erro do Playwright não é classificado pela mensagem: nada de ler `net::ERR_*`. Todo `ErroDoPlaywright` da entrada que não seja o fechamento da janela (o mesmo teste `_fechou` de `_ler_site`, `src/jobot/navegador/execucao.py:402`) grava `sem_rede`. Qualquer outra exceção grava `erro` e vai para o log com `exc_info` (seção 5.8). `NavegadorFechado` e `sqlite3.Error` seguem o caminho de hoje e não gravam estado. A saúde da leitura continua como hoje (`saude.excecao:<nome>`): a gravação do estado é a mais, não troca a saúde.

Na leitura agendada, a entrada passa pela cola do 2Captcha, como hoje (`_Site.ir`). Um CAPTCHA resolvido segue a leitura normal e dá `conectado`.

401 e 403 (D139.18, resposta (a) da seção 10): o pedido punha "401/403 da sessão" em "Precisa entrar de novo". O código trata 401 e 403 como `bloqueio` (`src/jobot/navegador/pagina.py:285`), e a regra do projeto diz que 401, 403, página de login ou desafio fazem a fonte falhar, sem distinguir. O construtor mantém o 401 e o 403 em "Não deu para conferir", com o motivo `bloqueio`, sem mudar o contrato de `visitar`. O dono confirmou em 2026-11-15 a opção (a): só a tela de login leva a "Precisa entrar de novo".

"Fazer login agora" (D139.20):

| `Resultado` | Estado | Motivo |
|---|---|---|
| `pronto` | `conectado`, e `entrou_em` passa a ser agora | nulo |
| `nao_entrou`, `tempo_esgotado` | `precisa_entrar`, `entrou_em` fica como estava | nulo |
| `sem_tela`, `sem_navegador`, `em_uso` | `nao_conferiu` | o nome do resultado |

Assim, quem nunca entrou e fecha a janela sem entrar continua em "Nunca entrou".

"Esquecer logins" (D139.19): depois de `apagar_perfil`, cada site de `leitores_do_painel(request)` (não o `LEITORES` global, para os testes poderem injetar) grava `estado = 'precisa_entrar'`, `motivo = 'esquecido'`, `entrou_em = NULL` e `avisado_em = NULL`. A tela mostra "Nunca entrou", sem faixa e sem aviso. A linha não é apagada.

(decisão da sessão) "Esquecer logins" grava `conferido_em` = agora, só para cumprir o `NOT NULL`: esquecer não é uma conferência. Com o motivo `esquecido`, o cartão não mostra hora, como no "Nunca entrou" sem linha (seção 5.7), e esse `conferido_em` não conta para o intervalo do "Conferir agora" (seção 5.4).

Interruptor: desligar o site não mexe na linha. A tela mostra "Desligado", e a faixa some porque ela só olha sites ligados (D139.13). Ao ligar de novo, volta o último estado gravado, com a hora dele; se a queda ainda estava aberta, a faixa volta junto.

### 5.2 Onde fica no banco

Migração `src/jobot/banco/migracoes/0009_sessao_site.sql` (D139.16):

> Número a confirmar na junção (D144, item 3). O lote do visual de app do Mac também cria uma migração (`NNNN_andamento.sql`). Quem chega à `dev` primeiro fica com o 0009; quem constrói Contas usa o primeiro número livre na base e renomeia, juntos, o arquivo `.sql` e o `test_migracao_NNNN.py`. O conteúdo da migração não muda.

```sql
-- Estado da conta de cada site com login (D139.16): uma linha por site, atualizada no lugar.
CREATE TABLE sessao_site (
  fonte        TEXT PRIMARY KEY REFERENCES fonte(chave),
  estado       TEXT NOT NULL CHECK (estado IN ('conectado','precisa_entrar','nao_conferiu')),
  motivo       TEXT CHECK (motivo IS NULL OR motivo IN (
                 'sem_rede','desafio','bloqueio','no_limite','sem_tela','sem_navegador',
                 'em_uso','erro','esquecido')),
  conferido_em TEXT NOT NULL,  -- hora da última conferência, ISO com fuso, do relógio injetado
  entrou_em    TEXT,           -- última vez visto conectado; NULL = nunca entrou
  avisado_em   TEXT            -- queda aberta: aviso já mandado ou marcado; NULL = sem queda aberta
);
```

- Uma função em `src/jobot/banco/` (por exemplo `banco/sessoes.py`) grava numa instrução só: `INSERT INTO sessao_site (...) VALUES (...) ON CONFLICT(fonte) DO UPDATE SET ...`, com `COALESCE` onde o valor antigo tem de ficar. O `entrou_em` vira agora em `conectado` e fica como está em `precisa_entrar` e `nao_conferiu`. Nunca `INSERT OR REPLACE` (`padroes.md («Esquema»)`).
- A mesma função decide o `avisado_em`: vira a hora de agora na passagem para `precisa_entrar` com `entrou_em` já preenchido e `avisado_em` nulo; volta a `NULL` quando o estado vira `conectado` e no "Esquecer logins"; fica como está nos outros casos, `nao_conferiu` inclusive. Site que nunca entrou (`entrou_em` nulo) nunca recebe `avisado_em`. Ela devolve se esta gravação abriu a queda (a passagem para "Precisa entrar de novo" ainda sem aviso), para quem chama decidir o `notify-send` (seção 5.6).
- Nada vai para `evento` (D139.17): o `CHECK` de `evento.acao` e o `vaga_id NOT NULL` são só de vaga. A história da sessão já fica na `execucao` e na saúde de cada leitura. A `sessao_site` guarda só o estado atual.
- Nenhum gatilho novo. Os que existem (`vaga_sem_delete`, `evento_sem_update`, `evento_sem_delete`, `vaga_fts_insert`, `vaga_fts_update`) não tocam a tabela nova. A migração só cria tabela, sem `DROP` nem reconstrução, então o cuidado com `foreign_keys` de `migrar.py:71` basta.
- Sem semeadura: site sem linha é "Nunca entrou". A chave estrangeira vale porque `LEITORES` já semeia a `fonte` de cada site com login em todo banco (`padroes.md («Interruptor»)`).
- O motivo tem ramo nulo e conjunto fechado, com teste do `CHECK` nos dois lados (`padroes.md («Teste de migração»)`).

### 5.3 A hora na tela

- `conferido_em` é gravado com a hora do relógio injetado, em ISO com fuso (`relogio.agora().isoformat()`).
- Na tela, a hora vira hora local, e o dia é comparado com o dia local de `relogio_do_painel(request).agora()`, nunca com UTC (`padroes.md («Dia de calendário»)`, `padroes.md («Painel»)`) (D139.24):
  - mesmo dia local: "conferido hoje às 09:02" / "checked today at 09:02";
  - dia anterior: "conferido ontem às 18:01" / "checked yesterday at 18:01";
  - antes: "conferido em 13/11 às 09:02" / "checked on 11/13 at 09:02", pela `data_curta` de `src/jobot/painel/formatos.py:84-89`, que devolve `13/11` em pt e `11/13` em en. Sem formato novo.
- A conta fica numa função pura e testável (por exemplo `formatos.conferido_texto(conferido_em, agora, idioma)`), com três chaves i18n com parâmetro `{hora}` e `{data}` (`padroes.md («i18n»)`).

### 5.4 "Conferir agora"

Camadas

- O navegador ganha `conferir_sessao(leitor, deps, relogio) -> Conferencia`, num arquivo próprio (por exemplo `src/jobot/navegador/conferir.py`) (decisão da sessão). `Dependencias` não tem relógio, e `Dependencias.politica` é `Callable[[LeitorComLogin], Politica]` (`src/jobot/navegador/execucao.py:76-83`). Por isso a política é `deps.politica(leitor)`, e o relógio entra como argumento: na rota, `relogio_do_painel(request)` (`src/jobot/painel/rotas/vagas.py:60`). Nenhum campo novo em `Dependencias`, e nenhuma montagem de `Dependencias` nos testes muda.
- Ela reaproveita o que `_sessao_aberta` faz: abre o contexto com o perfil, chama `visitar(page, leitor.url_entrada, leitor, deps.politica(leitor), relogio)` **sem** `cola` (sem gasto de 2Captcha) e, na `Captura`, olha `leitor.pagina_logada`. Devolve o estado e o motivo da tabela da seção 5.1. Quando dá `conectado`, grava `entrou_em` = agora, como a leitura agendada e o "Fazer login agora". O tratamento de exceção é o mesmo: `ErroDoPlaywright` que não seja fechamento dá `sem_rede`, outra `Exception` dá `erro` e vai para o log. Não abre escopo, não lê lista nem detalhe, não grava `execucao` nem saúde.
- O LinkedIn tem `rolar = True` (`src/jobot/nucleo/leitores/linkedin.py:140`), então a conferência também rola a página de entrada. É o mesmo caminho da entrada da leitura, e fica assim.
- Antes de abrir, `perfil_em_uso(pasta_do_perfil(...))` verdadeiro devolve `nao_conferiu` com `em_uso`.
- Sem tela ou sem navegador devolve `nao_conferiu` com `sem_tela` ou `sem_navegador`, sem abrir nada (mesmos testes que `executar_login`).
- A gravação no banco e o aviso ficam numa função de `navegador` que chama `banco`, para a rota e a leitura agendada usarem o mesmo caminho.

Rota e trava

- `POST /configuracoes/contas/{chave}/conferir` confere a chave contra `leitores_do_painel(request)`: fora dela, 404 (`padroes.md («Serve»)`: interruptor que só o laço respeita, a rota nova confere a chave; molde em `src/jobot/painel/rotas/configuracoes.py:411-420`). Site desligado (D139.31, decisão da sessão): a rota devolve o cartão como está, sem abrir nada e sem pegar a trava. O botão já some nesse caso; a recusa vale para quem chama a rota direto.
- Intervalo mínimo (D139.35): o "Conferir agora" só roda se já passaram 10 minutos desde o `conferido_em` do site, de qualquer origem (leitura agendada, "Buscar agora", "Conferir agora" ou "Fazer login agora").
  - A constante é `limites.INTERVALO_CONFERIR_S = 600`, em `src/jobot/navegador/limites.py`, ao lado de `PRAZO_CONFERIR_S`.
  - A conta compara `relogio_do_painel(request).agora()` com o `conferido_em`. A borda libera: com exatamente 600 s passa; com menos, recusa.
  - Dentro do intervalo, o botão do cartão fica desabilitado e o cartão mostra a hora da última conferência (seção 5.7). A rota recusa antes de pegar a trava e sem abrir o navegador, e devolve o cartão como está (vale também para quem chama a rota direto).
  - A conta fica numa função pura, usada pelo cartão e pela rota.
  - (decisão da sessão, D139.36) Site sem linha e linha com o motivo `esquecido` não entram na conta: esquecer não é conferência.
  - Só o botão tem intervalo: a leitura agendada e o "Fazer login agora" seguem sem ele.
  - A ordem na rota: chave (404), site desligado, intervalo, trava.
- Depois dessas conferências, a rota pega a trava `login` por `_trava(request, "login")` (nome da T240). Trava ocupada (leitura agendada, "Fazer login agora" ou outra conferência): responde na hora "Já tem algo usando o navegador; tente daqui a pouco." e não começa. Livre: `trava.acquire()` logo depois de `locked()`, sem `await` no meio (`padroes.md («Laço e travas»)`), e a conferência vira tarefa por `criar_tarefa(request, "conferir conta", trava, ...)`, com conexão própria e aguardada antes de fechar as conexões (`padroes.md («Serve»)`).
- Prazo: nova constante `limites.PRAZO_CONFERIR_S = 60` (D139.32). Estourou: `nao_conferiu` com `sem_rede`, a janela fecha e a trava solta. Toda espera de rede tem prazo (`padroes.md («Espera de rede tem prazo»)`).
- Limite aceito (decisão da sessão): dentro dos 60 s, um 429 faz o `visitar` dormir 30 s ou o `Retry-After` (até 600 s, `src/jobot/nucleo/http.py:20-21`, `src/jobot/navegador/limites.py:35`), e o Cloudflare espera até 30 s (`limites.py:14`). Nesses casos o prazo estoura, e o motivo sai `sem_rede`, não `no_limite` nem `desafio`. A constante leva o comentário `shortcut: 429 e Cloudflare longos estouram o prazo e viram sem_rede; rever se a pessoa precisar do motivo certo`.
- A janela é a do Playwright, com o perfil do joBot, a mesma da leitura agendada. Ela aparece e fecha sozinha.

Espera na tela

- O botão troca o miolo do cartão por "Conferindo…" com `aria-busy="true"`, num fragmento que repete `GET /configuracoes/contas/{chave}/conferir` a cada 2 s. O `GET` devolve 204 enquanto a tarefa roda (`padroes.md («Tela com HTMX»)`, `padroes.md («JS do painel»)`) e, no fim, o cartão inteiro com o estado novo e a hora. A faixa do topo é recarregada com um `HX-Trigger` (`contas-mudou`) que o `#aviso-contas` escuta.
- (decisão da sessão) Quatro respostas finais mandam o cabeçalho `HX-Trigger: contas-mudou`: o `GET` final do "Conferir agora", o `GET` final do "Fazer login agora", o interruptor e o `esquecer/confirmar`. Hoje o polling do login troca só o `#login-site-{chave}` (`src/jobot/painel/templates/configuracoes/_cartao_site_login.html:15`), o interruptor devolve o cartão sem gatilho (`src/jobot/painel/rotas/configuracoes.py:411-420`) e o esquecer devolve só o `_esquecer.html` (`:511-529`). Por isso:
  - o `GET` final do login devolve também o selo e a hora do cartão por `hx-swap-oob`, ou troca o cartão inteiro;
  - o `esquecer/confirmar`, no sucesso, devolve junto os cartões dos sites recarregados (`_sites_cartoes.html` por `hx-swap-oob`), e o gatilho atualiza a faixa. Os cartões não escutam o `contas-mudou`: só o `#aviso-contas` escuta, para nenhuma resposta disparar outra carga dos cartões.
- Como no `_login_site.html`, o estado da tarefa em andamento fica em `app.state` só enquanto ela roda. O resultado fica no banco.

### 5.5 A faixa no topo

- `base.html` ganha, logo depois do `#aviso-versao` (`base.html:64`), `<div id="aviso-contas" role="status" hx-get="/aviso-contas" hx-trigger="load, contas-mudou from:body" hx-swap="innerHTML"></div>` (D139.23).
- A rota `GET /aviso-contas` fica num arquivo próprio, `src/jobot/painel/rotas/aviso_contas.py`, no molde de `aviso_versao.py`. Ela devolve um fragmento vazio quando nenhum site tem queda aberta (seção 5.1): site ligado, com leitor registrado, com `entrou_em` e `avisado_em` preenchidos, seja qual for o `estado` gravado (`precisa_entrar` ou `nao_conferiu`; em `conectado` o `avisado_em` é sempre nulo). Com um ou mais, devolve a faixa (texto abaixo).
- (decisão da sessão) A consulta cruza `sessao_site` com `fonte.ligada` e com os leitores registrados: fonte órfã (sem leitor) não aparece, como em `_disparar_login` (`src/jobot/painel/rotas/execucao.py:136-138`). Os leitores vêm de `leitores_do_painel(request)`. A T241 cria essa função em `configuracoes.py` (`docs/superpowers/plans/2026-11-15-fase-2-primeiro-site-resto.md:185`) e o passo `/primeira-execucao/sites` já a usa; com a terceira rota, ela muda para um módulo de `painel/`, sem cópia, e as três rotas importam de lá (`padroes.md («Painel»)`).
- Texto da faixa:
  - um site: "Sua sessão no LinkedIn caiu. Entre de novo para o joBot voltar a ler as vagas." / "Your LinkedIn session ended. Sign in again so joBot can read jobs again.";
  - mais de um: "Sua sessão caiu em {quantos} sites. Entre de novo para o joBot voltar a ler as vagas." / "Your session ended on {quantos} sites. Sign in again so joBot can read jobs again.";
  - o botão "Entrar de novo" / "Sign in again" é um link para `/configuracoes/contas#conta-{chave}` (o primeiro site da lista). Ele não abre o Chrome direto: na aba Contas a pessoa vê o estado e aperta "Fazer login agora".
- Sem botão de fechar (D139.13). A faixa fica enquanto a queda estiver aberta, não só no estado "Precisa entrar de novo" (D139.34). Ela some quando o site volta a "Conectado", é desligado ou passa pelo "Esquecer logins". Em "Não deu para conferir" a faixa fica e o cartão mostra o estado real, com o motivo.
- Na própria aba Contas, a faixa continua (ela é da casca). O link leva ao cartão do site.
- A faixa usa só CSS do projeto, sem recurso externo.

### 5.6 Aviso no computador, uma vez por queda

- O aviso sai quando a gravação passa o site para "Precisa entrar de novo" (com `entrou_em` preenchido: site que nunca entrou não avisa) e `avisado_em` está nulo. Na mesma instrução, `avisado_em` vira a hora de agora (D139.22).
- Quem avisa (D139.22): só a leitura (`executar_login`), por `deps.avisar` em `asyncio.to_thread`, como `_Janela.parar` faz hoje (`src/jobot/navegador/execucao.py:267-269`). Título `_TITULO_AVISO` ("joBot"). Frase nova ao lado de `_FRASES_AVISO`, em pt e en, no idioma de `_idioma(con)` (`:117`), com o `{site}` vindo de `leitor.nome`:
  - pt: "Sua sessão no {site} caiu. Abra o joBot e entre de novo em Configurações › Contas."
  - en: "Your {site} session ended. Open joBot and sign in again in Settings › Accounts."
- (decisão da sessão) O "Buscar agora" também roda `executar_login`, com o motivo `agora` (`src/jobot/painel/rotas/execucao.py:128-145`). A leitura avisa seja qual for o motivo: continua uma vez por queda, e o código não precisa saber quem disparou.
- "Conferir agora" e "Fazer login agora" acontecem com a pessoa na tela: elas gravam `avisado_em` sem mandar o `notify-send`, porque a pessoa já vê a faixa. A próxima leitura agendada, então, não avisa de novo.
- Uma queda é o intervalo entre o site já conectado passar a "Precisa entrar de novo" e voltar a "Conectado" (ou passar pelo "Esquecer logins"). `nao_conferiu` no meio não reabre o aviso, e a faixa fica: o `avisado_em` só volta a nulo em "Conectado" ou no "Esquecer logins".
- Sem `notify-send`, `avisar` já trata o código 127 e só registra no log (`src/jobot/sistema/aviso.py`).
- É o mesmo canal do aviso de CAPTCHA da ADR 0005 ("aviso no computador", `docs/decisions/0005-sites-com-login.md:28`). Nada sai do computador: não é notificação push nem ntfy, que a ADR 0013 proíbe (`docs/decisions/0013-gmail-e-avisos.md:20`).

### 5.7 A aba Contas

Rotas (D139.25)

- `GRUPOS` troca `"sites-com-login"` por `"contas"`, no mesmo lugar (`configuracoes.py:61`): depois da T240, a penúltima, antes de `"ferramentas"`, e não no fim. `_COM_LOGIN` passa a valer `"contas"`, e `_PARCIAIS` aponta para o template novo `contas.html`. A aba continua visível só com leitor (`:94`).
- `GET /configuracoes/sites-com-login` responde 303 para `/configuracoes/contas`, numa rota declarada antes da genérica `/{grupo}` (`:400`).
- As rotas de ação passam para `/configuracoes/contas/...`: `{chave}/interruptor`, `{chave}/login` (POST e GET), `{chave}/conferir` (POST e GET, nova), `esquecer` e `esquecer/confirmar`. Sem cópia nas rotas velhas: só os templates do próprio painel as chamam, e a página antiga já leva para a nova.

Cartão do site (`_cartao_site_login.html`, dentro de `_sites_cartoes.html` da T241), com `id="conta-{chave}"`

- (decisão da sessão) Um id só. Hoje o cartão tem `id="cartao-site-{chave}"`, que o interruptor usa como `hx-target` (`src/jobot/painel/templates/configuracoes/_cartao_site_login.html:3,5`). Ele passa a `conta-{chave}` em todo lugar: o `hx-target` do interruptor, o link da faixa e os testes de tela e de integração, achados com `grep -rn "cartao-site-" src tests`.
- Nome do site e o selo do estado (seção 5.1), com o texto e a forma, nunca só a cor.
- A hora: "conferido hoje às 09:02". "Nunca entrou" não mostra hora, seja sem linha, seja com o motivo `esquecido` (seção 5.1); "Desligado" mostra a última hora gravada, se houver e se o motivo não for `esquecido`.
- O motivo em "Não deu para conferir", numa linha curta (seção 5.8).
- Botões: "Conferir agora" (some quando "Desligado" ou "Nunca entrou", D139.37, e a rota não recusa o "Nunca entrou"; fica desabilitado dentro do intervalo de 10 minutos da seção 5.4, com a hora da última conferência à vista e a frase `configuracoes.contas.conferir_espera` ligada ao botão por `aria-describedby`), "Fazer login agora" (como hoje), o interruptor (como hoje) e "Última leitura" com a saúde da última leitura, como hoje.
- Sem navegador: o cartão aponta para Configurações › Ferramentas, como a T240 já faz, e os botões que abrem o Chrome ficam desabilitados.

Fim da aba

- Os horários de leitura (como hoje).
- A linha do 2Captcha (D139.26): "2Captcha: chave salva" ou "2Captcha: sem chave", lida de `contexto_captcha` (só a máscara, nunca a chave). Com chave, o botão "Testar" chama o mesmo `POST /configuracoes/servicos/captcha/testar` e mostra o resultado num `#resultado-captcha-contas`; o teste roda só no clique. Um link "Mudar em Serviços" leva a `/configuracoes/servicos`.
- (decisão da sessão) `contexto_captcha` é reaproveitado como está, igual à aba Serviços (`src/jobot/painel/rotas/servicos.py:50-70`): ele lê o cofre a cada carga da página e pode esperar até `PRAZO_COFRE_S` (`src/jobot/navegador/limites.py:28`). O "Testar" manda o `POST` sem o campo `chave`, e a rota usa a chave salva; a resposta sai sempre com 200 (`servicos.py:119-150`).
- "Esquecer logins" no fim, como hoje.

Fora da aba

- `fontes/pagina.html:73`: o link vai para `/configuracoes/contas`, e o texto de `fontes.ligar_em_sites_com_login` passa a "Ligue e desligue em Configurações › Contas" / "Turn on and off in Settings › Accounts" (D139.28).
- O passo `/primeira-execucao/sites` da T241 mantém o título "Sites com login (opcional)" e os mesmos cartões, agora com o estado (D139.27). O assistente fala de sites; a aba fala de contas porque vai juntar outras coisas.

### 5.7.1 Cartão do Gmail

Entra na aba Contas junto com os cartões dos sites (ADR 0024, D145). É uma decisão do dono (R2); os nomes e os estados abaixo são escolhas da sessão, na D145.

- Campos: o endereço do Gmail e a senha de app. A senha é campo de senha e nunca é mostrada de volta: depois de salva, o cartão diz só que há uma senha guardada. Os dois valores vão para o cofre (`gmail_conta` e `gmail_senha_de_app`). O joBot tira os espaços da senha colada.
- "Conferir agora": entra por IMAP em `imap.gmail.com`, porta 993, SSL, com a biblioteca padrão, e abre a caixa de entrada só para leitura. Não lê nem grava mensagem. O intervalo mínimo de 10 minutos entre conferências (D139) vale também aqui.
- Estados, os mesmos dos sites com login (D139): "Conectado", "Precisa entrar de novo", "Nunca entrou" e "Não deu para conferir". Login recusado pelo Google (`AUTHENTICATIONFAILED`) é "Precisa entrar de novo", o que também acontece quando a pessoa troca a senha da conta Google e o Google revoga as senhas de app. Falha de rede é "Não deu para conferir".
- (decisão da sessão) O Gmail segue as mesmas regras de faixa do topo e de aviso `notify-send` dos sites (seções 5.1 e 5.6): só abrem depois de uma conferência que deu certo (`entrou_em` preenchido).
- (decisão da sessão) Ao salvar, o painel testa o login antes de guardar: senha recusada não é guardada, o cartão fica em "Nunca entrou" e a mensagem aparece embaixo do campo.
- O cartão linka para o tutorial da wiki (`Gmail-senha-de-app` e `Gmail-app-password`), com os links oficiais do Google e o aviso de quem não consegue senha de app (conta de trabalho ou escola, Proteção Avançada, verificação em duas etapas só com chaves de segurança).
- Só contas Google (R3). A leitura dos e-mails continua na fase 6; este lote só confere o login.
- Texto novo nos catálogos `pt` e `en`, como o resto da aba.

### 5.8 Textos (i18n)

Chaves novas em `src/jobot/painel/i18n/{pt,en}/configuracoes.json` e `casca` (D139.29). As que já existem em `configuracoes.sites_com_login.*` e mantêm o sentido (horários, esquecer, fazer login, `login.*`) ficam com o nome atual, para não espalhar troca de chave. Só a chave do nome da aba sai. O nome da aba vem de `configuracoes.grupo.<grupo>`, montada em `configuracoes.py:225` como `"configuracoes.grupo." + g.replace("-", "_")` (hoje `configuracoes.grupo.sites_com_login`, `src/jobot/painel/i18n/pt/configuracoes.json:77`). Ela dá lugar a `configuracoes.grupo.contas`, com `grep` em `src` e `tests` e teste de ausência de `configuracoes.grupo.sites_com_login` nos dois idiomas (`padroes.md («i18n»)`).

| Chave | pt | en |
|---|---|---|
| `configuracoes.grupo.contas` | Contas | Accounts |
| `configuracoes.contas.explicacao` | Aqui você vê se o joBot ainda está conectado em cada site e entra de novo quando precisar. | See whether joBot is still signed in to each site, and sign in again when needed. |
| `configuracoes.contas.estado.conectado` | Conectado | Signed in |
| `configuracoes.contas.estado.precisa_entrar` | Precisa entrar de novo | Needs to sign in again |
| `configuracoes.contas.estado.nunca_entrou` | Nunca entrou | Never signed in |
| `configuracoes.contas.estado.nao_conferiu` | Não deu para conferir | Could not check |
| `configuracoes.contas.estado.desligado` | Desligado | Off |
| `configuracoes.contas.conferido.hoje` | conferido hoje às {hora} | checked today at {hora} |
| `configuracoes.contas.conferido.ontem` | conferido ontem às {hora} | checked yesterday at {hora} |
| `configuracoes.contas.conferido.data` | conferido em {data} às {hora} | checked on {data} at {hora} |
| `configuracoes.contas.conferir` | Conferir agora | Check now |
| `configuracoes.contas.conferindo` | Conferindo… | Checking… |
| `configuracoes.contas.ocupado` | Já tem algo usando o navegador; tente daqui a pouco. | Something is already using the browser; try again in a moment. |
| `configuracoes.contas.conferir_espera` | Conferido há pouco. Dá para conferir de novo em alguns minutos. | Checked a moment ago. You can check again in a few minutes. |
| `configuracoes.contas.motivo.sem_rede` | Sem internet ou o site não respondeu. | No internet, or the site did not answer. |
| `configuracoes.contas.motivo.desafio` | O site pediu uma verificação anti-robô. | The site asked for an anti-robot check. |
| `configuracoes.contas.motivo.bloqueio` | O site recusou o acesso. | The site refused access. |
| `configuracoes.contas.motivo.no_limite` | O site pediu para esperar. | The site asked to wait. |
| `configuracoes.contas.motivo.sem_tela` | Sem tela para abrir o navegador. | No screen to open the browser. |
| `configuracoes.contas.motivo.sem_navegador` | O navegador não está instalado. | The browser is not installed. |
| `configuracoes.contas.motivo.em_uso` | O navegador do joBot já estava aberto. | joBot's browser was already open. |
| `configuracoes.contas.motivo.erro` | Algo deu errado. Os detalhes estão no registro. | Something went wrong. Details are in the log. |
| `configuracoes.contas.captcha.salva` | 2Captcha: chave salva | 2Captcha: key saved |
| `configuracoes.contas.captcha.sem_chave` | 2Captcha: sem chave | 2Captcha: no key |
| `configuracoes.contas.captcha.mudar` | Mudar em Serviços | Change in Services |
| `casca.aviso_contas.um` | Sua sessão no {site} caiu. Entre de novo para o joBot voltar a ler as vagas. | Your {site} session ended. Sign in again so joBot can read jobs again. |
| `casca.aviso_contas.varios` | Sua sessão caiu em {quantos} sites. Entre de novo para o joBot voltar a ler as vagas. | Your session ended on {quantos} sites. Sign in again so joBot can read jobs again. |
| `casca.aviso_contas.entrar` | Entrar de novo | Sign in again |

- O motivo `esquecido` não aparece: ele só existe para "Nunca entrou".
- Os conjuntos fechados (estados e motivos) têm teste que confere as chaves em pt e en (`padroes.md («i18n»)`).
- O `erro` é uma chave fixa, dada a qualquer exceção na entrada que não seja `ErroDoPlaywright`, `NavegadorFechado` nem `sqlite3.Error` (seção 5.1); o detalhe vai para `_LOG.warning` com `exc_info` onde a falha nasce (`padroes.md («Falha de sistema na tela»)`).
- Nenhum texto manda a pessoa ao terminal (`padroes.md («Painel e ADRs»)`, ADR 0023).

### 5.9 Documentos

- `CHANGELOG.md` e `CHANGELOG.en.md` (Não lançado, linha 13): "Configurações, Sites com login" vira "Configurações, Contas" / "Settings, Accounts", e entra uma linha nova: "A aba Contas mostra se o joBot ainda está conectado em cada site, confere na hora e avisa quando a sessão cai." / "The Accounts tab shows whether joBot is still signed in to each site, checks on demand and warns when the session ends." Sem número de dúvida (`padroes.md («Doc»)`).
- `README.md:179` e `README.en.md:179` dizem que "os sites com login chegam na fase 2". A segunda frase passa a: "Os sites com login (por enquanto, o LinkedIn) ficam em Configurações, Contas, que mostra se o joBot ainda está conectado em cada um." / "Sites with login (for now, LinkedIn) live in Settings, Accounts, which shows whether joBot is still signed in to each one." Usa a vírgula, como o resto do README.
- Wiki: `wiki/Como-funciona.md` e `wiki/How-it-works.md` citam "Sites com login" / "Sites with login" só como tipo de fonte, nunca como aba, e nenhuma página da wiki cita "Configurações ›". A wiki fica como está.
- `README.md:145` e `README.en.md:145` dizem "(Os sites com login chegam na fase 2, com duas buscas por dia.)" / "(Sites with login arrive in phase 2, with two searches a day.)". Passa a: "(Os sites com login, em Configurações, Contas, são lidos duas vezes por dia.)" / "(Sites with login, in Settings, Accounts, are read twice a day.)".
- Outros textos velhos que mudam no lote:
  - `src/jobot/painel/rotas/fontes.py:255`: o detalhe do 422 ("site com login liga em Configurações > Sites com login") passa a citar "Configurações > Contas";
  - `src/jobot/painel/rotas/fontes.py:64`: o comentário passa a citar "Configurações > Contas";
  - `src/jobot/painel/templates/configuracoes/_esquecer.html:7`: o link "cancelar" vai para `/configuracoes/contas`;
  - `src/jobot/painel/static/css/configuracoes.css:543`: o comentário passa a "Contas".
- Antes de fechar, `grep -rn "sites-com-login\|Sites com login\|Sites with login"` no repositório inteiro, menos `duvidas.md`, ADRs e planos antigos (`padroes.md («Doc»)`, `padroes.md («Texto de tela trocado»)`). O grep pega também o que esta lista não citou. Ficam como estão as linhas que falam de "sites com login" como tipo de fonte, não como aba (por exemplo `README.md:76`, `:116`, `:165`, `:190-192`, `:205`).

## 6. Riscos

1. A conferência pode ser lida pelo site como acesso automático. Mitigação: uma página só (`url_entrada`), sob a mesma política da leitura, e só no clique ou nas leituras agendadas. Sem visitas para manter a sessão (D139.7). O navegador não tem intervalo por host: a leitura só tem o sorteio de 3 a 8 s entre navegações da mesma execução (`src/jobot/navegador/execucao.py:352-353`, `src/jobot/navegador/limites.py:12-13`) e o `INTERVALO_MINIMO` de 4 h entre execuções (`src/jobot/agenda/login.py:8`). O "Conferir agora" tem o seu freio: o intervalo mínimo de 10 minutos desde o último `conferido_em` do site, de qualquer origem (`limites.INTERVALO_CONFERIR_S`, seção 5.4), mais a trava `login` (uma janela por vez) e o clique da pessoa.
2. Falso "Precisa entrar de novo": uma página logada que `pagina_logada` não reconhece. Mitigação: é o mesmo teste que a leitura já usa; se errar, a leitura também erra. O "Conferir agora" deixa a pessoa refazer.
3. Duas janelas no mesmo perfil. Mitigação: a trava `login` e o `perfil_em_uso`.
4. Avisos repetidos. Mitigação: `avisado_em` só volta a nulo em "Conectado" ou no "Esquecer logins".
5. A rota velha guardada em favorito. Mitigação: o 303.
6. Mudança de nome da aba quebra testes de tela que procuram "Sites com login". Mitigação: lista na seção 7.
7. A faixa diz que a sessão caiu mesmo quando a leitura seguinte só não conseguiu conferir (sem rede, navegador em uso, desafio), porque a faixa segue a queda aberta (D139.34). Mitigação: o cartão mostra "Não deu para conferir" com o motivo, e "Conectado" fecha a faixa.

## 7. Testes esperados

Todos com a rede bloqueada e o relógio injetado. Cada um nasce vermelho pelo motivo certo (`padroes.md («Vermelho»)`).

Unidade (`tests/unidade/`)

- A conta do estado na tela: as cinco linhas da tabela da seção 5.1, inclusive "Nunca entrou" sem linha e com `entrou_em` nulo, e "Desligado" na frente de tudo.
- O mapa da entrada para o estado: cada linha da tabela da leitura agendada, com o falso de `Page` em `tests/unidade` (`padroes.md («Teste sem navegador»)`).
- O mapa do `Resultado` do "Fazer login agora".
- `conferido_texto`: hoje, ontem e antes, com `TZ` fixado e entrada fora de UTC (`09:00-03:00`), desfeito no `yield` (`padroes.md («Dia de calendário»)`).
- Faixa: vazia sem queda aberta, vazia com o site desligado, vazia em "Nunca entrou" (`entrou_em` nulo, mesmo com `precisa_entrar`), texto de um e de vários sites.
- Intervalo do "Conferir agora" (função pura): 599 s recusa, 600 s libera (a borda) e 601 s libera; vale o `conferido_em` de qualquer origem; site sem linha e linha com o motivo `esquecido` liberam.
- Aviso uma vez: duas leituras seguidas em "Precisa entrar de novo" chamam `avisar` uma vez; volta a "Conectado" e cai de novo: avisa de novo; `nao_conferiu` no meio não avisa; `precisa_entrar` com `entrou_em` nulo (nunca entrou) não avisa e não grava `avisado_em`; o `avisado_em` volta a nulo em "Conectado" e no "Esquecer logins".
- `conferir_sessao` não passa `cola` para `visitar` e não abre escopo.
- Exceção na entrada: `ErroDoPlaywright` grava `sem_rede`; outra exceção grava `erro`; `NavegadorFechado` não grava nada.
- `Dependencias` não ganha campo (seção 5.4). Se um campo aparecer, ele entra nos oito lugares que montam `Dependencias` nos testes (`padroes.md («Teste de navegador»)`): `tests/navegador/test_execucao_logada.py:87` e `:650`, `tests/unidade/test_capturar_logado.py:303`, `tests/navegador/test_capturar_logado_site.py:110`, `tests/navegador/test_janela_parada.py:103`, `tests/navegador/test_login_manual.py:42`, `tests/navegador/test_captcha_logado.py:200` e `tests/unidade/test_janela_comum.py:110`.
- Chaves i18n dos conjuntos fechados em pt e en; ausência de `configuracoes.grupo.sites_com_login`.

Integração (`tests/integracao/`)

- `test_migracao_0009.py`: lê só a `0009`; banco em memória; `ULTIMA` pela contagem dos `.sql`; o `CHECK` do estado e do motivo, com o ramo nulo; a chave estrangeira para `fonte` (`padroes.md («Teste de migração»)`).
- Gravação: duas gravações do mesmo site deixam uma linha (`ON CONFLICT`); `entrou_em` mantido em `precisa_entrar` e `nao_conferiu`; nenhuma linha nova em `evento`.
- `test_rota_sites_com_login.py` vira `test_rota_contas.py`: `GET /configuracoes/sites-com-login` dá 303 para `/configuracoes/contas`; as rotas de ação no caminho novo; o "Esquecer logins" deixa o estado em "Nunca entrou", sem hora; o "Fazer login agora" grava o estado; o "Conferir agora" com a trava ocupada responde "ocupado" e não chama o navegador; com a trava livre, 204 enquanto roda e o cartão no fim; chave fora dos leitores dá 404; site desligado devolve o cartão sem chamar o navegador; as quatro respostas finais (seção 5.4) trazem `HX-Trigger: contas-mudou`.
- `GET /aviso-contas`: vazio e com faixa; vazio com fonte órfã (linha em `sessao_site` sem leitor registrado); a faixa continua quando "Precisa entrar de novo" vira "Não deu para conferir" (queda aberta); vazia em "Nunca entrou"; some em "Conectado" e depois do "Esquecer logins"; some com o site desligado e volta ao ligar com a queda aberta.
- "Conferir agora" e o intervalo (relógio injetado em `relogio_do_painel`): a 599 s do último `conferido_em` a rota devolve o cartão como está, sem chamar o navegador e sem pegar a trava (com a trava ocupada, a resposta é o cartão, não o "ocupado"; com ela livre, segue livre); a 600 s exatos libera e a conferência roda; o `conferido_em` de cada origem conta (leitura agendada, "Buscar agora", "Conferir agora" e "Fazer login agora"); o cartão dentro do intervalo traz o botão desabilitado, a hora da última conferência e a frase `conferir_espera`, e passado o intervalo o botão volta.
- A linha do 2Captcha: "chave salva" e "sem chave"; nenhum trecho da chave na resposta.
- `test_rota_fontes.py`: o link e o texto novos.
- `test_servir.py` não muda: ele não cita a aba, só a chave `configuracoes.sites_com_login.horarios.formato` (`tests/integracao/test_servir.py:234`), que fica pela D139.29.
- Leitura agendada com o site falso: entrada sem sessão grava `precisa_entrar`, e a leitura logada grava `conectado`.

Tela (`tests/tela/`, `-m tela`, só no CI)

- `test_sites_com_login.py` vira `test_contas.py`: o selo do estado e a hora; "Conferir agora" com a espera ("Conferindo…") e o cartão novo, esperando a resposta real e o fim do settle, nunca `sleep` (`padroes.md («Tela com HTMX»)`); a faixa no topo de outra tela e o link "Entrar de novo" levando ao cartão; a faixa que continua em "Não deu para conferir"; o botão "Conferir agora" desabilitado dentro do intervalo, com a hora da última conferência e a frase de espera.
- Procurar nos testes de tela e de integração as frases velhas e as negações (`not in`) de "Sites com login" (`padroes.md («Texto de tela trocado»)`).
- `tests/unidade/test_horarios.py:9` cita só o prefixo i18n `configuracoes.sites_com_login.horarios.`, não a rota. Fica como está (D139.29).

## 8. O que fica para o construtor

- O nome do arquivo e da função de gravação em `banco/` e do arquivo da conferência em `navegador/`, desde que respeitem as camadas.
- Se a gravação do estado entra em `_ler_paginas` direto ou num passo logo depois da entrada, desde que toda saída da entrada grave (`padroes.md («Site com parada»)`).
- O desenho visual do selo e da faixa, com as cores e formas que o painel já usa, e o texto além da cor.
- A ordem das tarefas dentro do lote, sempre depois da T240 e da T241; a tela e a faixa só depois da base visual (seção 3).
- Como o falso de `Page` simula o erro de rede.

## 9. Pontos que batem com o que já existe

- A trava `login` e `_trava(request, "login")` da T240.
- `criar_tarefa` e o molde do `GET` com 204 do "Fazer login agora".
- `_sessao_aberta` e `pagina_logada` para dizer se está logado.
- `deps.avisar` e o molde de `_Janela.parar` para o `notify-send`.
- O molde do `#aviso-versao` em `base.html` para a faixa.
- `contexto_captcha` e a rota `captcha/testar` de Serviços para a linha do 2Captcha.
- `relogio_do_painel` e `data_curta` para a hora.
- `leitores_do_painel` e `_sites_cartoes.html` da T241 para os cartões, no assistente e na aba.

## 10. Perguntas pendentes

O item 1 foi respondido pelo dono em 2026-11-15; os outros esperam a confirmação dele. A lista completa é a da D139, "Para confirmar" (itens 1 a 10); aqui ficam só os que mudam o desenho. O construtor não para por eles: segue a resposta dada em cada item. Se o dono trocar alguma, o desenho muda antes do plano.

1. (D139.18, R4) Respondido pelo dono em 2026-11-15, opção (a): 401 e 403 na entrada contam como "Não deu para conferir" (motivo `bloqueio`), como o código faz hoje, e não como "Precisa entrar de novo", como o pedido sugeria.
   - (a) Manter `bloqueio`. Não muda o contrato de `visitar`, segue a regra "401/403 = a fonte falhou", e a pessoa ainda vê o motivo. Escolhida pelo dono.
   - (b) Tratar 401/403 só da `url_entrada` como "Precisa entrar de novo", com um ramo próprio em `conferir_sessao` e em `_ler_paginas`. Pode mandar a pessoa entrar de novo quando o site só a bloqueou. Descartada.
   - O construtor segue (a), como a seção 5.1 descreve.
2. (D139.22) Só a leitura manda o `notify-send`. "Conferir agora" e "Fazer login agora" gravam o `avisado_em` sem mandar o aviso, porque a pessoa está na tela (seção 5.6).
3. (D139.25) As rotas de ação mudam de caminho sem cópia nas rotas velhas; só o `GET` velho leva para a nova.
4. (D139.27) O assistente mantém o título "Sites com login (opcional)".
5. (D139.29) As chaves i18n que mantêm o sentido ficam com o nome `configuracoes.sites_com_login.*`.
6. (D139.15) A ordem: T240 e T241 primeiro (o plano do lote declara `depende_de` T241), depois o lote Contas.

## 11. Todas as decisões da D139

Do dono (2026-11-15)

1. O protótipo do instalador no Canvas ganha a parte de IA no mesmo protótipo.
2. "Baixar Claude/Codex" quer dizer os programas de terminal Claude Code e Codex CLI, com login por assinatura; a chave de API é a alternativa, em Configurações › Serviços.
3. Grupo novo no instalador, "Inteligência artificial (opcional)", com Claude Code, Codex e Modelo local, desmarcados por padrão.
4. Cada site mostra um estado e a hora da última conferência, guardados no banco.
5. "Precisa entrar de novo" avisa na faixa do topo e no computador, uma vez por queda.
6. Botão "Conferir agora" por site, sem ler vagas, e conferência automática a cada leitura das 9h e das 18h.
7. Sem visitas para manter a sessão viva.
8. Uma aba "Contas" em Configurações troca a "Sites com login".
9. Lote pequeno agora, ainda na fase 2, antes do Panorama, só com o LinkedIn.
10. O Canvas ganha a IA agora; o instalador real sai na fase 3 sem ela e ganha o grupo de IA na fase 4.
11. O modelo local é escolhido pela RAM, e a pessoa pode trocar.
34. A faixa do topo segue a queda aberta, não só o estado "Precisa entrar de novo" (resposta do dono depois do desenho, 2026-11-15).
35. "Conferir agora" tem intervalo mínimo de 10 minutos desde o último `conferido_em` do site, de qualquer origem: `limites.INTERVALO_CONFERIR_S = 600` (resposta do dono depois do desenho, 2026-11-15).

Da sessão (para confirmar)

12. Estado "Desligado" para site com o interruptor desligado.
13. (confirmado pelo dono em 2026-11-15) A faixa fica enquanto a queda estiver aberta (site ligado, `entrou_em` e `avisado_em` preenchidos), mesmo em "Não deu para conferir"; some em "Conectado", ao desligar o site ou no "Esquecer logins"; sem botão de fechar.
14. Mudanças no Canvas (Ferramentas e página Pronto).
15. Este lote vem depois da T240 e da T241.
16. Tabela `sessao_site` na migração `0009`.
17. Nada vai para `evento`; nenhum gatilho novo.
18. Mapa da entrada para o estado, com 401 e 403 em "Não deu para conferir" (confirmado pelo dono em 2026-11-15).
19. "Nunca entrou" vem do `entrou_em` nulo; "Esquecer logins" volta a ele.
20. Mapa do resultado do "Fazer login agora".
21. "Conferir agora" mora no `navegador`, usa a trava `login`, não chama o 2Captcha e não grava `execucao`.
22. Aviso no computador só pela leitura agendada; as ações na tela marcam como avisado.
23. Faixa em `base.html` pela rota `/aviso-contas`, com o botão levando ao cartão do site.
24. Hora local, com hoje, ontem ou a data.
25. Grupo `contas`; o `GET` velho dá 303; as rotas de ação mudam de caminho sem cópia.
26. Linha do 2Captcha na aba, com o teste de Serviços.
27. O assistente mantém o título "Sites com login (opcional)".
28. Link e texto novos em `/fontes`.
29. Chaves i18n novas em `configuracoes.contas.*` e `casca.aviso_contas.*`; as antigas que mantêm o sentido ficam.
30. A conferência automática é a entrada da leitura agendada, sem visita a mais.
31. Site desligado não é conferido nem pelo botão nem pela leitura.
32. Prazo do "Conferir agora": `limites.PRAZO_CONFERIR_S = 60`.
33. A espera do "Conferir agora" pergunta a cada 2 s.
36. Site sem linha e linha com o motivo `esquecido` ficam fora do intervalo do "Conferir agora"; o botão desabilitado traz a frase `conferir_espera`, sem número.
37. O botão "Conferir agora" some em "Nunca entrou", como em "Desligado".

Os detalhes de cada uma estão em `duvidas.md`, D139.
