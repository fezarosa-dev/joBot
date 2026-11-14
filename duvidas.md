# Dúvidas

Decisões que dependem do dono do projeto. As resolvidas ficam registradas aqui, com a data.

Status usados: **resolvida** (o dono decidiu); **decidido pela sessão, para confirmar** (a sessão de 2026-11-13, ou a de 2026-11-14 com o dono fora, escolheu e o dono confere); **aberta, para confirmar** (o construtor só recomendou ou escolheu no código; o código segue a opção atual até o dono decidir).

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

**Status:** o arquivo já existe no repositório (ver a atualização de 2026-11-14); aberta só para o dono confirmar a conta

**Contexto:** o arquivo `.github/FUNDING.yml` mostra o botão Sponsor, mas precisa de uma conta de patrocínio, como GitHub Sponsors ou Ko-fi, que o projeto ainda não tem.

**Decisão provisória:** sem `FUNDING.yml` até o dono criar a conta e dizer qual usar.

**Atualização de 2026-11-14 (REG12):** o `.github/FUNDING.yml` já existe no repositório. Ele aponta para o Buy Me a Coffee e para a página Apoie da wiki (`custom`), então a escolha não foi GitHub Sponsors nem Ko-fi. A decisão provisória acima está desatualizada. Falta só o dono confirmar que a conta é a que ele quer. Status: o arquivo existe; a conta fica para o dono confirmar.

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

**Decisão:** Opção (a). A tela já volta com o valor corrigido, sem esperar a próxima busca. Para a T46 reprocessar uma vaga só, a T19 ganha `reprocessar_vaga` nas Interfaces, com `test_reprocessar_vaga_aplica_correcao`, e a T19 entra no `depende_de` da T46 (decisão 8 da sessão). Em 2026-11-14 as decisões 17, 18 e 23 completaram isso (D29): a assinatura é `reprocessar_vaga(con, vaga_id: int, *, hoje: date) -> None`, que também recalcula as colunas `sal_*` e as `_brl` da vaga, e a rota de correção recalcula ainda o encaixe e o `oculta_motivo` daquela vaga nas buscas ativas. Os critérios entraram no plano: `test_correcao_vence_regra_no_reprocesso` (T19), a correção valendo depois do reprocessamento das buscas salvas e do encaixe (T24) e `test_corrigir_aplica_na_hora` (T46). A docstring de `corrigir()` cita a decisão (ajuste F2). A ocorrência de `ultima_vista_em` mais recente, aberta de preferência (`test_reprocessar_vaga_usa_ocorrencia_aberta_mais_recente`), foi confirmada pela decisão 18. Escolha do redator, para confirmar (D29): `reprocessar_vaga` e `aplicar_cotacoes` saem numa transação só (o `reprocessar_vaga` abre a `BEGIN IMMEDIATE`, e o `aplicar_cotacoes`, que só abre uma quando não há e faz o `commit` no fim, entra nela: `src/jobot/banco/cotacoes.py`, `aplicar_cotacoes`); o que fica em transação separada é o `recalcular_encaixe`, que a rota de correção chama depois, então uma falha entre os dois deixa o encaixe velho até o próximo recálculo.

## D12. Ações da vaga (T21)

**Status:** decidido pela sessão em 2026-11-13, para confirmar

**Contexto:** A T21 gravou as ações de status, ocultar e mostrar. O desenho não define alguns detalhes.

**Opções:** `valor_antigo` de uf, salário e outro: (a) NULL até existir a lógica desses campos; (b) inventar um "de" agora. `trazer_de_volta`: (a) zerar `oculta_manual`; (b) restaurar um -1 anterior. Estado esperado: (a) as ações levantam `LookupError` (vaga não existe) e `ValueError` (valor inválido); (b) toleram o que está fora do estado esperado. `_transacao`: (a) recusa conexão que já está numa transação; (b) aninha.

**Decisão:** `valor_antigo` fica NULL para uf, salário e outro até a lógica existir (T46/T24). `trazer_de_volta` zera `oculta_manual` sem restaurar um -1. `acoes.py` levanta `LookupError` e `ValueError`, que a T45 traduz em 404 e 422 e testa. `_transacao` recusa conexão que já está numa transação. O critério de 404 e 422 entrou no plano, na célula de testes da T45.

**Ver também:** D40 (`POST /mostrar` em vaga que já está visível).

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

**Decisão:** Opção (a) (decisão 11 da sessão): perder a vaga por causa de um número de salário é pior do que ficar sem o salário. A regra vale para toda coluna inteira que a T19 grava, não só para o valor lido: se `sal_min`, `sal_max` ou `sal_mensal_min` passa de 2**63-1, `sal_moeda`, `sal_min`, `sal_max`, `sal_periodo`, `sal_mensal_min` e `sal_plausivel` ficam nulos e `sal_texto` fica (escolha do redator, para confirmar); a T25 grava nula só a coluna `_brl` cujo valor em reais inteiros passa de 2**63-1 (corrigido por D41: a decisão dizia "em centavos", mas as `_brl` guardam reais; decisão 17, `test_brl_gigante_fica_nulo`; D28). Entrou no plano, na T19, com `test_salario_gigante_nao_quebra_gravacao`, que leva também um caso por hora em que o original cabe e o mensal estoura.

## D27. Estados de `juntar_paginas` e a sentinela do 304 (T06, T07, T16)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A revisão da leva B achou lacunas no contrato do coletor: o 304 de uma página não tinha sentinela pública, o `LimiteAtingido` e o `ErroDeRede` sem nenhuma página lida viravam "parcial" com lista vazia, e o 304 misturado com 200 podia dar motivo `None`.

**Opções:** `ErroDeRede` com páginas lidas: (a) "parcial", com as vagas e o motivo; (b) sempre "falhou". 304 misturado com 200: (a) "parcial" com motivo novo; (b) "ok", ignorando o 304.

**Decisão:** Decisão 16 da sessão. `SEM_MUDANCA` é a sentinela pública do 304, e o coletor devolve exatamente `base.SEM_MUDANCA`, nunca uma cópia nem `()`. `ErroDeRede` e `LimiteAtingido` dão "falhou" sem página lida e "parcial" com uma ou mais (opção (a)). 304 misturado com 200 dá "parcial" com o motivo novo `saude.listagem_incompleta` (pt e en), nunca `None` (opção (a)). A T16 não trata motivo `None` de forma especial. Entrou no plano em T06, T07, T16 e no molde do coletor (`test_304` confere a sentinela por identidade).

**Ver também:** D41 (o docstring de `juntar_paginas` passou a dizer que só o que tem mais de 30 dias se fecha) e D35 (como o executor traduz o erro em motivo).

## D28. `hoje` em quem chama a conversão e `_brl` gigante (T25, T41, T24, T54)

**Status:** decidido pela sessão em 2026-11-14, para confirmar

**Contexto:** A cotação do PTAX vale 7 dias (`data >= hoje - 7`), mas quem chama a conversão não passava a data, e a `_brl` de um salário gigante estourava o INTEGER do SQLite.

**Opções:** `hoje`: (a) opcional na assinatura, obrigatório para quem chama por teste; (b) sem padrão (keyword-only obrigatório). `_brl` que não cabe: (a) coluna nula; (b) vaga sem nenhuma `_brl`.

**Decisão:** Decisão 17 da sessão. T41, T24 e T54 passam a data do `Relogio` para `aplicar_cotacoes` e `cotacao_mais_recente`, cada uma com o teste da validade de 7 dias. No F3: o `BEGIN IMMEDIATE` e o primeiro `SELECT` entram no try/rollback; `_PARA_MENSAL` e `_mensal` de `salario.py` e `_confere_http` de `modelo.py` ficam públicos; `_brl` que não cabe (acima de 2**63-1) é gravada nula, só a coluna que não cabe (a), com `test_brl_gigante_fica_nulo`; `aplicar_cotacoes` ganha o filtro `vaga_id`. Corrige a frase falsa da D26.

**Escolha do redator, para confirmar:** a decisão diz "`hoje` é obrigatório em quem chama". O código tem `hoje: date | None = None` (sem `hoje`, vale a cotação mais recente guardada, que serve a teste e ao `jobot buscar` antigo). O plano mantém a assinatura (a) e prende o "obrigatório" nos testes de quem chama. Tornar `hoje` keyword-only sem padrão muda uma assinatura pública e é R4: fica para o dono decidir.

**Ver também:** D41 (`_brl` gigante: as colunas guardam reais inteiros, e a dúvida sobre `sal_cotacao_data`; a D26 foi corrigida por ela) e D38 (dia local e transação).

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

**Ver também:** D41 (resolvedor que falha, resposta vazia e a guarda de rede dos testes).

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
- Vigia (T84) na leva J, decidido pela sessão em 2026-11-14 com o dono fora, para confirmar (D63): roda junto dos coletores T56–T65 e da REG7, com os valores já escritos aqui (segunda às 06:23 UTC, no máximo 5 pedidos por fonte, `FONTES_FORA = {"eureca", "abler", "gupy"}`) e com as opções em aberto acima (zero vagas, `saude.excecao`, detalhe quebrado, contexto fixo) seguindo a recomendação de cada uma. O link "reportar problema" e o aviso de versão (T50, T85, T87) já estão entregues.
- Vigia entregue pela T84 (leva J, juntada na `dev` em 2026-11-14), com os valores do plano: segunda às 06:23 UTC (`vigia.yml`), `VIGIA_MAX_PEDIDOS = 5`, `VIGIA_MAX_DETALHES = 2`, `FONTES_FORA = {"eureca", "abler", "gupy"}`. Seguem abertas, para o dono confirmar: o critério de "voltou" (`_voltou` em `scripts/vigia.py`: só pede estado ok, sem mudança ou parcial, e fonte sem quebra; a issue aberta por detalhe quebrado pode fechar como "voltou" quando o detalhe parou por orçamento ou bloqueio, o que a T121 corrige); o teto de 10 páginas da listagem de issues do GitHub (`MAX_PAGINAS_API`); o `timeout-minutes: 180` do fluxo; e o rótulo `fonte-quebrada`, que a pessoa cria no repositório do GitHub. O vigia só roda depois do merge na `main`. Os nomes privados do executor que `scripts/vigia.py` importa ficam para a T106 (D78).

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

**Atualização de 2026-11-14 (T83, leva L):** a seção 7 do guia `docs/consertar-fonte.md` (e de `docs/consertar-fonte.en.md`, linha 117 dos dois) diz que o primeiro PR de quem nunca contribuiu pode esperar o mantenedor liberar a execução dos testes. Se o dono escolher a opção (b), essa frase sai dos dois guias, numa edição só de texto.

## D34. O guia de conserto só depois da T17, da T27, da T50 e da T84 (ADR 0018)

**Status:** aberta, para confirmar com o dono

**Contexto:** O guia "Como consertar uma fonte que quebrou" (T83) usa o script de captura (T17) e o Greenhouse (T27) como exemplo real, e cita o link "reportar problema" (T50) e a issue do vigia (T84), então só pode ser escrito depois deles. No plano ele está na onda 8, com `depende_de: T17, T27, T50, T84`.

**Opções:** (a) escrever o guia depois da T17, da T27, da T50 e da T84, com comandos e exemplo reais e só com recursos que já existem (o plano); (b) escrever antes, com exemplo inventado, e corrigir depois.

**Recomendação:** (a). Até lá, o guia de contribuição segue como está: PR de código só entra depois da fase 8.


## D35. Executor: motivo do escopo, erro do detalhar e parada da fonte (T16, F3, molde do coletor)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T16 escolheu, sem o desenho dizer, como o executor traduz erro em motivo de saúde. As chaves de i18n já existem: `Bloqueio` vira `saude.bloqueio`, `LimiteAtingido` vira `saude.limite_atingido`, `OrcamentoGasto` vira `saude.orcamento`, `Parou429` vira `saude.parou_429`, `ErroDeRede` vira `saude.erro_de_rede`, `RespostaGrande` vira `saude.resposta_grande` e o resto vira `saude.excecao:<Tipo>`. A ordem de prioridade é: o motivo do coletor, depois `zero_inesperado`, depois o erro do detalhe e por último `sem_detalhe_n`. Quem consome isso é o vigia (T84, que copia a regra) e a tela de fontes (T50).

**Opções:**
- Erro no `detalhar` mostrado no motivo do escopo (o estado fica "ok", porque a lista veio inteira, como no `sem_detalhe_n`): (a) mostrar todo erro, como está; (b) mostrar só os de parada e `saude.excecao`, deixando o `ErroDeRede` calado. Risco da (a): um único 404 numa URL velha do sitemap mostra `saude.erro_de_rede` em toda execução, porque a URL volta como nova.
- Erro de parada no `detalhar` (`Bloqueio`, `LimiteAtingido`, `OrcamentoGasto`, `Parou429`): (a) para os detalhes da fonte inteira nesta execução, porque é o mesmo host (o próximo escopo não detalha nada e o motivo dele fica `None`; o motivo aparece só no escopo onde aconteceu); (b) para só o escopo.

**Decisão provisória:** (a) nas duas, porque ficar calado quando nenhuma vaga entra é pior (ADR 0004 e a lição da revisão) e porque o comentário original já dizia "a fonte inteira".

**Escolhas do redator, para confirmar com o dono:**
- Todo erro do `Historico` sobe num `ExceptionGroup` com o erro original, como o do `ao_terminar_escopo`. Antes, os erros de `urls_conhecidas`, `detalhe_recente` e `tres_ultimas_ok_trouxeram_vagas` viravam "falhou"; os que já ficavam fora do try (`ultima_coleta`, `ultimo_inicio_com_pedido` e `tem_ocorrencia_aberta`) continuam subindo. Está no docstring e nos 4 parâmetros de teste.
- Se o coletor puser `saude.sem_detalhe_n:<k>`, o executor soma `k` aos `None` do `detalhar`; um erro de detalhe vence esse motivo; `n` que não é inteiro dá `ValueError` e o escopo vira "falhou" com `saude.excecao:ValueError`. A contagem de item pulado no molde (`UrlListada` que levanta `ValueError`, D30) chega por esse mesmo motivo.
- O prazo (`tempo_esgotado`) usa o relógio de parede do `Relogio`: um pulo para frente (NTP ou suspensão) marca `tempo_esgotado` num escopo que terminou. Ficou o comentário `shortcut:` com a melhoria (relógio monotônico no `Relogio`, o que muda o contrato do `Relogio` e é R4). Recomendação: aceitar até aparecer o problema.
- Escopo que não detalhou nada porque o orçamento de detalhes da fonte acabou, ou porque outro escopo parou os detalhes, continua sem motivo (já era assim). Se a tela de fontes precisar mostrar isso, vira tarefa nova. Recomendação: deixar assim até a T50 pedir.

## D36. Captura de exemplos: limpeza de dado pessoal e alcance do script (T17)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O `scripts/capturar.py` guarda exemplos de resposta de fonte no repositório e limpa dado pessoal antes de gravar. Três escolhas ficaram abertas.

**Opções:**
- Portão de tipos: (a) pôr `scripts/` em `files` do mypy no `pyproject.toml`, para o portão pegar erro de tipo nos scripts; (b) deixar de fora. Mexer no `pyproject.toml` é R4.
- Campo sensível (`CAMPOS_SENSIVEIS`: cpf, telefone, phone, celular, whatsapp, email, e-mail): (a) só por nome exato da chave, como está (`phoneNumber` ou `user_email` não são pegos; registrado como `shortcut:` no docstring); (b) casamento por trecho do nome, com mais cobertura e mais risco de zerar campo inofensivo.
- Número codificado na URL (`phone=%2B5511987654321`) e marcadores `sms:`, `callto:` e `whatsapp://` sem `phone=`: (a) o detector acha o número codificado e a captura é recusada (falha fechado), e os outros três não são marcadores (documentado no docstring); (b) aceitar `(?:\+|%2B)?` na alternativa de marcador para limpar em vez de recusar.

**Decisão provisória:** a igual ao código atual, em todas: portão (a); campo sensível (a); URL codificada (a), isto é, a captura é recusada quando sobra o `%2B` (o detector o acha e o script não limpa). As outras entidades como separador de telefone (além de `&nbsp;`, `&#160;` e `&#xa0;`) seguem sem ser desfeitas antes da troca: o detector (que olha `html.unescape` e `unquote`) recusa a captura em vez de limpar.

**Recomendação:** para a URL codificada, a (b): aceitar `(?:\+|%2B)?` na alternativa de marcador, para o `%2B` ser limpo em vez de recusado. Para confirmar com o dono; hoje o código segue a (a).

**Para confirmar com o dono:**
- O meta de fonte lida em fluxo (sitemap) traz `ETag` e `Last-Modified`, mas não `Content-Type`, porque `ler_em_fluxo` (`src/jobot/nucleo/http.py`, F3) não expõe cabeçalhos. Recomendação: deixar assim até uma fonte precisar.
- Ficam como nota, sem decisão: o limite de 5 itens para lista auxiliar maior que a de vagas (`shortcut:`) e o telefone colado sem `+` e sem separadores, que continua fora (documentado).

## D37. Cadastros: país, área, etiqueta de banco de talentos e configuração (T23, T51, T54)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T23 criou `cadastros.py` e `empresas.json`. O apêndice (seção 7) não traz país da empresa, e a área vem como texto livre.

**Opções:**
- País (`empresas.json`): (a) manter `null` onde o apêndice não diz; (b) a sessão preenche à mão. Foi posto `BR` nas brasileiras óbvias (as 28 da Gupy, Greenhouse exceto Wellhub, Lever exceto Jeeves e Handoff, Netbr1 do SmartRecruiters), `US` em OpenAI e Zapier, e `null` em Wellhub, Jeeves, Handoff, Airwallex, Belvo, Supabase e nas outras 10 do SmartRecruiters. Não foi conferido na rede.
- Área: (a) texto livre do apêndice (ex.: `banco/finanças (investimentos)`), como está; (b) lista fechada, o que a T51 precisaria para filtrar por área.
- Etiqueta de banco de talentos do "Agibank (quadro de vagas futuras)": o nome ficou como no apêndice e a etiqueta que o apêndice cita fica para a tela da T51, sem campo novo no esquema (a T51 reconhece pelo nome, ou ganha um campo).
- Lista de fontes no registro: `semear` usa `carregar_fontes` com o caminho de `fontes.json` repetido em `cadastros.py`; (a) deixar assim; (b) `registro.py` ganha um `todas()` público (arquivo fechado).

**Decisão provisória:** país (a) até a T49 ou a T51 mostrarem se algum uso precisa dele; área (a) (se a T51 quiser filtro, a lista fechada é tarefa própria); etiqueta do Agibank: a T51 mostra pelo nome, sem campo novo; lista de fontes (a).

**Escolhas do redator, para confirmar com o dono:**
- `semear` atualiza `leva` e `intervalo_min` da tabela `fonte` a partir do arquivo a cada execução (o desenho diz que o intervalo é copiado) e nunca toca `ligada`. Se a T54 deixar a pessoa editar `intervalo_min`, a escolha seria sobrescrita; não há tal edição no plano. Recomendação: manter.
- `adicionar_empresa` de (fonte, identificador) já existente, removida ou não, vira a mesma linha, ativa de novo, com nome e `parametros` novos (área e país só se vierem; `origem` e `conferida_em` antigas ficam). Remover duas vezes mantém a primeira data; `ativar_empresa` em linha removida é permitido; `empresas()` traz as desligadas e não as removidas. As rotas T51 e T54 traduzem `LookupError` em 404 e `ValueError` em 422.
- `ler_config(con, chave)` sem `padrao` usa `PADROES` (seis interruptores `True` e `destaques_n` 10); chave fora de `PADROES` sem padrão dado levanta `KeyError`; JSON estragado na tabela cai no padrão. `segundo_plano`, `idioma` e `tema` ficam fora de `PADROES` de propósito. Chaves conferidas na 13.7 e no 7.7: `descoberta_cc_ligada`, `paginas_ligadas`, `enriquecimento_ligado`, `destaques_ligados`, `conversao_moeda_ligada`, `regras_ocultar_ligadas` e `destaques_n`.
- Os testes "desligada faz a função parar e sumir da tela" (critério 26, primeira metade) ficam nas tarefas que leem a chave (T41, T49, T54 etc.); a T23 só guarda e devolve os padrões.

## D38. Buscas salvas e conversão: dia local e transação (T24, T41, T46, T49, T52, T53, T54)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A D28 tornou `hoje` obrigatório em quem chama a conversão e o encaixe. A T24 acrescentou duas coisas que o desenho não dizia.

**Opções:** dia de referência: (a) `hoje = agora.astimezone().date()` (dia local do `Relogio`); (b) o dia em UTC. Transação: (a) cada módulo segue a sua convenção e a rota faz commit ou rollback antes de chamar; (b) uniformizar todos em `RuntimeError` como `acoes._transacao` (muda assinatura pública, R4).

**Decisão provisória:** (a) nas duas. `hoje` é obrigatório (R2) e `criar_busca` recebe `agora` e calcula o encaixe. A T41, a T46, a T49, a T52, a T53 (o passo 1 chama `criar_busca`) e a T54 passam `hoje = agora.astimezone().date()` e `agora` com fuso, com teste (entrou no plano como DP8 e nas tarefas citadas). `cotacoes.aplicar_cotacoes` e `buscas._escrita` juntam e confirmam a transação aberta do chamador, e `acoes._transacao` levanta `RuntimeError`; a rota faz commit ou rollback antes de chamar `buscas` ou `cotacoes`, e em erro o rollback desfaz também as escritas pendentes dela (lição em `registros/padroes.md`).

**Para confirmar com o dono:** o teste de corrida de `recalcular_encaixe` (`set_trace_callback` e `threading.Event`, vermelho ao trocar `BEGIN IMMEDIATE` por `pass`) não foi feito, por ser opcional na revisão. Recomendação: fazer, na T88.

## D39. Medição dos rótulos no gabarito (T37, T78)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T37 criou `avaliar-rotulos`, que mede o acerto das regras da T13 contra o gabarito (fora do repositório). O plano diz só "acerto por rótulo" e nomeia `avisos`.

**Opções:**
- Rótulos medidos: (a) os 7 que o código mede (`area`, `nivel`, `modalidade`, `contrato`, `avisos`, `pais`, `uf`); (b) só os que o plano nomeia. País e UF saem do primeiro `Local` da vaga tratada, e UF sem país vale `BR`, como em `rotular()` (há `shortcut:` no código sobre o primeiro local).
- Amostra: (a) só o que tem vaga e rótulo ao mesmo tempo, com a `proporcao_br` usando essa amostra no denominador (o plano diz "BR sobre o total rotulado"; com o exemplo dá o mesmo número); (b) todo rótulo, inclusive o sem vaga.
- Saída: caminho que existe mas sem `bruto/` ou sem `rotulos.jsonl`, linha JSON quebrada, rótulo obrigatório faltando ou amostra vazia saem com código 1 e uma linha em stderr; só caminho inexistente sai com 0 (DR-63).

**Decisão provisória:** (a) em todas, porque a T78 quer 90% por rótulo e a regra de UF é a mais frágil; o desenho não diz o que fazer nos outros casos de erro.

**Para confirmar com o dono:**
- R3: o subcomando ganhou `--relatorio <arquivo.md>` em `src/jobot/cli/__init__.py`, arquivo que não estava na lista da T37 (o parser só tinha `caminho`). É uma linha; se outra tarefa da leva mexer nesse arquivo, o conflito é trivial.
- Para a T78, sem ação agora: no gabarito de exemplo, "Contratação PJ" numa vaga sem local sai `nao_informado`, pois `pj` só vale para vaga no Brasil (D5). O exemplo guarda essa divergência de propósito (`g10`, contrato), e os testes não dependem dela.
- A calibração das regras de `rotulos.json` com o gabarito real e a geração de `docs/rotulos-medidos.md` seguem sendo da T78. Gabarito real com url fora de http/https aborta a medição com código 1 (arquivo e linha na mensagem); a T78 corrige a linha e roda de novo.

## D40. Tela de vagas: foco, "mostrar" e pendências baixas (T45, T46, T82)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T45 deixou três pontos para o dono e quatro pendências baixas da revisão.

**Opções:**
- Foco: (a) `.situacao`, `.lista` e `.vazio` com `:focus:not(:focus-visible)` no lugar de `outline: none`, igual ao padrão de `base.css` para `main` (o foco programático depois de ação por teclado fica visível; depois de clique de mouse continua sem contorno); (b) manter `outline: none`.
- `POST /mostrar` em vaga visível (`oculta_manual` 0 e sem motivo): (a) como está, grava `oculta_manual = -1` e o evento `mostrou` (decisão de desenho, D12 e DP2); (b) a rota responde sem efeito quando a vaga não está oculta.

**Decisão provisória:** foco (a) (já no código); `/mostrar`: o código segue a (a), e a recomendação é a (b).

**Para confirmar com o dono:** as pendências baixas viraram itens do plano: T46 (mover `_de_volta` para `seguranca.py`) e T82 (registrar os globais do Jinja em módulo explícito, junto do item do tema; teste de 422 por `ValueError` em `mostrar` e `ocultar`; teste de Tab real no lugar de `focus()` mais `Enter`). A rota `/mostrar` só muda se o dono escolher a (b).

**Resolvido (globais do Jinja):** os globais (`salario_texto`, `locais_texto`, `data_curta`, `data_completa`, `dinheiro`, `rotulo` e `motivo`) agora são registrados num só lugar, `registrar` em `src/jobot/painel/globais.py`, chamado em `src/jobot/painel/seguranca.py` logo depois de montar o `TEMPLATES`. Nenhuma rota registra global no import. O `tema` deixou de ser global e vai no contexto de `renderizar`. O teste é `test_globais_do_jinja_vem_do_modulo_explicito` em `tests/integracao/test_rota_preferencias.py`.

## D41. Guarda de rede dos testes e renomeações do F3 (F3, T05, T25)

**Status:** aberta, para confirmar (a guarda (b) foi entregue pela T88 em 2026-11-14; faltam a confirmação do `_brl`, do texto da decisão 19 e das escolhas do redator)

**Contexto:** O F3 trouxe o resolvedor de DNS (D30) e a conversão de `_brl` gigante (D28). Sobraram quatro pontos.

**Opções:**
- Guarda do `tests/conftest.py`: (a) só `socket.connect` (como está); (b) bloquear também `socket.getaddrinfo` fora de `127.0.0.1` e `::1`, o que torna permanente a garantia "sem DNS nos testes". É arquivo compartilhado, então ficou para a T88, entregue em 2026-11-14.
- `_brl` gigante: a decisão 17 fala em "valor em centavos acima de 2**63-1", mas as colunas `_brl` guardam reais inteiros. Foi seguido o que de fato estoura: o inteiro em reais gravado em cada coluna, quando passa do INTEGER do SQLite, fica `NULL` só naquela coluna. (a) `sal_cotacao_data` da vaga fica como está (`cotacoes.py`, o trecho que grava a data); (b) `sal_cotacao_data` também fica `NULL` quando as duas `_brl` saem nulas.
- Texto da decisão 19: o brief e o registro dizem `HttpEducado(..., resolver=None)`, mas a classe concreta é `ClienteEducado` (já em D30, escolha 1). Aqui só se acrescenta: o `resolver` entrou em `ClienteEducado.__init__`, só por nome e opcional.

**Decisão provisória:** guarda (b), entregue pela T88 em 2026-11-14: o `tests/conftest.py` bloqueia `socket.getaddrinfo` fora de `127.0.0.1` e `::1`, além de `socket.connect`, e o cliente que resolve nome nos testes recebe `resolver=` falso ou usa o IP literal; `_brl`: (a). A frase "em centavos" já foi corrigida na D26 e no plano (F3, decisão 17). O plano já diz `ClienteEducado`, e a D30 já explica a troca de nome. Para confirmar: corrigir o texto da decisão 19 no registro da sessão (fora deste repositório), que ainda diz `HttpEducado(..., resolver=None)`.

**Escolhas do redator, para confirmar com o dono:**
- Resolvedor que falha: `OSError` (`gaierror` incluso) e `UnicodeError` viram `ErroDeRede`; outra exceção que o resolvedor injetado levante sobe como está. Por segurança, e sem regra explícita no brief, o cliente também recusa a resposta do resolvedor vazia ou com texto que não é IP (`test_resolvedor_sem_endereco_valido_recusa`).
- Renomeações públicas (`confere_http`, `PARA_MENSAL`, `mensal`, `host_local`): na integração, procurar `_confere_http`, `_PARA_MENSAL` e `_mensal(` nos outros worktrees da leva. `registros/padroes.md` já cita o nome novo.
- Docstring de `juntar_paginas` (`base.py`): "nada se fecha" virou "só o que tem mais de 30 dias se fecha", para bater com o ciclo de vida (10.2). É só texto.

## D42. Correções da pessoa na vaga: formato do valor e efeito (T19, T46, T90)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T19 aplica as linhas de `correcao` por cima das regras, da mais velha para a mais nova (`_corrigir` em `src/jobot/banco/gravacao.py`). O desenho não diz em que formato a tela manda cada valor. Quem manda é a rota de correção da T46.

**Opções:**
- Formato do valor: (a) texto simples, como está; (b) um formato estruturado (JSON) para `salario` e `fechada`, decidido junto com a rota da T46.
- Correção `fechada` com valor negativo (`0`, `nao`, `não`, `false`, `no`): (a) só tira o fechamento forçado; se a fonte já tirou a vaga, ela continua fechada pelo ciclo de vida; (b) o negativo reabre a vaga mesmo sem ocorrência aberta.

**Decisão provisória:** (a) nas duas. A tela da T46 manda texto, e reabrir vaga que a fonte já tirou mostraria uma vaga que não existe mais.

**Provisório (o que o código faz hoje), para confirmar:**
- `salario`: texto livre, lido com `ler_salario`. Se o texto não traz moeda ("6.000 por mês"), vale a moeda que as regras leram. Valor vazio tira o salário. Valor que não dá para ler é ignorado.
- `uf`: duas letras, que viram a UF de todos os locais com país BR. Vaga sem local ganha um `Local(uf, BR)`.
- `area`, `nivel`, `modalidade` e `contrato`: só valor válido da lista fechada; o resto é ignorado.
- `fechada`: qualquer valor fecha a vaga, com `fechada_em` igual à data da correção, menos os negativos acima, que desfazem. Desfazer reabre a vaga na hora pelo `reprocessar_vaga`, mas só se ela ainda tem ocorrência aberta.
- `outro`: é só comentário, não muda nada.
- A rota de correção da T46 chama `recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)` logo depois de `reprocessar_vaga`, para atualizar `encaixe` e `oculta_motivo` (item fora do escopo da T19).
- A correção vale também em `gravar_escopo` e `gravar_detalhe`, não só no reprocesso. Sem isso, a próxima busca desfaria o valor corrigido (`test_correcao_vence_regra_no_reprocesso`).
- Os benefícios lidos da fonte (VR, VA) continuam quando a correção do salário não traz benefício, e também quando a correção vem vazia. Se a correção trouxer benefícios, eles substituem os da fonte.
- Quando o salário some, as colunas `sal_mensal_min_brl`, `sal_mensal_max_brl` e `sal_cotacao_data` também ficam nulas. Senão o valor em reais velho ficaria parado na vaga, porque `aplicar_cotacoes` só olha vaga com `sal_moeda`.
- Limite conhecido: para herdar a moeda, o código põe o código ISO na frente do texto. Moeda que o leitor de salário não reconhece no texto (por exemplo NZD, vinda do salário estruturado da fonte) cai na moeda do idioma; numa vaga em pt vira BRL. Resolvido pela T90 (entregue): a moeda herdada fica. Limite que sobra, marcado com `shortcut:` em `_corrigir`: quando a moeda herdada não está na lista do leitor, o salário corrigido sai com `plausivel=False`, e o período sem unidade escrita é deduzido pela faixa da moeda do idioma ("30" numa vaga NZD em pt vira hora pela faixa do BRL). O ajuste vem quando o leitor de salário aceitar moeda por parâmetro.

## D43. Gravação do escopo: validadores no 304 e outras escolhas (T19)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O desenho (`docs/superpowers/specs/2026-11-13-fase-1-design.md`, perto da linha 753) diz que os validadores (`ETag`, `Last-Modified`) são gravados "só quando o escopo termina ok". O teste do plano `test_304_toca_e_guarda_validadores` pede que eles fiquem guardados também no 304 (estado `sem_mudanca`).

**Opções:**
- (a) guardar em `ok` e em `sem_mudanca`, como está (`_GUARDA_VALIDADORES` em `gravacao.py`), e corrigir o texto do desenho; (b) guardar só em `ok`, como diz o desenho, e mudar o teste do plano.

**Decisão provisória:** (a). O `http.py` só devolve validador de resposta 200, então no `sem_mudanca` só entram os das páginas que vieram inteiras. `parcial`, `falhou`, `no_limite` e `desligada` não gravam nada. Falta alinhar a frase do desenho.

**Provisório (o que o código faz hoje), para confirmar:**
- `reprocessar(con, versao)` só mexe em vaga aberta e não chama `aplicar_cotacoes`. As colunas `_brl` ficam para o passo 5 da execução (T41), que já chama `aplicar_cotacoes`. A assinatura do plano não tem `hoje`, que a cotação precisa.
- `fechar_escopos_extintos` devolve quantas ocorrências marcou, não quantas vagas fecharam, e recusa `agora` sem fuso com `ValueError`.
- A `url` da vaga é gravada só na criação, com a URL canônica, e nunca mais trocada. `ocorrencia.url` guarda a URL como a fonte mandou.
- `gravar_detalhe` trata a vaga de novo, com correções e locais, herda a descrição antiga quando o detalhe chega vazio e só troca `id_externo` quando o novo não é nulo.
- Em escopo `falhou`, as vagas que vierem no resultado são gravadas, mas o ciclo de vida não muda nada. Na prática o executor manda a lista vazia quando falha.
- Continua aberta (D29): `aplicar_cotacoes` pula vaga fechada, então `reprocessar_vaga` numa vaga fechada não atualiza as `_brl`.

## D44. Execuções e saúde: forma das funções (T22, T41, T50, T51)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O plano deixou sem forma algumas funções de `src/jobot/banco/execucoes.py`. A T41 (execução), a T50 (tela de fontes) e a T51 dependem delas.

**Opções:**
- `HistoricoDoBanco`: (a) recebe `HistoricoDoBanco(con, relogio)`, como está, porque o `Historico` não passa `agora` e a janela de 30 dias do `detalhe_recente` precisa da hora atual; (b) recebe um `agora` fixo.
- `saude_recente(con, n=8)`: (a) devolve `tuple[LinhaSaude, ...]` com as linhas das `n` execuções mais recentes que gravaram saúde, da mais nova para a mais velha e depois por fonte e escopo, como está; (b) devolve agrupado por fonte, já pronto para os pontos da tela.

**Decisão provisória:** (a) nas duas. A T41 constrói com `HistoricoDoBanco(con, relogio)`. Se a forma não servir à tela de fontes, a T50 ajusta na própria tarefa.

**Provisório (o que o código faz hoje), para confirmar:**
- `gravar_saude` recebe campos soltos (execução, fonte, escopo, estado, vagas, pedidos, duração, motivo), sem `SaidaEscopo`, porque `desligada` e `no_limite` por intervalo não têm `SaidaEscopo`. Ela só confirma quando não há transação aberta, para a T19 chamá-la dentro da transação do escopo. As outras (`abrir_execucao`, `bater`, `fechar_execucao`, `marcar_interrompidas`) confirmam sozinhas e levantam `RuntimeError` com transação aberta, como `acoes.py`.
- `Andamento` (de `execucao_atual`) traz id, tipo, motivo, início, batimento e quantos escopos já gravaram saúde. Com mais de uma execução rodando, a busca vem primeiro.
- `ultima_coleta` usa o início da última execução em que o escopo teve saúde fora de `no_limite` e `desligada`. Assim o escopo que ficou no limite roda primeiro na próxima vez (DR-52). `falhou` conta como coletado.
- `tres_ultimas_ok_trouxeram_vagas` olha só as linhas com estado `ok` e exige três, todas com vagas.
- `fechar_execucao` não ressuscita execução já interrompida e levanta `LookupError` só para id que não existe. `bater` em execução encerrada não faz nada. `marcar_interrompidas` grava o fim igual ao último batimento.
- Pendência da T22: `detalhe_recente` em `src/jobot/banco/execucoes.py` chama `_data(buscado_em)` sem proteção; uma data malformada em `enriquecimento` derruba o escopo de sitemap inteiro. Opções: (a) tratar `ValueError` como "não recente" e ter um teste que fixa o formato gravado; (b) deixar falhar como hoje. Recomendação: (a).

## D45. Coletor Greenhouse: itens pulados, endereço colado e prazo (T27, T51, T54, T84)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O primeiro coletor (`src/jobot/nucleo/coletores/greenhouse.py`) deixou quatro pontos. O primeiro mexe no i18n compartilhado e no vigia, então é R4.

**Opções:**
- Motivo quando itens fora do formato são pulados (DR-08). O desenho (linha 688) e a DR-08 pedem o número de pulados no motivo, mas nenhuma chave `saude.*` com `n` fala disso (`saude.parcial_n` diz "lidas antes de parar"). (a) chave nova `saude.pulados_n` ("{n} vagas fora do formato foram puladas") em `comum.json`, e o vigia (T84) passa a tratá-la como quebra; (b) `saude.formato_mudou` sem contagem, como está; (c) parâmetro `n` na `saude.formato_mudou`.
- Caixa do identificador: o resolver devolve o token como veio (`Vitta` fica `Vitta`), e `escopos()` tira repetidos pelo texto exato. Então `Vitta` e `vitta` viram dois escopos e dois pedidos. (a) o resolver normaliza para minúsculas; (b) a rota de empresas (T51) normaliza para minúsculas; (c) a normalização é por fonte, no resolver de cada coletor, e a T51 nunca muda a caixa por conta própria. A (b) caiu: quebra a SmartRecruiters (a API diferencia maiúsculas e minúsculas, e o identificador `NielsenIQ` tem de ficar como está) e a Gupy (o `careerPageName` casa com a caixa exata).
- Prazo com hora e fuso (`application_deadline`): nenhuma captura real trouxe o campo. O código supõe ISO 8601 e usa o dia como está escrito, sem converter fuso. Então `2026-12-16T02:59:59Z` vira 16/12, mas em Brasília é 15/12. (a) converter para o dia local antes de pegar a data, com teste de entrada fora de UTC; (b) manter o dia escrito. A Himalayas (`expiryDate`, epoch em segundos) cai na mesma questão: o código usa o dia em UTC, e o epoch é um instante sem ambiguidade, então ali a (b) não existe, só o dia UTC (como está) ou o dia local (a). A Gupy traz data pura (`applicationDeadline` com meia-noite UTC), sem o problema.

**Decisão provisória:** pulados: todos os coletores da leva A seguiram a (b), marcada com `shortcut:` em `coletar`; a recomendação continua a (a), `saude.pulados_n` feita junto com o vigia (T84), porque `formato_mudou` é o que abre issue. Caixa: (c), por fonte, no resolver de cada coletor (a recomendação antiga, "a T51 normaliza para minúsculas", caiu); a T51 não muda a caixa. Prazo: Greenhouse e Himalayas seguem a (b) e o dia UTC, marcados com `shortcut:`; recomendação (a), o dia local, decidida junto para as duas, com teste de `TZ` fora de UTC. O comentário do `shortcut:` em `himalayas.py` diz "um dia antes", mas em UTC a vaga que vence à noite em Brasília aparece um dia depois (22h de 10/12 em Brasília é 01h de 11/12 em UTC); o comentário se corrige junto com a decisão.

**Coletores da leva B (leva J, 2026-11-14):** InHire, Quickin, Recrutei, Sólides, CIEE, IEL, Cia de Talentos, USP, Workday e Eightfold seguiram o `shortcut:` da (b): item pulado vira `saude.formato_mudou` sem contagem. A decisão não muda; as fontes entram na lista da D45 e saem junto quando a (a) for feita.

**Provisório (o que o código faz hoje), para confirmar:**
- O resolver devolve `{"identificador": token}`, sem fazer pedido, e levanta `ValueError` para o que não é quadro do Greenhouse. O desenho (8.1) diz que o resolver devolve `parametros`, mas o Greenhouse não tem parâmetros (8.6). Recomendação: a chave `identificador` vira convenção para todo resolver que normaliza o endereço colado, e a T51 e a T54 leem dela.
- O host europeu (`job-boards.eu.greenhouse.io`) é recusado pelo resolver. Segue em aberto no apêndice de fontes, seção 2.4.

**Coletores da leva L (2026-11-14):** Oracle HCM (`oracle_hcm.py:271`), Google (`google.py:165`), Amazon (`amazon.py:208`), Eureca (`eureca.py:182`) e Abler (`abler.py:481`) seguiram o `shortcut:` da (b): item pulado vira `saude.formato_mudou` sem contagem. A Super Estágios e a Abler contam à parte o que o sitemap trouxe fora do padrão, em `saude.sem_detalhe_n:<n>` (`super_estagios.py:271`, `abler.py:486`). A decisão não muda; as fontes entram na lista da D45 e saem junto quando a (a) for feita.

## D46. Tela de buscas: formato do formulário (T52)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T52 criou a tela de buscas salvas (`src/jobot/painel/rotas/buscas.py`). O desenho não diz como a pessoa digita cidades e salário.

**Opções:**
- Cidades: (a) texto livre, uma por linha, lido por `ler_locais` (`Curitiba, PR`, `Lisboa, Portugal`), como está; cidade sem UF nem país é recusada com mensagem (422); (b) campos separados de cidade, UF e país.
- Idioma `outro`: o tipo `Idioma` aceita `outro`, mas a tela só oferece pt, en e es. Uma busca com `outro` abriria na edição sem esse valor marcado e o perderia ao salvar. Hoje nenhuma tela grava `outro`. (a) deixar assim; (b) a edição preserva os valores que a tela não oferece.

**Decisão provisória:** (a) nas duas.

**Provisório (o que o código faz hoje), para confirmar:**
- Salário aceita `5000`, `5.000`, `5.000,50` e `5000,5` (ponto só no milhar, vírgula nos centavos, até 25 caracteres). `0`, `5000.5`, `5,000`, dígitos fora do ASCII e valor acima do INTEGER do SQLite dão 422 com mensagem. Em branco quer dizer sem mínimo e sem moeda.
- Moeda: BRL mais as 10 moedas de `MOEDAS` (`src/jobot/nucleo/cambio.py`).
- O seletor de busca na lista de vagas é uma fileira de links com cara de chip, não um `select`. Aparece só com duas buscas ou mais e mantém aba, texto, chips e ordem.
- Apagar pede confirmação em dois passos, sem JavaScript (um `<details>` com o botão "Apagar mesmo").
- As mensagens de erro saem numa só, no topo do formulário, não campo por campo.
- Edição em massa e reordenação de buscas ficam fora da fase 1, porque o desenho não pede e nenhuma tela da fase depende disso; volta se o dono pedir.

## D47. Menu da casca (T86, T53)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T86 pôs o menu principal na casca (`templates/base.html`), com seis itens: Vagas, Buscas, Fontes, Empresas, Sites e Configurações.

**Opções:**
- Links para telas que ainda não existem: (a) o menu mostra os seis itens desde já, e Fontes, Empresas, Sites e Configurações dão 404 até a T50, a T51, a T75 e a T54 entrarem; a fase não publica nada antes disso; (b) esconder cada item até a tela dele existir.
- Menu na primeira execução: em `/primeira-execucao` nenhum item fica marcado, e o menu aparece. (a) deixar assim; (b) esconder o menu durante a primeira execução, com um bloco Jinja no `base.html`.
- Barra do topo em tela estreita (até 40rem): (a) deixa de ser fixa ao rolar (`position: static` em `base.css`), para o menu quebrado em várias linhas não cobrir o conteúdo com zoom de 200%, como está; (b) continua fixa, só com a quebra de linha.

**Decisão provisória:** (a) nas três. A (a) da barra não foi pedida e nenhum teste de tela cobre a tela estreita; é fácil de tirar.

**Provisório (o que o código faz hoje), para confirmar:** o item Configurações aponta para `/configuracoes/fontes` e fica marcado em qualquer `/configuracoes/...`. A área de cada item casa o caminho inteiro ou seguido de `/` (`/vagasx` não marca Vagas), e `/` conta como Vagas.

## D48. Tratamento: cidades dos EUA, curso composto e salário (T82, T92, T78)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T82 fechou ajustes pequenos do tratamento. Algumas escolhas mudam o que a vaga mostra e dependem do gabarito (T78) para calibrar.

**Opções:**
- Cidade estrangeira sem país escrito: não dá para separar "Pittsburgh, PA" de "Belém, PA" sem lista. (a) lista curta de cidades dos EUA para as seis siglas que colidem (PA, MA, AL, SC, MS, MT), `_CIDADES_DOS_EUA` em `src/jobot/nucleo/tratamento/locais.py`: cidade da lista vira `Local(cidade, pais="US")`, as outras seguem UF do Brasil; (b) lista de cidades brasileiras, o que perderia vaga brasileira de cidade fora da lista.
- Curso composto: só vale com maiúscula depois do "e" e só em pt; "and" em inglês encerra o curso. Não há limite de tamanho, então "e" seguido de maiúscula que não é curso também entra (falso positivo fixado em teste de caracterização). (a) deixar assim até a T78; (b) valer também em inglês.
- Salário com `m` e `mi` como milhão: "5 m" solto passa a ser milhão, e "R$ 2.000 a 3.000 m/mês" lê o `m` como milhão. Barrar a barra quebraria "$1M/year". (a) deixar assim até a T78; (b) um caso específico para "/mês".

**Decisão provisória:** (a) em todas. A T78 amplia a lista de cidades e decide os limites com o gabarito.

**Provisório (o que o código faz hoje), para confirmar:**
- HTML escapado várias vezes: o texto é desfeito até 16 passadas (`_PASSADAS` em `src/jobot/nucleo/texto.py`). Acima de 15 escapes ainda sobra entidade (limite no comentário `shortcut:`).
- "Salary 120k USD 401k match" lê o salário e perde o benefício; "Fraud USD 401k" ainda vira valor. Ressalva conhecida, para a T78.
- "30 min" (minutos) é lido como 30 por hora ("Almoço de 30 min, R$ 5.000" dá BRL 30 por hora). Resolvido pela T92 (entregue): número seguido de `min`, `mins`, `minutos` ou `minutes` não é valor.
- Rótulo `min` sem moeda colada antes do número ("3.000 min a 5.000 max"): o primeiro valor é lido como duração e some, e só o segundo vira salário (marcado com `shortcut:` em `_valores`). O mesmo vale para o `min` depois do limite superior sem moeda ("R$ 3.000 a 5.000 min" lê só 3.000). Os controles do plano ("Min $50k - Max $70k" e "R$ 3.000 min a R$ 5.000 max por mês") seguem como faixa.
- As variantes `minuto` (singular) e `m.` não são tratadas, e `hora` no singular também não: "30 min a 1 hora, R$ 5.000" ainda lê 1 por hora.
- A conferência desses casos contra o gabarito fica para a T78, porque a rotulagem (T81) ainda não foi feita.

## D49. Primeira execução: "Não ligar" quando o sistema falha (T53)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** No passo 2 da primeira execução, "Não ligar" chama `desligar` sempre no Linux (`_gravar_passo_2` em `src/jobot/painel/rotas/primeira_execucao.py`), porque um "ligar" recusado no meio já deixou o arquivo do serviço. `desligar` pode falhar (`systemctl_falhou`) quando o arquivo ficou e o `systemd` não responde. Nesse caso a pessoa não consegue concluir a primeira execução: nenhuma das duas opções termina.

**Opções:** (a) a falha do `desligar` volta ao passo 2 com o motivo, como está; (b) conclui mesmo assim, com o segundo plano desligado, e mostra o aviso com o motivo.

**Decisão provisória:** o código segue a (a). A recomendação é a (b): a pessoa pediu para não ligar, e ficar presa no passo 2 é pior. O título errado da recusa ("Não foi possível ligar") foi corrigido pela T89 em 2026-11-14, que mostra o título de desligar; a escolha do dono segue aberta e o código segue a (a).

## D50. Escopo opaco e nome da empresa no coletor (T28, T29, T30, T35, T38, T40, T41, T50, T51, T84)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O contrato `coletar(escopo, http)` só recebe uma string, então cada coletor da leva A escolheu o que põe nela:
- SmartRecruiters (T30): `<identificador>|<pais>`, um escopo por par.
- Himalayas (T35): `<PAÍS>|<cargo>`. O país ISO fica vazio quando a busca não tem país (`|python`), e sem termos não há escopo. O corte é no primeiro `|`, então o cargo pode ter `|`.
- We Work Remotely (T38): `geral` (o feed geral) e o slug de cada categoria, 12 escopos ao todo.
- Gupy (T40): `empresa:<subdominio>:<careerPageName>` e `cargo:<termo>`. Trocar o `careerPageName` de uma empresa muda o escopo, e as ocorrências do escopo antigo somem pelo ciclo de vida normal.

Esse texto vira `vaga.escopo`, `ocorrencia.escopo` e chave de `por_escopo`. Quem o lê como identificador de empresa erra. Lever (T28) e Ashby (T29) têm outro problema: nem o `coletar` nem a resposta trazem o nome da empresa. Cada um guarda `identificador -> nome` na instância, preenchido a cada `escopos(ctx)` (o dicionário é reatribuído, não acumulado, para renomear a empresa no painel valer na hora) e lido em `coletar`. Sem `escopos` antes, o nome cai para o identificador. O executor chama `escopos` antes de `coletar`, então hoje não há perda; quem chama `coletar` por fora do executor (o "testar" da T51, o vigia da T84, a captura avulsa) pode perdê-lo. A captura da Gupy com `--escopo` em `scripts/capturar.py` já exige o formato novo.

**Opções:**
- Formato do escopo: (a) texto opaco, montado e lido só pelo coletor, como está; (b) escopo igual ao identificador em todo coletor, com país, termo e nome guardados em estado ou em campo novo do contrato (muda o `Protocol`, R4).
- Nome da empresa em Lever e Ashby: (a) estado na instância (como está); (b) `coletar` recebe o contexto ou o nome (muda o contrato); (c) o executor troca `empresa` depois da coleta.
- Hapvida na Gupy: a página dela se chama "Página de Carreira", e é esse o nome que sai na vaga. (a) deixar na fase 1 e abrir tarefa se incomodar; (b) preferir o nome do cadastro (`empresa.nome`), o que pede o contrato levar o nome (R4).

**Decisão provisória:** (a) nas três. O escopo é texto opaco: só o próprio coletor o monta, em `escopos(ctx)`, e o lê. Quem chama `coletar` (o executor da T41, o "testar" da T51, o vigia da T84) pega os escopos de `COLETOR.escopos(ctx)`, na mesma instância e antes de coletar, e nunca monta a string à mão. A recomendação para o nome é a (a) até uma terceira fonte sem nome na resposta pedir o mesmo; aí se decide (b) ou (c) para todas.

**Atualização de 2026-11-14 (A16):** a terceira fonte sem nome na resposta apareceu: o Workday (a empresa só vem em `hiringOrganization.name`, no detalhe). A sessão manteve a (a): o Workday guarda `identificador -> nome` na instância, como Lever e Ashby, sem mudar o contrato do `coletar`. Mudar o contrato mexe em todos os coletores e é decisão do dono: se quiser a (b) ou a (c), vira tarefa nova. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar. A Eightfold também guarda o cadastro na instância (`shortcut:` em `eightfold.py`). Os escopos novos da leva B seguem o texto opaco: um por empresa e país no Workday (T115, A17), o host no Eightfold, o identificador nas demais.

**Atualização de 2026-11-14 (A33, T115, leva K):** o escopo do Workday tem o formato `<tenant>/<site>|<wd>|<PAÍS>`, com o código ISO do país em maiúsculas (`workday.py:71-83`). O SmartRecruiters usa `<id>|<pais>` em minúsculas, porque a API dele pede assim: o escopo é opaco e cada coletor tem o seu. Escopo gravado com o nome antigo (sem país) dá `ValueError` em `_separar`, sem migração, porque a fase 1 ainda não saiu. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Escolhas do redator, para confirmar com o dono:**
- A T50 mostra o escopo como texto, como vem do coletor, sem separar nem traduzir.
- Hapvida: o nome genérico faz o escopo `hapvidandi` baixar vagas de várias empresas, e só o filtro de host do `jobUrl` as descarta depois de baixadas. O orçamento de 30 pedidos é da fonte inteira, então esse escopo pode gastar tudo e deixar os outros em `no_limite` (o rodízio por `ultima_coleta` ameniza, não elimina). Se acontecer na prática, vira tarefa nova: limite próprio por escopo ou filtro por outro parâmetro da API.
- SmartRecruiters: `escopos` não confere o identificador do cadastro. Um identificador vazio ou com `|` geraria escopo malformado. O resolver e o `empresas.json` já cuidam disso, então fica sem teste; filtrar por regex em `escopos` é opcional.

**Oracle HCM (T66, leva L):** o coletor segue o mesmo atalho do Workday. O nome da empresa vem do cadastro, guardado por `escopos` (`oracle_hcm.py:170-191`), e, sem passar por `escopos`, cai no primeiro rótulo do host (`oracle_hcm.py:196`, por exemplo `eeho`). A decisão não muda; sai junto com a D50.

## D51. GitHub Issues: cota, empresa e página 2 (T31, T84, T94, T99)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O coletor (`src/jobot/nucleo/coletores/github_issues.py`) deixou três pontos.
- Cota (antes da T94). A linha da tabela do plano promete "cota de 60/h acabou → no_limite", mas a cota esgotada chega como 403 ou 429. O `http.py` converte isso em `Bloqueio` sem os cabeçalhos, e o escopo sai `falhou` com `saude.bloqueio`, em vez de `no_limite` com `saude.cota`. O `no_limite` do coletor só sai com 200, `x-ratelimit-remaining: 0` e `Link rel=next`, quase inalcançável com `per_page=100`. No vigia (T84), `saude.bloqueio` só entra no resumo, sem issue; o efeito visível é o link "reportar problema" da tela de fontes (T50), inclusive para o 403 de cota.
- Empresa. Toda vaga da fonte leva o nome do repositório (`owner/repo`) como empresa. Filtros, encaixe, exibição e agrupamento vão tratar o repositório como empresa.
- Página 2. Formato quebrado na página 2 ou seguinte descarta as vagas da página 1 e devolve `falhou` (marcado com `shortcut:`). Nenhum dos cinco repositórios passa de uma página hoje.

**Opções:**
- Cota: (a) deixar assim; (b) `Bloqueio` e `LimiteAtingido` levam os cabeçalhos da resposta (mexe em `http.py`, teste novo em `test_http`) e o coletor devolve `no_limite` com `saude.cota` quando `x-ratelimit-remaining` for 0 num 403 ou 429; (c) o coletor guarda o `remaining` 0 na instância e pula os escopos seguintes. Vale para toda fonte com cota.
- Empresa: (a) `owner/repo` agora; (b) heurística depois, com o texto das vagas dos cinco repositórios.
- Página 2: (a) `falhou`, como está; (b) `parcial` com as vagas já lidas.

**Decisão provisória:** cota: (b), entregue pela T94: `Bloqueio` e `LimiteAtingido` levam os cabeçalhos (`cabecalhos`), e 403 ou 429 com `x-ratelimit-remaining: 0` vira `no_limite` com `saude.cota`, com as vagas já lidas. O caso que sobrava, o 429 de cota zero sem `Retry-After`, foi entregue pela T99 em 2026-11-14 (opção (b)): o laço de `pedir` em `nucleo/http.py` levanta `LimiteAtingido` com os cabeçalhos na hora, sem as esperas de 30, 60 e 120 s. A regra vale para qualquer fonte que mande `x-ratelimit-remaining: 0` num 429 sem `Retry-After`, não só para o GitHub; um `Retry-After` que não é número conta como ausente (teste `test_429_com_cota_zero_e_retry_after_invalido_para_na_hora`). Fonte que não manda esse cabeçalho segue as esperas de hoje. Empresa: (a); a heurística é tarefa própria, depois de haver corpus real. Página 2: (a), e troca-se por (b) quando algum repositório passar de 100 abertas.

**Provisório (o que o código faz hoje), para confirmar:**
- As fixtures `paginacao_1`, `paginacao_2` e `formato_mudou` foram montadas à mão. O `Link` delas (id do repositório e cursor) é inventado a partir do formato visto; o `.meta.json` diz isso, com o `sha256` conferido. O coletor segue o `Link` como vier.
- O coletor guarda as URLs já vistas começando pela URL sem a query. Um `Link rel=next` hostil que aponte para a página 1 (com a query) a lê de novo e duplica as vagas uma vez, antes de a repetição ser pega. O teto de 30 páginas limita o laço, e só uma API quebrada ou hostil faz isso. Semear a lista com a URL já com os parâmetros seria o conserto.
- O pedido condicional (`ETag`) vale só para a página 1.

## D52. SmartRecruiters: chave da vaga e empresa inexistente (T30, T51)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** Dois pontos do coletor (`src/jobot/nucleo/coletores/smartrecruiters.py`).
- Chave da vaga. A URL da vaga é montada da lista como `https://jobs.smartrecruiters.com/<identificador>/<id>`, sem slug, e é a chave da vaga. A `postingUrl` real do detalhe tem slug (`/744000161500208-analista-de-dados-e-relacionamento`). A URL sem slug nunca foi aberta na rede (os testes usam `MockTransport`). Se ela não abrir ou não redirecionar, o link do painel quebra, e a deduplicação entre fontes não casa com a URL que tem slug.
- Empresa inexistente. A API devolve 200 com `totalFound=0`, então não há `test_404_empresa_nao_encontrada` (a ausência é deliberada), e zero vagas não prova que o identificador existe.

**Opções:**
- Chave: (a) conferir antes de gravar vagas reais abrindo na rede um exemplo da captura e, se abrir, manter a URL sem slug; (b) montar o slug a partir de `name`; (c) usar a `postingUrl` do detalhe, o que pede um pedido por vaga.
- Empresa inexistente: (a) a T51 mostra aviso quando o "testar" dá zero vagas; (b) nada.

**Decisão provisória:** chave: (a); mudar a chave depois de gravar vagas custa migração, então a conferência vem antes da primeira coleta real (a T55 é o primeiro momento). Empresa inexistente: (a), registrado no critério da T51.

**Atualização de 2026-11-14 (A15):** o passo 4 do enriquecimento (`_enriquecer` em `agenda/execucao.py`, DR-70) já detalha a `VagaColetada` listada sem descrição. Onde este registro dizia que ligar o `detalhar` à vaga já listada era tarefa do enriquecimento, vale agora "feito pelo passo 4 (DR-70)". Workday e SmartRecruiters detalham por ele; o que falta é só a T114 (detalhar por escopo e no ritmo do `por_escopo`, D77). A dúvida da chave da vaga sem slug (T55) segue como está. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Provisório (o que o código faz hoje), para confirmar:**
- O escopo `<identificador>|<pais>` é o contrato da D50.
- O `detalhar` não lê o `applyUrl` do detalhe, então `url_candidatura` fica `None`. O plano não pede isso para a SmartRecruiters. Ligar o `detalhar` a vaga já listada (o executor só detalha `UrlListada`) é tarefa do enriquecimento (seção 10.6) ou do executor.
- A caixa do identificador é preservada (D45).

## D53. Gupy: escolhas do redator (T40, T51, T54)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O coletor (`src/jobot/nucleo/coletores/gupy.py`) fez quatro escolhas sem decisão no plano, além das da D50 e da D45.

**Opções:**
- Pedido condicional: (a) só na página 0 (como está; um 304 não diz quantas páginas existem, então o 304 da página 0 vale pela lista toda, e uma empresa com mais de 100 vagas que só mude da página 2 em diante demora a ser vista; a Localiza tem 894 vagas e muda toda hora); (b) pedido condicional em todas as páginas mais um pedido extra de terminador por escopo (dobra o custo dos 28 escopos contra o orçamento de 30 pedidos).
- Filtro de host: (a) só o escopo de empresa descarta a vaga cujo host do `jobUrl` não é `<identificador>.gupy.io`; o escopo `cargo:` não filtra, porque a vaga é de qualquer empresa do portal, inclusive com domínio próprio; (b) filtrar também o `cargo:`.
- Prazo: (a) `applicationDeadline` vale o dia escrito, sem fuso (a captura mostra `2027-01-12T00:00:00.000Z`, meia-noite UTC, ou seja, data pura); (b) converter para o dia local.
- Nome da empresa: o `resolver` devolve o `careerPageName` além do `identificador`. (a) a T51 grava esse par em `parametros` ao adicionar a empresa; (b) guardar só o identificador e deixar o coletor descobrir o nome a cada coleta.

**Decisão provisória:** (a) nas quatro. Para o prazo, a (a) é segura porque a Gupy manda data pura. A T51 passa a gravar o `careerPageName` do resolver (critério novo na T51). A rota da T54 que monta os `parametros` do "testar" não pode apagar o `careerPageName` (regra da D37).

**Escolhas do redator, para confirmar com o dono:** os itens pulados saem como `saude.formato_mudou` sem contagem, como nos outros coletores (D45). A decisão 29 (o `careerPageName` aceito pela API e as 9 empresas que levam o nome em `parametros`) está no apêndice de fontes, seções 2.5 e 7.5.

## D54. Execução completa: o que ficou para confirmar (T41, T95)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T41 (`src/jobot/agenda/execucao.py`) entregou a execução de sete passos e deixou pontos que mexem em `banco/` ou em escolha do dono.

**Opções:**
- Execução que fica "rodando" depois de uma exceção: o erro sobe e a execução continua "rodando" até `marcar_interrompidas` achar o batimento velho (mais de 5 min), e nesse tempo o índice `execucao_uma_por_tipo` impede outra execução do mesmo tipo. (a) deixar; (b) função nova `interromper_execucao` em `banco/execucoes.py`, que `executar_busca` chama ao pegar a exceção, marcando "interrompida" na hora e deixando a exceção subir.
- Detalhe e cache: o detalhe (`gravar_detalhe`) e o cache de 30 dias (`enriquecimento`) são gravados em duas transações, e o SQL do cache mora em `execucao.py` por falta de função em `banco/` (marcado com `shortcut:`). (a) deixar; (b) função nova `gravar_cache_detalhe` em `banco/gravacao.py` que grava os dois numa transação só.
- Recuo para a URL de detalhe que sempre quebra: ela é pedida em toda execução por até 30 dias (`JANELA_DETALHE`). (a) manter, com `shortcut:`; (b) gravar a tentativa no cache já na primeira falha comum, o que tira o "tenta de novo" da falha passageira; (c) contar as falhas, o que pede schema.
- Critério de fonte que "rodou" (a que recebe detalhes): entra a fonte que tem ao menos um escopo fora de `no_limite` e de `falhou`; sai a fonte em que algum escopo parou por intervalo, orçamento, 429, bloqueio ou limite. Com intervalo por escopo (DR-64), a fonte só recebe detalhes quando todos os escopos estão vencidos. Isso pega a Eightfold (o escopo `apply.careers.microsoft.com` tem 1440 min e os outros não têm intervalo), que só é enriquecida uma vez por dia. (a) manter, que é conservador e não fura o ritmo; (b) excluir só quando todos os escopos pararam ou quando o motivo é 429, bloqueio ou orçamento, deixando o intervalo de um escopo isolado fora da regra.

**Decisão provisória:** execução: (b), entregue pela T95 (`interromper_execucao` em `banco/execucoes.py`; `executar_busca` a chama num `except BaseException` e deixa a exceção subir). Detalhe e cache: (b), entregue na mesma T95 (`gravar_cache_detalhe` em `banco/gravacao.py`). O teste injeta o erro num passo seguinte (`recalcular_encaixe`), porque o executor absorve a exceção do coletor e a vira saúde `falhou`. Recuo: segue a (a), com `shortcut:` que diz que a (c) pede schema. Critério de fonte: (a).

**Provisório (o que o código faz hoje), para confirmar, sem decisão nova (recomendação: manter):**
- Vaga gravada com o interruptor de enriquecimento desligado é detalhada quando ele é religado.
- `executar_busca` aceita o argumento `coletores` (um mapa de chave para coletor; sem ele usa os coletores do registro). Ele não está nas Interfaces da T41 e serve aos testes.
- O teto de 200 detalhes por execução não limita os detalhes de sitemap que o executor da T16 já fez dentro da coleta; o limite de 200 conta só os feitos no passo 4.
- A fonte desligada ganha saúde "desligada", com motivo vazio, a cada execução.
- O pré-filtro em SQL das descrições vazias é mais restrito que o `strip()` do Python (o `trim()` do SQLite não tira `\v`, `\f` nem NBSP), então uma descrição só com esses caracteres nunca vira candidata a detalhe. O comentário em `execucao.py` diz o contrário e se corrige (o SQL decide, o `strip()` só confirma), ou o `trim` ganha `char(11,12,160)`. A T95 não mexeu nisso: o comentário e o `trim` seguem como estavam.

## D55. Agendador: travas compartilhadas com "buscar agora" (T42, T48, T49)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O `laco` do `src/jobot/agenda/agendador.py` cria os `asyncio.Lock`, um por tipo, dentro dele mesmo. A rota de "buscar agora" da T49 não alcança essas travas, mas o plano diz que ela "usa o laço da agenda e a trava", e o desenho (12.3, item 3, e a DR-36) pede um `asyncio.Lock` por tipo no processo, sem separar a agenda do botão. A primeira recomendação da T42 (deixar assim e contar só com o índice único `execucao_uma_por_tipo`) estava errada e foi corrigida.

**Opções:**
- (a) deixar assim e contar só com o índice único `execucao_uma_por_tipo` (T22), o que contraria o plano;
- (b) o `laco` ganha o parâmetro opcional `travas: Mapping[str, asyncio.Lock] | None = None`; com `None` ele cria as travas como hoje, e quem chama sem o parâmetro continua funcionando; a T48 cria o dicionário e passa o mesmo ao `laco` e à rota da T49.

**Decisão provisória:** (b), que o plano dá à T48 (ela mexe em `agendador.py`) e à T49 (critério com teste de que a rota usa as mesmas travas).

**Escolhas do redator, para confirmar com o dono:**
- A espera de 60 s depois de iniciar vale para os três tipos (`busca`, `descoberta`, `paginas`).
- O formato do `Protocol` `Estado`, que a T48 vai montar, fica como está em `agendador.py`.
- Uma busca que levanta exceção é disparada de novo a cada 60 s. Esperar mais depois de uma falha seria tarefa nova, se o dono quiser.

## D56. Detalhe da vaga: cor do prazo urgente (T46, T96)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O desenho 13.5 pede o prazo com "▲, em vermelho se faltam menos de 7 dias". A T46 entregou o corte de 7 dias, mas marca a faixa e o texto só em negrito, porque o vermelho pede um token novo (`--alerta`) e o par de contraste em `base.css` e na lista de contrastes, e o `base.css` é da T36. A marca ▲ da grade de meses também ficou sem destaque, pelo mesmo motivo.

**Opções:** (a) criar `--alerta` numa tarefa pequena (com par de contraste para a superfície e para o fundo, nos dois temas) e pintar o prazo e a marca ▲; (b) manter o negrito.

**Decisão provisória:** (a), entregue pela T96 com os valores de partida: `--alerta` é `light-dark(#d70015, #ff453a)`, e o prazo e a marca ▲ usam o token, com o negrito e o ▲ mantidos. Contraste medido: 4,94 sobre o fundo claro, 6,16 sobre o fundo escuro, 5,38 sobre a superfície clara e 4,99 sobre a superfície escura. O ▲ da grade de 12 meses fica sobre `--trilho` com 4,41 (claro) e 4,09 (escuro): é objeto gráfico (`aria-hidden`, o texto ao lado diz o mesmo), e o mínimo da WCAG 1.4.11 para ele é 3:1, então passa; o texto do prazo é que precisa de 4,5. O par `alerta/trilho` não entra na lista do `base.css`. Se o dono quiser 4,5 também na grade, pede outro tom para a marca ou para o fundo.

**Provisório (o que o código faz hoje), para confirmar:**
- O comentário da correção aparece em todas as linhas do formulário (um `textarea` por formulário, `id` `correcao-comentario-{campo}`). A dúvida anterior, se o comentário ficava em uma só linha, está resolvida a favor do desenho 13.5.
- Quando área, nível, modalidade ou contrato estão `NULL` (a coluna aceita), nenhum `<option>` sai marcado, e o navegador mostra a primeira opção como se fosse o valor da vaga. A sugestão da revisão é uma opção vazia marcada e desabilitada no topo, com teste de vaga de área `NULL`; fica para o dono pedir, porque o 422 seco para valor vazio já vale.
- `rotas/detalhe.py` importa nomes privados de `rotas/vagas.py` (`_MAX_ID`, `_busca_efetiva`, `_inteiro`, `_relogio`, `_utc`). Funciona, mas qualquer renomeação lá quebra aqui; tornar públicos os helpers compartilhados é ajuste à parte.

## D57. Coletores da leva A: escolhas dos redatores, para confirmar (T28, T29, T32, T33, T34, T35, T38, T39, T93)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** Cada coletor fez escolhas sem decisão no plano ou no apêndice. Um item por fonte. A recomendação de todos é manter, salvo onde está dito.

**Opções, e o que o código faz hoje:**
- Modalidade declarada: `modalidade_declarada="remote"` fixa em Remotive, Himalayas e We Work Remotely (as três só listam vaga remota; `remote` está em `rotulos.json`), mas `None` no RemoteOK (o apêndice não diz que a fonte declare modalidade). (a) igualar o RemoteOK às outras; (b) deixar a regra por fonte para a T13. Recomendação: (a), que vira a T93.
- Remotive (T32): `contrato_declarado` é o `job_type` cru (`full_time` não está em `declarados` e cai nas regras de texto; `contract` e `freelance` viram freelance); `etiquetas` é a categoria seguida das tags (a categoria ajuda a regra de área). Sem teste dedicado de 404: é fonte de escopo único, e o 404 cai em `saude.erro_de_rede`.
- RemoteOK (T33): `epoch` chega como inteiro na captura real (o `id` vem como texto), e o coletor aceita inteiro, número com ponto e texto numérico, nunca bool. A `url` vem com `remoteOK.com` em caixa mista; conferir na T09 se o host é normalizado para minúsculas. Sem teste de 304: a captura não mostrou `ETag` nem `Last-Modified`. O link de volta sem `nofollow` e o crédito "Remote OK" são do painel, não do coletor.
- Jobicy (T34): com cursor repetido e página idêntica, as vagas podem duplicar no resultado (`juntar_paginas` não deduplica); o estado sai `parcial` e o laço termina, e quem grava deduplica por `(fonte, id_externo)`. O salário aceita inteiro até `sys.float_info.max`, e o `SalarioBruto` guarda `float` (decisão do contrato); a conversão para centavos e a plausibilidade ficam com quem consome (T19).
- Himalayas (T35): `etiquetas` é só `seniority` (`categories` são slugs ruidosos); `locais` são os `locationRestrictions` como vêm (vaga mundial traz de 45 a 73 países); `contrato_declarado` é o `employmentType` cru. Salário só entra se `minSalary` e `maxSalary` forem número maior que zero; a moeda vem do `currency` como veio (pode ser `None`); o período mapeia `hourly`, `daily`, `weekly`, `monthly` e `annual`, e outro valor vira `None` (as capturas só têm `annual` e `hourly`). Página ilegível depois da primeira sai `parcial` com as vagas já lidas; na primeira, `falhou`. O prazo está na D45.
- We Work Remotely (T38): `etiquetas` leva só `category` (`skills` é lista gerada e ruidosa, e as etiquetas entram no cálculo de área); os ids de escopo são os da D50, e a T88 e a T46 não devem depender deles. As fixtures `normal.xml` e `categoria.xml` têm só 5 itens (o apêndice fala em 100 no feed geral), o que não afeta o código.
- Ashby (T29): o `salario_estruturado` não é lido; só o resumo em texto vai em `salario_texto` (`scrapeableCompensationSalarySummary`, com `compensationTierSummary` de reserva), porque o formato de `compensationTiers[].components[].interval` não apareceu em nenhuma captura. Recomendação: ler `components` quando uma captura trouxer o `interval`. `isListed` ausente ou que não é booleano conta como item pulado por formato (e vira `falhou` se nenhum item for legível), para um campo renomeado não dar `ok` vazio e fechar todas as vagas; `isListed=false` fica de fora sem contar como pulado. O resolver aceita `jobs.ashbyhq.com/<nome>` e `api.ashbyhq.com/posting-api/job-board/<nome>`, preserva a caixa, recusa o host europeu (não testado) e aceita nome de `[A-Za-z0-9_-]{1,100}`. `applyUrl` que não é http ou https faz a vaga inteira ser pulada (DR-08), mesmo com o `jobUrl` bom.
- Lever (T28): resposta que não é lista, ou lista não vazia sem nenhuma vaga legível, é `falhou`; lista com algum item pulado é `parcial`; lista vazia é `ok`. O nome da empresa fica na instância (D50).
- Hacker News (T39): a primeira linha do comentário (`Empresa | Cargo | Local`) é só costume, então vale `shortcut:`. A empresa é o primeiro segmento antes de `|`; o cargo é o segundo, a menos que seja rótulo de modalidade (`remote`, `onsite`, `hybrid`), e então, sem `|`, é a linha toda cortada em 120 caracteres. Local e modalidade ficam para o tratamento; a T78 calibra. Quando a busca devolve hits e nenhum tem o título "Ask HN: Who is hiring?", o coletor devolve `falhou` com `saude.formato_mudou`, para o `ok` não fechar todas as vagas; busca com `hits` vazio dá `ok` com zero vagas. Comentário com `text` nulo ou vazio (apagado) é ignorado e não conta como pulado; sem a chave `text`, conta como formato mudou, e se todos vierem sem texto o estado é `falhou`. O `intervalo_min` é `null` em `fontes.json` e o coletor faz 2 pedidos por execução, enquanto o apêndice diz que uma leitura basta; o intervalo é decisão do dono. No dia 1 ou 2 do mês, o tópico novo ainda vazio dá `ok` com zero vagas e fecha as vagas do mês anterior: quem trata isso é o `zero_inesperado` do executor (T16), e no vigia (T84) a fonte, sendo de escopo único, abriria issue nesse caso.
- Id booleano ou vazio: `isinstance(x, int | str)` aceita `bool`, então um `id` `true` vira `id_externo` `"True"` (Lever, Remotive, RemoteOK, Jobicy, Gupy); no Lever, `id` vazio vira `""`; `_numero` do Lever aceita NaN e Infinity. Nenhuma fonte real manda isso, e nada quebra. Recomendação: excluir bool e texto vazio quando algum coletor for mexido.

**Decisão provisória:** o código segue o que está acima; a modalidade do RemoteOK passou a `remote` pela T93 (entregue).

## D58. Comandos `serve` e `buscar`: recuperação, cliente único e saída do terminal (T48, T49, T100)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T48 (`src/jobot/cli/servir.py`, `src/jobot/cli/buscar.py`) sobe o servidor com a agenda e roda a busca pela linha de comando. Quatro escolhas ficaram sem decisão no plano.

**Opções:**
- Motivo da primeira busca do processo: (a) `recuperacao` só quando, ao subir, a última busca completa passou de 3 h ou está no futuro (`_perdida` em `servir.py`); as seguintes levam `agenda`, e banco sem nenhuma busca completa também leva `agenda`; (b) `recuperacao` também quando nunca houve busca. Recomendação: (a), que bate com o passo 21 do roteiro do dono.
- Cliente e travas: (a) o lifespan (`vida`, posto em `app.router.lifespan_context`) cria um só `ClienteEducado` para todos os tipos e o guarda em `app.state.cliente`; as travas por tipo ficam em `app.state.travas` (D55). Os validadores do cliente são lidos por uma conexão própria, aberta no lifespan. A rota "buscar agora" da T49 usa os dois e abre a sua conexão para `executar_busca`; (b) cada rota cria o seu cliente. Recomendação: (a), porque o desenho 12.3 pede o mesmo cliente para o ritmo por host valer entre os tipos.
- Preparação do banco: (a) `preparar_banco` (migrar, semear, `marcar_interrompidas`, `reprocessar_se_regras_mudaram` e, se algo mudou, `aplicar_cotacoes` e `recalcular_encaixe` com o dia local) roda no `montar`, antes do uvicorn; o `buscar` chama a mesma função; (b) no lifespan. Recomendação: (a): o `BancoMaisNovo` sai do `executar` com uma linha em stderr e código 1, sem subir o servidor.
- Saída do `jobot buscar`: (a) o motivo sai como a chave de i18n crua (`saude.bloqueio`), marcado com `shortcut:` em `_resumo`; (b) o motivo em português pelo catálogo de i18n. Recomendação: (b), que vira a T100.

**Decisão provisória:** (a) nas quatro; a saída do terminal muda pela T100. A semente das tabelas `fonte` e `empresa` agora roda em `preparar_banco` (`semear`), o que resolve a pendência da T51 (D60).

**Provisório (o que o código faz hoje), para confirmar:**
- O `montar` cria as travas dos três tipos (`busca`, `descoberta`, `paginas`), mas passa ao `laco` só a tarefa `busca`. A T71 e a T72 acrescentam a sua tarefa ao dicionário `tarefas` do `vida`.
- Quando o lifespan falha ao subir (por exemplo, erro ao montar o `ClienteEducado`), o terminal e o log dizem "porta ocupada?", e a causa real só aparece no log do uvicorn. O `except` dos dois `executar` também não pega `sqlite3.Error` (banco corrompido, `database is locked`), que sai como traceback. A trava é solta no `finally` e nada se perde. Ajuste opcional, se o dono quiser.

## D59. Tela de fontes: link "reportar problema" e forma da lista (T50)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T50 (`src/jobot/painel/rotas/fontes.py`) mostra a saúde das fontes e o link "reportar problema" (ADR 0018, D31). O escopo é texto opaco de cada coletor (D50), e nem todo escopo é identificador de empresa.

**Opções:**
- Escopo no link: (a) só a chave da fonte para todo escopo; (b) `<fonte>/<identificador>` quando o escopo é igual ao identificador de uma empresa cadastrada, não removida, daquela fonte; os outros escopos dividem um único link no cartão, só com a chave. Recomendação: (b). O escopo de busca (Himalayas `<PAÍS>|<cargo>`, Gupy `cargo:<termo>`) carrega termo da pessoa e não vai na URL. Os escopos de empresa da SmartRecruiters (`<id>|<pais>`) e da Gupy (`empresa:<id>:<nome>`) nunca casam com o identificador e hoje mandam só a chave; mudar isso mexe no contrato da D50 (R4).
- Forma da lista: (a) cartões, um por fonte; (b) tabela, como no desenho. Recomendação: (a), melhor no celular.
- Link por escopo: (a) o link de empresa cadastrada fica no escopo, dentro do `<details>`, e o da chave pura fica no cartão; (b) um link só por cartão.
- Validação do `fonte-quebrou.yml`: (a) o teste lê o arquivo como texto (regra da T01); (b) parser YAML, que pede `pyyaml` como dependência nova.

**Decisão provisória:** (a) para a forma e para o link por escopo; (b) para o escopo no link; (a) para a validação.

**Provisório (o que o código faz hoje), para confirmar:**
- A docstring do módulo `fontes.py` ainda diz que todo escopo leva `<fonte>/<escopo>`; vale a regra acima, e a docstring se corrige na próxima tarefa que mexer no arquivo.
- O item de menu para `/fontes`, que a T50 deixou fora, já existe: o menu da casca (`areas` em `base.html`) tem fontes, empresas e configurações.

## D60. Tela de empresas: cópia do coletor no "testar" e nome padrão (T51)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** A T51 (`src/jobot/painel/rotas/empresas.py`) adiciona, testa, desliga e remove empresas. Ela chama `escopos` e `coletar` fora do executor, o que toca na nuance da D50.

**Opções:**
- Estado do coletor no "testar": Lever (`_nomes`) e Ashby (`_empresas`) guardam estado entre `escopos` e `coletar`, e o `COLETOR` compartilhado é o mesmo da busca real, no mesmo laço de eventos. (a) o "testar" trabalha numa `copy.copy` do coletor; (b) uma instância nova por teste; (c) `copy.deepcopy`. Recomendação: (a), que vale enquanto `escopos` reatribui o estado; se um coletor passar a mudar no lugar um dict ou lista criado no `__init__`, trocar por (b) ou (c). Quem chamar `escopos` ou `coletar` fora do executor (T54, vigia T84) faz o mesmo.
- Lista das fontes por empresa: (a) a constante `ATS_POR_EMPRESA` na rota; (b) campo novo em `fontes.json` (contrato público, R4). Recomendação: (a) por ora; fonte nova por empresa entra na constante.
- Etiqueta de banco de talentos (D37): (a) reconhecida só pelo nome exato (`ETIQUETA_BANCO_DE_TALENTOS`); (b) campo novo no esquema. Recomendação: (a).
- Nome padrão: o nome digitado vale; sem ele, o nome já gravado (removida ou não), senão o `careerPageName` do resolver, senão o identificador. Recomendação: manter.

**Decisão provisória:** (a) nas três primeiras e o nome padrão como está.

**Provisório (o que o código faz hoje), para confirmar:**
- O "testar" da Gupy pode gastar o orçamento inteiro da fonte (perto de 18 s).
- O botão Testar fica só no formulário de adicionar; a empresa já gravada, inclusive a desligada, aparece na lista sem Testar próprio.
- Escopo que termina em `no_limite` ou `parcial` com zero vagas não conta como falha, então a tela pode mostrar o aviso de identificador errado (D52) junto com o motivo de limite. Raro, porque cada escopo do teste ganha orçamento cheio.
- A semente em runtime das tabelas `fonte` e `empresa`, que a T51 apontou como pendente, já roda em `preparar_banco` (D58).
- Edição de empresa na tela e o host europeu da Greenhouse seguem fora da fase 1.

## D61. Configurações: interruptor do segundo plano e 422 seco (T54, T91, T98)

**Status:** segundo plano: decidido (b) pela sessão em 2026-11-14 com o dono fora, para confirmar (A1, entregue na T98). 422 seco: aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** Dois pontos baixos das revisões da T54 e da T91.
- Segundo plano. O interruptor da tela de configurações (`_ctx_segundo_plano` em `src/jobot/painel/rotas/configuracoes.py`) mostra a chave `segundo_plano` do banco, não o estado real do systemd (desenho 12.5). Se o serviço for ligado ou desligado por fora, a tela erra.
- 422 seco. `POST /buscas/{id}/ligar` e `/desligar` (`_ligar` em `src/jobot/painel/rotas/buscas.py`) respondem com `HTTPException` 422 sem página nem mensagem, porque essas rotas não têm formulário.

**Opções:**
- Segundo plano: (a) seguir a chave do banco, como está; (b) ler o estado real do systemd ao montar a tela. Recomendação: (b) numa tarefa própria (T98), porque exige decidir qual é a fonte de verdade.
- 422: (a) seco, como está; (b) mensagem na lista de buscas. Recomendação: (a); vira item novo só se o dono quiser.

**Decisão provisória:** segundo plano: (b), entregue pela T98 em 2026-11-14. Com o dono fora, a sessão escolheu que o interruptor mostra `estado.habilitado` (o timer habilitado no systemd), e não `ativo` (rodando agora, que muda a cada execução). Fora do Linux sai desligado e desativado, sem consultar o systemd, e o GET não regrava a chave. Desfazer: voltar a ler a chave `segundo_plano` do banco. O desenho 12.5 não foi alterado; se ele diz que a tela segue a chave, acertar o texto quando o dono confirmar. 422: (a), seco, como está.

## D62. Primeira execução: sobras da tela de execução (T49, T106, T107)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** Cinco pontos baixos da revisão da T49.
- Nomes privados. Rotas importam nomes com `_` de outros módulos: `_rodar` (de `agenda/agendador.py`, em `rotas/execucao.py:20`), `_relogio` (de `rotas/vagas.py`, em `rotas/execucao.py:25`, `fontes.py:30` e `detalhe.py:28`) e `_de_volta` (de `painel/seguranca.py`, em `rotas/vagas.py:25`, `preferencias.py:15` e `execucao.py:26`).
- Contagem de novas. O "Buscar agora" mostra a contagem de vagas novas lida do banco, não do resultado da busca. Aceito.
- `primeira_execucao/pronto.html` é formulário comum, sem HTMX. O aviso "já roda" nesse caso sai pela T101.
- A tela final da primeira execução mostra dois botões "Buscar agora" (o da casca e o dela).
- A região vazia do andamento ocupa uma linha.

**Opções:** nomes privados: (a) tornar públicos numa tarefa pequena (T106); (b) aceitar como está. Dois botões e região vazia: (a) um só botão e região sem altura (T107); (b) aceitar. Recomendação: (a) nos dois.

**Decisão provisória:** o código segue como está. A T106 e a T107 estão no plano, livres.

## D63. Levas H, I e J: ordem do trabalho e cópia de segurança (A3, A10, A11, A12)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** Três escolhas de ordem, tomadas sem o dono.
- A3. A leva I juntou a T71 (descoberta) e a T72 (páginas acompanhadas) antes da T55, porque só dependiam de tarefas prontas e não dependem da rede real. O plano já diz isso na linha da onda 8.
- A10. A leva J roda em paralelo, até 8 tarefas ao mesmo tempo, cada uma no seu worktree: coletores T56–T65, o vigia T84 e a REG7 (estes registros). Modelo pela dificuldade: Opus nos coletores mais chatos (iel, workday, eightfold) e no vigia; Sonnet nos outros.
- A11. Depois de juntar a leva I e a T103, a `dev` vai ao GitHub como cópia de segurança: só a `dev`, sem PR e sem `main`; push na `dev` não roda CI. A regra registrada antes era push e PR só no fim de cada fase; esta é uma exceção só para a `dev`.
- A12. Depois da leva J (coletores T56–T65, vigia T84, REG7), a `dev` foi mandada de novo ao GitHub como cópia, pela mesma regra da A11. Esta é a regra anterior que a A12 (e a A11) substitui no dia a dia: "push e PR só no fim de cada fase". Continua valendo que PR e `main` só no fim da fase, e que o push da `dev` não roda CI.

**Opções:** A3: (a) como feito; (b) esperar a T55. A10: (a) paralelo; (b) uma tarefa por vez. A11 e A12: (a) copiar a `dev` ao fim de cada leva; (b) só no fim da fase. Recomendação: (a) nas quatro.

**Decisão provisória:** (a) nas quatro. Desfazer: A3 e A10 não têm o que desfazer; A11 e A12 se desfazem parando de dar push.

## D64. Aviso de versão e link de apoio: sobras (T85, T87, T104, T105)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir); o item de CSS, o item do salto recusado e o do link da versão foram decididos pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:**
- Hora da checagem (`checar_versao_nova` em `src/jobot/agenda/versao.py:100-126`). A hora só é gravada quando o servidor respondeu, mesmo com erro. `OrcamentoGasto` e `ErroDeRede` com `status` `None` voltam sem gravar, e a próxima volta (de hora em hora) tenta de novo. Escolha do agente que implementou, para confirmar.
- Salto recusado (A6). `ErroDeRede` com `status` `None` também cobre um redirecionamento recusado, e aí a checagem tenta de novo toda hora e nunca grava. Consertar exige mudar o contrato de `nucleo/http.py` (uma exceção própria para o salto). Fica como está.
- `atualizar()` tem o parâmetro `raiz`, que existe só para os testes (a nota está na T85 do plano).
- Fixture global. O `_laco_versao_parado` de `tests/conftest.py` é `autouse` e vale para todo teste, mas só quatro suítes sobem o lifespan. Mover só para `test_servir.py` quebraria as outras (T104).
- Falta teste de tela do aviso de versão (T105).
- CSS (A4). O estilo `.aviso-versao` entrou no `base.css` junto da T87, que já mexia nesse arquivo, e não numa tarefa à parte.
- Link da versão no aviso (T105, A39). O plano da T105 supunha um link da versão com `target="_blank"` e `rel="noopener noreferrer"`, mas o fragmento real (`painel/templates/aviso_versao/aviso.html`) não tem link: o aviso já diz para rodar `jobot atualizar`. A T105 foi entregue sem link, e o teste trava isso (`tests/tela/test_aviso_versao.py:80-83`).

**Opções:** salto recusado: (a) deixar; (b) exceção própria para o salto no `http.py`, o aviso grava a hora e o log diz o motivo. Hora da checagem: (a) como está; (b) gravar também sem resposta, com atraso de uma hora. Link da versão: (a) sem link, como o aviso real; (b) tarefa para pôr o link da release, com `target` e `rel` e teste que os exija. Recomendação: (a) nos três; o custo de tentar de hora em hora é um pedido por hora, só com o aviso ligado.

**Decisão provisória:** (a) nos três. T104 e T105 entregues e juntadas na `dev` em 2026-11-14 (leva K). Link da versão: decidido pela sessão em 2026-11-14 com o dono fora (A39), para confirmar. Desfazer o link: opção (b).

## D65. Primeira execução em modo edição e idioma do `jobot buscar` (T89, T100)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir); a escolha do formulário esvaziado é do redator

**Contexto:**
- Formulário esvaziado. No passo 1 em modo edição, se a pessoa esvazia todos os campos, a busca não muda e a tela segue ao passo 2. Escolha do redator, para confirmar.
- `editar_busca` (`src/jobot/banco/buscas.py:161`) não recebe `agora`, só `hoje`. O `agora` com fuso vai ao `criar_busca`, que deriva o `hoje`.
- Cidades. O formulário do passo 1 mostra 3 linhas de cidade, e a leitura aceita até 10 (`_MAX_CIDADES` em `rotas/primeira_execucao.py:48`).
- Idioma do `jobot buscar`. O resumo sai sempre em português (`cli/buscar.py`), sem olhar o idioma do sistema nem o da preferência. Limite conhecido, como as outras mensagens de terminal (D23).

**Opções:** formulário esvaziado: (a) manter a busca e seguir ao passo 2; (b) recusar com mensagem. Cidades: (a) 3 linhas na tela, 10 na leitura; (b) igualar. Idioma: (a) fixo em pt; (b) detectar o idioma do sistema. Recomendação: (a) nos três.

**Decisão provisória:** (a) nos três.

## D66. Desligar limpo e ajustes baixos da leva H (A2, A5, T101, T102)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:**
- A2. Ctrl+C e SIGTERM fechavam o cliente HTTP com a busca do "Buscar agora" ainda rodando. A T101 cancela e aguarda essa busca no lifespan, antes de fechar o cliente. `/sair` marca `app.state.saindo` e o "Buscar agora" recusa busca nova nessa janela. O relógio do app vem do `montar`. Sem HTMX, o aviso "já roda" volta pela página do redirect. É correção, não tem o que desfazer.
- A5. Os três ajustes baixos da revisão da leva H foram numa tarefa só, a T102: o "pular" do passo 1 em modo edição mantém `?busca=<id>`, o teste do `Retry-After` inválido no 429 de cota zero e o teste que prova que o catálogo recusa chave repetida.
- Notas baixas da T101: o nome do cookie `jobot_ja_roda` está repetido em `barra.html` e em `_AVISO` de `rotas/execucao.py:29` (um teste pega a divergência). Com o cookie e sem execução encerrada no banco, a carga do andamento devolve fragmento vazio (raro, só visual). POST sem HTMX durante o "saindo" só redireciona, sem aviso (aceito).

**Opções:** A2 e A5: sem alternativa. Cookie repetido: (a) deixar, o teste cobre; (b) passar o nome pelo contexto do template. Recomendação: (a).

**Decisão provisória:** como entregue; cookie repetido fica.

## D67. Segundo plano: falso dos testes sem estado (T98, T113)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir). A decisão da fonte de verdade (A1) está na D61.

**Contexto:** O `FalsoSistema` dos testes de configuração não guarda estado: o teste de desligar força o `is-enabled` na mão, com um comentário.

**Opções:** (a) aceitar como está; (b) dar estado ao falso (T113). Recomendação: (a); só vale (b) se mais testes passarem a depender do estado.

**Decisão provisória:** (a). A T113 está no plano, livre.

## D68. Busca real na rede: resultado da T55 e rodízio da Gupy e da Himalayas (A7, T55)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** A sessão rodou a T55 na `fedora-dev` em 2026-11-14 (3 min 8 s, 95 escopos). Todas as fontes da leva A ficaram "ok" ao menos uma vez e nenhuma respondeu 403. Gupy (30 pedidos) e Himalayas (30 pedidos) deixaram escopos `no_limite`: é o rodízio do DR-52, que atende primeiro os escopos mais antigos e deixa o resto para a próxima execução. O user agent fica provado pelos testes de unidade e pela ausência de 403 na rede real. A divergência real, o teto do Ashby, virou a T103 (D69).

**Opções:** (a) manter o orçamento de 30 pedidos e o rodízio; (b) subir `max_pedidos` da Gupy em `fontes.json`. Recomendação: (a): o desenho manda deixar o resto para a próxima execução, e mais pedidos à Gupy pesam em quem não pediu.

**Decisão provisória:** (a). Desfazer: subir `max_pedidos` em `fontes.json`.

## D69. Ashby: teto de 32 MB e motivos do executor (A8, T103)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** Na T55, os dois maiores quadros Ashby (14,8 MB e 8,1 MB) passaram do teto de 5 MB e falharam. A API do Ashby não tem paginação nem opção sem descrição. A T103 fez o Ashby ler com teto de 32 MB (o mesmo do feed do Google, `TETO_QUADRO_BYTES` em `nucleo/coletores/ashby.py:32`). O executor também passou a dar motivo próprio ao escopo: `RespostaGrande` vira `saude.resposta_grande` e `ErroDeRede` vira `saude.erro_de_rede`, em vez de `saude.excecao:<Tipo>`. Isso muda o motivo de quem antes caía no genérico: cada coletor que levantava esses dois tipos no escopo agora sai com o motivo novo, e `saude.resposta_grande` está em `MOTIVOS_DE_QUEBRA`, então passa a gerar o link "reportar problema".

**Opções:** (a) teto de 32 MB só no Ashby; (b) teto padrão maior para todos; (c) deixar as duas empresas de fora. Recomendação: (a): é o menor teto que resolve e não afrouxa os outros coletores.

**Decisão provisória:** (a). Desfazer: voltar o teto padrão (as duas empresas ficam de fora).

## D70. Exemplos dos coletores da leva B vêm das respostas reais guardadas (A9)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** Os exemplos (fixtures) dos coletores da leva B saem das respostas reais guardadas na conferência ao vivo de 2026-11-13, reduzidas e limpas pelas funções do `scripts/capturar.py`, em vez de esperar uma captura nova por fonte. Depois de juntar a leva, a sessão roda uma busca real das fontes novas, como a T55, e abre tarefa para o que divergir.

**Opções:** (a) usar as respostas já guardadas; (b) capturar de novo cada fonte. Recomendação: (a): as respostas são reais, e capturar de novo repete pedido às mesmas fontes.

**Decisão provisória:** (a). Desfazer: capturar de novo com `scripts/capturar.py` e trocar os exemplos.

## D71. Descoberta de empresas: sobras da T71 (T71, T108, T109, T110)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:**
- Empresa removida. Aprovar a sugestão de uma empresa já cadastrada e depois removida marca a sugestão como aprovada e devolve o id da removida, sem reativá-la.
- Interrupção. `executar_descoberta` (`src/jobot/agenda/descoberta.py`) pega `BaseException`: fechar o app no meio também marca a execução como interrompida e adia até o dia seguinte, e a próxima recomeça do zero (uns 105 MB do `cluster.idx` de novo).
- Fixtures sem `.meta.json`. `tests/fixtures/common_crawl/` e `tests/fixtures/ptax/` não têm meta.
- Orçamento da Gupy. No ramo da Gupy, `testar` (`nucleo/coletores/descoberta_cc.py:225-237`) usa um só escopo com `max_pedidos=2` para resolver e coletar. Se a página pedir nova tentativa ou salto, o coletar começa sem orçamento e a empresa não é sugerida.
- `descoberta.py` importa o `_bater` privado de `agenda/execucao.py`, e o batimento da descoberta não tem teste próprio.

**Opções:** empresa removida: (a) manter sem reativar, porque a remoção foi ato posterior da pessoa (a T74 pode avisar comparando com `removida_em`); (b) reativar. Interrupção: (a) aceitar; (b) só o 503 e o `LimiteAtingido` adiam até o dia seguinte, o resto tenta de novo no mesmo dia (T108); (c) guardar o candidato recusado, com estado novo no `CHECK` de `empresa_sugerida` (muda o schema). Fixtures: (a) registrar em `registros/padroes.md` que pasta de fonte que não é coletor dispensa meta; (b) acrescentar as metas. Orçamento da Gupy: um escopo por etapa (T109). `_bater`: tornar público e testar (T110). Recomendação: (a), (b), (a), um escopo por etapa e `_bater` público.

**Decisão provisória:** o código segue como está até o dono decidir; as T108, T109 e T110 estão no plano, livres.

**Atualização de 2026-11-14 (A31, A38, A40, leva K):** a T108, a T109 e a T110 foram entregues e juntadas na `dev`. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.
- A D71(b) ficou entregue em parte. No escopo do Common Crawl (`max_pedidos=2`), o `OrcamentoGasto` conta como 503 e adia até o dia seguinte (`agenda/descoberta.py:35-39`), mas ele também aparece na nova tentativa de outro 5xx, de falha de rede ou de salto. Separar os dois exige o `http.py` dizer qual status esgotou o orçamento, que é contrato novo em `nucleo/http.py` (A40). Desfazer: tarefa de contrato no `http.py`.
- Recuo de 1 h (A38, R2 da T108). Para erro que não é 503 nem limite, a descoberta marca a execução como interrompida e só tenta de novo depois de 1 h (`RECUO`, `descoberta.py:34`). Sem o recuo, o laço de 60 s tentaria uma vez por minuto e baixaria o `cluster.idx` (uns 105 MB) de novo a cada vez. O número é escolha do redator, para confirmar. Opções: 1 h (no máximo uns 15 tentativas por dia num erro persistente), 6 h ou recuo exponencial. Recomendação: 1 h.
- A chave de adiamento passou a ser `descoberta_adiada_ate`, com um instante ISO em UTC (`descoberta.py:33`). Valor estragado trava a descoberta; a T125 faz valer como ausente.

**Atualização de 2026-11-14 (A45, T74, leva L):** a T74 entregou a tela de sugeridas e seguiu a opção (a) da empresa removida. A tela só avisa, com a data de `removida_em` ("Você removeu esta empresa em 13/11/2026. Aprovar não a traz de volta; para acompanhá-la de novo, adicione-a em Empresas."). Aprovar marca a sugestão como aprovada e não reativa a empresa; o botão Aprovar continua no cartão. A opção alternativa é esconder o Aprovar nesses cartões e deixar só Descartar. Recomendação: manter. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.
- Desvio do desenho 13.9 (A45, para o dono confirmar). O desenho pede "Sugeridas" como sub-aba de Empresas. A T74 pôs o link como item de topo do menu, logo depois de Empresas (`painel/templates/base.html:13`; texto `casca.menu.sugeridas` em `painel/i18n/{pt,en}/casca.json:16`); o menu passou de 6 para 7 links, e o `base.html` marca com `aria-current` só a área de caminho mais longo (`/empresas/sugeridas` não marca Empresas). A largura da barra com 7 itens não foi vista em tela estreita; só os testes de contraste e de teclado rodaram. Opções: (a) manter no menu de cima; (b) fazer a sub-aba dentro de Empresas, como o desenho. Recomendação: (a) até alguém ver a tela estreita; (b) vira tarefa pequena de painel. A aprovação das fontes que não são Gupy não testa a fonte ao vivo (desenho 8.7): vira tarefa nova se o dono quiser a contagem de vagas antes de aprovar.
- Sobras da T74 que vão para a T127 (A46): o `ValueError` do resolver da Gupy dá 422 (hoje vira 502 "Não deu para falar com a fonte"), a Gupy grava o identificador que o resolver devolve, e a empresa removida não faz pedido à Gupy antes de aprovar.

## D72. Páginas acompanhadas: DNS, escolhas do redator e o que falta para a T75 (T72, T111, T112)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir); o DNS foi escolha do agente (regra R2), para confirmar

**Contexto:**
- DNS antes do primeiro pedido (R2). `verificar` resolve o host e recusa endereço local antes de pedir; o resolver é injetável. O hook do cliente só confere o esquema, então a URL digitada pela pessoa precisava disso. O mesmo código está repetido em `nucleo/coletores/paginas.py` (cópias de `_resolver_padrao` e `_conferir_dns` de `nucleo/http.py`), e a cópia é mais fraca: usa `host_local`, que não recusa texto que não é IP, e o original recusa.
- Escolhas do redator, para confirmar: leitura que falha mantém `verificada_em` da última boa e só o `estado` vira `falhou`; a primeira leitura não grava `mudanca_pagina`; `adicionar_pagina` com endereço repetido troca o nome e reativa; lista de nomes locais recusados (sem ponto, `.local`, `.localdomain`, `.lan`, `.home`, `.internal`, `.intranet`, `.arpa`, URL com usuário e senha, IPv4 decimal sem pontos).
- Faltas para a T75: desativar e remover página acompanhada (a coluna `ativa` existe); o `Content-Type` não é lido (tudo vira HTML, com `shortcut:` no código); não há batimento na execução de páginas.

**Opções:** DNS: (a) manter, com o resolver injetável; (b) tornar público o helper de `http.py` e usar o mesmo nos dois lugares, com a regra de recusa do original (T111). Recomendação: (b) numa tarefa pequena, e (a) até lá. Desativar e remover: (a) junto da T75; (b) tarefa própria (T112). Recomendação: (a).

**Decisão provisória:** (a) no DNS e junto da T75 no resto. A T111 e a T112 estão no plano, livres.

**Atualização de 2026-11-14 (T111, leva L):** a opção (b) do DNS foi entregue. `conferir_dns(host, resolver=None)` é público em `nucleo/http.py:175`; a cópia de `nucleo/coletores/paginas.py` e o método `ClienteEducado._conferir_nome` saíram, e `paginas.py` importa o helper (`paginas.py:14,80`). A recusa vale para texto que não é IP, como no original. A mensagem do salto recusado mudou para `<host> resolve para host local`, com a URL de origem só em `add_note` (`http.py:187,265`), e a nota não aparece no log: a T126 devolve a URL à mensagem. O que resta da D72 (desativar e remover página, `Content-Type`, batimento na execução de páginas) é da T75, junto com a T112, na leva M (A48), opção (a). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (T75, T112, leva M):** a T75 e a T112 foram entregues e juntadas na `dev`, numa tarefa só (A48). Entraram `desativar_pagina` e `remover_pagina` (`banco/paginas.py:147,158`), o batimento da execução de páginas (`agenda/paginas.py:37`) e a leitura do `Content-Type` (`nucleo/coletores/paginas.py:99-103`: tipo que não é texto levanta `ConteudoNaoLido` e a página fica `falhou`). Sobrou o R4 do motivo da falha de página: a tela só diz `falhou`, porque o banco não guarda o motivo. A opção (a) foi escolhida (A49): coluna `motivo` em `pagina_acompanhada` por migração nova, gravada por `marcar_falhou` e mostrada na tela, na T128 (D85). Página sem `Content-Type` seguir lida como HTML e adicionar de novo o mesmo endereço reativar a página desativada ficaram aceitos (D84). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (T128, leva N):** o R4 do motivo da falha foi entregue pela opção (a). A migração `0002_motivo_da_pagina.sql` acrescenta a coluna `motivo TEXT`, nula, em `pagina_acompanhada`. `marcar_falhou(con, pagina_id, motivo)` grava um código do conjunto `MOTIVOS` (`banco/paginas.py:17-19`: `fora_do_ar`, `bloqueada`, `nao_e_texto`, `endereco_recusado`, `grande_demais`, `erro`) e recusa outro com `ValueError` (`banco/paginas.py:152-154`). A leitura `ok` limpa o motivo. `agenda/paginas._motivo` (`agenda/paginas.py:31-43`) traduz a exceção no código. `/sites` e a aba Programas mostram o motivo por `sites.motivo.<código>` em pt e en; página com motivo nulo (falhou antes da migração) mostra o texto genérico, `sites.motivo.desconhecido`. As escolhas e o que sobrou estão na D86 e na D87. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

## D73. Aviso de depreciação do Starlette nos testes (ADR 0021)

**Status:** aberta, para confirmar (o código segue a opção atual até o dono decidir)

**Contexto:** O `TestClient` do Starlette avisa em toda a suíte que pede `httpx2` ("install httpx2"). Hoje só é ruído. A ADR 0021 tirou o Dependabot, então a atualização de dependências é manual.

**Opções:** (a) anotar e tratar na atualização de dependências do fim da fase; (b) filtrar o aviso em `pyproject.toml`. Recomendação: (a): trocar de cliente é mudança de dependência e fica com o dono.

**Decisão provisória:** (a).

**Atualização de 2026-11-14 (T80d, leva N):** a atualização de dependências conferiu o aviso. O Starlette do lock (1.10.0, a mais nova do PyPI) só deixa de avisar se o `httpx2` estiver instalado: o `testclient.py` do Starlette tenta `import httpx2` e, sem ele, cai em `httpx` e avisa. O `httpx2` (2.16.0, exige Python 3.11 ou mais) é dependência nova, e a sessão não o acrescentou (A53). O aviso fica. Opções: (a) `httpx2` só no grupo dev: o `TestClient` o usa, o aviso some e o `src` segue em `httpx` 0.28.1; (b) migrar `src` e testes de `httpx` para `httpx2`, mudança grande de contrato do `HttpEducado`; (c) `filterwarnings` no `pyproject.toml` escondendo o aviso; (d) deixar o aviso. Recomendação: (d), e (a) numa tarefa própria só se o dono aprovar a dependência dev. Decisão provisória: (d). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

## D74. Busca real da leva B: resultado e as quatro correções (A13, A26, A27, A28, A29, T55b)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** Depois de juntar a leva J, a sessão rodou as 10 fontes novas na `fedora-dev` em 2026-11-14, com as empresas de exemplo de cada uma: cerca de 8,2 mil vagas (T55b, no plano). Quatro coisas divergiram, e a sessão achou a causa de cada uma:
- CIEE, estágio `parcial` em toda rodada. 134 de 3.962 vagas vêm com `nomeEmpresa` só com espaço (empresa confidencial) e eram descartadas. Cada página de `size=1000` tem cerca de 1,07 MB e cabe no teto de 5 MB: fecha a dúvida da T60.
- Workday, Mastercard `falhou`. O data center `wd1` estava em manutenção: o `POST /jobs` respondeu 303 para a página HTML "Workday is currently unavailable". O coletor lia isso como formato mudado.
- Eightfold, Microsoft parou no 429. Não veio do resolver (a A13 dizia que o resolver usou 1 s em vez de 5 s; a causa certa está na A28, e a A13 já foi corrigida). O mais provável é limite por IP na borda do Eightfold depois de 41 pedidos a 1 s em Bayer e Mercado Livre (confiança média-baixa): meia hora depois, dois pedidos com 30 s entre eles deram 200. O `Retry-After` não ficou registrado, porque o `Parou429` não guarda os cabeçalhos.
- IEL, vagas de só 2 das 19 UFs. Os números são reais (GO sem vaga, SP com 3). O sitemap guarda entradas velhas, e as 8 UFs fora da lista (BA, CE, MA, PI, RJ, RS, AP e RR) não estão no portal: `/BA` responde 500.

**Opções:**
- CIEE: (a) a vaga com empresa em branco entra como "CIEE" (o IEL usa "IEL <estado>" quando a empresa está em sigilo); (b) continuar descartando e tratar como `parcial` esperado.
- Workday em manutenção: (a) resposta que não é JSON vira `saude.erro_de_rede` (fora do ar); (b) chave nova `saude.manutencao`.
- Microsoft: (a) a Microsoft vai primeiro na ordem dos escopos do Eightfold e o `Parou429` guarda os cabeçalhos; (b) subir o `espera_s` da fonte inteira (deixaria o Mercado Livre bem mais lento).
- IEL: a (b) da R4 da T61, lista fixa de 19 UFs; as outras eram (a) UFs vindas das buscas (`ContextoColeta.ufs`), (c) UFs lidas do `sitemap.xml` e (d) as 27 UFs. Zero vagas só é `ok` quando a página traz "Nenhuma vaga encontrada"; sem o aviso, `formato mudou`.

**Recomendação:** (a) em CIEE, Workday e Microsoft; (b) no IEL, pelos motivos acima.

**Decisão provisória:** as recomendações, nas tarefas T116 (CIEE), T115 (Workday), T117 (Eightfold) e T118 (IEL). Desfazer: CIEE voltando a descartar; Microsoft subindo `espera_s` do `eightfold` em `fontes.json`; IEL pela (a) ou (c).

**Atualização de 2026-11-14 (T55c, leva L):** a sessão rodou as seis fontes novas da leva L na `fedora-dev`, com banco descartável (A47; no plano, T55c). Resultado fonte por fonte: Amazon BR `ok`, 407 vagas em 5 pedidos, todas com descrição; Google `ok`, 49 vagas em 1 pedido; Eureca `ok`, 9 vagas em 1 pedido, e o link `app.eureca.me/vagas/<id>` saiu no formato esperado; Abler `ok`, 50 vagas em 51 pedidos (2 min); Super Estágios `ok`, 50 vagas em 51 pedidos (1 min). As duas últimas param em 50 pelo orçamento de detalhes do executor (`MAX_DETALHES_POR_FONTE`, `agenda/execucao.py:54`), e o resto entra nas rodadas seguintes: aceito. Uma divergência: Oracle HCM deu `ok` com 0 vagas na Oracle e no JPMorgan, porque a descoberta sem filtro traz só as maiores localidades (18 e 40 facetas) e o Brasil não aparece. Com `keyword=Brazil` a faceta vem (Oracle `300000000106728`, JPMorgan `300000000289141`), e a lista filtrada só pela faceta traz 8 e 20 vagas. É o risco que a T66 tinha previsto, e a opção (b) dela passa a valer.
- Opções: (a) a descoberta repete uma vez com `keyword=<nome do país em inglês>` quando a faceta não vem, e só sem a faceta nas duas termina `ok` vazio; (b) manter e cadastrar só tenants cuja faceta venha; (c) marcar `parcial` quando o país não aparece. Recomendação e decisão: (a), na T126 (A47). Desfazer: tirar o segundo pedido de descoberta.
- Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (T126, leva M): conferência ao vivo do Oracle e das empresas.** Depois da T126 (a segunda descoberta por keyword está em `oracle_hcm.py:237-239`; a keyword vai entre aspas, `oracle_hcm.py:207-208`), o `scripts/conferir_empresas.py` rodou na `fedora-dev`: Oracle 8 vagas e JPMorgan 20, e a keyword com aspas foi aceita pela API. A rodada de 2026-11-14 (sábado, `dev` `fa22d1e`) conferiu as 83 empresas do `empresas.json`, o primeiro escopo de cada uma, com filtro `BR`, termo `developer` e teto de 5 pedidos por empresa (`MAX_PEDIDOS`, `conferir_empresas.py:27`). Resultado: 81 de 83 respondem. Contam como resposta o estado `ok`, `sem_mudanca` ou `parcial` e o motivo `saude.orcamento`, que é o teto de pedidos da própria conferência (`scripts/conferir_empresas.py:31,43-45`). Os 81 são 76 `ok` mais 5 `no_limite` por orçamento (Localiza&Co, Sicredi, Hapvida, Santander e Mercado Livre). Os 2 que não respondem são a Mastercard (manutenção do Workday) e a Microsoft (`no_limite` por `saude.parou_429`, que não conta).
- `ok`, empresas por fonte: Ashby 5, Greenhouse 15, Lever 8, SmartRecruiters 11, Gupy 25, InHire 2, Quickin 2, Recrutei 2, Sólides 2, Eightfold 2, Oracle HCM 2.
- `ok` com 0 vagas: Beep Saúde e CNA Idiomas (Gupy). O quadro estava vazio no dia; conferir de novo na próxima rodada antes de tirar (A51). Se der 0 outra vez, vira tarefa de tirar a empresa do `empresas.json`. Conferido de novo em 2026-11-14 (A56): não era quadro vazio, e a escolha está na D91.
- `no_limite` pelo teto de 5 pedidos do script, então o número de vagas é um mínimo: Localiza&Co, Sicredi e Hapvida (Gupy, mais de 500), Santander (Workday, mais de 80) e Mercado Livre (Eightfold, mais de 50).
- Mastercard (Workday, `wd1`) `falhou`, `saude.erro_de_rede`, "resposta não é JSON". Conferido à mão: o pedido volta 303 para a página de manutenção do Workday. É manutenção do centro de dados, passageira. A Mastercard é a primeira empresa do Workday no `empresas.json`, então é a sonda semanal do vigia (segunda, 06:23 UTC; `contexto_da_fonte` usa a primeira empresa de cada fonte, `scripts/vigia.py:130-133`); erro de rede não abre issue (`quebrou`, `vigia.py:105-114`), só entra no resumo.
- Microsoft (Eightfold) `no_limite`, `saude.parou_429`, 10 vagas de 24 no Brasil. Conferido à mão: o 429 vem e vai sem depender do ritmo (o mesmo pedido deu 429 e depois 200). O `fontes.json` já tem `por_escopo` para a Microsoft (espera de 5 s, uma vez por dia, para no 429) e o coletor já registra o 429. Aceito como está.
- `conferida_em` não mudou: o script só relata. Nada foi tirado do `empresas.json`.

**Atualização de 2026-11-14 (A56, leva O):** Beep Saúde e CNA Idiomas deram 0 vagas outra vez, e a conferência mostrou que o quadro não está vazio: o filtro `careerPageName` do portal da Gupy não casa essas duas empresas. O achado, as opções e a recomendação estão na D91.

## D75. ATS por empresa da leva B: InHire, Quickin, Recrutei e Sólides (T56, T57, T58, T59, T120)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar; as escolhas do redator trazem o status dentro de cada item

**Contexto e opções:**
- InHire. O link `/vagas/<jobId>` vem do código do site e responde 200, mas a página monta a vaga no navegador e a extensão do Chrome estava desligada: não foi vista aberta (A24, para conferir). A página de carreira que não é a `default` usa outro caminho, e o coletor a ignora. O identificador do tenant é sempre minúsculo: o resolver normaliza, o coletor não, então quem montar `empresas.json` grava em minúsculas. Sem `tenantName`, a empresa vira o identificador. O `.meta.json` leva o campo extra `cabecalho_do_pedido` (X-Tenant), fora de `CAMPOS_META`. Opções: (a) aceitar o campo como convenção dos coletores com cabeçalho de pedido e acrescentá-lo como opcional na lista de `scripts/capturar.py`, numa tarefa pequena; (b) tirar o campo do meta. Recomendação: (a). Status: escolha do redator, para confirmar.
- Quickin. O nome do escopo e os campos de salário seguem como o código os pôs. O teto de 100 páginas e 3.000 vagas por conta é palpite (a captura tinha 85 vagas) e fica por constante (A18); a opção (b) seria `max_pedidos` no `fontes.json`, que mudaria o orçamento das fontes já testadas. Recomendação: manter a constante. As sobras (host `jobs.quickin.io` e teste que não prova) estão na T120.
- Recrutei. O `remote` 1, 2 e 3 segue o apêndice; só o 0 (presencial) foi confirmado (A23). A empresa é `company_name` (a consultoria de RH), não o `client.name`. Os exemplos de 404 e de "vazio" foram montados à mão. Lista menor que `data.total` vira `parcial` com `saude.listagem_incompleta` (escolha do redator). O `detalhar` só pede no host `jobs.recrutei.com.br` (barreira de SSRF): vaga com link em domínio próprio fica sem descrição. O formato de `expired_at` e de `benefits` é suposto. Recomendação: conferir o `remote` ao vivo depois do merge.
- Sólides. O teto `MAX_PAGINAS = 200` fica por constante (A18). `createdAt` só com data vira meia-noite em Brasília. A moeda é BRL fixa e o período é deduzido. O 404 foi montado à mão: a captura só mostrou 400. Recomendação: manter.

**Decisão provisória:** o código segue como está. As sobras baixas de InHire, Quickin e Recrutei estão na T120 (A25); o exemplo da InHire com UUID corrompido também.

## D76. Portais da leva B: CIEE, IEL, Cia de Talentos e USP (T59, T60, T61, T62, T63, T116, T118, T119)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar; as escolhas do redator trazem o status dentro de cada item

**Contexto e opções:**
- CIEE. `size=1000` cabe no teto de 5 MB (cerca de 1,07 MB por página): fecha a dúvida da T60. Empresa em branco vira "CIEE" (D74).
- IEL. Fuso de `vagaInclusao` (-03:00 suposto) e linhas `T` do Flight com campos longos: para conferir na rede. Lista fixa de 19 UFs (D74); as outras opções e por que a (b) ficou estão na D74.
- Cia de Talentos. O prazo (hoje mais `countFinishDays`) usa o relógio do sistema (`_agora`), porque o contrato do coletor não recebe relógio (A19). Escolhas do redator, para confirmar: a `url` é o `opportunityHotsiteUrl`, senão o de inscrição, e `url_candidatura` é o `opportunityInscriptionUrl`; só `hiringTypeId` 1, 2 e 3 viram contrato, e o texto de `hiringType` (o 13, "Ensino Médio", por exemplo) vai para as etiquetas; `opportunityAreas` entra na descrição. Não achamos termos de uso; o `robots.txt` do site de marketing diz `Allow: /`.
- USP. O detalhe é lido dentro do `coletar`, porque o executor só detalha `UrlListada` (A20); a USP entra ativa na leva B; a empresa das vagas da FEA é "FEA-USP"; o contato da empresa publicado no mural fica na descrição. Os marcadores de lista vazia e a lista do IF (montada à mão a partir do JSON) estão para conferir ao vivo.

**Recomendação:** manter tudo; conferir ao vivo o que está marcado.

**Decisão provisória:** o código segue como está. As bordas pequenas (float inteiro, 404 na página 2, tag aninhada, pager do IF) estão na T119 (A25).

## D77. Fontes mundiais da leva B e o enriquecimento por escopo (T64, T65, T114, T115, T117)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto e opções:**
- Workday. Nome da empresa guardado na instância (D50, A16). Países das buscas, com Brasil quando a lista vier vazia, e local com país, para o rótulo "no Brasil" e o contrato CLT funcionarem nas vagas do Santander (A17, T115). Um escopo por empresa e país: a fase 1 ainda não saiu, então as ocorrências com o nome de escopo antigo não se migram (A33). Resposta 521 ou 422 fica `saude.erro_de_rede`, sem chave nova (A22). Achados da T64: `total` vem 0 nas páginas com `offset` maior que 0, há tenant cuja faceta só tem `locations`, e `postedOn` é relativo (apêndice 3.3).
- Eightfold. Sem país nas buscas, busca o Brasil, também na execução agendada sem busca ativa (A21). O que se perdeu da primeira entrega foi comparado com a seção 3.3 e corrigido (apêndice, "corrigido pela captura de 2026-11-13"). Microsoft primeiro e `Parou429` com cabeçalhos: D74, T117.
- Passo 4 do enriquecimento (A14, A32, T114). Hoje a parada de um escopo tira a fonte inteira do passo 4, e o detalhe sai no ritmo da fonte: Mercado Livre, NVIDIA e Microsoft quase nunca ganham descrição, e os detalhes da Microsoft saem a 1 s em vez de 5 s. Opções: (a) parada que vale para a fonte toda (orçamento, bloqueio, limite) tira a fonte inteira; intervalo e 429 tiram só o escopo onde apareceram; o detalhe usa o `espera_s` e o `para_no_429` do `por_escopo`, e o orçamento de pedidos da fonte é um só, somado entre os escopos; (b) deixar como está. Recomendação: (a). A sessão já disse (A15) que o passo 4 detalha a `VagaColetada` sem descrição (D52).

**Decisão provisória:** (a), na T114 e na T115. Desfazer: voltar a parar a fonte toda no passo 4.

**Atualização de 2026-11-14 (A35 a A37, leva K):** a T114, a T115 e a T117 foram entregues e juntadas na `dev`. Status das duas decisões abaixo: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.
- Retry-After no log (R4 da T117, A36). A T117 deixou o `Retry-After` fora do log: o executor não tem logger e o enriquecimento registra só o nome do tipo (`agenda/execucao.py:273`). Opções: (a) o executor registra `str(erro)` quando o escopo para por `Parou429`, `LimiteAtingido` ou `Bloqueio`, e o `Parou429` que escapa do `coletar` vira `saude.parou_429` em vez de `saude.excecao:Parou429` (`executor.py:140-146`); (b) só o log de `agenda/execucao.py`; (c) campo novo no contrato. Recomendação e decisão: (a), na T123, junto da T106. Desfazer: (b) ou (c).
- Nome do país no Workday (T115, A37). O coletor importa o mapa privado `_PAISES` de `nucleo/tratamento/locais.py` (`workday.py:29,44`). Opções: (a) manter o import privado; (b) `nome_do_pais` público em `locais.py`, mais "Estados Unidos da América" reconhecido e sigla de estado americano que parece UF ("Columbus, MS") sem virar vaga no Brasil em escopo de fora. Recomendação e decisão: (b), na T124. Desfazer: (a).

**Atualização de 2026-11-14 (A36, T106-123, leva L):** a T123 entregou a opção (a) do `Retry-After` no log: `_registrar_parada` (`nucleo/coletores/executor.py:158`) põe no log o texto do `Parou429`, do `LimiteAtingido` e do `Bloqueio` que param um escopo, e o `Parou429` que escapa do `coletar` vira `saude.parou_429` (`executor.py:149-150`), que só vai para o resumo do vigia e não abre issue (travado por `test_parou429_que_escapa_do_coletar_nao_abre_issue`). Falta a listagem: `juntar_paginas` (`nucleo/coletores/base.py:118-125`) captura os três erros e devolve só a chave `saude.*`, então o 429 de uma listagem segue sem `Retry-After` no log. Opções: (a) `log.warning` com o texto do erro nos três `except`; (b) campo novo em `ResultadoEscopo`. Recomendação: (a), na T126 (A46). A T124 entregou `nome_do_pais` público e "Estados Unidos da América" como US (`nucleo/tratamento/locais.py:139`; a T124 acrescentou `irlanda` e `uruguai` para o nome em português de todo código voltar ao mesmo código). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

## D78. Leva K e as sobras da leva J (A25, A30, A31, A34, T106, T119, T120, T121)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:**
- A25. As sobras baixas da leva J viram tarefas pequenas por assunto: T119 (Cia de Talentos, Sólides e USP), T120 (testes que não provam e exemplos da Quickin, Recrutei e InHire) e T121 (vigia: "voltou" só com o detalhe conferido). Os nomes privados do executor que `scripts/vigia.py` importa (`_PARA_DETALHES`, `_motivo_do_detalhe`, `_motivo_do_escopo`) entram na T106, e o teste de varredura dela também olha `scripts/`, porque o ruff e o mypy de `src` não avisam se alguém os renomear.
- A30. A leva K junta: esta REG8, as correções da busca real (T115 a T118), o enriquecimento por escopo (T114), as sobras baixas da leva J (T119 a T121) e as tarefas livres que não brigam por arquivo (T104, T105, T107, T113 e a trinca da descoberta T108 a T110 numa tarefa só). T106, T111 e T112 ficam para a leva seguinte, porque mexem nos mesmos arquivos que outras desta leva.
- A31. Descoberta: seguem as recomendações da D71 (só o 503 e o limite adiam até o dia seguinte; um escopo por etapa no ramo da Gupy; `_bater` público com teste). Primeira execução: segue a da D62 (um só "Buscar agora"). Sem duplicar aqui o que já está nelas.
- A34. A leva K sai com 14 tarefas, até 8 ao mesmo tempo: Opus em T114, T115, T117 e na trinca da descoberta; Sonnet no resto; revisor do mesmo modelo; effort `high` em todas.

**Opções:** (a) como decidido; (b) esperar o dono para cada sobra baixa. Recomendação: (a): são correções pequenas, cada uma com teste, e não mexem em contrato público.

**Decisão provisória:** (a). Desfazer: não há o que desfazer; as tarefas são independentes e podem ser descartadas uma a uma.

## D79. Sobras da leva K aceitas (A38, T108, T114 a T121)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** as revisões da leva K deixaram estas sobras. A sessão as aceita sem mexer no código; cada uma vira tarefa pequena se o dono quiser:
- Um 429 no detalhe deixa sem descrição, naquela execução, as vagas do escopo que já estavam dentro do limite de 50 por fonte; as vagas dos outros escopos não ocupam o lugar, e a próxima execução as pega (T114).
- Vaga do CIEE com `nomeEmpresa` `null` (não em branco) segue pulada como `parcial`; a captura real mostra a empresa em sigilo como `" "`, e falta conferir na rede se algum dia vem `null` (T116).
- Detalhe do Workday com resposta que não é JSON volta sem descrição (T115).
- "Evergreen", vaga contínua do Santander, vira cidade (T115).
- O aviso "Nenhuma vaga encontrada" do IEL é procurado no HTML inteiro, e a posição e o texto reais nunca foram vistos na rede (T118).
- O seletor da paginação da USP (`ul.pager li a[href]`) ainda não foi visto ao vivo (T119).
- A mudança em `scripts/capturar.py` para não estragar UUID (a limpeza deixa de achar telefone dentro de UUID); só o UUID padrão 8-4-4-4-12 foi tratado (T120).
- A issue do vigia pode perder a marca "detalhe" quando o corpo é reescrito toda semana por outro motivo, e a semana seguinte fecha sem conferir o detalhe (T121).
- O `Retry-After` entra cru no texto da exceção (`nucleo/http.py:397-401`); um valor muito longo deixaria o texto grande (T117).
- O recuo de 1 h da descoberta para erro que não é 503 nem limite (T108 a T110; D71).

**Opções:** (a) aceitar todas; (b) abrir tarefa para cada uma. Recomendação: (a), pelo custo baixo de cada uma. As sobras que valem tarefa já estão no plano: T122 a T125.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D80. Eureca pela API do aplicativo de candidatos (A42, T70)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** o caminho público da Eureca estava em aberto desde o apêndice. A conferência de 2026-11-13 achou a API do aplicativo de candidatos (`candidate-api.eureca.me/opportunities`), que responde sem login. O escopo é um só. Os termos de uso da Eureca são restritivos (a cláusula 7 pede consentimento prévio e expresso), mas manter a Eureca na fase 1 já foi decisão do dono (Q6, de 2026-11-13), com chave liga/desliga, ritmo educado, link para a vaga original e aviso no README; Abler e Gupy seguem a mesma decisão. O link da vaga (`app.eureca.me/vagas/{id}`) foi deduzido do código do aplicativo e não foi aberto: fica para conferir na busca real.

**Opções:** (a) a Eureca entra pela API do aplicativo; (b) tirar a Eureca da fase 1, com o motivo no apêndice. Recomendação: (a), porque o dono já decidiu mantê-la e não há login a contornar.

**Decisão provisória:** (a), na T70. Desfazer: (b).

**Atualização de 2026-11-14 (T70, T55c, leva L):** a T70 entregou o coletor e a busca real o confirmou.
- O que a T70 achou (`portais/eureca.py:29-34`): `GET https://candidate-api.eureca.me/opportunities?page=N&pageSize=200`, JSON sem login, `{items, total, page, pageSize}`; teto local de 10 páginas (`MAX_PAGINAS`, 2.000 vagas; hoje há 9) com `saude.limite_atingido` ao chegar nele. A lista já traz a descrição, sem `ETag` nem `Last-Modified`, então não há pedido condicional. `/programs` ficou de fora: lista programas (grupos de vagas), e cada vaga já traz `programName`. Escolha: manter assim.
- A busca real (T55c): `ok`, 9 vagas em 1 pedido, e o link `https://app.eureca.me/vagas/<id>` saiu no formato esperado. Falta só abrir um link no navegador. O `pageSize=200` explícito foi aceito (a busca real o mandou).
- Pergunta ao dono, que ficou: as notas da conferência de 2026-11-13 recomendam pedir autorização à Eureca antes de ligar o coletor (cláusulas 7.2 e 7.3 dos termos; o endereço foi achado lendo o código do aplicativo). O dono decidiu manter a fonte (Q6/A42), mas a pergunta da autorização não foi respondida. Opções: (a) manter a Eureca ligada por padrão, como a Q6 decidiu; (b) deixar a fonte desligada por padrão até a Eureca autorizar, com o código e o interruptor prontos e o aviso no README dizendo por quê; (c) tirar a Eureca da fase 1. Recomendação: (b), porque a busca real deu certo, o código fica pronto sem perda e os termos são respeitados até a resposta.
- Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar; a escolha entre (a), (b) e (c) é do dono. Desfazer (b): ligar o interruptor.
- Sobras da T70 aceitas (D82): `workModels[]` com mais de um valor vira tarefa da T126; `locations.cities` com mais de uma cidade segue lida só por `cityName`.

**Atualização de 2026-11-14 (A50, leva M):** a sessão escolheu a opção (b), que era a recomendação: a Eureca nasce desligada até a empresa autorizar, com o código e o interruptor prontos. Motivo: as notas da conferência apontam as cláusulas 7.2 e 7.3 dos termos, e na dúvida o joBot respeita os termos. É a T130 (D85): um campo opcional no `fontes.json` diz se a fonte nasce ligada, e a semeadura da tabela `fonte` o usa só ao criar a linha, então quem já tem a linha mantém a escolha que fez. O README (T79) explica o motivo e ensina a ligar. A escolha continua sendo do dono. Desfazer: tirar o valor desligado da Eureca no `fontes.json` (uma linha). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (T130, leva N):** a T130 foi entregue e juntada na `dev`. O campo opcional `ligada_padrao` (booleano, padrão verdadeiro: `nucleo/coletores/base.py:80`) está no `fontes.json`, e só a Eureca o traz como `false` (`fontes.json:176`). O carregador recusa valor que não seja `bool`, com `ValueError` que cita a chave (`registro.py:29-30`). A semeadura grava `ligada` só ao criar a linha (`banco/cadastros.py:82-96`: o `ON CONFLICT DO UPDATE` não toca em `ligada`), então o banco que já tem a linha da Eureca mantém a escolha que fez. Quem já rodou o joBot antes continua com a Eureca ligada e a desliga em Configurações, na aba de fontes, se concordar com a A50. O nome `ligada_padrao` ficou como escolha do agente (D86). Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar; a escolha entre (a), (b) e (c) continua sendo do dono.

## D81. Leva L: o que entrou e o que ficou para a leva M (A41, A43)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** a leva L roda até 8 tarefas ao mesmo tempo: os seis coletores que faltam (Oracle HCM, Google, Amazon, Super Estágios, Eureca e Abler), o guia de conserto de fonte (T83), os nomes públicos junto com o log do 429 (T106 e T123, numa tarefa só), o DNS compartilhado (T111), a tela de empresas sugeridas (T74), os textos da tela (T122), o país no Workday (T124), as sobras pequenas (T125) e os registros (REG9). Ficam para a leva M, por mexerem nos mesmos arquivos de tarefas desta leva: a T75 (mexe em `rotas/vagas.py`, como a T106), a T112 (mexe em `tests/unidade/test_paginas.py`, como a T111) e a T76 (`empresas.json`, depende do Oracle HCM).

**Opções:** (a) como decidido; (b) rodar a T75 e a T112 junto, aceitando conflito de arquivo. Recomendação: (a): a leva M sai logo depois, e conflito de arquivo custa mais que a espera.

**Decisão provisória:** (a). Desfazer: tirar uma tarefa da leva (a branch fica, sem merge).

**Atualização de 2026-11-14 (A44, A47, A48, leva L):** a leva L foi juntada na `dev` (commit `b7d542c`), com 13 tarefas aprovadas e a REG9 com duas ressalvas médias no `registros/padroes.md` (as cinco lições perdidas e o limite de 350 caracteres por linha). Bateria: 3.326 testes de unidade, 82 de tela, ruff e mypy verdes. A `dev` subiu ao GitHub como cópia (push simples, sem PR). A busca real das seis fontes novas (T55c) está na D74 e na D80. A leva M foi lançada com seis tarefas a partir de `b7d542c` (A48): T75 junto com a T112 (opção (a) da D72, e as outras faltas da D72), T76, T77, T126 (D82 e D83), T127 e esta REG10. O que a leva L deixou aceito está na D82; o que virou tarefa, na D83.

**Atualização de 2026-11-14 (A49, leva M):** a leva M foi juntada na `dev` (commit `fa22d1e`): 6 de 6 tarefas aprovadas, só com problemas baixos (T75 com a T112, T76, T77, T126, T127 e REG10). Bateria: 3.528 testes de unidade e 91 de tela, ruff e mypy verdes. A `dev` subiu ao GitHub como cópia (push simples, sem PR). A conferência ao vivo do Oracle e das empresas está na D74. O que a leva M deixou aceito está na D84; o que virou tarefa, na D85. A leva N tem seis tarefas: T79 (README e CHANGELOG), T80d (dependências, o segundo passo da T80), T128 (sobras da leva M), T129 (cópias locais nas rotas), T130 (Eureca desligada por padrão) e esta REG11. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (A53, leva N):** a leva N foi juntada na `dev` (commit `10daf60`): 6 de 6 tarefas (T79, T80d, T128, T129, T130 e REG11), sem conflito. Bateria: 3.588 testes de unidade e 91 de tela, ruff e mypy limpos (o log da junção está guardado com a sessão). A `dev` subiu ao GitHub como cópia (push simples, sem PR). A T79 saiu "não aprovada" nas três rodadas de revisão por uma ressalva média que já existia antes dela: a frase de privacidade do README diz que o joBot só faz pedidos às fontes, ao Banco Central e ao GitHub, e a descoberta semanal pelo Common Crawl, ligada por padrão, também faz pedidos. Foi juntada assim mesmo, e a correção é a T131. O que a leva N deixou aceito está na D86; o que virou tarefa, na D87; as dependências, na D88. A leva O tem duas tarefas: T131 (sobras da leva N) e esta REG12. Depois dela, o que sobra da fase 1 precisa do dono: T81 (rotular o gabarito) e, depois dela, T37 e T78; o roteiro da T80; a T132; e o PR para a `main`. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

**Atualização de 2026-11-14 (A54 a A56, leva O):** a leva O foi juntada na `dev` (commit `0c5ddf1`): T131 e REG12 aprovadas com ressalvas baixas. Bateria: 3.596 testes de unidade, ruff e mypy verdes; na tela, 1 de 91 falhou numa rodada e as duas seguintes deram 91 de 91 (teste instável; a bateria só guardava a última linha, e o script agora mostra o nome do teste que falhar). A `dev` subiu ao GitHub como cópia (push simples, sem PR). Depois veio a T133 (`a51cb69`), com as ressalvas da T131. O que a leva O deixou aceito está na D89; a T133, na D90; a conferência ao vivo da Gupy, na D91. A REG13 registra tudo isso. Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

## D82. Sobras da leva L aceitas (A45, T66 a T74, T83, T106, T123)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** as revisões da leva L deixaram estas sobras. A sessão as aceita sem mudar o código; cada uma vira tarefa pequena se o dono quiser (a origem de cada item está entre parênteses):
- Oracle HCM (T66): só tenants em `*.oraclecloud.com` (`oracle_hcm.py:37`); o `site_number` aceito é `[A-Za-z0-9_]{1,50}` e o caminho do resolver é `/hcmUI/CandidateExperience/<idioma>/sites/<site>`, escolhas do coletor a partir de `CX_45001` e `CX_1001`; vaga com o Brasil só como local secundário entra (o filtro BR trouxe uma vaga do México) e o tratamento decide; `PostingEndDate` e `ExternalPostedEndDate` vieram nulos em todas as amostras, então o prazo nunca foi visto preenchido (`oracle_hcm.py:151,309`); o nome da empresa vem do cadastro (D50). O segundo pedido de descoberta é da T126 (D83).
- Google (T67): o filtro é só `country == 'Brazil'` (`google.py:31`), e as vagas remotas do mundo ficam fora; o pedido é condicional (`If-Modified-Since`: `google.py:152` chama `http.pedir` com `condicional=True` e `teto_bytes`, e o 304 vira sem mudança), e o que não aceita condicional é a leitura em fluxo (`ler_em_fluxo`, `nucleo/http.py:331`), que o Google não usa; quando o feed muda, o corpo de uns 20 MB (teto de 32 MB) fica inteiro na memória; se o feed trocar `Brazil` por `BR` ou `Brasil`, a coleta dá `ok` vazio e o vigia pega a fonte que zerou. A seção 3.4 do apêndice não traz os valores de `remote` e `isRemote`, e o `If-Modified-Since` segue como "a confirmar" (a captura não viu o 304).
- Amazon (T68): o escopo é o código ISO de 2 letras (`BR`), convertido para ISO-3 (`BRA`) por uma tabela de 18 países (`amazon.py:35`); a API não traz salário, e `url_candidatura` fica vazia (a vaga usa o link do `job_path`); o teto é de 30 páginas (`MAX_PAGINAS`, `amazon.py:32`, `saude.limite_atingido` ao passar); o pedido é condicional em todas as páginas, e um 304 só numa página posterior deixa o escopo `parcial` com `saude.listagem_incompleta` (`amazon.py:182`, coberto por `test_304_depois_de_pagina_nova_fica_parcial`); `job_schedule_type` (`full-time`, `part-time`) não vira contrato do rotulador (`amazon.py:127`); só se viu `ONSITE` em `locations[].type`, e `VIRTUAL` ficou só nos testes.
- Super Estágios (T69): 404 e 410 no `detalhar` devolvem `None` (cache de 30 dias, DR-70) e 403, 429 e 5xx sobem; sem pedido condicional (o sitemap só mostrou `cache-control`); `lastmod` e `datePosted` sem fuso valem meia-noite de Brasília (`shortcut:` no código, para conferir na rede); URL do sitemap fora do padrão `/vaga/<número>` é descartada e contada em `saude.sem_detalhe_n`. O `CONFIDENCIAL` vira tarefa (D83).
- Eureca (T70): `/programs` fora; teto de 10 páginas; `workModels[]` e `locations.cities` com mais de um valor (a parte do `workModels` vira tarefa); `_reais` devolve `float` quando a divisão não é exata (`eureca.py:64`), aceito porque `SalarioBruto` é `float` e a conversão por `Decimal(str(v))` é exata com 2 casas; o teto de páginas reusa `saude.limite_atingido`, cujo texto (`comum.json:84`) fala da espera pedida pela fonte, como Workday, Sólides e CIEE fazem; o total maior que o lido usa `saude.listagem_incompleta`, que a T122 reescreveu e agora serve. Os termos seguem na D80.
- Abler (T73): vaga com `status` "Em andamento" (o único valor visto) não é filtrada; se aparecer um segundo valor, passa a devolver `None` para status não vazio fora dos abertos. A fixture `vaga.html` leva o script `window.__NUXT__` de volta à mão depois do `capturar.reduzir` (R3, descrito no `.meta.json`); refazer pelo `capturar.py` se ele passar a guardar scripts pedidos.
- Guia de conserto (T83): `docs/consertar-fonte.md` e `.en.md` usam âncora `<a id>` com o mesmo id nas duas línguas em vez de títulos iguais (o título traduzido nunca bate); o teste compara a sequência de ids e exige título diferente. O guia diz que PR de código só entra depois da fase 8, como o CONTRIBUTING e a ADR 0018; a parte da D33 está na D33. A frase "costuma ser uma empresa que trocou de identificador" (`saude.empresa_nao_encontrada`) é do redator. O apêndice e a seção 2.4 estão só em português, e o guia em inglês avisa. O vigia não foi rodado ao vivo. O guia ainda diz que, se todas as vagas ficam ilegíveis, a fonte fica "Parcial", mas o Greenhouse dá `falhou` nesse caso (`greenhouse.py:105-106`), e diz que a issue do vigia vale para todo motivo, mas o `quebrou` de `scripts/vigia.py:105-114` só abre issue para quatro: tarefa pequena de texto, se o dono quiser.
- T106-123: o 429 da listagem segue sem `Retry-After` no log (a T126 faz, D77); a varredura de nomes privados de `tests/unidade/test_nomes_publicos.py` só pega `from X import _nome`, não `modulo._nome` nem `import x as y`; `agenda/execucao.py:57` ainda tem a cópia `_PARA_DETALHES` ao lado de `executor.PARA_DETALHES`; `Parou429` que escapa do `coletar` vira `saude.parou_429` e não abre issue no vigia.
- T111: o salto recusado pelo DNS leva a URL de origem só em `add_note` (a T126 a devolve à mensagem, D72).
- T122, T124, T125: o teste de texto da T122 só barra a redação antiga (palavras proibidas); "Evergreen" do Santander ainda vira cidade; em escopo US a UF da vaga ("Columbus, MS") se perde porque o país escrito vence a sigla; o nome em português de cada código em `nucleo/tratamento/locais.py:139` depende do último alias de cada grupo e de `_ACENTOS`, e só BR, US, FR e ZZ têm teste do nome; o vermelho do item 2 da T125 é uma exceção do `fromisoformat`, não uma asserção.

**Opções:** (a) aceitar todas; (b) abrir tarefa para cada uma. Recomendação: (a), pelo custo baixo de cada uma. As que valem tarefa estão na D83.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D83. Sobras da leva L que viram tarefa na leva M (A46, A47, T126, T127)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** duas tarefas novas, livres, na leva M (no plano, T126 e T127).
- T126, coletores: (1) Oracle HCM, segundo pedido de descoberta com `keyword=<nome do país em inglês>` quando a faceta do país não vem (D74), com `nome_em_ingles` público em `locais.py`; (2) Amazon, `publicada_em` à meia-noite de Brasília, não de UTC (hoje cai no dia anterior); (3) Super Estágios, a empresa `CONFIDENCIAL` (`super_estagios.py:206`) vira `Super Estágios`, como o CIEE faz com `CIEE`, para vagas de empresas diferentes não se misturarem; (4) Eureca, `workModels` com mais de um valor deixa `modalidade_declarada` vazia, como a Amazon faz com tipos mistos; (5) as docstrings de `_FormatoMudou` do Google e da Abler dizem o que de fato levanta, e o sitemap da Abler só com `<url>` sem `<loc>` termina `falhou`, não `parcial` (`abler.py:124`); (6) a mensagem do `ErroDeRede` do salto recusado volta a trazer a URL de origem (D72); (7) `juntar_paginas` registra no log o texto do erro (D77).
- T127, tela e documentos: (1) `painel/rotas/sugeridas.py` usa `relogio_do_painel` e os nomes públicos da T106 no lugar das cópias locais (hoje `_relogio` em `sugeridas.py:48`); (2) na aprovação da Gupy, `ValueError` do resolver dá 422 com mensagem própria, e só falha de rede dá 502 (hoje qualquer exceção vira 502, no `except Exception` de `aprovar_sugestao`); (3) a Gupy grava o identificador que o resolver devolve, em minúsculas (D45 de `empresas.py`); (4) sugestão de empresa removida (D71) não faz pedido à Gupy antes de aprovar; (5) `.github/CONTRIBUTING.md` e `.en.md` perdem a frase de que os comandos exatos serão documentados quando o código existir (linha 38 dos dois), porque o guia já os traz.

**Opções:** (a) uma tarefa por assunto (T126 e T127); (b) deixar tudo aceito, na D82. Recomendação: (a): cada item é pequeno, tem teste e não muda contrato público. A T126 é Opus (a mudança do Oracle mexe na descoberta); a T127, Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva M e mover o item para a D82.

**Atualização de 2026-11-14 (T126, T127, leva M):** as duas tarefas foram entregues e juntadas na `dev` (`fa22d1e`), com problemas só baixos.
- T126: os 7 itens estão feitos. Oracle HCM repete a descoberta uma vez com `keyword` quando a faceta do país não vem (`oracle_hcm.py:237-239`; `nome_em_ingles` público em `locais.py`), com três exemplos novos vindos das respostas reais da T55c; Amazon à meia-noite de Brasília; Super Estágios com `CONFIDENCIAL` virando `Super Estágios`; Eureca sem modalidade declarada com mais de um `workModels`; docstrings e sitemap do Abler sem `<loc>` como `falhou`; salto recusado com a URL de origem; `juntar_paginas` com o texto do erro no log (`base.py:100-101`). O que sobrou está na D84 e na D85.
- T127: os 5 itens estão feitos, e o item 3 pediu o parâmetro `identificador_novo` em `banco/sugeridas.aprovar` (R3, D84). A chave `sugeridas.erro.pagina` (422) entrou em pt e en.
- REG11: corrigiu a frase do Google na D82 e acrescentou a T66 ao `depende_de` da T126. A revisão da REG10 apontou os dois como baixos e não os corrigiu, e a A49 mandou os dois para a REG11.
- Status: decidido pela sessão em 2026-11-14 com o dono fora, para confirmar.

## D84. Sobras da leva M aceitas (A49, T75, T76, T126, T127, REG10)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** as revisões da leva M deixaram estas sobras. A sessão as aceita sem mudar o código; a tarefa de origem está entre parênteses:
- T75: página sem `Content-Type` segue lida como HTML (`nucleo/coletores/paginas.py:99-105`: sem o cabeçalho a checagem de tipo não roda e o texto passa por `para_texto(..., "html")`); `adicionar_pagina` com o mesmo endereço reativa a página desativada (`banco/paginas.py:48`, `ativa=1`; o docstring de `desativar_pagina` diz isso).
- T76, valores que são meus e sem fonte no apêndice, para o dono rever pelo painel: `area` de DIEFRA (`serviços (conservação, manutenção e facilities)`, deduzida dos títulos das vagas), de UCM Business Solutions (`tecnologia (consultoria)`) e de Riachuelo (`varejo (moda)`); `pais` null nas 8 empresas multinacionais ou globais (Mastercard, Santander, Mercado Livre, NVIDIA, Microsoft, Bayer, Oracle e JPMorgan Chase), como Bosch Group e ServiceNow já tinham, enquanto as 8 brasileiras da leva B são `BR`; a entrada `carreiras` da InHire (`InHire (carreiras da própria InHire)`, 3 vagas), porque o apêndice a lista entre as vistas. Se o dono não quiser uma empresa, remove pelo painel.
- T76: o teto `MAX_PEDIDOS = 5` por empresa (`scripts/conferir_empresas.py:27`) faz quadro grande (Gupy, Workday, Eightfold) sair `no_limite`, e o número de vagas é um mínimo; a rodada ao vivo teve 5 empresas assim (D74). Ajustar o teto só se fizer falta.
- T126: o exemplo da JPMC sem filtro (resposta com 40 facetas e 25 vagas) não entrou em `tests/fixtures/oracle_hcm/`, porque `capturar.reduzir` corta só a maior lista e o resultado não cabe em 50 KB; a lógica é a mesma para qualquer empresa e está provada pelo exemplo real da Oracle, e a JPMC segue coberta pelo exemplo antigo. Mudar o `reduzir` é contrato do script (R4); o Amazon usa o horário de Brasília para todo país (atalho comentado em `amazon.py:41-43`; a alternativa é o fuso do país da vaga); o log de parada de `juntar_paginas` (`base.py:100-101`, `listagem parou: <Tipo>: <texto>`) não traz fonte nem escopo, só a URL que vem no texto do erro.
- T127: o parâmetro opcional `identificador_novo` em `banco/sugeridas.aprovar` (`banco/sugeridas.py:76`) está fora da lista de arquivos da tarefa (R3) e é aditivo; a alternativa seria um `UPDATE` da empresa na rota, que não é atômico.
- REG10: `registros/padroes.md` fica no teto de 64 linhas, com linhas longas (A44), porque quebrar estoura o teto.

**Opções:** (a) aceitar todas; (b) abrir tarefa para cada uma. Recomendação: (a) para as de código e de teste; os valores de `area`, `pais` e a entrada `carreiras` ficam como pergunta ao dono, que revê pelo painel.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D85. Sobras da leva M que viram tarefa na leva N (A49, A50, T128, T129, T130)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** três tarefas novas, livres, na leva N (no plano, T128 a T130).
- T128, sobras da leva M: (1) motivo da falha de página (R4 da T75, D72), com coluna `motivo` por migração nova em `pagina_acompanhada`, gravada por `marcar_falhou`, limpa pela leitura `ok` e mostrada em `/sites` e na aba Programas; (2) a aba Programas mostra `falhou` também na página que já mudou antes (`templates/vagas/miolo.html`); (3) teste próprio de `ultimas_diferencas` (`banco/paginas.py:96`); (4) `executar_paginas` relê `paginas_ligadas`, como `executar_descoberta` (hoje só o laço da agenda respeita a chave, e nenhuma rota chama a função direto); (5) `conferir_empresas.py` usa `copy.copy(coletor)` (D50, D60), e o teste de que não escreve no `empresas.json` vira teste de efeito, com sha256 antes e depois; (6) `test_empresas_json_tem_67` ganha nome que diz o que confere; (7) teste do 404 na descoberta com keyword do Oracle HCM (`oracle_hcm.py:219`, hoje sem teste).
- T129, cópias locais nas rotas: `_relogio` em `buscas.py`, `configuracoes.py`, `empresas.py` e `primeira_execucao.py` vira `relogio_do_painel`, e `_SemValidadores`, hoje em `sugeridas.py` e `empresas.py`, fica numa versão só.
- T130, Eureca desligada por padrão (A50, D80 opção (b)): campo opcional no `fontes.json`, validado pelo carregador, usado pela semeadura da tabela `fonte` só ao criar a linha.

**Opções:** (a) uma tarefa por assunto (T128, T129 e T130); (b) deixar tudo aceito, na D84. Recomendação: (a): cada item é pequeno e tem teste. A T128 mexe em migração, tela e `conferir_empresas.py`, e a revisão dela é Opus; a T129 e a T130 são Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva N e mover o item para a D84.

## D86. Sobras da leva N aceitas (A52, A53, T79, T80d, T128, T129, T130)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** as revisões da leva N deixaram estas sobras. A sessão as aceita sem mudar o código; a tarefa de origem está entre parênteses:
- T128: o `ErroDeRede` que vem de "resolve para host local" ou de redirecionamento para host local cai em `fora_do_ar` (`agenda/paginas.py:41-42`), e a tela diz "parece estar fora do ar". Distinguir pediria código novo ou ler a mensagem do erro.
- T128: o conjunto fechado de códigos ficou em seis, `fora_do_ar`, `bloqueada`, `nao_e_texto`, `endereco_recusado`, `grande_demais` e `erro` (`banco/paginas.py:17-19`). Além dos três do exemplo do plano (`fora_do_ar`, `bloqueada`, `nao_e_texto`), entraram `endereco_recusado` (o `ValueError` de `verificar`), `grande_demais` (`RespostaGrande`) e `erro` (a exceção inesperada).
- T128: página que falhou antes da migração (motivo nulo) mostra o texto genérico antigo (`sites.motivo.desconhecido`), não um motivo inventado.
- T128: o texto novo de `/sites` e da aba Programas não tem teste de tela (Playwright); a cobertura é de rota, com `TestClient`. O 404 e o 410 da página seguem como `fora_do_ar`, e o 429 como `bloqueada`.
- T129: o módulo novo `painel/sem_validadores.py` (classe `SemValidadores`, sem o sublinhado, porque duas rotas a importam) foi aceito. As cópias de `_SemValidadores` dentro de `tests/` ficam, porque cada teste tem o seu dublê.
- T130: o nome do campo é `ligada_padrao`; o banco que já tem a linha da Eureca mantém a escolha dele (D80).
- T79: a data da 0.1.0 (2026-11-14) é provisória e se acerta na publicação (T132). Endurecer o regex do teste de ADRs do CHANGELOG fica como está.
- T80d: o `setup-uv` fica na v7, como a ADR 0021 e o plano mandam (D88).
- A52: `.env` e `.env.*` entram no `.gitignore` por prevenção, com a exceção `!.env.example`. Não havia `.env` na pasta do repositório, então nada vazou. Desfazer: apagar as linhas do `.gitignore`.

**Opções:** (a) aceitar todas; (b) abrir tarefa para cada uma. Recomendação: (a), pelo custo baixo de cada uma. As que valem tarefa estão na D87.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D87. Sobras da leva N que viram tarefa (A53, T131, T132)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** duas tarefas novas, livres, na leva O (no plano, T131 e T132).
- T131, sobras da leva N: (1) o texto de privacidade do README em pt e en (item "Só pedidos de busca", `README.md:318` e `README.en.md:318`) e o texto do painel (`configuracoes.privacidade.telemetria`) esquecem a descoberta semanal pelo Common Crawl, que vem ligada por padrão (`banco/cadastros.py`, `descoberta_cc_ligada`; hosts em `nucleo/coletores/descoberta_cc.py`); a tarefa levanta todo pedido de rede que o joBot faz sozinho e completa os quatro textos; (2) o teste da Eureca de `tests/unidade/test_documentos.py` perde o `skip`, porque a T130 já entrou; (3) o CHANGELOG em pt e en troca os itens que citam D1 e D3 por número por frases com o efeito, ou os tira; (4) teste novo de que todo código de `MOTIVOS` tem a chave `sites.motivo.<código>` em pt e en; (5) o `except` que o `ruff format` partiu em `agenda/paginas.py` volta a uma linha; (6) o teste da migração `0002` aplica só o arquivo dela; (7) o teste de cópias nas rotas olha também `AsyncFunctionDef` e prova por AST que nenhuma rota lê `app.state.relogio`; (8) o teste da Eureca em `test_cadastros.py` deriva o total de fontes ligadas do `fontes.json`, sem o 27 fixo; (9) `_ambiente`, `_rodar` e `_no_linux` (em `configuracoes.py` e `primeira_execucao.py`) e `_um` (em `buscas.py` e `detalhe.py`) ficam numa versão só, se os corpos forem iguais.
- T132, status da fase 1 nos documentos: `CONTRIBUTING.md`, a ADR 0017 e a wiki ainda dizem "em andamento". Atualizar quando a fase fechar, junto com a data da 0.1.0 no CHANGELOG em pt e en. Roda antes do PR para a `main`, depois da T80 e da T81.

**Opções:** (a) uma tarefa por assunto (T131 e T132); (b) deixar tudo aceito, na D86. Recomendação: (a): a primeira corrige uma frase de privacidade que hoje está incompleta, e a segunda só pode rodar quando a fase fechar. As duas são Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva O e mover o item para a D86.

**Atualização de 2026-11-14 (A54, leva O):** a T131 foi entregue e juntada na `dev` (`0c5ddf1`), com os nove itens, e saiu aprovada com ressalvas baixas. O que ela deixou aceito está na D89, e o que virou a T133, na D90. A T132 segue aberta: roda no fim da fase, depois da T80 e da T81, que dependem do dono.

## D88. Atualização de dependências do fim da fase 1 (A53, T80d)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** a atualização manual da ADR 0021 (segundo passo da T80) foi feita na leva N, como T80d. O que mudou: `actions/checkout` foi da v4 para a v7 nos três workflows (`ci.yml:21`, `vigia.yml:28`, `wiki.yml:28`), `astral-sh/setup-uv` foi da v6 para a v7 (`ci.yml:22`, `vigia.yml:31`) e o requisito do `uv_build` ganhou o teto `<0.14` (`pyproject.toml:2`; o lock e o `uv build` aceitaram). O que não mudou: nenhum pacote do `uv.lock`, porque o `pyproject.toml` fixa tudo com `==` e `uv lock --upgrade` saiu idêntico; HTMX 2.0.11 e Inter 4.1 já estão na versão estável mais nova, com sha256 igual ao do `.meta.json`. Bateria verde antes e depois. O que ficou de fora, e por quê:
- `setup-uv`: a versão publicada é a v10.3.3. As v8 a v10 trazem quebras de cache (poda desligada na v9; cache desligado em `pull_request_target`, `workflow_run` e `release`, e `version: latest-known` na v10). O `ci.yml` só usa `enable-cache: true`, então a v10 provavelmente não quebra nada, mas a ADR 0021 e o plano mandam a v7.
- `playwright`: o pin é 1.65.1 e existe a 1.65.2 (só patch). Subir o pin pede reinstalar o Chromium da `fedora-dev` e do CI.
- HTMX: a 4.0.1 existe só como dist-tag `next` (major com quebra); o `latest` do npm é o 2.0.11, o que está vendorizado.
- `httpx2`: dependência nova, na D73.

**Opções:** (a) ficar na v7 do `setup-uv`, no playwright 1.65.1 e no HTMX 2.0.11 até a atualização da fase 2; (b) subir `setup-uv` para a v10 e o playwright para 1.65.2 já, em tarefa própria. Recomendação: (a), e fazer o (b) na atualização da fase 2, depois de a linha 4 do HTMX virar `latest`.

**Decisão provisória:** (a). Desfazer: tarefa pequena para subir as versões.

## D89. Sobras da leva O aceitas (A54, A55, T131, T133, REG12)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** as revisões da T131, da T133 e da REG12 deixaram estas sobras. A sessão as aceita sem mudar o código; a tarefa de origem está no começo de cada item:
- T131: dois módulos novos do painel, `painel/ambiente.py` (`ambiente_do_painel`, `rodar_do_painel`, `no_linux`) e `painel/formulario.py` (`campo_unico`). Os nomes são novos porque o nome antigo sem sublinhado seria sombreado por variável local nas rotas (`rodar, env = rodar(request)` dá `UnboundLocalError`). Se o dono preferir um módulo só, é juntar os dois.
- T131: o CHANGELOG ficou sem o item da D1 (não é mudança de produto) e com a D3 em frase simples.
- T131: "aceitar uma sugestão" faz pedido só na Gupy (`painel/rotas/sugeridas.py:80`, `_resolvido`), e o texto de privacidade diz de forma geral que o pedido sai quando a pessoa aceita uma sugestão.
- T131: a ADR 0014 e a wiki não repetem a frase antiga de privacidade (conferido em 2026-11-14), então nada muda lá.
- T131: as outras funções privadas de mesmo nome nas rotas (`_ler`, `_centavos`, `_montar`, `_resumo`, `_pagina`, `_achar`, `_gravar`, `_ligar`, `_motivo`, `_texto`, `_fontes`, `_conferir`, `_local`, `_linhas`) têm corpo diferente e ficam. As cópias de `_SemValidadores` dentro de `tests/` também ficam, porque cada teste tem o seu dublê.
- T133: a frase "pelo git e pelo uv" no README e no painel fica, porque o destino varia com o clone; o teste exige o texto.
- T133: `aviso_versao_ligada` continua fora de `PADROES` (`banco/cadastros.py:32`) de propósito: a T54 é a dona da chave (exceção da lista 13.7). O padrão desligado mora só em `aviso_ligado` (`agenda/versao.py:64`).
- REG12: `tests/integracao/test_cadastros.py` segue com o total de 28 fontes escrito no teste (linhas 171, 185 e 238). É uma guarda de propósito: fonte nova pede mudar o teste junto.
- Correção da A54: a atualização é o comando `jobot atualizar`, não um botão do painel.

**Opções:** (a) aceitar todas; (b) abrir tarefa para cada uma. Recomendação: (a), pelo custo baixo de cada uma.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D90. T133 entregue: a privacidade cita a atualização e o teste lê o padrão real (A55, T133)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** a T133 fechou as ressalvas da revisão da T131 (A54) e foi juntada na `dev` (`a51cb69`). O que mudou:
- O texto de privacidade (`README.md`, `README.en.md` e `configuracoes.privacidade.telemetria` em pt e en) cita o pedido de rede de `jobot atualizar` (o git e o uv, só quando a pessoa pede).
- `test_privacidade_cita_todos_os_pedidos` e `test_texto_acompanha_o_padrao_real` (`tests/unidade/test_documentos.py`) tiram a condição do padrão real: `PADROES` de `banco/cadastros.py`, `ligada_padrao` do `fontes.json` e `aviso_ligado`. `test_condicao_aceita_os_dois_generos` prova que a expressão aceita "vem ligado" e "vem ligada", "vem desligado" e "vem desligada".
- `_ligado` virou `aviso_ligado`, público, em `agenda/versao.py:64`, e a rota de configurações usa ele (`painel/rotas/configuracoes.py:97`).
- A revisão achou um problema médio: o teste exigia a condição com o gênero fixo, então, se um padrão feminino mudasse, o texto certo nunca passaria. Foi corrigido antes da junção. Os dois problemas baixos também (o teste fecha a conexão; o padrão do aviso fica num lugar só).
- A bateria da junção passou a rodar `uv sync --locked` e `ruff format --check` em linha própria. Resultado: `uv sync --locked` ok, 3.603 testes de unidade, 91 de tela, `ruff check`, `ruff format --check` e `mypy` limpos. Isso prova o passo inteiro da T80 (sobra da REG12).
- Ressalvas baixas e opcionais da re-revisão, aceitas: o nome de exibição da fonte sai de `capitalize` no teste, e não há mutante dirigido para o padrão do aviso.

**Opções:** (a) aceitar como está; (b) tarefa nova para a mutação do aviso e o nome de exibição. Recomendação: (a), pelo custo baixo.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D91. Beep Saúde e CNA Idiomas dão 0 vagas pela Gupy (A56, T55b, T40)

**Status:** decidido pela sessão em 2026-11-14 com o dono fora, para confirmar

**Contexto:** conferido ao vivo na `fedora-dev` em 2026-11-14, três vezes. Vem da D74, que pedia conferir de novo antes de tirar a empresa.
- Fato: `scripts/conferir_empresas.py gupy` deu 28 de 28 respondem, mas Beep Saúde e CNA Idiomas com 0 vagas, com ou sem o termo `developer` e com ou sem o `careerPageName`.
- O `resolver` do coletor (`nucleo/coletores/gupy.py:192-218`, o mesmo que o painel usa) devolve o mesmo `careerPageName` que está no `empresas.json` ("Beep Saúde", "CNA Idiomas").
- As páginas de carreira (`beepsaude.gupy.io`, `cnaidiomas.gupy.io`) listam 74 e 58 vagas.
- A API do portal (`portal.gupy.io/api/job-search/jobs`) com o `careerPageName` exato devolve total 0. Buscando por `jobName` com o título de uma vaga dessas páginas, o portal devolve a vaga com o `careerPageName` igual.
- Conclusão: o filtro `careerPageName` do portal não casa essas duas empresas. Não é quadro vazio nem nome errado. As outras 26 empresas da Gupy funcionam.
- Conferência das 28 empresas da Gupy (2026-11-14, A58): com o mesmo `careerPageName` que o coletor usa (`parametros.careerPageName` ou o nome da empresa) e o mesmo filtro pelo host do `jobUrl`, as outras 26 respondem pelo portal. Nas que têm até 100 vagas, a contagem do portal, comparada à da página de carreira, diferiu em no máximo 4 (provavelmente vaga que abriu ou fechou entre os dois pedidos). Nas que têm mais de 100 (Localiza, Sicredi, Hapvida, Fortbras, Ambev, Porto e GrupoSC), a primeira página do portal veio com 100 vagas, todas do host da empresa. A SPDM divide o nome "SPDM/PAIS" com outras unidades: na primeira página, 14 de 100 vagas são do host dela, e o filtro de host separa as dela (as páginas seguintes não foram conferidas). Só Beep Saúde e CNA Idiomas dão 0 vagas pelo portal.
- Também está no apêndice de fontes (`docs/superpowers/specs/2026-11-13-fase-1-fontes.md`, seção 7.5).

**Opções:** (a) tirar as duas do `empresas.json`; (b) tarefa nova: no coletor da Gupy, quando o portal devolve 0 para uma empresa, ler a página de carreira `<identificador>.gupy.io` (host novo, muda a decisão 29 e o contrato do coletor; precisa do detalhe de cada vaga, porque a página traz só título, departamento e local); (c) manter as duas e conferir de novo na próxima rodada; (d) (c) agora e (b) na fase 2. Recomendação: (d). Custo de manter: um pedido por dia por empresa, sem erro. Risco: quem adicionar pelo painel uma empresa com o mesmo problema vê 0 vagas sem aviso.

**Decisão provisória:** (d). Desfazer: tirar as duas do `empresas.json` (opção (a)) ou abrir a tarefa da opção (b).
