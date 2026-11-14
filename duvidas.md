# Dúvidas

Decisões que dependem do dono do projeto. As resolvidas ficam registradas aqui, com a data.

Status usados: **resolvida** (o dono decidiu); **decidido pela sessão, para confirmar** (a sessão de 2026-11-13 escolheu e o dono confere); **aberta, para confirmar** (o construtor só recomendou ou escolheu no código; o código segue a opção atual até o dono decidir).

## D1. Manter a opção "sessão do Claude Code"

**Status:** resolvida em 2026-11-13

**Assunto:** manter a opção em que o joBot chama, de forma automática e agendada, o Claude Code que a própria pessoa instalou e logou.

**Contexto:** as regras da Anthropic proíbem que um app de terceiro ofereça login do Claude.ai, encaminhe pedidos pelas credenciais de planos em nome dos usuários ou intermedeie credenciais. Elas também colocam produtos que rodam o Claude Code sob os Termos Comerciais, com cada pessoa autenticada na própria conta. O joBot não toca em credenciais e não empacota o Claude Code.

**Decisão:** manter a opção. O dono do projeto leu as regras da Anthropic e decidiu que esse uso está dentro delas: cada pessoa roda o próprio Claude Code, no próprio computador, com a própria assinatura e dentro do próprio limite. Nada é compartilhado entre pessoas. Os cuidados técnicos da ADR 0010 continuam valendo.

**Link:** [ADR 0010](docs/decisions/0010-claude-code-da-pessoa.md)

Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

## D2. Titular do copyright no arquivo LICENSE

**Status:** resolvida em 2026-11-13

**Contexto:** a licença MIT pede uma linha `Copyright (c) <ano> <titular>`.

**Decisão:** o titular é o apelido público do dono do projeto no GitHub. O arquivo [`LICENSE`](LICENSE) já está no repositório.

**Link:** [ADR 0016](docs/decisions/0016-licenca-clean-room-e-processo.md)

## D3. Contato para denúncias do Código de Conduta

**Status:** resolvida em 2026-11-13

**Contexto:** o Código de Conduta pede um contato privado para denúncias.

**Decisão:** o contato é o e-mail fezarosa@gmail.com, escolhido pelo dono do projeto. Ele está no Código de Conduta, em português e em inglês.

**Link:** [`.github/CODE_OF_CONDUCT.md`](.github/CODE_OF_CONDUCT.md)

## D4. Botão de patrocínio (FUNDING.yml)

**Status:** aberta, para confirmar

**Contexto:** o arquivo `.github/FUNDING.yml` mostra o botão Sponsor, mas precisa de uma conta de patrocínio, como GitHub Sponsors ou Ko-fi, que o projeto ainda não tem.

**Decisão provisória:** sem `FUNDING.yml` até o dono criar a conta e dizer qual usar.

## D5. Convenções da rotulagem do gabarito

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** O gabarito de 329 vagas (fora do repositório) foi rotulado por dois modelos, com um juiz nas 100 divergências. Algumas vagas não cabem num valor só.

**Decisão provisória:** Vaga remota para o mundo todo ou para uma região (LATAM, Américas, Europa) fica sem país. Faixa de nível (ex.: pleno/sênior) conta o menor nível. Contrato `clt` ou `pj` só vale para vaga no Brasil. As regras da T13 seguem as mesmas convenções, para a medição da T37 ser justa.

## D6. Ferramentas do esqueleto

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir). A parte do Dependabot (`target-branch`) está obsoleta pela ADR 0021.

**Contexto:** A T01 montou o pyproject, o CI e o Dependabot (o Dependabot saiu: obsoleta pela ADR 0021).

**Decisão provisória:** Backend de build `uv_build`. ~~O Dependabot do `uv` aponta para a `dev` (`target-branch`), o que só se confirma depois do primeiro push.~~ Obsoleta pela ADR 0021 (sem Dependabot). O CI de tela sai com código 5 enquanto não houver teste de tela (a T36 cria o primeiro).

## D7. Pasta de dados

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** A T02 lê a pasta de `JOBOT_DADOS`, depois `XDG_DATA_HOME`, depois `~/.local/share/jobot`.

**Decisão provisória:** Caminho relativo nessas variáveis é aceito como está (relativo à pasta atual). O umask 0o077 e a permissão do `jobot.db` ficam no ponto de entrada (T48), com `configurar_log` antes de `preparar_pasta`.

## D8. Cópia antes de migrar o banco

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** Antes de migrar, o joBot copia o banco.

**Decisão provisória:** A cópia se chama `jobot.db.antes-v<N>`, com N = versão guardada dentro dela; ficam as 3 mais recentes. Banco vazio (versão 0) não gera cópia. Chave estrangeira quebrada na migração levanta `sqlite3.IntegrityError`, sem exceção própria.

## D9. Tipos do núcleo

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** A T04 fechou os tipos que as outras tarefas usam.

**Decisão provisória:** `SalarioBruto` guarda os valores lidos como número decimal (float) antes da conversão para centavos. `RequisitosEstagio` guarda os campos como texto. `Salario.periodo_deduzido` marca quando o período foi deduzido. `VagaColetada` e `VagaTratada` só se constroem com argumentos nomeados.

## D10. Catálogo de textos (i18n)

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** A T07 criou o catálogo base em português e inglês.

**Decisão provisória:** Chaves no formato `area.<valor>`, `nivel.<valor>`, `modalidade.<valor>`, `contrato.<valor>`, `aviso.<valor>`, `fonte.<chave>`, `saude.<motivo>` e `seguranca.recarregue` (87 por idioma). Chave ausente devolve a própria chave; idioma desconhecido cai para português.

## D11. Quem aplica a correção na vaga (T21)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** O desenho se contradiz: a linha 553 diz que o reprocessamento aplica a correção por cima das regras, e a linha 1299 (seção 13.5) diz que a correção "aplica na hora". A T21 expôs o conflito.

**Opções:** (a) `corrigir()` só grava em `correcao`, e o reprocessamento aplica a correção; para cumprir o "aplica na hora", a rota de correção (T46) chama `corrigir()` e em seguida reprocessa aquela vaga. (b) `corrigir()` faz UPDATE nas colunas da vaga; uf, salário e fechada exigiriam lógica própria duplicada.

**Decisão:** Opção (a). A tela já volta com o valor corrigido, sem esperar a próxima busca. Para a T46 reprocessar uma vaga só, a T19 ganha `reprocessar_vaga(con, vaga_id) -> None` nas Interfaces, com `test_reprocessar_vaga_aplica_correcao`, e a T19 entra no `depende_de` da T46 (decisão 8 da sessão). Os critérios entraram no plano: `test_correcao_vence_regra_no_reprocesso` (T19), a correção valendo depois do reprocessamento das buscas salvas e do encaixe (T24) e `test_corrigir_aplica_na_hora` (T46). A docstring de `corrigir()` cita a decisão (ajuste F2). Escolhas do redator, para confirmar: `reprocessar_vaga` trata a ocorrência de `ultima_vista_em` mais recente, aberta de preferência (`test_reprocessar_vaga_usa_ocorrencia_aberta_mais_recente`), e a rota de correção não recalcula o encaixe por busca (nota e `oculta_motivo`), que fica com o da próxima busca ou recálculo.

## D12. Ações da vaga (T21)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A T21 gravou as ações de status, ocultar e mostrar. O desenho não define alguns detalhes.

**Opções:** `valor_antigo` de uf, salário e outro: (a) NULL até existir a lógica desses campos; (b) inventar um "de" agora. `trazer_de_volta`: (a) zerar `oculta_manual`; (b) restaurar um -1 anterior. Estado esperado: (a) as ações levantam `LookupError` (vaga não existe) e `ValueError` (valor inválido); (b) toleram o que está fora do estado esperado. `_transacao`: (a) recusa conexão que já está numa transação; (b) aninha.

**Decisão:** `valor_antigo` fica NULL para uf, salário e outro até a lógica existir (T46/T24). `trazer_de_volta` zera `oculta_manual` sem restaurar um -1. `acoes.py` levanta `LookupError` e `ValueError`, que a T45 traduz em 404 e 422 e testa. `_transacao` recusa conexão que já está numa transação. O critério de 404 e 422 entrou no plano, na célula de testes da T45.

## D13. Cliente HTTP educado (T05)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A revisão da T05 deixou quatro escolhas para o dono. O Greenhouse (T27) precisa do 404 e o 4xx genérico virava `ErroDeRede` sem o status.

**Opções:** Status: (a) atributo `status: int | None` em `ErroDeRede`, sem mudar o Protocol; (b) exceção nova `NaoEncontrado`, que muda o contrato (R4). `para_no_429`: (a) só o 429; (b) 429 e 503. `ler_em_fluxo`: (a) segue gerador assíncrono, usado com `contextlib.aclosing`; (b) vira função que devolve o corpo. Redirecionamento e DNS: (a) recusar redirecionamento de host público para loopback, link-local, rede privada ou `localhost`, e deixar a resolução de DNS para IP privado fora da fase 1; (b) resolver o DNS e conferir o IP.

**Decisão:** `ErroDeRede` ganha `status: int | None` (a), já no código (`src/jobot/nucleo/http.py:94-96`, repassado em `:362` e `:365`). `para_no_429` vale só para o 429; o 503 segue a regra do `Retry-After` mesmo nesse escopo (a) (`:347-349`). `ler_em_fluxo` segue gerador assíncrono com `aclosing` (a); o Protocol passa a anunciar `AsyncGenerator[bytes]` em vez de `AsyncIterator[bytes]` (`:62-64`), para quem chama usar `aclosing` sem cast (decisão 9, ajuste F2). O redirecionamento de host público para endereço local ou privado é recusado com `ErroDeRede`, e loopback para loopback, como nos testes, segue (conferência de host em `:126-141` e recusa em `:209-210`; `tests/unidade/test_http.py:504` e `:512`). IPv6 que embute IPv4 (`::/96` sem `::` e `::1`, e `64:ff9b::/96`) passa pela mesma conferência (decisão 14, ajuste F2).

**Risco aceito:** DNS rebinding e redirecionamento entre dois hosts locais (decisão 13). Num 307 ou 308 para outra origem o corpo JSON ainda é repassado, como fazem o httpx e os navegadores. A resolução de DNS para IP privado, que a opção (a) deixava fora da fase 1, ganha uma defesa parcial no ajuste F3 (decisão 15): quando a origem é pública, o host de destino do salto é resolvido com `loop.getaddrinfo` e o salto é recusado se algum endereço não for global, com `test_redirecionamento_para_nome_que_resolve_local_recusado` (sem rede). Fica aceito o rebinding entre a checagem e a conexão, porque fixar o IP exigiria um transporte próprio. A defesa olha só o salto de redirecionamento: a primeira requisição a uma URL local ou privada que vem de dado da fonte (`UrlListada.url` do sitemap, `VagaColetada.url`, que `src/jobot/nucleo/modelo.py:118-122` só confere como http ou https) não tem barreira, e o DR-19 do desenho vale só para "Adicionar site". Risco aceito até o dono decidir (para confirmar); a recomendação é checar o host de `UrlListada.url` com `_local` no executor (T16).

## D14. Leitor de salário (T10)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A T10 leu salário em texto livre. Algumas escolhas foram do construtor.

**Opções:** Moeda sem faixa de plausibilidade: (a) conta como implausível; (b) conta como plausível. Faixas fora do BRL: (a) as do construtor; (b) o dono define. Benefícios: (a) chave ASCII (ex.: `retirement`); (b) texto original. `401k` logo depois de símbolo de moeda: (a) é valor; (b) é benefício. Texto de salário muito longo: (a) acima de 2.000 caracteres não é lido; (b) lê tudo. Faixa com períodos mistos (só um lado diz o período): (d2) quando o máximo passa de 10 vezes o mínimo, não forma faixa e fica só o valor que tem período; a fonte da sessão não detalha as outras opções. Benefício seguido de valor sem conectivo: (a) tira esse valor do salário; (b) mantém.

**Decisão:** As primeiras opções (a) dos cinco primeiros itens (decisão 4 da sessão). Texto acima de 2.000 caracteres devolve o mesmo que texto sem salário. Faixa com períodos mistos: (d2); a faixa normal (até 10 vezes) e a regra de plausibilidade do desenho 10.3 não mudam (decisão 10, ajuste F2). Salário com `Decimal(int)` direto, sem `str`, para int grande (ajuste F2). O caso 107 do JSON falhou com `OverflowError` (vermelho por exceção, não por asserção); se esse vermelho vale fica para o revisor julgar. O último item (benefício seguido de valor sem conectivo) não consta nas decisões da sessão: o código segue a opção (a) até o dono confirmar.

## D15. Testes de tela rodam na fedora-dev (T36)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A caixa nortao não tem a `libatomic` que o driver do Playwright pede, então o Chromium não abre lá.

**Opções:** (a) rodar os testes de tela na fedora-dev; (b) instalar a biblioteca na caixa nortao.

**Decisão:** Opção (a) (decisão 5 da sessão). O Chromium do Playwright 1.65.1 (revisão 1254) foi instalado na fedora-dev. Na nortao, só rodam os testes sem a marca `tela`.

## D16. Texto e idioma (T08)

**Status:** aberta, para confirmar

**Contexto:** `detectar_idioma` e o extrator de HTML foram escritos sem corpus real.

**Opções:** Limiares: (a) 20 palavras, 5 acertos e 75%, calibrados na T37; (b) outros valores agora. Genérico de código com nome de elemento HTML de uma letra (`<B>`, `<I>`, `<U>`, `<S>`, `<Q>`, `<A>`): (a) tratado como tag; (b) lista de exceções. Prefixos de namespace do Word: (a) `o v w m x xml st1`; (b) aceitar qualquer prefixo.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opções (a). Se aparecer outro prefixo, ele entra na lista.

## D17. Parâmetros de rastreio na URL (T09)

**Status:** aberta, para confirmar

**Contexto:** `source`, `src`, `ref`, `referrer` e `referral` podem identificar a vaga em alguns sites.

**Opções:** (a) ficam fora da lista de rastreio; (b) entram na lista para todas as fontes; (c) entram por fonte, quando uma captura provar que é rastreio.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opção (a) agora, com (c) depois: incluir por fonte só com captura que prove. A normalização do caminho (`%7E`, ponto final no host, `//`) fica como limite da fase 1.

## D18. Contrato e local nas vagas do Brasil (T13)

**Status:** aberta, para confirmar

**Contexto:** `clt` e `pj` só valem para vaga no Brasil (D5). A Gupy remota chega com cidade e estado vazios, e `rotular()` não sabe que é Brasil.

**Opções:** (a) o coletor põe "Brasil" em `locais`; (b) `rotular()` presume Brasil quando a fonte é brasileira; (c) vaga sem local nunca recebe clt ou pj.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opção (a), como o construtor recomendou. A conferência com o gabarito (T37/T78) mostra se resolve.

## D19. Contrato do ciclo de vida (T14)

**Status:** aberta, para confirmar

**Contexto:** A T14 fechou as funções puras do ciclo de vida sem mudar o esquema.

**Opções:** Para cada item, (a) manter como está ou (b) mudar o contrato.

**Decisão provisória (o código segue esta opção até o dono decidir):** Manter os quatro. `OcorrenciaAberta` tem `url_hash`, `ultima_vista_em` e `sumiu_em` (kw_only), e quem chama passa todas as ocorrências do escopo, inclusive as sumidas, senão `reviram` nunca dispara. `MudancasCiclo` devolve `url_hash` em tuplas (sumiram, reviram, tocar), sem id de ocorrência; a T19 resolve por (fonte, escopo). `vaga_fechada([])` devolve False. Em `sem_mudanca`, `tocar` só inclui ocorrências abertas e `reviram` fica vazio.

## D20. Encaixe da busca (T15)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** Com cidades preenchidas e modalidades vazias, vaga remota fora das cidades dá 0 no critério de local (`local_fora`, `src/jobot/nucleo/encaixe.py:93-97`): remoto só pontua com `REMOTO` nas modalidades (`:80`). Com cidades e modalidades vazias o critério é neutro (`:77-78`). O desenho (11.1) diz que critério vazio é neutro.

**Opções:** (a) modalidades vazio aceita remoto: com cidades escolhidas, vaga remota pontua `local_remoto` em vez de `local_fora`; (b) manter como está.

**Decisão:** Opção (a), que segue o desenho 11.1 (decisão 12 da sessão). Ainda não está no código da dev: entra no ajuste F2, com teste.

**Destino do que a T15 deixou em aberto (decisão 13):** as chaves `encaixe.*` nos catálogos de i18n (pt e en, e no `test_motivos_fixos_existem`) e o filtro "vaga aberta, não oculta e status nova" nas Candidatas e nos Destaques viram critérios da T45, porque `destaques()` não filtra isso (`src/jobot/nucleo/destaques.py:30`: "quem chama já entrega" só essas vagas). Os ids das regras de ocultar, a regra de local e modalidade, a regra de país e o idioma "outro" estão em `src/jobot/nucleo/dados/encaixe.json` e `src/jobot/nucleo/encaixe.py`; o que a T45 precisar deles, lê de lá.

## D21. Data de referência na leitura (T20)

**Status:** aberta, para confirmar

**Contexto:** `detalhe(..., agora: datetime | None = None)` lê o relógio da parede quando o valor padrão é usado (`src/jobot/banco/leitura.py:286-291`).

**Opções:** (a) manter o parâmetro opcional e a rota da T45 sempre passar `relogio.agora()`; (b) torná-lo obrigatório (keyword) e corrigir o plano.

**Decisão provisória (o código segue a opção (a) até o dono decidir):** o valor padrão, `datetime.now().astimezone()`, e o `listar` passam pelo mesmo `_hoje` no fuso local (`leitura.py:191-193`), então os selos não divergem. A recomendação do construtor é (b), na T45, porque o padrão esconde uma leitura do relógio da parede (e obrigatório mudaria a chamada de 3 argumentos do plano, um contrato). Segue aberto o filtro por motivo e por status em `Filtros` (`leitura.py:85-97`). Os candidatos da aba Destaques vão para a T45 (decisão 13, ver D20).

## D22. App do painel (T26)

**Status:** aberta, para confirmar

**Contexto:** O `abrir()` usa `check_same_thread=True`, e o 500 não tratado sai sem CSP e sem `nosniff`, porque o handler de `Exception` fica por fora do middleware de cabeçalhos.

**Opções:** Conexão: (a) rota que recebe `Con` é `async def`, e quem precisa do banco fora da rota abre conexão curta; (b) trocar de thread no `abrir()`. 500: (a) deixar como está (o corpo é texto puro, risco baixo); (b) `try/except` em volta do `seguinte(request)`, com `logging.exception` para não perder o traceback.

**Decisão provisória (o código segue esta opção até o dono decidir):** Rota `async def` com conexão curta fora dela, e o 500 como está (a nos dois). É o que o código do construtor já faz (rota `async def`, `abrir()` sem `check_same_thread=False`); a sessão registra para confirmar. O relatório da T26 cita uma recomendação "(b)" sem defini-la, por isso ela não foi atribuída a nenhuma opção.

## D23. Abrir e sair do programa (T43, T48)

**Status:** aberta, para confirmar

**Contexto:** A T43 decide como o comando sabe se o servidor local é o joBot e o que diz no terminal.

**Opções:** `e_o_jobot`: (a) HTTP 200 e JSON objeto com `app == 'jobot'` em `/saude-local`; (b) só a porta aberta. Trava: (a) `serve` pega a `Trava` antes do uvicorn e tenta de novo após ~50 ms; (b) sobe o uvicorn primeiro. Mensagens de terminal: (a) texto fixo em português, fora do i18n; (b) catálogo de terminal agora.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opções (a). O `serve` registra no log a porta ocupada. As mensagens de abrir e sair (inclui "Não consegui concluir o comando: <erro>") ficam em português, até existir um catálogo de terminal.

## D24. Segundo plano no Linux (T44, T53)

**Status:** aberta, para confirmar

**Contexto:** A T44 liga o joBot em segundo plano pelo systemd do usuário. A tela de configurações (T53) mostra as mensagens.

**Opções:** Chaves de i18n: (a) `segundo_plano.sem_host_exec`, `.systemd_nao_responde`, `.home_diferente` e `.systemctl_falhou` (parâmetros `comando` e `saida`); (b) mensagem única. Atalho `.desktop`: (a) sem `--no-tty` (desenho 12.5), com `--no-tty` em `ExecStart` e `ExecStop`; (b) com `--no-tty` também no atalho `.desktop`, além do `ExecStart` e do `ExecStop`. Desligar: (a) recusa só se o `disable` falha e o arquivo do serviço existe; (b) recusa sempre que o `disable` falha.

**Decisão provisória (o código segue as opções (a) até o dono decidir):** o `--no-tty` entra por parâmetro, `sem_terminal` (`src/jobot/sistema/segundo_plano_linux.py:107-112`): o serviço usa `sem_terminal=True` (`:117`) e o atalho `.desktop`, `False` (`:140`). Efeito de (a) em desligar: com `systemctl` sempre falhando e o arquivo do serviço presente, a pessoa não limpa pela CLI.

## D25. Referrer do painel e o CSRF (T36)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** O desenho 14.2 manda `Referrer-Policy: no-referrer` (`src/jobot/painel/app.py:25`). Com ele, o Chromium manda `Origin: null` no POST de formulário sem JS, e o `exigir_csrf` responde 403 (`src/jobot/painel/seguranca.py:80-83`).

**Opções:** (1) manter o `<meta name="referrer" content="same-origin">` no `base.html` (linha 10) como exceção anotada ao cabeçalho; (2) aceitar `Origin: null` com `Sec-Fetch-Site: same-origin`; (3) trocar o cabeçalho para `same-origin`.

**Decisão:** Opção (1), decisão 7 da sessão. O token CSRF continua obrigatório. O `meta` manda a origem certa ao próprio painel e nada para fora.

## D26. Salário que não cabe no banco (T19)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** O SQLite só guarda inteiro de até 2**63-1; acima disso o `sqlite3` levanta `OverflowError` ao ligar o valor e a gravação do escopo inteiro quebra. Um texto de salário absurdo (ou um por hora, multiplicado por 160 no cálculo mensal) chega a isso. As colunas inteiras de salário são `sal_min`, `sal_max`, `sal_mensal_min` (centavos), `sal_mensal_min_brl` e `sal_mensal_max_brl` (`src/jobot/banco/migracoes/0001_inicial.sql:71-74`); as `_brl` são gravadas pela T25 (`aplicar_cotacoes`) e valem centavos ÷ 100 vezes a cotação, então nunca estouram quando o original cabe.

**Opções:** (a) gravar a vaga sem salário (colunas nulas) quando qualquer valor não cabe; (b) recusar a vaga.

**Decisão:** Opção (a) (decisão 11 da sessão): perder a vaga por causa de um número de salário é pior do que ficar sem o salário. A regra vale para toda coluna inteira que a T19 grava, não só para o valor lido: se `sal_min`, `sal_max` ou `sal_mensal_min` passa de 2**63-1, `sal_moeda`, `sal_min`, `sal_max`, `sal_periodo`, `sal_mensal_min` e `sal_plausivel` ficam nulos e `sal_texto` fica (escolha do redator, para confirmar); as `_brl` herdam o nulo na T25. Entrou no plano, na T19, com `test_salario_gigante_nao_quebra_gravacao`, que leva também um caso por hora em que o original cabe e o mensal estoura.
