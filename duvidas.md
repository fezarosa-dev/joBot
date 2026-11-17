# Dúvidas

Decisões que dependem do dono do projeto. As resolvidas ficam registradas aqui, com a data.

Status usados: **resolvida** (o dono decidiu ou aceitou a decisão da sessão, com a data); **decidido pelo dono** e **decisão aceita** (variantes de resolvida, com a data); **superada por Dn** (outra decisão tomou o lugar dela); **decidido pela sessão, para confirmar** (a sessão decidiu com o dono ausente: ele confirma ou manda desfazer). Textos antigos que dizem "para confirmar" (D11 a D76) são o registro de quando a decisão ainda estava com a sessão: o dono aceitou todas em 2026-11-15 (Q7), e a decisão final de cada uma está no Status do início dela. **resolvida com escolha da sessão para confirmar** (o dono decidiu o quê e a sessão escolheu o como, que ele ainda confirma: D121 e D123). Só as D110 a D119 e as escolhas da D121, da D123 e da D126 ainda esperam o dono.

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

**Status:** resolvida em 2026-11-15: GitHub Sponsors ativo e a conta Buy Me a Coffee zanoni.dev é do dono

**Contexto:** o arquivo `.github/FUNDING.yml` mostra o botão Sponsor, mas precisa de uma conta de patrocínio, como GitHub Sponsors ou Ko-fi, que o projeto ainda não tem.

**Decisão provisória:** sem `FUNDING.yml` até o dono criar a conta e dizer qual usar.

**Atualização de 2026-11-14 (REG12):** o `.github/FUNDING.yml` já existe no repositório. Ele aponta para o Buy Me a Coffee e para a página Apoie da wiki (`custom`), então a escolha não foi GitHub Sponsors nem Ko-fi. A decisão provisória acima está desatualizada. Falta só o dono confirmar que a conta é a que ele quer. Status: o arquivo existe; a conta fica para o dono confirmar.

**Atualização de 2026-11-14: GitHub Sponsors ativo, decidido pelo dono (D96).**

## D5. Convenções da rotulagem do gabarito

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O gabarito de 329 vagas (fora do repositório) foi rotulado por dois modelos, com um juiz nas 100 divergências. Algumas vagas não cabem num valor só.

**Decisão provisória:** Vaga remota para o mundo todo ou para uma região (LATAM, Américas, Europa) fica sem país. Faixa de nível (ex.: pleno/sênior) conta o menor nível. Contrato `clt` ou `pj` só vale para vaga no Brasil. As regras da T13 seguem as mesmas convenções, para a medição da T37 ser justa.

## D6. Ferramentas do esqueleto

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão (a parte do Dependabot segue obsoleta pela ADR 0021)

**Contexto:** A T01 montou o pyproject, o CI e o Dependabot (o Dependabot saiu: obsoleta pela ADR 0021).

**Decisão provisória:** Backend de build `uv_build`. ~~O Dependabot do `uv` aponta para a `dev` (`target-branch`), o que só se confirma depois do primeiro push.~~ Obsoleta pela ADR 0021 (sem Dependabot). O CI de tela sai com código 5 enquanto não houver teste de tela (a T36 cria o primeiro).

## D7. Pasta de dados

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T02 lê a pasta de `JOBOT_DADOS`, depois `XDG_DATA_HOME`, depois `~/.local/share/jobot`.

**Decisão provisória:** Caminho relativo nessas variáveis é aceito como está (relativo à pasta atual). O umask 0o077 e a permissão do `jobot.db` ficam no ponto de entrada (T48), com `configurar_log` antes de `preparar_pasta`.

## D8. Cópia antes de migrar o banco

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Antes de migrar, o joBot copia o banco.

**Decisão provisória:** A cópia se chama `jobot.db.antes-v<N>`, com N = versão guardada dentro dela; ficam as 3 mais recentes. Banco vazio (versão 0) não gera cópia. Chave estrangeira quebrada na migração levanta `sqlite3.IntegrityError`, sem exceção própria.

## D9. Tipos do núcleo

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T04 fechou os tipos que as outras tarefas usam.

**Decisão provisória:** `SalarioBruto` guarda os valores lidos como número decimal (float) antes da conversão para centavos. `RequisitosEstagio` guarda os campos como texto. `Salario.periodo_deduzido` marca quando o período foi deduzido. `VagaColetada` e `VagaTratada` só se constroem com argumentos nomeados.

## D10. Catálogo de textos (i18n)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T07 criou o catálogo base em português e inglês.

**Decisão provisória:** Chaves no formato `area.<valor>`, `nivel.<valor>`, `modalidade.<valor>`, `contrato.<valor>`, `aviso.<valor>`, `fonte.<chave>`, `saude.<motivo>` e `seguranca.recarregue` (87 por idioma). Chave ausente devolve a própria chave; idioma desconhecido cai para português.

## D11. Quem aplica a correção na vaga (T21)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O desenho se contradiz: a linha 553 diz que o reprocessamento aplica a correção por cima das regras, e a linha 1299 (seção 13.5) diz que a correção "aplica na hora". A T21 expôs o conflito.

**Opções:** (a) `corrigir()` só grava em `correcao`, e o reprocessamento aplica a correção; para cumprir o "aplica na hora", a rota de correção (T46) chama `corrigir()` e em seguida reprocessa aquela vaga. (b) `corrigir()` faz UPDATE nas colunas da vaga; uf, salário e fechada exigiriam lógica própria duplicada.

**Decisão:** Opção (a). A tela já volta com o valor corrigido, sem esperar a próxima busca. Para a T46 reprocessar uma vaga só, a T19 ganha `reprocessar_vaga` nas Interfaces, com `test_reprocessar_vaga_aplica_correcao`, e a T19 entra no `depende_de` da T46 (decisão 8 da sessão). Em 2026-11-14 as decisões 17, 18 e 23 completaram isso (D29): a assinatura é `reprocessar_vaga(con, vaga_id: int, *, hoje: date) -> None`, que também recalcula as colunas `sal_*` e as `_brl` da vaga, e a rota de correção recalcula ainda o encaixe e o `oculta_motivo` daquela vaga nas buscas ativas. Os critérios entraram no plano: `test_correcao_vence_regra_no_reprocesso` (T19), a correção valendo depois do reprocessamento das buscas salvas e do encaixe (T24) e `test_corrigir_aplica_na_hora` (T46). A docstring de `corrigir()` cita a decisão (ajuste F2). A ocorrência de `ultima_vista_em` mais recente, aberta de preferência (`test_reprocessar_vaga_usa_ocorrencia_aberta_mais_recente`), foi confirmada pela decisão 18. Escolha do redator, para confirmar (D29): `reprocessar_vaga` e `aplicar_cotacoes` saem numa transação só (o `reprocessar_vaga` abre a `BEGIN IMMEDIATE`, e o `aplicar_cotacoes`, que só abre uma quando não há e faz o `commit` no fim, entra nela: `src/jobot/banco/cotacoes.py`, `aplicar_cotacoes`); o que fica em transação separada é o `recalcular_encaixe`, que a rota de correção chama depois, então uma falha entre os dois deixa o encaixe velho até o próximo recálculo.

## D12. Ações da vaga (T21)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T21 gravou as ações de status, ocultar e mostrar. O desenho não define alguns detalhes.

**Opções:** `valor_antigo` de uf, salário e outro: (a) NULL até existir a lógica desses campos; (b) inventar um "de" agora. `trazer_de_volta`: (a) zerar `oculta_manual`; (b) restaurar um -1 anterior. Estado esperado: (a) as ações levantam `LookupError` (vaga não existe) e `ValueError` (valor inválido); (b) toleram o que está fora do estado esperado. `_transacao`: (a) recusa conexão que já está numa transação; (b) aninha.

**Decisão:** `valor_antigo` fica NULL para uf, salário e outro até a lógica existir (T46/T24). `trazer_de_volta` zera `oculta_manual` sem restaurar um -1. `acoes.py` levanta `LookupError` e `ValueError`, que a T45 traduz em 404 e 422 e testa. `_transacao` recusa conexão que já está numa transação. O critério de 404 e 422 entrou no plano, na célula de testes da T45.

**Ver também:** D40 (`POST /mostrar` em vaga que já está visível), D155 (o Desfazer da faixa volta a -1).

## D13. Cliente HTTP educado (T05)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A revisão da T05 deixou quatro escolhas para o dono. O Greenhouse (T27) precisa do 404 e o 4xx genérico virava `ErroDeRede` sem o status.

**Opções:** Status: (a) atributo `status: int | None` em `ErroDeRede`, sem mudar o Protocol; (b) exceção nova `NaoEncontrado`, que muda o contrato (R4). `para_no_429`: (a) só o 429; (b) 429 e 503. `ler_em_fluxo`: (a) segue gerador assíncrono, usado com `contextlib.aclosing`; (b) vira função que devolve o corpo. Redirecionamento e DNS: (a) recusar redirecionamento de host público para loopback, link-local, rede privada ou `localhost`, e deixar a resolução de DNS para IP privado fora da fase 1; (b) resolver o DNS e conferir o IP. URL vinda da fonte: (a) sem barreira; (b) recusar host local ao montar a `UrlListada`.

**Decisão:** `ErroDeRede` ganha `status: int | None` (a), já no código (`ErroDeRede.status`, em `src/jobot/nucleo/http.py`, repassado nos `raise ErroDeRede(..., status)` de `ClienteEducado._abrir`). `para_no_429` vale só para o 429; o 503 segue a regra do `Retry-After` mesmo nesse escopo (a) (o teste de `Parou429` em `ClienteEducado._abrir` só olha o 429). `ler_em_fluxo` segue gerador assíncrono com `aclosing` (a); o Protocol passa a anunciar `AsyncGenerator[bytes]` em vez de `AsyncIterator[bytes]` (`ler_em_fluxo` do Protocolo `HttpEducado`), para quem chama usar `aclosing` sem cast (decisão 9, ajuste F2). O redirecionamento de host público para endereço local ou privado é recusado com `ErroDeRede`, e loopback para loopback, como nos testes, segue (conferência de host em `_local` e recusa em `_conferir_salto`, em `src/jobot/nucleo/http.py`; testes `test_redirecionamento_de_host_publico_para_local_e_recusado` e `test_redirecionamento_dentro_do_host_local_segue` em `tests/unidade/test_http.py`). IPv6 que embute IPv4 (`::/96` sem `::` e `::1`, e `64:ff9b::/96`) passa pela mesma conferência (decisão 14, ajuste F2).

**Risco aceito (decisão 13):** DNS rebinding e redirecionamento entre dois hosts locais. Num 307 ou 308 para outra origem o corpo JSON ainda é repassado, como fazem o httpx e os navegadores. A resolução de DNS para IP privado, que a opção (a) deixava fora da fase 1, ganha uma defesa parcial no ajuste F3 (decisões 15 e 19): quando a origem é pública e o destino é um nome, o host é resolvido por um resolvedor injetável (padrão `asyncio.get_running_loop().getaddrinfo`) e o salto é recusado se algum endereço não for global, com `test_redirecionamento_para_nome_que_resolve_local_recusado` (sem rede). Fica aceito o rebinding entre a checagem e a conexão, porque fixar o IP exigiria um transporte próprio, e o redirecionamento entre dois hosts locais. A URL vinda da fonte deixa de ser risco aceito (decisão 19): a conferência de host local fica pública em `http.py` como `host_local`, e a `UrlListada` recusa URL de host local com `ValueError` (`test_url_listada_recusa_host_local`); no molde, o item que levanta `ValueError` é pulado e contado em `sem_detalhe_n`. O DR-19 do desenho vale só para "Adicionar site". As leituras do redator estão na D30.

**Risco em aberto, para confirmar:** a `VagaColetada.url` não passa pela conferência de host local (`_confere_http`, em `src/jobot/nucleo/modelo.py`, só a confere como http ou https). Nenhuma decisão da sessão aceitou esse risco. Recomendação: a mesma recusa da `UrlListada` na montagem da `VagaColetada` (cobre o caminho que não passa pela `UrlListada`), em tarefa própria, porque muda o contrato do modelo (R4).

## D14. Leitor de salário (T10)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T10 leu salário em texto livre. Algumas escolhas foram do construtor.

**Opções:** Moeda sem faixa de plausibilidade: (a) conta como implausível; (b) conta como plausível. Faixas fora do BRL: (a) as do construtor; (b) o dono define. Benefícios: (a) chave ASCII (ex.: `retirement`); (b) texto original. `401k` logo depois de símbolo de moeda: (a) é valor; (b) é benefício. Texto de salário muito longo: (a) acima de 2.000 caracteres não é lido; (b) lê tudo. Faixa com períodos mistos (só um lado diz o período): (d2) quando o máximo passa de 10 vezes o mínimo, não forma faixa e fica só o valor que tem período; a fonte da sessão não detalha as outras opções. Benefício seguido de valor sem conectivo: (a) tira esse valor do salário; (b) mantém.

**Decisão:** As primeiras opções (a) dos cinco primeiros itens (decisão 4 da sessão). Texto acima de 2.000 caracteres devolve o mesmo que texto sem salário. Faixa com períodos mistos: (d2); a faixa normal (até 10 vezes) e a regra de plausibilidade do desenho 10.3 não mudam (decisão 10, ajuste F2). Salário com `Decimal(int)` direto, sem `str`, para int grande (ajuste F2). O último item (benefício seguido de valor sem conectivo) não consta nas decisões da sessão: o código segue a opção (a) até o dono confirmar.

## D15. Testes de tela rodam na fedora-dev (T36)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A caixa nortao não tem a `libatomic` que o driver do Playwright pede, então o Chromium não abre lá.

**Opções:** (a) rodar os testes de tela na fedora-dev; (b) instalar a biblioteca na caixa nortao.

**Decisão:** Opção (a) (decisão 5 da sessão). O Chromium do Playwright 1.65.1 (revisão 1254) foi instalado na fedora-dev. Na nortao, só rodam os testes sem a marca `tela`.

## D16. Texto e idioma (T08)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** `detectar_idioma` e o extrator de HTML foram escritos sem corpus real.

**Opções:** Limiares: (a) 20 palavras, 5 acertos e 75%, calibrados na T37; (b) outros valores agora. Genérico de código com nome de elemento HTML de uma letra (`<B>`, `<I>`, `<U>`, `<S>`, `<Q>`, `<A>`): (a) tratado como tag; (b) lista de exceções. Prefixos de namespace do Word: (a) `o v w m x xml st1`; (b) aceitar qualquer prefixo.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opções (a). Se aparecer outro prefixo, ele entra na lista.

## D17. Parâmetros de rastreio na URL (T09)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** `source`, `src`, `ref`, `referrer` e `referral` podem identificar a vaga em alguns sites.

**Opções:** (a) ficam fora da lista de rastreio; (b) entram na lista para todas as fontes; (c) entram por fonte, quando uma captura provar que é rastreio.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opção (a) agora, com (c) depois: incluir por fonte só com captura que prove. A normalização do caminho (`%7E`, ponto final no host, `//`) fica como limite da fase 1.

## D18. Contrato e local nas vagas do Brasil (T13)

**Status:** superada por D97 (T144) em 2026-11-15

**Contexto:** `clt` e `pj` só valem para vaga no Brasil (D5). A Gupy remota chega com cidade e estado vazios, e `rotular()` não sabe que é Brasil.

**Opções:** (a) o coletor põe "Brasil" em `locais`; (b) `rotular()` presume Brasil quando a fonte é brasileira; (c) vaga sem local nunca recebe clt ou pj.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opção (a), como o construtor recomendou. A conferência com o gabarito (T37/T78) mostra se resolve.

**Atualização de 2026-11-14 (A80, T144):** a opção (b) foi implementada em `tratar()` para as fontes só brasileiras (lista `fontes.so_brasil` em `rotulos.json`): sem país em nenhum local, a vaga ganha BR. Conferido com o gabarito: o acerto de país foi de 67,2% para 87,2% (D97). O dono aceitou em 2026-11-15 (Q7); a decisão final é a D97.

## D19. Contrato do ciclo de vida (T14)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T14 fechou as funções puras do ciclo de vida sem mudar o esquema.

**Opções:** Para cada item, (a) manter como está ou (b) mudar o contrato.

**Decisão provisória (o código segue esta opção até o dono decidir):** Manter os quatro. `OcorrenciaAberta` tem `url_hash`, `ultima_vista_em` e `sumiu_em` (kw_only), e quem chama passa todas as ocorrências do escopo, inclusive as sumidas, senão `reviram` nunca dispara. `MudancasCiclo` devolve `url_hash` em tuplas (sumiram, reviram, tocar), sem id de ocorrência; a T19 resolve por (fonte, escopo). `vaga_fechada([])` devolve False. Em `sem_mudanca`, `tocar` só inclui ocorrências abertas e `reviram` fica vazio.

## D20. Encaixe da busca (T15)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Com cidades preenchidas e modalidades vazias, vaga remota fora das cidades dá 0 no critério de local (`local_fora`, `src/jobot/nucleo/encaixe.py:93-97`): remoto só pontua com `REMOTO` nas modalidades (`:80`). Com cidades e modalidades vazias o critério é neutro (`:77-78`). O desenho (11.1) diz que critério vazio é neutro.

**Opções:** (a) modalidades vazio aceita remoto: com cidades escolhidas, vaga remota pontua `local_remoto` em vez de `local_fora`; (b) manter como está.

**Decisão:** Opção (a), que segue o desenho 11.1 (decisão 12 da sessão). Ainda não está no código da dev: entra no ajuste F2, com teste.

**Destino do que a T15 deixou em aberto (decisão 13):** as chaves `encaixe.*` nos catálogos de i18n (pt e en, e no `test_motivos_fixos_existem`) e o filtro "vaga aberta, não oculta e status nova" nas Candidatas e nos Destaques viram critérios da T45, porque `destaques()` não filtra isso (`src/jobot/nucleo/destaques.py:30`: "quem chama já entrega" só essas vagas). Os ids das regras de ocultar, a regra de local e modalidade, a regra de país e o idioma "outro" estão em `src/jobot/nucleo/dados/encaixe.json` e `src/jobot/nucleo/encaixe.py`; o que a T45 precisar deles, lê de lá.

## D21. Data de referência na leitura (T20)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** `detalhe(..., agora: datetime | None = None)` lê o relógio da parede quando o valor padrão é usado (`src/jobot/banco/leitura.py:286-291`).

**Opções:** (a) manter o parâmetro opcional e a rota da T45 sempre passar `relogio.agora()`; (b) torná-lo obrigatório (keyword) e corrigir o plano.

**Decisão provisória (o código segue a opção (a) até o dono decidir):** o valor padrão, `datetime.now().astimezone()`, e o `listar` passam pelo mesmo `_hoje` no fuso local (`leitura.py:191-193`), então os selos não divergem. A recomendação do construtor é (b), na T45, porque o padrão esconde uma leitura do relógio da parede (e obrigatório mudaria a chamada de 3 argumentos do plano, um contrato). Segue aberto o filtro por motivo e por status em `Filtros` (`leitura.py:85-97`). Os candidatos da aba Destaques vão para a T45 (decisão 13, ver D20).

## D22. App do painel (T26)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O `abrir()` usa `check_same_thread=True`, e o 500 não tratado sai sem CSP e sem `nosniff`, porque o handler de `Exception` fica por fora do middleware de cabeçalhos.

**Opções:** Conexão: (a) rota que recebe `Con` é `async def`, e quem precisa do banco fora da rota abre conexão curta; (b) trocar de thread no `abrir()`. 500: (a) deixar como está (o corpo é texto puro, risco baixo); (b) `try/except` em volta do `seguinte(request)`, com `logging.exception` para não perder o traceback.

**Decisão provisória (o código segue esta opção até o dono decidir):** Rota `async def` com conexão curta fora dela, e o 500 como está (a nos dois; a T150 da D106 muda o 500 para página amigável com cabeçalhos de segurança). É o que o código do construtor já faz (rota `async def`, `abrir()` sem `check_same_thread=False`); o dono aceitou em 2026-11-15 (Q7). O relatório da T26 cita uma recomendação "(b)" sem defini-la, por isso ela não foi atribuída a nenhuma opção.

## D23. Abrir e sair do programa (T43, T48)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T43 decide como o comando sabe se o servidor local é o joBot e o que diz no terminal.

**Opções:** `e_o_jobot`: (a) HTTP 200 e JSON objeto com `app == 'jobot'` em `/saude-local`; (b) só a porta aberta. Trava: (a) `serve` pega a `Trava` antes do uvicorn e tenta de novo após ~50 ms; (b) sobe o uvicorn primeiro. Mensagens de terminal: (a) texto fixo em português, fora do i18n; (b) catálogo de terminal agora.

**Decisão provisória (o código segue esta opção até o dono decidir):** Opções (a). O `serve` registra no log a porta ocupada. As mensagens de abrir e sair (inclui "Não consegui concluir o comando: <erro>") ficam em português, até existir um catálogo de terminal.

## D24. Segundo plano no Linux (T44, T53)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T44 liga o joBot em segundo plano pelo systemd do usuário. A tela de configurações (T53) mostra as mensagens.

**Opções:** Chaves de i18n: (a) `segundo_plano.sem_host_exec`, `.systemd_nao_responde`, `.home_diferente` e `.systemctl_falhou` (parâmetros `comando` e `saida`); (b) mensagem única. Atalho `.desktop`: (a) sem `--no-tty` (desenho 12.5), com `--no-tty` em `ExecStart` e `ExecStop`; (b) com `--no-tty` também no atalho `.desktop`, além do `ExecStart` e do `ExecStop`. Desligar: (a) recusa só se o `disable` falha e o arquivo do serviço existe; (b) recusa sempre que o `disable` falha.

**Decisão provisória (o código segue as opções (a) até o dono decidir):** o `--no-tty` entra por parâmetro, `sem_terminal` (`src/jobot/sistema/segundo_plano_linux.py:107-112`): o serviço usa `sem_terminal=True` (`:117`) e o atalho `.desktop`, `False` (`:140`). Efeito de (a) em desligar: com `systemctl` sempre falhando e o arquivo do serviço presente, a pessoa não limpa pela CLI.

## D25. Referrer do painel e o CSRF (T36)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O desenho 14.2 manda `Referrer-Policy: no-referrer` (`src/jobot/painel/app.py:25`). Com ele, o Chromium manda `Origin: null` no POST de formulário sem JS, e o `exigir_csrf` responde 403 (`src/jobot/painel/seguranca.py:80-83`).

**Opções:** (1) manter o `<meta name="referrer" content="same-origin">` no `base.html` (linha 10) como exceção anotada ao cabeçalho; (2) aceitar `Origin: null` com `Sec-Fetch-Site: same-origin`; (3) trocar o cabeçalho para `same-origin`.

**Decisão:** Opção (1), decisão 7 da sessão. O token CSRF continua obrigatório. O `meta` manda a origem certa ao próprio painel e nada para fora.

## D26. Salário que não cabe no banco (T19)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O SQLite só guarda inteiro de até 2**63-1; acima disso o `sqlite3` levanta `OverflowError` ao ligar o valor e a gravação do escopo inteiro quebra. Um texto de salário absurdo (ou um por hora, multiplicado por 160 no cálculo mensal) chega a isso. As colunas inteiras de salário são `sal_min`, `sal_max`, `sal_mensal_min` (centavos), `sal_mensal_min_brl` e `sal_mensal_max_brl` (`src/jobot/banco/migracoes/0001_inicial.sql:71-74`); as `_brl` são gravadas pela T25 (`aplicar_cotacoes`) e valem o valor mensal vezes a cotação. Elas podem estourar mesmo com o original gravado: o `sal_mensal_min` que a T19 confere vira `sal_mensal_min_brl` vezes a cotação, e o `sal_mensal_max_brl` parte de `sal_max` vezes o fator do período, que a T19 não confere.

**Opções:** (a) gravar a vaga sem salário (colunas nulas) quando qualquer valor não cabe; (b) recusar a vaga.

**Decisão:** Opção (a) (decisão 11 da sessão): perder a vaga por causa de um número de salário é pior do que ficar sem o salário. A regra vale para toda coluna inteira que a T19 grava, não só para o valor lido: se `sal_min`, `sal_max` ou `sal_mensal_min` passa de 2**63-1, `sal_moeda`, `sal_min`, `sal_max`, `sal_periodo`, `sal_mensal_min` e `sal_plausivel` ficam nulos e `sal_texto` fica (escolha do redator, para confirmar); a T25 grava nula só a coluna `_brl` cujo valor em reais inteiros passa de 2**63-1 (corrigido por D41: a decisão dizia "em centavos", mas as `_brl` guardam reais; decisão 17, `test_brl_gigante_fica_nulo`; D28). Entrou no plano, na T19, com `test_salario_gigante_nao_quebra_gravacao`, que leva também um caso por hora em que o original cabe e o mensal estoura.

## D27. Estados de `juntar_paginas` e a sentinela do 304 (T06, T07, T16)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A revisão da leva B achou lacunas no contrato do coletor: o 304 de uma página não tinha sentinela pública, o `LimiteAtingido` e o `ErroDeRede` sem nenhuma página lida viravam "parcial" com lista vazia, e o 304 misturado com 200 podia dar motivo `None`.

**Opções:** `ErroDeRede` com páginas lidas: (a) "parcial", com as vagas e o motivo; (b) sempre "falhou". 304 misturado com 200: (a) "parcial" com motivo novo; (b) "ok", ignorando o 304.

**Decisão:** Decisão 16 da sessão. `SEM_MUDANCA` é a sentinela pública do 304, e o coletor devolve exatamente `base.SEM_MUDANCA`, nunca uma cópia nem `()`. `ErroDeRede` e `LimiteAtingido` dão "falhou" sem página lida e "parcial" com uma ou mais (opção (a)). 304 misturado com 200 dá "parcial" com o motivo novo `saude.listagem_incompleta` (pt e en), nunca `None` (opção (a)). A T16 não trata motivo `None` de forma especial. Entrou no plano em T06, T07, T16 e no molde do coletor (`test_304` confere a sentinela por identidade).

**Ver também:** D41 (o docstring de `juntar_paginas` passou a dizer que só o que tem mais de 30 dias se fecha) e D35 (como o executor traduz o erro em motivo).

## D28. `hoje` em quem chama a conversão e `_brl` gigante (T25, T41, T24, T54)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A cotação do PTAX vale 7 dias (`data >= hoje - 7`), mas quem chama a conversão não passava a data, e a `_brl` de um salário gigante estourava o INTEGER do SQLite.

**Opções:** `hoje`: (a) opcional na assinatura, obrigatório para quem chama por teste; (b) sem padrão (keyword-only obrigatório). `_brl` que não cabe: (a) coluna nula; (b) vaga sem nenhuma `_brl`.

**Decisão:** Decisão 17 da sessão. T41, T24 e T54 passam a data do `Relogio` para `aplicar_cotacoes` e `cotacao_mais_recente`, cada uma com o teste da validade de 7 dias. No F3: o `BEGIN IMMEDIATE` e o primeiro `SELECT` entram no try/rollback; `_PARA_MENSAL` e `_mensal` de `salario.py` e `_confere_http` de `modelo.py` ficam públicos; `_brl` que não cabe (acima de 2**63-1) é gravada nula, só a coluna que não cabe (a), com `test_brl_gigante_fica_nulo`; `aplicar_cotacoes` ganha o filtro `vaga_id`. Corrige a frase falsa da D26.

**Escolha do redator, para confirmar:** a decisão diz "`hoje` é obrigatório em quem chama". O código tem `hoje: date | None = None` (sem `hoje`, vale a cotação mais recente guardada, que serve a teste e ao `jobot buscar` antigo). O plano mantém a assinatura (a) e prende o "obrigatório" nos testes de quem chama. Tornar `hoje` keyword-only sem padrão muda uma assinatura pública e é R4: fica para o dono decidir.

**Ver também:** D41 (`_brl` gigante: as colunas guardam reais inteiros, e a dúvida sobre `sal_cotacao_data`; a D26 foi corrigida por ela) e D38 (dia local e transação).

## D29. "Aplica na hora" vale para todas as colunas derivadas (T19, T24, T46)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A D11 fazia a correção voltar com o valor novo, mas a rota de correção deixava o salário em reais e o encaixe por busca com o valor velho até a próxima busca.

**Opções:** (a) reprocessar a vaga e recalcular, na hora, `sal_*`, `_brl`, encaixe e `oculta_motivo`; (b) só as colunas lidas do texto.

**Decisão:** Decisão 18 da sessão, opção (a); `reprocessar_vaga` recebe `hoje` pela decisão 23. `reprocessar_vaga(con, vaga_id, *, hoje)` recalcula as colunas `sal_*` e as `_brl` com `aplicar_cotacoes(..., hoje=hoje, vaga_id=vaga_id)` (T19, depende também de T23 e T25). A rota de correção (T46) chama depois `recalcular_encaixe(con, None, regras, hoje=hoje, vaga_id=vaga_id)` (T24 ganha o filtro `vaga_id`). A ocorrência usada é a de `ultima_vista_em` mais recente, aberta de preferência.

**Escolhas do redator, para confirmar:** (1) a decisão escreve a chamada de `recalcular_encaixe` sem `hoje`, e a decisão 17 manda a T24 passar o dia: o plano põe `hoje` como keyword, pela 17. (2) `reprocessar_vaga` e `aplicar_cotacoes` ficam na mesma transação (`aplicar_cotacoes` só abre uma quando não há e fecha no fim), mas a rota chama `reprocessar_vaga` e `recalcular_encaixe` em transações separadas, então uma falha entre elas deixa o encaixe velho até o próximo recálculo. (3) com a conversão ligada, `aplicar_cotacoes` pula vaga fechada, então a correção de salário de uma vaga fechada não atualiza as `_brl` (a vaga não aparece na lista aberta; recomendação: aceitar). Com a conversão desligada o código zera as `_brl` de toda vaga em moeda estrangeira, fechada ou não: a T25 cobre os dois ramos em `test_vaga_fechada_pula_com_conversao_ligada_e_zera_com_desligada`.

## D30. Resolvedor de DNS e URL de host local (T05, T06, molde, T69, T73)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A D13 aceitava o risco de DNS rebinding inteiro e de URL local vinda da fonte. A revisão de segurança automática pediu uma defesa.

**Opções:** ver D13.

**Decisão:** Decisões 15 e 19 da sessão. Resolvedor injetável `host -> list[str]`, só em salto vindo de origem pública e para destino que é nome; falha do resolvedor vira `ErroDeRede`; `host_local(host: str) -> bool` público em `http.py`; `UrlListada` recusa host local com `ValueError`; item que levanta `ValueError` no molde é pulado e contado em `sem_detalhe_n`. Testes: `test_redirecionamento_para_nome_que_resolve_local_recusado`, `test_host_local`, `test_url_listada_recusa_host_local` e, em T69 e T73, `test_url_de_host_local_e_pulada_e_contada`.

**Escolhas do redator, para confirmar:** (1) a decisão escreve `HttpEducado(..., resolver=None)`, mas `HttpEducado` é o Protocol e quem tem construtor é `ClienteEducado`: o parâmetro entra em `ClienteEducado` e o Protocol não muda. (2) Como a contagem do item pulado chega ao executor fica com o construtor: campo novo em `ResultadoEscopo` seria R4. (3) Fica aceito o rebinding entre a checagem e a conexão e o redirecionamento entre dois hosts locais.

**Ver também:** D41 (resolvedor que falha, resposta vazia e a guarda de rede dos testes).

## D31. ADR 0018: manutenção pela comunidade, vigia, `jobot atualizar` e link "reportar problema" (T50, T83, T84, T85, T01)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão; o aviso de versão desligado por padrão e a lista de serviços da ADR 0014 ficam substituídos pela D105; falta o dono criar o rótulo `fonte-quebrada` no GitHub

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
- Vigia (T84) na leva J, decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7) (D63): roda junto dos coletores T56–T65 e da REG7, com os valores já escritos aqui (segunda às 06:23 UTC, no máximo 5 pedidos por fonte, `FONTES_FORA = {"eureca", "abler", "gupy"}`) e com as opções em aberto acima (zero vagas, `saude.excecao`, detalhe quebrado, contexto fixo) seguindo a recomendação de cada uma. O link "reportar problema" e o aviso de versão (T50, T85, T87) já estão entregues.
- Vigia entregue pela T84 (leva J, juntada na `dev` em 2026-11-14), com os valores do plano: segunda às 06:23 UTC (`vigia.yml`), `VIGIA_MAX_PEDIDOS = 5`, `VIGIA_MAX_DETALHES = 2`, `FONTES_FORA = {"eureca", "abler", "gupy"}`. Seguem abertas, para o dono confirmar: o critério de "voltou" (`_voltou` em `scripts/vigia.py`: só pede estado ok, sem mudança ou parcial, e fonte sem quebra; a issue aberta por detalhe quebrado pode fechar como "voltou" quando o detalhe parou por orçamento ou bloqueio, o que a T121 corrige); o teto de 10 páginas da listagem de issues do GitHub (`MAX_PAGINAS_API`); o `timeout-minutes: 180` do fluxo; e o rótulo `fonte-quebrada`, que a pessoa cria no repositório do GitHub. O vigia só roda depois do merge na `main`. Os nomes privados do executor que `scripts/vigia.py` importa ficam para a T106 (D78).

## D32. `tratar` chama `ler_requisitos` em toda vaga (T18)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A leitura de requisitos de estágio (T12) roda no `tratar` para vaga de qualquer área, não só para as que dizem ser de estágio.

**Opções:** (a) chamar em toda vaga e guardar `None` quando não há achado; (b) chamar só quando o título ou o contrato indicam estágio.

**Decisão:** Decisão 21 da sessão, opção (a): fica como está no código (`src/jobot/nucleo/tratamento/tratar.py:33`). Entrou no plano, na T18, com `test_tratar_chama_ler_requisitos_em_toda_vaga`.

## D33. Aprovação do primeiro PR de quem nunca contribuiu (ADR 0018)

**Status:** decisão aceita em 2026-11-15 (opção (a), deixar ligada); falta o dono conferir em Settings > Actions > General > Fork pull request workflows, na tela do GitHub

**Contexto:** A ADR 0018 põe o CI em todo PR, inclusive de fork. O GitHub tem uma configuração que segura o primeiro PR de quem nunca contribuiu até o dono aprovar a execução. Ela não está no repositório.

**Opções:** (a) deixar ligada: o primeiro PR de cada pessoa espera o ok do dono, e é a principal trava contra abuso de minutos; (b) desligar: PR de qualquer pessoa roda na hora.

**Recomendação:** (a). O dono confere em Settings > Actions > General > Fork pull request workflows, na tela do GitHub, antes de divulgar o projeto.

**Atualização de 2026-11-14 (T83, leva L):** a seção 7 do guia `docs/consertar-fonte.md` (e de `docs/consertar-fonte.en.md`, linha 117 dos dois) diz que o primeiro PR de quem nunca contribuiu pode esperar o mantenedor liberar a execução dos testes. Se o dono escolher a opção (b), essa frase sai dos dois guias, numa edição só de texto.

## D34. O guia de conserto só depois da T17, da T27, da T50 e da T84 (ADR 0018)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O guia "Como consertar uma fonte que quebrou" (T83) usa o script de captura (T17) e o Greenhouse (T27) como exemplo real, e cita o link "reportar problema" (T50) e a issue do vigia (T84), então só pode ser escrito depois deles. No plano ele está na onda 8, com `depende_de: T17, T27, T50, T84`.

**Opções:** (a) escrever o guia depois da T17, da T27, da T50 e da T84, com comandos e exemplo reais e só com recursos que já existem (o plano); (b) escrever antes, com exemplo inventado, e corrigir depois.

**Recomendação:** (a). Até lá, o guia de contribuição segue como está: PR de código só entra depois da fase 8.


## D35. Executor: motivo do escopo, erro do detalhar e parada da fonte (T16, F3, molde do coletor)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A D28 tornou `hoje` obrigatório em quem chama a conversão e o encaixe. A T24 acrescentou duas coisas que o desenho não dizia.

**Opções:** dia de referência: (a) `hoje = agora.astimezone().date()` (dia local do `Relogio`); (b) o dia em UTC. Transação: (a) cada módulo segue a sua convenção e a rota faz commit ou rollback antes de chamar; (b) uniformizar todos em `RuntimeError` como `acoes._transacao` (muda assinatura pública, R4).

**Decisão provisória:** (a) nas duas. `hoje` é obrigatório (R2) e `criar_busca` recebe `agora` e calcula o encaixe. A T41, a T46, a T49, a T52, a T53 (o passo 1 chama `criar_busca`) e a T54 passam `hoje = agora.astimezone().date()` e `agora` com fuso, com teste (entrou no plano como DP8 e nas tarefas citadas). `cotacoes.aplicar_cotacoes` e `buscas._escrita` juntam e confirmam a transação aberta do chamador, e `acoes._transacao` levanta `RuntimeError`; a rota faz commit ou rollback antes de chamar `buscas` ou `cotacoes`, e em erro o rollback desfaz também as escritas pendentes dela (lição em `registros/padroes.md`).

**Para confirmar com o dono:** o teste de corrida de `recalcular_encaixe` (`set_trace_callback` e `threading.Event`, vermelho ao trocar `BEGIN IMMEDIATE` por `pass`) não foi feito, por ser opcional na revisão. Recomendação: fazer, na T88.

## D39. Medição dos rótulos no gabarito (T37, T78)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T45 deixou três pontos para o dono e quatro pendências baixas da revisão.

**Opções:**
- Foco: (a) `.situacao`, `.lista` e `.vazio` com `:focus:not(:focus-visible)` no lugar de `outline: none`, igual ao padrão de `base.css` para `main` (o foco programático depois de ação por teclado fica visível; depois de clique de mouse continua sem contorno); (b) manter `outline: none`.
- `POST /mostrar` em vaga visível (`oculta_manual` 0 e sem motivo): (a) como está, grava `oculta_manual = -1` e o evento `mostrou` (decisão de desenho, D12 e DP2); (b) a rota responde sem efeito quando a vaga não está oculta.

**Decisão provisória:** foco (a) (já no código); `/mostrar`: o código segue a (a), e a recomendação é a (b).

**Para confirmar com o dono:** as pendências baixas viraram itens do plano: T46 (mover `_de_volta` para `seguranca.py`) e T82 (registrar os globais do Jinja em módulo explícito, junto do item do tema; teste de 422 por `ValueError` em `mostrar` e `ocultar`; teste de Tab real no lugar de `focus()` mais `Enter`). A rota `/mostrar` só muda se o dono escolher a (b).

**Resolvido (globais do Jinja):** os globais (`salario_texto`, `locais_texto`, `data_curta`, `data_completa`, `dinheiro`, `rotulo` e `motivo`) agora são registrados num só lugar, `registrar` em `src/jobot/painel/globais.py`, chamado em `src/jobot/painel/seguranca.py` logo depois de montar o `TEMPLATES`. Nenhuma rota registra global no import. O `tema` deixou de ser global e vai no contexto de `renderizar`. O teste é `test_globais_do_jinja_vem_do_modulo_explicito` em `tests/integracao/test_rota_preferencias.py`.

## D41. Guarda de rede dos testes e renomeações do F3 (F3, T05, T25)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** A T86 pôs o menu principal na casca (`templates/base.html`), com seis itens: Vagas, Buscas, Fontes, Empresas, Sites e Configurações.

**Opções:**
- Links para telas que ainda não existem: (a) o menu mostra os seis itens desde já, e Fontes, Empresas, Sites e Configurações dão 404 até a T50, a T51, a T75 e a T54 entrarem; a fase não publica nada antes disso; (b) esconder cada item até a tela dele existir.
- Menu na primeira execução: em `/primeira-execucao` nenhum item fica marcado, e o menu aparece. (a) deixar assim; (b) esconder o menu durante a primeira execução, com um bloco Jinja no `base.html`.
- Barra do topo em tela estreita (até 40rem): (a) deixa de ser fixa ao rolar (`position: static` em `base.css`), para o menu quebrado em várias linhas não cobrir o conteúdo com zoom de 200%, como está; (b) continua fixa, só com a quebra de linha.

**Decisão provisória:** (a) nas três. A (a) da barra não foi pedida e nenhum teste de tela cobre a tela estreita; é fácil de tirar.

**Provisório (o que o código faz hoje), para confirmar:** o item Configurações aponta para `/configuracoes/fontes` e fica marcado em qualquer `/configuracoes/...`. A área de cada item casa o caminho inteiro ou seguido de `/` (`/vagasx` não marca Vagas), e `/` conta como Vagas.

## D48. Tratamento: cidades dos EUA, curso composto e salário (T82, T92, T78)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono escolheu concluir o passo 2 com aviso, sem prender a pessoa (opção (b))

**Princípio do dono:** nenhum erro trava o programa; todo erro aparece com o que a pessoa pode fazer (ver D106).

**Contexto:** No passo 2 da primeira execução, "Não ligar" chama `desligar` sempre no Linux (`_gravar_passo_2` em `src/jobot/painel/rotas/primeira_execucao.py`), porque um "ligar" recusado no meio já deixou o arquivo do serviço. `desligar` pode falhar (`systemctl_falhou`) quando o arquivo ficou e o `systemd` não responde. Nesse caso a pessoa não consegue concluir a primeira execução: nenhuma das duas opções termina.

**Opções:** (a) a falha do `desligar` volta ao passo 2 com o motivo, como está; (b) conclui mesmo assim, com o segundo plano desligado, e mostra o aviso com o motivo.

**Decisão:** opção (b), escolhida pelo dono em 2026-11-15 (a T152 a entrega na versão 0.1.1; até lá o código segue a (a)): a pessoa pediu para não ligar, e ficar presa no passo 2 é pior. O título errado da recusa ("Não foi possível ligar") foi corrigido pela T89 em 2026-11-14, que mostra o título de desligar.

## D50. Escopo opaco e nome da empresa no coletor (T28, T29, T30, T35, T38, T40, T41, T50, T51, T84)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Atualização de 2026-11-14 (A16):** a terceira fonte sem nome na resposta apareceu: o Workday (a empresa só vem em `hiringOrganization.name`, no detalhe). A sessão manteve a (a): o Workday guarda `identificador -> nome` na instância, como Lever e Ashby, sem mudar o contrato do `coletar`. Mudar o contrato mexe em todos os coletores e é decisão do dono: se quiser a (b) ou a (c), vira tarefa nova. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7). A Eightfold também guarda o cadastro na instância (`shortcut:` em `eightfold.py`). Os escopos novos da leva B seguem o texto opaco: um por empresa e país no Workday (T115, A17), o host no Eightfold, o identificador nas demais.

**Atualização de 2026-11-14 (A33, T115, leva K):** o escopo do Workday tem o formato `<tenant>/<site>|<wd>|<PAÍS>`, com o código ISO do país em maiúsculas (`workday.py:71-83`). O SmartRecruiters usa `<id>|<pais>` em minúsculas, porque a API dele pede assim: o escopo é opaco e cada coletor tem o seu. Escopo gravado com o nome antigo (sem país) dá `ValueError` em `_separar`, sem migração, porque a fase 1 ainda não saiu. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Escolhas do redator, para confirmar com o dono:**
- A T50 mostra o escopo como texto, como vem do coletor, sem separar nem traduzir.
- Hapvida: o nome genérico faz o escopo `hapvidandi` baixar vagas de várias empresas, e só o filtro de host do `jobUrl` as descarta depois de baixadas. O orçamento de 30 pedidos é da fonte inteira, então esse escopo pode gastar tudo e deixar os outros em `no_limite` (o rodízio por `ultima_coleta` ameniza, não elimina). Se acontecer na prática, vira tarefa nova: limite próprio por escopo ou filtro por outro parâmetro da API.
- SmartRecruiters: `escopos` não confere o identificador do cadastro. Um identificador vazio ou com `|` geraria escopo malformado. O resolver e o `empresas.json` já cuidam disso, então fica sem teste; filtrar por regex em `escopos` é opcional.

**Oracle HCM (T66, leva L):** o coletor segue o mesmo atalho do Workday. O nome da empresa vem do cadastro, guardado por `escopos` (`oracle_hcm.py:170-191`), e, sem passar por `escopos`, cai no primeiro rótulo do host (`oracle_hcm.py:196`, por exemplo `eeho`). A decisão não muda; sai junto com a D50.

## D51. GitHub Issues: cota, empresa e página 2 (T31, T84, T94, T99)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Dois pontos do coletor (`src/jobot/nucleo/coletores/smartrecruiters.py`).
- Chave da vaga. A URL da vaga é montada da lista como `https://jobs.smartrecruiters.com/<identificador>/<id>`, sem slug, e é a chave da vaga. A `postingUrl` real do detalhe tem slug (`/744000161500208-analista-de-dados-e-relacionamento`). A URL sem slug nunca foi aberta na rede (os testes usam `MockTransport`). Se ela não abrir ou não redirecionar, o link do painel quebra, e a deduplicação entre fontes não casa com a URL que tem slug.
- Empresa inexistente. A API devolve 200 com `totalFound=0`, então não há `test_404_empresa_nao_encontrada` (a ausência é deliberada), e zero vagas não prova que o identificador existe.

**Opções:**
- Chave: (a) conferir antes de gravar vagas reais abrindo na rede um exemplo da captura e, se abrir, manter a URL sem slug; (b) montar o slug a partir de `name`; (c) usar a `postingUrl` do detalhe, o que pede um pedido por vaga.
- Empresa inexistente: (a) a T51 mostra aviso quando o "testar" dá zero vagas; (b) nada.

**Decisão provisória:** chave: (a); mudar a chave depois de gravar vagas custa migração, então a conferência vem antes da primeira coleta real (a T55 é o primeiro momento). Empresa inexistente: (a), registrado no critério da T51.

**Atualização de 2026-11-14 (A15):** o passo 4 do enriquecimento (`_enriquecer` em `agenda/execucao.py`, DR-70) já detalha a `VagaColetada` listada sem descrição. Onde este registro dizia que ligar o `detalhar` à vaga já listada era tarefa do enriquecimento, vale agora "feito pelo passo 4 (DR-70)". Workday e SmartRecruiters detalham por ele; o que falta é só a T114 (detalhar por escopo e no ritmo do `por_escopo`, D77). A dúvida da chave da vaga sem slug (T55) segue como está. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Provisório (o que o código faz hoje), para confirmar:**
- O escopo `<identificador>|<pais>` é o contrato da D50.
- O `detalhar` não lê o `applyUrl` do detalhe, então `url_candidatura` fica `None`. O plano não pede isso para a SmartRecruiters. Ligar o `detalhar` a vaga já listada (o executor só detalha `UrlListada`) é tarefa do enriquecimento (seção 10.6) ou do executor.
- A caixa do identificador é preservada (D45).

## D53. Gupy: escolhas do redator (T40, T51, T54)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O coletor (`src/jobot/nucleo/coletores/gupy.py`) fez quatro escolhas sem decisão no plano, além das da D50 e da D45.

**Opções:**
- Pedido condicional: (a) só na página 0 (como está; um 304 não diz quantas páginas existem, então o 304 da página 0 vale pela lista toda, e uma empresa com mais de 100 vagas que só mude da página 2 em diante demora a ser vista; a Localiza tem 894 vagas e muda toda hora); (b) pedido condicional em todas as páginas mais um pedido extra de terminador por escopo (dobra o custo dos 28 escopos contra o orçamento de 30 pedidos).
- Filtro de host: (a) só o escopo de empresa descarta a vaga cujo host do `jobUrl` não é `<identificador>.gupy.io`; o escopo `cargo:` não filtra, porque a vaga é de qualquer empresa do portal, inclusive com domínio próprio; (b) filtrar também o `cargo:`.
- Prazo: (a) `applicationDeadline` vale o dia escrito, sem fuso (a captura mostra `2027-01-12T00:00:00.000Z`, meia-noite UTC, ou seja, data pura); (b) converter para o dia local.
- Nome da empresa: o `resolver` devolve o `careerPageName` além do `identificador`. (a) a T51 grava esse par em `parametros` ao adicionar a empresa; (b) guardar só o identificador e deixar o coletor descobrir o nome a cada coleta.

**Decisão provisória:** (a) nas quatro. Para o prazo, a (a) é segura porque a Gupy manda data pura. A T51 passa a gravar o `careerPageName` do resolver (critério novo na T51). A rota da T54 que monta os `parametros` do "testar" não pode apagar o `careerPageName` (regra da D37).

**Escolhas do redator, para confirmar com o dono:** os itens pulados saem como `saude.formato_mudou` sem contagem, como nos outros coletores (D45). A decisão 29 (o `careerPageName` aceito pela API e as 9 empresas que levam o nome em `parametros`) está no apêndice de fontes, seções 2.5 e 7.5.

## D54. Execução completa: o que ficou para confirmar (T41, T95)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O desenho 13.5 pede o prazo com "▲, em vermelho se faltam menos de 7 dias". A T46 entregou o corte de 7 dias, mas marca a faixa e o texto só em negrito, porque o vermelho pede um token novo (`--alerta`) e o par de contraste em `base.css` e na lista de contrastes, e o `base.css` é da T36. A marca ▲ da grade de meses também ficou sem destaque, pelo mesmo motivo.

**Opções:** (a) criar `--alerta` numa tarefa pequena (com par de contraste para a superfície e para o fundo, nos dois temas) e pintar o prazo e a marca ▲; (b) manter o negrito.

**Decisão provisória:** (a), entregue pela T96 com os valores de partida: `--alerta` é `light-dark(#d70015, #ff453a)`, e o prazo e a marca ▲ usam o token, com o negrito e o ▲ mantidos. Contraste medido: 4,94 sobre o fundo claro, 6,16 sobre o fundo escuro, 5,38 sobre a superfície clara e 4,99 sobre a superfície escura. O ▲ da grade de 12 meses fica sobre `--trilho` com 4,41 (claro) e 4,09 (escuro): é objeto gráfico (`aria-hidden`, o texto ao lado diz o mesmo), e o mínimo da WCAG 1.4.11 para ele é 3:1, então passa; o texto do prazo é que precisa de 4,5. O par `alerta/trilho` não entra na lista do `base.css`. Se o dono quiser 4,5 também na grade, pede outro tom para a marca ou para o fundo.

**Provisório (o que o código faz hoje), para confirmar:**
- O comentário da correção aparece em todas as linhas do formulário (um `textarea` por formulário, `id` `correcao-comentario-{campo}`). A dúvida anterior, se o comentário ficava em uma só linha, está resolvida a favor do desenho 13.5.
- Quando área, nível, modalidade ou contrato estão `NULL` (a coluna aceita), nenhum `<option>` sai marcado, e o navegador mostra a primeira opção como se fosse o valor da vaga. A sugestão da revisão é uma opção vazia marcada e desabilitada no topo, com teste de vaga de área `NULL`; fica para o dono pedir, porque o 422 seco para valor vazio já vale.
- `rotas/detalhe.py` importa nomes privados de `rotas/vagas.py` (`_MAX_ID`, `_busca_efetiva`, `_inteiro`, `_relogio`, `_utc`). Funciona, mas qualquer renomeação lá quebra aqui; tornar públicos os helpers compartilhados é ajuste à parte.

## D57. Coletores da leva A: escolhas dos redatores, para confirmar (T28, T29, T32, T33, T34, T35, T38, T39, T93)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão (segundo plano pela opção (b), A1; 422 seco como está)

**Contexto:** Dois pontos baixos das revisões da T54 e da T91.
- Segundo plano. O interruptor da tela de configurações (`_ctx_segundo_plano` em `src/jobot/painel/rotas/configuracoes.py`) mostra a chave `segundo_plano` do banco, não o estado real do systemd (desenho 12.5). Se o serviço for ligado ou desligado por fora, a tela erra.
- 422 seco. `POST /buscas/{id}/ligar` e `/desligar` (`_ligar` em `src/jobot/painel/rotas/buscas.py`) respondem com `HTTPException` 422 sem página nem mensagem, porque essas rotas não têm formulário.

**Opções:**
- Segundo plano: (a) seguir a chave do banco, como está; (b) ler o estado real do systemd ao montar a tela. Recomendação: (b) numa tarefa própria (T98), porque exige decidir qual é a fonte de verdade.
- 422: (a) seco, como está; (b) mensagem na lista de buscas. Recomendação: (a); vira item novo só se o dono quiser.

**Decisão provisória:** segundo plano: (b), entregue pela T98 em 2026-11-14. Com o dono fora, a sessão escolheu que o interruptor mostra `estado.habilitado` (o timer habilitado no systemd), e não `ativo` (rodando agora, que muda a cada execução). Fora do Linux sai desligado e desativado, sem consultar o systemd, e o GET não regrava a chave. Desfazer: voltar a ler a chave `segundo_plano` do banco. O desenho 12.5 não foi alterado; se ele diz que a tela segue a chave, acertar o texto quando o dono confirmar. 422: (a), seco, como está.

## D62. Primeira execução: sobras da tela de execução (T49, T106, T107)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Cinco pontos baixos da revisão da T49.
- Nomes privados. Rotas importam nomes com `_` de outros módulos: `_rodar` (de `agenda/agendador.py`, em `rotas/execucao.py:20`), `_relogio` (de `rotas/vagas.py`, em `rotas/execucao.py:25`, `fontes.py:30` e `detalhe.py:28`) e `_de_volta` (de `painel/seguranca.py`, em `rotas/vagas.py:25`, `preferencias.py:15` e `execucao.py:26`).
- Contagem de novas. O "Buscar agora" mostra a contagem de vagas novas lida do banco, não do resultado da busca. Aceito.
- `primeira_execucao/pronto.html` é formulário comum, sem HTMX. O aviso "já roda" nesse caso sai pela T101.
- A tela final da primeira execução mostra dois botões "Buscar agora" (o da casca e o dela).
- A região vazia do andamento ocupa uma linha.

**Opções:** nomes privados: (a) tornar públicos numa tarefa pequena (T106); (b) aceitar como está. Dois botões e região vazia: (a) um só botão e região sem altura (T107); (b) aceitar. Recomendação: (a) nos dois.

**Decisão provisória:** o código segue como está. A T106 e a T107 estão no plano, livres.

## D63. Levas H, I e J: ordem do trabalho e cópia de segurança (A3, A10, A11, A12)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Três escolhas de ordem, tomadas sem o dono.
- A3. A leva I juntou a T71 (descoberta) e a T72 (páginas acompanhadas) antes da T55, porque só dependiam de tarefas prontas e não dependem da rede real. O plano já diz isso na linha da onda 8.
- A10. A leva J roda em paralelo, até 8 tarefas ao mesmo tempo, cada uma no seu worktree: coletores T56–T65, o vigia T84 e a REG7 (estes registros). Modelo pela dificuldade: Opus nos coletores mais chatos (iel, workday, eightfold) e no vigia; Sonnet nos outros.
- A11. Depois de juntar a leva I e a T103, a `dev` vai ao GitHub como cópia de segurança: só a `dev`, sem PR e sem `main`; push na `dev` não roda CI. A regra registrada antes era push e PR só no fim de cada fase; esta é uma exceção só para a `dev`.
- A12. Depois da leva J (coletores T56–T65, vigia T84, REG7), a `dev` foi mandada de novo ao GitHub como cópia, pela mesma regra da A11. Esta é a regra anterior que a A12 (e a A11) substitui no dia a dia: "push e PR só no fim de cada fase". Continua valendo que PR e `main` só no fim da fase, e que o push da `dev` não roda CI.

**Opções:** A3: (a) como feito; (b) esperar a T55. A10: (a) paralelo; (b) uma tarefa por vez. A11 e A12: (a) copiar a `dev` ao fim de cada leva; (b) só no fim da fase. Recomendação: (a) nas quatro.

**Decisão provisória:** (a) nas quatro. Desfazer: A3 e A10 não têm o que desfazer; A11 e A12 se desfazem parando de dar push.

## D64. Aviso de versão e link de apoio: sobras (T85, T87, T104, T105)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- Hora da checagem (`checar_versao_nova` em `src/jobot/agenda/versao.py:100-126`). A hora só é gravada quando o servidor respondeu, mesmo com erro. `OrcamentoGasto` e `ErroDeRede` com `status` `None` voltam sem gravar, e a próxima volta (de hora em hora) tenta de novo. Escolha do agente que implementou, para confirmar.
- Salto recusado (A6). `ErroDeRede` com `status` `None` também cobre um redirecionamento recusado, e aí a checagem tenta de novo toda hora e nunca grava. Consertar exige mudar o contrato de `nucleo/http.py` (uma exceção própria para o salto). Fica como está.
- `atualizar()` tem o parâmetro `raiz`, que existe só para os testes (a nota está na T85 do plano).
- Fixture global. O `_laco_versao_parado` de `tests/conftest.py` é `autouse` e vale para todo teste, mas só quatro suítes sobem o lifespan. Mover só para `test_servir.py` quebraria as outras (T104).
- Falta teste de tela do aviso de versão (T105).
- CSS (A4). O estilo `.aviso-versao` entrou no `base.css` junto da T87, que já mexia nesse arquivo, e não numa tarefa à parte.
- Link da versão no aviso (T105, A39). O plano da T105 supunha um link da versão com `target="_blank"` e `rel="noopener noreferrer"`, mas o fragmento real (`painel/templates/aviso_versao/aviso.html`) não tem link: o aviso já diz para rodar `jobot atualizar`. A T105 foi entregue sem link, e o teste trava isso (`tests/tela/test_aviso_versao.py:80-83`).

**Opções:** salto recusado: (a) deixar; (b) exceção própria para o salto no `http.py`, o aviso grava a hora e o log diz o motivo. Hora da checagem: (a) como está; (b) gravar também sem resposta, com atraso de uma hora. Link da versão: (a) sem link, como o aviso real; (b) tarefa para pôr o link da release, com `target` e `rel` e teste que os exija. Recomendação: (a) nos três; o custo de tentar de hora em hora é um pedido por hora, só com o aviso ligado.

**Decisão provisória:** (a) nos três. T104 e T105 entregues e juntadas na `dev` em 2026-11-14 (leva K). Link da versão: decidido pela sessão em 2026-11-14 com o dono fora (A39); o dono aceitou em 2026-11-15 (Q7). Desfazer o link: opção (b).

## D65. Primeira execução em modo edição e idioma do `jobot buscar` (T89, T100)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- Formulário esvaziado. No passo 1 em modo edição, se a pessoa esvazia todos os campos, a busca não muda e a tela segue ao passo 2. Escolha do redator, para confirmar.
- `editar_busca` (`src/jobot/banco/buscas.py:161`) não recebe `agora`, só `hoje`. O `agora` com fuso vai ao `criar_busca`, que deriva o `hoje`.
- Cidades. O formulário do passo 1 mostra 3 linhas de cidade, e a leitura aceita até 10 (`_MAX_CIDADES` em `rotas/primeira_execucao.py:48`).
- Idioma do `jobot buscar`. O resumo sai sempre em português (`cli/buscar.py`), sem olhar o idioma do sistema nem o da preferência. Limite conhecido, como as outras mensagens de terminal (D23).

**Opções:** formulário esvaziado: (a) manter a busca e seguir ao passo 2; (b) recusar com mensagem. Cidades: (a) 3 linhas na tela, 10 na leitura; (b) igualar. Idioma: (a) fixo em pt; (b) detectar o idioma do sistema. Recomendação: (a) nos três.

**Decisão provisória:** (a) nos três.

## D66. Desligar limpo e ajustes baixos da leva H (A2, A5, T101, T102)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- A2. Ctrl+C e SIGTERM fechavam o cliente HTTP com a busca do "Buscar agora" ainda rodando. A T101 cancela e aguarda essa busca no lifespan, antes de fechar o cliente. `/sair` marca `app.state.saindo` e o "Buscar agora" recusa busca nova nessa janela. O relógio do app vem do `montar`. Sem HTMX, o aviso "já roda" volta pela página do redirect. É correção, não tem o que desfazer.
- A5. Os três ajustes baixos da revisão da leva H foram numa tarefa só, a T102: o "pular" do passo 1 em modo edição mantém `?busca=<id>`, o teste do `Retry-After` inválido no 429 de cota zero e o teste que prova que o catálogo recusa chave repetida.
- Notas baixas da T101: o nome do cookie `jobot_ja_roda` está repetido em `barra.html` e em `_AVISO` de `rotas/execucao.py:29` (um teste pega a divergência). Com o cookie e sem execução encerrada no banco, a carga do andamento devolve fragmento vazio (raro, só visual). POST sem HTMX durante o "saindo" só redireciona, sem aviso (aceito).

**Opções:** A2 e A5: sem alternativa. Cookie repetido: (a) deixar, o teste cobre; (b) passar o nome pelo contexto do template. Recomendação: (a).

**Decisão provisória:** como entregue; cookie repetido fica.

## D67. Segundo plano: falso dos testes sem estado (T98, T113)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão (a decisão da fonte de verdade, A1, está na D61)

**Contexto:** O `FalsoSistema` dos testes de configuração não guarda estado: o teste de desligar força o `is-enabled` na mão, com um comentário.

**Opções:** (a) aceitar como está; (b) dar estado ao falso (T113). Recomendação: (a); só vale (b) se mais testes passarem a depender do estado.

**Decisão provisória:** (a). A T113 está no plano, livre.

## D68. Busca real na rede: resultado da T55 e rodízio da Gupy e da Himalayas (A7, T55)

**Status:** resolvida em 2026-11-15: o dono confirmou a recomendação (rodízio em lotes da Gupy e da Himalayas)

**Contexto:** A sessão rodou a T55 na `fedora-dev` em 2026-11-14 (3 min 8 s, 95 escopos). Todas as fontes da leva A ficaram "ok" ao menos uma vez e nenhuma respondeu 403. Gupy (30 pedidos) e Himalayas (30 pedidos) deixaram escopos `no_limite`: é o rodízio do DR-52, que atende primeiro os escopos mais antigos e deixa o resto para a próxima execução. O user agent fica provado pelos testes de unidade e pela ausência de 403 na rede real. A divergência real, o teto do Ashby, virou a T103 (D69).

**Opções:** (a) manter o orçamento de 30 pedidos e o rodízio; (b) subir `max_pedidos` da Gupy em `fontes.json`. Recomendação: (a): o desenho manda deixar o resto para a próxima execução, e mais pedidos à Gupy pesam em quem não pediu.

**Decisão provisória:** (a). Desfazer: subir `max_pedidos` em `fontes.json`.

## D69. Ashby: teto de 32 MB e motivos do executor (A8, T103)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Na T55, os dois maiores quadros Ashby (14,8 MB e 8,1 MB) passaram do teto de 5 MB e falharam. A API do Ashby não tem paginação nem opção sem descrição. A T103 fez o Ashby ler com teto de 32 MB (o mesmo do feed do Google, `TETO_QUADRO_BYTES` em `nucleo/coletores/ashby.py:32`). O executor também passou a dar motivo próprio ao escopo: `RespostaGrande` vira `saude.resposta_grande` e `ErroDeRede` vira `saude.erro_de_rede`, em vez de `saude.excecao:<Tipo>`. Isso muda o motivo de quem antes caía no genérico: cada coletor que levantava esses dois tipos no escopo agora sai com o motivo novo, e `saude.resposta_grande` está em `MOTIVOS_DE_QUEBRA`, então passa a gerar o link "reportar problema".

**Opções:** (a) teto de 32 MB só no Ashby; (b) teto padrão maior para todos; (c) deixar as duas empresas de fora. Recomendação: (a): é o menor teto que resolve e não afrouxa os outros coletores.

**Decisão provisória:** (a). Desfazer: voltar o teto padrão (as duas empresas ficam de fora).

## D70. Exemplos dos coletores da leva B vêm das respostas reais guardadas (A9)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** Os exemplos (fixtures) dos coletores da leva B saem das respostas reais guardadas na conferência ao vivo de 2026-11-13, reduzidas e limpas pelas funções do `scripts/capturar.py`, em vez de esperar uma captura nova por fonte. Depois de juntar a leva, a sessão roda uma busca real das fontes novas, como a T55, e abre tarefa para o que divergir.

**Opções:** (a) usar as respostas já guardadas; (b) capturar de novo cada fonte. Recomendação: (a): as respostas são reais, e capturar de novo repete pedido às mesmas fontes.

**Decisão provisória:** (a). Desfazer: capturar de novo com `scripts/capturar.py` e trocar os exemplos.

## D71. Descoberta de empresas: sobras da T71 (T71, T108, T109, T110)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- Empresa removida. Aprovar a sugestão de uma empresa já cadastrada e depois removida marca a sugestão como aprovada e devolve o id da removida, sem reativá-la.
- Interrupção. `executar_descoberta` (`src/jobot/agenda/descoberta.py`) pega `BaseException`: fechar o app no meio também marca a execução como interrompida e adia até o dia seguinte, e a próxima recomeça do zero (uns 105 MB do `cluster.idx` de novo).
- Fixtures sem `.meta.json`. `tests/fixtures/common_crawl/` e `tests/fixtures/ptax/` não têm meta.
- Orçamento da Gupy. No ramo da Gupy, `testar` (`nucleo/coletores/descoberta_cc.py:225-237`) usa um só escopo com `max_pedidos=2` para resolver e coletar. Se a página pedir nova tentativa ou salto, o coletar começa sem orçamento e a empresa não é sugerida.
- `descoberta.py` importa o `_bater` privado de `agenda/execucao.py`, e o batimento da descoberta não tem teste próprio.

**Opções:** empresa removida: (a) manter sem reativar, porque a remoção foi ato posterior da pessoa (a T74 pode avisar comparando com `removida_em`); (b) reativar. Interrupção: (a) aceitar; (b) só o 503 e o `LimiteAtingido` adiam até o dia seguinte, o resto tenta de novo no mesmo dia (T108); (c) guardar o candidato recusado, com estado novo no `CHECK` de `empresa_sugerida` (muda o schema). Fixtures: (a) registrar em `registros/padroes.md` que pasta de fonte que não é coletor dispensa meta; (b) acrescentar as metas. Orçamento da Gupy: um escopo por etapa (T109). `_bater`: tornar público e testar (T110). Recomendação: (a), (b), (a), um escopo por etapa e `_bater` público.

**Decisão provisória:** o código segue como está até o dono decidir; as T108, T109 e T110 estão no plano, livres.

**Atualização de 2026-11-14 (A31, A38, A40, leva K):** a T108, a T109 e a T110 foram entregues e juntadas na `dev`. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).
- A D71(b) ficou entregue em parte. No escopo do Common Crawl (`max_pedidos=2`), o `OrcamentoGasto` conta como 503 e adia até o dia seguinte (`agenda/descoberta.py:35-39`), mas ele também aparece na nova tentativa de outro 5xx, de falha de rede ou de salto. Separar os dois exige o `http.py` dizer qual status esgotou o orçamento, que é contrato novo em `nucleo/http.py` (A40). Desfazer: tarefa de contrato no `http.py`.
- Recuo de 1 h (A38, R2 da T108). Para erro que não é 503 nem limite, a descoberta marca a execução como interrompida e só tenta de novo depois de 1 h (`RECUO`, `descoberta.py:34`). Sem o recuo, o laço de 60 s tentaria uma vez por minuto e baixaria o `cluster.idx` (uns 105 MB) de novo a cada vez. O número é escolha do redator, aceita pelo dono em 2026-11-15 (Q7). Opções: 1 h (no máximo uns 15 tentativas por dia num erro persistente), 6 h ou recuo exponencial. Recomendação: 1 h.
- A chave de adiamento passou a ser `descoberta_adiada_ate`, com um instante ISO em UTC (`descoberta.py:33`). Valor estragado trava a descoberta; a T125 faz valer como ausente.

**Atualização de 2026-11-14 (A45, T74, leva L):** a T74 entregou a tela de sugeridas e seguiu a opção (a) da empresa removida. A tela só avisa, com a data de `removida_em` ("Você removeu esta empresa em 13/11/2026. Aprovar não a traz de volta; para acompanhá-la de novo, adicione-a em Empresas."). Aprovar marca a sugestão como aprovada e não reativa a empresa; o botão Aprovar continua no cartão. A opção alternativa é esconder o Aprovar nesses cartões e deixar só Descartar. Recomendação: manter. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).
- Desvio do desenho 13.9 (A45, aceito pelo dono em 2026-11-15, Q7). O desenho pede "Sugeridas" como sub-aba de Empresas. A T74 pôs o link como item de topo do menu, logo depois de Empresas (`painel/templates/base.html:13`; texto `casca.menu.sugeridas` em `painel/i18n/{pt,en}/casca.json:16`); o menu passou de 6 para 7 links, e o `base.html` marca com `aria-current` só a área de caminho mais longo (`/empresas/sugeridas` não marca Empresas). A largura da barra com 7 itens não foi vista em tela estreita; só os testes de contraste e de teclado rodaram. Opções: (a) manter no menu de cima; (b) fazer a sub-aba dentro de Empresas, como o desenho. Recomendação: (a) até alguém ver a tela estreita; (b) vira tarefa pequena de painel. A aprovação das fontes que não são Gupy não testa a fonte ao vivo (desenho 8.7): vira tarefa nova se o dono quiser a contagem de vagas antes de aprovar.
- Sobras da T74 que vão para a T127 (A46): o `ValueError` do resolver da Gupy dá 422 (hoje vira 502 "Não deu para falar com a fonte"), a Gupy grava o identificador que o resolver devolve, e a empresa removida não faz pedido à Gupy antes de aprovar.

## D72. Páginas acompanhadas: DNS, escolhas do redator e o que falta para a T75 (T72, T111, T112)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- DNS antes do primeiro pedido (R2). `verificar` resolve o host e recusa endereço local antes de pedir; o resolver é injetável. O hook do cliente só confere o esquema, então a URL digitada pela pessoa precisava disso. O mesmo código está repetido em `nucleo/coletores/paginas.py` (cópias de `_resolver_padrao` e `_conferir_dns` de `nucleo/http.py`), e a cópia é mais fraca: usa `host_local`, que não recusa texto que não é IP, e o original recusa.
- Escolhas do redator, aceitas pelo dono em 2026-11-15 (Q7): leitura que falha mantém `verificada_em` da última boa e só o `estado` vira `falhou`; a primeira leitura não grava `mudanca_pagina`; `adicionar_pagina` com endereço repetido troca o nome e reativa; lista de nomes locais recusados (sem ponto, `.local`, `.localdomain`, `.lan`, `.home`, `.internal`, `.intranet`, `.arpa`, URL com usuário e senha, IPv4 decimal sem pontos).
- Faltas para a T75: desativar e remover página acompanhada (a coluna `ativa` existe); o `Content-Type` não é lido (tudo vira HTML, com `shortcut:` no código); não há batimento na execução de páginas.

**Opções:** DNS: (a) manter, com o resolver injetável; (b) tornar público o helper de `http.py` e usar o mesmo nos dois lugares, com a regra de recusa do original (T111). Recomendação: (b) numa tarefa pequena, e (a) até lá. Desativar e remover: (a) junto da T75; (b) tarefa própria (T112). Recomendação: (a).

**Decisão provisória:** (a) no DNS e junto da T75 no resto. A T111 e a T112 estão no plano, livres.

**Atualização de 2026-11-14 (T111, leva L):** a opção (b) do DNS foi entregue. `conferir_dns(host, resolver=None)` é público em `nucleo/http.py:175`; a cópia de `nucleo/coletores/paginas.py` e o método `ClienteEducado._conferir_nome` saíram, e `paginas.py` importa o helper (`paginas.py:14,80`). A recusa vale para texto que não é IP, como no original. A mensagem do salto recusado mudou para `<host> resolve para host local`, com a URL de origem só em `add_note` (`http.py:187,265`), e a nota não aparece no log: a T126 devolve a URL à mensagem. O que resta da D72 (desativar e remover página, `Content-Type`, batimento na execução de páginas) é da T75, junto com a T112, na leva M (A48), opção (a). Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Atualização de 2026-11-14 (T75, T112, leva M):** a T75 e a T112 foram entregues e juntadas na `dev`, numa tarefa só (A48). Entraram `desativar_pagina` e `remover_pagina` (`banco/paginas.py:147,158`), o batimento da execução de páginas (`agenda/paginas.py:37`) e a leitura do `Content-Type` (`nucleo/coletores/paginas.py:99-103`: tipo que não é texto levanta `ConteudoNaoLido` e a página fica `falhou`). Sobrou o R4 do motivo da falha de página: a tela só diz `falhou`, porque o banco não guarda o motivo. A opção (a) foi escolhida (A49): coluna `motivo` em `pagina_acompanhada` por migração nova, gravada por `marcar_falhou` e mostrada na tela, na T128 (D85). Página sem `Content-Type` seguir lida como HTML e adicionar de novo o mesmo endereço reativar a página desativada ficaram aceitos (D84). Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Atualização de 2026-11-14 (T128, leva N):** o R4 do motivo da falha foi entregue pela opção (a). A migração `0002_motivo_da_pagina.sql` acrescenta a coluna `motivo TEXT`, nula, em `pagina_acompanhada`. `marcar_falhou(con, pagina_id, motivo)` grava um código do conjunto `MOTIVOS` (`banco/paginas.py:17-19`: `fora_do_ar`, `bloqueada`, `nao_e_texto`, `endereco_recusado`, `grande_demais`, `erro`) e recusa outro com `ValueError` (`banco/paginas.py:152-154`). A leitura `ok` limpa o motivo. `agenda/paginas._motivo` (`agenda/paginas.py:31-43`) traduz a exceção no código. `/sites` e a aba Programas mostram o motivo por `sites.motivo.<código>` em pt e en; página com motivo nulo (falhou antes da migração) mostra o texto genérico, `sites.motivo.desconhecido`. As escolhas e o que sobrou estão na D86 e na D87. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

## D73. Aviso de depreciação do Starlette nos testes (ADR 0021)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** O `TestClient` do Starlette avisa em toda a suíte que pede `httpx2` ("install httpx2"). Hoje só é ruído. A ADR 0021 tirou o Dependabot, então a atualização de dependências é manual.

**Opções:** (a) anotar e tratar na atualização de dependências do fim da fase; (b) filtrar o aviso em `pyproject.toml`. Recomendação: (a): trocar de cliente é mudança de dependência e fica com o dono.

**Decisão provisória:** (a).

**Atualização de 2026-11-14 (T80d, leva N):** a atualização de dependências conferiu o aviso. O Starlette do lock (1.10.0, a mais nova do PyPI) só deixa de avisar se o `httpx2` estiver instalado: o `testclient.py` do Starlette tenta `import httpx2` e, sem ele, cai em `httpx` e avisa. O `httpx2` (2.16.0, exige Python 3.11 ou mais) é dependência nova, e a sessão não o acrescentou (A53). O aviso fica. Opções: (a) `httpx2` só no grupo dev: o `TestClient` o usa, o aviso some e o `src` segue em `httpx` 0.28.1; (b) migrar `src` e testes de `httpx` para `httpx2`, mudança grande de contrato do `HttpEducado`; (c) `filterwarnings` no `pyproject.toml` escondendo o aviso; (d) deixar o aviso. Recomendação: (d), e (a) numa tarefa própria só se o dono aprovar a dependência dev. Decisão provisória: (d). Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

## D74. Busca real da leva B: resultado e as quatro correções (A13, A26, A27, A28, A29, T55b)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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
- Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Atualização de 2026-11-14 (T126, leva M): conferência ao vivo do Oracle e das empresas.** Depois da T126 (a segunda descoberta por keyword está em `oracle_hcm.py:237-239`; a keyword vai entre aspas, `oracle_hcm.py:207-208`), o `scripts/conferir_empresas.py` rodou na `fedora-dev`: Oracle 8 vagas e JPMorgan 20, e a keyword com aspas foi aceita pela API. A rodada de 2026-11-14 (sábado, `dev` `fa22d1e`) conferiu as 83 empresas do `empresas.json`, o primeiro escopo de cada uma, com filtro `BR`, termo `developer` e teto de 5 pedidos por empresa (`MAX_PEDIDOS`, `conferir_empresas.py:27`). Resultado: 81 de 83 respondem. Contam como resposta o estado `ok`, `sem_mudanca` ou `parcial` e o motivo `saude.orcamento`, que é o teto de pedidos da própria conferência (`scripts/conferir_empresas.py:31,43-45`). Os 81 são 76 `ok` mais 5 `no_limite` por orçamento (Localiza&Co, Sicredi, Hapvida, Santander e Mercado Livre). Os 2 que não respondem são a Mastercard (manutenção do Workday) e a Microsoft (`no_limite` por `saude.parou_429`, que não conta).
- `ok`, empresas por fonte: Ashby 5, Greenhouse 15, Lever 8, SmartRecruiters 11, Gupy 25, InHire 2, Quickin 2, Recrutei 2, Sólides 2, Eightfold 2, Oracle HCM 2.
- `ok` com 0 vagas: Beep Saúde e CNA Idiomas (Gupy). O quadro estava vazio no dia; conferir de novo na próxima rodada antes de tirar (A51). Se der 0 outra vez, vira tarefa de tirar a empresa do `empresas.json`. Conferido de novo em 2026-11-14 (A56): não era quadro vazio, e a escolha está na D91.
- `no_limite` pelo teto de 5 pedidos do script, então o número de vagas é um mínimo: Localiza&Co, Sicredi e Hapvida (Gupy, mais de 500), Santander (Workday, mais de 80) e Mercado Livre (Eightfold, mais de 50).
- Mastercard (Workday, `wd1`) `falhou`, `saude.erro_de_rede`, "resposta não é JSON". Conferido à mão: o pedido volta 303 para a página de manutenção do Workday. É manutenção do centro de dados, passageira. A Mastercard é a primeira empresa do Workday no `empresas.json`, então é a sonda semanal do vigia (segunda, 06:23 UTC; `contexto_da_fonte` usa a primeira empresa de cada fonte, `scripts/vigia.py:130-133`); erro de rede não abre issue (`quebrou`, `vigia.py:105-114`), só entra no resumo.
- Microsoft (Eightfold) `no_limite`, `saude.parou_429`, 10 vagas de 24 no Brasil. Conferido à mão: o 429 vem e vai sem depender do ritmo (o mesmo pedido deu 429 e depois 200). O `fontes.json` já tem `por_escopo` para a Microsoft (espera de 5 s, uma vez por dia, para no 429) e o coletor já registra o 429. Aceito como está.
- `conferida_em` não mudou: o script só relata. Nada foi tirado do `empresas.json`.

**Atualização de 2026-11-14 (A56, leva O):** Beep Saúde e CNA Idiomas deram 0 vagas outra vez, e a conferência mostrou que o quadro não está vazio: o filtro `careerPageName` do portal da Gupy não casa essas duas empresas. O achado, as opções e a recomendação estão na D91.

## D75. ATS por empresa da leva B: InHire, Quickin, Recrutei e Sólides (T56, T57, T58, T59, T120)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto e opções:**
- InHire. O link `/vagas/<jobId>` vem do código do site e responde 200, mas a página monta a vaga no navegador e a extensão do Chrome estava desligada: não foi vista aberta (A24, para conferir). A página de carreira que não é a `default` usa outro caminho, e o coletor a ignora. O identificador do tenant é sempre minúsculo: o resolver normaliza, o coletor não, então quem montar `empresas.json` grava em minúsculas. Sem `tenantName`, a empresa vira o identificador. O `.meta.json` leva o campo extra `cabecalho_do_pedido` (X-Tenant), fora de `CAMPOS_META`. Opções: (a) aceitar o campo como convenção dos coletores com cabeçalho de pedido e acrescentá-lo como opcional na lista de `scripts/capturar.py`, numa tarefa pequena; (b) tirar o campo do meta. Recomendação: (a). Status: escolha do redator, aceita pelo dono em 2026-11-15 (Q7).
- Quickin. O nome do escopo e os campos de salário seguem como o código os pôs. O teto de 100 páginas e 3.000 vagas por conta é palpite (a captura tinha 85 vagas) e fica por constante (A18); a opção (b) seria `max_pedidos` no `fontes.json`, que mudaria o orçamento das fontes já testadas. Recomendação: manter a constante. As sobras (host `jobs.quickin.io` e teste que não prova) estão na T120.
- Recrutei. O `remote` 1, 2 e 3 segue o apêndice; só o 0 (presencial) foi confirmado (A23). A empresa é `company_name` (a consultoria de RH), não o `client.name`. Os exemplos de 404 e de "vazio" foram montados à mão. Lista menor que `data.total` vira `parcial` com `saude.listagem_incompleta` (escolha do redator). O `detalhar` só pede no host `jobs.recrutei.com.br` (barreira de SSRF): vaga com link em domínio próprio fica sem descrição. O formato de `expired_at` e de `benefits` é suposto. Recomendação: conferir o `remote` ao vivo depois do merge.
- Sólides. O teto `MAX_PAGINAS = 200` fica por constante (A18). `createdAt` só com data vira meia-noite em Brasília. A moeda é BRL fixa e o período é deduzido. O 404 foi montado à mão: a captura só mostrou 400. Recomendação: manter.

**Decisão provisória:** o código segue como está. As sobras baixas de InHire, Quickin e Recrutei estão na T120 (A25); o exemplo da InHire com UUID corrompido também.

## D76. Portais da leva B: CIEE, IEL, Cia de Talentos e USP (T59, T60, T61, T62, T63, T116, T118, T119)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto e opções:**
- CIEE. `size=1000` cabe no teto de 5 MB (cerca de 1,07 MB por página): fecha a dúvida da T60. Empresa em branco vira "CIEE" (D74).
- IEL. Fuso de `vagaInclusao` (-03:00 suposto) e linhas `T` do Flight com campos longos: para conferir na rede. Lista fixa de 19 UFs (D74); as outras opções e por que a (b) ficou estão na D74.
- Cia de Talentos. O prazo (hoje mais `countFinishDays`) usa o relógio do sistema (`_agora`), porque o contrato do coletor não recebe relógio (A19). Escolhas do redator, para confirmar: a `url` é o `opportunityHotsiteUrl`, senão o de inscrição, e `url_candidatura` é o `opportunityInscriptionUrl`; só `hiringTypeId` 1, 2 e 3 viram contrato, e o texto de `hiringType` (o 13, "Ensino Médio", por exemplo) vai para as etiquetas; `opportunityAreas` entra na descrição. Não achamos termos de uso; o `robots.txt` do site de marketing diz `Allow: /`.
- USP. O detalhe é lido dentro do `coletar`, porque o executor só detalha `UrlListada` (A20); a USP entra ativa na leva B; a empresa das vagas da FEA é "FEA-USP"; o contato da empresa publicado no mural fica na descrição. Os marcadores de lista vazia e a lista do IF (montada à mão a partir do JSON) estão para conferir ao vivo.

**Recomendação:** manter tudo; conferir ao vivo o que está marcado.

**Decisão provisória:** o código segue como está. As bordas pequenas (float inteiro, 404 na página 2, tag aninhada, pager do IF) estão na T119 (A25).

## D77. Fontes mundiais da leva B e o enriquecimento por escopo (T64, T65, T114, T115, T117)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto e opções:**
- Workday. Nome da empresa guardado na instância (D50, A16). Países das buscas, com Brasil quando a lista vier vazia, e local com país, para o rótulo "no Brasil" e o contrato CLT funcionarem nas vagas do Santander (A17, T115). Um escopo por empresa e país: a fase 1 ainda não saiu, então as ocorrências com o nome de escopo antigo não se migram (A33). Resposta 521 ou 422 fica `saude.erro_de_rede`, sem chave nova (A22). Achados da T64: `total` vem 0 nas páginas com `offset` maior que 0, há tenant cuja faceta só tem `locations`, e `postedOn` é relativo (apêndice 3.3).
- Eightfold. Sem país nas buscas, busca o Brasil, também na execução agendada sem busca ativa (A21). O que se perdeu da primeira entrega foi comparado com a seção 3.3 e corrigido (apêndice, "corrigido pela captura de 2026-11-13"). Microsoft primeiro e `Parou429` com cabeçalhos: D74, T117.
- Passo 4 do enriquecimento (A14, A32, T114). Hoje a parada de um escopo tira a fonte inteira do passo 4, e o detalhe sai no ritmo da fonte: Mercado Livre, NVIDIA e Microsoft quase nunca ganham descrição, e os detalhes da Microsoft saem a 1 s em vez de 5 s. Opções: (a) parada que vale para a fonte toda (orçamento, bloqueio, limite) tira a fonte inteira; intervalo e 429 tiram só o escopo onde apareceram; o detalhe usa o `espera_s` e o `para_no_429` do `por_escopo`, e o orçamento de pedidos da fonte é um só, somado entre os escopos; (b) deixar como está. Recomendação: (a). A sessão já disse (A15) que o passo 4 detalha a `VagaColetada` sem descrição (D52).

**Decisão provisória:** (a), na T114 e na T115. Desfazer: voltar a parar a fonte toda no passo 4.

**Atualização de 2026-11-14 (A35 a A37, leva K):** a T114, a T115 e a T117 foram entregues e juntadas na `dev`. Status das duas decisões abaixo: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).
- Retry-After no log (R4 da T117, A36). A T117 deixou o `Retry-After` fora do log: o executor não tem logger e o enriquecimento registra só o nome do tipo (`agenda/execucao.py:273`). Opções: (a) o executor registra `str(erro)` quando o escopo para por `Parou429`, `LimiteAtingido` ou `Bloqueio`, e o `Parou429` que escapa do `coletar` vira `saude.parou_429` em vez de `saude.excecao:Parou429` (`executor.py:140-146`); (b) só o log de `agenda/execucao.py`; (c) campo novo no contrato. Recomendação e decisão: (a), na T123, junto da T106. Desfazer: (b) ou (c).
- Nome do país no Workday (T115, A37). O coletor importa o mapa privado `_PAISES` de `nucleo/tratamento/locais.py` (`workday.py:29,44`). Opções: (a) manter o import privado; (b) `nome_do_pais` público em `locais.py`, mais "Estados Unidos da América" reconhecido e sigla de estado americano que parece UF ("Columbus, MS") sem virar vaga no Brasil em escopo de fora. Recomendação e decisão: (b), na T124. Desfazer: (a).

**Atualização de 2026-11-14 (A36, T106-123, leva L):** a T123 entregou a opção (a) do `Retry-After` no log: `_registrar_parada` (`nucleo/coletores/executor.py:158`) põe no log o texto do `Parou429`, do `LimiteAtingido` e do `Bloqueio` que param um escopo, e o `Parou429` que escapa do `coletar` vira `saude.parou_429` (`executor.py:149-150`), que só vai para o resumo do vigia e não abre issue (travado por `test_parou429_que_escapa_do_coletar_nao_abre_issue`). Falta a listagem: `juntar_paginas` (`nucleo/coletores/base.py:118-125`) captura os três erros e devolve só a chave `saude.*`, então o 429 de uma listagem segue sem `Retry-After` no log. Opções: (a) `log.warning` com o texto do erro nos três `except`; (b) campo novo em `ResultadoEscopo`. Recomendação: (a), na T126 (A46). A T124 entregou `nome_do_pais` público e "Estados Unidos da América" como US (`nucleo/tratamento/locais.py:139`; a T124 acrescentou `irlanda` e `uruguai` para o nome em português de todo código voltar ao mesmo código). Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

## D78. Leva K e as sobras da leva J (A25, A30, A31, A34, T106, T119, T120, T121)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:**
- A25. As sobras baixas da leva J viram tarefas pequenas por assunto: T119 (Cia de Talentos, Sólides e USP), T120 (testes que não provam e exemplos da Quickin, Recrutei e InHire) e T121 (vigia: "voltou" só com o detalhe conferido). Os nomes privados do executor que `scripts/vigia.py` importa (`_PARA_DETALHES`, `_motivo_do_detalhe`, `_motivo_do_escopo`) entram na T106, e o teste de varredura dela também olha `scripts/`, porque o ruff e o mypy de `src` não avisam se alguém os renomear.
- A30. A leva K junta: esta REG8, as correções da busca real (T115 a T118), o enriquecimento por escopo (T114), as sobras baixas da leva J (T119 a T121) e as tarefas livres que não brigam por arquivo (T104, T105, T107, T113 e a trinca da descoberta T108 a T110 numa tarefa só). T106, T111 e T112 ficam para a leva seguinte, porque mexem nos mesmos arquivos que outras desta leva.
- A31. Descoberta: seguem as recomendações da D71 (só o 503 e o limite adiam até o dia seguinte; um escopo por etapa no ramo da Gupy; `_bater` público com teste). Primeira execução: segue a da D62 (um só "Buscar agora"). Sem duplicar aqui o que já está nelas.
- A34. A leva K sai com 14 tarefas, até 8 ao mesmo tempo: Opus em T114, T115, T117 e na trinca da descoberta; Sonnet no resto; revisor do mesmo modelo; effort `high` em todas.

**Opções:** (a) como decidido; (b) esperar o dono para cada sobra baixa. Recomendação: (a): são correções pequenas, cada uma com teste, e não mexem em contrato público.

**Decisão provisória:** (a). Desfazer: não há o que desfazer; as tarefas são independentes e podem ser descartadas uma a uma.

## D79. Sobras da leva K aceitas (A38, T108, T114 a T121)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** decidido pelo dono em 2026-11-14: a Eureca nasce ligada (A66, T136; a A50 está rejeitada)

**Contexto:** o caminho público da Eureca estava em aberto desde o apêndice. A conferência de 2026-11-13 achou a API do aplicativo de candidatos (`candidate-api.eureca.me/opportunities`), que responde sem login. O escopo é um só. Os termos de uso da Eureca são restritivos (a cláusula 7 pede consentimento prévio e expresso), mas manter a Eureca na fase 1 já foi decisão do dono (Q6, de 2026-11-13), com chave liga/desliga, ritmo educado, link para a vaga original e aviso no README; Abler e Gupy seguem a mesma decisão. O link da vaga (`app.eureca.me/vagas/{id}`) foi deduzido do código do aplicativo e não foi aberto: fica para conferir na busca real.

**Opções:** (a) a Eureca entra pela API do aplicativo; (b) tirar a Eureca da fase 1, com o motivo no apêndice. Recomendação: (a), porque o dono já decidiu mantê-la e não há login a contornar.

**Decisão provisória:** (a), na T70. Desfazer: (b).

**Atualização de 2026-11-14 (T70, T55c, leva L):** a T70 entregou o coletor e a busca real o confirmou.
- O que a T70 achou (`portais/eureca.py:29-34`): `GET https://candidate-api.eureca.me/opportunities?page=N&pageSize=200`, JSON sem login, `{items, total, page, pageSize}`; teto local de 10 páginas (`MAX_PAGINAS`, 2.000 vagas; hoje há 9) com `saude.limite_atingido` ao chegar nele. A lista já traz a descrição, sem `ETag` nem `Last-Modified`, então não há pedido condicional. `/programs` ficou de fora: lista programas (grupos de vagas), e cada vaga já traz `programName`. Escolha: manter assim.
- A busca real (T55c): `ok`, 9 vagas em 1 pedido, e o link `https://app.eureca.me/vagas/<id>` saiu no formato esperado. Falta só abrir um link no navegador. O `pageSize=200` explícito foi aceito (a busca real o mandou).
- Pergunta ao dono, que ficou: as notas da conferência de 2026-11-13 recomendam pedir autorização à Eureca antes de ligar o coletor (cláusulas 7.2 e 7.3 dos termos; o endereço foi achado lendo o código do aplicativo). O dono decidiu manter a fonte (Q6/A42), mas a pergunta da autorização não foi respondida. Opções: (a) manter a Eureca ligada por padrão, como a Q6 decidiu; (b) deixar a fonte desligada por padrão até a Eureca autorizar, com o código e o interruptor prontos e o aviso no README dizendo por quê; (c) tirar a Eureca da fase 1. Recomendação: (b), porque a busca real deu certo, o código fica pronto sem perda e os termos são respeitados até a resposta.
- Status: decidido pela sessão em 2026-11-14 com o dono fora; a decisão final do dono está no Status do início da D80. Desfazer (b): ligar o interruptor.
- Sobras da T70 aceitas (D82): `workModels[]` com mais de um valor vira tarefa da T126; `locations.cities` com mais de uma cidade segue lida só por `cityName`.

**Atualização de 2026-11-14 (A50, leva M):** a sessão escolheu a opção (b), que era a recomendação: a Eureca nasce desligada até a empresa autorizar, com o código e o interruptor prontos. Motivo: as notas da conferência apontam as cláusulas 7.2 e 7.3 dos termos, e na dúvida o joBot respeita os termos. É a T130 (D85): um campo opcional no `fontes.json` diz se a fonte nasce ligada, e a semeadura da tabela `fonte` o usa só ao criar a linha, então quem já tem a linha mantém a escolha que fez. O README (T79) explica o motivo e ensina a ligar. A escolha continua sendo do dono. Desfazer: tirar o valor desligado da Eureca no `fontes.json` (uma linha). Status: decidido pela sessão em 2026-11-14 com o dono fora; a decisão final do dono está no Status do início da D80.

**Atualização de 2026-11-14 (T130, leva N):** a T130 foi entregue e juntada na `dev`. O campo opcional `ligada_padrao` (booleano, padrão verdadeiro: `nucleo/coletores/base.py:80`) está no `fontes.json`, e só a Eureca o traz como `false` (`fontes.json:176`). O carregador recusa valor que não seja `bool`, com `ValueError` que cita a chave (`registro.py:29-30`). A semeadura grava `ligada` só ao criar a linha (`banco/cadastros.py:82-96`: o `ON CONFLICT DO UPDATE` não toca em `ligada`), então o banco que já tem a linha da Eureca mantém a escolha que fez. Quem já rodou o joBot antes continua com a Eureca ligada e a desliga em Configurações, na aba de fontes, se concordar com a A50. O nome `ligada_padrao` ficou como escolha do agente (D86). Status: decidido pela sessão em 2026-11-14 com o dono fora; a decisão final do dono está no Status do início da D80.

**Atualização de 2026-11-14 (A66, T136):** o dono voltou e rejeitou a A50. A Eureca nasce ligada, como as outras fontes (A66 é essa decisão do dono). A T136 tirou o `ligada_padrao: false` da Eureca em `nucleo/dados/fontes.json`; o campo `ligada_padrao` continua no carregador e na semeadura (D85), mas nenhuma fonte o usa hoje. O README, o CHANGELOG em pt e en, os textos de Configurações e os testes foram ajustados: o README diz que os termos da Eureca pedem consentimento prévio e ensina a desligar a fonte em Configurações. Quem já tinha a linha da Eureca desligada mantém a escolha, porque a semeadura não toca em `ligada` depois de criar a linha. Status: decidido pelo dono em 2026-11-14.

## D81. Leva L: o que entrou e o que ficou para a leva M (A41, A43)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** a leva L roda até 8 tarefas ao mesmo tempo: os seis coletores que faltam (Oracle HCM, Google, Amazon, Super Estágios, Eureca e Abler), o guia de conserto de fonte (T83), os nomes públicos junto com o log do 429 (T106 e T123, numa tarefa só), o DNS compartilhado (T111), a tela de empresas sugeridas (T74), os textos da tela (T122), o país no Workday (T124), as sobras pequenas (T125) e os registros (REG9). Ficam para a leva M, por mexerem nos mesmos arquivos de tarefas desta leva: a T75 (mexe em `rotas/vagas.py`, como a T106), a T112 (mexe em `tests/unidade/test_paginas.py`, como a T111) e a T76 (`empresas.json`, depende do Oracle HCM).

**Opções:** (a) como decidido; (b) rodar a T75 e a T112 junto, aceitando conflito de arquivo. Recomendação: (a): a leva M sai logo depois, e conflito de arquivo custa mais que a espera.

**Decisão provisória:** (a). Desfazer: tirar uma tarefa da leva (a branch fica, sem merge).

**Atualização de 2026-11-14 (A44, A47, A48, leva L):** a leva L foi juntada na `dev` (commit `b7d542c`), com 13 tarefas aprovadas e a REG9 com duas ressalvas médias no `registros/padroes.md` (as cinco lições perdidas e o limite de 350 caracteres por linha). Bateria: 3.326 testes de unidade, 82 de tela, ruff e mypy verdes. A `dev` subiu ao GitHub como cópia (push simples, sem PR). A busca real das seis fontes novas (T55c) está na D74 e na D80. A leva M foi lançada com seis tarefas a partir de `b7d542c` (A48): T75 junto com a T112 (opção (a) da D72, e as outras faltas da D72), T76, T77, T126 (D82 e D83), T127 e esta REG10. O que a leva L deixou aceito está na D82; o que virou tarefa, na D83.

**Atualização de 2026-11-14 (A49, leva M):** a leva M foi juntada na `dev` (commit `fa22d1e`): 6 de 6 tarefas aprovadas, só com problemas baixos (T75 com a T112, T76, T77, T126, T127 e REG10). Bateria: 3.528 testes de unidade e 91 de tela, ruff e mypy verdes. A `dev` subiu ao GitHub como cópia (push simples, sem PR). A conferência ao vivo do Oracle e das empresas está na D74. O que a leva M deixou aceito está na D84; o que virou tarefa, na D85. A leva N tem seis tarefas: T79 (README e CHANGELOG), T80d (dependências, o segundo passo da T80), T128 (sobras da leva M), T129 (cópias locais nas rotas), T130 (Eureca desligada por padrão) e esta REG11. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Atualização de 2026-11-14 (A53, leva N):** a leva N foi juntada na `dev` (commit `10daf60`): 6 de 6 tarefas (T79, T80d, T128, T129, T130 e REG11), sem conflito. Bateria: 3.588 testes de unidade e 91 de tela, ruff e mypy limpos (o log da junção está guardado com a sessão). A `dev` subiu ao GitHub como cópia (push simples, sem PR). A T79 saiu "não aprovada" nas três rodadas de revisão por uma ressalva média que já existia antes dela: a frase de privacidade do README diz que o joBot só faz pedidos às fontes, ao Banco Central e ao GitHub, e a descoberta semanal pelo Common Crawl, ligada por padrão, também faz pedidos. Foi juntada assim mesmo, e a correção é a T131. O que a leva N deixou aceito está na D86; o que virou tarefa, na D87; as dependências, na D88. A leva O tem duas tarefas: T131 (sobras da leva N) e esta REG12. Depois dela, o que sobra da fase 1 precisa do dono: T81 (rotular o gabarito) e, depois dela, T37 e T78; o roteiro da T80; a T132; e o PR para a `main`. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

**Atualização de 2026-11-14 (A54 a A56, leva O):** a leva O foi juntada na `dev` (commit `0c5ddf1`): T131 e REG12 aprovadas com ressalvas baixas. Bateria: 3.596 testes de unidade, ruff e mypy verdes; na tela, 1 de 91 falhou numa rodada e as duas seguintes deram 91 de 91 (teste instável; a bateria só guardava a última linha, e o script agora mostra o nome do teste que falhar). A `dev` subiu ao GitHub como cópia (push simples, sem PR). Depois veio a T133 (`a51cb69`), com as ressalvas da T131. O que a leva O deixou aceito está na D89; a T133, na D90; a conferência ao vivo da Gupy, na D91. A REG13 registra tudo isso. Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

## D82. Sobras da leva L aceitas (A45, T66 a T74, T83, T106, T123)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** duas tarefas novas, livres, na leva M (no plano, T126 e T127).
- T126, coletores: (1) Oracle HCM, segundo pedido de descoberta com `keyword=<nome do país em inglês>` quando a faceta do país não vem (D74), com `nome_em_ingles` público em `locais.py`; (2) Amazon, `publicada_em` à meia-noite de Brasília, não de UTC (hoje cai no dia anterior); (3) Super Estágios, a empresa `CONFIDENCIAL` (`super_estagios.py:206`) vira `Super Estágios`, como o CIEE faz com `CIEE`, para vagas de empresas diferentes não se misturarem; (4) Eureca, `workModels` com mais de um valor deixa `modalidade_declarada` vazia, como a Amazon faz com tipos mistos; (5) as docstrings de `_FormatoMudou` do Google e da Abler dizem o que de fato levanta, e o sitemap da Abler só com `<url>` sem `<loc>` termina `falhou`, não `parcial` (`abler.py:124`); (6) a mensagem do `ErroDeRede` do salto recusado volta a trazer a URL de origem (D72); (7) `juntar_paginas` registra no log o texto do erro (D77).
- T127, tela e documentos: (1) `painel/rotas/sugeridas.py` usa `relogio_do_painel` e os nomes públicos da T106 no lugar das cópias locais (hoje `_relogio` em `sugeridas.py:48`); (2) na aprovação da Gupy, `ValueError` do resolver dá 422 com mensagem própria, e só falha de rede dá 502 (hoje qualquer exceção vira 502, no `except Exception` de `aprovar_sugestao`); (3) a Gupy grava o identificador que o resolver devolve, em minúsculas (D45 de `empresas.py`); (4) sugestão de empresa removida (D71) não faz pedido à Gupy antes de aprovar; (5) `.github/CONTRIBUTING.md` e `.en.md` perdem a frase de que os comandos exatos serão documentados quando o código existir (linha 38 dos dois), porque o guia já os traz.

**Opções:** (a) uma tarefa por assunto (T126 e T127); (b) deixar tudo aceito, na D82. Recomendação: (a): cada item é pequeno, tem teste e não muda contrato público. A T126 é Opus (a mudança do Oracle mexe na descoberta); a T127, Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva M e mover o item para a D82.

**Atualização de 2026-11-14 (T126, T127, leva M):** as duas tarefas foram entregues e juntadas na `dev` (`fa22d1e`), com problemas só baixos.
- T126: os 7 itens estão feitos. Oracle HCM repete a descoberta uma vez com `keyword` quando a faceta do país não vem (`oracle_hcm.py:237-239`; `nome_em_ingles` público em `locais.py`), com três exemplos novos vindos das respostas reais da T55c; Amazon à meia-noite de Brasília; Super Estágios com `CONFIDENCIAL` virando `Super Estágios`; Eureca sem modalidade declarada com mais de um `workModels`; docstrings e sitemap do Abler sem `<loc>` como `falhou`; salto recusado com a URL de origem; `juntar_paginas` com o texto do erro no log (`base.py:100-101`). O que sobrou está na D84 e na D85.
- T127: os 5 itens estão feitos, e o item 3 pediu o parâmetro `identificador_novo` em `banco/sugeridas.aprovar` (R3, D84). A chave `sugeridas.erro.pagina` (422) entrou em pt e en.
- REG11: corrigiu a frase do Google na D82 e acrescentou a T66 ao `depende_de` da T126. A revisão da REG10 apontou os dois como baixos e não os corrigiu, e a A49 mandou os dois para a REG11.
- Status: decidido pela sessão em 2026-11-14 com o dono fora; o dono aceitou em 2026-11-15 (Q7).

## D84. Sobras da leva M aceitas (A49, T75, T76, T126, T127, REG10)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** três tarefas novas, livres, na leva N (no plano, T128 a T130).
- T128, sobras da leva M: (1) motivo da falha de página (R4 da T75, D72), com coluna `motivo` por migração nova em `pagina_acompanhada`, gravada por `marcar_falhou`, limpa pela leitura `ok` e mostrada em `/sites` e na aba Programas; (2) a aba Programas mostra `falhou` também na página que já mudou antes (`templates/vagas/miolo.html`); (3) teste próprio de `ultimas_diferencas` (`banco/paginas.py:96`); (4) `executar_paginas` relê `paginas_ligadas`, como `executar_descoberta` (hoje só o laço da agenda respeita a chave, e nenhuma rota chama a função direto); (5) `conferir_empresas.py` usa `copy.copy(coletor)` (D50, D60), e o teste de que não escreve no `empresas.json` vira teste de efeito, com sha256 antes e depois; (6) `test_empresas_json_tem_67` ganha nome que diz o que confere; (7) teste do 404 na descoberta com keyword do Oracle HCM (`oracle_hcm.py:219`, hoje sem teste).
- T129, cópias locais nas rotas: `_relogio` em `buscas.py`, `configuracoes.py`, `empresas.py` e `primeira_execucao.py` vira `relogio_do_painel`, e `_SemValidadores`, hoje em `sugeridas.py` e `empresas.py`, fica numa versão só.
- T130, Eureca desligada por padrão (A50, D80 opção (b)): campo opcional no `fontes.json`, validado pelo carregador, usado pela semeadura da tabela `fonte` só ao criar a linha. Atualização de 2026-11-14: a T130 continua entregue (o campo `ligada_padrao` segue no carregador e na semeadura), mas a Eureca não o usa mais: o dono rejeitou a A50 e a T136 tirou o valor dela (D80, A66).

**Opções:** (a) uma tarefa por assunto (T128, T129 e T130); (b) deixar tudo aceito, na D84. Recomendação: (a): cada item é pequeno e tem teste. A T128 mexe em migração, tela e `conferir_empresas.py`, e a revisão dela é Opus; a T129 e a T130 são Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva N e mover o item para a D84.

## D86. Sobras da leva N aceitas (A52, A53, T79, T80d, T128, T129, T130)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** duas tarefas novas, livres, na leva O (no plano, T131 e T132).
- T131, sobras da leva N: (1) o texto de privacidade do README em pt e en (item "Só pedidos de busca", `README.md:318` e `README.en.md:318`) e o texto do painel (`configuracoes.privacidade.telemetria`) esquecem a descoberta semanal pelo Common Crawl, que vem ligada por padrão (`banco/cadastros.py`, `descoberta_cc_ligada`; hosts em `nucleo/coletores/descoberta_cc.py`); a tarefa levanta todo pedido de rede que o joBot faz sozinho e completa os quatro textos; (2) o teste da Eureca de `tests/unidade/test_documentos.py` perde o `skip`, porque a T130 já entrou; (3) o CHANGELOG em pt e en troca os itens que citam D1 e D3 por número por frases com o efeito, ou os tira; (4) teste novo de que todo código de `MOTIVOS` tem a chave `sites.motivo.<código>` em pt e en; (5) o `except` que o `ruff format` partiu em `agenda/paginas.py` volta a uma linha; (6) o teste da migração `0002` aplica só o arquivo dela; (7) o teste de cópias nas rotas olha também `AsyncFunctionDef` e prova por AST que nenhuma rota lê `app.state.relogio`; (8) o teste da Eureca em `test_cadastros.py` deriva o total de fontes ligadas do `fontes.json`, sem o 27 fixo; (9) `_ambiente`, `_rodar` e `_no_linux` (em `configuracoes.py` e `primeira_execucao.py`) e `_um` (em `buscas.py` e `detalhe.py`) ficam numa versão só, se os corpos forem iguais.
- T132, status da fase 1 nos documentos: `CONTRIBUTING.md`, a ADR 0017 e a wiki ainda dizem "em andamento". Atualizar quando a fase fechar, junto com a data da 0.1.0 no CHANGELOG em pt e en. Roda antes do PR para a `main`, depois da T80 e da T81.

**Opções:** (a) uma tarefa por assunto (T131 e T132); (b) deixar tudo aceito, na D86. Recomendação: (a): a primeira corrige uma frase de privacidade que hoje está incompleta, e a segunda só pode rodar quando a fase fechar. As duas são Sonnet.

**Decisão provisória:** (a). Desfazer: tirar a tarefa da leva O e mover o item para a D86.

**Atualização de 2026-11-14 (A54, leva O):** a T131 foi entregue e juntada na `dev` (`0c5ddf1`), com os nove itens, e saiu aprovada com ressalvas baixas. O que ela deixou aceito está na D89, e o que virou a T133, na D90. A T132 segue aberta: roda no fim da fase, depois da T80 e da T81, que dependem do dono.

## D88. Atualização de dependências do fim da fase 1 (A53, T80d)

**Status:** resolvida em 2026-11-14: o dono confirmou a recomendação (a)

**Contexto:** a atualização manual da ADR 0021 (segundo passo da T80) foi feita na leva N, como T80d. O que mudou: `actions/checkout` foi da v4 para a v7 nos três workflows (`ci.yml:21`, `vigia.yml:28`, `wiki.yml:28`), `astral-sh/setup-uv` foi da v6 para a v7 (`ci.yml:22`, `vigia.yml:31`) e o requisito do `uv_build` ganhou o teto `<0.14` (`pyproject.toml:2`; o lock e o `uv build` aceitaram). O que não mudou: nenhum pacote do `uv.lock`, porque o `pyproject.toml` fixa tudo com `==` e `uv lock --upgrade` saiu idêntico; HTMX 2.0.11 e Inter 4.1 já estão na versão estável mais nova, com sha256 igual ao do `.meta.json`. Bateria verde antes e depois. O que ficou de fora, e por quê:
- `setup-uv`: a versão publicada é a v10.3.3. As v8 a v10 trazem quebras de cache (poda desligada na v9; cache desligado em `pull_request_target`, `workflow_run` e `release`, e `version: latest-known` na v10). O `ci.yml` só usa `enable-cache: true`, então a v10 provavelmente não quebra nada, mas a ADR 0021 e o plano mandam a v7.
- `playwright`: o pin é 1.65.1 e existe a 1.65.2 (só patch). Subir o pin pede reinstalar o Chromium da `fedora-dev` e do CI.
- HTMX: a 4.0.1 existe só como dist-tag `next` (major com quebra); o `latest` do npm é o 2.0.11, o que está vendorizado.
- `httpx2`: dependência nova, na D73.

**Opções:** (a) ficar na v7 do `setup-uv`, no playwright 1.65.1 e no HTMX 2.0.11 até a atualização da fase 2; (b) subir `setup-uv` para a v10 e o playwright para 1.65.2 já, em tarefa própria. Recomendação: (a), e fazer o (b) na atualização da fase 2, depois de a linha 4 do HTMX virar `latest`.

**Decisão provisória:** (a). Desfazer: tarefa pequena para subir as versões.

## D89. Sobras da leva O aceitas (A54, A55, T131, T133, REG12)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão; o aviso de versão desligado por padrão (item de `aviso_versao_ligada`) foi substituído pela D105

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

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

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

**Status:** resolvida em 2026-11-14: o dono confirmou a recomendação (d)

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

## D92. Rodada de segurança antes do PR da fase 1 (A60, A61, A64, T134)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão (a varredura extra de segurança segue adiada pelo dono, A75)

**Contexto:**
- (A60) O semgrep (regras `p/python`, `p/security-audit`, `p/owasp-top-ten`, `p/trailofbits`, métricas desligadas) rodou em `src`, `scripts` e `.github`: 215 arquivos, 20 alertas.
- (A60) 10 alertas de variável em `href` nos templates são falso positivo. Todo link de vaga passa por `canonica` (só http/https com host, `nucleo/url.py`) e por `confere_http` (`nucleo/modelo.py`). O link de candidatura passa ainda por `_http` na rota (`painel/rotas/detalhe.py`). A vaga sugerida passa por `confere_http` (`descoberta_cc.py`) e pelo teste de prefixo da rota (`painel/rotas/sugeridas.py`). Os demais são rotas internas ou textos do i18n.
- (A60) 5 alertas de XML sem `defusedxml` (RSS e sitemaps) ficam sem mudança. O Python do projeto (3.14.9) traz o expat 2.9.0, que barra expansão de entidades ('billion laughs'), explosão quadrática e tokens grandes, e o ElementTree não busca entidade externa. `defusedxml` seria dependência nova sem ganho.
- (A61) Actions fixadas pelo hash do commit, com a versão em comentário (T134). 5 alertas de tag mutável nas Actions viraram a T134.
- (A64) Auditoria de configurações inseguras por padrão (segredo de reserva, credencial padrão, falha aberta, criptografia fraca, acesso largo, depuração exposta): 0 achados. Os 7 candidatos caíram na verificação:
  - token do `wiki.yml`: é o token do próprio job, com `persist-credentials: false` e sem gatilho de PR;
  - `contents: write` do `wiki.yml`: o mínimo para enviar a wiki;
  - retorno antecipado na checagem de salto do `http.py`: toda URL de fora recusa host local já no primeiro salto;
  - ausência do cabeçalho Origin no CSRF: o token de 256 bits continua conferido e falha fechado;
  - modo 0644 do arquivo do serviço do systemd: sem segredo dentro;
  - duas mensagens de validação.

**Opções:** (a) aceitar como está; (b) acrescentar `defusedxml` mesmo assim; (c) rodar o semgrep no CI (workflow novo, fase 2). Recomendação: (a).

**Decisão provisória:** (a). Desfazer: abrir tarefa para (b) ou (c).

**Atualização de 2026-11-14 (A75):** o dono adiou a varredura extra de segurança, porque o joBot não guarda dado de ninguém na internet: roda no computador da pessoa, escuta só em `127.0.0.1` e não tem conta nem servidor. A A62 era a decisão da sessão de rodar uma varredura extra de segurança antes do PR da fase 1. A rodada deste item (semgrep, Actions por hash e auditoria de configurações) já está feita e segue valendo; a varredura extra fica para depois, e a decisão de aceitar ou não os achados já feitos continua a (a) acima. Status: decidido pelo dono em 2026-11-14.

## D93. Defeitos do ensaio da T80 corrigidos (A67 a A72, T137 a T142)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** o ensaio da T80 (o roteiro do dono, rodado na `fedora-dev`) achou oito defeitos. Seis viraram tarefa e foram entregues e juntadas na `dev` em 2026-11-14, com a bateria verde (unidade, tela, `ruff check`, `ruff format --check` e `mypy`). Os outros dois estão na D95, e o item da agenda parada tem a D94. As decisões A67 a A72 são as escolhas da sessão em cada tarefa:
- (A67, T137, defeito 1) O teto de 4 MiB do `cluster.idx` da descoberta pelo Common Crawl vale só para os blocos escolhidos para baixar (`_TETO_BLOCO` e `escolher()` em `nucleo/coletores/descoberta_cc.py`). Os blocos de outros sites chegam a cerca de 5,8 MB e nunca são baixados. Toda linha que recusa tamanho 0 continua recusando. Antes, um bloco grande de outro site derrubava a descoberta inteira.
- (A68, T138, defeito 2) A Greenhouse pede o quadro com teto de 32 MiB (`TETO_QUADRO_BYTES` em `nucleo/coletores/greenhouse.py`). A Stripe manda 6,2 MB e o padrão do cliente HTTP é 5 MB.
- (A69, T139, defeito 3) O agendador não roda nada enquanto `primeira_execucao_concluida` não for verdadeira (`cli/servir.py`). O painel e `jobot buscar` não passam por essa trava. A consequência está na D94.
- (A70, T140, defeito 4) A barra de andamento lista as fontes que ainda rodam. A tabela nova `execucao_fonte` (migração `0003_execucao_fonte.sql`) guarda o início e o fim de cada fonte, gravados por callbacks do executor (o fim num `finally` dentro do semáforo). A gravação é de melhor esforço: `sqlite3.Error` vai para o log e não derruba a busca. A marca "visto" é o texto `<prontas>:<chaves>`, ou `-1`. Fonte que espera vaga no semáforo não aparece. A tela mostra até 5 nomes e " +N" para o resto.
- (A71, T141, defeito 6) Em Fontes, a fonte no limite mostra a última rodada real por escopo, por `ultimas_que_rodaram(con)` em `banco/execucoes.py`: uma consulta com `ROW_NUMBER` por (fonte, escopo), sem `no_limite` e sem a linha desligada, chamada uma vez por página. Os escopos são filtrados pelos da última execução, e o recurso "todos os escopos antigos" só vale quando a última execução teve só o escopo `''`. O cartão soma exatamente o que a lista mostra, com a hora mais recente. O selo vem do estado atual (desligada, ou `sem_execucao` se religada). Fonte que nunca rodou mostra "—", com o texto "Nunca rodou" para leitor de tela.
- (A72, T142, defeito 8) Um POST válido em Configurações volta com 303 para `?salvo=1` e a página mostra "Salvo." (em inglês, "Saved."). A aba Aparência fica de fora, porque salva por `/preferencias`. F5 depois de salvar mostra o aviso de novo (aceito). `url_de_volta` (`painel/seguranca.py`) tira o `salvo` do campo `voltar`. Mudou em 2026-11-15 (T193, D131): o aviso some em 5 s e o `salvo` sai do endereço, então o F5 não repete o aviso.

**Opções:** (a) aceitar as seis correções como estão; (b) mudar alguma escolha (por exemplo, o aviso "Salvo." sumir sozinho, ou a barra mostrar também a fonte que espera o semáforo). Recomendação: (a), porque cada correção tem teste e o custo de mudar depois é baixo.

**Decisão provisória:** (a). Desfazer: cada item vira tarefa pequena.

## D94. Agenda parada se o assistente nunca for concluído (A69, T139)

**Status:** resolvida em 2026-11-15: o dono manteve (a agenda espera o fim do assistente)

**Contexto:** desde a T139 (A69, a escolha da sessão de segurar a agenda até o assistente acabar), o agendador não roda nada enquanto `primeira_execucao_concluida` não for verdadeira (`cli/servir.py`). A razão (o comentário do código): sem as preferências do assistente a busca sairia vazia e ocuparia o "Buscar agora" do fim dele. Efeito colateral: quem sobe o `jobot serve` e nunca conclui o assistente fica com a agenda parada, sem aviso. O painel e `jobot buscar` não passam pela trava, então buscar à mão sempre funciona.

**Opções:** (a) aceitar: o painel abre direto no assistente, então quase ninguém chega à agenda sem passar por ele; (b) liberar a agenda depois de N horas sem o assistente concluído; (c) mostrar um aviso no painel dizendo que a agenda está parada até o assistente acabar. Recomendação: (a). (b) rodaria busca sem a pessoa ter escolhido nada; (c) é código novo para um caso raro.

**Decisão provisória:** (a). Desfazer: tarefa para (b) ou (c).

## D95. Defeitos 5 e 7 do ensaio da T80 mantidos como desenhado (A73)

**Status:** resolvida em 2026-11-15: defeito 7 confirmado antes; defeito 5 (rodízio) confirmado pelo dono

**Contexto:** dos oito defeitos do ensaio (D93), dois não viraram tarefa. A decisão A73 é mantê-los como estão:
- Defeito 5: o rodízio de escopos da Gupy, como no desenho 8.3. Com `max_pedidos`, o executor reordena os escopos por `ultima_coleta`, então cada rodada lê uma parte e a seguinte lê as que ficaram para trás.
- Defeito 7: "ligar" o segundo plano vem marcado no Linux (`painel/templates/primeira_execucao/passo2.html:36`), seguindo a intenção do desenho: quem usa no Linux quer a busca a cada 3 horas sem manter o painel aberto, e a pessoa vê a caixa e desmarca se não quiser.

**Opções:** (a) manter os dois como desenhado; (b) abrir tarefa para o rodízio (por exemplo, mostrar na tela quais escopos ficaram para a próxima rodada); (c) deixar o "ligar" desmarcado e a pessoa liga. Recomendação: (a): o rodízio é o desenho e o segundo plano ligado é o que quem instala espera.

**Decisão provisória:** (a). Desfazer: tarefa para (b) ou (c).

## D96. GitHub Sponsors ativo (A74, T143)

**Status:** decidido pelo dono em 2026-11-14

**Contexto:** o dono ativou o GitHub Sponsors em 2026-11-14 (`github.com/sponsors/fezarosa-dev`), o que a ADR 0020 deixava para quando o perfil fosse ativado. A decisão A74 é incluí-lo nos canais de apoio ao lado do Pix e do Buy Me a Coffee. A T143 entregou: `.github/FUNDING.yml`, as seções de apoio do README em pt e en e as páginas da wiki (`wiki/Apoie.md` e `wiki/Support-the-project.md`), com o teste `test_apoio_cita_o_github_sponsors_em_todos_os_lugares`. A ADR 0020 foi atualizada. O QR do Pix continua proibido.

**Opções:** (a) os três canais, como está; (b) tirar algum. Recomendação: (a).

**Decisão provisória:** (a), do dono. Desfazer: tirar a linha de cada arquivo.

## D97. Rótulos medidos e ajustados (T37, T78, T144; A77-A80)

**Status:** resolvida em 2026-11-15: o dono manteve o país BR

**Contexto:** a T37 mediu os rótulos das regras contra o gabarito de 329 vagas (comando `jobot avaliar-rotulos`; o relatório `docs/rotulos-medidos.md` traz só números, sem texto de vaga). A T78 ajustou as regras e a T144 passou a trazer o país e a restrição da própria fonte. As três foram entregues e juntadas na `dev` em 2026-11-14. Acerto por rótulo:

| Rótulo | Antes (T37) | Depois da T78 | Depois da T144 |
|---|---|---|---|
| área | 56,2% | 63,5% | 63,5% |
| nível | 69,0% | 71,7% | 71,7% |
| modalidade | 57,1% | 61,1% | 61,1% |
| contrato | 56,5% | 64,4% | 64,4% |
| avisos | 76,0% | 80,2% | 84,2% |
| país | 67,2% | 79,3% | 87,2% |
| UF | 86,3% | 94,5% | 94,5% |

A meta de 90% só foi batida em UF. Ela não trava a fase 1.

**O que a T78 mudou** (`nucleo/dados/rotulos.json` e `tests/casos/rotulos.json`): exclusões de híbrido (mobile, desenvolvimento, plataforma, framework, aplicação, app); "data entry" fora de dados; gestora com exclusão "de tráfego"; ceo e cto com exclusões ("assistant to", "assistente de" etc.); pl, ssr e mid com exclusões ("pl sql", "mid-market"...); negação de CNPJ; nível achado na descrição com peso 2; províncias do Canadá e cidades estrangeiras conhecidas; `pais_escrito` público. O formulário de buscas mostra o país em inglês ("Itu, Brazil") e todo país do leitor volta igual pelo formulário. O Workday só filtra pelo `location` quando ele traz o país escrito ou, no escopo BR, a sigla de UF ("Sao Paulo, SP"); o tenant que só lista "Austin, TX" fica sem filtro (`shortcut:` no código).

**O que a T144 mudou:** a lista `fontes.so_brasil` em `rotulos.json` (github_issues, gupy, inhire, solides, abler, ciee, iel, super_estagios, cia_de_talentos, eureca, usp) e a lista `fontes.local_e_restricao_de_pais` (himalayas, jobicy, remotive). `tratar()` completa os locais com país BR quando a fonte é só brasileira e nenhum local tem país; o cartão mostra "BR". A vaga remota de himalayas, jobicy ou remotive em que todo local vira país ganha o aviso `restrito_a_pais` (região ou mundo não). Quickin e Recrutei ficam fora, porque têm campo de país próprio. A medição traduz os nomes de fonte da captura antiga (`github-backend-br`, `usp_fea`, `iel_carreiras`...) para o nome do produto. A Sólides passa a pôr o país no texto do local quando a API diz país diferente de Brasil (ajuste da revisão). A `versao_algoritmo` sobe para reprocessar as vagas já guardadas.

**Decisões da sessão:**
- (A77) A fonte que só publica vaga no Brasil recebe país BR quando nenhum local diz país. A lista fica em dados (`rotulos.json`), não no código.
- (A78) Himalayas, Jobicy e Remotive acrescentam `restrito_a_pais` quando a vaga é remota e todo local declarado é país.
- (A79) Correções da T78: o formulário mostra o país em inglês; o Workday só usa o `location` com país escrito (mais a UF no escopo BR); `pais_escrito` é público; números finais da T78 (tabela acima).
- (A80) A A77 vale no produto (`tratar()`), não só na medição: o cartão mostra "BR". O cartão passa a mostrar BR; antes, a decisão (A77, acima) era usar BR só na medição. Quickin e Recrutei ficam fora.

**Riscos e limites:**
- Gupy, InHire, Abler e Cia de Talentos não trazem país: vaga de fora com cidade fora das listas ganha BR (`shortcut:` no código).
- As 10 vagas remotas para o mundo de `github_issues` passam a sair BR. A convenção do D5 dizia sem país; fica assim porque as comunidades são brasileiras.
- Na Gupy, modalidade e contrato aparecem com erro na medição porque o gabarito foi rotulado sem o campo declarado da Gupy. Não é defeito do produto.
- Workday: o tenant que só lista "Cidade, Estado" de fora fica sem filtro de país.
- Sólides com país fora da tabela de países (Angola, Moçambique) ou estado de fora com sigla de UF ainda vira BR (`shortcut:` no código). Região fora da lista (por exemplo "Middle East") junto de país conta como país no aviso `restrito_a_pais`.

**Opções:** (a) manter BR nas fontes brasileiras, como está; (b) voltar a deixar sem país e perder o ganho da T144 no acerto de país (87,2% contra 79,3%). Recomendação: (a): o acerto de país sobe e a lista é dado fácil de editar; o risco são as poucas vagas de fora que passam por BR.

**Decisão provisória:** (a). Desfazer: esvaziar `fontes.so_brasil` em `rotulos.json` e subir a `versao_algoritmo`.

## D98. Triagem do ensaio da T80 (A82)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** a sessão rodou o roteiro da T80 dentro da `fedora-dev`. Dezoito passos passaram; seis defeitos viraram as tarefas T145 a T149 (cidade com nome de país, sinais de vida na busca e no terminal, países no aviso de restrição, cartão "Sem mudança" em Fontes e página nova). Ficam como estão: o rodízio de escopos da Gupy (A73), a ordem por salário com a conversão desligada (salário em dólar sai da ordem), um clique perdido em filtro com cliques muito rápidos (aconteceu uma vez, depende de tempo), a vaga Worldwide sem local no cartão e o "Ligar o segundo plano" marcado por padrão (D95).

**Opções:** (a) corrigir os seis defeitos e manter os outros como estão; (b) abrir tarefa também para os que ficam. Recomendação: (a): os que ficam são desenho já decidido ou esperado.

**Decisão provisória:** (a). Desfazer: abrir tarefa para o item escolhido.

## D99. Cidade com nome de país e UF brasileira vira cidade (T145)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** "Franca, São Paulo" (Gupy e Sólides) virava o país FR. Agora, quando um token tem nome de país diferente de BR e outro token tem UF brasileira, o token vira cidade no Brasil. Os casos ambíguos "Peru, Amazonas", "Denmark, SC" e "SP, Spain" ficam Brasil. "Franca, sp" (sigla minúscula) continua país FR, como antes. A `versao_algoritmo` subiu para 4, para reprocessar.

**Opções:** (a) manter assim; (b) exigir que a fonte diga o país para decidir os ambíguos. Recomendação: (a), e melhorar quando a fonte disser o país.

**Decisão provisória:** (a). Desfazer: voltar o ramo novo de `_ler_um` e subir a `versao_algoritmo`.

## D100. Sinais de vida na busca e no terminal (T146)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** a linha do terminal do `jobot abrir` sai só em português, como o resto da CLI. A fase "depois da coleta" aparece na tela de andamento quando toda fonte ligada já gravou em `execucao_fonte`. O link de pular para o conteúdo fica sem mouse até receber foco.

**Opções:** (a) como está; (b) traduzir a linha do terminal pelo idioma do painel. Recomendação: (a): a CLI inteira é em português.

**Decisão provisória:** (a). Desfazer: abrir tarefa para (b).

## D101. Aviso de restrição diz os países (T147)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** o aviso lista os países na ordem dos locais da fonte; código sem nome conhecido aparece como código ISO.

**Opções:** (a) ordem da fonte; (b) ordem alfabética. Recomendação: (a): a fonte costuma pôr o país principal primeiro.

**Decisão provisória:** (a). Desfazer: ordenar em `paises_texto`.

## D102. Cartão "Sem mudança" mostra as vagas da última rodada que leu (T148)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** o cartão mostra a hora e a duração da checagem, mas as vagas da última rodada que leu; escopo que nunca leu fica em 0. O sintoma "pode rodar de novo" com a hora vencida não reproduziu nos testes; ficou teste de regressão.

**Opções:** (a) como está; (b) mostrar "Vagas 0" quando a checagem não leu nada. Recomendação: (a): o 0 enganava, porque as vagas continuam no banco.

**Decisão provisória:** (a). Desfazer: voltar a contagem da rodada atual em `painel/rotas/fontes.py`.

## D103. Página nova é lida na próxima volta da agenda (T149)

**Status:** resolvida em 2026-11-15: o dono aceitou a decisão da sessão

**Contexto:** a página nova é lida na próxima volta da agenda (até 60 s); a regra de "devida" tem folga de 1 h (23 h). A página que falha é tentada de novo a cada execução de páginas. A execução extra por página nova reinicia o ritmo das outras: no pior caso, até cerca de 48 h entre duas leituras de uma página.

**Opções:** (a) como está; (b) guardar a data da última tentativa por página, para não reiniciar o ritmo das outras. Recomendação: (a) na fase 1; (b) se a espera de 48 h incomodar.

**Decisão provisória:** (a). Desfazer: tarefa para (b).

## D104. Fase 1 marcada como concluída antes dos passos 3, 21 e 24 da T80 (A83, T132)

**Status:** resolvida em 2026-11-14: o dono confirmou a recomendação (a)

**Contexto:** a T132 marcou a fase 1 como concluída nos documentos antes dos passos 3, 21 e 24 do roteiro, que ligam e desligam o systemd do computador e pedem reiniciá-lo. Eles ficam com o dono, junto da semana de teste na rede real (critério 15).

**Opções:** (a) marcar já como concluída e tratar uma falha desses passos como correção numa versão 0.1.x; (b) esperar o dono rodar os três passos. Recomendação: (a): o ensaio da sessão cobriu o resto, e o dono autorizou em 2026-11-14 a sessão a abrir o PR para a `main` quando julgar pronto.

**Decisão provisória:** (a). Desfazer: voltar o status nos documentos para "em andamento" (o teste `test_status_da_fase_1_igual_nos_documentos` acompanha).

## D105. Aviso de versão ligado por padrão (Q3)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** o aviso de versão nascia desligado por causa da regra da ADR 0014. Ele não usa login: uma vez por dia pergunta à API pública de versões do GitHub qual é a última versão; o pedido leva só o user agent fixo e o IP.

**Decisão:** passa a nascer ligado. A pessoa desliga em Configurações, Privacidade. Quem já gravou a escolha mantém a sua. README, README.en, CHANGELOG e o texto de privacidade passam a dizer isso. ADRs 0014 e 0018 atualizadas. Feito na versão 0.1.1.

## D106. Nenhum erro trava, todo erro aparece: versão 0.1.1 (QA, D49)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** pedido do dono: os erros devem ser avisados para a pessoa tomar providência, e nenhum erro, problema ou falta de alguma coisa pode travar o programa. Hoje há buracos: erro inesperado mostra página seca (500), clique HTMX que falha não mostra nada, alguns formulários respondem 422 seco, o passo 2 da primeira execução pode prender a pessoa e "a busca parou" não diz o motivo.

**Decisão:** versão 0.1.1, antes da fase 2, fecha os cinco buracos. Cada aviso diz o que aconteceu e o que a pessoa pode fazer. Tarefas no plano.

## D107. Filtros novos, país e moeda: versão 0.2.0 (QB, QC, QD, QE)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Decisão:** versão 0.2.0, antes da fase 2. Filtros novos na tela de vagas: faixa de salário (de... até...), país, cidade, empresa, publicada há (24 h, 7 dias, 30 dias), "precisa ter estas palavras" e "não pode ter estas palavras". O valor convertido pequeno e apagado embaixo do salário passa a usar a moeda que a pessoa escolher, entre 11: real e as 10 que o Banco Central já fornece (USD, EUR, GBP, CAD, AUD, CHF, JPY, SEK, NOK, DKK), sem fonte nova; outras só se alguém pedir. Nova opção "Meu país" em Configurações: define o país usado quando a busca não tem cidade e a moeda que vem escolhida (Brasil, real). O idioma do painel continua à parte. O desenho detalhado fica em docs/superpowers/specs.

## D108. Mais IAs e teste ao ligar, na fase 3 (QF, QG, QH)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Decisão:** além da sessão do Claude Code, da chave da API da Anthropic e do modelo local, entram Google Gemini, OpenAI e um backend "compatível com OpenAI" (endereço e chave opcional), que atende serviços como OpenRouter, Groq, DeepSeek e Mistral e programas locais como Ollama e LM Studio. Isso reverte a exclusão do Ollama como opção (o pacote continua sem trazer o Ollama). Toda IA, ao ser ligada, mostra um sinal de espera, faz um teste curto e mostra ✓ ou o erro com o que fazer. A IA continua na fase 3, depois da fase 2. ADRs 0003, 0009 e 0014 atualizadas.

## D109. Dica de variações na tela de buscas (QI)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** o encaixe compara a palavra exata, sem sinônimos; comparar pelo sentido só chega na fase 3.

**Decisão:** na tela de buscas, uma dica em pt e en: coloque variações, uma por linha (ex.: infraestrutura, servidores, sysadmin). Feita na versão 0.1.1.

## D110. Ctrl+C sai com 130 em todos os comandos (T154, T158)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** a T153 recomendou sair com 1 quando o `jobot buscar` é interrompido por Ctrl+C. A T154 faz o `main` sair com 130 e a frase "Interrompido." nos outros comandos. Dois códigos para o mesmo gesto confundem quem usa o terminal em script.

**Decisão:** todo comando sai com 130 no Ctrl+C, inclusive o `buscar`; os outros erros seguem com 1, e o motivo da parada continua gravado no banco. Vale a consistência com a T154. Desfazer: voltar o `buscar` a 1 (uma linha e um teste).

## D111. Frase do terminal separada da tela (T153, T158)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** a frase de motivo da parada reaproveitava a chave da tela, que termina com "Clique em Buscar agora para tentar de novo". No terminal não há botão.

**Decisão:** o terminal ganha a chave `execucao.parada.tentar_cli` ("Rode jobot buscar de novo para tentar outra vez." / "Run jobot buscar again to try once more."); a tela fica com a dela.

## D112. CLI só em português, sem escolha de língua (T153, T154, T158)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** o painel tem pt e en, e as mensagens novas do terminal (parada da busca, erro do banco, "Interrompido.") saem em português fixo, como o resto da CLI e como a D100 já decidiu para o `jobot abrir`.

**Decisão:** a CLI continua só em português nesta versão, sem opção de língua. Quem quiser em inglês abre uma tarefa própria (idioma do painel guardado em `config`, lido pela CLI).

## D113. Aviso de erro também nos pedidos de carga, sem insistir (T151, T159)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** pedidos que a página faz sozinha (`hx-get` em `load` e o polling da tela de andamento) também podem falhar, e com o servidor fechado o aviso reabriria a cada tentativa.

**Decisão:** todo erro aparece, inclusive o dos pedidos de carga; depois que a pessoa fecha, o mesmo aviso (mesmo texto) não reabre até um pedido HTMX dar certo, e um aviso de texto diferente abre normalmente.

## D114. Saída do `systemctl` e `str(exceção)` só no log (T152, T159)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** a `Recusa` do segundo plano levava a saída crua do `systemctl` para a tela do passo 2 e de Configurações, e os `except (ValueError, OSError)` passavam o texto da exceção. Isso mostra caminho e jargão a quem não pediu, contra a D106.

**Decisão:** a tela mostra texto fixo ("O systemctl {comando} falhou. Os detalhes ficaram no jobot.log.") e a saída completa vai ao log com `warning`, uma vez, onde a `Recusa` nasce. Vale para todo ponto de `src/jobot/painel` e `src/jobot/sistema` que levava saída de comando ou `str(exceção)` à tela.

## D115. `role='alert'` em aspas simples na casca (T151)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** a região do aviso de erro está em `base.html`, ou seja, em toda página, e vários testes de rota procuram `role="alert"` como sinal de erro da página. Com a região na casca eles passariam à toa.

**Decisão:** o atributo leva aspas simples (`role='alert'`) de propósito, com teste que confere a casca; o HTML é o mesmo para o navegador e o leitor de tela. Desfazer: trocar os testes de rota para outro sinal e usar aspas duplas.

## D116. Os "para confirmar" antigos ficam como estão

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** o critério de zerar "para confirmar" não passa por `grep` literal: sobram 36 ocorrências antigas (fora a legenda da linha 5), todas em D11 a D76 (a D76, "Escolhas do redator, para confirmar", inclusive). São o registro de quando a decisão estava com a sessão, e o dono aceitou todas em 2026-11-15 (Q7).

**Decisão:** ficam como estão, explicadas na linha 5 deste arquivo. O critério vale como "fora do histórico".

## D117. A T157 troca também as frases de versão atual (T157)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** o plano da 0.1.1 listava só SECURITY, CONTRIBUTING e README. Outros arquivos também dizem "versão 0.1.0" como versão atual.

**Decisão:** a T157 troca para 0.1.1 as frases de versão atual de `SECURITY`, `CONTRIBUTING`, `README`, das quatro páginas da `wiki/` que dizem o status, da ADR 0017 e de `docs/decisions/README.md`. Ficam em 0.1.0 as frases históricas: o `## [0.1.0]` do CHANGELOG, as fixtures e os testes que usam a versão como dado.

## D118. Todo 403 mostra "recarregue a página" (T150)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** o único 403 do painel é o do CSRF, que vira a frase `seguranca.recarregue` na página e no fragmento HTMX.

**Decisão:** o handler dá essa frase a todo 403. Se surgir outro 403 (permissão, por exemplo), ele ganha texto próprio na mesma entrega.

## D119. A dica de variações também vai ao passo 1 da primeira execução (T156)

**Status:** decidido pela sessão em 2026-11-15, para confirmar

**Contexto:** a D109 pediu a dica na tela de buscas, mas o campo de cargos aparece também no passo 1 da primeira execução, onde a pessoa nova digita os cargos.

**Decisão:** a dica entra nas duas telas (`buscas.dica.cargos` e `primeira_execucao.p1.cargos_dica`), em pt e en.

## D120. Documentação de arquitetura na wiki (T160)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** o projeto é público e feito para a comunidade manter os coletores, mas não tem uma página que mostre como as peças se encaixam.

**Decisão:** uma página Arquitetura (e Architecture, em inglês) na wiki, com o modelo entidade-relacionamento do banco, as camadas, a sequência de uma busca, os casos de uso e um `classDiagram` pequeno do núcleo, tudo em Mermaid. Um teste prende o ER às migrações e o diagrama às camadas, para a página não envelhecer. Sai antes da 0.2.0. O diagrama de classes UML completo ficou de fora: o código é quase todo função e dataclass, e um diagrama de classes inteiro mostraria pouco.

## D121. Estrutura de pastas do código (T161)

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** `nucleo/coletores/` mistura ATS, agregadores e portais num só nível. As subpastas `carreiras/` e `portais/` que já existem têm uma divisão diferente da do apêndice de fontes (`portais/` guarda até Sólides e Abler). A T161 reorganiza o que já existe.

**Decisão:** os coletores se separam por tipo, seguindo o apêndice de fontes; todo pacote ganha uma docstring que diz o que ele é, com teste que confere; os nomes continuam em português e a raiz do repositório fica como está. Ordem: REG19, T161, T160 e depois a 0.2.0.

**Escolhas da sessão, para confirmar:** a pasta de agregadores se chama `agregadores/` (e não `quadros/`, porque "quadro" já quer dizer a página de uma empresa num sistema de vagas); Sólides e Abler ficam em `plataformas/`; os testes e as fixtures continuam soltos, sem acompanhar as pastas novas. Desfazer: renomear a pasta ou mover os dois coletores, com ajuste dos imports.

## D122. Modelo leve na máquina da pessoa, fases 3 e 6

**Status:** resolvida em 2026-11-15: o dono decidiu

**Contexto:** o problema a resolver é a mesma habilidade escrita de um jeito na vaga e de outro no currículo. Comparar só a palavra exata (D109) não pega isso.

**Decisão:** comparar pelo sentido, com o Laya ajustado (ADR 0015). Se ele pesar demais, o caminho é: quantizar primeiro (int8, cerca de 4 vezes menor); destilar para um modelo menor só se ainda ficar lento num PC comum (8 a 16 GB, sem placa de vídeo); poda manual fica de fora. O modelo roda só na máquina da pessoa. O GitHub Actions nunca recebe currículo nem as vagas da pessoa: só confere que o modelo carrega e acerta um teste pequeno, com exemplos públicos. O treino continua no RunPod. A ADR 0015 ganhou a seção "Modelo leve na máquina da pessoa (2026-11-15)".

## D123. A bateria de testes roda no GitHub Actions (CI1)

**Status:** resolvida em 2026-11-15: o dono pediu; o jeito foi escolha da sessão, para confirmar

**Contexto:** a memória RAM da máquina do dono estoura com a bateria de testes. Ele pediu que os testes rodem no GitHub Actions (repositório público, sem custo), com quantas branches forem precisas lá.

**Decisão da sessão:** o `ci.yml` ganha o gatilho de push para branches `lote/**` do próprio repositório e o `workflow_dispatch`. Tudo o que a sessão rodaria na máquina (a bateria antes de juntar, a conferência do vermelho contra o código antigo e a nova rodada depois de uma correção) sobe numa branch `lote/<nome>` e roda no Actions. Uma tarefa só entra na `dev` com o CI verde, e a branch remota é apagada depois. Na máquina fica só o arquivo de teste da própria tarefa (vermelho e verde de quem implementa) e o `ruff`. A ADR 0018 ganhou a linha do novo gatilho. Desfazer: tirar o `push` e o `workflow_dispatch` do `ci.yml` (o `test_ci.py` acompanha).

**Decisão do dono, no mesmo dia:** a `dev` vai para o GitHub toda vez que algo verde entra nela, e o PR da `dev` para a `main` sai com menos frequência, quando juntar um bloco bom, sem pedir de novo. Antes, os dois esperavam o fim da fase.

## D124. 2Captcha: resolver CAPTCHA pelo serviço da pessoa (ADR 0022)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** o dono pediu, por voz, um campo em Configurações para a chave de API do 2Captcha e um liga/desliga; nas telas com CAPTCHA da navegação automática, com a chave posta e ligada, o 2Captcha resolve. Pediu também uma tela bonita, com animações e sem controle padrão do HTML. Hoje a ADR 0005 diz que o joBot nunca tenta contornar CAPTCHA e que a janela fica parada para a pessoa resolver. A fase 1 não tem navegador, e o token do 2Captcha sozinho não passa a tela "Just a moment" do Cloudflare num cliente HTTP. O desenho completo está em `docs/superpowers/specs/2026-11-15-captcha-design.md`.

**Decisão da sessão, para confirmar:**

- Escopo: o 2Captcha só age na navegação com login da fase 2 (Chrome visível pelo Playwright, com o perfil do joBot, ADR 0005). As fontes públicas seguem a ADR 0004 sem mudança: CAPTCHA é "a fonte falhou".
- Vem desligado. O interruptor fica travado enquanto não houver chave salva, e o servidor recusa ligar sem chave.
- A chave fica no cofre de senhas do sistema, pela `keyring` (já decidida na ADR 0014, licença MIT), fixada com `==`. Sem cofre: arquivo legível só pelo usuário (0600) na pasta de dados, e aviso no painel. O interruptor fica na tabela `config` (chave `captcha_ligado`, padrão falso em `cadastros.PADROES`).
- Tipos: reCAPTCHA v2 (inclusive invisível), reCAPTCHA v3 e Cloudflare Turnstile, pelas tarefas sem proxy da API JSON (`createTask`, `getTaskResult`, `getBalance`, em `https://api.2captcha.com`). hCaptcha fica fora (não está na documentação pública).
- Fluxo da fase 2: o navegador acha o desafio, pede ao 2Captcha com o endereço da página, a `sitekey` e o user agent do próprio navegador, consulta a cada 5 segundos ou mais, com tempo-limite total de 180 segundos, injeta o token e segue. Falha, tempo esgotado, saldo zero ou chave errada: cai no comportamento da 0005 (aviso vermelho, janela parada). Uma tentativa por página por rodada.
- Teto de gasto: no máximo 30 resoluções por dia, valor fixo no código (não é configuração). Cada resolução vai para o `jobot.log` com o custo, sem a chave.
- O que entra já, junto da 0.2.0: a aba nova "Serviços" em Configurações com o cartão do 2Captcha (campo de chave mascarado com botão mostrar e ocultar, Salvar, Apagar chave, interruptor, botão "Testar chave" que mostra o saldo), o cofre e o cliente da API no núcleo (saldo e resolver), tudo testado offline. A cola com o navegador (achar o desafio e injetar o token) entra com a fase 2.
- Texto honesto no cartão: vale para a navegação com login, que chega numa versão futura; as fontes públicas nunca usam; resolver CAPTCHA pode ir contra os termos de alguns sites e a conta pode ser restringida; cada resolução custa dinheiro da conta da pessoa no 2Captcha. O link para o site do 2Captcha abre no navegador da pessoa (`target="_blank"`, `rel="noopener noreferrer"`); o painel não carrega recurso externo.
- A chave nunca volta ao HTML (só pontos e os 4 últimos caracteres) e nunca vai para log, mensagem de erro ou exceção. Salvar com o campo vazio mantém a chave atual. Apagar é um POST próprio, com CSRF.
- Erros da API viram mensagens do painel por um conjunto fechado de códigos (chave inexistente, sem saldo, sem vaga no momento, não resolvível, IP bloqueado, conta suspensa, tempo esgotado, outro), nos catálogos pt e en.
- Rede: pelo `ClienteEducado` do núcleo (já aceita `POST` com `corpo_json`, `src/jobot/nucleo/http.py:302-312`), com o relógio injetado; o painel não importa `httpx`. O cliente não tem lista de hosts permitidos (`nucleo/http.py:238`), então `api.2captcha.com` passa sem mudança; o construtor confere com um teste e cuida de o `createTask` não ser repetido em erro de rede.
- Visual: interruptor animado (melhora o `.chave` de `configuracoes.css`: mola na bolinha, cor do trilho em transição, bolinha que estica ao apertar, anel de foco, estado desativado de verdade); campos de texto e de chave com estilo próprio; botão com indicador de espera durante o teste (classe `htmx-request`); resultado do teste entra com fade e leve deslize; tudo respeita `prefers-reduced-motion`; acessível (rótulo, `aria-pressed` no olho, `aria-live` no resultado). JS só em arquivo do próprio painel (CSP `script-src 'self'`).

**Escolhas da sessão dentro desta decisão, para confirmar:** o nome `captcha_ligado` (e não `captcha.ligado`) para seguir o padrão das outras chaves e cair na conferência de `test_integracao_final.py`; o interruptor grava na hora, num POST próprio, e não pelo "Salvar" da chave; o botão "Testar chave" usa a chave digitada, se houver, senão a salva, e não grava; o tamanho aceito da chave é de 16 a 64 caracteres, só letras e números.

**Ainda aberto para o dono** (seção 7 do desenho): o teto de 30 por dia; chave em arquivo 0600 quando não há cofre; uso em todos os sites ou por site; saldo só ao clicar em "Testar chave"; nome da aba.

**Como desfazer:** tirar a aba e o cliente da API, apagar a chave do cofre, e voltar a 0005 e a 0014 ao texto anterior (a 0022 passa a "substituída" ou sai).

## D125. IA pela sessão do Claude Code e do Codex, com botão Baixar (ADR 0009)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** na configuração da IA, o dono pediu, por voz, rodar pela sessão do Claude Code e, se der, pela sessão do Codex da OpenAI, com um botão de download ao lado que baixa ou leva à página de download. A fase 3 (IA, ADR 0017) é quem constrói; agora só se registra. (Numeração antiga das fases; a atual está na [ADR 0017](docs/decisions/0017-fases.md).)

**Decisão da sessão, para confirmar:**

- Nada é construído agora; só o registro, na ADR 0009 e no desenho `docs/superpowers/specs/2026-11-15-captcha-design.md` (parte F).
- A sessão do Claude Code já está decidida (ADR 0010). Entra também a sessão do Codex CLI da pessoa (comando `codex exec`), com teste ao ligar no molde da 0009. Antes de construir, conferir nos termos da OpenAI se o uso do plano do ChatGPT em automação pessoal é permitido; a documentação pública recomenda chave de API e não autoriza nem proíbe o plano, e os Termos de Uso vigentes não foram lidos. Se não for permitido, o Codex entra só com chave de API (o backend OpenAI que já existe).
- Ao lado de cada backend de sessão, um botão "Baixar" que abre a página oficial de instalação no navegador da pessoa (Claude Code: <https://code.claude.com/docs/en/setup>; Codex: a página oficial do Codex CLI, endereço conferido na fase 3). O joBot não baixa nem roda instalador: a página oficial escolhe o sistema certo, e o painel não carrega recurso externo. O botão aparece quando o programa não é achado no `PATH`. (Numeração antiga das fases; a atual está na [ADR 0017](docs/decisions/0017-fases.md). Atualização: o botão agora instala pelo instalador oficial do programa, e o joBot nunca remove o que instalou; ver [ADR 0023](docs/decisions/0023-tudo-pelo-painel.md).)
- "Codex" é marca da OpenAI; o joBot não é afiliado à OpenAI (mesma linha que já existe para o Claude).

**Como desfazer:** tirar o backend do Codex e o botão da ADR 0009; nada de código a desfazer.

## D126. Quatro escolhas do desenho da 0.2.0, limite de 1 s relativo e salário sem moeda na URL (D107)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** o desenho da 0.2.0 (`docs/superpowers/specs/2026-11-15-0-2-0-filtros-moeda-design.md`) deixou quatro perguntas na seção 7 para o dono, mais dois pontos que a sessão fechou ao conferir o código. O dono está ausente; a sessão decidiu pela recomendação de cada uma e o desenho já segue essas respostas.

**Decisão da sessão, para confirmar:**

- Vaga sem salário sai quando o filtro de salário está ligado, com o aviso "N vagas sem salário ficaram de fora" e um jeito de incluí-las (`sem_salario=1`).
- "Meu país" é perguntado no passo 1 da primeira execução, já marcado pelo `Accept-Language` (região em `_PAISES`) e, sem ele, BR. O "pular" também grava o valor pré-escolhido quando ainda não há um.
- Os campos novos (salário, cidade, empresa, "não pode ter") ficam dentro de "Mais filtros"; os chips de país e "publicada há" ficam à vista (opção b da seção 7).
- País fora das 11 moedas mostra em USD.
- Desempenho (parte H): o limite de 1 s vale para o acréscimo de cada filtro novo sobre a vista atual, medido antes e depois na mesma máquina pelo script da parte H (comparação relativa, sem máquina de referência). A vista sem filtro também é medida; se ela já passar de 1 s, vira uma D para a próxima versão, sem tarefa na 0.2.0.
- Salário (parte B): `sal_de` e `sal_ate` seguem em unidades da moeda de exibição Y, sem moeda na URL (painel local, Y muda pouco). Um link antigo reaberto depois de trocar Y lê os mesmos números na moeda nova.

**Como desfazer:** o dono manda trocar qualquer item. Vaga sem salário: tirar o filtro `sem_salario` e o aviso, ou deixar a vaga sempre dentro. Meu país: tirar o campo do passo 1 e deixar só em Configurações. Posição dos filtros: mover os chips para dentro do `<details>` (opção a; o custo é o mesmo). Moeda desconhecida: trocar o USD por uma pergunta ou por BRL. Limite: voltar ao 1 s absoluto numa máquina de referência. Moeda na URL: acrescentar o parâmetro e a conversão na rota. Nada disso está construído ainda; basta mudar o desenho e as tarefas.

## D127. Escolhas do plano do 2Captcha (T180 a T187)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** o plano do 2Captcha (`docs/superpowers/plans/2026-11-15-captcha.md`) fez escolhas que o desenho (`docs/superpowers/specs/2026-11-15-captcha-design.md`) deixou em aberto. Elas seguem a D124 (CAPTCHA resolvido pelo serviço que a pessoa liga, só na navegação com login da fase 2); o dono está ausente e a sessão decidiu pela recomendação de cada uma. Cada escolha tem o teste que a prende.

**Escolhas do plano:**

| # | Escolha | Teste |
|---|---|---|
| E1 | `saldo` e `resolver` recebem o `ClienteEducado` (não um `HttpEducado`): o `createTask` sai num escopo próprio com `max_pedidos=1`, que transforma a repetição automática em `OrcamentoGasto`. O contrato do `HttpEducado` não muda. | `test_erro_de_rede_no_createtask_nao_abre_segunda_tarefa` |
| E2 | O prazo de 180 s conta pelo relógio injetado, no topo de cada volta. Por fora, um teto real `asyncio.timeout(PRAZO_S + MARGEM_S)` em volta da resolução inteira (com o `RelogioFalso` nunca dispara) e `max_pedidos` também no escopo da consulta. | `test_passou_de_180_s_e_tempo_esgotado`, `test_503_com_retry_after_longo_nao_passa_do_prazo` |
| E3 | Todo escopo do 2Captcha usa `para_no_429=True` e `teto_espera_s=30`: 429 vira `OUTRO` na hora; 503 com espera acima de 30 s também, sem dormir (frequência errada pode bloquear a conta). O parâmetro `teto_espera_s` é novo no `escopo` do `ClienteEducado`, opcional e `None` por padrão. | `test_saldo_429_vira_outro_sem_esperar`, `test_teto_espera_corta_retry_after_longo` |
| E4 | O conjunto fechado ganha `TETO_DIARIO`, além dos oito do desenho. | `test_teto_recusa_antes_do_pedido` |
| E5 | Sem vaga (`errorId` 2) até o prazo acabar devolve `SEM_VAGA`, não `TEMPO_ESGOTADO`. | `test_sem_vaga_ate_o_fim_e_sem_vaga` |
| E6 | `userAgent` vai só no reCAPTCHA v2: a seção 4 do desenho lista o campo só nele. | `test_resolver_recaptcha_v2`, `test_resolver_recaptcha_v3`, `test_resolver_turnstile` |
| E7 | Teto e contador em `banco/captcha.py` (`TETO_DIA = 30`), na chave `captcha_uso` da `config`, com `{"dia": "<AAAA-MM-DD local>", "n": <int>}`, num comando SQL só. Conta antes do `createTask`, uma vez por chamada de `resolver`. | `test_reserva_ate_o_teto_e_recusa_a_seguinte`, `test_reserva_e_um_comando_so` |
| E8 | O portão da fase 2 é `captcha_pronto(con, chave)`, no `banco`. | `test_pronto_so_com_chave_e_ligado` |
| E9 | Cofre: lê do sistema e depois do arquivo; grava no sistema e confere lendo de volta; deu certo, apaga o arquivo antigo; caiu no arquivo, tenta apagar a cópia do sistema. Apagar confere lendo de volta (ainda lá = `OSError`). Arquivo `<pasta de dados>/<nome>.segredo`. Log só com o tipo da exceção, sem `exc_info`. | `test_gravar_no_cofre_apaga_o_arquivo_antigo`, `test_cofre_que_falha_cai_no_arquivo_0600`, `test_reserva_no_arquivo_nao_deixa_chave_velha_no_sistema`, `test_apagar_que_o_cofre_recusa_levanta` |
| E9b | Chamadas ao cofre no painel com `asyncio.wait_for(run_in_threadpool(...), 15)`; estourou = `erro.cofre`. `shortcut:` a thread do keyring fica presa até o cofre responder; trocar quando houver API assíncrona. | `test_cofre_que_trava_vira_erro_em_15_s` |
| E9c | Dependências da `keyring` aceitas pelo ADR 0014; licença fora de MIT/BSD/Apache = parar (R4). A T180 lista a diferença do `uv.lock` (abaixo). | conferência manual na T180 |
| E10 | Os testes rodam com `PYTHON_KEYRING_BACKEND=keyring.backends.fail.Keyring` (posto no topo de `tests/conftest.py`): nunca tocam o cofre real de quem roda. | `test_testes_nunca_tocam_o_cofre_real` |
| E11 | "Testar chave" responde 200 com o resultado no fragmento, também no erro (o HTMX não troca resposta 4xx). Prazo do teste: 30 s. | `test_cada_falha_da_api_vira_o_texto_dela` |
| E12 | Ligar sem chave salva: 409. | `test_ligar_sem_chave_da_409_e_nao_grava` |
| E13 | Saldo com 2 casas, cortando (`ROUND_DOWN`), separadores do idioma, sem moeda. | `test_decimal_curto` |
| E14 | Custo fora do formato vira `None`; a resolução continua valendo. | `test_custo_torto_fica_none` |
| E15 | O interruptor é o `<input type="checkbox">` nativo com `role="switch"`, sem `aria-checked` (o estado vem do `checked`). | `test_espaco_liga_e_desliga` |
| E16 | Cor nova `--sucesso: light-dark(#1e7b34, #30d158)` em `base.css` (5,33:1 no `#fff`, 4,9:1 no `#f5f5f7`, 8,42:1 no `#1c1c1e`), com par no contraste. | `test_contraste_minimo`, `test_resultado_ok_usa_o_token_nos_dois_temas` |
| E17 | O `ClienteEducado` do painel nasce num lugar só (`painel/cliente.py:cliente_do_painel`), usado por empresas, sugeridas e serviços. | `test_cliente_do_painel_definido_uma_vez` |

**Parâmetro novo:** `teto_espera_s` no `escopo` do `ClienteEducado` (E3): opcional, `None` por padrão; os escopos do 2Captcha passam 30. Quem não passa nada mantém o comportamento de antes.

**Dependências que a T180 trouxe no `uv.lock`** (`keyring==25.7.0` é a única direta, fixada com `==`; as demais são transitivas):

| Pacote | Versão | Licença | Roda para o 3.14 |
|---|---|---|---|
| keyring | 25.7.0 | MIT | `py3-none-any` |
| jaraco-classes | 3.4.0 | MIT | `py3-none-any` |
| jaraco-context | 6.1.2 | MIT | `py3-none-any` |
| jaraco-functools | 4.6.0 | MIT | `py3-none-any` |
| more-itertools | 11.2.1 | MIT | `py3-none-any` |
| jeepney | 0.9.0 | MIT | `py3-none-any` (só Linux) |
| secretstorage | 3.5.0 | BSD-3-Clause | `py3-none-any` (só Linux) |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | `cp311-abi3` (vale no 3.14) e `cp314-cp314t`, manylinux e musllinux (só Linux) |
| cffi | 2.1.1 | MIT | `cp314-cp314` e `cp314t`: rodas de Linux (manylinux e musllinux) e de iOS; sem Windows nem macOS no lock |
| pycparser | 3.12 | BSD-3-Clause | `py3-none-any` |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | `py3-none-any` (só Windows) |

`cryptography` e `cffi` entram só pelo `secretstorage`, que o `keyring` pede só no Linux: por isso o `uv.lock` não traz roda de Windows nem de macOS para eles. Todas as licenças estão em MIT, BSD ou Apache, como manda a E9c.

**Escolhas extras da construção, para confirmar:**

- `HttpEducado` ganha `seguir_saltos=False` nos escopos do 2Captcha: o POST com a chave no corpo não segue 307/308 (o httpx reenviaria o corpo ao `Location`). Aditivo, padrão `True`.
- Cofre: apagar com o cofre trancado levanta `OSError`; só `NoKeyringError` conta como "não há cofre".
- Cofre: `NoKeyringError` loga em DEBUG; outras falhas em WARNING, só com o tipo da exceção.
- Cofre trancado no gravar: a chave velha do sistema pode voltar depois do desbloqueio (atalho aceito).
- Teste da chave: `POST /configuracoes/servicos/captcha/testar` responde sempre 200, com prazo de 30 s (`PRAZO_TESTE_S`); o log da falha traz só o tipo da falha.
- T173 nova: o detector de camadas resolve import relativo.

**Como desfazer:** o dono manda trocar qualquer item; nada disso está no ar. Para mudar uma escolha, basta mudar o plano e a tarefa dona (a coluna "Teste" diz qual).

## D128. Escolhas do redator da 0.2.0: filtros, país e moeda (T162 a T170)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** o desenho da 0.2.0 (`docs/superpowers/specs/2026-11-15-0-2-0-filtros-moeda-design.md`) e o plano (`docs/superpowers/plans/2026-11-15-0-2-0.md`) deixaram detalhes para quem escreve o código. O dono está ausente; a sessão decidiu pela recomendação de cada um, complementando a D126.

**Decisão da sessão, para confirmar:**

- Coroas (SEK, NOK, DKK) e franco suíço (CHF) aparecem pelo código, não por símbolo: o símbolo "kr" é o mesmo para as três coroas e "Fr" é ambíguo.
- `publicada` (há quantos dias) conta dentro do `contar_chips`, como os outros chips, e não numa consulta à parte.
- A conversão da moeda Y (a de exibição) para BRL mora em `nucleo/cambio.py`, junto da conversão que já existia.
- A linha do valor convertido segue a ordem "≈ valor · cotação".
- Vaga em BRL sem cotação da moeda Y: sem linha de convertido e sem nota (já está em reais). Vaga em outra moeda (nem BRL nem Y) quando Y não tem cotação: mostra o valor em reais, com a nota "em reais: ainda não temos a cotação de {moeda}" (en: "shown in reais: no {moeda} exchange rate yet").
- `sql_de_listar` é público em `banco/leitura.py`, para o teste de plano (`EXPLAIN QUERY PLAN`) usar o mesmo SQL da tela.
- Escolhas da construção da T169: `_SIMBOLO` com CAD `C$`, AUD `A$` e JPY `¥`; a data da cotação mostrada é a mais antiga das duas (taxa cruzada); valor convertido que passa do `INTEGER_MAX` do SQLite (cotação minúscula) some em vez de dar erro 500; cotação da vaga estragada (valor não finito, menor ou igual a zero, ou data ilegível) faz sumir só a cotação e mantém o convertido, nos dois ramos (exibição em reais e moeda cruzada).
- O teste de plano compara a consulta com e sem o filtro, porque o texto do `EXPLAIN` muda com a versão do SQLite (o CI tem um SQLite mais velho).

**Como desfazer:** o dono manda trocar qualquer item; nada disso muda dado gravado. Coroas e CHF: trocar o código pelo símbolo em `_SIMBOLO`. Chip `publicada`: mover para uma consulta própria. Ordem da linha: trocar a ordem no template. Vaga em outra moeda sem cotação de Y: esconder a nota, ou mostrar o valor original sem converter. Teste de plano: voltar a comparar o texto exato do `EXPLAIN`, o que quebra quando o SQLite muda.

## D129. Custo dos filtros com 300 mil vagas e o que fazer na próxima versão (T170)

**Status:** resolvida em 2026-11-15: medição feita pelo script da parte H; as propostas valem para a próxima versão, sem tarefa na 0.2.0 (D126). Na 0.2.1 foram feitos o item 1 (chips depois da lista) e o item 3 (índice, migração `0006_ocorrencia_fonte_vaga.sql`: de 2,216 s para 0,458 s com 300 mil vagas); ver D131

**Contexto:** a D126 pôs o limite de 1 s no acréscimo de cada filtro novo sobre a vista sem filtro, medido na mesma máquina, e mandou registrar a vista sem filtro também. `scripts/medir_filtros.py` semeia 300 mil vagas (316.667 locais, banco de cerca de 400 MB em disco) e cronometra, para cada filtro, `listar`, `contar_chips` e `contar_abas` (mediana de 3 rodadas, em segundos). Máquina: AMD Ryzen 5 220 (12 threads), 14 GB de RAM, com cerca de 5,7 GB livres e outros programas abertos durante a medição. Os valores valem pela comparação entre as linhas, não em absoluto.

| Filtro | listar | chips | abas | total | acréscimo |
|---|---|---|---|---|---|
| sem filtro novo | 0,209 | 4,622 | 0,636 | 5,466 | 0 |
| país | 0,211 | 4,824 | 0,626 | 5,660 | +0,194 |
| UF | 0,208 | 5,349 | 0,653 | 6,210 | +0,744 |
| cidade | 0,579 | 9,112 | 0,661 | 10,352 | **+4,886** |
| empresa | 0,424 | 5,573 | 0,628 | 6,625 | **+1,159** |
| publicada há 7 dias | 0,134 | 3,009 | 0,626 | 3,769 | -1,697 |
| não pode ter | 0,207 | 4,496 | 0,619 | 5,322 | -0,144 |
| salário: só de | 0,713 | 7,175 | 0,631 | 8,518 | **+3,052** |
| salário: só até | 0,157 | 3,105 | 0,628 | 3,889 | -1,577 |
| salário: de e até | 0,560 | 5,915 | 0,621 | 7,096 | **+1,630** |
| salário: com sem salário | 0,177 | 4,299 | 0,624 | 5,100 | -0,366 |
| todos juntos | 0,558 | 6,144 | 0,623 | 7,325 | **+1,859** |

Acréscimo negativo é filtro que encolhe a lista e os chips. `contar_abas` não recebe filtro: custa o mesmo em toda linha. O plano de consulta (`tests/integracao/test_plano_consulta.py`) confirma que os índices da 0005 entram em país, UF, cidade, publicada e nos três casos de salário.

**O que a medição mostra:**

- A vista sem filtro já passa de 1 s (5,5 s), quase toda em `contar_chips` (4,6 s). `listar` leva 0,2 s. Dos chips, o de fonte custa 2,2 s (junção com `ocorrencia` e `COUNT(DISTINCT)`), UF 0,8 s, país 0,4 s e os outros cerca de 0,2 s cada.
- Cidade e empresa passam de 1 s porque a condição chama a função `jobot_normalizar` em Python para cada linha de `local_vaga` ou de `vaga` (o índice `local_vaga_vaga` só resolve a junção por vaga; o `LIKE` sobre `jobot_normalizar` não usa índice nenhum), e cada uma das 9 consultas dos chips repete a condição. Uma só consulta de contagem leva 0,6 s (cidade) e 0,4 s (empresa).
- Salário "só de" usa `vaga_sal_alto_brl`, mas o filtro deixa passar cerca de 159 mil das 300 mil vagas nos dados medidos: o índice não poupa trabalho e as 9 consultas dos chips repetem a condição. "De e até" passa de 1 s pelo mesmo motivo.

**Proposta para a próxima versão (sem tarefa na 0.2.0):**

1. **Feito na 0.2.1 (T191, D131).** Chips fora do caminho da lista: um fragmento HTMX (`hx-trigger="load"`) busca as contagens depois que a lista aparece. A lista chega em cerca de 0,2 s mesmo com filtros pesados, e a vista sem filtro deixa de bloquear. Resolve a vista sem filtro e o custo extra dos chips em todas as linhas acima.
2. **Não feito (D131).** Cidade e empresa: gravar o texto já normalizado numa coluna própria (`local_vaga.cidade_normalizada` e `vaga.empresa_normalizada`, preenchidas junto de cada gravação) e filtrar por prefixo com índice. Isto muda o filtro de "contém" para "começa com" (mudança de contrato, a decidir com o dono). O `LIKE` só usa índice com collation `NOCASE` na coluna; mais simples é a faixa `col >= :p AND col < :p_proximo` sobre a coluna já normalizada. Se a busca precisar achar no meio do nome, a alternativa é uma tabela FTS5 só para cidade e empresa. As duas pedem migração e mudam o contrato de gravação, por isso ficam para a próxima versão.
3. **Feito na 0.2.1 (T192, D131): índice na migração 0006, de 2,216 s para 0,458 s com 300 mil vagas.** Fonte: contar com um índice que cubra `ocorrencia(fonte, vaga_id)` ou guardar a contagem por fonte numa tabela de resumo atualizada na gravação. Medir antes e depois com o mesmo script.
4. **Não feito (D131): medir de novo depois do item 1.** Salário: não precisa de índice novo. O custo some com o item 1; se ainda pesar depois dele, contar os chips com uma consulta só (uma passada pela tabela) em vez de nove.

**Como desfazer:** nada foi construído além do script e do teste do plano. Tirar `scripts/medir_filtros.py`, `tests/integracao/test_plano_consulta.py` e `tests/integracao/test_medir_filtros.py`; `sql_de_listar` é só a extração do SQL que `listar` já executava.

## D130. Rodada de segurança da 0.2.0 (T189, T190)

**Status:** resolvida em 2026-11-15: escolha da sessão, para confirmar com o dono

**Contexto:** antes do PR da 0.2.0 para a `main` rodaram a revisão do diff de segurança (cofre e reserva em arquivo, cliente do 2Captcha, CSRF, máscara da chave, teto diário, `http.py`, `app.js`), o `semgrep` e a varredura de padrões inseguros em `src/jobot`. O `semgrep` deu 7 achados de variável em `href`, todos falsos: os links de terceiros passam por `_http`/`http()`, que só aceita `http://` e `https://`. A varredura (6 categorias, 7 candidatos) não confirmou nenhum.

**Confirmado:** a chave não vai a log, HTML, URL nem banco; o CSRF é global; o `Host` só aceita `127.0.0.1` e `localhost`; `captcha_ligado` nasce desligado e o portão exige a chave; o teto diário conta antes de qualquer pedido.

**Corrigido agora:**

- T189: o arquivo de reserva do cofre é gravado de forma atômica (arquivo `.tmp`, `fsync`, `os.replace`), porque uma queda ou disco cheio no meio da gravação apagava a chave antiga.
- T190: contador negativo do teto diário vale como teto atingido (só acontece com banco adulterado).

**Fica como está (risco baixo):**

- Com o cofre do sistema trancado, a chave velha volta a valer depois do desbloqueio. Já está marcado como `shortcut:` no `cofre.py`; rever na fase 2.
- A corrida entre ligar e apagar em duas abas deixa `captcha_ligado` sem chave, mas `captcha_pronto` exige a chave e nada é resolvido.
- Com `seguir_saltos=False`, o gancho ainda consulta o DNS do `Location` de um 3xx antes de recusar; nenhum pedido sai.

**Para confirmar:** a varredura completa do plugin de segurança de terceiros não rodou, porque ela pede escolhas interativas e o dono estava fora. Rodar na volta, se o dono quiser.

**Como desfazer:** o dono manda trocar qualquer item. As duas correções são pequenas e têm teste próprio (T189 no cofre, T190 no teto diário); reverter uma delas devolve o comportamento anterior.

## D131. Lote 0.2.1: chips depois da lista, índice do chip de fonte e aviso "Salvo." (T191, T192, T193)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar

**Contexto:** a D129 mediu 300 mil vagas e propôs quatro itens para a versão seguinte. A 0.2.1 faz dois deles (itens 1 e 3), mais o ajuste do aviso "Salvo." que ficou pendente da 0.2.0. O item 2 e o item 4 ficam de fora, pelos motivos abaixo.

**Decisões:**

- **(a) Chips depois da lista (T191, item 1 da D129).** Os chips de `/vagas` carregam depois da lista, por HTMX: `GET /vagas/chips` com `hx-trigger="load"`. A lista não espera mais a contagem. A rota nova é `GET /vagas/chips` em `painel/rotas/chips.py`, com o template `vagas/chips.html`. Sem JavaScript os chips não aparecem (o painel já depende de HTMX para as outras trocas parciais). *Riscos aceitos:* a lista dá um pulo para baixo quando os chips chegam (o contêiner de espera tem uma linha); um pedido de chips que a pessoa abandonou ao trocar de aba ainda roda as contagens no servidor (mesmo custo total de antes, em dois pedidos); se o pedido dos chips falhar, o texto de espera some e o aviso de erro geral aparece. *Como desfazer:* voltar a chamar `contar_chips` na própria rota `/vagas` e tirar `chips.py` e `vagas/chips.html`.
- **(b) Índice do chip de fonte (T192, item 3 da D129).** Regra posta antes de medir: o índice só entra se o ganho for de pelo menos 20%. Com 300 mil vagas o chip de fonte foi de 2,216 s para 0,458 s (-79%), então entra a migração `0006_ocorrencia_fonte_vaga.sql`, com o índice `ocorrencia_fonte_vaga` em `ocorrencia(fonte, vaga_id)`. O índice `ocorrencia_vaga` já era redundante com o autoíndice do `UNIQUE (vaga_id, fonte, escopo)` (`0001_inicial.sql:120`); não foi tocado. Decidir sobre ele só depois de medir o custo na gravação. *Como desfazer:* uma migração nova com `DROP INDEX` (migração já aplicada nunca é editada).
- **(c) "Salvo." some sozinho (T193).** O aviso some em 5 s em todas as telas de Configurações (antes, o de Serviços sumia em 2 s e o das outras telas ficava). O parâmetro `salvo` sai do endereço depois de mostrar o aviso, então F5 não repete o aviso (isto muda o que a D93/A72 aceitava). *Como desfazer:* tirar `data-some-sozinho` do `configuracoes/pagina.html` e o código que limpa o `salvo` do endereço.
- **(d) Item 2 da D129 (cidade e empresa por prefixo): não feito.** Mudaria o que o filtro encontra (de "contém" para "começa com"), e isso é decisão de produto, do dono. Fica como está até ele escolher.
- **(e) Item 4 da D129 (contar os chips numa passada só): não feito.** Medir de novo depois do item 1 (a): com os chips fora do caminho da lista, o custo pode já não pesar.

**Para confirmar com o dono:** (c) o tempo de 5 s e o F5 sem aviso; (d) se quer a busca por prefixo em cidade e empresa; (e) se vale medir de novo.

**Rodada de segurança da 0.2.1 (T194).** Revisão do diff 842ce48..fe033be (`chips.py`, `chips.html`, `miolo.html`, `app.js` e a migração 0006): sem achado. O que se conferiu: as mesmas defesas de `/vagas` (Host, CSP, Vary, CSRF só em POST); `ler_estado` sem parâmetro novo e com bind no SQL; `Estado.url` com caminho fixo no código (sem open redirect); autoescape sem `|safe`; `app.js` sem `innerHTML` e com `replaceState` na mesma origem. O semgrep (`p/python`, `p/javascript`, `p/security-audit`) nos 5 arquivos deu 3 avisos `var-in-href` em `vagas/miolo.html`, linhas 10, 17 e 78. São falsos positivos, em linhas que já existiam na 0.2.0: as URLs saem de `Estado.url`, que sempre começa por `/vagas?`. Observação que não é falha nova: uma página de outro site pode disparar um GET para 127.0.0.1 e forçar a contagem dos chips (cerca de 0,46 s com 300 mil vagas), sem ler a resposta; isso já valia para `/vagas`. Fora de segurança: `_id_html` podia gerar id repetido (`a b` e `a_b`), e o foco podia voltar para o chip errado; feito na T195.

## D132. Desenho da fase 2: leitura com login no navegador da pessoa (Parte A)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar

**Entrega:** Parte A entregue na dev em 2026-11-15 (T196 a T220; registros na REG24, escolhas na D134). Parte B (leitores reais, botão Baixar o navegador) segue com o dono.

**Contexto:** o desenho está em `docs/superpowers/specs/2026-11-15-fase-2-design.md`. Passou por 4 rodadas de revisão, e a seção 12 lista todas as decisões, de D132.1 a D132.57.

**Decisões:** o pacote `navegador/` é o único que importa o Playwright, e os leitores de cada site ficam em `nucleo/leitores/`, puros. As execuções automáticas só navegam, esperam e rolam a página. A checagem de login vem antes da do CAPTCHA, e o 2Captcha só age em página de desafio que não é de login. A proteção por AST do pacote `navegador` usa uma lista permitida de chamadas ao Playwright. Os testes usam só sites falsos em `127.0.0.1`. Entram as migrações 0007 (tipo de execução `login`) e 0008 (coluna `com_login` na `fonte`).

**Para confirmar com o dono:**

1. (D132.6) Leituras com login nos horários 9h e 18h, com 15 minutos de tolerância; horário perdido é pulado, não recuperado ao ligar, e leitura com erro ou interrompida não repete na janela (foge da ADR 0006, que ganha nota).
2. (D132.15) Na navegação com login vale o user agent do próprio Chrome, não o fixo do joBot (muda a regra de coleta educada do `CLAUDE.md`).
3. (D132.19) Tetos por site em cada leitura: 10 páginas de lista e 20 de vaga, 30 no total, com 3 a 8 s entre navegações.
4. (D132.24) Na `fedora-dev`, sem Chrome, usa o Chromium do Playwright: na Parte A só o já instalado; o botão "Baixar o navegador" entra com o primeiro site.
5. (D132.25) "Buscar agora" também lê os sites com login se a última leitura começou há 4 horas ou mais (no máximo 6 por dia).
6. (D132.26) Com CAPTCHA que o 2Captcha não resolve, as janelas ficam abertas até 15 minutos no total e depois fecham (complementada pela T225, D135.3).
7. (D132.27) Se a Gupy logada não mostrar nada além da pública, o primeiro site da 0.3.0 passa a ser o LinkedIn. (respondida pelo dono em 2026-11-15: o LinkedIn vem primeiro, D136)
8. (D132.28) Passo opcional "Sites com login" no assistente de primeira execução, com o primeiro site.
9. (D132.29) A Gupy entra na lista da ADR 0005, com nota no lote do primeiro site.
10. (D132.30) Ordem das checagens: login primeiro, depois o desafio do Cloudflare (30 s), depois o CAPTCHA reconhecido (mesmo com 403 ou 429), por fim o bloqueio; o desafio que volta depois do token vira bloqueio.
11. (D132.31) O joBot escreve o token no campo do próprio CAPTCHA e chama o `data-callback` que ele declarou, só em página de desafio (nunca no login); reCAPTCHA v3 fica fora da fase 2.
12. (D132.32) Sem descrição na lista, abre a página de até 20 vagas por site (as mais novas, sem detalhe tentado nos últimos 30 dias por qualquer fonte).
13. (D132.44) O 2Captcha resolve só o Turnstile avulso; o desafio inteiro do Cloudflare ganha 30 s e depois fica para a pessoa (a ADR 0022 ganha um reparo).

**Como desfazer:** nada está construído; o dono manda trocar qualquer item e a sessão muda o desenho (a seção 12 diz onde cada um vale).

## D133. Escolhas do plano da Parte A da fase 2 (T196 a T220)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar

**Contexto:** o plano `docs/superpowers/plans/2026-11-15-fase-2-parte-a.md` quebra a Parte A do desenho da fase 2 (D132) nas tarefas T196 a T220 e REG24. O desenho deixou escolhas pequenas para o plano (seção 9); estas são as que a sessão tomou, cada uma presa por um teste nomeado no plano.

**Decisões:**

1. (E1) Playwright pela API assíncrona: o `serve` é asyncio e a leitura com login roda no mesmo laço.
2. (E2) Registro de leitores explícito em `nucleo/leitores/registro.py`, que começa vazio; o painel e os testes leem por `app.state`.
3. (E3) Os padrões de resposta de cada leitor são expressões regulares sobre host e caminho; os prefixos de login casam pelo começo.
4. (E4) O estado do escopo devolve junto as vagas que podem ser gravadas.
5. (E5) Nomes: `manter_batimento`, `candidatas_a_detalhe` e `inicio_da_ultima_leitura_login`.
6. (E6) O agendador ganha a leitura com login por um parâmetro opcional, e o estado do banco ganha `login()` na mesma tarefa, para a agenda não parar.
7. (E7) Horários inválidos gravados no banco valem o padrão (9h e 18h), com aviso no log; no painel, os horários são um campo de texto.
8. (E8) O Chrome é achado pelo caminho de instalação; o Chromium do Playwright, pelo próprio Playwright, calculado uma vez ao subir o `serve` e só com leitor registrado.
9. (E9) O desafio do Cloudflare é reconhecido pelo título "Just a moment" ou pelo script do desafio; rever com página real na Parte B.
10. (E10) "O mesmo desafio voltou" quer dizer mesmo tipo e mesma chave do widget, no mesmo site e na mesma leitura.
11. (E11) A página assenta com o evento `load` e uma espera de até 10 s pela rede parada.
12. (E12) Fechar o navegador é ação normal: a leitura fica interrompida com `fechado`, sem erro no log.
13. (E13) O nome da chave do 2Captcha no cofre passa do painel para `banco/captcha.py`.
14. (E14) A leitura do `Retry-After` do cliente HTTP vira pública, e o navegador usa o mesmo teto de 10 minutos.
15. (E15) Testes de navegador em `tests/navegador/`, com o site e o leitor falsos em `tests/apoio/site_falso.py`.
16. (E16) A página de entrada conta como uma das 10 páginas de lista, para o total por site ficar em 30.
17. (E17) Só o pacote `navegador` abre o Playwright; o `cli`, o painel e o script de captura usam a entrada de produção dele.
18. A lista permitida do Playwright confere os nomes de `Page`, `Frame`, `Locator`, `BrowserContext`, `Browser`, `Request` e `Response`. `APIRequestContext` fica fora, porque chegar a ele exige `.request`, que sempre reprova. Só `name` é tolerado como homônimo; o pacote usa `asyncio.timeout` e `json.loads` para não esbarrar em `wait_for` e `json`.
19. O script de captura com login segura a trava do joBot com porta 0. Trava presa sem porta quer dizer captura em andamento: `jobot`, `jobot sair` e `jobot atualizar` avisam e saem, sem encerrar a captura nem subir servidor.
20. Exceção à D132.13: a wiki muda na Parte A só em `Arquitetura.md` e `Architecture.md`, porque o teste do diagrama de camadas exige o nó `navegador` e uma seta para cada import novo entre pacotes. As outras páginas da wiki não mudam.
21. Na execução: as escolhas feitas durante a execução estão na D134. O item 1 do "Para confirmar com o dono" abaixo seguiu a opção (a), e o item 3 também seguiu a opção (a) (leitor falso em `tests/apoio/site_falso.py`).

**Para confirmar com o dono:**

1. Página logada com campo de senha escondido (D132.37). O desenho trata como login toda página com campo de senha; um site logado com formulário de login escondido ficaria sempre em "precisa login". Opções: (a) qualquer campo de senha, como no desenho; (b) só campo visível; (c) a opção (a) mais o leitor poder dizer "não é login", o que muda o contrato do leitor. Recomendação: (a) na Parte A, que nunca põe nada numa página de login, e rever com a captura real do primeiro site.
2. Cidades na busca dos sites com login (D132.35). Opções: (a) termos e países, como no desenho; (b) levar as cidades da busca ao contexto da coleta, o que muda o contrato de todos os coletores. Recomendação: (a), e decidir (b) na Parte B, site por site.
3. Onde mora o leitor do site falso. Opções: (a) em `tests/apoio/`, fora do pacote publicado; (b) um leitor de exemplo em `src/jobot/nucleo/leitores/`, que apareceria no registro. Recomendação: (a), que mantém a Parte A sem nada visível (D132.23); o plano segue (a).

**Como desfazer:** nada está construído; cada escolha mora numa tarefa do plano e num lugar só do código (os números em `navegador/limites.py` e `agenda/login.py`). O dono manda trocar e a tarefa dona muda o teste e o valor.

## D134. Escolhas da sessão na execução da Parte A da fase 2 (T196 a T221)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar

**Contexto:** a Parte A (desenho na D132, plano e escolhas do plano na D133) foi feita nas ondas 1 a 9 do plano e entrou na `dev`. Durante a execução saíram escolhas pequenas que o plano não fixava. Estão aqui, em ordem de tarefa, seguidas da rodada de segurança (T221).

**Decisões:**

1. (T202) A semeadura das fontes, dos leitores e das empresas é uma transação só: falha no meio desfaz tudo.
2. (T204) `horarios_validos` confere as regras nesta ordem: formato, muitos (mais de 4, antes de olhar os itens), repetido, perto. Só dígitos ASCII contam.
3. (T205) Os quatro motivos novos (`precisa_login`, `captcha`, `sem_tela`, `sem_navegador`) ficam fora do link "reportar problema" (`FORA_DO_LINK`), e o vigia não abre issue por eles (`SO_RESUMO`): são do lado de quem usa, não defeito do coletor, e o vigia só roda fontes públicas.
4. (T206) `login_horarios` torto no banco vale o padrão e avisa no log uma vez por valor, não a cada volta de 60 s.
5. (T207) Se a escrita do token lançar erro, `ENTREGAR_TOKEN` devolve false e não chama a função de retorno do site.
6. (T207) `nome_retorno` fora do padrão de identificador devolve False sem chamar `evaluate`.
7. (T207) Função nativa como retorno é recusada, o que também recusa `.bind()`.
8. (T207) `navegador/js.py` não tem prazo próprio: quem chama envolve a chamada em `asyncio.timeout`.
9. (T207) Nenhum teste do node prova que o token é escrito no campo de resposta; ficou como nota para o teste da T216 conferir.
10. (T208) Fica aberta a janela TOCTOU em `Default/` (troca por symlink entre a checagem e a gravação); para usá-la, alguém precisa escrever na pasta de dados 0700 da própria pessoa.
11. (T208) Os nomes das três chaves do Chromium seguem sem conferência no Chrome real.
12. (T209) URL com `usuário:senha@` é aceita quando o hostname real está nos hosts do leitor (`https://mal.io@site.com/` passa; `https://site.com@mal.io/` não).
13. (T209) Barra invertida, caractere de controle e porta inválida recusam a URL.
14. (T210) Sem `DISPLAY` nem `WAYLAND_DISPLAY` válido, `ambiente_da_tela` devolve vazio mesmo com `XAUTHORITY` ou `XDG_RUNTIME_DIR` válidos: não há tela sem um dos dois.
15. (T210) Linhas do `systemctl show-environment` com valor entre `$'...'` são ignoradas.
16. (T211) Se o Chrome falha, o joBot cai no Chromium com log de nível debug sem `exc_info`, e o motivo da falha se perde; ligar o `exc_info` se o uso real mostrar falha frequente.
17. (T211) A mensagem de erro do Playwright pode levar o caminho do perfil ao log local (que é 0600).
18. (T211) O Chrome é procurado só em `/opt/google/chrome/chrome`; Chrome de Flatpak ou Snap cai no Chromium do Playwright.
19. (T211) `navegador_instalado` não trata falha do driver: ela vira exceção para quem chama.
20. (T212) Depois de rolar, "estável" só vale depois de pelo menos um pedido novo; página que não pede nada ao rolar espera os 5 passos (5 s em produção por navegação com rolar).
21. (T212) `ESPERA_ASSENTAR_MS`, `_PASSOS_DEPOIS_DE_ROLAR` e a espera de 30 s do 429 sem `Retry-After` (`ESPERAS_LIMITE[0]`) ficam em `navegador/pagina.py`; levá-los para `navegador/limites.py` é tarefa nova (feita na T228, D135.7).
22. (T212) Os ouvintes da página não são desligados (comentário `shortcut:` no código).
23. (T213) Entrada recusada pela política grava `falhou` com motivo `saude.listagem_incompleta` e escopo vazio; o site não é lido.
24. (T213) Depois de um erro do Playwright, a execução espera até 1 s (`limites.ESPERA_FECHAR_S`, valor técnico) pelo `close` do contexto antes de decidir se a pessoa fechou o navegador.
25. (T213) `fechar_escopos_extintos` roda mesmo quando o site para no meio de um escopo; só não roda com parada na entrada ou com `escopos()` quebrado, como o plano diz.
26. (T214) Detalhe que quebra não tem recuo: pediria mudança de esquema (D54, opção c).
27. (T214) Parada no detalhe não grava linha de saúde. (trocada pela T224, D135.2)
28. (T214) Vaga em dois escopos grava a descrição numa ocorrência só.
29. (T215) `navegador_instalado()` é lido ao subir o `serve`: instalar o Chrome com o `serve` no ar só aparece depois de reiniciar (atualizar quando o botão "Baixar o navegador" da Parte B existir).
30. (T215) O "Buscar agora" só sobe o navegador com fonte ligada e leitor registrado.
31. (T215) A mensagem do `serve` quando há uma captura no ar é tarefa nova. (feita na T227, D135.6)
32. (T216) Widget numa página que passa em `leitor.pagina_logada` e veio com 200 é formulário da página, não desafio: não vai ao 2Captcha nem tem a função de retorno chamada, o que evita enviar formulário (A8, D132.11). Desafio que mantém o cabeçalho logado com 200 fica sem resolver: o leitor lê a página como está.
33. (T216) `Ouvidas.ultimas` não separa documento de XHR (`shortcut:` no código; separar por `resource_type` se um site real fizer fetch à mesma URL).
34. (T216) reCAPTCHA v3 do site inteiro em página não logada vira desafio sem resolver (`captcha`), como antes.
35. (T216) 403 e 429 viram 200 quando o desafio sai sem documento novo; token sem saída é `captcha`; 429 depois do token repete o `goto` sem novo pedido ao 2Captcha.
36. (T216) `PRAZO_COFRE_S` aparece em `navegador/limites.py` e em `painel/rotas/servicos.py`; um lugar só e o cache do cofre na Cola são tarefa nova. (trocada pela T226, D135.4 e D135.5)
37. (T217) O aviso no computador sai só em português na Parte A; o idioma entra por `Dependencias` na Parte B. (trocada pela T229, D135.8)
38. (T217) O tempo de olhar a janela vai para `limites.OLHAR_S = 5` (era `_OLHAR_S` em `navegador/execucao.py`), ao lado do `INTERVALO_LOGIN_MANUAL_S` da T219; são dois nomes porque medem coisas diferentes. (`INTERVALO_LOGIN_MANUAL_S` saiu na T232, D136.3)
39. (T218) O cartão mostra "rodando" com o site ligado no meio da leitura; `_estado` e `_motivo` de `fontes.py` viraram `estado_dos_escopos` e `motivo_mais_grave`, públicos.
40. (T219) `_criar` de `painel/rotas/execucao.py` virou `criar_tarefa`, público, para o login manual reaproveitar; entra `limites.INTERVALO_LOGIN_MANUAL_S`. (`INTERVALO_LOGIN_MANUAL_S` saiu na T232, D136.3)
41. (T220) Segredo opaco sai pelo nome do campo (lista ampliada).
42. (T220) JSON dentro de `<script>` no HTML não é limpo pela posição (`shortcut:`; a primeira captura é lida por gente).
43. (T220) Valor trocado com menos de 3 caracteres não é procurado; caso existente é sobrescrito; o meta guarda `tipo`.

**Rodada de segurança da Parte A (T221):**

44. O semgrep (`p/security-audit`, `p/python`, `p/trailofbits`) em `src`, `scripts` e `.github` deu 17 alertas, todos já conhecidos (A60, D131); nada novo da Parte A.
45. A revisão do diff `origin/main...dev` conferiu CSRF, Host, política de hosts, `js.py`, chave do 2Captcha, perfil, aviso, migrações e templates sem achado, e achou 2 problemas de gravidade baixa, corrigidos na T221.
46. (T221) Página final que a política recusa (http no próprio host depois de redirecionar, da função de retorno do widget ou de uma troca sozinha ao rolar) vira `bloqueio`, ou `precisa_login` quando casa com o prefixo de login, como o salto para fora dos hosts. A conferência é refeita antes da cola do 2Captcha e antes da captura, com a URL lida depois do HTML.
47. (T221) reCAPTCHA ou Turnstile preso a `button` ou `input` não é desafio, para não chamar a função de retorno que envia o formulário.
48. Ficam para a Parte B, com fixture real: `div` invisível ou dentro de `<form>` tratada como desafio; downloads e service workers no contexto persistente (os padrões do Playwright não foram conferidos); o ambiente inteiro do `serve` passado ao Chrome. (downloads e service workers: T230, D135.9; ambiente do `serve`: T231, D135.10)

**Para confirmar com o dono:**

1. (decisão 37) O aviso no computador só em português até a Parte B. (trocada pela T229, D135.8)
2. (decisão 32) Widget em página logada que veio com 200 não é tratado como desafio: o joBot não resolve nem chama a função de retorno, e um desafio que mantém o cabeçalho logado fica sem resolver.
3. (decisão 18) O Chrome só é achado em `/opt/google/chrome/chrome`; quem tem o Chrome por Flatpak ou Snap usa o Chromium do Playwright.
4. (decisão 17) O caminho do perfil pode aparecer no log local (0600) pela mensagem de erro do Playwright.
5. (decisão 10) A janela TOCTOU em `Default/` fica aberta, porque só alguém que já escreve na pasta de dados da pessoa a usaria.
6. A Parte A fica na `dev`, sem PR para a `main`: quem instala clona a `main`, e o PR levaria as migrações 0007 e 0008 e o Playwright a quem usa antes da 0.3.0 (D132.23).

**Tarefas novas para o plano da Parte B:**

- Provar o `close` do contexto no `test_janela_parada` pelo evento `close`, não por `pages == []`.
- Falso positivo do `achar_widget`, que devolve `None` também por timeout no `get_attribute`.
- Desafio no detalhe parado na janela sem gravar `saude.captcha`.
- A pessoa fecha só a aba parada e a execução espera o prazo inteiro.
- `PRAZO_COFRE_S` num lugar só e cache do cofre na Cola.
- Mensagem do `serve` quando há uma captura no ar.
- Mover `ESPERA_ASSENTAR_MS`, `_PASSOS_DEPOIS_DE_ROLAR` e `ESPERAS_LIMITE[0]` de `navegador/pagina.py` para `navegador/limites.py`.
- Aviso no computador no idioma da pessoa.
- Com fixture real: `div` invisível ou dentro de `<form>` tratada como desafio.
- Downloads e service workers no contexto persistente (conferir os padrões do Playwright).
- O ambiente inteiro do `serve` passado ao Chrome.

**Como desfazer:** o dono manda trocar qualquer item, e a troca vira tarefa nova, com teste, no plano da Parte B. Os pontos marcados com `shortcut:` estão no código com o limite escrito.

## D135. Escolhas do plano das sobras da Parte A (T222 a T231)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar

**Contexto:** a D134 deixou dez tarefas novas da execução da Parte A, e o plano `docs/superpowers/plans/2026-11-15-fase-2-sobras-a.md` as transforma em T222 a T231. O item com fixture real (`div` invisível ou dentro de `<form>` tratada como desafio) fica para a Parte B. O plano fixa as escolhas abaixo. Cada tarefa que troca um item da D134 marca esse item na mesma entrega.

**Decisões:**

1. (T223) Quando o `get_attribute` do widget estoura o prazo, o `achar_widget` devolve um desafio `nao_aceito`. A página para como `captcha` e nunca passa como página limpa. A exceção é a página logada que veio com 200: ali o widget continua sendo tratado como formulário (D134.32). Página que troca no meio continua sem widget. Na espera do token e na olhada da janela, o `nao_aceito` conta como "saiu do desafio", do mesmo jeito que o `None` contava antes. Por isso um estouro passageiro na olhada faz o site ler a mesma página de novo uma vez; se o desafio continua, ela volta à janela no mesmo prazo. É aceito: custa uma leitura a mais, não o prazo.
2. (T224) Parada no detalhe grava a linha de saúde do site, com escopo vazio, pelo mesmo `estado_do_escopo` da parada na entrada. Um desafio só na página da vaga deixa a fonte `parcial`, com motivo `saude.captcha`. Troca a D134.27.
3. (T225) Quando a pessoa fecha a aba parada, a espera daquela aba acaba, mesmo que ela feche logo ao ver o aviso (o joBot passa a ouvir o fechamento antes de avisar). O site grava `captcha` logo, as outras abas paradas seguem no mesmo prazo e a execução termina `concluida`. Para o resto da execução, fechar a aba não vale como fechar o navegador. Quando o navegador inteiro fecha, o fechamento da aba pode chegar antes do dele; por isso, antes de decidir que foi só a aba, a espera aguarda até `limites.ESPERA_FECHAR_S` (o mesmo 1 s da D134.24) pelo fechamento do navegador, e se ele vier a execução para como `fechado`. A alternativa seria marcar a execução inteira como interrompida (`fechado`).
4. (T226) `PRAZO_COFRE_S` fica só em `navegador/limites.py`. A aba "Serviços" lê `limites.PRAZO_COFRE_S`. O painel já importava `jobot.navegador.limites`, então não há import novo entre pacotes.
5. (T226) A chave do 2Captcha é lida do cofre uma vez por execução e serve a todas as abas. Um cofre que não responde custa um prazo por execução, não um por site. A chave fica na memória do processo até a execução acabar. Antes ela também ficava, mas só durante cada resolução.
6. (T227) O `serve` que acha uma captura de exemplos no ar mostra a mensagem que o `abrir` e o `atualizar` já usam para esse caso. Ela sai só em português, como as outras mensagens do terminal.
7. (T228) `ESPERA_ASSENTAR_MS`, `PASSOS_DEPOIS_DE_ROLAR` e `ESPERA_429_S` passam a morar em `navegador/limites.py`. O `ESPERA_429_S` é o primeiro valor de `ESPERAS_LIMITE` de `nucleo/http.py`, para o número continuar num lugar só.
8. (T229) O aviso no computador sai no idioma salvo na configuração (`idioma`), lido no começo de cada execução. Sem idioma salvo, ou com um valor que não é `pt` nem `en`, sai em português. As duas frases ficam em `navegador/execucao.py`, porque o navegador não importa o painel. O idioma não entra por `Dependencias`, como a D134.37 previa, para não mexer nas montagens de teste.
9. (T230) O contexto do navegador abre com downloads recusados e com o registro de service workers bloqueado. A resposta continua chegando pelo evento `response`, e toda a bateria de navegação roda com essas duas opções.
10. (T231) O Chrome recebe do ambiente do `serve` só `PATH`, `HOME`, `USER`, `LOGNAME`, `LANG`, `LC_ALL`, `LANGUAGE`, `TMPDIR`, `XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, `XDG_DATA_HOME`, `XDG_DATA_DIRS`, `XDG_CURRENT_DESKTOP`, `XDG_SESSION_TYPE` e `DBUS_SESSION_BUS_ADDRESS`. Recebe também o ambiente da tela já validado (`DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY`, `XDG_RUNTIME_DIR`). O resto não passa, nem token nem chave de API. As `XDG_*`, `TMPDIR`, `USER` e `LOGNAME` entram porque o Chrome costuma lê-las e nenhuma carrega segredo. Risco: os testes usam lançador falso, então nenhum deles prova que o Chrome ou o Chromium abre com esse ambiente. Se faltar alguma variável, o navegador não abre (`SemNavegador`) e a leitura com login para para todo mundo. A T231 traz uma verificação manual com tela, com o Chromium e, se houver, com o Chrome; o resultado vai no resumo da tarefa.
11. (T222) O fechamento do contexto no `test_janela_parada` passa a ser provado pelo evento `close`. A linha `pages == []` que sobrava no teste de cancelar sai.
12. (T239, tarefa nova, fora deste lote) Ressalva da T225: se a aba já estava fechada quando o `parar()` começa (a pessoa fecha durante o desafio gerenciado do Cloudflare, que leva até 30 s, antes de o joBot ouvir o `close`), a espera vai até o fim do prazo, porque o evento `close` já passou. Conferir `pagina.is_closed()` antes de esperar resolveria, mas `is_closed` não está em `PERMITIDOS` de `tests/unidade/test_navegador_ast.py`. Além disso, várias abas fechadas na mesma olhada esperam `ESPERA_FECHAR_S` uma depois da outra (só atraso; nada se perde). Os números T232 a T238 ficam reservados ao plano do login. A T239 foi feita com a opção (a), escolhida pela sessão e ainda para confirmar com o dono (item 6): `is_closed` entrou em `PERMITIDOS` (só leitura), o `parar()` o confere logo depois de registrar o `close`, e a olhada espera o contexto uma vez só para todas as abas fechadas. A lista das abas fechadas é guardada antes dessa espera: a aba que fecha durante a olhada fica para a próxima. O fim do prazo também confere o contexto antes de gravar a parada `captcha`.

**Para confirmar com o dono:**

1. (T231) Variáveis de proxy (`http_proxy`, `https_proxy`, `no_proxy`, `all_proxy` e as maiúsculas). Sem elas, quem usa proxy só pelo ambiente perde o proxy no Chrome. Opções: (a) passá-las junto com a lista; (b) deixá-las de fora. Recomendação: (a), porque o navegador precisa delas para sair pela rede da pessoa. A T231 sai sem elas até a resposta.
2. (decisão 3) Fechar a aba parada encerra só a espera daquele site.
3. (decisão 5) A chave do 2Captcha fica na memória durante a execução inteira, e não só durante cada resolução.
4. (decisão 9) Downloads e service workers desligados também no login manual e na captura de exemplos (`login_manual.py` e `scripts/capturar_logado.py` abrem pelo mesmo `abrir_contexto`). (o login manual passou à janela comum, com o padrão do navegador; T232, D136.1)
5. (decisão 10) O `env` do Chrome é só a lista, sem conferência automática no Chrome real; a única prova é a verificação manual da T231 (verificação manual feita em 2026-11-15: o Chrome e o Chromium do Playwright abriram com o ambiente restrito e mostraram a página).
6. (decisão 12) Opções da T239: (a) pôr `is_closed` em `PERMITIDOS` (só leitura) e conferir antes de esperar, com teste de aba fechada antes do `parar`, e esperar as várias abas em paralelo; (b) guardar o fechamento num sinal registrado assim que a aba abre, sem chamada nova do Playwright; (c) deixar como está, porque o custo é só esperar o prazo. Recomendação: (a).
7. (fechamento) O `registros/padroes.md` chegou ao teto (64 linhas de até 650 caracteres). Para caber as lições das sobras, quatro pares de lições velhas viraram uma linha cada e perderam regras secundárias (a versão inteira fica no histórico do git, antes desta junção); a lição "Índice de grupo" saiu; as armadilhas do fim de fase foram para o passo a passo do ADR 0021. Opções: (a) seguir juntando e cortando as velhas, como está; (b) separar as lições de tela (CSS, HTMX, acessibilidade, Playwright do painel) num `registros/padroes-tela.md`, lido só em tarefa de tela, e devolver as regras cortadas; (c) subir o teto. Recomendação: (b).

**Como desfazer:** o dono manda trocar qualquer item, e a troca vira tarefa nova com teste. Os nomes e os valores ficam em `navegador/limites.py`, em `navegador/abrir.py` e em `navegador/execucao.py`.

## D136. Login pela janela comum e leitor do LinkedIn (T232 a T238)

**Status:** login pela janela comum decidido pelo dono em 2026-11-15; as escolhas do plano são da sessão, para confirmar; os dois itens R4 (D136.R4-cidades e D136.R4-lista) saem com a opção (a), escolhida pela sessão com o dono fora, para confirmar

**Contexto:** a primeira sessão de mapeamento (Parte B, D132) começou pelo LinkedIn e esbarrou no login com Google, que recusa entrar na janela controlada pelo Playwright. O plano `docs/superpowers/plans/2026-11-15-fase-2-login-linkedin.md` transforma o que se provou em T232 a T238: a janela comum para o login (T232, que absorve a T233), a captura com recorte (T234), o leitor do LinkedIn (T235), a documentação (T236) e as duas tarefas que mudam o contrato do leitor (T237 e T238, com as escolhas da sessão da D136.R4-cidades e da D136.R4-lista). A base é a `dev` depois do lote das sobras (T222 a T231, D135).

**Fatos provados na sessão de mapeamento (2026-11-15):**

- O Google recusa o login dentro da janela do Playwright. O mesmo binário do Chromium do Playwright, com o mesmo perfil do joBot e sem automação, entra: `<navegador> --user-data-dir=<dados>/navegador --password-store=basic --no-first-run <url_login>`.
- Com `--password-store=basic`, os cookies ficam gravados como v10 e a janela automática os lê. Sem a opção, saem como v11 (chaveiro do sistema) e a janela automática não os lê. Depois do login pela janela comum, a janela automática no mesmo perfil já abre com a sessão.
- O Playwright 1.65.1 já passa `--password-store=basic`, `--no-first-run` e `--use-mock-keychain` em toda janela que abre (lista `chromiumSwitches` do pacote do Playwright).
- O perfil fica em `<dados>/navegador`. Duas janelas não usam o mesmo perfil ao mesmo tempo: o Chrome guarda o `SingletonLock` na pasta. A trava de instância do joBot é o `jobot.lock`.
- Busca do LinkedIn: `/jobs/search/?keywords=X&location=Y` redireciona para `/jobs/search-results/?keywords=X&currentJobId=...`. Essa busca ignora `location` e `f_WT` e usa a cidade do perfil. Cidade ou "remoto" escritos no texto da busca funcionam ("enfermeiro em Belo Horizonte", "desenvolvedor python remoto"). A página seguinte é `&start=25` (25 cartões por página). `f_TPR=r604800` (última semana) funciona. A conta usada está em inglês; o leitor precisa aceitar pt e en.
- Cartões: a marca estável é `componentkey="job-card-component-ref-<id>"`, que aparece duas vezes por cartão; as classes CSS são embaralhadas. A ordem do texto é título (às vezes repetido, às vezes com " (Verified job)"), empresa, local com "(On-site|Remote|Hybrid)" opcional; depois o botão `aria-label="Dismiss <título> job"`; depois, opcionais, salário, uma frase pessoal ("2 school alumni work here", que não pode ser guardada), "Posted N … ago" e "Easy Apply".
- Detalhe: `/jobs/view/<id>/` montado tem uns 155 KB; o `<title>` é "Título | Empresa | LinkedIn". O bloco do topo traz empresa, título, local, "4 months ago", número de candidatos, salário, "Remote" e "Full-time". O texto inteiro de "About the job" está no DOM montado. O HTML que o servidor manda não traz a descrição (ela chega por um POST de RSC), então o leitor lê o `page.content()`.
- Candidatura externa: `aria-label="Apply on company website"`, com `href=https://www.linkedin.com/safety/go/?url=<codificada>&urlhash=..&mt=<token>`. Só o `url` interessa; `mt` e `urlhash` saem. Vaga com "Easy Apply" não tem esse link.
- O HTML que o servidor manda em `/jobs/` logado tem o link da navegação global `a[data-view-name="navigation-notifications"]` (href para `/notifications/`) e nenhum cartão: `job-card-component-ref` só aparece em `/jobs/search-results/`. O visitante sem sessão não tem o link. (superado em parte pela captura de 2026-11-15: ver "O que a captura real mostrou" abaixo)
- Ruído: telemetria, mensagens, perfil, feed e e-mail chegam pela rede na mesma página. Nada disso entra em fixture nem no banco. A página montada tem nomes de pessoas, frases de ex-alunos e o menu com o nome do dono.
- O `scripts/capturar_logado.py` recusa arquivo acima de 50 KB (`scripts/capturar.py:55`), e as páginas montadas têm de 150 a 250 KB.

**Respostas do dono na rodada de 2026-11-15:**

- Pergunta 1: o mapeamento usa a ferramenta do próprio joBot (`scripts/capturar_logado.py`).
- Pergunta 2: um site por sessão.
- Pergunta 3: roteiro fixo por site.
- Pergunta 4: o LinkedIn vem primeiro (responde a D132.27).
- Pergunta 5: conta que falta, o dono cria. O joBot e a sessão nunca criam conta nem digitam senha.
- Pergunta 6: trocada pela pergunta 8.
- Pergunta 7: sites só de tecnologia ficam por último.
- Pergunta 8: o login acontece numa janela comum, sem automação. A pessoa entra no site e fecha a janela; o joBot confere a sessão sozinho. Texto do dono: "Entre no site e feche a janela quando terminar". Vale para Google e para e-mail e senha.
- O mapeamento serve a todas as profissões. Entrar com Google é necessário, e quem não tem Google também precisa conseguir entrar.

**Pedido recusado:** o dono perguntou se dava para esconder a automação da janela. A sessão recusou: o desenho da fase 2, seção 2 (`docs/superpowers/specs/2026-11-15-fase-2-design.md:45`), e a D132.15 proíbem disfarçar automação (a ADR 0005 trata de senha e CAPTCHA). A janela comum não é disfarce: nela não há automação nenhuma, o joBot só abre o navegador no endereço de login, e quem digita é a pessoa. A janela automática segue como é, com a marca de automação do navegador.

**Decisões (da sessão, para confirmar, menos a 1, que é do dono):**

1. (T232) O "Fazer login agora" abre a janela comum: o processo do navegador, sem Playwright, com `--user-data-dir=<dados>/navegador --password-store=basic --no-first-run --no-default-browser-check <url_login>` e nenhum outro argumento. Nada é injetado na página. Vale para todo jeito de entrar (Google, e-mail e senha, outro provedor). Troca a forma da D132.52; o que a pessoa faz continua igual: ela digita.
2. (T232) A janela comum usa o mesmo navegador da janela automática, na mesma ordem do `abrir_contexto`: o Chrome em `/opt/google/chrome/chrome` se existe, senão o Chromium do Playwright (`executable_path`). Assim o perfil não passa de uma versão de navegador para outra. A procura mora em `abrir.caminho_do_navegador()`, e o `navegador_instalado()` passa a usá-la. Limite conhecido, registrado no código como `shortcut:`: `caminho_do_navegador` escolhe o Chrome só porque o arquivo existe; se o canal `chrome` do Playwright falhar, o `abrir_contexto` cai no Chromium com o mesmo perfil, e os cookies v10 com `--password-store=basic` foram conferidos só no Chromium; mudar se aparecer sessão perdida nessa troca.
3. (T232) A espera acaba quando o processo da janela sai (a pessoa fechou a janela). O prazo continua `limites.PRAZO_LOGIN_MANUAL_S = 600`. Estourado o prazo, o joBot pede para a janela fechar (SIGTERM), espera até `limites.ESPERA_SAIR_JANELA_S = 10` e só então mata o processo (SIGKILL). O joBot não lê a página durante a espera, então `limites.INTERVALO_LOGIN_MANUAL_S` sai (troca a D134.40 nessa parte).
4. (T232) A sessão se confere depois que a janela sai: a janela automática abre no mesmo perfil, vai ao `url_entrada` do leitor, espera a página assentar (`networkidle`, até `limites.ESPERA_ASSENTAR_MS`; estourar o prazo não é erro), pergunta `leitor.pagina_logada(html, url)` e fecha. A pessoa vê essa janela abrir e fechar sozinha em poucos segundos.
5. (T232) Antes de abrir, `perfil_em_uso(perfil)` lê o `SingletonLock` da pasta do perfil (link simbólico "máquina-pid"). Sem o link, ou com a mesma máquina e o pid morto, o perfil está livre. Com o pid vivo, ou com outra máquina no nome (com log do motivo), o resultado é "em_uso" e nada abre. Alvo torto (sem `-`, ou com um pid que não é número) também conta como em uso, com log do motivo. Se o `os.readlink` der um `OSError` diferente de `FileNotFoundError` (por exemplo `EINVAL`, quando `SingletonLock` não é um link), também é "em_uso", com log. Motivo: com o perfil aberto, o navegador repassa o endereço para o processo que já está aberto e sai na hora, e o joBot conferiria a sessão cedo demais.
6. (T232) Resultados do login manual: "pronto", "nao_entrou", "tempo_esgotado", "sem_tela", "sem_navegador" e "em_uso" (mais o "erro" da rota). "fechado" sai, com a chave de i18n `configuracoes.sites_com_login.login.fechado` nos dois idiomas. Prazo estourado com a conferência logada dá "pronto"; prazo estourado sem login dá "tempo_esgotado". Textos novos:
   - aguardando: "Entre no site e feche a janela quando terminar. Depois o joBot confere o login sozinho (a janela fecha em {minutos} minutos se ficar aberta)." / "Sign in to the site and close the window when you are done. joBot then checks the sign-in by itself (the window closes after {minutos} minutes if left open)."
   - pronto: "Login feito. O joBot já pode ler este site." / "Signed in. joBot can now read this site."
   - nao_entrou: "Não deu para confirmar o login. Tente de novo e entre no site antes de fechar a janela." / "Could not confirm the sign-in. Try again and sign in before closing the window."
   - tempo_esgotado: "A janela ficou aberta por {minutos} minutos sem login e foi fechada. Tente de novo." / "The window stayed open for {minutos} minutes without a sign-in and was closed. Try again."
   - em_uso: "O navegador do joBot já está aberto. Feche-o e tente de novo." / "joBot's browser is already open. Close it and try again."
   Os textos não citam Google: valem para todo jeito de entrar.
7. (T232) Onde mora: módulo novo `navegador/janela_comum.py`, com `argumentos_da_janela(executavel, perfil, url)`, `perfil_em_uso(perfil)`, o protocolo `Janela` (`wait`, `terminate`, `kill`), `AbrirJanela`, `JanelaComum(caminho, abrir)` e `janela_de_producao()`. `fazer_login(leitor, deps, janela)` recebe a `JanelaComum` como parâmetro, e não por `Dependencias`, para não mexer nas seis montagens de teste. O `relogio` sai da assinatura. `abrir.ambiente_do_navegador(ambiente)` sai de dentro do `lancador_de_producao` da T231, e as duas janelas usam o mesmo ambiente. A janela comum abre com entrada e saídas em `DEVNULL`. O trecho "abrir a janela e esperar" mora em `login_manual.abrir_e_esperar(janela, dados, ambiente, url)`, que devolve `"fechou"`, `"prazo"`, `"sem_tela"`, `"sem_navegador"` ou `"em_uso"` e é usado pelo `fazer_login` e pelo `scripts/capturar_logado.py` (decisão 10).
8. (T232) Cancelar a tarefa (o `serve` fechando) fecha a janela comum pelo mesmo caminho do prazo: SIGTERM, espera, SIGKILL.
9. (T232, era a T233) A janela automática não muda: o Playwright já passa `--password-store=basic`. Um teste de guarda lê o pacote do Playwright e falha se uma troca de versão tirar a opção. A T233 some dentro da T232.
10. (T234) `scripts/capturar_logado.py --login URL` abre a janela comum nesse endereço antes da janela automática da captura, com a mensagem "Entre no site e feche a janela quando terminar." O endereço vem explícito (o mapeamento acontece antes de existir leitor) e precisa ser `http` ou `https`. O script chama `abrir_e_esperar` (decisão 7) dentro do `async with dependencias(...)`, antes de navegar.
11. (T234) A captura ganha `--recorte SELETOR` (CSS, repetível): guarda o `<title>` e os nós de fora que casam, antes do `reduzir`. Com recorte, a captura grava só o HTML final da página, com ou sem leitor, e nenhuma resposta JSON (telemetria, mensagens e perfil chegam por JSON no mesmo host). No recorte, todo `href` e `src` que aponta para o host capturado tem o valor de cada parâmetro da query trocado por `<limpo>`, menos o parâmetro `url` (o do `/safety/go/`), porque `mt` (token por usuário), `urlhash`, `trackingId`, `refId`, `trk` e `eBP` não casam o `_SEGREDO` do `capturar`; na captura manual, a pessoa confere a olho o valor do `url=`. Ganha `--tirar REGEX` (repetível): troca por `<limpo>` o texto que casa, e também o valor de atributo que casa, e a conferência final recusa o arquivo se ainda sobrar algo que casa. Recorte só recusa a captura (código 2) quando nenhum seletor casou nada; um seletor sem nó, com outro que casou, não recusa. A `.meta.json` guarda os seletores e as expressões usados; por isso o `--tirar` só leva padrões genéricos, nunca o nome de alguém. O limite de 50 KB continua.
12. (T235) O leitor mora em `nucleo/leitores/linkedin.py` (o pedido dizia `nucleo/coletores`; os leitores com login moram em `nucleo/leitores`). Chave `linkedin_logado`, nome "LinkedIn", hosts `("www.linkedin.com",)`, `url_login` `https://www.linkedin.com/login`, `url_entrada` `https://www.linkedin.com/jobs/`, `prefixos_login` `/login`, `/checkpoint/`, `/authwall`, `/uas/login` e `/signup`, `respostas=()`, `campos_conta=()`, `rolar=True` e `lista_tem_descricao=False`.
13. (T235) Um escopo por termo das buscas ativas (`ctx.termos`), com `id` igual ao termo. O país não entra, porque a busca do LinkedIn usa a cidade do perfil. Endereço: `https://www.linkedin.com/jobs/search/?keywords=<termo>&f_TPR=r604800` (última semana). `proxima` acrescenta `start` de 25 em 25 enquanto a página vem com 25 cartões: monta o endereço a partir de `keywords` e `start` da captura (no mesmo caminho dela) e repõe sempre `f_TPR=r604800`, em vez de copiar a URL capturada (sem `currentJobId`); `limites.MAX_LISTA` corta. Como a fixture real tem no máximo 5 cartões (o `reduzir` do `capturar` corta a lista a `MAX_ITENS = 5`), a contagem de 25 se testa com HTML sintético.
14. (T235) Cartões: um por `componentkey="job-card-component-ref-<id>"`, sem repetir o id. O texto vira linhas; linhas seguidas iguais (depois de tirar " (Verified job)" e " (Vaga verificada)") contam uma vez. As três primeiras são título, empresa e local; o que vem entre parênteses no local vai cru para `modalidade_declarada`. O resto se classifica por expressão: salário vai para `salario_texto` cru (o `ler_salario` já lê "1,621 BRL/month - 2,000 BRL/month" e "R$ 1.621/mês"); "Posted N … ago" ou "há N …" vira `publicada_em`; "Easy Apply" ou "Candidatura simplificada" é ignorado; qualquer outra linha (a frase pessoal) é descartada e não vai para lugar nenhum. `url` é `https://www.linkedin.com/jobs/view/<id>/` e `id_externo` é o id. Cartão sem id ou sem título conta em `pulados`.
15. (T235) Datas relativas: minutos, horas e dias exatos; semanas valem 7 dias; meses valem 30 dias. O leitor recebe o relógio pelo construtor (`__init__(self, relogio: Relogio | None = None)` com `self._relogio = relogio or RelogioReal()`, para o ruff não reclamar de chamada no valor padrão, B008), porque o protocolo não tem relógio.
16. (T235) `detalhar`: a descrição vem de "About the job" ou "Sobre a vaga", em `html`; o contrato vem do bloco do topo ("Full-time", "Tempo integral" e afins, cru); `url_candidatura` é o parâmetro `url` do link `safety/go`, decodificado, sem `mt` nem `urlhash`; endereço que não é `http` ou `https`, ou que falta, dá `None`. Sem a seção da descrição, `detalhar` devolve `None`.
17. (T235) Zero cartões com a mensagem de lista vazia ("No matching jobs found" ou "Nenhuma vaga encontrada") é leitura válida e vazia; zero cartões sem essa mensagem é `formato_mudou`. `pagina_logada` e `e_login` saem das fixtures da T235 (a de `/jobs/` logada e uma de visitante montada à mão). `pagina_logada` não depende de vaga: vale `url` fora dos `prefixos_login` e o link `a[data-view-name="navigation-notifications"]` no HTML. Assim, conta nova sem recomendação não fica presa em `precisa_login`. `pagina_bloqueada` devolve `False`: o desafio é achado pelo `achar_widget` do navegador. (texto real: "No results found"; ver "O que a captura real mostrou")
18. (T235) As fixtures do LinkedIn só saem pela captura com recorte da T234, com `--tirar` para as frases pessoais, e uma pessoa lê cada uma antes de entrar (bloco de recrutadores, nomes). As frases em português, que a sessão não viu numa conta em pt, entram em fixtures montadas à mão, com `montado_a_mao` na `.meta.json`.
19. (T238) O leitor só entra em `LEITORES` na T238, depois da T237 (D136.R4-cidades e D136.R4-lista). Até lá ele existe, tem testes e não aparece para a pessoa.
20. (T236) Documentos: README, wiki e CHANGELOG em pt e en contam o login pela janela comum; os textos de privacidade (README e `configuracoes.privacidade.telemetria`) passam a listar os sites com login que a pessoa liga. A ADR 0005 ganha nota: login pela janela comum e ordem LinkedIn, Gupy, Vagas.com, Catho, Indeed. A T236 vem depois da T238.
21. (T232) O `preparar_preferencias` passa a gravar `signin.allowed = false` no perfil (`PREFERENCIAS` de `navegador/perfil.py`). É uma preferência do perfil, não um argumento do navegador nem automação. Motivo: o Chrome não deve ligar o perfil do joBot à conta do Google que a pessoa usa ao entrar com Google na página. Vale para as duas janelas. Se o login com Google na página quebrar com essa preferência (conferido na verificação manual da T232), a T232 tira a preferência e registra aqui.
22. (T243) A captura logada limpa imagens: `sem_imagens` troca por um marcador o endereço de `img`, `source`, `video` e SVG, os `data-*` com endereço nessas tags e o `url()` de `style`. Motivo: a captura logada mostra imagens ligadas à conta (logo de escola e de empresa do perfil), e nenhum leitor lê imagem. O `--tirar` e a leitura de uma pessoa continuam valendo para o resto.
23. (T238) Na página Saúde das fontes (`/fontes`), o cartão de site com login mostra o nome e um link para Configurações > Sites com login, sem o interruptor (`painel/templates/fontes/pagina.html`). O POST que liga ou desliga uma fonte com login em `/fontes` devolve 422 e não grava (`painel/rotas/fontes.py:254`). Motivo: o aviso de risco só aparece em Sites com login.
24. (T236) Ordem dos sites com login nos documentos: LinkedIn, Gupy (com login), Vagas.com, Catho, Indeed; depois InfoJobs, Glassdoor, Remotar e Trampos, um por vez; os só de tecnologia (Programathor, GeekHunter, Revelo, Coodesh) por último. Remotar e Trampos contam como sites gerais.

**O que a captura real mostrou (2026-11-15):**

- A marca de sessão `a[data-view-name="navigation-notifications"]` sumiu. Hoje o link de notificações (href para `/notifications/`) fica dentro de `[data-testid="primary-nav"]`, e o `pagina_logada` aceita as duas formas.
- O aviso de lista vazia é "No results found" (com "Try shortening or rephrasing your search."), não "No matching jobs found". O conjunto aceita os dois e os equivalentes em português. O texto em português de "No results found" ainda não foi visto.
- A página da vaga não tem `h1`. O topo é o bloco logo depois de `[componentkey^="JobDetails_ManageJobBanner_"]`, a descrição é `[componentkey^="JobDetails_AboutTheJob_"]` e a Easy Apply é um botão `[aria-label^="Easy Apply"]`, sem link.
- O `start=25` fica na URL depois do redirecionamento para `/jobs/search-results/`.
- A página 2 da fixture vem da busca "enfermeiro em São Paulo", porque a de Belo Horizonte da última semana não chegava a 50 vagas.
- Há vagas anunciadas por pessoa física, com o nome no cartão e no título da página. As fixtures foram escolhidas sem esses cartões.
- Na navegação logada, 4 ou 5 respostas em fluxo nunca entregavam o corpo e travavam a página. A T242 pôs prazo nessa espera.
- A T235 tira o contrato dos links da página da vaga que apontam para a própria vaga (`/jobs/view/<id>/`), filtrados por um conjunto fechado (en: Full-time, Part-time, Contract, Temporary, Internship, Volunteer; pt: Tempo integral, Meio período, Contrato, Temporário, Estágio, Voluntário), e não pelo seletor do topo, porque o recorte não traz o irmão do banner. A descrição é a seção "About the job" inteira, sem o título e sem o botão "… more". O link de candidatura só sai quando passa pelo `safety/go` do LinkedIn; link direto para fora fica vazio. Os textos em português ("Selecionada,", contrato, aviso de lista vazia, rótulo de candidatura) não foram vistos numa conta em português.
- Limite conhecido do leitor (T235): `_linhas` (`nucleo/leitores/linkedin.py`) lê uma linha por `<p>` do cartão, e `_vaga` toma as três primeiras como título, empresa e local. Cartão sem a linha da empresa desloca as linhas, e o campo empresa recebe o local. Fica como limite conhecido; vira tarefa nova se aparecer na semana de rede real.
- Vazamento pego na revisão da T235: uma fixture capturada trazia o endereço da imagem do logo de uma escola ligada ao perfil logado; o `src` foi trocado por `exemplo_escola`. Daí a T243: `sem_imagens` (`scripts/capturar_logado.py`, chamada por `preparar` depois do recorte e antes do `--tirar`) troca por um marcador o endereço de imagem de `img`, `source`, `video` (`poster`) e `image` de SVG, os atributos `data-*` com endereço nessas mesmas tags e todo `url()` dentro de `style`.
- Risco conhecido: com o LinkedIn em `LEITORES`, `if leitores():` em `src/jobot/cli/servir.py:198` passa a ser sempre verdadeiro, então `navegador_instalado()` (linha 202) roda em todo `serve`, inclusive nos testes de vida do servidor. Se o CI ficar lento ou instável por isso, os testes trocam a função por um falso.

**Para confirmar com o dono (os mais importantes primeiro):**

1. D136.R4-cidades abaixo (cidade e remoto no texto da busca do LinkedIn), com a opção (a) escolhida pela sessão.
2. D136.R4-lista abaixo (lista do LinkedIn que nunca é completa), com a opção (a) escolhida pela sessão.
3. (decisão 4) A janela automática abre e fecha sozinha por alguns segundos depois que a pessoa fecha a janela de login.
4. (decisão 6) Os textos novos do login e a saída do resultado "fechado".
5. (decisão 13) Filtro fixo da última semana e um escopo por termo.
6. (decisão 14) A frase pessoal do cartão é descartada e o "Easy Apply" não vira etiqueta.
7. (decisão 15) Semanas como 7 dias e meses como 30.
8. (decisão 3) O prazo de 10 minutos continua; a janela é morta 10 segundos depois do pedido para fechar.
9. (decisão 5) Trava do perfil com o nome de outra máquina conta como perfil em uso; o mesmo vale para um `SingletonLock` que não se lê como link e para um alvo torto (sem `-`, ou com um pid que não é número). Consequência: uma pasta de perfil copiada de outra máquina fica "em uso" até a pessoa apagar o `SingletonLock`.
10. (decisão 10) O `--login` da captura só com endereço explícito.
11. (decisão 21) O perfil do joBot grava `signin.allowed = false`, para o Chrome não ligar o perfil à conta do Google.
12. D136.R4-hosts (T234): a limpeza das queries no recorte vale só para links do host da resposta (www.linkedin.com). Links de outros hosts, como os logos em media.licdn.com (com `e=`, `v=` e `t=`), ficam como vieram. Opções: (a) manter; (b) limpar também os hosts que o leitor declarar. Recomendação: (a), porque são assinaturas públicas de logo de empresa, sem dado da pessoa, e cada fixture continua sendo lida por uma pessoa antes de entrar.
13. D136.T235-contrato: contrato pelos links da própria vaga com conjunto fechado (a, atual) ou pelo seletor do topo, refazendo a captura com o irmão do banner (b). Recomendação: (a), porque não depende da árvore de ancestrais e o teste com a página real já cobre.
14. (decisão 23) Saúde mostra o site com login sem interruptor, com link para Sites com login, e a rota recusa com 422.
15. (decisão 24) Remotar e Trampos tratados como sites gerais, não só de tecnologia.
16. (decisão 19, efeito) Com o LinkedIn em `LEITORES`, o grupo "Sites com login" aparece sempre em Configurações (o LinkedIn vem desligado).
17. (T236) A resposta sobre Docker nas Perguntas frequentes deixou de citar CAPTCHA (a pergunta própria sobre CAPTCHA continua na mesma página), e a página Tecnologias ganhou a linha do Playwright ("Lê os sites com login, usando a sessão que você abriu (fase 2). Também roda os testes de tela.").

**D136.R4-cidades (T237, feita na T237): cidade e remoto na busca do LinkedIn.** O `ContextoColeta` só leva `empresas`, `termos` e `paises` (`nucleo/coletores/base.py`), e o desenho já marcava levar as cidades como R4 (`2026-11-15-fase-2-design.md:565`). Sem as cidades, a busca do LinkedIn usa a cidade do perfil da conta, que pode não ser a das buscas da pessoa. Opções: (a) `ContextoColeta` ganha `buscas: Sequence[Busca] = ()`, e o leitor monta um escopo por cargo e cidade (`<cargo> em <cidade>, <UF>`, pulando o `Local` sem cidade, com repetidos tirados por `normalizar`, como o `termos_das_buscas`) e um por cargo remoto (`<cargo> remoto`); (b) ficar só com os termos e a cidade do perfil, e dizer isso na tela do site; (c) um método novo no protocolo do leitor só para o LinkedIn. Recomendação: (a), porque é um campo opcional que os coletores não leem e serve aos próximos sites com login. Trocar o `id` dos escopos depois fecha as vagas dos escopos antigos (`fechar_escopos_extintos`, `navegador/execucao.py:412`) e reabre as que voltarem, então a troca deve vir antes de o leitor ir para `LEITORES`. A T235 sai só com os termos.

Escolha da sessão (dono fora): a opção (a), para confirmar. Consequências: os escopos cargo × cidade + remoto se multiplicam contra o `MAX_LISTA` de 10 páginas por site; o rodízio segura, mas a ida à página 2 fica rara. Trocar o id de escopo marca as ocorrências velhas como sumidas; nada é apagado, e a vaga reabre ao aparecer no escopo novo. Por isso a T237 entra antes de o leitor ir para `LEITORES`. Se o dono mudar a escolha depois, a sessão reescreve a T237.

**D136.R4-lista (T238, feita na T238): lista que nunca é completa.** A busca do LinkedIn ordena por relevância e o filtro é da última semana: uma vaga aberta sai da lista sem ter fechado. Com o escopo "ok", a vaga ausente fecha na hora (`nucleo/tratamento/ciclo_de_vida.py:34-38`), então vagas abertas seriam fechadas por engano toda semana. Opções: (a) o protocolo `LeitorComLogin` ganha `lista_exaustiva: bool`; com `False`, a vaga ausente só fecha depois de 30 dias sem ser vista (`JANELA_PARCIAL`), e a saúde continua "ok"; (b) o leitor marca toda leitura como cortada, e a saúde mostra "parcial" com "listagem incompleta" para sempre; (c) nada, e as vagas fecham por engano. Recomendação: (a), porque não mente na saúde e vale para os próximos sites com busca por relevância. É contrato público do leitor. A T238 também põe o leitor em `LEITORES`. Ponto escolhido para o ciclo de vida: `aplicar_ciclo(..., exaustiva: bool = True)` (`nucleo/tratamento/ciclo_de_vida.py`) e `gravar_escopo(..., *, exaustiva: bool = True)` (`banco/gravacao.py`), sem mudar o `SaidaEscopo`; o `navegador/execucao.py` passa `exaustiva=<leitor>.lista_exaustiva`, e o `agenda/execucao.py` fica no padrão.

Escolha da sessão (dono fora): a opção (a), para confirmar. Consequência: com o filtro de 7 dias, "fechada" no LinkedIn quer dizer "não vista há 30 dias" (a T236 documenta); uma vaga fechada por engano reabre ao reaparecer. Se o dono mudar a escolha depois, a sessão reescreve a T238.

**Como desfazer:** o dono manda trocar qualquer item, e a troca vira tarefa nova com teste. Voltar ao login dentro da janela automática é trocar a `JanelaComum` do `fazer_login` pelo `abrir_contexto` de antes; o Google volta a recusar. Os nomes e os prazos ficam em `navegador/janela_comum.py`, `navegador/abrir.py`, `navegador/limites.py` e `nucleo/leitores/linkedin.py`.

## D137. Tela "Ferramentas" (baixar e remover o navegador) e passo "Sites com login" do assistente (T240 e T241)

**Status:** decidida pela sessão em 2026-11-15 com o dono fora, para confirmar. A tela "Ferramentas" (itens 12 a 16) vem das respostas do dono de 2026-11-15; o desenho fino dela é da sessão, para confirmar.

**Contexto:** o desenho da fase 2 (`docs/superpowers/specs/2026-11-15-fase-2-design.md`, seção 6) pede no lote do primeiro site o botão "Baixar o navegador" no grupo "Sites com login" e o passo opcional "Sites com login" no assistente de primeira execução (D132.24, D132.28; ADR 0011). O plano do login (`2026-11-15-fase-2-login-linkedin.md`) deixou os dois de fora. Em 2026-11-15 o dono mudou o lugar do botão: ele vira o primeiro item de uma tela "Ferramentas" em Configurações, com estado, tamanho, "Baixar" e "Remover", e o grupo "Sites com login" aponta para ela. O plano `docs/superpowers/plans/2026-11-15-fase-2-primeiro-site-resto.md` cobre os dois (T240 e T241) e lista, com o texto proposto, o que espera o dono: o `CLAUDE.md` do projeto e as notas nas ADRs 0005, 0006, 0011, 0022 e 0017. Nenhuma escolha abaixo é de arquitetura, dependência, esquema ou contrato público: nenhuma tarefa fica travada.

**Fatos conferidos na sessão (2026-11-15, Playwright 1.65.1 do projeto):**

- `playwright install chromium` baixa três coisas: o Chrome for Testing (uns 207 MB), o FFmpeg (uns 2 MB) e o Chrome Headless Shell (uns 132 MB). Os tamanhos vieram do cabeçalho do servidor, sem baixar.
- No disco, a pasta do Chromium tem uns 413 MB e a do Headless Shell, uns 283 MB.
- O instalador aceita `--no-shell` (pula o Headless Shell), `--no-progress`, `--dry-run` e `--with-deps`.
- O Playwright grava a marca `INSTALLATION_COMPLETE` na pasta do navegador (`chromium-<n>/`) só no fim, e baixa de novo quando ela falta. O `navegador_instalado` de hoje só confere o executável, que pode existir depois de um download cortado.
- O `navegador_instalado` roda uma vez, ao subir o `serve`, e só com leitor registrado (comentário `shortcut:` em `cli/servir.py`).
- O `python -m playwright` (o `__main__` do pacote) abre o driver node com `subprocess.run` e só espera por ele: um SIGTERM no Python não chega ao node, que seguiria baixando sozinho.
- O `playwright uninstall` sem `--all` apaga só o vínculo desta instalação (`.links/` na pasta dos navegadores) e depois a coleta do próprio Playwright apaga as pastas de navegador que nenhum vínculo restante usa (a mesma coleta que o `install` já roda a cada instalação). Com outra instalação do Playwright usando a mesma versão (os testes de quem desenvolve, por exemplo), a pasta fica. Ele não pega a trava `__dirlock` que o `install` pega. Conferido no `coreBundle.js` do driver 1.65.1 (`uninstall`, `_validateInstallationCache`, `_deleteStaleBrowsers`).
- Na máquina de quem desenvolve, a pasta `chromium-<n>/` tem a marca `INSTALLATION_COMPLETE` e o executável em `chrome-linux64/chrome`, e `.links/` tem três vínculos.

**Decisões (da sessão, para confirmar):**

1. (T240) O comando de baixar é `<python> -P -m playwright install --no-shell chromium`, como processo filho, sem shell e nunca com `--with-deps`. O `--no-shell` pula o Chrome Headless Shell, que o joBot não usa (só abre janela visível): uns 132 MB a menos de download e 283 MB a menos no disco. O `-P` tira o diretório atual do `sys.path`, para uma pasta `playwright/` deixada ali não rodar no lugar do pacote. Contra: os testes de tela, que rodam sem janela, usam o Headless Shell; quem roda os testes instala pelo comando do `CLAUDE.md`, como hoje. Atualiza o desenho, seção 6 (`--no-shell` e `-P`); a T240 corrige a linha do desenho.
2. (T240) O instalador recebe o mesmo ambiente restrito da janela (`ambiente_do_navegador`, com as variáveis de `VARIAVEIS_DO_NAVEGADOR`), mais `PLAYWRIGHT_BROWSERS_PATH` se o `serve` tem, para o Chromium ir para a pasta onde o joBot procura. Nada de tela, token nem chave. As variáveis de proxy seguem a D135, "Para confirmar", item 1: hoje não passam, e quem está atrás de proxy vê "falhou" com o que fazer, e o código de saída fica no registro do joBot.
3. (T240) Prazo de 30 minutos para baixar (`limites.PRAZO_BAIXAR_S = 1800`): 210 MB cabem a 1 Mbit/s. Estourado o prazo, ou fechado o joBot no meio, o processo recebe SIGTERM, espera `ESPERA_SAIR_JANELA_S` e recebe SIGKILL, pela `encerrar` da janela comum (o `_fechar` da T232, que vira público). O instalador abre num grupo de processos próprio (`start_new_session`), e os sinais vão ao grupo (`os.killpg`): o Python e o node que ele abre. Quando o líder sai (sozinho ou por sinal), o `wait()` manda ainda um SIGKILL final ao grupo, ignorando `ProcessLookupError`, para o driver node não ficar órfão. Se o joBot for morto à força (SIGKILL), o instalador segue sozinho até terminar.
4. (T240) O que roda ou o último resultado fica em `app.state` (some ao reiniciar; o estado do navegador volta a ser lido do disco). Um download por vez, com trava própria, separada da trava do login. O segundo clique mostra "Baixando". O resultado terminal (`pronto`, `removido`, `continua` e as falhas) é apagado do `app.state` na primeira leitura que o mostra; a visita seguinte mostra só o estado, para um "Falhou" ou um "Navegador baixado" antigo não ficar na tela. Depois de baixar ou remover, o joBot lê de novo do disco qual navegador usa; o grupo "Sites com login" mostra o novo estado ao abrir de novo a página, sem reiniciar o joBot.
5. (T240) "Baixar" só aparece quando nenhum navegador foi encontrado. Não há passo de confirmação: o tamanho fica escrito na linha ("uns 210 MB de download, dos servidores do Playwright, e uns 420 MB no disco"). Um pedido de baixar com navegador já encontrado (outra aba) não abre nada.
6. (T240) O Chromium do Playwright só conta como instalado com a marca `INSTALLATION_COMPLETE`. Um download cortado volta a mostrar o botão, e o Playwright retoma do zero. Um teste de tela de guarda falha se uma troca de versão do Playwright mudar o lugar da marca. A marca só é conferida em Linux e Windows (`# shortcut:` em `caminho_do_navegador`): revisar quando o Mac entrar.
7. (T240) "Falhou" diz o que fazer: conferir a internet e o espaço livre no disco e tentar de novo, e avisa que os detalhes ficam no registro do joBot (`jobot.log`). A saída do instalador não vai à tela nem ao log; só o código de saída vai ao log. Troca de 2026-11-15: a primeira versão mostrava o comando exato para rodar no terminal; saiu porque a ADR 0023 (`docs/decisions/0023-tudo-pelo-painel.md`, "quem usa nunca precisa do terminal") e a D138 (itens 7, 8 e 11) mandam resolver tudo pelo painel. O texto de falha, portanto, nunca cita o terminal nem mostra comando.
8. (T240) Textos: o aviso de "nenhum navegador" do grupo "Sites com login" ganha o link para "Ferramentas", e o `login.sem_navegador` passa a apontar "Configurações, Ferramentas"; o `saude.sem_navegador` não muda, porque ali a causa pode ser a falta de bibliotecas do sistema. A privacidade (README pt e en e `configuracoes.privacidade.telemetria` pt e en) ganha "aos servidores do Playwright, para baixar o navegador, só quando você aperta 'Baixar' em Ferramentas", e a tabela de tamanhos do README troca "A definir" por "uns 210 MB de download e 420 MB no disco". A T240 entra depois da T236, que mexe nos mesmos quatro textos.
9. (T241) O passo novo fica em `/primeira-execucao/sites`, entre a busca e o segundo plano, na ordem da ADR 0011 (logins antes do segundo plano). O `/primeira-execucao/2` continua sendo o segundo plano. Os números se calculam: com site com login, "Passo 1 de 3", "Passo 2 de 3" e "Passo 3 de 3"; sem, como hoje, "de 2". O assistente escolhe o passo pelo id (`1`, `sites`, `2`), nunca pelo número. As chaves `primeira_execucao.passo` e `primeira_execucao.p2.voltar` ganham parâmetro (`{total}` e `{n}`) nos dois idiomas.
10. (T241) O passo mostra o navegador (item 15) e os cartões dos sites, com o interruptor e o "Fazer login agora". "Continuar" segue com o que a pessoa ligou; "Pular" desliga os sites com login e segue; "Voltar ao passo 1" volta. Os horários das leituras com login não entram no assistente: valem os padrões (9h e 18h) e mudam em Configurações. Foge da ADR 0011, passo 5.
11. (T241) O passo só existe quando há site com login registrado (D132.23); sem nenhum, o assistente fica como hoje e o endereço do passo dá 404. Os testes de hoje do assistente fixam "nenhum site com login", para não mudar quando o LinkedIn entrar no registro.
12. (T240, dono) A tela "Ferramentas" é um grupo novo de Configurações, o último da lista. Ela mostra só o que o joBot usa nesta versão: hoje, só o navegador dos sites com login (o Chromium do Playwright). Cada ferramenta tem nome, estado (instalado, não instalado, baixando, removendo, falhou), tamanho e o botão que couber. Da sessão: como a única ferramenta serve aos sites com login, o grupo só aparece com site com login registrado, como o grupo deles; o tamanho é o aproximado do texto, não medido no disco (medir pediria varrer uma pasta que outras instalações dividem).
13. (T240, dono) O navegador pode ser removido. "Remover" roda `<python> -P -m playwright uninstall`, sem `--all`, pelo mesmo abridor em grupo de processos: ele só apaga o que nenhuma outra instalação do Playwright usa (ver os fatos acima), e o joBot nunca apaga a pasta por conta própria. Da sessão: o botão só aparece com o Chromium do Playwright em uso; com uma leitura ou um login com o navegador aberto (trava do login presa), nada é removido e a tela pede para esperar; a remoção segura a trava do login até acabar. Prazo de 5 minutos (`limites.PRAZO_REMOVER_S = 300`), estourado: SIGTERM e SIGKILL ao grupo e "falhou" com o que fazer. No mesmo venv, o `uninstall` remove também os navegadores dos testes de tela, e quem desenvolve baixa de novo pelo comando do `CLAUDE.md`; a verificação manual usa `PLAYWRIGHT_BROWSERS_PATH` numa pasta vazia. Fechado o joBot no meio, a remoção não recebe sinal e termina sozinha: cortada no meio, poderia deixar a marca sem o navegador. Se outra instalação usa a mesma pasta, ela fica, e a tela diz que outro programa a usa e que o joBot continua usando.
14. (T240, nota do dono) Com o Google Chrome do sistema encontrado, o joBot já o usa (`navegador_instalado` devolve `chrome`). Da sessão: a linha do navegador diz "O joBot usa o Google Chrome deste computador. Não precisa baixar nada, e o joBot não mexe nele", sem tamanho, sem "Baixar" e sem "Remover". Um Chromium do Playwright que também esteja no disco não aparece: o joBot não o usa enquanto o Chrome existir.
15. (T241, dono pediu a escolha) O passo do assistente reaproveita o mesmo fragmento da tela "Ferramentas" (com "Baixar" e "Remover"), em vez de um link para Configurações: o link tiraria a pessoa do assistente no meio, e o fragmento já funciona em qualquer página. Não há um segundo modo do fragmento sem o "Remover": a resposta do HTMX é a mesma nas duas telas.
16. (regra futura, sem tarefa, dono) As ferramentas que entrarem na fase 4, o Claude Code e o Codex, o joBot instala mas nunca remove: a tela mostra o estado e o "Baixar", sem "Remover". Até lá, nenhuma das duas aparece na tela nem no plano.

**Para confirmar com o dono (os mais importantes primeiro):**

1. (decisão 10) "Pular" desliga os sites com login que a pessoa tiver ligado no passo.
2. (decisão 1) O `--no-shell`: o joBot baixa só o Chromium com janela.
3. (decisão 5) Sem passo de confirmação antes do download, só o tamanho escrito ao lado do botão.
4. (decisão 9) O passo dos sites entre a busca e o segundo plano, com "Passo 2 de 3".
5. (decisão 3) Prazo de 30 minutos para o download.
6. (decisão 2) Sem as variáveis de proxy no instalador, junto da D135, "Para confirmar", item 1.
7. (decisão 13) "Remover" pelo `playwright uninstall`, que deixa a pasta quando outra instalação a usa, e bloqueado durante leitura ou login.
8. (decisão 12) A tela "Ferramentas" só com site com login registrado, como o grupo deles.
9. (decisão 15) O passo do assistente com o mesmo fragmento da tela "Ferramentas", "Remover" incluído.
10. (decisão 10) Os horários dos sites com login fora do assistente.

**Como desfazer:** o dono manda trocar qualquer item, e a troca vira tarefa nova com teste. Os comandos, o ambiente e o abridor em grupo moram em `navegador/instalador.py`; os prazos, em `navegador/limites.py`; a marca de instalação, em `caminho_do_navegador` de `navegador/abrir.py`; a tela, em `painel/rotas/configuracoes.py` (`contexto_ferramenta_navegador` e as rotas `/configuracoes/ferramentas/navegador`); o passo do assistente, em `painel/rotas/primeira_execucao.py` (`numeros_dos_passos`). Tirar o passo é voltar os três redirecionamentos do passo 1 para `/primeira-execucao/2`.

## D138. Ideias do memo: painel, fila, instalador e ordem das fases

**Status:** decidida pelo dono em 2026-11-15 (itens 1 a 14); itens 15 a 17 são escolhas da sessão, para confirmar; a tecnologia da tela do instalador (item 16) o dono respondeu em 2026-11-15: Tauri (D142)

**Contexto:** o dono respondeu às perguntas do memo de ideias. As respostas mudam a ordem das fases (ADR [0017](docs/decisions/0017-fases.md)), criam a tela Ferramentas e o princípio "tudo pelo painel" (ADR [0023](docs/decisions/0023-tudo-pelo-painel.md)) e mexem na [0009](docs/decisions/0009-ia-backends-e-modelos.md) (Claude Code e Codex). Os números Q1 a Q13 são os das perguntas do memo.

**Decisões do dono:**

1. (Q3, dono) A candidatura automática fica para depois. A ADR 0001 segue como está.
2. (Q1, dono) A tela "Panorama" (visão geral das vagas e da busca) entra na 0.3.0, num lote separado do login.
3. (Q2, dono) Completar a fila de candidaturas: link de candidatura por e-mail, a pergunta "Você se candidatou?" quando a pessoa volta ao painel e as datas de cada passo. Entra na 0.3.0, junto com o Panorama.
4. (Q4, dono) O instalador vem logo depois da fase 2, só para 64 bits.
5. (Q5, dono) O instalador mostra uma lista de ferramentas para marcar. As que ficarem sem marca aparecem depois no painel, para baixar quando a pessoa quiser. O painel permite reconfigurar a escolha.
6. (Q9, dono) A lista mostra só o que o joBot já usa naquela versão. O Claude Code e o Codex entram junto com a IA.
7. (Q10, dono) Tela "Ferramentas" em Configurações, com estado, tamanho e botão "Baixar". O navegador pode ser removido. O Claude Code e o Codex o joBot instala, pelos instaladores oficiais deles, mas nunca remove. O joBot nunca vê senha nem token: o login é feito pela própria ferramenta. A ADR 0009 registra isso.
8. (Q11, dono) O botão "Baixar o navegador" (T240) vira o primeiro item da tela Ferramentas. O cartão dos sites com login aponta para lá.
9. (Q12, dono) Ordem: LinkedIn (fase 2), Panorama e fila, versão 0.3.0, instalador (vira a fase 3), IA local (vira a fase 4). As fases seguintes andam um número: extensão fase 5, áudio e Gmail fase 6, treino fase 7, GitHub Pages fase 8, publicação fase 9. Os instaladores saem da fase de publicação. A ADR 0017 e os documentos de quem usa (README, wiki, guia de contribuição) já usam a nova ordem.
10. (Q13, dono) O instalador sai para Windows e Linux primeiro. O Mac vem depois e é testado só no GitHub Actions.
11. (Q6, dono) Tudo pelo painel: quem usa nunca precisa do terminal. O painel ganha os botões "Atualizar o joBot" e "Encerrar". Registrado na ADR 0023.
12. (Q7, dono) A revisão da documentação vem depois da T236.
13. (Q8, dono) O mapa das perguntas do perfil é escrito agora, só como documento: `docs/superpowers/specs/2026-11-15-perguntas-do-perfil.md`. Outro trabalho o escreve; aqui só se cita.
14. (pedido novo, dono) No instalador, as ferramentas 100% essenciais vêm marcadas e não dá para desmarcar. A tela do instalador deve ser muito bonita, para quem instala ter confiança, e pode usar outra linguagem, mais adequada para essa tela.

**Escolhas da sessão (para confirmar):**

15. (sessão) Quais são as essenciais travadas: o joBot e o Python que ele usa. O navegador para sites com login é opcional: vem marcado, mas dá para desmarcar.
16. (sessão) A tecnologia da tela do instalador foi respondida pelo dono em 2026-11-15: Tauri (D142). A assinatura de código (que tem custo) não foi escolhida. A pesquisa voltou; a sessão recomenda o resto, para o dono decidir:
   - Tela: Tauri (escolhida, D142). A tela é feita em HTML e CSS, no mesmo visual do painel, ~~num projeto à parte~~ (superado em 2026-11-17: pasta `desktop/` do mesmo repositório, D171.4 e ADR 0025) (Rust e HTML); gera o instalador NSIS no Windows, AppImage e .deb no Linux e .dmg no Mac. O joBot em si continua instalado pelo `uv tool install`, chamado pela tela. Alternativas: Inno Setup com a página de componentes (só Windows, visual limitado) ou pywebview com PyInstaller (tudo em Python, visual menos polido).
   - Assinatura no Windows: SignPath Foundation, grátis para projeto de código aberto (exige o build no GitHub Actions, MFA e uma página com a política de assinatura). Sem assinatura, o SmartScreen pede "Executar assim mesmo"; mesmo assinado, ele avisa até o programa ganhar reputação. O Azure Artifact Signing (US$ 9,99 por mês) não atende o Brasil. Um certificado OV custa de US$ 129 a 434 por ano.
   - Mac: sem a conta de desenvolvedor da Apple (US$ 99 por ano) e a notarização, a pessoa precisa liberar o programa em Ajustes, em "Abrir Mesmo Assim". Recomendação: documentar esse passo até o Mac entrar (decisão 10).
17. (sessão) Sem PR da `dev` para a `main` até a 0.3.0 (já na D134.6).

**Para confirmar com o dono:**

1. (decisão 15) As essenciais travadas são só o joBot e o Python que ele usa. Se a pessoa desmarca o navegador, os sites com login ficam desligados até ela baixar pela tela Ferramentas.
2. (decisão 16) A tecnologia da tela do instalador (recomendação: Tauri) e a assinatura de código (recomendação: SignPath Foundation no Windows, grátis; no Mac, documentar o "Abrir Mesmo Assim" até decidir sobre os US$ 99 por ano). (Tecnologia respondida pelo dono em 2026-11-15: Tauri, D142. A assinatura continua aberta.)
3. (decisão 17) Nenhum PR para a `main` até a 0.3.0.
4. (decisão 7) O Claude Code e o Codex passam a ser baixados pelo joBot. Antes, a D125 só abria a página oficial. Falta conferir, na fase 4, o endereço e o jeito de cada instalador oficial, e se os termos de cada um permitem o joBot chamá-lo.
5. (decisão 14) A tela do instalador é feita em HTML e CSS dentro do Tauri (D142) e segue o visual de app do Mac (D140).

**Como desfazer:** o dono manda trocar qualquer item. A ordem das fases fica na ADR 0017 e a regra "tudo pelo painel" na ADR 0023; trocar uma delas é editar a ADR e os documentos listados na decisão 9.

## D139. Estado das contas no painel e IA no instalador

**Status:** decidida pelo dono em 2026-11-15 (itens 1 a 11, 34 e 35); itens 12 a 33, 36 e 37 são escolhas da sessão, para confirmar, menos o 13 e o 401/403 do 18, que o dono confirmou em 2026-11-15

**Contexto:** o dono respondeu, em 2026-11-15, a duas perguntas: como o painel mostra se a sessão de cada site com login ainda vale, e como a IA entra no instalador. Os números Q1 a Q11 são os das perguntas dessa rodada; Q12 e Q13 vieram depois do desenho (itens 34 e 35), e a resposta sobre 401 e 403 (item 18) também. O desenho do lote "Contas" está em `docs/superpowers/specs/2026-11-15-contas-design.md`; os números D139.n são os da seção 11 dele. A parte de IA mexe no que a D138.6, a ADR [0023](docs/decisions/0023-tudo-pelo-painel.md) (`:24`) e a ADR [0009](docs/decisions/0009-ia-backends-e-modelos.md) já dizem; a decisão 10 mantém as três como estão.

**Decisões do dono:**

1. (Q1, dono) O protótipo do instalador no Canvas ganha a parte de IA no mesmo protótipo.
2. (Q2, dono) "Baixar Claude/Codex" quer dizer os programas de terminal Claude Code e Codex CLI.
   - O login é pela assinatura: o instalador baixa cada um e abre o login dele no fim.
   - A chave de API é a alternativa, em Configurações › Serviços.
   - O Claude Code precisa de plano pago (Pro, Max ou acima).
   - O Codex entra com "Sign in with ChatGPT" ou com chave de API. Os termos da OpenAI sobre automação são conferidos na fase 4 (D125); se proibirem, o Codex fica só com a chave de API.
   - Os textos dizem "baixa o Claude Code se você marcar", nunca "vem com".
3. (Q3, dono) Grupo novo no instalador, "Inteligência artificial (opcional)", com Claude Code, Codex e Modelo local, desmarcados por padrão. O instalador pode lembrar a última escolha.
4. (Q4, dono) Cada site mostra um estado, com a hora da última conferência ("conferido hoje às 09:02"), guardados no banco. Os estados são: Conectado; Precisa entrar de novo; Nunca entrou; Não deu para conferir (sem internet, desafio, bloqueio).
5. (Q5, dono) "Precisa entrar de novo" avisa em dois lugares: uma faixa no topo de toda tela do painel, com o botão "Entrar de novo", e um aviso no computador (`notify-send`), uma vez por queda.
6. (Q6, dono) Botão "Conferir agora" por site: abre o site, confere a sessão e atualiza o estado, sem ler vagas. A conferência também é automática a cada leitura das 9h e das 18h.
7. (Q7, dono) Sem visitas para manter a sessão viva. O perfil persistente guarda a sessão; se ela cai, o aviso da decisão 5 dispara.
8. (Q8, dono) Uma aba única, "Contas", em Configurações, troca a "Sites com login".
   - LinkedIn e os próximos sites: agora.
   - Claude Code e Codex: fase 4, com o estado vindo da própria ferramenta.
   - Gmail: fase 6 (OAuth) (superado pela D145: o cartão do Gmail entra no lote de Contas, por senha de app; a leitura dos e-mails fica na fase 6).
   - 2Captcha: mostra "chave salva", testada só no clique.
9. (Q9, dono) Lote pequeno agora, ainda na fase 2, antes do Panorama (0.3.0). Só o LinkedIn por enquanto.
10. (Q10, dono) O Canvas ganha a parte de IA agora. O instalador real sai na fase 3 sem ela e ganha o grupo de IA na fase 4. A D138.6 continua valendo: a lista do instalador mostra só o que a versão usa.
11. (Q11, dono) O modelo local é escolhido pela RAM, e a pessoa pode trocar.
   - Só o Qwen3.5 2B (1,28 GB) e o 4B (2,74 GB), com o tamanho à vista: 2B para 8 GB de RAM, 4B para 12 GB ou mais (ADR 0009).
   - O 9B espera a medida de velocidade em CPU.
   - O Whisper fica para a fase 6.

**Escolhas da sessão (para confirmar):**

12. (sessão) Estado "Desligado" para site com o interruptor desligado: sem conferência e sem aviso. Ele vem da `fonte.ligada` e não é gravado.
13. (sessão, confirmado pelo dono em 2026-11-15) A faixa fica enquanto a queda estiver aberta, não só no estado "Precisa entrar de novo". Queda aberta é: site ligado, com leitor registrado, `entrou_em` e `avisado_em` preenchidos. A faixa some quando o site volta a "Conectado" (`avisado_em` vira nulo), é desligado ou passa pelo "Esquecer logins". Assim, "Precisa entrar de novo" que vira "Não deu para conferir" (sem rede, em uso, desafio) mantém a faixa, e o cartão continua mostrando "Não deu para conferir", com o motivo. "Nunca entrou" (`entrou_em` nulo) nunca mostra a faixa. Ela não tem botão de fechar.
14. (sessão) Mudanças no Canvas:
   - Painel › Ferramentas ganhou cartões de IA: Claude Code e Codex só com "Baixar" (nunca remover, D138.7); Modelo local com "Baixar", "Remover" e "Trocar modelo".
   - A página "Pronto" ganhou os botões "Entrar no Claude Code" e "Entrar no Codex".
15. (sessão) O lote Contas mexe em `configuracoes.py` como a T240 e a T241. Ele vem depois delas e usa os nomes delas (`_trava(request, nome)`, `leitores_do_painel`, `contexto_sites_com_login`, `_sites_cartoes.html`). Ordem com o visual (D140, decisão 9): o lado de trás (migração 0009, gravação, `conferir_sessao`, rotas, aviso no computador) vai em paralelo ao visual novo; a aba Contas e a faixa do topo esperam a base visual nova da D140. Rotas, ids, chaves i18n e textos não mudam com o visual.
16. (sessão) Tabela `sessao_site` na migração `0009_sessao_site.sql`, uma linha por site: `fonte` (chave, ligada à `fonte`), `estado` (`conectado`, `precisa_entrar`, `nao_conferiu`), `motivo` (nulo ou conjunto fechado), `conferido_em`, `entrou_em` e `avisado_em`. O `entrou_em` vira agora em "Conectado" e fica como está em "Precisa entrar de novo" e "Não deu para conferir". Gravação numa instrução só, com `INSERT ... ON CONFLICT DO UPDATE`.
17. (sessão) Nada vai para `evento`, que só aceita ações de vaga. Nenhum gatilho novo.
18. (sessão) Na entrada de cada leitura: página logada dá "Conectado" (e `entrou_em` passa a ser agora); página de login dá "Precisa entrar de novo"; 401, 403, bloqueio, desafio, 429, erro de rede, falta de tela ou de navegador dão "Não deu para conferir", com o motivo. O 401 e o 403 ficam em "Não deu para conferir" porque o código já os trata como bloqueio (`src/jobot/navegador/pagina.py:285`) (confirmado pelo dono em 2026-11-15: só a tela de login leva a "Precisa entrar de novo").
19. (sessão) "Nunca entrou" é "Precisa entrar de novo" com `entrou_em` nulo, ou site sem linha. "Esquecer logins" volta todos os sites a esse estado, sem apagar a linha.
20. (sessão) "Fazer login agora": "pronto" dá "Conectado" (e `entrou_em` passa a ser agora); "nao_entrou" e "tempo_esgotado" dão "Precisa entrar de novo" (ou "Nunca entrou", se nunca entrou); "sem_tela", "sem_navegador" e "em_uso" dão "Não deu para conferir".
21. (sessão) "Conferir agora" mora no `navegador`, abre só a página de entrada, usa a trava `login`, recusa se o perfil estiver em uso, não chama o 2Captcha e não grava `execucao` nem saúde. Quando dá "Conectado", grava `entrou_em` = agora, como a leitura agendada e o "Fazer login agora".
22. (sessão) O aviso no computador sai só pela leitura agendada, na passagem para "Precisa entrar de novo" de um site em que a pessoa já entrou (`entrou_em` preenchido), e o `avisado_em` lembra que já avisou. "Conferir agora" e "Fazer login agora" marcam como avisado sem mandar o aviso, porque a pessoa está na tela. O `avisado_em` só volta a nulo em "Conectado" ou no "Esquecer logins".
23. (sessão) A faixa fica em `base.html`, logo depois do aviso de versão, carregada pela rota `/aviso-contas`. O botão "Entrar de novo" leva ao cartão do site na aba Contas.
24. (sessão) A hora aparece em hora local: "hoje às", "ontem às" ou a data, comparando com o dia local do relógio do painel.
25. (sessão) O grupo passa a ser `contas`. O `GET /configuracoes/sites-com-login` responde 303 para `/configuracoes/contas`. As rotas de ação mudam de caminho, sem cópia nas velhas.
26. (sessão) A aba Contas tem a linha do 2Captcha ("chave salva" ou "sem chave"), com o botão "Testar" da tela Serviços e um link para ela.
27. (sessão) O passo do assistente mantém o título "Sites com login (opcional)".
28. (sessão) O link de `/fontes` vai para a aba Contas, com o texto "Ligue e desligue em Configurações › Contas".
29. (sessão) Chaves i18n novas em `configuracoes.contas.*` e `casca.aviso_contas.*`. As chaves `configuracoes.sites_com_login.*` que mantêm o sentido ficam com o nome atual; só a do nome da aba sai.
30. (sessão) A conferência automática é a própria entrada da leitura agendada, sem visita a mais.
31. (sessão) Site desligado não é conferido, nem pelo botão (que some) nem pela leitura.
32. (sessão) Prazo do "Conferir agora": `limites.PRAZO_CONFERIR_S = 60`. Estourou, o estado fica "Não deu para conferir", com o motivo `sem_rede`.
33. (sessão) A espera do "Conferir agora" pergunta ao painel a cada 2 s.

**Respostas do dono depois do desenho (2026-11-15) e a escolha da sessão que veio com elas:**

34. (Q12, dono) A faixa do topo segue a queda aberta, não só o estado "Precisa entrar de novo" (regra na decisão 13). Assim a faixa não some quando a leitura seguinte só não consegue conferir.
35. (Q13, dono) "Conferir agora" tem intervalo mínimo de 10 minutos desde o último `conferido_em` do site, de qualquer origem (leitura agendada, "Buscar agora", "Conferir agora", "Fazer login agora").
   - Constante nova `limites.INTERVALO_CONFERIR_S = 600`, em `src/jobot/navegador/limites.py`.
   - Dentro do intervalo, o botão fica desabilitado e o cartão mostra a hora da última conferência.
   - A rota recusa antes de pegar a trava e sem abrir o navegador, e devolve o cartão como está.
   - A comparação usa o `relogio_do_painel`; a borda libera (exatamente 600 s passa).
36. (sessão) Site sem linha e linha com o motivo `esquecido` ficam fora da conta do intervalo (esquecer não é conferência). O botão desabilitado traz a frase `configuracoes.contas.conferir_espera` ("Conferido há pouco. Dá para conferir de novo em alguns minutos."), sem número, para o texto não depender da constante.
37. (sessão) O botão "Conferir agora" some quando o site está "Nunca entrou" (sem linha, ou `entrou_em` nulo), como já some em "Desligado". A rota não recusa esse caso: só o cartão esconde o botão.

**Para confirmar com o dono:**

1. (decisão 12) O estado "Desligado". A faixa sem botão de fechar (decisão 13) o dono já confirmou em 2026-11-15.
2. (decisão 14) As mudanças no Canvas: os cartões de IA na tela Ferramentas e os botões de login na página Pronto.
3. (decisão 18) Respondido pelo dono em 2026-11-15: 401 e 403 na entrada ficam em "Não deu para conferir", com o motivo `bloqueio`, como o código faz hoje. Só a tela de login leva a "Precisa entrar de novo".
4. (decisão 22) As ações feitas na tela não mandam aviso no computador.
5. (decisões 25 e 27) As rotas de ação mudam de caminho sem cópia, e o assistente mantém o título "Sites com login (opcional)".
6. (decisão 15) A ordem: T240 e T241 primeiro, depois o lote Contas, e só então o Panorama.
7. (decisão 22) O "Buscar agora" também lê os sites com login, então ele também pode mandar o aviso no computador, mesmo com a pessoa na tela. Continua uma vez por queda.
8. (decisões 18 e 32) Qualquer erro do navegador ao abrir a página de entrada aparece como "Sem internet ou o site não respondeu". No "Conferir agora", um site que pede para esperar ou uma verificação anti-robô demorada estouram o prazo de 60 s e aparecem com esse mesmo motivo.
9. (decisão 36) Site sem linha e linha "esquecido" ficam fora do intervalo de 10 minutos, e o botão desabilitado diz "Conferido há pouco. Dá para conferir de novo em alguns minutos.", sem número.
10. (decisão 37) O botão "Conferir agora" some em "Nunca entrou" (como em "Desligado"): não há sessão para conferir, e quem nunca entrou usa "Fazer login agora".

**Como desfazer:** o dono manda trocar qualquer item. O desenho do lote fica em `docs/superpowers/specs/2026-11-15-contas-design.md`; trocar um estado, a faixa, o intervalo ou o aviso é editar o desenho antes do plano. A parte de IA do instalador fica no protótipo do Canvas até a fase 4; voltar atrás é tirar o grupo do protótipo.

## D140. Visual de app do Mac

**Status:** decidida pelo dono em 2026-11-15. Todos os itens são do dono; não há escolha da sessão. As regras de cada item, a segunda rodada de respostas do dono e as escolhas da sessão estão na D143.

**Contexto:** o dono pediu, em 2026-11-15, que o joBot pareça um app da Apple para Mac, seguindo as Human Interface Guidelines (developer.apple.com/design). A ADR [0008](docs/decisions/0008-painel-e-visual.md) dizia só "estilo Apple".

**Decisões do dono:**

1. Alcance: o painel inteiro, o assistente da primeira execução e o instalador (o protótipo agora; o instalador real na fase 3).
2. Referência: as Human Interface Guidelines atuais para macOS (macOS 27). Ideias e fatos públicos podem ser usados; nenhum arquivo da Apple entra no repositório (sala limpa, ADR [0016](docs/decisions/0016-licenca-clean-room-e-processo.md)).
3. Estrutura como a do Mail: barra lateral no lugar das abas de cima, com Destaques de hoje, Todas, Novas, Fecham logo, Salvas, Candidatei, Programas e Ocultas; depois Buscas, Empresas e Fontes. Barra de ferramentas com a busca, a lista no meio e o detalhe à direita. Configurações no jeito dos Ajustes do Sistema. Os endereços das páginas não mudam.
4. Material: o Liquid Glass do macOS 27 (translucidez), com fundo sólido quando a pessoa liga "Reduzir transparência" ou "Aumentar contraste".
5. Janela até a fase 3: modo app do Chrome, Edge ou Chromium instalado; sem eles, o Chromium do Playwright que o joBot já baixa; sem ele, uma aba comum. A janela própria vem na fase 3 (D142).
6. Fonte: a SF no Mac, pela fonte do sistema; a Inter, já embutida, nos outros sistemas. SF Pro e SF Symbols nunca entram no repositório: a licença só vale nas plataformas da Apple.
7. Ícones: Lucide, copiados para o repositório com o arquivo de licença deles.
8. Ordem: construído no painel de verdade, numa branch; a tela de vagas vai primeiro para o ok do dono, depois as outras telas. Ver também: D157 (conferência por fotos, para confirmar).
9. Contas: o lado de trás do lote Contas (D139) segue em paralelo; a aba Contas e a faixa do topo esperam a base visual nova.

**Continuam valendo:** o painel só em 127.0.0.1, nenhum recurso externo, o contraste do critério 29, o movimento reduzido e os dois idiomas.

**Como desfazer:** o dono manda trocar qualquer item. O visual novo nasce numa branch; enquanto o dono não dá o ok, descartar a branch desfaz tudo. A ADR 0008 guarda uma nota sobre isto; voltar atrás é tirar a nota e voltar ao "estilo Apple".

## D141. Laya antes da fase 4

**Status:** decidida pelo dono em 2026-11-15. Todos os itens são do dono; não há escolha da sessão.

**Contexto:** havia um descompasso. O encaixe pelo sentido (D122) dependia do Laya ajustado (ADR [0015](docs/decisions/0015-treino.md)), mas o treino ficava na fase 7 (ADR [0017](docs/decisions/0017-fases.md)). Até lá o encaixe compara a palavra exata (D109).

**Decisões do dono:**

1. O ajuste fino do Laya (ADR 0015) sai da fase 7 e acontece antes da fase 4.
2. O Laya ajustado entra no encaixe junto com o Qwen local: ele reconhece palavras diferentes que querem dizer a mesma competência.
3. Os outros treinos continuam na fase 7.
4. Sem mudança no resto da D122: quantizar primeiro, destilar só se ficar lento, rodar só na máquina da pessoa, treino no RunPod.

**O que acontece até o Laya entrar:** a dica de variações da D109 segue como está, na tela de buscas ("coloque variações, uma por linha"), porque o encaixe compara a palavra exata e sem sinônimos. Esta decisão não mexe nela. O texto da D109 ("só chega na fase 3") e o título da D122 ("fases 3 e 6") usam a numeração antiga das fases; vale a ordem da ADR 0017. O ponto em aberto da ADR 0015 (conferir nos termos de cada fonte se as vagas podem entrar em treino de modelo público) passa a valer antes deste treino, não antes da fase 7.

**Como desfazer:** o dono manda trocar qualquer item. Voltar atrás é devolver o ajuste do Laya à fase 7 e tirar as notas das ADRs 0015 e 0017.

## D142. App de desktop e botões da janela

**Status:** decidida pelo dono em 2026-11-15. Todos os itens são do dono; não há escolha da sessão.

**Contexto:** o dono decidiu como o joBot vira um app com janela própria. A D140 cobre o visual; a D138 (decisão 16 e item 2 do "Para confirmar") deixava a tecnologia da tela do instalador em aberto.

**Decisões do dono:**

1. Na fase 3 o joBot vira um app de desktop: uma casca Tauri com ícone e janela própria em volta do mesmo painel. O servidor continua em 127.0.0.1 e nada é reescrito. A janela usa o navegador embutido do sistema: WebKitGTK no Linux, WebView2 no Windows e WKWebView no Mac.
2. O mesmo projeto Tauri gera o instalador (D138, decisão 16). Isso responde a parte da tecnologia do item 2 do "Para confirmar" da D138; a assinatura de código continua aberta.
3. Botões da janela: no Mac, os botões do próprio sistema, com a barra de título sobreposta ao conteúdo. No Windows e no Linux, janela sem a moldura do sistema e três círculos (vermelho, amarelo e verde) à esquerda, desenhados por nós em CSS ou SVG, nunca imagem da Apple. Continuam funcionando: arrastar pela barra, clique duplo para maximizar, redimensionar pela borda, os atalhos de teclado do sistema e nomes acessíveis nos botões.
4. Custos aceitos: no Windows 11 some o menu de encaixe que aparece ao passar o mouse no botão de maximizar; quem usa Windows está acostumado com os botões à direita; os gerenciadores de janela do Linux variam e serão conferidos na fase 3.
5. Até a fase 3, a janela do modo app (D140) usa a moldura do sistema.

**Como desfazer:** o dono manda trocar qualquer item. Até a fase 3 só existe texto (esta D e as notas das ADRs 0003, 0008 e 0017); voltar atrás é editá-los. Se o Tauri sair, a tela do instalador volta ao item 2 da D138.

## D143. Regras do visual de app do Mac

**Status:** os itens 12 a 20 foram decididos pelo dono em 2026-11-15, na segunda rodada, e os itens 55 a 60 em 2026-11-16, na terceira. Os itens 1 a 11 são os da D140 e da D142, com a mesma numeração do desenho. Os itens 21 a 54 e 61 a 71 são escolhas da sessão, para confirmar com o dono, menos o 32, confirmado pelo dono no item 58, e a parte do 48 aceita no item 60. Nenhuma pergunta aberta trava o plano: o "Para confirmar" abaixo lista só escolhas da sessão, que valem para construir.

**Contexto:** depois da D140 e da D142, a sessão levantou as regras das Human Interface Guidelines que valem para o painel (tipo, cor, vidro, janela, controles, teclado, escrita e acessibilidade) e levou ao dono, em 2026-11-15, as que mudam o que ele vê. O dono respondeu "sim" a quase tudo e recusou uma: tirar o seletor de tema. O desenho com todos os valores está em `docs/superpowers/specs/2026-11-15-visual-mac-design.md`, e a numeração abaixo é a da seção 11 dele (D143.1 a D143.71). Em 2026-11-16, numa terceira rodada, o dono respondeu como a barra de progresso anda, onde ela aparece e o que a linha da etapa diz, e escolheu a barra lateral e a linha de vaga.

**Decisões do dono (primeira rodada):** os itens 1 a 11 repetem a D140 (itens 1 a 9) e a D142 no desenho, sem mudança. O item 4 (Configurações com a lista de grupos à esquerda, cada grupo no seu endereço) é desvio consciente da HIG, que no Mac põe os ajustes numa janela com barra de painéis.

**Decisões do dono (segunda rodada):**

12. Texto de 13px em controles e listas, de 14 a 15px na descrição da vaga, e uma opção de tamanho do texto em Configurações.
13. Tema: o dono não quer tirar o seletor. A pessoa escolhe se o joBot fica claro, escuro ou igual ao sistema, como a ADR [0008](docs/decisions/0008-painel-e-visual.md) já diz ("chave manual"). A HIG recomenda seguir só o sistema; é um desvio consciente, registrado no desenho.
14. O seletor de idioma sai da barra e vai para Configurações > Geral.
15. Paleta de comandos no ⌘K (Ctrl+K fora do Mac) e menu de contexto no botão direito. Sem barra de menus falsa.
16. Descartar e arquivar sem pergunta de confirmação, com Desfazer.
17. O Desfazer aparece numa faixa que fica até a pessoa fechar; não some sozinho. As duas exceções (outra ação desfazível toma o lugar dela, e uma página nova carregada inteira a tira) são escolha da sessão, no item 36.
18. Primeira execução com três passos e "Pular" sempre visível; quem pula cai em Vagas com os padrões.
19. Mesmo visual no Windows e no Linux; só a fonte muda (a Inter).
20. As abas de Vagas viram itens da barra lateral; sem controle segmentado no lugar delas.

**Escolhas da sessão (para confirmar):**

21. O seletor de tema fica em Configurações > Geral, junto do idioma e do tamanho do texto, com padrão Sistema, e na paleta de comandos; sai da barra de cima e não fica na barra de ferramentas, porque o tema se escolhe uma vez e a barra fica com as ações do dia a dia. Já foi anunciado ao dono.
22. O grupo Geral fica em primeiro na lista e reúne o que hoje está em Aparência: tema, idioma, tamanho do texto, país e moeda. O grupo se chama `geral`, e `GET /configuracoes/aparencia` manda para `/configuracoes/geral` (303), como na D139, para o link velho continuar funcionando. O 303 vale só para o GET; o formulário de país e moeda passa a gravar em `/configuracoes/geral`.
23. Tamanho do texto: Padrão (13px), Grande (15px) e Maior (17px, o de hoje), gravado na chave `tamanho_texto` pela rota nova `/preferencias/texto`, igual à do tema.
24. Cor de destaque fixa em #0071e3: o azul do sistema não chega a 4,5:1 com texto branco.
25. Vidro só na barra lateral, na barra de cima e nas camadas que flutuam (menu, paleta, alerta, folha). O conteúdo fica opaco, e as faixas de aviso também; os cartões de hoje perdem o vidro. A lista e o detalhe rolam no próprio espaço, sem nada passar por baixo do vidro. Fundo sólido com "Reduzir transparência", "Aumentar contraste", navegador sem suporte ou janela fora de foco.
26. Movimento sem rebote no app todo; um rebote mínimo só na folha que desce e no detalhe sobreposto. A mola de hoje sai. Com movimento reduzido, só esmaecer.
27. Atalhos: ⌘, (Configurações), ⌘K, ⌘Z (desfazer), ⇧⌘Z (refazer), ⌘?, Esc e ⌘., / (busca), setas, Home, End, J, K e Return na lista. ⌘Z e ⇧⌘Z só fora de campo de texto; dentro dele ficam com o navegador. ⌘F e ⌘A ficam com o navegador: a lista é de seleção única e não há ação em lote, então o ⌘A levado ao dono sai. Sem ⌘R, ⌘N e ⌘W. O ⌘K conflita com a busca do Firefox e do Chrome fora do Mac; por isso a paleta também tem um botão na barra.
28. Caixa de marcar na maior parte de Configurações; interruptor só onde a opção comanda um grupo.
29. Um tamanho de barra lateral; contagem em texto simples, sem pílula.
30. Escrita: só a primeira letra maiúscula em português; Title Case em inglês em botão, menu e título; botão no infinitivo; "você"; erro sem humor.
31. Os valores sem medição (cores novas, vidro, raios, sombras, tempos e medidas) valem como proposta e são conferidos depois num Mac com o Medidor de Cores Digital. A lista está no fim do desenho.
32. Sugeridas como segundo nível sob Empresas, Sites depois de Fontes e Configurações por último. O dono confirmou em 2026-11-16 (item 58).
33. Barra lateral com as seções "Vagas" e "Onde buscar"; as contagens aparecem em toda página, por um ajudante único que junta a contagem das abas e a de Destaques de hoje (que hoje é calculada à parte, só em Vagas); os links levam a busca escolhida (item 50).
34. O seletor de busca e a ordem de Vagas viram menus na barra da lista. O de busca lista só as buscas, com 2 ou mais, como hoje; não há "Todas as buscas", porque encaixe, nota e Destaques são calculados por busca.
35. A barra lateral recolhe pela largura da janela (abaixo de 900px); a lista e o detalhe seguem a largura da coluna de conteúdo: detalhe à direita com 860px ou mais, sobreposto de 640 a 860px e em página própria abaixo de 640px.
36. O Desfazer de Ocultar usa a rota `/mostrar`, que já existe. ⌘Z aciona a faixa visível. Depois do Desfazer, a faixa oferece "Refazer", pela rota `/ocultar`, que já existe, e ⇧⌘Z o aciona. Um nível só, sem histórico de várias ações: desvio consciente da HIG, que pede vários desfazer, porque o painel mostra uma faixa por vez. A faixa sai quando a pessoa fecha, quando outra ação desfazível toma o lugar dela ou quando uma página nova é carregada inteira; as trocas por HTMX dentro de Vagas (aba, busca, ordem, filtro) não a tiram. Descartar uma empresa sugerida e remover uma empresa também rodam sem pergunta, com a faixa de Desfazer, por duas rotas novas: `POST /empresas/sugeridas/{id}/restaurar` volta a sugestão a `pendente`, e `POST /empresas/{id}/restaurar` limpa `removida_em`. Nada é apagado; Refazer usa o `/descartar` e o `/remover` de hoje.
37. Apagar uma busca, remover um site acompanhado e "Esquecer logins" não voltam; os três pedem confirmação num alerta (a pergunta de hoje do "Esquecer logins" vira o alerta). O botão da ação não leva o estilo destrutivo, porque a pessoa escolheu a ação; nenhum botão é o padrão, e "Cancelar" nunca é.
38. Paleta com os comandos que já existem (ir para cada tela, cada grupo de Configurações, "Buscar agora", "Sair", tema, idioma e tamanho do texto), nos dois idiomas, com um botão na barra.
39. Menu de contexto da vaga: Abrir, Abrir no site da vaga, Salvar, Ocultar e Copiar link. Tudo também está no detalhe.
40. Primeira execução: "O que você procura?", "Sites com login (opcional)" e "Segundo plano"; a tela nova entra depois da T241, já com os três passos; "Tudo pronto" não conta como passo. "Pular" grava o país, o segundo plano desligado e a conclusão, cria o atalho do menu no Linux como o "desligar" do passo 2 (DR-37), sem prender em falha, e leva a Vagas; a rota nova é registrada antes da rota genérica dos passos. O assistente não mostra a barra lateral.
41. Janela do modo app: primeiro o Chrome, o Edge ou o Chromium instalados; depois o Chromium do joBot, com um perfil próprio que nunca é o perfil do login (D132); por fim uma aba comum. O Chromium do joBot só é procurado quando o primeiro passo não acha navegador, para o driver do Playwright não subir a cada abertura.
42. Faixas de aviso abaixo da barra de cima, na ordem erro, versão, contas e Desfazer (contas logo depois da versão, como na D139, decisão 23). Erro, versão e Desfazer têm botão de fechar; a de contas não tem (D139, decisão 13). O aviso de erro sai do rodapé.
43. O item Configurações da barra lateral e o ⌘, abrem o último grupo visto, como a HIG pede; sem registro, e sem JavaScript, abrem o grupo Geral.
44. Os ícones entram pelo CSS, e o link da barra lateral fica só com o texto.
45. A cor do trilho dos controles continua num valor fixo, porque entra na conta de contraste.
46. "Descartar" uma vaga é o Ocultar de hoje; "arquivar" não existe no joBot e não entra.
47. Sem espaçamento fixo entre letras; a fonte do sistema ajusta sozinha.
48. O que fica fora do escopo está na seção abaixo.
49. A ADR 0008 não muda: ela já diz "chave manual" para o tema e não diz onde ficam os seletores.
50. A busca escolhida em Vagas fica gravada nas preferências (`busca_escolhida`). A da URL vence; sem ela, vale a gravada; se ela sumiu ou foi desligada, a primeira ativa. Assim as contagens e os links da barra lateral não mudam ao sair de Vagas.
51. Escolher uma vaga põe `vaga=<id>` no endereço de `/vagas`; recarregar ou voltar no navegador abre a mesma vista, com a vaga no detalhe. `/vagas/{id}` continua sendo o link direto.
52. A busca continua por Enter. O formulário da busca fica na barra da lista, e o campo da barra de cima e a ordem entram nele pelo atributo `form`, que funciona sem JavaScript. "Mais filtros" abre abaixo da barra da lista; os avisos de filtro ficam ali, sem botão de fechar; na aba Programas, as páginas acompanhadas ficam numa seção própria abaixo das vagas.
53. A linha de vaga só tem texto, sem botões, porque é um item de lista para o leitor de tela; as ações ficam no detalhe e no menu de contexto. O que a linha mostra é o item 59.
54. A base e a tela de Vagas ficam numa branch longa, que passa pelo CI, e só entram na `dev` com o ok do dono; as outras telas esperam o ok. A base traz o ajuste mínimo das telas de hoje para elas funcionarem na casca nova. A janela do modo app não muda nenhuma tela e entra na `dev` sozinha. Ver também: D157 (conferência por fotos, para confirmar).

**Decisões do dono (terceira rodada, 2026-11-16):**

55. Ritmo da barra: ela segue o andamento real, com uma curva que segura o começo e acelera no fim, como no estudo de Harrison, Amento, Kuznetsov e Bell, "Rethinking the progress bar" (UIST 2007). O tempo total é o real. A barra nunca volta, nunca chega a 100% antes do fim, nunca fica parada sem explicação e nunca mostra mais do que a etapa seguinte permite. É a barra lisa do Mac. A curva exata é proposta da sessão (item 62).
56. Onde: toda espera de mais de 1 s usa o mesmo componente: "Buscar agora", a primeira busca da primeira execução, "Conferir agora" de Contas, "Esquecer logins" e o instalador (no Canvas agora, em Tauri na fase 3). Espera curta não mostra nada. Sem total, a barra é indeterminada e passa a determinada quando o total aparece.
57. Linha da etapa: uma linha com a etapa e a contagem, a espera de cada site com contagem regressiva e "Ver detalhes" com a lista por site. O lado de trás guarda o total planejado, a etapa atual e o estado de cada site.
58. Barra lateral: Sugeridas sob Empresas, só quando há sugestão esperando; Sites depois de Fontes; Configurações por último.
59. Linha de vaga: três linhas de texto, cerca de 64px: título com o encaixe; empresa e local; salário, selos de estado e data. Os botões ficam no detalhe e no menu de contexto.
60. Notificações do navegador e "desconectar um site só" ficam fora deste lote. O dono viu e aceitou.

**Escolhas da sessão, terceira rodada (para confirmar):**

61. A barra é um trilho com `role="progressbar"` e um preenchimento com a largura em `style`, de 6px de altura, sem indicador giratório; a barra indeterminada cobre o começo. O `<progress>` nativo fica de fora porque o CSS não anima o `value` dele, e a barra precisa andar entre uma pergunta e outra. A barra na barra de ferramentas é desvio consciente da HIG, que ali prefere o indicador giratório; o dono pediu o mesmo componente em toda espera. Um token novo, `--trilho-progresso`, deixa o trilho mais escuro no tema escuro, porque o de hoje não chega a 3:1 com o azul de destaque.
62. A curva é `f(p) = p^1,25`, uma função pura testada sozinha. Ela é desvio consciente da HIG, que sugere ritmo uniforme: o dono pediu a curva, que é leve e fica sempre abaixo do andamento real. O valor mostrado sai só do servidor, do andamento, do valor de partida e do tempo desde a última mudança do andamento; por isso é o mesmo em toda página e em toda aba, e nunca volta. Fica em 99% no máximo até a busca fechar; nunca passa de `f` aplicada ao começo da etapa seguinte; parada por 3 s, avança um décimo do que falta até esse limite a cada 2 s. Entre uma pergunta e outra, ela anda numa transição de 2 s.
63. Peso de cada etapa na barra: coleta 80%, detalhes 12%, cotações 3% e encaixe 5%. A etapa que não roda sai, e as outras crescem na mesma proporção. O passo que trata de novo as vagas quando as regras mudam conta dentro da etapa seguinte, sem peso próprio, e tem texto próprio na linha.
64. O componente só aparece depois de 1 s, contado do clique; antes disso, só o resultado, como hoje. O atraso vale só na primeira resposta depois do clique, nunca nas perguntas de 2 s, para a barra não piscar.
65. Os textos da tabela do desenho (seção 5.9), nos catálogos `pt` e `en`, com até dois nomes de site na linha. Três exemplos do dono mudam de forma: "Juntando vagas repetidas" não vira etapa, porque as repetidas se juntam dentro da gravação de cada consulta; "seu perfil" vira "suas buscas", o termo do joBot; "Pronto: 18 vagas novas" vira "Pronto. Vagas novas: {n}.", que não depende de plural.
66. "Ver detalhes" abre uma camada presa ao componente, com uma linha por fonte: nome, estado com ícone e texto, consultas feitas sobre o total e, quando falhou, o motivo. Esc ou clique fora fecha.
67. O leitor de tela anuncia só a troca de etapa e o fim, nunca cada consulta nem cada segundo da espera.
68. O lado de trás guarda o total planejado, a etapa atual com a contagem, o instante da última mudança do andamento e o estado de cada fonte com o fim da espera. O total é a soma das consultas de cada fonte ligada, mais 1 para cada fonte cuja lista de consultas falha; hoje ele não existe, porque cada fonte monta a sua lista só quando começa (`executor.py:269-296`), e o executor muda para montar todas antes. As feitas deixam de contar as linhas "desligada". O cliente HTTP avisa toda espera: a pedida pelo site (429 e 503, com ou sem `Retry-After`) e a nova tentativa depois de erro. O núcleo avisa por funções passadas a ele, sem importar o banco; a gravação é de melhor esforço, por `INSERT ... ON CONFLICT DO UPDATE`, sem apagar nada. O plano decide a migração.
69. A tela "Tudo pronto" da primeira execução mostra "Buscar agora" e o andamento na barra, exceção ao assistente sem barra.
70. O lado de trás do progresso pode entrar na `dev` sozinho, antes da casca nova; o componente visual entra na base.
71. Parar uma busca no meio pelo progresso fica fora deste lote: pede desenho próprio, e o dono não pediu.

**Para confirmar com o dono** (nada aqui trava o plano; tudo vale para construir):

1. As escolhas da sessão que respondem às perguntas P1, P3 e P5 do desenho: o grupo `geral` com o 303 do endereço velho (item 22, era a P1), as rotas de restaurar empresa (item 36, era a P3) e o tema só em Configurações > Geral e na paleta (item 21, era a P5).
2. Os valores marcados como proposta no desenho (item 31), agora também os do progresso: pesos, curva, teto, tempos, medidas e textos.
3. As escolhas do progresso, itens 61 a 71. As que mais mudam o que o dono vê: os três exemplos de texto que mudaram de forma (item 65) e deixar o "Parar" de fora (item 71).

**Fora do escopo:** cor de destaque escolhida pela pessoa; barra lateral pequena e grande e reordenar itens; barra de menus; seleção de várias vagas e ações em lote; botões da janela e casca Tauri, que ficam para a fase 3 (D142). O aviso pela API de notificações do navegador e "desconectar um site só" também ficam de fora, com o aceite do dono em 2026-11-16 (item 60). Parar uma busca no meio também fica (item 71).


**Desenho:** `docs/superpowers/specs/2026-11-15-visual-mac-design.md`.

**Como desfazer:** o dono manda trocar qualquer item. Até o lote ser construído só existe texto (esta D e o desenho); voltar atrás é editá-los. Depois, o visual novo nasce numa branch; enquanto o dono não dá o ok da tela de Vagas, descartar a branch desfaz tudo.

## D144. Escolhas do plano do visual de app do Mac

**Status:** decidido pela sessão, para confirmar com o dono. Nenhuma escolha trava o plano: todas valem para construir, e cada uma tem um teste que a prende.

**Contexto:** o plano `docs/superpowers/plans/2026-11-16-visual-mac.md` (T244 a T268) implementa o desenho `docs/superpowers/specs/2026-11-15-visual-mac-design.md`. Onde o desenho deixa uma escolha aberta, ou onde a base de hoje obriga a um caminho, o plano decidiu. A numeração abaixo é a da tabela "Escolhas deste plano" do plano; quem muda uma escolha muda os dois lugares.

**Escolhas:**

1. **E1, curva do progresso.** A curva e os pesos ficam em `nucleo/andamento.py`, puros; a partida nova é calculada por quem grava, no instante da mudança. Com a etapa parada, o valor chega ao limite da etapa e para nele: depois de uns 690 s o arredondamento do `float` o iguala ao limite. Por isso o teste pede "nunca passa do limite" em toda a faixa e "fica abaixo do limite", estritamente, só até 600 s, o maior `Retry-After` aceito. Teste: `test_avanco_lento_nunca_passa_do_limite`.
2. **E2, esquema do progresso.** Duas tabelas novas, `andamento` e `andamento_fonte`; as de hoje não mudam. Teste: `test_migracao_andamento_*`.
3. **E3, número da migração.** A migração do progresso usa o primeiro número livre na base da T246. Se a `0009_sessao_site.sql` do lote Contas ainda não estiver na `dev`, a do progresso fica com o 0009 e o lote Contas passa ao número seguinte; quem junta depois renomeia o arquivo `.sql` e o `test_migracao_NNNN.py`. O desenho de Contas leva uma nota igual. Teste: `test_migracoes.py`.
4. **E4, ajudantes do painel num módulo de baixo.** A lateral é um global do Jinja e não pode importar `rotas/vagas.py` (que importa `seguranca`, que importa `globais`: import circular). Por isso `relogio_do_painel`, `busca_efetiva`, `utc_do_banco`, `ids_destaques` (era `_ids_destaques`), `config_ou_padrao` (era `_config`) e as duas constantes dos destaques vão para `painel/consultas.py`, que não importa `rotas`, `seguranca` nem `globais`. Quem os importa hoje passa a importar de lá, sem cópia. Testes: `test_consultas_nao_importa_o_painel_de_cima`, `test_rotas_sem_copia_de_relogio`.
5. **E5, paleta depois do ok.** A paleta de comandos entra com as outras telas, depois do ok do dono; o desenho a punha antes.
6. **E6, ajuda.** O ⌘? abre a página inicial da wiki, numa aba nova. Teste: `test_atalho_de_ajuda_abre_a_wiki`.
7. **E7, o que conta como espera.** Só 429, 503 e as novas tentativas; o intervalo normal entre pedidos não. Teste: `test_espera_avisada_*`.
8. **E8, espera vencida.** Fonte "esperando" com o fim já passado aparece como "Lendo". Teste: `test_espera_vencida_mostra_lendo`.
9. **E9, lançador da janela.** O `_rodar` de hoje espera o processo sair e o mataria em 10 s; a janela do modo app abre por um lançador que não espera (`start_new_session`, saídas descartadas), como o `subir_servidor`. O comando `abrir` vai para `cli/abrir.py`, que monta o abridor. Teste: `test_lancador_nao_espera_o_navegador`.
10. **E10, linha de vaga.** Cada linha é o próprio link, `<a role="option" href="/vagas/{id}">`, sem controle dentro: sem JavaScript, o clique abre a página própria. Teste: `test_linha_e_link_sem_js`.
11. **E11, contraste de objeto gráfico.** O par `destaque/trilho-progresso` vai num segundo comentário, `contraste-grafico`, conferido a 3:1; os de texto continuam a 4,5:1. Se o par gráfico reprovar, o trilho muda e o destaque não. Testes: `test_contraste_grafico_minimo`, `test_pares_novos_presentes`.
12. **E12, região viva.** O nó com `role="status"` fica fixo na casca e só o conteúdo dele muda (`innerHTML`), para o leitor de tela anunciar a etapa nova. Testes: `test_regiao_viva_so_com_etapa_nova`, `test_regiao_viva_e_o_mesmo_no`.
13. **E13, foco do alerta.** O alerta abre com o foco no próprio diálogo, nunca num botão; Return logo depois de abrir não apaga nada. Testes: `test_apagar_tem_alerta`, `test_return_ao_abrir_nao_apaga`.
14. **E14, atalho escrito.** O servidor não sabe o sistema de quem vê; manda as duas formas (⌘K e Ctrl+K), e o `app.js` mostra a que vale. Teste: `test_paleta_tem_as_duas_formas_do_atalho`.
15. **E15, progresso do "Esquecer logins".** O componente já vem na página do grupo, como indicador do formulário, e só aparece durante o pedido, depois de 1 s. Teste: `test_esquecer_mostra_o_componente_indeterminado`.
16. **E16, busca escolhida.** Só um id válido de uma busca ativa grava a escolha; a busca da URL continua valendo na página só por existir, como hoje. Testes: `test_busca_invalida_nao_grava`, `test_busca_desligada_na_url_continua_valendo`.
17. **E17, botões de ação sempre visíveis.** A fileira de botões do assistente, do sheet de correção e do alerta fica presa no pé e só o conteúdo rola. Veio do Canvas do instalador, onde a barra sumia com tudo marcado. Testes: `test_botoes_visiveis_com_janela_baixa` (primeira execução) e `test_sheet_correcao_botoes_visiveis`.
18. **Nomes propostos.** Ícones que o mapa do desenho não cobre (grupos de Configurações, estado vazio e Saiu) e os textos novos marcados "proposta" no plano. Teste: `test_icones_do_mapa_existem`.

**Como desfazer:** até o lote ser construído só existe texto; voltar atrás é editar o plano e esta D. Depois, cada escolha tem o seu teste: mudar a escolha é mudar o teste e o código da tarefa responsável por ela.

## D145. Gmail por senha de app

**Status:** os itens do dono (Q1 a Q4 e R1 a R3) foram decididos em 2026-11-16. As escolhas da sessão estão em "Para confirmar" e valem para construir.

**Contexto:** a ADR [0013](docs/decisions/0013-gmail-e-avisos.md) pedia que cada pessoa criasse o próprio projeto no Google Cloud para o joBot ler o Gmail por OAuth. É trabalhoso, e muita gente não consegue. O registro da troca é a ADR [0024](docs/decisions/0024-gmail-por-senha-de-app.md).

**Decisões do dono:**

- Q1. IMAP com senha de app substitui o projeto no Google Cloud por pessoa da ADR 0013.
- Q2. Guardar no cofre local a senha de app colada pela pessoa é permitido. O joBot continua sem digitar a senha da conta Google.
- Q3. O projeto por pessoa fica só como tarefa futura, para quem não consegue senha de app.
- Q4. O cliente OAuth único e verificado fica descartado por ora: a revisão de escopo restrito leva semanas e pede avaliação de segurança anual (CASA); não confirmamos se um app que só guarda os dados no aparelho fica isento. Um cliente não verificado tem teto de 100 usuários no total.
- R1. O tutorial é uma página da wiki, em português e em inglês, com os dois links oficiais do Google, no `_Sidebar` e no FAQ. O painel linka para ela.
- R2. O cartão do Gmail entra na aba Contas já no lote de Contas: endereço e senha de app, "Conferir agora" com login só de leitura, estados "Conectado" e "Precisa entrar de novo". A leitura dos e-mails continua na fase 6.
- R3. Só contas Google (Gmail).

**Para confirmar com o dono:**

1. Os nomes `gmail_conta` e `gmail_senha_de_app` no cofre.
2. O tutorial sem imagens por ora, só texto e links. As imagens dos passos ficam para uma tarefa futura, porque exigiriam capturar telas da conta Google.
3. Os estados do cartão são os dos sites com login da D139: "Conectado", "Precisa entrar de novo", "Nunca entrou" e "Não deu para conferir". Recusa de login (`AUTHENTICATIONFAILED`) vira "Precisa entrar de novo"; falha de rede vira "Não deu para conferir".
4. O mínimo de 10 minutos do "Conferir agora" (D139) vale também para o Gmail.
5. (decisão da sessão) O Gmail segue as mesmas regras de faixa do topo e de aviso `notify-send` dos sites (seções 5.1 e 5.6 do desenho de Contas): só abrem depois de uma conferência que deu certo (`entrou_em` preenchido). Ao salvar, o painel testa o login antes de guardar: senha recusada não é guardada, o cartão fica em "Nunca entrou" e a mensagem aparece embaixo do campo.

**Como desfazer:** o dono manda trocar qualquer item. Voltar à ADR 0013 é tirar o cartão do Gmail e a nota da ADR 0013, e apagar a senha de app na conta Google.

## D146. Escolhas do plano do lote Contas

**Status:** para confirmar. O plano `docs/superpowers/plans/2026-11-16-contas.md` (T269 a T279) segue estas escolhas; mudar uma muda a tarefa responsável antes de ela começar.

**Contexto:** o plano do lote Contas junta o desenho `2026-11-15-contas-design.md` (com o cartão do Gmail, 5.7.1), a D139, a D140 (item 9: o lado de trás corre em paralelo ao visual; a aba e a faixa esperam a base visual nova), a D145 e a ADR 0024. Ao detalhar as tarefas, apareceram escolhas que o desenho não fechava. O dono perguntou se precisa fazer alguma coisa ou dar algum acesso: para construir e testar o lote, não precisa de nada (os testes rodam com a rede bloqueada, o IMAP e o navegador são falsos e o CI roda no Actions). O que fica com ele está no fim desta dúvida.

**Escolhas:**

1. **E1, duas tabelas.** A migração `0010_sessao_site.sql` cria `sessao_site` (chave estrangeira para `fonte`) e `sessao_conta` (só `'gmail'`, motivos `sem_rede`, `bloqueio`, `erro` e `esquecido`). O Gmail não é fonte; pôr uma linha dele em `fonte` sujaria as telas de fontes. Teste: `test_check_conta_so_gmail`.
2. **E2, regra pura da queda.** `nucleo/contas.proxima_sessao` decide o `entrou_em`, o `avisado_em` e se a gravação abriu a queda; o banco grava sob `BEGIN IMMEDIATE` com `ON CONFLICT DO UPDATE`. Troca a "instrução única com `COALESCE`" do desenho por uma regra testável sem banco. Teste: `test_queda_abre_uma_vez`, `test_devolve_abriu_uma_vez`.
3. **E3, mapa num lugar só.** `navegador/sessao.py` traz o mapa da entrada e da falha para o estado e o registro com aviso; o título do aviso (`TITULO_AVISO`) muda para lá e `_fechou` vira `fechou`. Teste: `test_mapa_da_entrada`, `test_titulo_so_em_sessao`.
4. **E4, falha na entrada.** Na leitura agendada, a falha antes de ler a entrada do site grava `sem_rede` (erro do Playwright) ou `erro`; exceção antes de abrir a aba não grava estado. Teste: `test_erro_de_rede_na_entrada_grava_sem_rede`.
5. **E5, janela fechada.** Se a pessoa fecha a janela no meio do "Conferir agora", nada é gravado. Teste: `test_fechar_a_janela_devolve_none`.
6. **E6, Gmail no núcleo.** `nucleo/gmail.py` com `imaplib` da biblioteca padrão e o abridor injetado (sem dependência nova); o painel pega o abridor por `imap_do_painel`. Nomes no cofre: `gmail_conta` e `gmail_senha_de_app`. Teste: `test_abrir_imap_ssl_usa_host_porta_prazo`.
7. **E7, Gmail na própria resposta.** A conferência do Gmail roda dentro do pedido, com prazo de 20 s no socket e 30 s na rota (estourou, "Sem internet"), sem trava nem polling; o botão fica desabilitado durante o pedido. Teste: `test_prazo_estourado_vira_sem_rede`.
8. **E8, como o IMAP vira estado.** `AUTHENTICATIONFAILED` vira "Precisa entrar de novo"; outro erro de login vira "Não deu para conferir" (`bloqueio`); rede, SSL e prazo viram `sem_rede`; caixa que não abre vira `erro`. Teste: `test_authenticationfailed_vira_recusada`, `test_outro_erro_de_login_vira_bloqueio`.
9. **E9, senha e endereço.** A senha de app perde os espaços, precisa ter 16 letras e é guardada em minúsculas; fora disso o joBot recusa sem falar com o Google. O endereço aceita qualquer domínio (conta Google com domínio próprio também), só com caracteres ASCII comuns e sem `"`, parênteses, chaves, `%`, `*` e `\`, porque o `imaplib` manda o endereço ao Google sem aspas. Teste: `test_salvar_senha_torta_nao_chama_o_google`, `test_validar_endereco_recusa`.
10. **E10, só guarda o que entrou.** "Salvar e conferir" não tem o intervalo de 10 minutos; só guarda com o login aceito; se o cofre falha no meio, apaga as duas partes. Limite: herda o atalho do `no_cofre` de Serviços; se o cofre do sistema travar e estourar o prazo, a gravação atrasada ainda pode acontecer depois do apagar e deixar meia credencial, que some na próxima gravação ou no "Remover". O cartão avisa que a senha de app dá acesso a todo o e-mail (o joBot só abre a caixa de entrada para leitura), como a seção de privacidade do README. Teste: `test_salvar_recusada_nao_guarda`, `test_cofre_que_falha_nao_deixa_meia_credencial`.
11. **E11, Gmail sem aviso no computador neste lote.** Sem leitura de e-mails (fase 6), o Gmail só é conferido na tela; por isso a queda dele aparece na faixa do topo e no cartão, mas não gera `notify-send`. Isso detalha o item 5 da D145: a regra do aviso é a dos sites, e conferência na tela nunca avisa no computador. O aviso do Gmail chega com a conferência automática, na fase 6. Teste: `test_conferir_recusada_abre_queda_sem_aviso`.
12. **E12, "Remover" no cartão do Gmail.** Com o alerta de confirmação, apaga a senha e o endereço do cofre e volta a "Nunca entrou". "Esquecer logins" não mexe no Gmail. Teste: `test_remover_apaga_e_volta_a_nunca_entrou`, `test_esquecer_nao_mexe_no_gmail`.
13. **E13, aba Contas sempre visível.** Sem site com login, a aba mostra só o cartão do Gmail. Mostrar não libera as ações dos sites: sem leitor, gravar os horários, ligar e desligar, fazer login e esquecer continuam dando 404. Teste: `test_sem_leitor_aba_visivel_so_gmail`, `test_sem_leitor_horarios_404` (com leitor, exatamente 303), e o `test_sem_leitor_rotas_de_login_e_esquecer_dao_404` que já existe, mantido como está para o esquecer e o login. Em `gravar`, o `_grupo_valido` genérico fica; o `_exige_leitor` entra a mais nos horários.
14. **E14, "contas" na faixa.** Com mais de uma queda, a faixa diz "Sua sessão caiu em {quantos} contas. Entre de novo em Configurações › Contas.", porque o Gmail entra na conta; só o Gmail em queda diz "Sua sessão no Gmail caiu. Entre de novo em Configurações › Contas.". Nas duas a frase não promete "voltar a ler as vagas", porque neste lote o joBot não lê nada do Gmail. Um site só fica com o texto do desenho. O Gmail vem depois dos sites. Teste: `test_varios_conta_o_gmail`, `test_gmail_entra_na_faixa`.
15. **E15, selo sem ícone.** O estado aparece em texto com borda e fundo próprios, sem ícone novo. Teste: `test_selo_por_estado`.
16. **E16, ordem e publicação.** O lado de trás (T269 a T274) entra na `dev` em paralelo ao visual; as telas (T275 a T278) depois do portão T258, da T262, da T263 e da T266 (estas duas mexem nos mesmos arquivos da aba). O aviso no computador da T272 cita a aba que existe hoje ("Configurações › Sites com login"), e a T275 troca a frase para "Contas" junto com a aba; assim a `dev` pode ir para a `main` a qualquer hora. Alternativa: a T272 já citar "Contas" e a `dev` não ir para a `main` até a T275, o que pode segurar uma publicação enquanto o portão T258 espera o dono. Recomendo a primeira. Teste: `test_registrar_avisa_uma_vez_por_queda`, `test_frase_da_queda_cita_contas`.
17. **E17, cartão trocado inteiro.** No fim do "Fazer login agora" e do "Conferir agora" o cartão `#conta-{chave}` é trocado inteiro e a faixa se atualiza pelo evento `contas-mudou`; "Esquecer logins" devolve os cartões juntos. Teste: `test_login_final_com_gatilho`, `test_esquecer_grava_esquecido_e_devolve_cartoes`.
18. **E18, `leitores_do_painel` em `painel/ambiente.py`.** Muda de lugar, sem cópia, porque três rotas usam. Teste: `test_leitores_do_painel_definido_uma_vez`.
19. **E19, hora no cartão.** "Nunca entrou" nunca mostra hora; "Desligado" mostra a última, se não foi esquecida; data ilegível não mostra nada. Teste: `test_hora_visivel`, `test_conferido_ilegivel_vazio`.
20. **E20, login com erro não grava.** "Fazer login agora" que termina em exceção não grava estado, porque não se sabe se a pessoa entrou. Teste: `test_login_com_erro_nao_grava`.
21. **E21, endereço das rotas do Gmail.** As rotas do cartão do Gmail ficam em `/configuracoes/gmail/...`, fora de `/configuracoes/contas/{chave}/...`. O painel inclui as rotas em ordem alfabética dos arquivos, e o "Conferir agora" dos sites (`/configuracoes/contas/{chave}/conferir`) pegaria o do Gmail e responderia 404. Alternativa: limitar o `{chave}` dos sites às chaves que terminam em `_logado`; prende a rota a um costume de nome e não protege rotas futuras. Recomendo a primeira. Teste: `test_rotas_do_gmail_casam_primeiro`.
22. **E22, nota de privacidade do README (para confirmar).** A nota do topo da seção de privacidade dos dois README diz que as regras do Gmail e do cofre de senhas são de fases futuras; com o lote, o cartão do Gmail já guarda a senha de app no cofre e abre a caixa só para leitura. A T279 troca a nota: o Gmail sai da lista do futuro, com a frase de que o cartão já vale e a leitura dos e-mails vem na fase 6; "cofre de senhas" sai (o cofre já guarda a chave do 2Captcha) e "Telegram" entra, para o token do Telegram continuar marcado como futuro. Alternativa: deixar a nota como está e só registrar. Recomendo trocar. Teste: `test_nota_de_privacidade_sem_gmail_futuro`.
23. **E23, anúncio do "Conferir agora".** Escolha do redator na T277: o anúncio do resultado usa a chave `configuracoes.contas.conferido_resultado` ("{site}: {estado}.") e o motivo vem depois como frase própria. Para desfazer, juntar a frase numa chave só.

**O que o dono faz:** nada para o lote ser construído, e nenhum acesso. Fica com ele: (a) confirmar estas escolhas, com atenção a E9, E11, E12, E13, E14, E16, E21 e E22; (b) os itens "para confirmar" que já estavam abertos na D139 e na D145; (c) o ok do portão T258 do visual, que libera as telas; (d) opcional, depois da T278 na `dev`: no próprio computador, criar uma senha de app do Gmail pela página da wiki e colar no cartão do Gmail do painel (nunca no chat), e apertar "Conferir agora" no cartão do LinkedIn com a sessão real.

**Como desfazer:** o dono manda trocar qualquer item; a tarefa responsável muda antes de começar (ou ganha uma `Tn` nova, se já entrou na `dev`). Tirar o Gmail do lote é tirar a T274 e a T278, a tabela `sessao_conta` da `0010` e as linhas do Gmail da T276.

## D147. Panorama e fila de candidaturas (0.3.0)

**Status:** para confirmar. O desenho `docs/superpowers/specs/2026-11-16-panorama-e-fila-design.md` segue estas escolhas. A lista completa, com os detalhes, está na seção 11 dele (D147.1 a D147.31).

**Contexto:** o dono decidiu na D138 que a 0.3.0 traz a tela Panorama (item 2) e a fila de candidaturas completa: link de candidatura por e-mail, a pergunta "Você se candidatou?" quando a pessoa volta ao painel e as datas de cada passo (item 3). A ordem é depois do lote Contas (item 9). A candidatura automática segue recusada (item 1, Q3): o joBot nunca envia nada (ADR 0001). O dono delegou as escolhas de desenho, e a sessão decidiu pela recomendação. O dono perguntou se precisa fazer alguma coisa ou dar algum acesso: para desenhar, construir e testar este lote, não precisa de nada. Os testes rodam com a rede bloqueada, o e-mail dos testes usa domínio reservado e o CI roda no Actions.

**Escolhas:**

1. (D147.1 e D147.2) **Panorama na lateral, `/` continua em Vagas.** `GET /panorama` é o primeiro item da lateral, acima de "Vagas" (en "Overview"). A tela inicial não muda. Alternativa: o Panorama como início, o que é uma linha em `raiz`. Recomendo manter Vagas.
2. (D147.4) **Quatro grupos fixos.** Hoje (Novas, Fecham logo, Salvas, Candidatei, Todas, cada número com link), Candidaturas (contagem por passo, "Para responder" e salvas que fecham em até 7 dias), A busca (última e próxima busca, fontes com problema, contas em queda) e O que aparece (encaixe, modalidade, área e fonte). Os números saem das mesmas funções da tela de Vagas, para nunca divergirem. A tela segue a busca escolhida. O estado vazio é "nenhuma vaga no banco", não "aba Todas com zero" (a aba Todas esconde fechadas e ocultas, e quem só tem candidaturas antigas veria uma tela vazia falsa). "Salvas que fecham" deixa de fora a salva que já fechou na fonte.
3. (D147.10) **Gráfico sem biblioteca.** As barras são SVG em linha, `<rect width="%">`, porque a CSP recusa o atributo `style`. A barra é decorativa: o número fica no texto, e cada bloco tem uma frase de resumo.
4. (D147.12) **Datas dos passos sem esquema novo.** Saem do histórico `evento`, que já existe: vale o último evento que levou a vaga a cada passo. Passo pulado não mostra data. De Oferta e Recusada, que valem o mesmo degrau, só o passo atual aparece. O detalhe ganha uma "Linha do tempo". As datas não se editam nesta versão.
5. (D147.15) **Tabela nova `candidatura` na `0011_candidatura.sql` (R4, esquema).** Guarda `vaga_id`, `abriu_em` e `perguntar`, com gravação `ON CONFLICT` e um gatilho que impede apagar. Alternativas: uma ação nova em `evento`, que exige reconstruir a tabela e os gatilhos; ou nada no banco, e a pergunta não existe. Recomendo a tabela. O número segue a regra da D144.E3.
6. (D147.16) **Registro do clique por `fetch` com `keepalive` no `app.js` (R4, segurança).** O link de "Candidatar-se" continua um link normal. O `app.js` manda um POST com o token CSRF ao clicar. Sem JavaScript, o clique não é registrado, e a pessoa usa "Me candidatei". Alternativa: um `GET` local que registra e redireciona; funciona sem JavaScript, mas é um GET com efeito, que outra página pode disparar. Recomendo o `fetch`.
7. (D147.18) **A pergunta numa faixa, nunca num alerta.** A faixa fica em `#aviso-candidatura`, depois de Contas e antes de Desfazer, e aparece ao carregar a página e quando a janela volta ao foco. Ela mostra a mais recente, com "Sim, me candidatei" e "Ainda não", e o link "e mais {n}" leva ao Panorama. Não tem botão de fechar. "Sim" muda o status para Candidatei e oferece "Desfazer", que tem rota própria e devolve a faixa (a rota de status devolve o cartão da lista, que não serve ali). Quando o que está à vista não mudou, a faixa não é refeita (resposta 204), para o leitor de tela não repetir a pergunta a cada volta à janela. A faixa não escuta o evento `candidatura-mudou`: no HTMX fixado ele dispara antes da troca, e a faixa pediria de novo com o estado velho, apagando o "Desfazer"; quem dispara o evento já troca a faixa.
8. (D147.20) **Data do passo Candidatei = hora da resposta.** A hora em que a pessoa abriu a candidatura aparece à parte na linha do tempo. Alternativa: usar a hora da abertura, que grava um evento com data anterior a outros.
9. (D147.21) **"Ainda não" não pergunta de novo, e a pergunta não expira.** Abrir a candidatura de novo pergunta de novo. Marcar Candidatei por outro caminho tira a vaga da pergunta.
10. (D147.22) **E-mail achado na descrição, na hora de mostrar.** Uma função pura no `nucleo` procura um endereço na mesma frase ou na mesma linha de uma palavra de candidatura (pt, en, es) e recusa `noreply`. O endereço passa por uma lista fechada de caracteres (sem `?`, `&`, `=`, `%`, `#`, `/` nem espaço), para nada do texto virar parâmetro do `mailto:`. O endereço não é guardado.
11. (D147.23 e D147.24) **Botões do e-mail.** O link http próprio continua o principal, e o e-mail entra como secundário; sem link próprio, o e-mail vira o principal. O `mailto:` leva o título no assunto e não tem corpo. Isso é uma exceção à regra 14.3 da fase 1 (link de terceiro só em http ou https, e nunca link da descrição): só `mailto:`, montado pelo joBot com o endereço validado. A exceção entra como nota na regra 14.3 e na ADR 0014. O endereço fica à vista, com "Copiar endereço", e uma linha diz que o joBot não envia nada.
12. (D147.25) **`mailto:` mandado pela fonte fica fora (R4, contrato dos coletores).** Aceitar esse link muda `confere_http` e `VagaColetada`. Opções: deixar fora agora; mais tarde, um campo próprio `email_candidatura` numa `Tn`; ou afrouxar `confere_http`, o que não recomendo. Recomendo deixar fora neste lote.
13. (D147.27) **Ordem.** O lote vem depois de Contas (T269 a T279) e do portão T258 do visual. O lado de trás pode entrar na `dev` antes. As telas entram juntas e fecham a 0.3.0.
14. (D147.28) **Privacidade.** A tabela `candidatura` fica só no banco local. README e wiki ganham uma linha sobre isso.
15. (D147.29) **A vaga na tela se atualiza depois da faixa (para confirmar).** Quem responde "Sim" com o detalhe da vaga aberto via o status velho, e o "Desfazer" velho do detalhe levaria a vaga para onde ela não estava. As rotas da faixa mandam também um evento da própria vaga (`vaga-mudou-{id}`); o bloco de status e a linha do tempo do detalhe pedem de novo a página e ficam só com eles mesmos, e o cartão da lista pede uma rota nova pequena, `GET /vagas/{id}/cartao`. Evento por vaga porque o painel não permite filtro de evento (`allowEval: false`). Alternativa: a resposta da faixa levar o bloco por `hx-swap-oob`, o que dá mais código e erro quando o bloco não está na página. Recomendo o evento. Teste: `test_tela_detalhe_atualiza_depois_da_faixa`, `test_cartao_get_devolve_corpo_sem_foco`.
16. (D147.30) **"Todas as fontes funcionaram" só quando é verdade (para confirmar).** A frase aparece só com busca completa e toda fonte ligada em `ok` ou `sem_mudanca`, e diz "da última vez que rodaram", porque o estado de cada fonte vem da última execução de qualquer tipo. Fonte no limite ou que nunca rodou não conta como problema, mas tira a frase; sem busca completa, a linha some. Alternativa: contar `no_limite` e `sem_execucao` como problema. Recomendo assim, como a tela de Fontes. Teste: `test_sem_busca_completa_sem_frase_de_fontes_ok`, `test_fonte_no_limite_ou_sem_execucao_sem_frase`.
17. (D147.31) **O `voltar` da faixa e o caminho sem JavaScript (para confirmar).** A faixa só aparece com JavaScript, o que é esperado. O `voltar` dos botões dela sai do endereço da página (`HX-Current-URL`), pela mesma regra do `de_volta`, numa função só; "Para responder" vem pronta do servidor com `voltar=/panorama`. O Desfazer não recebe do formulário o status para onde voltar: o servidor lê o último evento de status da vaga. Teste: `test_voltar_sai_do_hx_current_url`, `test_desfazer_ignora_campo_para`.

**O que o dono faz:** nada para construir, e nenhum acesso. Fica com ele: (a) confirmar estas escolhas, com atenção a 1, 5, 6, 8, 11 (a exceção à regra 14.3), 12, 15 e 16; (b) o ok do portão T258 do visual, que já libera as telas de Contas e também libera estas; (c) opcional, com o lote na `dev`: abrir uma candidatura real, voltar ao painel e conferir se a pergunta incomoda ou ajuda.

**Como desfazer:** até o lote ser construído, só existe texto: basta editar o desenho e esta D. Depois, cada escolha tem o seu teste (seção 7 do desenho). Tirar a pergunta, antes de o lote sair numa versão, é tirar a 0011, a faixa e o `fetch` do `app.js`. Depois de publicado, a 0011 já foi aplicada no banco de quem atualizou, e a versão do esquema conta os `.sql`: apagar o arquivo deixa o esquema e a versão fora de acordo. Então tirar a pergunta é tirar a faixa, as rotas e o `fetch`, e deixar a tabela `candidatura` sem uso; apagar a tabela, se for preciso, é uma migração nova. Nos dois casos, nenhum dado da vaga se perde. Tirar o e-mail é tirar a função do `nucleo` e o botão.

## D148. Escolhas do plano do lote Panorama e fila

**Status:** para confirmar. O plano `docs/superpowers/plans/2026-11-16-panorama-e-fila.md` (T280 a T291) segue estas escolhas; mudar uma muda a tarefa responsável antes de ela começar.

**Contexto:** o plano quebra o desenho da D147 em doze tarefas e fecha a versão 0.3.0. As escolhas abaixo são de como construir, não de o que construir: o que a pessoa vê segue a D147 e as recomendações P1 a P5 do desenho. O dono perguntou se precisa fazer alguma coisa ou dar algum acesso: para construir e testar este lote, não precisa de nada.

**Escolhas:**

1. **E1, divisão e ordem.** O lado de trás (T280 função do e-mail, T281 migração e gravação, T282 consultas) pode entrar na `dev` antes do portão T258, num `lote/panorama-dados`, porque não muda tela. A T283 (mudança de lugar das consultas) espera a T261 e a T276. As telas (T284 a T289) entram juntas num `lote/panorama-tela`; documentos (T290) e versão (T291) por último. Teste: (ordem).
2. **E2, testes de banco em `tests/integracao/`.** O desenho listava alguns em `tests/unidade/`; ficam em `integracao/`, como `test_acoes.py` e `test_leitura.py`. A migração tem arquivo próprio, `test_migracao_0011.py`, que lê só a 0011. Teste: `test_candidatura_sem_delete`, `test_perguntar_so_0_ou_1`.
3. **E3, número da migração.** `0011` vale com a 0009 (T246) e a 0010 (T270) já na `dev`; se a ordem mudar, vale a D144.E3 (quem junta depois renomeia). Teste: `test_migracoes.py`.
4. **E4, consultas de outras telas mudam de lugar, sem cópia.** Os cartões de saúde de `rotas/fontes.py` vão para um módulo novo, `painel/saude_das_fontes.py` (`_cartoes` vira `cartoes`), com a próxima busca separada em `proxima_busca(con, agora)`. `contas_em_queda` vai de `rotas/aviso_contas.py` para `painel/consultas.py`. Alternativa: o Panorama importar de `rotas/`, o que a lição «Painel» proíbe. Teste: `test_definidos_uma_vez`, `test_proxima_igual_a_de_fontes`.
5. **E5, `DEGRAU` público.** O `_DEGRAU` de `banco/acoes.py` vira `DEGRAU`, importado por `datas_dos_passos`, sem cópia; se der import circular, muda para `leitura.py`. Teste: `test_degrau_definido_uma_vez`.
6. **E6, o que as funções do banco devolvem.** `responder_candidatura` devolve o status de antes quando o Sim trocou o status (a confirmação com Desfazer só aparece nesse caso), senão `None`. `perguntas_pendentes(con, limite)` devolve `(lista, total)` com `Pergunta`. A linha do tempo lê `abertura_da_candidatura(con, vaga_id)`. Teste: `test_responder_sim_devolve_o_status_de_antes`, `test_abertura_da_candidatura`.
7. **E7, módulos de rota.** As ações sob `/vagas/` em `rotas/candidatura.py` (vem antes de `detalhe.py` na ordem alfabética); a faixa em `rotas/aviso_candidatura.py`; o Panorama em `rotas/panorama.py`. Teste: `test_rotas_de_candidatura_casam_antes_do_detalhe`.
8. **E8, uma macro para a pergunta.** `templates/candidatura/_pergunta.html`, com prefixo de id (`faixa` ou `responder`), para a faixa e "Para responder" não repetirem `id`. Teste: `test_ids_unicos_com_faixa_e_para_responder`.
9. **E9, sem JavaScript.** As respostas e o Desfazer voltam pelo `de_volta(voltar)`, como as outras ações; nunca pelo `Referer`. O `voltar` de "Para responder" é `/panorama`; o da faixa sai do `HX-Current-URL` (E21). Sem JavaScript a faixa não aparece. Teste: `test_resposta_sem_js_303`, `test_desfazer_sem_js_303`, `test_voltar_sai_do_hx_current_url`.
10. **E10, só o clique normal registra.** O botão do meio do mouse e o "abrir em nova aba" do menu não registram a abertura; a pessoa usa "Me candidatei". Alternativa: escutar também `auxclick`. Teste: `test_tela_clique_registra`.
11. **E11, largura das barras.** `pct(n, maior)` em `rotas/panorama.py`, com piso de 2 quando `n > 0`. Teste: `test_pct_das_barras`.
12. **E12, medidas e ícones.** Número de 28px, barra de 8px, grade de 4px; ícones `layout-dashboard` e `circle-help` (ou `gauge` e `help-circle`, se a versão fixada do Lucide não tiver). Teste: `test_estaticos.py`, `test_contraste.py`.
13. **E13, os 300 ms medidos à mão.** Uma medição na T288 com o banco de `scripts/medir_filtros.py`, anotada no resumo; passou de 300 ms, abre uma `Tn` (cache fica fora deste lote). Não vira teste, porque o tempo no CI depende da máquina. Teste: (resumo da T288).
14. **E14, a 0.3.0 espera a fase 2 concluída.** A ADR 0017 diz "depois da fase 2 sai a versão 0.3.0"; a T291 só começa com a fase 2 concluída na `dev`, inclusive o resto do lote do primeiro site que o plano do LinkedIn põe como condição da 0.3.0: T240, T241 e os itens 1 e 2 (`CLAUDE.md` do projeto), 4 (ADR 0006), 6 (ADR 0022) e 7 (ADR 0017) de "Espera o dono" do plano `2026-11-15-fase-2-primeiro-site-resto.md`, cada um com o ok do dono. Na ADR 0017 a T291 aplica o item 7 (Status da fase 2 e linha "Atualizada") e, pela «Troca de versão», atualiza a frase de histórico do Contexto, que hoje para na 0.2.1: "Hoje as fases 1 e 2 estão concluídas, as versões 0.1.0, 0.1.1, 0.2.0, 0.2.1 e 0.3.0 já saíram (...; a 0.3.0 traz o navegador com login, o LinkedIn, o visual novo do painel, a aba Contas, o Panorama e a fila de candidaturas) e as outras fases estão planejadas", sem apagar as versões antigas; o texto inteiro está na E14 do plano. Para confirmar junto do ok do item 7, porque mexe em ADR aceita. O resumo da 0.3.0 no CHANGELOG cobre tudo o que está em "Não lançado" (fase 2 com o LinkedIn, visual novo, Contas, Panorama e fila), e o teste confere "LinkedIn" e "Panorama" na linha de resumo. Alternativa: soltar a 0.3.0 antes, mudando a ADR 0017 primeiro. Recomendo seguir a ADR. Teste: `test_changelog_fecha_a_0_3_0`.
15. **E15, o link "e mais {n}".** Leva a `/panorama#para-responder`; por isso a T285 e a T288 entram juntas no `lote/panorama-tela`, e o link nunca dá 404 na `dev`. Teste: `test_e_mais_n_leva_ao_panorama`.
16. **E16, datas no dia local.** `data_curta` e `data_completa` (`painel/formatos.py`) não convertem o fuso, e o relógio grava em UTC: uma ação às 22:30 de Brasília sairia com o dia seguinte. A T283 corrige uma vez, na função compartilhada (instante com fuso passa por `.astimezone()`; data sem hora não muda). Efeito colateral bom: o dia em Sites, Sugeridas e Programas, que hoje sai em UTC, passa a sair local. Alternativa: converter em cada chamador, como o `_faixa` do detalhe, o que deixa o erro voltar no próximo. Recomendo a função compartilhada. Teste: `test_instante_vira_dia_local`.
17. **E17, vaga oculta.** "Para responder" e a faixa deixam fora a vaga ocultada à mão (`oculta_manual <> 1`); a que a pessoa mandou "mostrar mesmo assim" (-1) continua, como o `_OCULTA` da lista já faz; a escondida só por regra da busca continua, porque a regra depende da busca. "Salvas que fecham" segue a aba Salvas, que mostra a salva oculta. Alternativa: mostrar tudo, ou esconder também nas salvas. Recomendo assim. Teste: `test_pendentes_sem_oculta_a_mao`.
18. **E18, o Desfazer decide no servidor.** `desfazer_candidatura` não recebe do formulário o status para onde voltar: lê o último evento de status da vaga (com `para` não nulo, para o `desfez` de "trazer de volta" uma vaga oculta não contar) e só desfaz um `mudou_status` para `candidatei` vindo de `nova` ou `salva`. Uma confirmação velha ou um formulário mexido não levam a vaga a um status que ela não teve. Alternativa: receber `para` e validar. Recomendo o servidor. Teste: `test_desfazer_volta_ao_de_do_ultimo_evento`, `test_desfazer_depois_de_desfez_nao_muda`, `test_desfazer_ignora_desfez_da_ocultacao`.
19. **E19, a próxima busca em outro dia.** A chave `panorama.busca.proxima` do desenho só tem a hora ("por volta das {hora}"), e a busca roda a cada 3 horas, então a próxima pode cair no dia seguinte. No mesmo dia, a T288 usa a chave do desenho; em outro dia, uma chave nova, `panorama.busca.proxima_dia` ("Próxima busca automática em {dia}, por volta das {hora}." / "Next automatic search on {dia}, around {hora}."). Mudança de texto do desenho. Alternativa: uma chave só, sempre com o dia. Recomendo as duas chaves, que mantêm o texto do desenho no caso comum. Teste: `test_ultima_e_proxima_busca`, `test_proxima_no_mesmo_dia_so_hora`.
20. **E20, a vaga na tela depois da faixa (para confirmar).** As rotas da faixa mandam `HX-Trigger: candidatura-mudou, vaga-mudou-{id}`. O detalhe (T286) envolve o status e a linha do tempo num bloco que pede de novo o próprio `GET /vagas/{id}` com `hx-select`; o cartão da lista (T285) pede `GET /vagas/{id}/cartao`, rota nova em `rotas/vagas.py` que usa o mesmo `_resposta` com um parâmetro novo, `foco`, valendo `False`. A T286 passa a depender da T285. Alternativa: `hx-swap-oob` na resposta da faixa. Recomendo o evento por vaga, que tem menos código e não corre contra o `HX-Trigger` disparado antes da troca. Teste: `test_cartao_get_devolve_corpo_sem_foco`, `test_detalhe_estado_escuta_a_vaga`, `test_tela_detalhe_atualiza_depois_da_faixa`.
21. **E21, o `voltar` da faixa (para confirmar).** A regra do `de_volta` sai, sem mudar, para `caminho_do_painel` em `painel/seguranca.py`, e a rota da faixa passa por ela o caminho e a consulta do `HX-Current-URL`; sem o cabeçalho, `/`. Alternativa: `/` fixo, porque a faixa só existe com JavaScript. Recomendo o `HX-Current-URL`. Teste: `test_voltar_sai_do_hx_current_url`.

**O que o dono faz:** nada para construir e testar, e nenhum acesso: os testes rodam com a rede bloqueada, o link de candidatura dos testes aponta para um servidor local, o CI roda no Actions do repositório público, e o PR da `dev` para a `main` já foi autorizado em 2026-11-15. Fica com ele: (a) confirmar estas escolhas, com atenção a E4, E10, E13, E14, E16, E17, E19 e E20; (b) os itens da D147 e as perguntas P1 a P5 do desenho, que o plano segue pela recomendação; (c) o ok do portão T258 do visual, que libera as telas; (d) dizer quando a fase 2 está concluída, ou mandar mudar a ADR 0017, para a 0.3.0 sair, e dar o ok dos itens 1, 2, 4, 6 e 7 de "Espera o dono" do plano do primeiro site (`CLAUDE.md`, ADRs 0006, 0022 e 0017) e da frase nova do Contexto da ADR 0017 (E14); (e) opcional, com o lote na `dev`: clicar em "Candidatar-se" numa vaga real, voltar ao painel e responder.

**Como desfazer:** até a tarefa começar, basta editar o plano e esta D. Depois, cada escolha tem o seu teste; trocar uma é uma `Tn` nova. Tirar a E4 é desfazer a mudança de lugar da T283 (os nomes voltam para as rotas, e o Panorama perde A busca).

## D149. CI em paralelo

**Status:** para confirmar. O dono pediu em 2026-11-16 uma CI em paralelo, quebrada no máximo e a mais rápida possível; a sessão decidiu pela recomendação, com o dono fora.

**Contexto:** o CI rodava a bateria inteira num job só e levava cerca de 10 minutos por rodada. Agora `.github/workflows/ci.yml` divide a bateria em jobs paralelos. Cada job recebe a variável `JOBOT_PARTE=i/n`; o hook `pytest_collection_modifyitems` (`trylast`, depois do filtro `-m`) de `tests/conftest.py` mantém só a fatia `i` de `n` da coleta, pela função `parte_dos_itens` de `tests/apoio/partes.py` (o item de índice `k` fica na parte `i` quando `k % n == i - 1`). Sem a variável, nada muda, e é assim que a bateria roda na máquina de quem mantém.

**Escolhas:**

1. **Jobs.** `lint` (ruff e mypy), `comuns` em 2 partes (`-m 'not tela'`), `tela` em 16 partes (`-m tela`, com o Chromium) e o `ok`, que junta os três e falha se algum não deu `success`. Uma rodada tem 20 jobs, o teto de jobs ao mesmo tempo do plano grátis do GitHub, então nenhum fica na fila. A rodada caiu de cerca de 10 minutos para cerca de 2,5. Teste: `tests/unidade/test_partes.py`, `test_as_partes_juntas_dao_a_lista_inteira` e `test_gancho_roda_depois_do_filtro_de_marcadores`.
2. **Número de partes (para confirmar).** 2 para os testes comuns e 16 para os de tela. Os de tela são os lentos (cada um sobe o painel e abre o navegador); os comuns acabam logo e mais partes só somariam o custo de preparar cada job. Alternativa: mais partes nos comuns, o que estoura o teto de 20 jobs, ou menos nas de tela, o que alonga a rodada. Recomendo 2 e 16.
3. **Check obrigatório (para confirmar).** O `ok` é o nome estável do check: olhar ou exigir só ele, e não cada parte, que muda de nome se o número de partes mudar. A proteção da `main` hoje não exige checks; se passar a exigir, o certo é exigir o `ok` (mudar a estrutura de jobs muda o nome do check exigido). Alternativa: não exigir nada, como hoje. Recomendo o `ok` se algum dia exigir.

**O que o dono faz:** nada para funcionar. Fica com ele: confirmar o número de partes (item 2) e, quando for ligar a proteção de checks na `main`, escolher o `ok`.

**Como desfazer:** apagar a variável do workflow e voltar a um job só devolve a rodada longa; o hook do `conftest.py` não faz nada sem `JOBOT_PARTE`. Mudar o número de partes é mudar a lista `parte` da matriz no `ci.yml`.

## D150. Pendências do visual e de Contas (para confirmar)

**Status:** para confirmar. Decidido pela recomendação de cada item, com o dono fora.

**Contexto:** a T251 (lateral e barra do visual novo) e a T273 (Contas, "Conferir agora") deixaram escolhas pequenas que o desenho não fechava. Cada uma segue a recomendação até o dono dizer outra coisa.

**Escolhas:**

1. (D150.1, T251) **Dois `aria-current="page"` em `/vagas`.** A lateral e a `nav.abas` marcam a página atual ao mesmo tempo. Alternativa: deixar os dois até a tarefa que tira as abas. Recomendo que a tarefa que tira as abas (T254) remova a `nav.abas` ou troque o atributo dela por `aria-selected`.
2. (D150.2, T251) **Rótulo do `nav` lateral.** Segue "Principal" em português e "Main" em inglês. Alternativa: um nome mais específico. Recomendo manter.
3. (D150.3, T251) **Altura da barra.** A barra usa `min-block-size` de 52px, não altura fixa, para crescer com texto maior. Alternativa: altura fixa de 52px. Recomendo manter, com o teste de 52px a 1200px só no CI.
4. (D150.4, T251) **Title Case no inglês dos itens da lateral.** Os itens em inglês ainda não seguem a capitalização da HIG. Alternativa: ajustar já. Recomendo deixar para a T254, que mexe nos rótulos.
5. (D150.5, T273) **`abrir_contexto` fora do prazo do "Conferir agora".** O prazo `PRAZO_CONFERIR_S` (60 s) cobre só `new_page` e `visitar`, não a abertura do contexto do Chromium. Cancelar o launch no meio deixaria o perfil travado (`SingletonLock`); a espera na abertura passa a depender do prazo próprio do launch do Playwright. Alternativa: pôr a abertura dentro dos 60 s, o que pode deixar um Chromium órfão e o perfil preso. Recomendo manter.

**O que o dono faz:** nada para funcionar. Fica com ele confirmar os itens ou mandar trocar algum.

**Como desfazer:** cada item é uma `Tn` pequena: o 1 e o 4 entram na T254, o 3 troca uma linha de CSS e o 5 move a abertura do contexto para dentro do prazo.

## D151. Último evento de status do Desfazer pela ordem de gravação (para confirmar)

**Status:** para confirmar. Decidido pela recomendação, com o dono fora.

**Contexto:** `desfazer_candidatura` (T281, E18) acha o último evento de status da vaga. Ordenar por `julianday(criado_em) DESC, id DESC` erra se o relógio voltar: o Sim às T+5h, uma mudança para `entrevista` às T+1h e o Desfazer do status às T+2h deixam a vaga em `candidatei`, mas o Sim, de instante maior, ainda parece o último evento. A função devolveria `True` e levaria a vaga a `salva`, um status que ela não tem a ver com a última ação. Como `evento` só recebe acréscimo, o `id` é a ordem real de gravação.

**Escolhas:**

1. **Opção A (escolhida).** Ordenar só por `id DESC`. Cobre o relógio que volta. Prende com o teste `test_desfazer_com_relogio_que_volta`.
2. **Opção B.** Manter `julianday(criado_em) DESC, id DESC` e aceitar o caso. Menos mudança, mas o Desfazer pode levar a vaga a um status que ela não devia ter.

**Recomendação:** A.

**O que o dono faz:** nada.

**Como desfazer:** voltar a ordenação para `julianday(criado_em) DESC, id DESC` e apagar o teste.

## D152. Linha azul na lista estreita com a vaga aberta (para confirmar)

**Status:** para confirmar. Decidido pela recomendação, com o dono fora.

**Contexto:** a T255 abre o detalhe da vaga ao lado da lista. Abaixo de 640px, com `?vaga=` na URL, a linha da vaga aberta pode ficar azul de seleção. A regra de "sem foco" mora dentro do `@container` da coluna e não vale fora dele. O caso é raro: pede janela estreita e link direto com `?vaga=`.

**Escolhas:**

1. **Opção A (escolhida).** Deixar como está.
2. **Opção B.** Repetir a regra de "sem foco" fora do `@container`. A linha deixa de ficar azul em janela estreita, ao custo de uma regra duplicada que precisa andar junto com a original.

**Recomendação:** A, porque o caso é raro e o efeito é só visual.

**O que o dono faz:** nada.

**Como desfazer:** acrescentar uma regra de CSS em `vagas.css`.

## D153. Itens da lateral levam só aba e busca (para confirmar)

**Status:** para confirmar. Decidido pela recomendação, com o dono fora.

**Contexto:** na T254, ao trocar de aba pela lateral, os filtros escolhidos (chips) se perdem. Só a aba e a busca escolhida vão no link do item.

**Escolhas:**

1. **Opção A (escolhida).** Aceitar. É como no Mail do Mac, onde trocar de caixa limpa o filtro.
2. **Opção B.** Levar os filtros no link de cada item. A pessoa não perde o filtro ao trocar de aba, mas o link da lateral fica maior e cada item precisa conhecer os parâmetros de filtro.
3. **Dois itens pequenos na mesma D.** Chips em inglês em sentence case (como "Work mode") ficam para a T268 (revisão de textos). A aba Programas continua em cartões e vira `Tn` nova do plano visual quando o lote voltar à `dev`.

**Recomendação:** A para a escolha 1 e as duas sugestões do item 3.

**O que o dono faz:** nada.

**Como desfazer:** o link da lateral passa a copiar os parâmetros de filtro.

## D154. A faixa de desfazer e a troca de aba pela lateral (T256)

**Status:** para confirmar. O agente da T256 propôs a opção 1; a sessão ainda confirma ou ajusta, com o dono fora.

**Contexto:** o desenho (5.4) diz que a faixa de desfazer sobrevive às trocas HTMX dentro de Vagas e cita a aba entre elas. Só que as abas da lateral (`lateral_vagas.html`) são links comuns, sem `hx-get` nem `hx-boost`: trocar de aba carrega a página inteira, e a página nova não traz a faixa. As trocas do miolo (busca, ordem, chips, "carregar mais", busca escolhida) são HTMX e a mantêm.

**Opções:**

1. **Aceitar (recomendado).** Trocar de aba pela lateral conta como página nova e tira a faixa, como qualquer outra página inteira. Não mexe na lateral nem na navegação. Teste: `test_faixa_fica_ao_trocar_a_ordem` (a faixa fica na troca do miolo).
2. **Abas de Vagas por HTMX.** As abas trocariam só o miolo, com `hx-get` e `hx-push-url`. É mudança de navegação (lateral, histórico, foco e região viva) e vira tarefa nova.

**O que o dono faz:** confirmar a opção 1 ou pedir a 2.

**Como desfazer:** a opção 2 é uma `Tn` nova; a faixa já sobrevive a qualquer troca HTMX, então não muda.

## D155. O Desfazer da faixa volta ao "mostrar mesmo assim" (T256, muda a D12)

**Status:** para confirmar. Decidido pela recomendação, com o dono fora.

**Contexto:** a D12 decidiu que `trazer_de_volta` zera `oculta_manual` sem restaurar um -1. A T256 mantém isso no "Trazer de volta" da aba Ocultas. Mas o Desfazer da faixa de Ocultar, quando o Ocultar saiu de um "mostrar mesmo assim" (-1) numa vaga que a regra esconde, tem de levar a vaga de volta a -1; com 0, a vaga oculta por regra não voltaria à lista.

**Escolhas:**

- **A (escolhida).** `acoes.trazer_de_volta` ganha o parâmetro opcional `oculta` (0 por padrão; -1 só no Desfazer da faixa, que manda `antes=-1`). Uma transação e um evento `desfez`. Teste: `test_desfazer_volta_ao_mostrar_mesmo_assim`, `test_trazer_de_volta_recusa_oculta_invalida`.
- **B.** A rota chama `trazer_de_volta` e depois `mostrar`: duas transações e dois eventos (`desfez` e `mostrou`) para um só clique, com a vaga passando por 0 no meio.

**Recomendação:** A, que é atômica e deixa um evento só no histórico.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** tirar o campo `antes` do formulário da faixa (`_faixa_desfazer.html`) devolve o comportamento da D12 (o Desfazer zera). Trocar para B é uma `Tn` nova.

## D156. Molde de site novo: como acrescentar uma plataforma (para confirmar)

**Status:** para confirmar.

**Contexto:** o dono pediu que acrescentar uma plataforma nova seja simples: um molde pronto, um guia e os passos de captura. Nenhum site entra agora. Gupy continua só pública e o LinkedIn continua o único site com login. Hoje o caminho existe só no plano da fase 1 ('Molde do coletor') e na Parte B do desenho da fase 2. Quem chega de fora não sabe que a chave precisa estar em fontes.json antes do import, que cinco testes têm a lista de fontes escrita à mão, nem que o exemplo de um leitor com login não passa por nenhuma conferência. Desenho: docs/superpowers/specs/2026-11-16-molde-de-site-design.md. Plano: T296 a T300.

**Escolhas:**
1. Molde = arquivos de exemplo testados em tests/apoio/ (um coletor por termo em JSON paginado e um leitor HTML com login), copiados à mão; sem gerador scripts/novo_site.py (M1 a M4).
2. Guarda nova no CI, tests/unidade/test_site_novo.py: todo site registrado tem teste próprio, o exemplo do leitor é válido e o nome está nos catálogos pt e en; as listas fixas de fontes continuam (M5, M6).
3. Captura com os scripts de hoje, sem modo novo (M7).
4. Guia bilíngue docs/site-novo.md e .en.md, ligado do CONTRIBUTING, da wiki e do formulário de fonte, sem página nova na wiki; o guia de conserto passa a dizer fase 9, como o CONTRIBUTING (M8 a M10).
5. Site com termos restritivos: issue primeiro e entrada em FONTES_FORA; ligar ou não por padrão fica com o dono (M11). Uma linha no CHANGELOG (M12).

**Recomendação:** as cinco escolhas como estão.

**O que o dono faz:** lê a seção 11 do desenho e confirma ou troca alguma escolha. Nada a fazer na máquina.

**Como desfazer:** antes de construir, trocar a escolha no desenho e no plano. Depois de construir, apagar tests/apoio/molde_*.py, os testes e as fixtures dos moldes, test_site_novo.py e docs/site-novo*.md, e tirar os links do CONTRIBUTING, da wiki, do fonte.yml e do CHANGELOG. Nenhum dado nem esquema muda.

## D157. Conferência visual por fotos, com o dono fora (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** a T258 era o portão da branch longa `feat/visual-mac`: ela só entraria na `dev` depois do ok do dono, com o painel aberto na frente dele (D140.8, D143.54). O dono deu autonomia para seguir até a fase 9 e não estava para conferir. A sessão fez a conferência sozinha: a T258 virou 40 fotos do painel (fora do repositório), cobrindo os sete itens da T258 (três larguras, claro e escuro, vidro e caminho sólido, os três tamanhos de texto, contagens e busca escolhida, Desfazer, teclado e menu, "Buscar agora"). A branch visual entrou na `dev` sem esperar o ok. Os defeitos vistos nas fotos viram a T301 do plano visual (dez itens: filtros, sobreposto a 800px, lugar do "Mais filtros", topo a 600px, glifo do encaixe médio, primeira linha marcada, "Ver detalhes", texto Maior, Sugeridas e as violações de CSP na troca da lista); o defeito da página própria a 600px vai como item a mais na T264.

Uma escolha de desenho da T301 vai junto, também para confirmar: o "Mais filtros" passa a vir fechado ao carregar a página, mesmo com filtro ativo (se a pessoa o abre, ele continua aberto quando a lista é trocada: chip, envio, troca de busca; o `app.js` guarda isso em `htmx:beforeSwap` e `htmx:afterSwap`), e mostra no resumo quantos filtros valem (no formato de hoje, "Mais filtros (2)", agora contando também os chips), e os grupos de chips (Modalidade, Nível, Área e os outros) passam para dentro dele, para a lista começar na primeira dobra. Isso muda a barra da T254 (desenho 5.2), em que os chips ficam à mostra e o "Mais filtros" abre quando algum campo está preenchido. E outra, do item 6: some só a marca que aparece ao carregar a página; entrar na lista pelo teclado (Tab ou o link "Pular para a lista de vagas") marca a linha focada, porque a seleção segue o foco, como hoje.

Do item 2 (T305 h), aceito e documentado. Sem JavaScript, o detalhe sobreposto fica preso ao `#vagas-miolo` (a contenção do container prende o fixed): cobre a lista na altura toda do miolo e as ações ficam no pé dele. Só chega aí quem abre `?vaga=` direto; sem JavaScript o clique na linha abre a página própria (E10).

**Escolhas:**

- **A (escolhida).** Conferir por fotos, juntar a branch visual na `dev` e corrigir o que as fotos mostram numa tarefa própria (T301), sem parar o resto das ondas 7 e 8.
- **B.** Segurar a branch longa fora da `dev` até o dono conferir, como a T258 pedia. As ondas 7 e 8 (T259 a T268) esperariam.

**Recomendação:** A. A conferência do dono continua valendo: ela só passa a ser feita sobre a `dev`, e cada pedido vira tarefa.

**O que o dono faz:** abrir o painel e dizer o que trocar, inclusive se a barra de filtros da T301 (chips dentro do "Mais filtros", fechado com a contagem) fica assim. Cada pedido vira uma tarefa nova do plano visual.

**Como desfazer:** reverter na `dev` os commits do visual (os das tarefas T248 a T257). A T301 e as tarefas que vierem depois saem junto.

## D158. Pular da primeira execução desliga os sites com login (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** na T263, o botão Pular (`POST /primeira-execucao/pular`, função `pular` em `src/jobot/painel/rotas/primeira_execucao.py:517`) conclui a primeira execução com os padrões e desliga todo site com login (`ligar_fonte(con, leitor.chave, False)` por leitor, linha 527). Uma versão intermediária tinha trocado para "não mexe no que a pessoa ligou"; voltou ao combinado porque o texto da T263, a D137.10, a ADR 0011 e a E10 da fase 2 dizem que Pular deixa os padrões, sem site com login.

**Escolhas:**

- **A (escolhida).** Manter: Pular desliga os sites com login e segue, como a D137.10 e a D143.18 mandam.
- **B.** Pular não mexe no que a pessoa ligou antes no passo dos sites.

**Recomendação:** A (manter, isto é, desligar). Quem pula quer os padrões; um site com login ligado sem a pessoa ter olhado o aviso do passo não deve ficar valendo.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** a troca para B é uma linha em `pular()` (tirar o laço de `ligar_fonte`) e o teste que a prende em `tests/integracao/test_rota_primeira_execucao.py` (a família `test_pular_*`, a partir da linha 905). Nenhum esquema muda.

**Ver também:** D137.10, D143.18.

## D159. Sem JavaScript, Apagar uma busca não pede confirmação (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** na T259, com JavaScript, "Apagar" na lista de Buscas abre um alerta (a macro `src/jobot/painel/templates/_alerta.html`, usada em `buscas/lista.html:65`) e o Return não age sobre ele (E13). Sem JavaScript o botão envia o `POST` direto, como o plano da T259 manda (`test_apagar_sem_js_continua`, `tests/integracao/test_rota_buscas.py:373`). O joBot não apaga dado de vaga: `apagar_busca` (`src/jobot/banco/buscas.py:181-185`) só tira a busca e o encaixe dela (`ON DELETE CASCADE`); a vaga não é tocada.

**Escolhas:**

- **A (escolhida).** Manter: sem JavaScript, o `POST` apaga sem pergunta.
- **B.** Um passo de confirmação para quem está sem JavaScript: uma página intermediária ("Apagar a busca X?") atrás de um `<noscript>` ou de uma rota `GET`. Vira tarefa nova e mais uma tela para manter nas duas línguas.

**Recomendação:** A. O painel é local, de uma pessoa só, quase todo mundo roda com JavaScript, e a busca se refaz em um minuto sem perder nenhuma vaga.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** a B é uma `Tn` nova; a macro do alerta e a rota de hoje não mudam.

## D160. Título em inglês da correção fora do Title Case (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** na T264, `detalhe.correcao.titulo` em `src/jobot/painel/i18n/en/detalhe.json:32` é "Something wrong with this job?" (título do sheet e texto do link). A regra do plano visual pede Title Case em botão, item de menu, título e item da lateral no catálogo `en` (desenho 5.6). O texto aparece também em `README.en.md:221` e em `wiki/How-it-works.md:129`.

**Escolhas:**

- **A (escolhida).** Trocar para "Something Wrong with This Job?" no catálogo `en`, no `README.en.md` e em `wiki/How-it-works.md`, numa vez só, dentro da T268 (documentos de quem usa; item acrescentado lá).
- **B.** Deixar a frase como pergunta em caixa de frase, como exceção à regra.

**Recomendação:** A. A regra fica sem exceção e os três lugares nunca divergem.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** voltar a frase nos três arquivos; nenhum teste de lógica muda (conferir `grep -rn "Something wrong" tests` antes de fechar a T268).

## D161. Ícones do encaixe: o bom parece menos cheio que o médio (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** a T301 (item 5) trocou o glifo "◐" pelos ícones Lucide de `src/jobot/painel/templates/_encaixe.html:5`: bom = `circle` (vazio), médio = `contrast` (meio cheio), fraco = `circle-dashed` (tracejado). Nas fotos o bom parece menos cheio que o médio, ao contrário do que o nome diz.

**Escolhas:**

- **A (escolhida).** Uma escala que cresce: fraco = `circle` (vazio), médio = `contrast` (meio cheio), bom = `circle-check` (cheio, com o visto). O `circle-check.svg` já está em `src/jobot/painel/static/icones/` e no `lucide.meta.json`, então não entra SVG novo; a regra CSS `[data-icone="circle-check"]` hoje mora em `static/css/execucao.css:218` e passa para `casca.css`, ao lado das de `circle` e `contrast` (linhas 171 e 172), para a lista de Vagas achar o ícone.
- **B.** Manter os três de hoje e trocar só o bom para `circle-dot` (círculo com ponto).
- **C.** Embutir um círculo cheio de verdade: o Lucide não tem; pede SVG nosso, fora da licença e do `lucide.meta.json`.

**Recomendação:** A. Cresce da esquerda para a direita, usa só ícones já embutidos e o visto diz "bom encaixe" sem depender da cor. O `circle-dashed` continua nos ícones do progresso (`execucao/_progresso.html:54`).

**O que o dono faz:** confirmar a A ou pedir outra. A troca vira o item (k) da T305.

**Como desfazer:** voltar o dicionário de `_encaixe.html:5` e os dois testes que o prendem (`tests/integracao/test_rota_vagas.py:1765`, `tests/tela/test_vagas.py:968`).

## D162. O alerta de Remover site diz o que se perde (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** o plano visual (T261) mandava o texto "As vagas que ele trouxe continuam.". Mas nenhuma vaga nasce de uma página acompanhada (`src/jobot/banco/migracoes/0001_inicial.sql:197-208` não liga `vaga` a `pagina_acompanhada`), e `remover_pagina` apaga de verdade a página e as mudanças dela (`src/jobot/banco/paginas.py:183`, `DELETE` em cascata), a única remoção real do banco. A frase do plano diria o oposto do que acontece. Também mudou o nome acessível da caixa de ligar cada fonte: agora inclui o nome da fonte (antes era só "Ligada").

**Escolhas:**

- **A.** Manter o texto do plano ("As vagas que ele trouxe continuam.").
- **B.** As duas frases: o que continua e o que se perde.
- **C (escolhida).** Só o que se perde: pt "O texto guardado e as mudanças dele serão apagados." / en "Its saved text and changes will be deleted."

**Recomendação:** C. É curta, é verdadeira e é o que a pessoa precisa saber antes de confirmar.

**O que o dono faz:** confirmar a C ou pedir a A ou a B.

**Como desfazer:** trocar `sites.remover_texto` em `src/jobot/painel/i18n/pt/sites.json` e `src/jobot/painel/i18n/en/sites.json` e as asserções em `tests/integracao/test_rota_sites.py` e `tests/tela/test_sites.py`.

## D163. Sem JavaScript, as ações que apagam não pedem confirmação (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora. Junta a D159.

**Contexto:** com o alerta da T259 (macro `_alerta.html`), o envio do formulário de hoje continua valendo sem JavaScript. O resultado é que, sem JavaScript, três ações agem direto, sem pergunta: Apagar uma busca (D159), Remover site (apaga a página e as mudanças dela, D162) e Esquecer logins (apaga a pasta do perfil do navegador: `src/jobot/painel/templates/configuracoes/sites_com_login.html:15-23`, `src/jobot/painel/rotas/configuracoes.py:593-610`). Antes, Remover site tinha dois cliques (o `details` "Remover mesmo"). O painel é local e usa JavaScript em tudo; sem JavaScript é caminho raro.

**Escolhas:**

- **A (escolhida).** Aceitar por ora e fazer a T307 (página de confirmação sem JavaScript para as três ações).
- **B.** Aceitar de vez, como a D159 fez só para as buscas.

**Recomendação:** A. A T307 fecha o buraco para as três ações com uma página só, sem mudar o caminho com JavaScript.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** a T307 cobre o assunto; nada a desfazer agora.

**Ver também:** D159, D162, T307.

## D164. Configurações lembra o último grupo visto (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** a T262 guarda o último grupo de Configurações em `localStorage` (com `try/catch`). O item Configurações da lateral e o atalho ⌘, (Ctrl+, fora do Mac) abrem esse grupo; sem registro ou sem JavaScript, abrem `/configuracoes/geral`. Grupos que só existem com um leitor (`sites-com-login`, `ferramentas`) podem sumir, e o link guardado daria 404. Também: o estilo comum da caixa de marcar e o interruptor `.chave` e `.chave-mini` foram para `base.css`, valendo para todos os formulários (Buscas, primeira execução, Fontes).

**Escolhas:**

- **A (escolhida).** Manter o último grupo guardado; o 404 do grupo que sumiu vira a T308.
- **B.** Não guardar nada: a lateral e o atalho abrem sempre `/configuracoes/geral`.

**Recomendação:** A. Voltar onde a pessoa estava é o comportamento de um app de Mac, e a T308 tira o único defeito.

**O que o dono faz:** confirmar a A ou pedir a B.

**Como desfazer:** tirar o trecho do `localStorage` em `src/jobot/painel/static/js/app.js` (procure `itemConfiguracoes`); o item volta a abrir `/configuracoes/geral`.

**Ver também:** T308.

## D165. Esquecer logins sem JavaScript devolve só um pedaço de página (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** depois da T307, a confirmação de "Esquecer logins" em Configurações > Sites com login funciona sem JavaScript por uma página própria (`GET .../esquecer/confirmar`). Mas o `POST` que ela envia, sem JavaScript, responde o fragmento `_esquecer.html`: um `<p>` solto, sem o layout do painel. Era assim antes da T307 também; a T307 não mudou esse contrato porque os testes `test_esquecer_so_apaga_ao_confirmar` e `test_resposta_de_esquecer_nao_traz_o_componente` esperam 200 com o fragmento.

**Escolhas:**

- **A.** Deixar como está.
- **B (recomendada).** Sem o cabeçalho `HX-Request`, responder 303 para `/configuracoes/sites-com-login` com um aviso do tipo "salvo", como os outros formulários do painel.
- **C.** Sem `HX-Request`, renderizar a página inteira do grupo já com o resultado.

**Escolha do redator (T310, para confirmar):** sem JavaScript, o sucesso volta para `/configuracoes/sites-com-login?salvo=1` e a falha volta com `?erro=em_andamento` ou `?erro=esquecer`, como a tela de serviços faz com `?erro=cofre`. Com HTMX o fragmento segue igual.

**Recomendação:** B, numa tarefa própria (T310): segue o padrão dos outros formulários e só muda a resposta sem `HX-Request`; com HTMX continua o fragmento.

**O que o dono faz:** confirmar a B ou escolher outra. Nada a fazer na máquina.

**Como desfazer:** antes de construir, trocar a escolha aqui e na T310. Depois, voltar a resposta sem `HX-Request` para o fragmento e os dois testes para 200. Nenhum dado muda.

**Ver também:** D163, T307, T310.

## D166. Sem navegador, os botões que abrem o navegador ficam desabilitados (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** o desenho 5.7 pede que, sem navegador (nem o Google Chrome nem o Chromium do Playwright), os botões que abrem o navegador fiquem desabilitados. A lista da T275 no plano não trazia esse item, e a revisão da T275 o achou faltando. Antes, "Fazer login agora" ficava ativo e só depois de clicado dizia "Nenhum navegador encontrado".

**Escolhas:**

- **A.** Deixar o botão ativo e explicar a falta só depois do clique, como antes.
- **B (recomendada).** Desabilitar o botão quando não há navegador, com `aria-describedby` na frase que explica a falta.

**Escolha do redator (T275, para confirmar):** B. Na aba Contas, o botão aponta para a frase de sempre, "Nenhum navegador encontrado. Instale o Google Chrome ou baixe o navegador em Ferramentas.", que ganha o `id` `contas-sem-navegador`. No passo dos sites do assistente, que não leva a Ferramentas, uma frase nova com o mesmo `id`: "Sem navegador, o botão Fazer login agora fica desligado: baixe o navegador acima ou instale o Google Chrome." O cartão sabe do navegador por conta própria, então a regra vale na página, no fim do login e nos cartões que o "Esquecer logins" devolve. O "Conferir agora" da T277 segue a mesma regra.

**Recomendação:** B. Um botão que não pode funcionar não deve parecer que funciona, e a frase diz o que fazer.

**O que o dono faz:** confirmar a B ou escolher outra. Nada a fazer na máquina.

**Como desfazer:** tirar o `disabled` e o `aria-describedby` de `_cartao_site_login.html` e a frase nova do assistente, e inverter `test_sem_navegador_o_botao_de_login_fica_desligado` e `test_passo_sites_sem_navegador_desliga_o_login`. Nenhum dado muda.

**Ver também:** T275, T277, D137.8.

## D167. A faixa de queda vale para o Gmail mesmo sem leitor de site (para confirmar)

**Status:** para confirmar. Decidido pela sessão, com o dono fora.

**Contexto:** o plano da T276 dizia que, sem leitor registrado, a rota `GET /aviso-contas` devolve fragmento vazio. Isso contradiz E11 e E13: o Gmail não depende de leitor de site, a aba Contas mostra o cartão dele sem leitor, e a queda dele conta na faixa.

**Escolhas:**

- **A.** Sem leitor, faixa sempre vazia, como o plano dizia. A pessoa com o Gmail caído e nenhum site com login não vê aviso no topo; só vê o cartão ao abrir a aba Contas.
- **B (recomendada).** Sem leitor, o site nunca aparece, mas a queda do Gmail abre a faixa ("Sua sessão no Gmail caiu. Entre de novo em Configurações › Contas.").

**Escolha do redator (T276, para confirmar):** B. `contas_em_queda` roda sempre; sem leitor a lista só pode ter o Gmail. O teste `test_sem_leitor_so_o_gmail_da_faixa` prende os dois lados (sem queda do Gmail, vazio; com queda, a faixa).

**Recomendação:** B. Queda sem aviso vira leitura parada sem a pessoa saber; o cartão do Gmail já aparece sem leitor, então a faixa deve acompanhá-lo.

**O que o dono faz:** confirmar a B ou escolher outra. Nada a fazer na máquina.

**Como desfazer:** voltar o `if leitores else []` na rota e trocar `test_sem_leitor_so_o_gmail_da_faixa` por "fragmento vazio". Nenhum dado muda.

**Ver também:** T276, E11, E13, E14.

## D169. Cartão do Gmail: frase do cofre, Remover sem JavaScript e troca com o cofre falhando

**Status:** decidida pelo dono em 2026-11-16: confirmou as escolhas recomendadas abaixo.

**Contexto:** a revisão da T278 (cartão do Gmail na aba Contas) achou três pontos que o plano não fixava:

1. A frase do cofre (`configuracoes.contas.gmail.erro.cofre`) era "O cofre do sistema não respondeu. A senha não foi guardada." e aparecia também quando a leitura falha (abrir a aba, "Conferir agora") e quando o "Remover" falha. Ali ela é falsa ou soa como sucesso.
2. Sem JavaScript, o "Salvar e conferir" devolvia o pedaço do cartão como página solta, e o "Remover" não fazia nada (botão comum que só abre o alerta).
3. "Salvar e conferir" com o cofre falhando na segunda gravação apaga as duas partes, e com elas a credencial antiga, que funcionava (E10).

**Escolhas:**

- **Frase do cofre.** A: uma frase só, a de antes, em todo caso. **B (recomendada):** a frase vira neutra ("O cofre do sistema não respondeu." / "The system password vault did not respond.") e o cartão completa conforme a origem: no salvar, "A senha não foi guardada."; no remover, "A senha não foi apagada. Tente de novo." / "The password was not removed. Try again."; na leitura, só a neutra.
- **Sem JavaScript.** A: deixar como estava. **B (recomendada):** como o "Esquecer logins" (D165, T307, T310): sem `HX-Request` as três rotas respondem 303 para `/configuracoes/contas` com `?salvo=1` ou `?erro=<código>` de uma lista fechada (`_ERROS_DO_GMAIL` em `painel/rotas/gmail.py`), e o cartão mostra a mesma frase que mostraria com JavaScript. O "Remover" vira um formulário GET para `/configuracoes/gmail/remover/confirmar`, que mostra a pergunta em `confirmar.html`; o POST fica só no alerta e nessa página. O "Conferir agora" ganhou também um formulário POST, para funcionar sem JavaScript. O endereço digitado não volta no campo depois do 303 sem JavaScript.
- **Troca da credencial com o cofre falhando.** **A (recomendada, a de agora):** apagar as duas partes, como a E10 manda: nunca sobra meia credencial, e a pessoa perde a antiga e precisa salvar de novo. B: apagar só quando o par ficou inconsistente (a senha nova gravou e o endereço não), mantendo a antiga quando a primeira gravação já falhou; mais ramos e mais testes, e o par antigo pode não combinar com o que a pessoa acabou de digitar.

**Escolha do redator (T278, para confirmar):** B, B e A. O "Remover" aparece com qualquer pedaço da credencial no cofre ou com o cofre em falha, e só o "Conferir agora" pede a credencial inteira: um `apagar` que sai pela metade nunca deixa senha sem jeito de tirá-la.

**Complemento (2ª revisão):** na troca com o cofre falhando, o `apagar` também pode falhar: ficam a senha nova e o endereço antigo, e o cartão não pode dizer "Conectado" nem "A senha não foi guardada". Nesse caso mostra o "não foi apagada" (código `gmail_cofre_troca`, o "Remover" segue à mão) e uma sessão `conectado` passa a `nao_conferiu` (`erro`). Se o `apagar` deu certo, a credencial sumiu e a sessão existente vira `precisa_entrar`/`esquecido`, como no "Remover", para a faixa do topo não sobrar com o cartão em "Nunca entrou". Sem JavaScript, só o "Salvar" e o "Remover" voltam com `?salvo=1`; o "Conferir agora" volta sem sufixo, para não dizer "Salvo." sobre uma queda.

**Recomendação:** B, B e A. A frase diz só o que aconteceu; sem JavaScript as ações seguem o padrão do painel; e a regra da E10 continua simples.

**O que o dono faz:** confirmar as três escolhas ou trocar alguma. Nada a fazer na máquina.

**Como desfazer:** frase: voltar `erro.cofre` ao texto antigo, tirar `erro.nao_apagou` e o `falhou_cofre` por origem do `_cartao_gmail.html`, e ajustar `test_gmail_tem_texto`, `test_remover_cofre_falha_nao_grava` e `test_leitura_do_cofre_falhando_no_get`. Sem JavaScript: tirar o 303 de `_responder`, a rota `GET /remover/confirmar` e os formulários do cartão, e os testes `test_sem_js_*`, `test_erro_do_gmail_na_url_e_lista_fechada` e `test_remover_sem_js_pergunta_numa_pagina`. Troca com o cofre falhando (B): em `salvar`, apagar só se a senha nova gravou e o endereço não, com um teste por ramo. Nenhum dado muda.

**Ver também:** T278, E10, E12, E13, D165, T307, T310.

## D170. A lista depois da faixa "Você se candidatou?"

**Status:** decidida pelo dono em 2026-11-16: confirmou as escolhas recomendadas abaixo.

**Contexto:** a E20 do plano do panorama mandava o cartão da lista (`<article id="vaga-{id}">` de `vagas/cartao.html`) pedir `GET /vagas/{id}/cartao` quando a faixa responde, com o `_resposta` ganhando `foco`. A T305 tirou esse cartão: a linha da lista agora é `<a role="option" id="vaga-{id}">` em `vagas/linha.html`, já usa o `hx-get` para abrir o detalhe e não mostra o status (fora da aba Candidatei, onde a T287 pôs o "desde"). O `_resposta` também não existe mais. Sem mudança, depois do "Sim" a linha fica na aba Salvas até a lista ser recarregada, e o "Salvar" do menu dela continua com o estado antigo.

**Escolhas:**

- **A (recomendada, a de agora):** não mexer na lista. O detalhe ao lado (`#estado-da-vaga`, T286) se atualiza pelo `vaga-mudou-{id}`; a lista fica certa no próximo carregamento. Sem rota, sem JS novo.
- B: um ouvinte de `candidatura-mudou` no `app.js` chama o `recarregarLista` que já existe. Pouco código, mas a lista recarrega enquanto a pessoa está na faixa: pede teste de tela de foco e de rolagem.
- C: rota nova que devolve a linha por `hx-swap-oob`. Mais código e contexto da lista dentro da rota da faixa.

**O que o dono faz:** confirmar a A ou pedir a B. Nada a fazer na máquina.

**Como desfazer:** para a B, um `addEventListener("candidatura-mudou", ...)` no `app.js` com `recarregarLista` e um teste de tela. Nenhum dado muda.

**Ver também:** E20 do plano `2026-11-16-panorama-e-fila.md`, T285, T286, T287, T305.

## D171. Fase 3: app de desktop e instalador

**Status:** itens 1 a 8 decididos pelo dono em 2026-11-17; itens 9 a 18 são escolhas da sessão, para confirmar.

**Contexto:** começo da fase 3 (ADR [0017](docs/decisions/0017-fases.md)). A D142 já tinha escolhido o Tauri e os botões da janela; faltavam a distribuição, a assinatura, os pacotes, o Mac, onde fica o código, o que acontece ao fechar a janela e como a janela se atualiza. Desenho em `docs/superpowers/specs/2026-11-17-fase-3-design.md` (seção 13 traz a mesma lista); plano em `docs/superpowers/plans/2026-11-17-fase-3.md`.

**Decisões do dono:**

1. O instalador traz o `uv` embutido e instala o joBot da release do GitHub da mesma versão, com o sha256 conferido.
2. Linux: AppImage, `.deb` e `.rpm`.
3. Mac: `.dmg` experimental, gerado e testado só no CI.
4. O projeto Tauri fica na pasta `desktop/` do mesmo repositório (muda o "projeto à parte" da ADR 0003).
5. Assinatura: sem selo por enquanto, custo zero. O dono pede o SignPath Foundation (grátis) quando quiser; a SignPath só aceita depois de o instalador já ter saído, então o pedido vem depois da 0.4.0.
6. Não comprar certificado (responde o item de assinatura da D138.16).
7. Fechar a janela fecha só a janela; o servidor segue se o segundo plano estiver ligado. Sem ícone na bandeja.
8. A janela (casca) não se atualiza sozinha: avisa que há versão nova e abre a página da release.

**Escolhas da sessão (para confirmar):**

9. A tela de instalação é a primeira abertura da própria casca, igual nos três sistemas; o NSIS e os pacotes do Linux levam só a casca e o `uv` (os `.deb`/`.rpm` instalam como root e o `uv tool` é por usuário).
10. Essenciais travadas: joBot e Python. O navegador vem marcado e dá para desmarcar (confirma a D138.15).
11. Uma checagem de versão só, a do painel; a casca não consulta o GitHub (mantém a ADR 0014 e o interruptor de Privacidade).
12. Segundo plano no Windows (Agendador de Tarefas) e no Mac (LaunchAgent, experimental) entram na fase 3, para o item 7 valer em todo sistema.
13. Sem npm na casca: `withGlobalTauri` e HTML/CSS/JS puros.
14. Parada no Windows por um segredo local (`<dados>/sair.token`) aceito pelo `POST /sair`; no Linux e no Mac segue o SIGTERM.
15. Com WebKitGTK (ou WebView) sem os recursos de CSS do painel, a casca cai no modo app de hoje e diz por quê.
16. Círculos da janela: 12px, 8px de espaço, símbolos no hover, cinza com a janela inativa (proposta).
17. O `uv` da casca usa pastas próprias, separadas de um `uv` que a pessoa já tenha.
18. Desinstalar nunca apaga a pasta de dados.

**O que o dono faz:** confirmar 9 a 18 ou trocar algum. Depois da 0.4.0, fazer o pedido do SignPath (passo a passo no plano, T343).

**Como desfazer:** cada item mora numa seção do desenho (13 lista as seções); trocar é editar o desenho antes da tarefa correspondente. Depois de construído: 7 e 12 são a `segundo_plano` e a casca (T328, T329, T337); 11 é tirar o aviso da casca na faixa (T332); 15 é tirar a conferência de recursos (T335). Nenhum dado muda.

**Ver também:** D138, D139.10, D140, D142, D143, ADR 0003, 0017, 0018, 0023 e [0025](docs/decisions/0025-app-de-desktop-e-instalador.md).

## D172. Todo PR passa pela aprovação do dono

**Status:** decidida pelo dono em 2026-11-17 e já aplicada no GitHub.

**Contexto:** o dono pediu que todo PR do joBot passe pela aprovação dele, para diminuir o risco de alguém mal-intencionado. Antes, a `main` exigia PR com zero aprovações, a `dev` só não podia ser reescrita nem apagada, e o CI de fork pedia o ok do dono só no primeiro PR de cada pessoa (ADR 0018).

**Decisões:**

1. (dono) Regras `proteger-main` e `proteger-dev`: todo PR precisa de uma aprovação do responsável (`.github/CODEOWNERS`), que cai se entrar commit novo, e o último push também precisa ser aprovado. Continuam valendo: sem reescrever e sem apagar.
2. (sessão, para confirmar) Exceção só para o papel de administrador (o dono), porque o GitHub não deixa aprovar o próprio PR: na `main`, só por dentro de um PR (para juntar o PR `dev` → `main`); na `dev`, sempre (fluxo de lotes que entra direto).
3. (dono) CI de PR vindo de fork espera o ok do dono para todo contribuidor de fora, não só o primeiro PR.
4. (dono) Varredura de código do GitHub (CodeQL) na configuração padrão: Python, JavaScript e os workflows do Actions, nos PRs para a `main`, em cada push na `main` e uma vez por semana. Não põe arquivo no repositório e não leva segredo. Os alertas do Dependabot continuam ligados (só avisam); os PRs automáticos dele continuam desligados (ADR 0021). A detecção de segredos genéricos não está disponível nesta conta; a de provedores e o bloqueio de push com segredo já estavam ligados.

**Como desfazer:** Settings › Rules › Rulesets (`proteger-main`, `proteger-dev`) e Settings › Actions › General › Fork pull request workflows. Nada no código muda; ADR 0016 e 0018 e o guia de contribuição citam esta decisão.

## D173. Hash das dependências na instalação pela casca (para decidir)

**Status:** aberta, o dono decide antes da T336 (tela de instalação) e da T337.

**Contexto:** a T322 mediu (`uv 0.12.3`, `scripts/provar_uv.py`) que o `uv tool install` não confere o hash de cada dependência, nem com `--constraints` nem com `--with-requirements` e `UV_REQUIRE_HASHES=1`. O `uv pip install --require-hashes -r restricoes.txt` recusa o mesmo arquivo adulterado. Desenho 6.2 e 6.3.

**Opções:**

1. **Manter `uv tool install --constraints`** com o limite escrito no README e na ADR 0025. A garantia fica no sha256 da wheel e do `restricoes.txt` (conferidos em Rust) e nos pinos `==`; uma dependência trocada no índice com a mesma versão passaria. Mais simples: o `uv tool` cuida do executável `jobot`, do `--force` na atualização e do `uv tool uninstall`.
2. **Trocar por `uv venv` + `uv pip install --require-hashes -r restricoes.txt <wheel>`** numa pasta da casca. Cada dependência tem o hash conferido. Custo: a casca e o `atualizar.py` (canal `casca`) passam a cuidar do executável (caminho dentro do venv), da troca na atualização (venv novo e troca de pasta) e da remoção no desinstalador.

**Recomendada:** 2. O instalador é a porta de entrada de quem não usa terminal, e o custo fica em código da casca que ainda não existe.

**Como desfazer:** 1 para 2 é mudar o comando em `desktop/src/instalar.rs`, no canal `casca` do `atualizar.py` e no hook do desinstalador (T336, T337), sem mexer nos dados. 2 para 1 é o mesmo caminho ao contrário; o `instalacao.json` ganha o caminho do executável, que fica sem uso.

**Ver também:** D171 (itens 1 e 17), T322, desenho 6.2.

## D174. Segundo plano no Windows e no Mac: escolhas da T328 e da T329 (para confirmar)

**Status:** escolhas da sessão, para confirmar.

**Contexto:** a T328 liga o segundo plano no Windows pelo Agendador de Tarefas (`sistema/segundo_plano_windows.py`) e põe a tela Configurações › Segundo plano e o passo 2 do assistente atrás de uma função só (`sistema/segundo_plano.py`: `suportado`, `ligar`, `desligar`, `status`, `criar_atalho`), como pede o desenho 6.5 (D171 item 12). Ficaram estas escolhas:

1. Ligar só registra a tarefa (`schtasks /Create /TN joBot /XML <arquivo> /F`); não roda `/Run`. O servidor que está aberto continua; a tarefa sobe o joBot na próxima entrada no Windows. O XML sai de uma função pura (`xml_da_tarefa`) e vai num arquivo temporário em UTF-16, apagado logo depois. Ele troca o `/SC ONLOGON` do desenho porque os padrões do Agendador desligariam um servidor que fica no ar: a tarefa não subiria na bateria, pararia ao passar para a bateria e morreria em 72 h. O XML leva `LogonTrigger` e `Principal` com o usuário atual (`USERDOMAIN\USERNAME`, `InteractiveToken`, `LeastPrivilege`), `DisallowStartIfOnBatteries` e `StopIfGoingOnBatteries` em `false`, `ExecutionTimeLimit` `PT0S` e `MultipleInstancesPolicy` `IgnoreNew`. A ação é o `pythonw.exe` com `-m jobot serve`; no pythonw o `sys.stdout` é `None`, por isso o `serve` passa `use_colors=False` ao uvicorn. O `schtasks` roda com `CREATE_NO_WINDOW`, para não piscar console.
2. "Rodando agora" segue o "Serviço instalado" no Windows: o `schtasks /Query` escreve o estado na língua do sistema, e ler o estado sem depender dela (PowerShell `Get-ScheduledTask`) fica para depois.
3. Desligar sem tarefa registrada vale (o `/Delete` falha à toa); com a tarefa ainda lá (`/Query` acha), a falha vira recusa `segundo_plano.schtasks_falhou`, com a saída só no log, como no systemctl (T159).
4. O atalho do menu só é criado no Linux; no Windows o instalador da casca (NSIS) cria o do Menu Iniciar (desenho 6.5).
5. O comando `jobot segundo-plano` (CLI) continua só com o systemd; no Windows ele recusa com "o systemd do usuário não responde". Passar o CLI para a função única fica para uma tarefa própria.
6. Fora do Linux, do Windows e do Mac a tela e o passo 2 dizem "chega numa próxima versão" (chaves `nao_suportado`, que trocam as `nao_linux`); a T329 acrescentou o Mac (`darwin`) em `segundo_plano.suportado`.
7. Risco a provar no Windows de verdade (seção 10 do desenho): em conta sem administrador, o `schtasks /Create` pode responder "acesso negado" (o gatilho com o usuário atual costuma dispensar administrador, mas falta ver), e falta ver a tarefa subir na bateria e passar de 72 h. A tela mostra a recusa com texto fixo e nada é gravado. Saída, se acontecer: um atalho na pasta Inicializar do usuário (`shell:startup`), que não pede administrador.

8. (T329, Mac) `sistema/segundo_plano_mac.py`: o plist sai do `plistlib` (`texto_do_plist`), com `Label` `io.github.fezarosa-dev.jobot`, `ProgramArguments` `<python> -m jobot serve`, `RunAtLoad` e `KeepAlive` `{SuccessfulExit: false}` (o launchd só o refaz se sair com erro). Ligar grava o plist em `~/Library/LaunchAgents/` e roda `launchctl bootstrap gui/<uid> <plist>`; se o `launchctl print gui/<uid>/<rótulo>` já acha o serviço, só regrava o plist (outro `bootstrap` falharia e um `bootout` pararia o servidor no ar; o plist novo vale no próximo login). `bootstrap` recusado apaga o plist, para não subir no próximo login com o segundo plano desligado. Desligar roda `bootout` e apaga o plist; sem serviço carregado vale, com ele a falha vira recusa `segundo_plano.launchctl_falhou` (saída só no log). Status: "Serviço instalado" é o `launchctl print` achar o serviço carregado (um `bootout` feito fora do joBot mostra desligado, mas o plist que ficou sobe o serviço no próximo login; desligar pela tela apaga o plist), e "Rodando agora" é a saída dele trazer `state = running` (o `launchctl` não traduz). Sem atalho: o app vem do `.dmg`.
9. (T329, Mac) O `bootstrap` com `RunAtLoad` sobe o serviço na hora, diferente do Windows (item 1). Ligado pelo painel que já está aberto, o `serve` do launchd acha a trava. Se saísse com 1, o `KeepAlive` o refaria a cada 10 s (o `ThrottleInterval` padrão) enquanto o painel estivesse aberto, sem fim na casca. Por isso o `serve` sai com 0 quando outra instância do joBot está no ar ("O joBot já está aberto."): o launchd não o refaz e ele volta no próximo login, igual ao Windows; o `Restart=on-failure` do systemd também deixa de gastar o `StartLimitBurst`. Com a captura de exemplos no ar continua 1, porque ela acaba logo e o serviço assume na nova tentativa. Teste: `test_serve_com_outro_jobot_aberto_avisa_e_sai_com_0` em `tests/integracao/test_servir.py`.

**Como desfazer:** 9 é voltar o `return 0` de "já está aberto" em `cli/servir.py` para 1 e pôr `ThrottleInterval` alto no plist; 8 é trocar `segundo_plano_mac.ligar` (por exemplo, `bootout` e `bootstrap` sempre) ou o `KeepAlive` para `true`; 1 é acrescentar `schtasks /Run /TN joBot` no `ligar` do Windows (ou voltar ao `/SC ONLOGON /TR`, com os padrões de bateria e 72 h); 2 é trocar o `status` do Windows; 5 é apontar `segundo-plano` em `cli/__init__.py` para um `executar` que use `sistema.segundo_plano`. Nenhum dado muda.

**Ver também:** D171 (itens 7 e 12), D61, desenho 6.5, T328, T329.

**Nota de junção:** as branches t344-offline, t330-navegador e t331-atualizar também criaram uma D174 ("Instalador completo e sem rede"). Na junção do lote, renumerar uma das duas e atualizar quem cita (desenho 6.5, plano T328 e T329).
