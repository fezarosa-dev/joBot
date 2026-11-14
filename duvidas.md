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

**Status:** aberta, para confirmar (o registro vem de uma passada anterior e não consta nas decisões da sessão; o código segue a opção atual até o dono decidir)

**Contexto:** A T01 montou o pyproject, o CI e o Dependabot.

**Decisão provisória:** Backend de build `uv_build`. O Dependabot do `uv` aponta para a `dev` (`target-branch`), o que só se confirma depois do primeiro push. O CI de tela sai com código 5 enquanto não houver teste de tela (a T36 cria o primeiro).

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

**Decisão:** Opção (a). A tela já volta com o valor corrigido, sem esperar a próxima busca. Para a T46 reprocessar uma vaga só, a T19 ganha `reprocessar_vaga` nas Interfaces, com `test_reprocessar_vaga_aplica_correcao`, e a T19 entra no `depende_de` da T46 (decisão 8 da sessão). Em 2026-11-14 as decisões 17, 18 e 23 completaram isso (D29): a assinatura é `reprocessar_vaga(con, vaga_id: int, *, hoje: date) -> None`, que também recalcula as colunas `sal_*` e as `_brl` da vaga, e a rota de correção recalcula ainda o encaixe e o `oculta_motivo` daquela vaga nas buscas ativas. Os critérios entraram no plano: `test_correcao_vence_regra_no_reprocesso` (T19), a correção valendo depois do reprocessamento das buscas salvas e do encaixe (T24) e `test_corrigir_aplica_na_hora` (T46). A docstring de `corrigir()` cita a decisão (ajuste F2). A ocorrência de `ultima_vista_em` mais recente, aberta de preferência (`test_reprocessar_vaga_usa_ocorrencia_aberta_mais_recente`), foi confirmada pela decisão 18. Escolha do redator, para confirmar (D29): `reprocessar_vaga` e `aplicar_cotacoes` saem numa transação só (o `reprocessar_vaga` abre a `BEGIN IMMEDIATE`, e o `aplicar_cotacoes`, que só abre uma quando não há e faz o `commit` no fim, entra nela: `src/jobot/banco/cotacoes.py`, `aplicar_cotacoes`); o que fica em transação separada é o `recalcular_encaixe`, que a rota de correção chama depois, então uma falha entre os dois deixa o encaixe velho até o próximo recálculo.

## D12. Ações da vaga (T21)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A T21 gravou as ações de status, ocultar e mostrar. O desenho não define alguns detalhes.

**Opções:** `valor_antigo` de uf, salário e outro: (a) NULL até existir a lógica desses campos; (b) inventar um "de" agora. `trazer_de_volta`: (a) zerar `oculta_manual`; (b) restaurar um -1 anterior. Estado esperado: (a) as ações levantam `LookupError` (vaga não existe) e `ValueError` (valor inválido); (b) toleram o que está fora do estado esperado. `_transacao`: (a) recusa conexão que já está numa transação; (b) aninha.

**Decisão:** `valor_antigo` fica NULL para uf, salário e outro até a lógica existir (T46/T24). `trazer_de_volta` zera `oculta_manual` sem restaurar um -1. `acoes.py` levanta `LookupError` e `ValueError`, que a T45 traduz em 404 e 422 e testa. `_transacao` recusa conexão que já está numa transação. O critério de 404 e 422 entrou no plano, na célula de testes da T45.

## D13. Cliente HTTP educado (T05)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A revisão da T05 deixou quatro escolhas para o dono. O Greenhouse (T27) precisa do 404 e o 4xx genérico virava `ErroDeRede` sem o status.

**Opções:** Status: (a) atributo `status: int | None` em `ErroDeRede`, sem mudar o Protocol; (b) exceção nova `NaoEncontrado`, que muda o contrato (R4). `para_no_429`: (a) só o 429; (b) 429 e 503. `ler_em_fluxo`: (a) segue gerador assíncrono, usado com `contextlib.aclosing`; (b) vira função que devolve o corpo. Redirecionamento e DNS: (a) recusar redirecionamento de host público para loopback, link-local, rede privada ou `localhost`, e deixar a resolução de DNS para IP privado fora da fase 1; (b) resolver o DNS e conferir o IP. URL vinda da fonte: (a) sem barreira; (b) recusar host local ao montar a `UrlListada`.

**Decisão:** `ErroDeRede` ganha `status: int | None` (a), já no código (`ErroDeRede.status`, em `src/jobot/nucleo/http.py`, repassado nos `raise ErroDeRede(..., status)` de `ClienteEducado._abrir`). `para_no_429` vale só para o 429; o 503 segue a regra do `Retry-After` mesmo nesse escopo (a) (o teste de `Parou429` em `ClienteEducado._abrir` só olha o 429). `ler_em_fluxo` segue gerador assíncrono com `aclosing` (a); o Protocol passa a anunciar `AsyncGenerator[bytes]` em vez de `AsyncIterator[bytes]` (`ler_em_fluxo` do Protocolo `HttpEducado`), para quem chama usar `aclosing` sem cast (decisão 9, ajuste F2). O redirecionamento de host público para endereço local ou privado é recusado com `ErroDeRede`, e loopback para loopback, como nos testes, segue (conferência de host em `_local` e recusa em `_conferir_salto`, em `src/jobot/nucleo/http.py`; testes `test_redirecionamento_de_host_publico_para_local_e_recusado` e `test_redirecionamento_dentro_do_host_local_segue` em `tests/unidade/test_http.py`). IPv6 que embute IPv4 (`::/96` sem `::` e `::1`, e `64:ff9b::/96`) passa pela mesma conferência (decisão 14, ajuste F2).

**Risco aceito (decisão 13):** DNS rebinding e redirecionamento entre dois hosts locais. Num 307 ou 308 para outra origem o corpo JSON ainda é repassado, como fazem o httpx e os navegadores. A resolução de DNS para IP privado, que a opção (a) deixava fora da fase 1, ganha uma defesa parcial no ajuste F3 (decisões 15 e 19): quando a origem é pública e o destino é um nome, o host é resolvido por um resolvedor injetável (padrão `asyncio.get_running_loop().getaddrinfo`) e o salto é recusado se algum endereço não for global, com `test_redirecionamento_para_nome_que_resolve_local_recusado` (sem rede). Fica aceito o rebinding entre a checagem e a conexão, porque fixar o IP exigiria um transporte próprio, e o redirecionamento entre dois hosts locais. A URL vinda da fonte deixa de ser risco aceito (decisão 19): a conferência de host local fica pública em `http.py` como `host_local`, e a `UrlListada` recusa URL de host local com `ValueError` (`test_url_listada_recusa_host_local`); no molde, o item que levanta `ValueError` é pulado e contado em `sem_detalhe_n`. O DR-19 do desenho vale só para "Adicionar site". As leituras do redator estão na D30.

**Risco em aberto, para confirmar:** a `VagaColetada.url` não passa pela conferência de host local (`_confere_http`, em `src/jobot/nucleo/modelo.py`, só a confere como http ou https). Nenhuma decisão da sessão aceitou esse risco. Recomendação: a mesma recusa da `UrlListada` na montagem da `VagaColetada` (cobre o caminho que não passa pela `UrlListada`), em tarefa própria, porque muda o contrato do modelo (R4).

## D14. Leitor de salário (T10)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A T10 leu salário em texto livre. Algumas escolhas foram do construtor.

**Opções:** Moeda sem faixa de plausibilidade: (a) conta como implausível; (b) conta como plausível. Faixas fora do BRL: (a) as do construtor; (b) o dono define. Benefícios: (a) chave ASCII (ex.: `retirement`); (b) texto original. `401k` logo depois de símbolo de moeda: (a) é valor; (b) é benefício. Texto de salário muito longo: (a) acima de 2.000 caracteres não é lido; (b) lê tudo. Faixa com períodos mistos (só um lado diz o período): (d2) quando o máximo passa de 10 vezes o mínimo, não forma faixa e fica só o valor que tem período; a fonte da sessão não detalha as outras opções. Benefício seguido de valor sem conectivo: (a) tira esse valor do salário; (b) mantém.

**Decisão:** As primeiras opções (a) dos cinco primeiros itens (decisão 4 da sessão). Texto acima de 2.000 caracteres devolve o mesmo que texto sem salário. Faixa com períodos mistos: (d2); a faixa normal (até 10 vezes) e a regra de plausibilidade do desenho 10.3 não mudam (decisão 10, ajuste F2). Salário com `Decimal(int)` direto, sem `str`, para int grande (ajuste F2). O último item (benefício seguido de valor sem conectivo) não consta nas decisões da sessão: o código segue a opção (a) até o dono confirmar.

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

**Contexto:** O SQLite só guarda inteiro de até 2**63-1; acima disso o `sqlite3` levanta `OverflowError` ao ligar o valor e a gravação do escopo inteiro quebra. Um texto de salário absurdo (ou um por hora, multiplicado por 160 no cálculo mensal) chega a isso. As colunas inteiras de salário são `sal_min`, `sal_max`, `sal_mensal_min` (centavos), `sal_mensal_min_brl` e `sal_mensal_max_brl` (`src/jobot/banco/migracoes/0001_inicial.sql:71-74`); as `_brl` são gravadas pela T25 (`aplicar_cotacoes`) e valem o valor mensal vezes a cotação. Elas podem estourar mesmo com o original gravado: o `sal_mensal_min` que a T19 confere vira `sal_mensal_min_brl` vezes a cotação, e o `sal_mensal_max_brl` parte de `sal_max` vezes o fator do período, que a T19 não confere.

**Opções:** (a) gravar a vaga sem salário (colunas nulas) quando qualquer valor não cabe; (b) recusar a vaga.

**Decisão:** Opção (a) (decisão 11 da sessão): perder a vaga por causa de um número de salário é pior do que ficar sem o salário. A regra vale para toda coluna inteira que a T19 grava, não só para o valor lido: se `sal_min`, `sal_max` ou `sal_mensal_min` passa de 2**63-1, `sal_moeda`, `sal_min`, `sal_max`, `sal_periodo`, `sal_mensal_min` e `sal_plausivel` ficam nulos e `sal_texto` fica (escolha do redator, para confirmar); a T25 grava nula só a coluna `_brl` cujo valor em centavos passa de 2**63-1 (decisão 17, `test_brl_gigante_fica_nulo`; D28). Entrou no plano, na T19, com `test_salario_gigante_nao_quebra_gravacao`, que leva também um caso por hora em que o original cabe e o mensal estoura.

## D27. Estados de `juntar_paginas` e a sentinela do 304 (T06, T07, T16)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A revisão da leva B achou lacunas no contrato do coletor: o 304 de uma página não tinha sentinela pública, o `LimiteAtingido` e o `ErroDeRede` sem nenhuma página lida viravam "parcial" com lista vazia, e o 304 misturado com 200 podia dar motivo `None`.

**Opções:** `ErroDeRede` com páginas lidas: (a) "parcial", com as vagas e o motivo; (b) sempre "falhou". 304 misturado com 200: (a) "parcial" com motivo novo; (b) "ok", ignorando o 304.

**Decisão:** Decisão 16 da sessão. `SEM_MUDANCA` é a sentinela pública do 304, e o coletor devolve exatamente `base.SEM_MUDANCA`, nunca uma cópia nem `()`. `ErroDeRede` e `LimiteAtingido` dão "falhou" sem página lida e "parcial" com uma ou mais (opção (a)). 304 misturado com 200 dá "parcial" com o motivo novo `saude.listagem_incompleta` (pt e en), nunca `None` (opção (a)). A T16 não trata motivo `None` de forma especial. Entrou no plano em T06, T07, T16 e no molde do coletor (`test_304` confere a sentinela por identidade).

## D28. `hoje` em quem chama a conversão e `_brl` gigante (T25, T41, T24, T54)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A cotação do PTAX vale 7 dias (`data >= hoje - 7`), mas quem chama a conversão não passava a data, e a `_brl` de um salário gigante estourava o INTEGER do SQLite.

**Opções:** `hoje`: (a) opcional na assinatura, obrigatório para quem chama por teste; (b) sem padrão (keyword-only obrigatório). `_brl` que não cabe: (a) coluna nula; (b) vaga sem nenhuma `_brl`.

**Decisão:** Decisão 17 da sessão. T41, T24 e T54 passam a data do `Relogio` para `aplicar_cotacoes` e `cotacao_mais_recente`, cada uma com o teste da validade de 7 dias. No F3: o `BEGIN IMMEDIATE` e o primeiro `SELECT` entram no try/rollback; `_PARA_MENSAL` e `_mensal` de `salario.py` e `_confere_http` de `modelo.py` ficam públicos; `_brl` que não cabe (acima de 2**63-1) é gravada nula, só a coluna que não cabe (a), com `test_brl_gigante_fica_nulo`; `aplicar_cotacoes` ganha o filtro `vaga_id`. Corrige a frase falsa da D26.

**Escolha do redator, para confirmar:** a decisão diz "`hoje` é obrigatório em quem chama". O código tem `hoje: date | None = None` (sem `hoje`, vale a cotação mais recente guardada, que serve a teste e ao `jobot buscar` antigo). O plano mantém a assinatura (a) e prende o "obrigatório" nos testes de quem chama. Tornar `hoje` keyword-only sem padrão muda uma assinatura pública e é R4: fica para o dono decidir.

## D29. "Aplica na hora" vale para todas as colunas derivadas (T19, T24, T46)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A D11 fazia a correção voltar com o valor novo, mas a rota de correção deixava o salário em reais e o encaixe por busca com o valor velho até a próxima busca.

**Opções:** (a) reprocessar a vaga e recalcular, na hora, `sal_*`, `_brl`, encaixe e `oculta_motivo`; (b) só as colunas lidas do texto.

**Decisão:** Decisão 18 da sessão, opção (a); `reprocessar_vaga` recebe `hoje` pela decisão 23. `reprocessar_vaga(con, vaga_id, *, hoje)` recalcula as colunas `sal_*` e as `_brl` com `aplicar_cotacoes(..., hoje=hoje, vaga_id=vaga_id)` (T19, depende também de T23 e T25). A rota de correção (T46) chama depois `recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)` (T24 ganha o filtro `vaga_id`). A ocorrência usada é a de `ultima_vista_em` mais recente, aberta de preferência.

**Escolhas do redator, para confirmar:** (1) a decisão escreve a chamada de `recalcular_encaixe` sem `hoje`, e a decisão 17 manda a T24 passar o dia: o plano põe `hoje` como keyword, pela 17. (2) `reprocessar_vaga` e `aplicar_cotacoes` ficam na mesma transação (`aplicar_cotacoes` só abre uma quando não há e fecha no fim), mas a rota chama `reprocessar_vaga` e `recalcular_encaixe` em transações separadas, então uma falha entre elas deixa o encaixe velho até o próximo recálculo. (3) com a conversão ligada, `aplicar_cotacoes` pula vaga fechada, então a correção de salário de uma vaga fechada não atualiza as `_brl` (a vaga não aparece na lista aberta; recomendação: aceitar). Com a conversão desligada o código zera as `_brl` de toda vaga em moeda estrangeira, fechada ou não: a T25 cobre os dois ramos em `test_vaga_fechada_pula_com_conversao_ligada_e_zera_com_desligada`.

## D30. Resolvedor de DNS e URL de host local (T05, T06, molde, T69, T73)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A D13 aceitava o risco de DNS rebinding inteiro e de URL local vinda da fonte. A revisão de segurança automática pediu uma defesa.

**Opções:** ver D13.

**Decisão:** Decisões 15 e 19 da sessão. Resolvedor injetável `host -> list[str]`, só em salto vindo de origem pública e para destino que é nome; falha do resolvedor vira `ErroDeRede`; `host_local(host: str) -> bool` público em `http.py`; `UrlListada` recusa host local com `ValueError`; item que levanta `ValueError` no molde é pulado e contado em `sem_detalhe_n`. Testes: `test_redirecionamento_para_nome_que_resolve_local_recusado`, `test_host_local`, `test_url_listada_recusa_host_local` e, em T69 e T73, `test_url_de_host_local_e_pulada_e_contada`.

**Escolhas do redator, para confirmar:** (1) a decisão escreve `HttpEducado(..., resolver=None)`, mas `HttpEducado` é o Protocol e quem tem construtor é `ClienteEducado`: o parâmetro entra em `ClienteEducado` e o Protocol não muda. (2) Como a contagem do item pulado chega ao executor fica com o construtor: campo novo em `ResultadoEscopo` seria R4. (3) Fica aceito o rebinding entre a checagem e a conexão e o redirecionamento entre dois hosts locais.

## D31. ADR 0018: manutenção pela comunidade, vigia, `jobot atualizar` e link "reportar problema" (T50, T83, T84, T85, T01)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** O dono quer divulgar o joBot para muita gente e que a comunidade ajude a manter os coletores. Em 2026-11-14 pediu que o vigia semanal e a atualização fácil, antes da fase 8, entrem já na fase 1, junto com o que deixar o projeto bom para a comunidade (ADR 0018, [0017](docs/decisions/0017-fases.md)).

**Opções:** o link da tela de fontes: (a) abre o modelo de issue com a chave da fonte e o motivo já preenchidos, só por clique; (b) o joBot abre a issue por conta própria (descartada: contraria a ADR 0014).

**Decisão:** Decisão 20 da sessão. ADR 0018 escrita e aceita; a fase 1 ganha T83 (guia), T84 (vigia) e T85 (`jobot atualizar`) e a T50 ganha o link e o modelo `fonte-quebrou.yml`. CI em todo PR (T01), sempre `pull_request`, nunca `pull_request_target`, token só de leitura e sem segredo. O motivo do link é uma chave `saude.*` do conjunto fechado, sem `saude.excecao` e sem os contadores; os estados de limite de ritmo não geram o link; o vigia deixa de fora Eureca, Abler e Gupy.

**Escolhas do redator, para confirmar:**
- Link: `https://github.com/fezarosa-dev/joBot/issues/new?template=fonte-quebrou.yml&fonte=<chave>&motivo=<chave saude.*>`, com os campos `fonte` e `motivo` no modelo; o identificador de empresa entra na URL e o clique já o entrega ao GitHub, então a tela mostra ao lado do link a frase do que vai (opções: (a) identificador na URL com a frase na tela, o plano; (b) tirar o identificador do link e a pessoa o escreve no formulário; recomendação: (a)); o conjunto fechado mora em `src/jobot/nucleo/quebra.py` (`MOTIVOS_DE_QUEBRA`, `FORA_DO_LINK`, `link_reportar`), e a URL é montada com `urlencode`, com teste de identificador malicioso; em fonte por empresa a chave é `<fonte>/<identificador>`; o modelo é bilíngue num arquivo só, como os outros, com o rótulo `fonte-quebrada`.
- Vigia (T84): dia e hora (segunda às 06:23 UTC, fora da hora cheia), no máximo 5 pedidos por fonte (`VIGIA_MAX_PEDIDOS`), um escopo por fonte, `FONTES_FORA = {"eureca", "abler", "gupy"}`. O vigia chama o coletor direto, sem o executor da T16 (que pede `Historico` e banco), e captura a exceção do coletor como o executor faz ("falhou" com `saude.excecao`, só o nome do tipo). "Quebrou" é "falhou" ou "parcial" com `saude.formato_mudou`, "falhou" com `saude.excecao` e, só em fonte de escopo único, "ok com zero vagas" (opções: (a) zero vagas só no resumo; (b) abre issue em fonte de escopo único, que é o jeito comum de um parser quebrar sem erro; recomendação: (b)). Fonte de escopo único é a que devolve exatamente um escopo com um `ContextoColeta` vazio. `bloqueio`, `empresa_nao_encontrada`, `tempo_esgotado`, `erro_de_rede`, `resposta_grande`, `listagem_incompleta`, `zero_inesperado`, os contadores `parcial_n` e `sem_detalhe_n`, "ok com zero vagas" nas outras fontes, "no_limite", a fonte "não vigiada" e os motivos de limite de ritmo e orçamento só entram no resumo do job; cada chave `saude.*` está em exatamente uma de `ABRE_ISSUE` e `SO_RESUMO` (classificação com teste, T84). Uma issue por fonte, com o rótulo `fonte-quebrada` e a marca `<!-- vigia:<chave> -->`, atualizada (PATCH) e fechada quando a fonte volta. Só é do vigia a issue com a marca, o rótulo e o autor `github-actions[bot]`, e só conta o comentário escrito por esse autor: em repositório público qualquer pessoa escreve a marca, e a issue de pessoa nunca é tocada nem impede a do vigia; item da listagem com `pull_request` é ignorado. Quem fechou a issue se decide pelo ator do último evento `closed`, não pelo comentário `<!-- vigia:<chave>:voltou -->`, que fica para sempre: fechada pelo vigia, reabre se a fonte quebrar de novo; fechada por pessoa, não é reaberta, nem se abre outra, e ganha um só comentário `visto` depois de cada fechamento (recomendação do redator). Detalhe de fonte de sitemap: o vigia detalha no máximo `VIGIA_MAX_DETALHES = 2` `UrlListada` (escolha do redator), as de `atualizada_em` mais recente, dentro dos 5 pedidos, e o erro do `detalhar` segue o executor da T16: `Bloqueio`, `LimiteAtingido`, `OrcamentoGasto` e `Parou429` param os detalhes e viram o motivo deles (`saude.bloqueio`, `saude.limite_atingido`, `saude.orcamento`, `saude.parou_429`, todos só no resumo); `ErroDeRede` vira `saude.erro_de_rede`; outro erro pula aquela URL e vira `saude.excecao:<Tipo>`; o estado do escopo continua o do `coletar`, sem virar "falhou", e o erro do detalhe só vira o motivo quando o `coletar` não trouxe outro. **Detalhe quebrado, para confirmar com o dono:** na T69 (sitemap, escopo único) toda a leitura da vaga fica no `detalhar`, então, se o erro do detalhe só for ao resumo, o parser dela fica sem vigia. (a) Fica só no resumo. (b) Em fonte de escopo único, abre issue quando todos os detalhes tentados (`min(VIGIA_MAX_DETALHES, itens listados)`, sem nenhum parar por erro de parada) falham com erro comum (`saude.excecao`) ou devolvem `None` e nenhuma vaga sai; risco: issue falsa quando as 2 URLs mais recentes não têm título ou empresa. Recomendação: (b), porque o vigia existe para pegar parser quebrado e a T69 é justamente o caso em que o parser mora todo no `detalhar`; a issue falsa se resolve fechando-a, e a regra da issue fechada por pessoa impede que ela volte. O plano (T84) segue a (b). "Zero vagas" conta os itens que o `coletar` listou (`len(resultado.vagas)`, `VagaColetada` ou `UrlListada`), como o `listadas` do executor. Sem isso, o sexto pedido de uma fonte de sitemap daria `OrcamentoGasto` e uma issue falsa toda semana. A classificação compara só a chave antes do primeiro `:`, porque o motivo com parâmetro chega como `chave:valor` (`saude.excecao:KeyError`). O `schedule` só vale no ramo padrão, então o vigia só roda depois do merge na `main`, e o GitHub o desliga em repositório público sem atividade por 60 dias (limite conhecido, religa-se à mão); o token do GitHub só vai a `api.github.com`, por um cliente separado, e o `ClienteEducado` nunca manda `Authorization`; permissões `contents: read` e `issues: write`, sem segredo do repositório, nunca em PR; o corpo da issue não leva conteúdo de vaga. O rótulo `fonte-quebrada` precisa existir no repositório do GitHub.
- `saude.excecao` no vigia (T84), **para confirmar com o dono**: a decisão 20 tira `saude.excecao` só do link da T50 e não diz nada do vigia. Opções: (a) abre issue, com só o nome do tipo da exceção no corpo (o plano); (b) só entra no resumo do job. Recomendação: (a), porque exceção de parser (`KeyError`, `TypeError`) quando o site muda o JSON é a quebra mais comum, e em (b) ela não abriria issue nenhuma.
- Contexto fixo do vigia (T84), **para confirmar com o dono**: o vigia não tem banco nem buscas, então monta o `ContextoColeta` com `termos == ("developer",)`, `paises == ("BR",)` e a primeira empresa de cada fonte em `empresas.json`; fonte cujo `escopos` volta vazio fica "não vigiada" no resumo e nunca abre issue. Opções: (a) a primeira empresa de `empresas.json` e "não vigiada" quando falta (o plano: as fontes por empresa da leva B, sem empresa no arquivo até a T76, ficam "não vigiadas" até lá, e a IEL também, se a UF não sair desse contexto); (b) uma lista própria no `scripts/vigia.py`, com uma empresa por fonte, que cobre a leva B antes da T76 mas é um segundo lugar para manter. Recomendação: (a), com as fontes "não vigiadas" à vista no resumo de cada semana.
- Canal de instalação (T85), **ainda indeciso**: o plano assume dois canais, o clone do repositório e o `uv tool install`, porque os instaladores para o público são da fase 8. Opções: (a) suportar só esses dois e recusar com mensagem o resto (o que o plano faz); (b) esperar a fase 8 e só então fazer o comando. Recomendação: (a), com o aviso de que a fase 8 estende a lista.
- `jobot atualizar` (T85): detecta `clone_git` (`git pull --ff-only` e `uv sync --locked`), `uv_tool` (`uv tool upgrade`) ou desconhecida (recusa); recusa com mudança local ou branch divergente antes de tocar em qualquer coisa; para o segundo plano (`desligar`, T44) e o servidor (`sair_do_servidor` de `sistema/abrir.py`, o `sair` da T43, que acha o PID por `pid_do_servidor` e manda SIGTERM) antes e religa só o que estava ligado depois (`ligar`, ou `subir_servidor`), e tenta religar também se a atualização ou a parada falhar (sai com 1); as migrações rodam no próximo início; comandos sempre em lista, nunca `shell=True`. Para religar o servidor sem duplicar código, o `_subir_servidor` de `sistema/abrir.py` (T43) passa a público como `subir_servidor`, só com a troca do nome (Modify `sistema/abrir.py` e `tests/unidade/test_abrir.py` na T85).
- `laco_versao` (T85) abre a própria conexão com `abrir` de `banco/conexao.py` e a fecha ao sair: duas tarefas asyncio numa só `sqlite3.Connection` se cruzam nos `await` (o `commit` e o `rollback` de uma valem para a outra), e a T48 não dá conexão ao laço da agenda.
- Link "reportar problema" (T50): a base da URL é a constante `URL_REPOSITORIO` de `nucleo/quebra.py`. A mesma URL hoje só existe literal no user agent de `nucleo/http.py`, que é do F3; `test_url_do_repositorio_bate_com_o_user_agent` prende as duas. Fazer o `http.py` usar a constante fica para depois do F3, se o dono quiser.
- Aviso de versão no painel: uma checagem por dia à API de versões do GitHub (o pedido leva só o user agent fixo, que traz a versão do joBot, e o IP que todo pedido mostra; sem cookie, busca nem identificador), feita por uma tarefa asyncio própria que o `cli/servir.py` inicia (a agenda da T42 não tem gancho para isso; mexer nela seria escolha do dono) e com a etiqueta validada (até 32 caracteres e `re.fullmatch(r"v?[0-9]+\.[0-9]+\.[0-9]+", etiqueta)`, antes de qualquer `int()`), com o interruptor `aviso_versao_ligada`, que o plano deixa **desligado por padrão**, por causa da regra da ADR 0014 (os dados só saem do computador para os serviços que a pessoa ligar). A ADR 0018 cita a chamada e o que ela envia (só o user agent fixo). Opções para o dono: (a) desligado por padrão e a pessoa liga em Privacidade (o plano); (b) ligado por padrão, o que exige mudar a ADR 0014; (c) desligado e perguntar na primeira execução (tela nova). Recomendação: (a).
- Interruptor `aviso_versao_ligada`: a T54 é a dona (cria a chave, os textos e a gravação, como exceção à lista da 13.7) e a T85 só lê.
- Lista de serviços da ADR 0014, **para confirmar com o dono**: a 0014 diz que os dados só saem do computador para os serviços que a pessoa ligar e lista Anthropic, Google, Telegram, Jev e RunPod. O aviso de versão (T85), ligado pela pessoa, fala com o GitHub, que não está na lista. A frase do desenho "o único código que faz pedidos para fora é o `HttpEducado`" e a regra de `Authorization` das Global Constraints já ganharam a ressalva do vigia, que é script de CI, fora do joBot instalado. Opções: (a) acrescentar à 0014 o GitHub, para o aviso de versão, na lista de serviços que a pessoa liga; (b) deixar a 0014 como está e valer a exceção registrada na 0018. Recomendação: (a), para a 0014 continuar sendo a lista completa.
- O guia (T83) sai depois da T17, da T27, da T50 e da T84, que ele cita (D34), e a aprovação do primeiro PR é do dono (D33). A T84 deixou de depender da T17: o vigia não usa o script de captura.

## D32. `tratar` chama `ler_requisitos` em toda vaga (T18)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A leitura de requisitos de estágio (T12) roda no `tratar` para vaga de qualquer área, não só para as que dizem ser de estágio.

**Opções:** (a) chamar em toda vaga e guardar `None` quando não há achado; (b) chamar só quando o título ou o contrato indicam estágio.

**Decisão:** Decisão 21 da sessão, opção (a): fica como está no código (`src/jobot/nucleo/tratamento/tratar.py:33`). Entrou no plano, na T18, com `test_tratar_chama_ler_requisitos_em_toda_vaga`.

## D33. Aprovação do primeiro PR de quem nunca contribuiu (ADR 0018)

**Status:** aberta, para confirmar com o dono

**Contexto:** A ADR 0018 põe o CI em todo PR, inclusive de fork. O GitHub tem uma configuração que segura o primeiro PR de quem nunca contribuiu até o dono aprovar a execução. Ela não está no repositório.

**Opções:** (a) deixar ligada: o primeiro PR de cada pessoa espera o ok do dono, e é a principal trava contra abuso de minutos; (b) desligar: PR de qualquer pessoa roda na hora.

**Recomendação:** (a). O dono confere em Settings > Actions > General > Fork pull request workflows, na tela do GitHub, antes de divulgar o projeto.

## D34. O guia de conserto só depois da T17, da T27, da T50 e da T84 (ADR 0018)

**Status:** aberta, para confirmar com o dono

**Contexto:** O guia "Como consertar uma fonte que quebrou" (T83) usa o script de captura (T17) e o Greenhouse (T27) como exemplo real, e cita o link "reportar problema" (T50) e a issue do vigia (T84), então só pode ser escrito depois deles. No plano ele está na onda 8, com `depende_de: T17, T27, T50, T84`.

**Opções:** (a) escrever o guia depois da T17, da T27, da T50 e da T84, com comandos e exemplo reais e só com recursos que já existem (o plano); (b) escrever antes, com exemplo inventado, e corrigir depois.

**Recomendação:** (a). Até lá, o guia de contribuição segue como está: PR de código só entra depois da fase 8.
