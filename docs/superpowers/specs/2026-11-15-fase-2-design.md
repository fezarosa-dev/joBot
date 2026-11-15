# Fase 2, navegação com login: desenho

Data: 2026-11-15. Decisões de origem: ADR 0005 (sites com login), ADR 0006 (agenda), ADR 0017 (fases), ADR 0022 (CAPTCHA pelo serviço da pessoa) e o desenho do 2Captcha (`docs/superpowers/specs/2026-11-15-captcha-design.md`). As decisões novas ficam em `duvidas.md` como D132.

Este documento é a especificação para planejar e construir a fase 2 sem voltar ao dono, menos a Parte B, que precisa do login dele, site por site. A fase 2 sai da `dev` atual, que já tem a `0006_ocorrencia_fonte_vaga.sql` (só um índice); as migrações novas, 0007 e 0008, valem contra ela. Todo fato sobre o código vem com `arquivo:linha`, conferido na árvore da fase 2 em 2026-11-15, e vale também na `dev` para os arquivos citados. As linhas podem andar: quando a linha não bater, procure pelo nome.

Cada decisão deste documento é **decisão da sessão, para confirmar com o dono**, menos o que já está em ADR (citada ao lado). Cada uma leva o número da lista completa da seção 12 (D132.1 a D132.57); as que dependem de resposta do dono estão também na seção 11.

## 1. Intenção e porquê

LinkedIn, Indeed, Catho, Vagas.com e outros só mostram a vaga completa para quem está logado (ADR 0005, `docs/decisions/0005-sites-com-login.md:9`). A fase 1 só lê fontes públicas e, por regra, para quando encontra login (ADR 0004, `docs/decisions/0004-fontes-publicas.md:41`). A fase 2 é o "navegador com login: Chrome visível, mapeamento dos sites e tratamento de CAPTCHA" (ADR 0017, `docs/decisions/0017-fases.md:15`).

O jeito já está decidido (ADR 0005, `:21-24`): o joBot abre um Chrome visível, com um perfil só dele; a pessoa faz o login com as próprias mãos; o joBot só lê, duas vezes por dia. O 2Captcha, já preparado na 0.2.0, só age aqui e só com a chave posta e o interruptor ligado (ADR 0022, `docs/decisions/0022-captcha-pelo-servico-da-pessoa.md:22-31`).

Por que agora: a 0.2.0 fechou a fase 1 (ADR 0017, `:9`), e a cola do 2Captcha com o navegador ficou explicitamente para o plano da fase 2 (desenho do 2Captcha, `2026-11-15-captcha-design.md:210`).

O joBot continua de uso pessoal: a conta é da pessoa, o risco com os termos de cada site é da pessoa, e ela decide site por site (ADR 0005, `:41`).

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos

1. A pessoa liga, site por site, a leitura com login, e faz o login uma vez numa janela do Chrome que o joBot abre.
2. Nos horários escolhidos (9h e 18h por padrão), o joBot abre o Chrome visível, lê as vagas dos sites ligados e as grava nas mesmas tabelas das fontes públicas.
3. Sessão vencida, CAPTCHA sem 2Captcha, bloqueio ou falta de tela aparecem na saúde das fontes com motivo claro, e o painel diz o que fazer.
4. Com o 2Captcha pronto, um CAPTCHA reCAPTCHA v2 (inclusive invisível) ou Turnstile avulso numa página de desafio é resolvido uma vez por página. Fora disso, aviso vermelho, aviso no computador e janela parada (ADR 0005, `:28-31`).
5. Cada site entra com um leitor puro, testado com fixtures capturadas por nós e sem dado pessoal (ADR 0005, `:35-37`).
6. A infraestrutura inteira (Parte A) entra na `dev` sem mudar nada visível na versão publicada; a fase 2 sai como 0.3.0 com a Gupy (D132.23).

Não objetivos (ficam como estão)

- Fontes públicas: nada muda. CAPTCHA, 401, 403 ou bloqueio continua sendo "a fonte falhou", e o 2Captcha nunca age nelas (ADR 0022, `:23`; `tests/unidade/test_camadas.py:78-82`).
- reCAPTCHA v3: fica fora da fase 2 (D132.31). Usá-lo exigiria trocar o `grecaptcha.execute` do site, o que a exceção dos anti-objetivos não permite. A ADR 0022 continua aceitando o v3 no cliente da API (`src/jobot/nucleo/captcha.py:231-235`), mas a fase 2 não o usa. Um v3 na página é tratado como "tipo não aceito": janela parada.
- Desafio gerenciado do Cloudflare (a página inteira de desafio, mesmo com o iframe do Turnstile dentro): o 2Captcha não age nele (D132.44, pergunta ao dono, porque estreita a ADR 0022, `:24`); ver a seção A8.
- Windows e macOS: a fase 2 é só Linux, como o segundo plano da fase 1 (desenho da fase 1, seção 12.5, `2026-11-13-fase-1-design.md:1201`).
- Candidatura, mensagem, mudança de perfil: nunca (ADR 0005, `:23`).
- Sites além da ordem da ADR 0005: entram um de cada vez, depois da 0.3.0.
- `reportCorrect` e `reportIncorrect` do 2Captcha: fora da fase 2 (D132.57). O `id_tarefa` já fica na `Solucao` (`src/jobot/nucleo/captcha.py:130-135`) para quem quiser depois.
- Comando de terminal para a leitura com login: o `jobot buscar` não roda sites com login (D132.49). A leitura com login só roda dentro do `serve`, que tem a trava do navegador.

Anti-objetivos (o que isto não pode fazer)

- Nunca digitar senha, nunca preencher formulário, nunca clicar, nunca clicar em "candidatar", nunca enviar nada, nunca mexer na conta. Nas execuções automáticas o joBot só navega, espera e rola (D132.16; ADR 0005, `:22-23`).
  - Exceção estreita, só para a cola do CAPTCHA e só na página de desafio, que nunca é página de login (D132.31, D132.37): o joBot pode (a) escrever o token no campo de resposta do próprio widget (`g-recaptcha-response` ou `cf-turnstile-response`) e (b) chamar a função de retorno que o próprio widget declarou (`data-callback`). Nada além disso: não clica, não envia formulário, não troca nem embrulha função do site. O pedido que o próprio site faz quando a função de retorno roda é do site.
- Nunca disfarçar o navegador: sem plugin de "stealth", sem mexer em `navigator.webdriver`, sem trocar o user agent do Chrome. Site que bloqueia automação conta como "falhou" (D132.15). Um desafio anti-robô que se resolve (sozinho, pelo 2Captcha ou pela pessoa) não conta como bloqueio; conta quando o mesmo desafio volta depois de resolvido, na mesma execução (D132.30; seção A8).
- Nunca rodar escondido: sem tela, a execução falha com motivo; nada de modo sem janela às escondidas (D132.9).
- Nunca usar o perfil do Chrome do dia a dia da pessoa (D132.3).
- Nunca deixar o Chrome guardar senha ou preencher formulário sozinho no perfil do joBot (D132.43).
- Nunca abrir porta TCP de depuração: o Playwright fala com o navegador por pipe, o padrão; nunca `--remote-debugging-port`, nunca `connect_over_cdp` (D132.17).
- Nunca fazer pedido fora do navegador com os cookies da pessoa: sem `page.request` nem `context.request` (D132.38).
- Nunca deixar o perfil (cookies de sessão) sair da máquina, entrar em backup ou exportação do joBot, ou aparecer no log (D132.22).
- Nunca obedecer ao conteúdo da página: texto, links e JSON dos sites são dados, nunca instrução (`CLAUDE.md` do projeto, regras).
- Nunca levar o gabarito, um dado pessoal, um cookie ou um token para uma fixture, um teste ou o código.

## 3. Restrições

- Camadas (desenho da fase 1, seção 6.1, `2026-11-13-fase-1-design.md:205-211`): `nucleo` puro; `banco` só `nucleo`; `agenda` só `nucleo` e `banco`; `painel` sem `httpx` (`tests/unidade/test_camadas.py:69-70`). O teste das camadas hoje proíbe `nucleo/coletores`, `agenda` e `cli` de importar `jobot.nucleo.captcha` (`tests/unidade/test_camadas.py:78-82`).
- Dependência: sem pacote novo sem decisão; tudo fixado com `==` (`CLAUDE.md` do projeto; ADR 0021). O Playwright 1.65.1 já está no projeto, só no grupo `dev` (`pyproject.toml:26-33`).
- Gravação: `INSERT ... ON CONFLICT DO UPDATE`, nada apagado; `vaga` tem gatilho que recusa `DELETE` (`src/jobot/banco/migracoes/0001_inicial.sql:97-100`). Migração aplicada nunca é editada (`0001_inicial.sql:1`).
- Duplicata: a única chave é o hash da URL canônica (`0001_inicial.sql:63`; ADR 0007).
- Painel só em `127.0.0.1`, sem recurso externo, CSP sem script inline, texto novo em `i18n/pt` e `i18n/en` (desenho do 2Captcha, seção 3).
- Chave `saude.*` nova é R4 (`registros/padroes.md:32`): só as que este desenho lista (D132.7), e o que der reaproveita as que existem.
- Rede nova muda juntos o README em pt e en e o texto `configuracoes.privacidade.telemetria` em pt e en, com o teste `test_privacidade_cita_todos_os_pedidos` (desenho do 2Captcha, seção 3, `2026-11-15-captcha-design.md:64`).
- Testes sem rede (`tests/conftest.py` só deixa `127.0.0.1` e `::1`) e com relógio injetado. Atenção: a guarda do `conftest.py` age no Python; o navegador é outro processo e não passa por ela (seção 8).
- Sala limpa (ADR 0016, `docs/decisions/0016-licenca-clean-room-e-processo.md:20-22`): fixtures capturadas por nós; nada copiado de outro projeto.

## 4. Como funciona hoje (fatos conferidos)

Navegador e Playwright

- O Playwright 1.65.1 e o `pytest-playwright` 0.10.0 estão só no grupo `dev` (`pyproject.toml:27-30`); as dependências de execução não o têm (`pyproject.toml:13-21`).
- O desenho da fase 1 diz que o Playwright só viraria dependência de execução se uma fonte pública exigisse JavaScript (`2026-11-13-fase-1-design.md:1491`; DR-16, `:1548`), e que o Chromium dele passa de 100 MB (`:1498`).
- A `fedora-dev` não tem Chrome nem navegador: os testes de tela usam o Chromium baixado pelo Playwright (`2026-11-13-fase-1-design.md:1436`), e o painel abre no navegador do sistema de fora por `distrobox-host-exec xdg-open` (`:161`, `:1213`).
- O CI instala o Chromium com `uv run playwright install --with-deps chromium` (`.github/workflows/ci.yml:35`) e roda `pytest -m tela` sem tela (`:36`).
- Não há pacote `jobot/navegador` nem código que abra navegador para ler site.

2Captcha (pronto na 0.2.0)

- `resolver(cliente, chave, desafio, relogio, *, reservar)` devolve `Solucao(token, custo, user_agent, id_tarefa)` (`src/jobot/nucleo/captcha.py:316-343`, `:130-135`). Conta no teto antes de qualquer pedido (`:329-330`), prazo de 180 s (`:35`, `:332`), `createTask` uma vez só (`:264-286`).
- `Desafio(tipo, url, sitekey, user_agent, invisivel, acao, min_score)` valida tudo e tira query e fragmento da URL antes de ir ao serviço (`src/jobot/nucleo/captcha.py:81-127`, em especial `:106-109`). Não tem `cData` nem `chlPageData`, que o desafio gerenciado do Cloudflare pede (`:81-89`).
- Falhas num conjunto fechado, `ErroCaptcha(Falha)` (`src/jobot/nucleo/captcha.py:57-74`), inclusive `TETO_DIARIO` (`:65`).
- Portão: `captcha_pronto(con, chave)` = `captcha_ligado` verdadeiro e chave não nula (`src/jobot/banco/captcha.py:33-35`); teto `reservar_resolucao(con, dia)` com `TETO_DIA = 30` (`:12`, `:38-42`). O padrão `captcha_ligado: False` mora em `cadastros.PADROES` (`src/jobot/banco/cadastros.py:46`).
- A chave mora no `Cofre` (`src/jobot/sistema/cofre.py:41-46`), lida pelo nome `2captcha` (o painel usa `NOME` de `painel/rotas/servicos.py`, `src/jobot/painel/rotas/configuracoes.py:34`, `:267`).

Agenda, serviço e "Buscar agora"

- A agenda só tem intervalos: busca 3 h, descoberta 7 dias, páginas 24 h (`src/jobot/agenda/agendador.py:20-24`), laço a cada 60 s (`:26`, `:128`), nada nos primeiros 60 s depois de iniciar (`:25`, `:66-67`). Não há horário de parede. `o_que_roda` recebe as últimas de cada tipo como parâmetros fixos (`:50-78`).
- O laço recebe as tarefas por injeção: `laco(tarefas, estado, relogio, *, travas)` (`src/jobot/agenda/agendador.py:90-101`), e o `cli/servir.py` monta o mapa `tarefas` com uma função por tipo (`src/jobot/cli/servir.py:149-153`) e chama o laço (`:154-156`). Cada tarefa roda dentro de `rodar(tipo, trava, tarefa)`, que loga o erro e solta a trava (`agendador.py:81-87`).
- O laço lê a última execução de cada tipo por `inicio_da_ultima_completa(con, tipo)` (`src/jobot/cli/servir.py:35`, `:91-93`), que só conta as `concluida`; interrompida e rodando não contam (`src/jobot/banco/execucoes.py:231-236`).
- O tipo de execução é `Literal["busca", "descoberta", "paginas"]` (`src/jobot/banco/execucoes.py:25`), e o banco recusa outro valor: `CHECK (tipo IN ('busca','descoberta','paginas'))` (`src/jobot/banco/migracoes/0001_inicial.sql:38`). Uma execução "rodando" por tipo, pelo índice único (`0001_inicial.sql:47`). O motivo aceita `agenda`, `agora` e `recuperacao` (`:39`).
- O `serve` roda painel e agenda num processo, com uma trava `asyncio.Lock` por tipo em `app.state.travas`, a mesma do laço e do "Buscar agora" (`src/jobot/cli/servir.py:123-125`), e um `ClienteEducado` só (`:133-134`). A agenda não roda nada antes da primeira execução concluída (`src/jobot/cli/servir.py:95-101`).
- O "Buscar agora" (`src/jobot/painel/rotas/execucao.py:116-138`) pega `travas["busca"]` (`:126`), dispara a busca numa tarefa guardada em `app.state.tarefas` com motivo `agora` e não espera (`:100-113`). A tela de andamento já descarta execuções que não são busca (`:75-76`).
- Os ajudantes de execução que só mexem no banco moram na agenda: `parada_de` (`src/jobot/agenda/execucao.py:112-118`), `interromper` (`:121-135`) e o batimento assíncrono `bater` (`:143-157`). O `banco/execucoes.py` já tem um `bater` síncrono com o mesmo nome (`src/jobot/banco/execucoes.py:104-110`).
- O passo de detalhes da busca escolhe as candidatas com uma consulta SQL na própria agenda: ocorrências abertas de vagas vistas pela primeira vez nos últimos 30 dias, sem descrição na ocorrência, as mais novas primeiro, e depois tira as que têm detalhe recente por `detalhe_recente` (`src/jobot/agenda/execucao.py:270-291`, consulta em `:273-286`).
- O motivo de parada é `Literal["fechado", "sem_batimento", "banco", "erro"]` (`src/jobot/banco/execucoes.py:28`); `parada_de` dá `fechado` para cancelamento, Ctrl+C e saída (`src/jobot/agenda/execucao.py:112-115`). A coluna `parada` e o `CHECK` dela vêm de `src/jobot/banco/migracoes/0004_motivo_da_parada.sql:4-5`.
- O serviço do systemd não trata `DISPLAY` nem `WAYLAND_DISPLAY`: o texto do `.service` só tem `ExecStart`, `ExecStop`, `Restart` e `WantedBy` (`src/jobot/sistema/segundo_plano_linux.py:118-139`). Dentro da distrobox, os comandos ao sistema de fora passam por `distrobox-host-exec` (`src/jobot/sistema/caso.py:12-13`).

Banco e migrações

- A `dev` atual tem as migrações até `0006_ocorrencia_fonte_vaga.sql` (0.2.1, só um índice), passando por `0005_filtros.sql`; depois da `0001_inicial.sql`, só a `0004_motivo_da_parada.sql` mexe em `execucao` (`:4-5`). As novas da fase 2 são a 0007 e a 0008, contra essa `dev`.
- `migrar._aplicar` desliga `foreign_keys` antes do `BEGIN`, roda a migração num `executescript`, confere `PRAGMA foreign_key_check` antes do `COMMIT` e religa no fim (`src/jobot/banco/migrar.py:66-88`); o comentário explica que, sem isso, o `DROP TABLE` de uma reconstrução apagaria os filhos em cascata (`:67-68`).
- `saude.execucao_id` aponta para `execucao(id)` com `ON DELETE CASCADE` (`0001_inicial.sql:50`), e `execucao_fonte.execucao_id` também (`src/jobot/banco/migracoes/0003_execucao_fonte.sql:3`).

Gravação

- `gravar_escopo(con, execucao_id, saida, tratadas, agora)` grava saúde, validadores, vagas, ocorrências, locais, cache de detalhe e ciclo de vida do escopo numa transação só (`src/jobot/banco/gravacao.py:290-424`, transação em `:311`). Recebe uma `SaidaEscopo(fonte, escopo, resultado, duracao_ms, validadores, urls_vistas, urls_sem_detalhe, detalhes)` (`src/jobot/nucleo/coletores/executor.py:80-89`), com `ResultadoEscopo(vagas, estado, motivo, pedidos)` (`src/jobot/nucleo/coletores/base.py:65-70`).
  - Os validadores só entram no `cache_http` com estado `ok` ou `sem_mudanca` (`gravacao.py:38`, `:329-335`).
  - Vaga que já tem ocorrência no escopo mantém a descrição antiga quando a nova vem sem ela (`:349`).
  - Cada URL de `urls_sem_detalhe` vira uma linha de `enriquecimento` com conteúdo vazio (`:386-391`): "detalhe tentado, nada veio". No executor público, essas são as URLs cujo `detalhar` devolveu `None` (`executor.py:347-348`).
  - As `urls_vistas` contam como vistas no ciclo de vida, mesmo sem vaga (`gravacao.py:393-415`); só uma URL que casa com uma ocorrência do escopo muda alguma coisa (`:401`, `:418`).
- `gravar_cache_detalhe(con, ocorrencia_id, url, detalhe, agora)` grava o detalhe (quando há) e a tentativa no `enriquecimento` numa transação só (`src/jobot/banco/gravacao.py:454-475`, com `_gravar_detalhe` em `:478-490`); a busca a importa (`src/jobot/agenda/execucao.py:36-41`).
- `fechar_escopos_extintos(con, fonte, escopos_vivos, agora)` marca como sumidas as ocorrências abertas dos escopos que não estão em `escopos_vivos` (`src/jobot/banco/gravacao.py:427-445`).

Pasta de dados

- `preparar_pasta` força 0700 nas pastas e 0600 nos arquivos, recursivamente, por `os.walk` (`src/jobot/sistema/pastas.py:32-40`), e roda a cada `serve` (`src/jobot/cli/servir.py:57-63`). Não segue symlink (`pastas.py:24-25`). Não há pasta de perfil de navegador.

Coletores, fontes, saúde e ciclo de vida

- O contrato `Coletor` é só HTTP: `coletar(escopo, http: HttpEducado)` (`src/jobot/nucleo/coletores/base.py:84-98`). `LimitesDaFonte.ligada_padrao` já existe e só vale ao criar a linha (`base.py:80`).
- O `ContextoColeta` que os coletores recebem tem `empresas`, `termos` e `paises`; não tem cidade (`src/jobot/nucleo/coletores/base.py:31-35`; montado em `src/jobot/agenda/execucao.py:172-176`). As cidades existem na busca salva (`busca.cidades`, `0001_inicial.sql:130`), mas só servem para tirar os países (`paises_das_buscas`, `src/jobot/banco/buscas.py:217-224`).
- `VagaColetada.escopo` é obrigatório (`src/jobot/nucleo/modelo.py:135`).
- A tabela `fonte` aceita só `leva IN ('A','B')` (`0001_inicial.sql:6`); `semear` cria a linha com `ligada` do `ligada_padrao` e nunca sobrescreve a escolha da pessoa (`src/jobot/banco/cadastros.py:85-101`).
- A busca pública só roda fontes que têm coletor registrado e grava "desligada", escopo `''`, para as desligadas (`src/jobot/agenda/execucao.py:168-171`).
- Depois de coletar, a busca chama `fechar_escopos_extintos` por fonte, e pula a fonte cujo `escopos()` quebrou (`src/jobot/agenda/execucao.py:212-217`).
- A tela de andamento considera que a coleta acabou quando toda fonte ligada tem linha em `execucao_fonte` (`src/jobot/banco/execucoes.py:254-260`). Uma fonte com login ligada, que a busca pública não roda, faria `coleta_acabou` nunca virar verdade.
- A saúde aceita os estados `ok`, `sem_mudanca`, `parcial`, `falhou`, `desligada`, `no_limite` (`0001_inicial.sql:53`), com `motivo` em chave de i18n (`:57`). Gravar a saúde avulsa é `gravar_saude(...)` com `ON CONFLICT DO UPDATE` (`src/jobot/banco/execucoes.py:166-194`). Linha da fonte inteira tem escopo `''` (`registros/padroes.md:57`).
- O catálogo dos motivos `saude.*` fica em `src/jobot/painel/i18n/pt/comum.json:75-90` (e o par em inglês). Já existem `saude.formato_mudou` (`:75`), `saude.zero_inesperado` (`:76`), `saude.bloqueio` ("A fonte bloqueou o acesso", `:80`), `saude.parou_429` (`:84`) e `saude.listagem_incompleta` (`:90`). Nenhum fala de login nem de CAPTCHA.
- Padrões da fase 1 para leitura (`registros/padroes.md`): lista não vazia sem vaga legível é `falhou` com `saude.formato_mudou`, lista vazia é `ok` (`:52`); entrada sem o campo esperado é `parcial` com `saude.formato_mudou` e nenhuma legível é `falhou` (`:64`); lista paginada que pode ter vindo incompleta nunca é `ok` (`:61`).
- "Zero inesperado": escopo `ok` sem nenhum item, quando as três últimas execuções `ok` dele trouxeram vagas (`tres_ultimas_ok_trouxeram_vagas`), vira `parcial` com `saude.zero_inesperado` (`src/jobot/nucleo/coletores/executor.py:357-363`, DR-10).
- Ciclo de vida: escopo `ok` fecha o que não foi visto; `parcial` só fecha o que não é visto há mais de 30 dias (`JANELA_PARCIAL`, `src/jobot/nucleo/tratamento/ciclo_de_vida.py:7`, `:37-38`); `falhou`, `desligada` e `no_limite` não mudam nada (`:34-35`).
- Cada escopo é gravado por `gravar_escopo` depois de `tratar` (`src/jobot/agenda/execucao.py:179-182`).
- Detalhe com cache: a tabela `enriquecimento` guarda quando cada URL teve o detalhe tentado; a janela é de 30 dias (`JANELA_DETALHE`, `src/jobot/banco/execucoes.py:32`). `HistoricoDoBanco.detalhe_recente` diz quais URLs ainda estão dentro dela, e o cache é por URL, de qualquer fonte (`:385-398`, em especial `:386`). `ultima_coleta(fonte, escopo)` dá o início da última execução que tentou o escopo, sem contar `no_limite` e `desligada` (`:362-369`).

Configurações

- `GRUPOS = ("fontes", "funcoes", "segundo-plano", "aparencia", "privacidade", "servicos")` (`src/jobot/painel/rotas/configuracoes.py:43`), com `_PARCIAIS` (`:54-61`), `_CONTEXTOS` (`:119-126`) e `_GRAVADORES` (`:274-281`). As abas saem de `GRUPOS` (`:134`). A aba "Fontes" lista todas as fontes da tabela, por leva (`:74-76`).

Captura de fixtures

- `scripts/capturar.py` se apresenta como o único script que fala com a rede de propósito (`scripts/capturar.py:1`). A limpeza é `limpar_pessoais` (`:224-229`) e a conferência é `achar_pessoais` (`:247-269`), funções dentro dele; não existem `scripts/limpar_pessoais.py` nem `scripts/achar_pessoais.py`. Redução a 5 itens e 50 KB (`:54-55`, `:389-397`), meta com `sha256` (`:569-577`), e nada gravado se sobrar dado pessoal (`:567-568`, `:581-582`). Nome de pessoa em texto livre não é achado: a primeira captura de cada fonte é lida por gente (`:10-11`).

## 5. O como, Parte A (sem o dono, construível agora)

### A1. Dependência e navegador

- O Playwright 1.65.1 passa do grupo `dev` para as dependências de execução, com a mesma versão e `==` (D132.1). O `pytest-playwright` fica no `dev`. Não é pacote novo; a licença (Apache-2.0) já foi conferida (`2026-11-13-fase-1-design.md:1498`). O pacote Python é pequeno; o Chromium, à parte, passa de 100 MB (`:1498`).
- O pacote Python do Playwright não traz navegador. O joBot usa o Chrome instalado (`channel="chrome"`); sem ele, o Chromium do Playwright (D132.2).
- Na `fedora-dev` do dono não há Chrome (seção 4), e o Chrome do sistema de fora não serve: o transporte por pipe exige que o processo do navegador seja filho do Playwright, e isso não passa pelo `distrobox-host-exec`. Então, no caso do dono, o caminho real é o Chromium do Playwright dentro do container (D132.24; ver a seção 10).
- Na Parte A, o joBot não baixa navegador (D132.24). Ele usa o Chromium que o Playwright já tem instalado, o mesmo de `uv run playwright install chromium` na máquina de quem desenvolve e no CI (`.github/workflows/ci.yml:35`). Sem Chrome e sem Chromium, cada site ligado fica com `saude.sem_navegador`.
- O botão "Baixar o navegador" (download do Chromium pelo joBot) entra só na Parte B, no lote do primeiro site, junto com o texto de privacidade que cita esse caminho de rede (seção 6).
- Biblioteca de sistema faltando (comum em container): a falha ao abrir o navegador também vira `saude.sem_navegador`. O painel mostra uma frase fixa e a sugestão de instalar as bibliotecas pelo gerenciador de pacotes do sistema; a mensagem do Playwright vai só ao log (D132.55; `registros/padroes.md:46`).

### A2. Camadas e pacote novo

- Pacote novo `src/jobot/navegador/`: a única camada que importa `playwright` e a única, além do `painel`, que pode importar `jobot.nucleo.captcha` (D132.4). O orquestrador da execução `login` mora aqui (D132.39).
- A leitura das páginas fica pura em `src/jobot/nucleo/leitores/`: um módulo por site, mais `base.py` (o protocolo) e `registro.py` (a lista de leitores) (D132.4).
- Quem pode importar o quê (D132.4, D132.39):
  - `navegador` importa `nucleo`, `banco` e `sistema`; nunca `painel`, `agenda` nem `cli`.
  - `painel` e `cli` podem importar `navegador`; `nucleo`, `banco`, `agenda` e `sistema` não.
  - Passam da agenda para `banco` (por exemplo `banco/execucoes.py`), e a agenda importa de lá:
    - os ajudantes de execução que só mexem no banco: `parada_de`, `interromper` e o batimento assíncrono (`src/jobot/agenda/execucao.py:112-157`). O batimento ganha outro nome, porque `banco/execucoes.py` já tem o `bater` síncrono (`:104-110`);
    - a consulta das candidatas a detalhe (`src/jobot/agenda/execucao.py:270-291`), que passa a servir às duas leituras (seção A7).
  - O construtor procura todos os chamadores antes de mover (`registros/padroes.md:19`).
  - A agenda não chama o navegador: o `cli/servir.py` monta a tarefa `login` (uma função que abre a sua conexão e chama o orquestrador do `navegador`) e a põe no mapa `tarefas` que entrega ao laço, como já faz com busca, descoberta e páginas (`src/jobot/cli/servir.py:149-156`).
- Regras novas em `tests/unidade/test_camadas.py` (D132.4):
  1. `PROIBIDOS_NO_NUCLEO` (`test_camadas.py:7-16`) ganha `playwright` e `jobot.navegador`.
  2. Nenhum módulo fora de `src/jobot/navegador/` importa `playwright`.
  3. `jobot.nucleo.captcha` só é importado por `navegador`, `painel` e pelo próprio módulo. O teste atual, que lista pastas proibidas (`:78-82`), vira uma lista de pastas permitidas; antes de trocar, o construtor confere que nada mais o importa hoje.
  4. `nucleo`, `banco`, `agenda` e `sistema` não importam `jobot.navegador`.
  5. `navegador` não importa `jobot.painel`, `jobot.agenda` nem `jobot.cli`.
  6. Cada regra tem o seu teste do detector com pasta temporária, como `test_detector_acha_import_do_captcha` (`:85-87`).

### A3. Perfil do navegador

- Pasta própria `<pasta de dados>/navegador/`, criada com 0700, e um contexto persistente só, para todos os sites (D132.3). Nunca o perfil do Chrome do dia a dia.
- `preparar_pasta` (`src/jobot/sistema/pastas.py:36-38`) para de descer em `navegador/`: fecha a pasta em 0700 e não percorre o que está dentro, porque o Chrome cria os arquivos com as permissões dele (D132.3). Teste: um arquivo 0644 dentro de `navegador/` continua 0644 depois de `preparar_pasta`, e a pasta continua 0700.
- Antes de cada abertura, o joBot grava no arquivo de preferências do perfil (`Default/Preferences`, JSON) `credentials_enable_service = false`, `profile.password_manager_enabled = false` e `autofill.profile_enabled = false`, mantendo o resto do arquivo (D132.43). É arquivo de configuração, não argumento de linha de comando (que A7 proíbe). Arquivo torto: o joBot o reescreve só com essas três chaves e loga o fato, sem o conteúdo. Gravação em `.tmp` no mesmo diretório e `os.replace` (`registros/padroes.md:31`). Teste: perfil vazio, perfil com outras chaves (preservadas) e arquivo torto.
- O perfil é dado sensível (D132.22): nenhum caminho de dentro dele, cookie ou cabeçalho vai ao log; nenhuma exportação ou cópia do joBot o leva (a cópia antes de migrar, DR-06, copia só o banco); o painel nunca o serve.
- "Esquecer logins" apaga a pasta inteira (D132.21; seção A9). É o único jeito de sair; as vagas no banco não mudam.

### A4. O contrato do leitor (núcleo, puro)

Protocolo novo `LeitorComLogin`, separado do `Coletor` (D132.5). Assinaturas (os nomes finais são do construtor):

- `chave: str`: termina em `_logado`, por exemplo `gupy_logado` (D132.20).
- `nome: str`, `hosts: tuple[str, ...]`.
- `url_login: str`, `url_entrada: str`.
- `prefixos_login: tuple[str, ...]`: host e caminho das páginas de login do site e do login único (SSO) que ele usa, `url_login` inclusive (D132.37).
- `respostas: tuple[str, ...]`: padrões das URLs das respostas a capturar. Preferir o JSON que a própria página pede às APIs internas, capturado pelo evento `response` da página, ao HTML (D132.5; mesma ordem de preferência da DR-16, `2026-11-13-fase-1-design.md:1548`).
- `campos_conta: tuple[str, ...]`: posições (nomes de campo JSON ou seletores CSS) onde o site põe o nome e os dados da conta da pessoa (nome, id de usuário, de perfil, e-mail da conta). Só a captura de fixtures os usa (seção A10; D132.53). São posições, nunca valores.
- `escopos(ctx: ContextoColeta) -> Sequence[EscopoLogado]`, com `EscopoLogado(id: str, url: str)`; o `id` vai para a coluna `escopo` da saúde e para `VagaColetada.escopo`. Os escopos vêm das buscas da pessoa: termos × países do `ContextoColeta` (`src/jobot/nucleo/coletores/base.py:31-35`), cada par mapeado para a busca do site. O leitor pode somar escopos próprios do site, como "vagas recomendadas" (D132.34).
  - O `ContextoColeta` não tem cidade; as cidades estão em `busca.cidades` (`0001_inicial.sql:130`) e hoje só viram países (`src/jobot/banco/buscas.py:217-224`). Levar as cidades ao `ContextoColeta` mexe no contrato dos coletores: é R4, vai ao `duvidas.md` antes (D132.35).
- `e_login(captura: Captura) -> bool`: a página é de login para este site, além da regra geral do navegador (D132.37; seção A7).
- `pagina_logada(html: str, url: str) -> bool`.
- `pagina_bloqueada(html: str, url: str) -> bool`: página de bloqueio ou de "atividade incomum" própria do site (D132.30).
- `proxima(captura: Captura) -> str | None`: endereço da próxima página da lista, se houver (D132.34).
- `rolar: bool`: a lista carrega mais itens ao rolar (D132.16).
- `ler(captura: Captura, escopo: EscopoLogado) -> Leitura`, puro, com `Leitura(vagas: tuple[VagaColetada, ...], pulados: int, formato_mudou: bool)` (D132.36). Cada vaga sai com `escopo = escopo.id` (`src/jobot/nucleo/modelo.py:135`). Segue os padrões da fase 1 (`registros/padroes.md:52`, `:61`, `:64`):
  - lista não achada na página (nem vazia legível): `formato_mudou = True`;
  - lista com itens e nenhum legível: `formato_mudou = True`;
  - item fora do formato no meio de itens bons: pulado e contado em `pulados`;
  - lista achada e vazia: `Leitura((), 0, False)`.
  - O resultado em vez de exceção segue o `ResultadoEscopo` dos coletores (`src/jobot/nucleo/coletores/base.py:65-70`); o `_FormatoMudou` citado em `registros/padroes.md:35` é privado de um coletor de XML, não contrato.
- `lista_tem_descricao: bool`: a lista já traz a descrição inteira de cada vaga (D132.32).
- `detalhar(captura: Captura, vaga: VagaColetada) -> VagaColetada | None`, opcional, puro: lê a página da própria vaga e devolve a vaga com a descrição. Só é chamado quando `lista_tem_descricao` é falso (D132.32).

Estado do escopo (D132.36): uma função pura no núcleo, por exemplo `estado_do_escopo(leituras, *, parada, cortada, tres_ok_com_vagas) -> (estado, motivo)`. Entradas:

- `leituras`: todas as `Leitura` das páginas do escopo;
- `parada`: motivo de parada da navegação no escopo, opcional, um de `precisa_login`, `bloqueio`, `captcha`, `no_limite`. Toda parada encerra o site nesta execução: os escopos seguintes dele não são visitados e não gravam saúde, como os que não couberam no teto (seção A7);
- `cortada`: a lista não foi até o fim, porque o teto acabou com `proxima` ainda presente ou porque a política de navegação recusou uma URL da lista (seção A7). Com pelo menos uma página do escopo lida, é `parcial`; sem nenhuma (a URL inicial do escopo foi recusada), é `falhou` (veja a precedência);
- `tres_ok_com_vagas`: o histórico do zero inesperado, calculado pelo navegador com `HistoricoDoBanco.tres_ultimas_ok_trouxeram_vagas` antes de chamar a função, que continua pura.

Precedência, de cima para baixo; a primeira que casa decide:

1. `parada`, na ordem `precisa_login` > `bloqueio` > `captcha` > `no_limite`: `precisa_login`, `bloqueio` e `captcha` dão `falhou` com `saude.precisa_login`, `saude.bloqueio` ou `saude.captcha`; `no_limite` dá `no_limite` com `saude.parou_429`. Nada fecha (`src/jobot/nucleo/tratamento/ciclo_de_vida.py:34-35`). As vagas das páginas lidas antes da parada são gravadas, a não ser que alguma página do escopo tenha `formato_mudou`: aí o estado continua o da parada, mas nenhuma vaga do escopo é gravada.
2. Alguma página com `formato_mudou`: `falhou` com `saude.formato_mudou`. As vagas das outras páginas do mesmo escopo não são gravadas, e nada fecha.
3. `cortada`: com pelo menos uma página do escopo lida, `parcial` com `saude.listagem_incompleta` (`registros/padroes.md:61`); sem nenhuma página lida (a URL inicial do escopo recusada pela política), `falhou` com `saude.listagem_incompleta`, e nada fecha.
4. Algum item pulado (`pulados > 0`): `parcial` com `saude.formato_mudou` (`registros/padroes.md:64`).
5. Lista lida até o fim, sem item e sem pulado, com `tres_ok_com_vagas`: `parcial` com `saude.zero_inesperado`, a mesma regra e a mesma chave da fase 1 (`src/jobot/nucleo/coletores/executor.py:357-363`; `comum.json:76`).
6. O resto: `ok` (lista vazia inclusive, `registros/padroes.md:52`).

Um teste por caso (seção 8).

Dados que o navegador entrega ao leitor (dataclasses imutáveis no núcleo):

- `RespostaCapturada(url: str, status: int, tipo: str, texto: str)`.
- `Captura(url: str, status: int, html: str, respostas: tuple[RespostaCapturada, ...])`.

A `VagaColetada` sai com `fonte = chave` (`gupy_logado`) e com a URL canônica da vaga no site. Assim ela cai nas mesmas tabelas, e o tratamento junta com a mesma vaga vinda da fonte pública quando a URL canônica é a mesma (D132.20). Onde a URL difere (ou não há fonte pública do site), vira uma vaga a mais, com a própria ocorrência.

Testes: cada leitor com fixtures capturadas por nós (Parte B); o protocolo, a precedência e um leitor de exemplo do site falso (seção 8) na Parte A.

### A5. Fontes com login no banco

- Cada site com login é uma fonte, com linha na tabela `fonte` e chave própria (D132.20). A linha nasce desligada: `ligada_padrao = False` (`src/jobot/nucleo/coletores/base.py:80`; ADR 0005, `:41`). O liga/desliga do site é o `ligada` dessa linha (D132.8).
- A tabela `fonte` só aceita leva `A` ou `B` (`0001_inicial.sql:6`) e não diz se a fonte tem login. Migração 0008 (por exemplo `0008_fonte_com_login.sql`): coluna `com_login INTEGER NOT NULL DEFAULT 0 CHECK (com_login IN (0,1))` por `ALTER TABLE ADD COLUMN`, sem reconstruir a tabela (D132.46). A leva de uma fonte com login é `A` por convenção e não aparece em lugar nenhum.
- As fontes com login são semeadas a partir do registro de leitores, não do `fontes.json` (D132.46), com o mesmo `INSERT ... ON CONFLICT(chave) DO UPDATE` de `semear` (`src/jobot/banco/cadastros.py:96-101`), que nunca troca o `ligada` escolhido.
- Onde a fonte com login aparece: na saúde das fontes, sim (com os motivos novos); na aba "Fontes" de Configurações, não (`configuracoes.py:74-76` passa a filtrar `com_login`). O liga/desliga dela fica no grupo "Sites com login".
- `execucao_atual` passa a ignorar fontes com login no cálculo de `coleta_acabou` (`src/jobot/banco/execucoes.py:254-260`), senão o andamento da busca pública nunca acaba (D132.46). Teste: com uma fonte com login ligada, a busca pública termina e `coleta_acabou` vira verdade.
- Tipo de execução novo `login` (D132.6). O `CHECK` de `execucao.tipo` (`0001_inicial.sql:38`) não aceita esse valor: migração 0007 (por exemplo `0007_execucao_login.sql`) que reconstrói a tabela `execucao` (D132.47):
  - ordem fixa: criar `execucao_nova` com o `CHECK` novo e todas as colunas atuais, inclusive `parada` com o `CHECK` de `0004_motivo_da_parada.sql:4-5`; copiar as linhas; `DROP TABLE execucao`; `ALTER TABLE execucao_nova RENAME TO execucao`; recriar o índice `execucao_uma_por_tipo` (`0001_inicial.sql:47`). Nunca renomear a velha primeiro: o SQLite reescreveria as chaves estrangeiras de `saude` e `execucao_fonte` para o nome velho;
  - `saude` (`0001_inicial.sql:50`) e `execucao_fonte` (`0003_execucao_fonte.sql:3`) apontam para `execucao` com `ON DELETE CASCADE`; o `DROP` só não as apaga porque `migrar._aplicar` desliga `foreign_keys` e confere `foreign_key_check` no fim (`src/jobot/banco/migrar.py:66-88`);
  - `Tipo` em `src/jobot/banco/execucoes.py:25` e `TIPOS` em `src/jobot/cli/servir.py:49` acompanham;
  - testes (lendo só o arquivo da migração, `registros/padroes.md:6`): banco com execuções antigas migra sem perder linha; `saude` e `execucao_fonte` têm o mesmo número de linhas antes e depois; `tipo='login'` passa a ser aceito; o `CHECK` de `parada` continua valendo; o índice único continua valendo.
- Motivos da saúde da leitura com login (D132.7, D132.45): as quatro chaves novas são todas `falhou`; as reaproveitadas seguem a precedência da seção A4 (`no_limite` para `parou_429`; `parcial` para `listagem_incompleta`, `zero_inesperado` e `formato_mudou` com itens pulados; `falhou` para `bloqueio`, para `formato_mudou` quando uma página perdeu o formato e para `listagem_incompleta` quando nenhuma página do escopo foi lida).
  - novas (chave nova é R4, `registros/padroes.md:32`, por isso listadas na D132): `saude.precisa_login`, `saude.captcha`, `saude.sem_tela`, `saude.sem_navegador`. Textos em pt e en; o teste que percorre o conjunto de motivos nos dois idiomas acompanha;
  - reaproveitadas: `saude.bloqueio` ("A fonte bloqueou o acesso", `comum.json:80`) para bloqueio do site, `saude.formato_mudou` (`:75`), `saude.zero_inesperado` (`:76`), `saude.parou_429` (`:84`) e `saude.listagem_incompleta` (`:90`).
- Falha do site inteiro (`precisa_login`, `sem_tela`, `sem_navegador`, `bloqueio` na entrada) grava uma linha de saúde com escopo `''` (`registros/padroes.md:57`). Site com login desligado grava `desligada` com escopo `''`, como as fontes públicas (`src/jobot/agenda/execucao.py:170-171`) (D132.51).

### A6. Agenda: horários de parede

- Configuração `login_horarios`, padrão `["09:00", "18:00"]` no horário local, em `cadastros.PADROES` (`src/jobot/banco/cadastros.py:34-48`) (D132.6; ADR 0005, `:24`; ADR 0006, `docs/decisions/0006-agenda-e-segundo-plano.md:16`).
- Valor aceito: de 1 a 4 horários `HH:MM`, sem repetição, com pelo menos 4 horas entre um e outro (D132.48). Valor torto volta com mensagem, sem gravar e sem 500.
- `ultima` (D132.6, D132.25): o início da última execução `login` em qualquer estado final, `concluida` ou `interrompida`, por uma consulta nova em `banco`, irmã de `inicio_da_ultima_completa` (`src/jobot/banco/execucoes.py:231-236`), que só conta as concluídas. Assim uma leitura que terminou em erro, ou que a pessoa interrompeu fechando o navegador, também segura as próximas: o site já foi visitado naquela hora. `ultima` no futuro (relógio que voltou, `src/jobot/agenda/agendador.py:45-47`) conta como nula.
- Regra única do horário (D132.6), numa função pura nova na agenda, por exemplo `login_vencido(agora, horarios, ultima) -> bool`:
  - `H` é a ocorrência mais recente de um dos horários que não passa de `agora` (hoje ou ontem, no dia local);
  - `H` vence só se `agora - H < 15 min` (janela de tolerância, para o laço de 60 s, a espera de 60 s ao iniciar e uma trava presa por pouco tempo), se nenhuma leitura com login começou em `[H, agora]` (`ultima` nula ou `ultima < H`) e, havendo `ultima`, se `H - ultima >= 4 h`.
- Horário perdido (joBot fechado ou máquina desligada durante toda a janela de `H`) é pulado, nunca recuperado. Isso troca, para a leitura com login, a regra da execução perdida que roda ao ligar (ADR 0006, `:26`); se o dono confirmar, a ADR 0006 ganha uma nota (D132.6, pergunta ao dono).
- Exemplos, todos testes (seção 8):
  - perdeu as 9h, ligou às 15h: não roda às 15h. Às 18h roda se a última leitura com login começou há 4 h ou mais (às 14h ou antes); senão (por exemplo, um "Buscar agora" às 15h30) a próxima é às 9h do dia seguinte;
  - a pessoa fechou o navegador às 9h02, na leitura das 9h (interrompida, parada `fechado`): não reabre às 9h03;
  - erro às 9h01 (interrompida, parada `erro`): não repete dentro da janela das 9h.
- `o_que_roda` (`src/jobot/agenda/agendador.py:50-78`) ganha o tipo `login`, com a mesma espera de 60 s ao iniciar (`:66-67`). O `Estado` (`:29-42`) passa a dizer se há algum site com login ligado, quais são os horários e a `ultima` acima; sem site ligado, `login` não roda.
- "Buscar agora" (D132.25): lê os sites com login se `agora - ultima >= 4 h`, com a mesma `ultima` (nula ou no futuro: pode).
- Com as duas regras, há sempre 4 horas ou mais entre os inícios de duas leituras com login, terminem como terminarem: no máximo 6 por dia (24 h ÷ 4 h), contando os cliques em "Buscar agora". A ADR 0005 fala em duas por dia (`:24`); o padrão continua duas, e o teto de 6 só vem dos cliques da pessoa e de até 4 horários. O "Buscar agora busca tudo" da ADR 0006 (`:17`) continua verdade, respeitando o intervalo mínimo como a própria ADR já prevê para as fontes com intervalo.
- `travas["login"]` é a trava do navegador: um objeto só em `app.state.travas`, criado junto com os outros (`src/jobot/cli/servir.py:123-125`) e usado pelo laço, pelo "Buscar agora", pelo "Fazer login agora" e pelo "Esquecer logins" (D132.18).
- "Buscar agora" (`src/jobot/painel/rotas/execucao.py:116-138`), além da busca de hoje (D132.41):
  - confere se há site com login ligado e a regra das 4 horas;
  - se sim e `travas["login"]` está livre, pega a trava e dispara a tarefa `login` com motivo `agora` em `app.state.tarefas`, como `_disparar` faz com a busca (`:100-113`), sem esperar;
  - a tela de andamento e `execucao_atual` continuam mostrando só a busca (`:75-76`); o estado da leitura com login aparece no grupo "Sites com login";
  - testes de cada ramo: sem site ligado, menos de 4 h, trava presa, dispara.
- Hora local: compara com o horário local do fuso da máquina (`agora.astimezone()`), como o resto do projeto (`src/jobot/nucleo/captcha.py:329`; `src/jobot/cli/servir.py:78`; `registros/padroes.md:13`). Testes com relógio injetado e fuso fixo, inclusive um caso fora de UTC.
- A agenda continua parada antes da primeira execução concluída (`src/jobot/cli/servir.py:95-101`).

### A7. O navegador (camada `navegador`)

Abrir

- `launch_persistent_context` com a pasta `navegador/`, `channel="chrome"` primeiro, depois o Chromium do Playwright; nada de `headless`, sem argumento extra de linha de comando, sem `--remote-debugging-port` (D132.2, D132.3, D132.17). Antes, as preferências do perfil da seção A3 (D132.43).
- O lançador entra por injeção. Produção: sempre visível. Testes: o teste pede sem tela explicitamente; um teste de unidade confere que a montagem de produção abre visível e sem argumento de depuração.
- User agent: o do próprio Chrome, sem troca (D132.15). O user agent do `Desafio` sai sem JavaScript: do cabeçalho `user-agent` de qualquer pedido da página (é o mesmo para todos), lido pelo evento `request` com `headers` (nunca `all_headers`, que traz cookie). Se isso não servir na versão instalada, um terceiro script literal em `navegador/js.py`, `() => navigator.userAgent` (D132.38). Usar o user agent do Chrome contraria a regra de coleta educada do `CLAUDE.md` do projeto ("user agent fixo do joBot") e depende do ok do dono (seção 11).

Tela

- Antes de abrir, o navegador confere `DISPLAY` ou `WAYLAND_DISPLAY` (D132.9). O serviço do systemd pode subir antes de a sessão gráfica exportar essas variáveis. Então, sem elas no ambiente do processo, o joBot lê `systemctl --user show-environment` (pelo `distrobox-host-exec` dentro do container, `src/jobot/sistema/caso.py:12-13`) e usa de lá só `DISPLAY`, `WAYLAND_DISPLAY`, `XAUTHORITY` e `XDG_RUNTIME_DIR`, só para o processo do navegador (D132.50).
- Validação (D132.50): `DISPLAY` no formato `[host]:n[.n]`; `WAYLAND_DISPLAY` um nome sem `/` ou um caminho absoluto; `XAUTHORITY` e `XDG_RUNTIME_DIR` caminhos absolutos que existem. Valor fora disso é ignorado. A saída crua do comando nunca vai ao log; o log leva só quais variáveis foram aceitas (`registros/padroes.md:46`). Teste com um SEGREDO na saída do executor falso: ele não aparece no `caplog` nem no ambiente do navegador.
- Ainda sem tela: `saude.sem_tela` em cada site ligado, sem modo escondido.
- O comando passa pelo executor injetado, como no segundo plano (`src/jobot/sistema/segundo_plano_linux.py:31`, `:64-79`). Isso mora em `sistema`, e o navegador recebe o ambiente pronto.
- O teste em máquina real (Wayland do Silverblue, dentro da `fedora-dev`, com o serviço do systemd) é do dono (D132.9).

Política de navegação (D132.42)

- Entra por injeção. A montagem de produção é fixa: só `https`, só os `hosts` do leitor, recusa host local por `host_local` (`src/jobot/nucleo/coletores/base.py:47`, importado de `nucleo/http.py`). Os testes injetam a política que aceita o site falso em `127.0.0.1`.
- Teste de unidade da montagem de produção: recusa `http://`, `127.0.0.1` e host fora da lista; aceita `https` de um host do leitor.
- Vale para todo endereço que o joBot manda abrir: `url_entrada`, URL de escopo, `proxima` e URL de vaga para o detalhe. Recusado: não é visitado e o log leva só o host. Uma `proxima` recusada depois de pelo menos uma página lida faz o escopo `cortada`: `parcial` com `saude.listagem_incompleta`. A URL inicial do escopo recusada (nenhuma página lida): `falhou` com `saude.listagem_incompleta`, e nada fecha (seção A4). Uma URL de vaga recusada só não é detalhada.
- Depois de cada navegação, o host de `page.url` é conferido de novo (o site pode ter redirecionado): fora dos `hosts`, se casa com `prefixos_login` vira a parada `precisa_login`, senão a parada `bloqueio`. Só captura e lê dentro dos `hosts`.
- Recursos de terceiros que a página carrega sozinha (imagens, scripts) não são bloqueados: bloquear quebraria o site e seria mexer na página.

Tetos por site, em cada execução (D132.19)

- No máximo 30 navegações por site: até 10 páginas de lista, somando todos os escopos, e até 20 páginas de vaga (detalhe, D132.32).
- Entre uma navegação e outra, espera de 3 a 8 s, sorteada por um gerador injetado e dormida pelo relógio injetado. Vale também para as páginas de vaga.
- Rodízio dos escopos (D132.34): primeiro o escopo visitado há mais tempo, pela última linha de saúde do escopo (`HistoricoDoBanco.ultima_coleta`, `src/jobot/banco/execucoes.py:362-369`); escopo nunca visitado vem antes. Escopo que não coube no teto não grava linha de saúde nesta execução, e o estado anterior dele fica.

Ordem das checagens depois de cada navegação (D132.30, D132.37, D132.44)

1. Host: a conferência de `page.url` da política acima.
2. Login: a página é de login se tem `input[type=password]`, se `e_login(captura)` do leitor diz que sim, ou se host e caminho casam com `prefixos_login`. Página de login vira a parada `precisa_login` (escopo `''` na entrada, a do escopo no meio da lista) e o site para nesta execução. Nada é injetado numa página de login, e o 2Captcha não é chamado, mesmo com CAPTCHA nela.
3. Desafio gerenciado do Cloudflare ("Just a moment", com ou sem o iframe do Turnstile): espera até 30 s que ele saia sozinho, sem tocar na página. Saiu: segue. Não saiu: janela parada, sem 2Captcha (seção A8).
4. Página de desafio: página que passou pelas checagens 2 e 3 e traz um widget reconhecido (reCAPTCHA v2, inclusive invisível, ou Turnstile avulso), qualquer que seja o status da resposta (200, 403, 429). Segue o caminho do CAPTCHA (seção A8); se não for resolvido, a parada é `captcha`.
5. Só quando não há CAPTCHA reconhecido: 401, 403 ou página que `pagina_bloqueada` reconhece viram a parada `bloqueio`, e o site para nesta execução. 429: respeita `Retry-After` com o mesmo teto da fase 1; se repetir, a parada `no_limite` (`saude.parou_429`), e o site também para nesta execução: os escopos seguintes dele não são visitados e não gravam saúde, como os que não couberam no teto.

Uma execução `login`

1. Abre a execução `login` (`abrir_execucao`, `src/jobot/banco/execucoes.py:83-101`) e o batimento, como a busca (`src/jobot/agenda/execucao.py:81-85`), com os ajudantes já movidos para `banco` (seção A2).
2. Pega a trava do navegador (veja "Concorrência" abaixo) e abre o contexto. Sites com login desligados ganham `desligada` com escopo `''` (D132.51).
3. Para cada site ligado, na ordem do registro, numa aba nova:
   - vai à `url_entrada` e passa pela ordem das checagens acima; se `pagina_logada` é falsa: `saude.precisa_login` com escopo `''` e passa ao próximo site (ADR 0005, `:42`);
   - chama `escopos(ctx)`; se quebrar, grava `falhou` com escopo `''` e passa ao próximo site;
   - para cada escopo, na ordem do rodízio, enquanto houver teto e o site não tiver parado: navega à URL, passa pelas checagens, espera a página assentar, rola se `rolar`, junta as respostas que casam com `respostas`, monta a `Captura` e chama `ler(captura, escopo)`; segue por `proxima` dentro do teto de 10 páginas de lista, acumulando as `Leitura` do escopo;
   - estado do escopo pela função pura da seção A4, com a parada (se houve), `cortada` e `tres_ok_com_vagas` lido do `HistoricoDoBanco` (D132.33, D132.36);
   - gravação do escopo (D132.36): uma chamada a `gravar_escopo` por escopo, numa transação (`src/jobot/banco/gravacao.py:290-424`), depois de `tratar`, como a busca (`src/jobot/agenda/execucao.py:179-182`). A `SaidaEscopo` (`src/jobot/nucleo/coletores/executor.py:80-89`) leva:
     - `resultado = ResultadoEscopo(vagas, estado, motivo, pedidos)`, com as vagas que a precedência manda gravar e `pedidos` = navegações do escopo;
     - `validadores = {}`: o navegador não faz pedido condicional (`gravacao.py:329-335` não grava nada);
     - `urls_vistas`: as URLs das páginas de lista visitadas no escopo. Pelo `gravacao.py:393-418`, só uma URL que casa com ocorrência do escopo mexe no ciclo; as das vagas lidas já estão nas `tratadas`;
     - `urls_sem_detalhe = ()`: no executor público, essa lista grava `enriquecimento` vazio, "tentado, nada veio" (`gravacao.py:386-391`). Na leitura com login o detalhe vem depois, pela `gravar_cache_detalhe`; pôr ali a vaga que o teto não deixou abrir a marcaria como tentada e a esconderia por 30 dias;
     - erro num site não para os outros (ADR 0004, `:46`);
   - escopos extintos (D132.40): se o site não parou na entrada e `escopos()` não quebrou, chama `fechar_escopos_extintos(con, chave, {todos os ids de escopos(ctx)}, agora)`, visitados ou não, como a busca (`src/jobot/agenda/execucao.py:212-217`; `src/jobot/banco/gravacao.py:427-445`). Assim a busca removida pela pessoa fecha, e o escopo pulado pelo teto não;
   - detalhe (D132.32), só se o leitor tem `lista_tem_descricao` falso, depois de gravar os escopos do site:
     - as candidatas saem da consulta que a busca usa hoje (`src/jobot/agenda/execucao.py:270-291`), extraída para `banco` e usada pelas duas leituras (D132.39): ocorrências abertas de vagas vistas pela primeira vez nos últimos 30 dias, sem descrição na ocorrência, as mais novas primeiro, sem as que têm detalhe tentado nos últimos 30 dias por `detalhe_recente`, que é por URL, de qualquer fonte (`src/jobot/banco/execucoes.py:385-398`, `:386`). Ela devolve o `ocorrencia_id` que `gravar_cache_detalhe` pede (`src/jobot/banco/gravacao.py:454-490`). A busca continua aplicando por cima os filtros dela (`rodaram`, `ja_detalhadas`, `:259-265`, `:282-285`); o navegador fica com as da fonte do site e dos escopos visitados nesta execução;
     - até 20 por site; cada página passa pela política, pelas checagens e por `detalhar`;
     - cada página aberta grava, numa transação, o detalhe (quando veio) e a tentativa, por `gravar_cache_detalhe(con, ocorrencia_id, url, detalhe, agora)`;
     - a vaga que o teto não deixou abrir não grava nada no cache e volta na próxima execução. A descrição já obtida não se perde quando a lista vem sem ela (`gravacao.py:349`).
4. Fecha o contexto, fecha a execução. Exceção no meio: `interromper` (seção A2).
5. A pessoa fechar o navegador no meio da execução: a execução é interrompida com a parada `fechado`, que já existe (`src/jobot/banco/execucoes.py:28`; `0004_motivo_da_parada.sql:4-5`) e já quer dizer "fechado antes do fim" (`src/jobot/agenda/execucao.py:112-115`); não há valor novo no `CHECK` (D132.51). Os escopos já gravados ficam, e a execução interrompida conta como `ultima` na regra do horário (seção A6).

Captura e log (D132.54)

- Captura: só respostas dos `hosts` do leitor, com tipo JSON ou HTML, no máximo 5 MB cada (o teto da fase 1, DR-11) e 50 por página; o resto é ignorado.
- Log: só host e caminho, nunca query, cookie, cabeçalho ou corpo.

Chamadas ao Playwright e JavaScript na página (D132.38)

- Lista permitida. Fora de `navegador/js.py`, um teste por AST, em todo o pacote `navegador`, reprova qualquer atributo usado sobre `Page`, `Frame`, `Locator`, `BrowserContext`, `Browser`, `APIRequestContext`, `Request` ou `Response` que não esteja na lista. O detector compara o nome do atributo com os métodos e propriedades dessas classes no Playwright instalado e reprova os que não estão na lista. Lista inicial (o construtor confirma os nomes no Playwright 1.65.1 instalado):
  - `launch_persistent_context` (do `BrowserType`), `new_page`, `pages`, `goto`, `wait_for_load_state`, `content`, `url`, `title`, `close`, `frames`;
  - `on` e `once`, só para os eventos `response` (captura), `request` (ler o cabeçalho `user-agent`) e `close` (a pessoa fechou o navegador); qualquer outro evento reprova;
  - `locator`, com `get_attribute`, `inner_text`, `count` e `all`;
  - `Request`: só `url` e `headers`;
  - `Response`: só `url`, `status`, `headers`, `text` e `body`.
  - `headers`, nunca `all_headers` nem `headers_array`, que trazem cookie.
- Proibidos em produção, sem exceção: `route`, `unroute`, `fulfill`, `page.request` e `context.request` (o `APIRequestContext` manda os cookies da pessoa), `all_headers`, `eval_on_selector`, `eval_on_selector_all`, `evaluate_all`, `evaluate_handle`, `wait_for_function`, `add_script_tag`, `add_init_script`, `expose_function`, `expose_binding`, `press_sequentially`, `clear`, `click`, `dblclick`, `tap`, `fill`, `type`, `press`, `check`, `uncheck`, `set_checked`, `select_option`, `set_input_files`, `hover`, `focus`, `dispatch_event`, `drag_and_drop`, tudo de `mouse` e de `keyboard`, e `evaluate` fora de `navegador/js.py`.
- `route` e `fulfill` só existem nos testes do site falso, fora do pacote (seção 8).
- Teste do próprio detector, numa pasta temporária: um exemplo ruim por categoria (ação na página, JavaScript fora de `js.py`, rota, pedido com os cookies, `all_headers`, evento fora da lista como `page.on("dialog", ...)`, atributo fora da lista) é pego, e um exemplo bom passa.
- Chamada nova na lista permitida só entra com teste e uma D nova.
- `navegador/js.py` é o único módulo que chama `page.evaluate`. Os scripts dele são literais fixos no código (sem f-string, `format` ou concatenação), e são todos estes:
  1. rolar a página;
  2. entregar o token (escrever no campo de resposta do widget e chamar a função de retorno);
  3. só se o cabeçalho não servir, ler o user agent: `() => navigator.userAgent`.
- O token e o nome da função de retorno entram como argumento do `evaluate`, nunca dentro do texto do script.
- O nome da função de retorno tem de casar com `^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$`. O script o resolve por busca de propriedade a partir de `window`, parte por parte, nunca por `eval` nem `Function`. Nome fora do padrão ou que não leva a uma função: não chama nada e segue o caminho da janela parada.
- Um segundo teste por AST confere que os scripts de `js.py` são literais e que não há outros.

Concorrência (D132.18)

- A trava do navegador é `travas["login"]` (seção A6), dividida entre a tarefa `login` da agenda, o "Buscar agora", o "Fazer login agora" e o "Esquecer logins". O `jobot.lock` já impede um segundo `serve` (desenho da fase 1, `:1178`).
- "Fazer login agora" com uma execução rodando: o painel diz "uma leitura está em andamento; tente de novo quando terminar" e não espera (D132.52). Execução da agenda com um login manual aberto: espera a trava na volta seguinte do laço (o laço já pula tipo travado, `src/jobot/agenda/agendador.py:124-125`), dentro da janela de 15 minutos do horário (seção A6).

Conexão com o banco

- A execução `login` abre a sua conexão, como as outras tarefas (`src/jobot/cli/servir.py:138-139`); a conexão não troca de thread nem se divide entre tarefas (`CLAUDE.md` do projeto, armadilhas).

### A8. CAPTCHA: a cola com o 2Captcha

- Achar: na checagem 4 da seção A7, só numa página de desafio (não é login, não é desafio gerenciado do Cloudflare), o navegador procura reCAPTCHA v2 (inclusive invisível) ou Turnstile avulso e lê a `sitekey`, a função de retorno declarada (`data-callback`) e, no Turnstile, a ação quando houver, por `locator(...).get_attribute` (D132.10; tipos da ADR 0022, `:24`, menos o v3, que fica fora da fase 2, seção 2).
- Se `captcha_pronto(con, chave)` (`src/jobot/banco/captcha.py:33-35`), com a chave lida do `Cofre` (`src/jobot/sistema/cofre.py:41`): monta o `Desafio` com a URL da página e o user agent real (seção A7; `src/jobot/nucleo/captcha.py:81-89`), chama `resolver` com `reservar = lambda dia: reservar_resolucao(con, dia)` (`src/jobot/banco/captcha.py:38-42`) e com o `ClienteEducado` do `serve`. Uma tentativa por página por execução (ADR 0022, `:29`). Um interruptor só para todos os sites, o da aba Serviços (D132.14).
- Injetar (D132.31; a exceção dos anti-objetivos, seção 2): pelo script fixo de `navegador/js.py` (seção A7), escreve o token no campo de resposta do próprio widget (`g-recaptcha-response` ou `cf-turnstile-response`) e, se o widget declarou `data-callback`, chama essa função com o token. Nunca clica, nunca envia formulário, nunca troca função do site. Depois espera até 30 s que a página saia do desafio.
- Se o Turnstile devolver um `user_agent` diferente do do navegador, o joBot não troca o do navegador (D132.56): tenta o token; se não passar, segue o caminho da janela parada.
- Desafio que volta (D132.30): se o mesmo desafio reaparece no mesmo site depois de um token aceito, na mesma execução, a parada é `bloqueio` (`saude.bloqueio`) e o site para nesta execução. É aqui que o site conta como "bloqueia automação" (D132.15).
- Desafio gerenciado do Cloudflare (D132.44, pergunta ao dono): segue a checagem 3 (30 s) e depois a janela parada, sem 2Captcha. O `Desafio` não leva `cData` nem `chlPageData` (`src/jobot/nucleo/captcha.py:81-89`), que esse desafio pede. O `turnstile.render` lembrado no desenho do 2Captcha (`2026-11-15-captcha-design.md:210`) fica descartado: seria trocar uma função do site. Isso estreita a ADR 0022 (`:24`), que aceita o Turnstile sem distinguir o avulso do que vem no desafio gerenciado: se o dono confirmar, a ADR 0022 ganha um reparo dizendo que a fase 2 só resolve o Turnstile avulso.
- Fora disso (v3 ou outro tipo, desafio gerenciado do Cloudflare que não saiu, `ErroCaptcha`, teto, interruptor desligado, chave ausente, página que não saiu do desafio em 30 s depois do token): `saude.captcha`, aviso vermelho no painel, aviso no computador e janela parada (ADR 0005, `:28-31`; D132.10).
- Janela parada (D132.26): a aba do site fica aberta na página do desafio, para a pessoa terminar, e a execução segue com os outros sites em abas novas. No fim, espera até 15 minutos no total, olhando todas as abas paradas ao mesmo tempo. Aba resolvida: continua aquele site, dentro do mesmo prazo. Ao fim dos 15 minutos, as que não foram resolvidas ficam com a parada `captcha`, o navegador fecha, e a próxima execução tenta de novo. Aba parada que a pessoa fecha encerra a espera daquele site: ele fica com `captcha` na hora, e as outras abas seguem no mesmo prazo.
- Aviso no computador: `notify-send` com título e uma frase curta, sem URL; dentro do container, por `distrobox-host-exec` (`src/jobot/sistema/caso.py:12-13`); sem `notify-send` no sistema, só o painel (D132.10). Mora em `sistema`, com executor injetado.
- Log: cada resolução já vai ao `jobot.log` com o custo e sem a chave (`src/jobot/nucleo/captcha.py:337-342`). A cola não leva ao log a chave, o token nem a URL com query.

### A9. O grupo "Sites com login" em Configurações

- Grupo novo `sites-com-login` em `GRUPOS` (`src/jobot/painel/rotas/configuracoes.py:43`), com parcial, contexto e gravador próprios (`:54-61`, `:119-126`, `:274-281`). Ele só aparece quando há pelo menos um leitor registrado (D132.23): sem leitor, a rota devolve 404 e a aba não é listada. As abas deixam de sair direto da tupla fixa (`:134`) e passam por esse filtro; o teste de abas acompanha.
- Conteúdo, de cima para baixo (D132.8):
  1. Uma frase do que é e do risco: ler sites com login pode ir contra os termos deles, e a conta pode ser restringida; a pessoa decide site por site; o joBot nunca digita senha e só lê.
  2. Estado do navegador: "Chrome encontrado", "Usando o Chromium do Playwright" ou "Nenhum navegador encontrado", com o que fazer. O botão "Baixar o navegador" entra aqui só na Parte B (seção 6).
  3. Um cartão por site: interruptor (nasce desligado), estado da última leitura com o motivo, se uma leitura está rodando agora (D132.41), e o botão "Fazer login agora".
  4. Horários das leituras (`login_horarios`, seção A6).
  5. "Esquecer logins".
- Visual: os mesmos componentes da aba Serviços, interruptor animado `.chave` com `role="switch"` e campos `.campo-texto`, sem controle padrão do HTML (desenho do 2Captcha, parte E). Todo POST com CSRF; o interruptor grava na hora.
- "Fazer login agora" (D132.52): POST que pega `travas["login"]`, abre o Chrome visível na `url_login` do site e só observa, conferindo `pagina_logada` a cada poucos segundos, por até 10 minutos. A pessoa digita; o joBot nunca preenche nada. Logou: fecha o navegador e o cartão mostra "Pronto". Não é execução e não lê vaga; a próxima leitura agendada lê. O painel acompanha pelo HTMX, como o andamento da busca.
- "Esquecer logins" (D132.21): o primeiro clique troca o botão por uma confirmação na própria página ("Apagar os logins de todos os sites?", com "Apagar" e "Cancelar"), sem diálogo do navegador; o segundo POST pega `travas["login"]`, apaga a pasta `navegador/` inteira e mostra "Logins apagados". Com uma leitura rodando, diz que está em andamento e não apaga. As vagas não mudam.
- Textos novos em pt e en.

### A10. Ferramenta de captura com login

`scripts/capturar_logado.py <leitor> --caso <nome>` (D132.12, D132.53), feita para a Parte B:

- Pega e segura a trava `jobot.lock` (`Trava` de `jobot.sistema.instancia`, importada em `src/jobot/cli/servir.py:43`) enquanto roda; com o joBot aberto, recusa, porque o perfil não aceita dois processos.
- Abre o Chrome visível com o perfil do joBot (com as preferências da seção A3) na `url_entrada`; a pessoa loga (se precisar) e navega; o script grava as respostas dos `hosts` do leitor que casam com `respostas` e a pessoa encerra no terminal. Sem leitor ainda, grava todo JSON e o HTML final dos hosts dados por `--host`, e as posições da conta vêm de `--campo`, repetível (nome de campo JSON ou seletor CSS).
- Nome e dado da conta se tratam pela posição, nunca pelo valor literal: a limpeza troca o que está nos campos ou seletores de `campos_conta` do leitor (ou de `--campo`, dado na hora). O nome real da pessoa nunca entra em código, teste ou fixture, nem como regra de limpeza; os testes usam um nome inventado.
- Primeiro limpa, depois confere (logado, o corpo pode trazer segredo da sessão):
  1. Limpeza: troca por um marcador fixo o valor de cada campo com `csrf` ou `xsrf` no nome, de cada JWT (texto que começa com `eyJ` e tem três partes separadas por ponto), de cada `JSESSIONID` e de cada posição de `campos_conta` (ou `--campo`). Os valores trocados ficam só na memória, durante a captura, para a conferência; nunca vão a arquivo nem ao log.
  2. `limpar_pessoais`, `reduzir` e `achar_pessoais`, importados de `scripts/capturar.py` (`:224`, `:389`, `:247`).
  3. Conferência: se ainda sobrar um JWT, um `JSESSIONID`, um campo `csrf` ou `xsrf` com valor diferente do marcador, um dos valores trocados no passo 1 em qualquer outro lugar do corpo (numa URL, num texto), ou dado pessoal, nada é gravado, como em `capturar` (`scripts/capturar.py:567-568`). A mensagem diz a posição ou o tipo do achado, nunca o valor.
- Meta: URL sem os valores da query (só os nomes dos parâmetros) e sem fragmento, sem cabeçalho de pedido, sem cookie, sem `Set-Cookie`; o resto como `CAMPOS_META` (`scripts/capturar.py:82`). O meta também passa pela limpeza e por `achar_pessoais` (`:581-582`).
- Grava em `tests/fixtures/<chave>/` e roda `problemas` na pasta (`scripts/capturar.py:403-429`).
- A docstring de `scripts/capturar.py:1` ("único script que fala com a rede") muda na mesma fatia, para citar o `capturar_logado.py`.
- Logado, a resposta pode trazer o nome da própria pessoa em texto livre, fora das posições conhecidas, e a limpeza não o acha (`scripts/capturar.py:10-11`). Por isso toda captura com login é lida por gente antes do commit; achou o nome, a posição dele entra em `campos_conta` (ou `--campo`) e a captura é refeita, nunca editada à mão.

### A11. Ordem de entrega sugerida (fatias testáveis)

Cada fatia entra verde e sem mudar nada visível na versão publicada (D132.23).

1. Dependência, camadas e banco base: Playwright para execução, pacote `navegador/` vazio, pacote `nucleo/leitores/` com o protocolo, `Leitura`, a função de precedência do estado do escopo e as dataclasses, regras novas do `test_camadas`, `preparar_pasta` sem descer em `navegador/`, ajudantes de execução e consulta das candidatas a detalhe movidos da agenda para `banco` (com a agenda importando de lá).
2. Banco: migração 0007 de `execucao.tipo` (ordem fixa), migração 0008 com a coluna `com_login`, a consulta da última leitura com login em qualquer estado final, semeadura pelo registro de leitores, `coleta_acabou` sem fontes com login, `login_horarios` em `PADROES`, os quatro motivos novos em pt e en.
3. Agenda e serve: `login_vencido` com a janela de 15 minutos e o horário pulado, tipo `login` no `o_que_roda`, regra das 4 h no "Buscar agora", `travas["login"]`, a tarefa `login` no mapa `tarefas` do `cli/servir.py`, "Buscar agora" disparando a leitura com login.
4. Navegador sem CAPTCHA: preferências do perfil, política de navegação, abrir (Chrome, Chromium já instalado, sem navegador), tela, `navegador/js.py` com o script de rolar, teste por AST da lista permitida, uma execução contra o site falso, captura, rolar, paginação, tetos e rodízio, espera, ordem das checagens (host, login, Cloudflare, bloqueio), estados do escopo, gravação com `gravar_escopo` e `gravar_cache_detalhe`, escopos extintos, detalhe com cache, pessoa que fecha o navegador.
5. Cola do CAPTCHA: achar, user agent pelo cabeçalho, `Desafio`, `resolver` com transporte falso, script de entrega do token, desafio que volta, desafio gerenciado do Cloudflare, janela parada, `notify-send`.
6. Painel: grupo "Sites com login" (visível só com leitor; nos testes, com o leitor do site falso registrado pelo teste), "Fazer login agora", "Esquecer logins", horários, estado do navegador.
7. `scripts/capturar_logado.py`, `campos_conta` no protocolo, `--campo`, e a docstring de `scripts/capturar.py`.

## 6. O como, Parte B (com o dono, um site por vez)

- Ordem: Gupy, LinkedIn, Vagas.com, Catho, Indeed, depois os demais (ADR 0005, `:16`; D132.12). A ADR 0005 tem a Gupy fora da lista do `:15`; ver a seção 11.
- Para cada site, numa sessão com o dono:
  1. O dono faz o login no perfil do joBot (pelo `capturar_logado.py`, que abre o mesmo perfil) e navega até a lista de vagas.
  2. A sessão captura com `scripts/capturar_logado.py`, lê cada arquivo e, se sobrar nome ou dado da conta, acrescenta a posição em `campos_conta` e captura de novo.
  3. TDD do leitor com as fixtures: `e_login`, `prefixos_login`, `campos_conta`, `pagina_logada`, `pagina_bloqueada`, `proxima`, `ler`, o mapeamento das buscas da pessoa para a busca do site (`escopos`) e, se a lista não traz a descrição, `detalhar`.
  4. O leitor entra no registro. Com o primeiro leitor, o grupo "Sites com login" passa a aparecer (D132.23).
  5. O dono testa na máquina real: liga o site, faz o login pelo botão, espera o horário (ou "Buscar agora"), confere as vagas e a saúde.
- Gupy primeiro: a Gupy já é fonte pública (ADR 0004, `:19`). A primeira sessão de mapeamento confere o que a Gupy logada mostra a mais que a pública. Se não mostrar nada a mais, a sessão registra no `duvidas.md` e propõe pular para o LinkedIn como primeiro site da 0.3.0 (D132.27).
- No lote do primeiro site que funciona, tudo junto (D132.13, D132.24; ADR 0022, `:64`):
  - o botão "Baixar o navegador" no grupo "Sites com login": roda `<python> -m playwright install chromium` como processo filho, sem `--with-deps` (pede root), avisa o tamanho (mais de 100 MB, `2026-11-13-fase-1-design.md:1498`) e mostra o estado (baixando, pronto, falhou com o que fazer). O Chromium vai para a pasta padrão do Playwright, a mesma dos testes de tela;
  - `README.md` e `README.en.md`: a navegação com login, o aviso de risco, os caminhos de rede novos (os sites ligados e o download do Chromium pelos servidores do Playwright), e a troca de "não contorna CAPTCHA" por "só resolve CAPTCHA pelo serviço da pessoa, se ela pôs a chave e ligou";
  - `configuracoes.privacidade.telemetria` em pt e en, com o `test_privacidade_cita_todos_os_pedidos` cobrindo os caminhos novos;
  - `wiki/`, nas páginas que repetem a regra (lista no desenho do 2Captcha, `2026-11-15-captcha-design.md:76`);
  - `CLAUDE.md` do projeto: a regra de coleta educada passa a citar a navegação com login (e, com o ok do dono, o user agent do próprio navegador), e o mapa ganha `navegador` e `nucleo/leitores`;
  - nota na ADR 0005 pondo a Gupy na lista do `:15`, se o dono confirmar (D132.29); nota na ADR 0006 sobre o horário perdido (D132.6) e reparo na ADR 0022 sobre o Turnstile (D132.44), se o dono confirmar;
  - `CHANGELOG.md` e o par em inglês, na 0.3.0; ADR 0017 com a fase 2 concluída.
- Passo "Sites com login" no assistente de primeira execução (ADR 0011, `docs/decisions/0011-perfil-e-primeira-execucao.md:25`, `:29`, `:31`): entra com o primeiro site, opcional, com o mesmo cartão do grupo de Configurações e o botão "Pular" (D132.28).
- A 0.3.0 sai com a Gupy (ou com o primeiro site que funcionar). Os outros sites saem em versões seguintes, um de cada vez.

## 7. Riscos

- Termos dos sites: LinkedIn, Indeed e outros proíbem automação nos termos (ADR 0005, `:9`). O risco é da pessoa, dito com franqueza no grupo "Sites com login" e no README, e cada site nasce desligado. Os termos não foram lidos nesta sessão.
- Bloqueio da conta: mesmo devagar, o site pode restringir a conta (ADR 0005, `:41`). Mitigação: 2 leituras por dia por padrão, 4 h ou mais entre os inícios de duas leituras, terminem como terminarem (no máximo 6 por dia), horário perdido não recuperado, leitura que falhou não repete na mesma janela, no máximo 30 navegações por site (10 de lista e 20 de vaga), 3 a 8 s entre navegações, só leitura, sem disfarce, e parada na primeira página de bloqueio, no 429 repetido ou no desafio que volta.
- Bibliotecas do Chromium no container: o Chromium do Playwright com janela pede bibliotecas gráficas que a `fedora-dev` pode não ter; o `install --with-deps` pede root e não cobre o Fedora oficialmente. Mitigação: o motivo `saude.sem_navegador` com o que fazer; o dono testa na máquina real.
- Wayland e o serviço do systemd: o serviço pode não ter `DISPLAY` nem `WAYLAND_DISPLAY` (seção 4). Mitigação: ler o ambiente do systemd do usuário na hora, validado (seção A7) e, sem tela, `saude.sem_tela`. Se ainda assim não funcionar, a alternativa é o `.service` ganhar `After=graphical-session.target`, o que muda o texto do serviço já instalado; isso vai ao `duvidas.md` antes.
- Perfil roubado: os cookies do perfil dão acesso à conta da pessoa. Dentro de container sem cofre de senhas, o Chrome guarda os cookies sem a proteção do chaveiro do sistema. A pasta é 0700, mas outro programa do mesmo usuário consegue ler. Mitigação: o perfil nunca sai da máquina nem vai ao log, o painel recomenda criptografia de disco (ADR 0014, `docs/decisions/0014-seguranca-e-privacidade.md:14`), e "Esquecer logins" apaga tudo.
- Cookie fora do navegador: o `APIRequestContext` (`page.request`, `context.request`) mandaria os cookies da pessoa num pedido que a página não fez, e `all_headers` os traria para o código. Mitigação: proibidos em produção pelo teste da lista permitida (seção A7).
- Senha guardada pelo Chrome: se a pessoa aceitasse "salvar senha" no perfil do joBot, a senha ficaria no disco, ao lado dos cookies, sem o chaveiro do sistema. Mitigação: as preferências da seção A3 desligam o gerenciador de senhas e o preenchimento automático (D132.43). O Chrome pode mudar o nome dessas chaves numa versão nova; o teste só prova o arquivo, e a conferência na máquina real é do dono.
- Injeção no lugar errado: um token entregue numa página de login seria o joBot ajudando a entrar na conta. Mitigação: a checagem de login vem antes da de CAPTCHA, e nada é injetado em página de login (seção A7; teste no site falso, seção 8).
- O site muda: o leitor quebra em silêncio. Mitigação: `formato_mudou` vira `falhou` com `saude.formato_mudou` e nada fecha; o "zero inesperado" da fase 1 (DR-10) vale também para os leitores (seção A4).
- Segredo da sessão ou nome da pessoa numa fixture: a resposta logada pode trazer token, CSRF, id ou nome da conta. Mitigação: o `capturar_logado` limpa pela posição e recusa o que sobrar (seção A10), o nome real nunca vira regra no código, e toda captura é lida por gente.
- CAPTCHA e custo: coberto pela ADR 0022 (teto de 30 por dia, uma tentativa por página, log do custo). A injeção é a mais estreita possível (seção 2); um site que só aceita o token por outro caminho, e o desafio gerenciado do Cloudflare, ficam na janela parada.
- Conteúdo hostil: a página pode trazer texto ou link que tenta levar o navegador a outro lugar, ou um nome de função de retorno feito para rodar código. Mitigação: política de navegação, conferência de `page.url`, scripts literais em `js.py`, nome de função validado e resolvido sem `eval`, e conteúdo tratado como dado.

## 8. Testes esperados

Nenhum teste usa a rede real (D132.11). O navegador é outro processo e não passa pela guarda do `tests/conftest.py`. Por isso todo teste com navegador instala uma rota no contexto que recusa qualquer pedido fora de `127.0.0.1` e confere, no fim, que nenhum pedido foi recusado (o mesmo espírito do critério 27 da fase 1, `2026-11-13-fase-1-design.md:143`). Essa rota (`route`, e `fulfill` quando o teste precisar) é só dos testes do site falso; em produção, o pacote `navegador` não usa `route` nem `fulfill` (seção A7).

Sites falsos (marcador `tela`, rodam no CI sem tela, pelo lançador injetado e com a política que aceita `127.0.0.1`)

- Servidor local em `127.0.0.1` com: página de login (o formulário é preenchido pelo teste, nunca pelo joBot), página de login com reCAPTCHA invisível e `data-callback` que envia o formulário, página logada com a lista de vagas em JSON (pedido pela própria página) e em HTML, lista que carrega mais ao rolar, paginação, lista em que a segunda página perdeu o formato, lista vazia, lista cuja `proxima` aponta para fora dos hosts, escopo cuja URL inicial está fora dos hosts, páginas de vaga, página sem a lista (formato mudou), lista com item torto, lista só com itens tortos, página de bloqueio, resposta 403, resposta 429 com `Retry-After`, redirecionamento para fora dos hosts (um para a página de SSO, outro para um host qualquer), desafio gerenciado "Just a moment" falso que sai sozinho e outro que não sai (este com iframe de Turnstile), reCAPTCHA v2 falso e Turnstile avulso falso (cada um com `sitekey` e uma função de retorno que confere o token), 403 com Turnstile, 429 com reCAPTCHA, desafio que volta depois do token aceito, uma página com reCAPTCHA v3 falso e uma com `data-callback` de nome torto (`alert(1)`).
- Uma execução lê as vagas do site falso e grava na `vaga` e na `ocorrencia` com `fonte = <chave>_logado` e o `escopo` do escopo lido; a mesma URL de uma vaga da fonte pública vira uma linha só.
- Gravação: uma chamada a `gravar_escopo` por escopo, com as vagas das várias páginas do escopo, `validadores` vazio e `urls_sem_detalhe` vazio; nenhuma linha nova em `cache_http`.
- Login com CAPTCHA: na página de login com reCAPTCHA invisível, `resolver` não é chamado, a saúde é `saude.precisa_login`, o servidor recebe zero POST, e nenhum campo muda.
- Sem login: `saude.precisa_login` com escopo `''`, nenhuma vaga, e os outros sites seguem.
- Redirecionamento para fora: para o SSO, `saude.precisa_login`; para outro host, `saude.bloqueio`; nada é capturado fora dos hosts.
- 403 e página de bloqueio sem widget: `saude.bloqueio`; 429 sem widget: espera o `Retry-After` pelo relógio injetado; 429 repetido: o escopo fica `no_limite` com `saude.parou_429`, os escopos seguintes do site não são visitados e não ganham linha de saúde (a linha anterior deles fica igual), e o próximo site segue.
- 403 com Turnstile e 429 com reCAPTCHA: seguem o caminho do CAPTCHA, não o do bloqueio.
- Desafio gerenciado que sai em menos de 30 s: o site segue. O que não sai (com iframe de Turnstile): `resolver` não é chamado, `saude.captcha` e janela parada.
- Desafio que volta depois de um token aceito, na mesma execução: `saude.bloqueio` e o site para.
- reCAPTCHA v3 na página: `resolver` não é chamado, `saude.captcha` e janela parada.
- `data-callback` de nome torto: o token não chama nada, e a página não roda o texto do nome; janela parada.
- Estado do escopo, de ponta a ponta no site falso: página sem a lista dá `falhou` com `saude.formato_mudou` e nenhuma ocorrência fecha; segunda página sem formato, com a primeira boa, não grava nenhuma vaga da primeira; `proxima` fora dos hosts dá `parcial` com `saude.listagem_incompleta`; escopo cuja URL inicial está fora dos hosts não é visitado e dá `falhou` com `saude.listagem_incompleta`, e nenhuma ocorrência dele fecha; login no meio da lista dá `falhou` com `saude.precisa_login`, as vagas da primeira página são gravadas e nada fecha.
- Tetos: no máximo 10 páginas de lista por site, somando os escopos; no máximo 20 páginas de vaga; espera entre 3 e 8 s em toda navegação (gerador e relógio injetados; sem `sleep` real).
- Rodízio: com três escopos e teto para dois, vão os dois visitados há mais tempo; o terceiro não ganha linha de saúde e a linha anterior dele fica igual.
- Escopos extintos: busca removida pela pessoa fecha as ocorrências do escopo dela; escopo pulado pelo teto não fecha; site que parou na entrada não fecha nada.
- Detalhe: com `lista_tem_descricao` falso, só abre vaga sem descrição na ocorrência e sem detalhe tentado nos últimos 30 dias, as mais novas primeiro; vaga cuja URL teve detalhe tentado por outra fonte há menos de 30 dias não é aberta; cada página aberta grava o `enriquecimento` (com o detalhe ou vazio); a vaga que o teto não deixou abrir não ganha linha no `enriquecimento` e é aberta na execução seguinte; a descrição de um detalhe antigo continua depois de uma nova leitura da lista; com `lista_tem_descricao` verdadeiro, nenhuma página de vaga é aberta.
- Só leitura: o servidor falso conta os POST que recebe; uma execução sem CAPTCHA faz zero POST, e nenhum campo de formulário muda de valor.
- CAPTCHA com 2Captcha pronto: `resolver`, com `httpx.MockTransport`, recebe o tipo, a `sitekey` e o user agent do navegador, lido do cabeçalho de um pedido da página; o token chega à função de retorno da página; uma tentativa só por página. Fora o campo de resposta do widget, nenhum campo da página muda de valor; o único pedido depois do token é o que a própria função de retorno do site faz.
- CAPTCHA sem 2Captcha (interruptor desligado, sem chave, tipo não aceito, `ErroCaptcha`, teto, página que não sai do desafio em 30 s): `saude.captcha`, o aviso no computador chamado pelo executor falso, e a aba continua aberta.
- Janela parada com duas abas: os 15 minutos contam uma vez só, para as duas; uma resolvida segue, a outra grava `saude.captcha` no fim.
- A pessoa fecha o navegador no meio: a execução fica `interrompida` com a parada `fechado`, e os escopos já gravados ficam.
- Site com login desligado: linha `desligada` com escopo `''`.

Unidade

- `test_camadas`: as regras da seção A2, cada uma com o seu teste do detector.
- AST do pacote `navegador`, lista permitida (seção A7): fora de `js.py`, atributo de `Page`, `Frame`, `Locator`, `BrowserContext`, `Browser`, `APIRequestContext`, `Request` ou `Response` fora da lista reprova; `on` e `once` só com os eventos listados. Teste do detector numa pasta temporária, com um exemplo ruim por categoria (`page.click`, `page.evaluate` fora de `js.py`, `page.route`, `context.request.get`, `pedido.all_headers()`, `page.on("dialog", ...)`, um atributo qualquer fora da lista) e um exemplo bom (`page.goto`, `page.locator(...).get_attribute`, `page.on("response", ...)`, `pedido.headers`).
- AST de `js.py`: os scripts são literais, e são só os listados na seção A7; o detector pega uma f-string e uma concatenação de exemplo.
- `js.py`: o nome da função de retorno passa pela regex; `alert(1)`, `a..b`, `1a` e nome com espaço são recusados; `a.b.c` é aceito.
- Precedência do estado do escopo (função pura), um teste por caso:
  - cada parada sozinha: `precisa_login`, `bloqueio` e `captcha` dão `falhou` com a chave delas; `no_limite` dá `no_limite` com `saude.parou_429`; em todas, as vagas das páginas lidas antes são gravadas;
  - duas paradas juntas: vale a da frente (`precisa_login` antes de `bloqueio`, `bloqueio` antes de `captcha`, `captcha` antes de `no_limite`);
  - parada com página `formato_mudou` no mesmo escopo: vale o estado da parada, e nenhuma vaga do escopo é gravada;
  - `formato_mudou` numa página e outra boa: `falhou` com `saude.formato_mudou` e nenhuma vaga a gravar;
  - lista só com itens tortos: `falhou` com `saude.formato_mudou`;
  - `cortada` (teto ou `proxima` recusada pela política) com item torto e pelo menos uma página lida: `parcial` com `saude.listagem_incompleta`;
  - `cortada` sem nenhuma página lida (URL inicial do escopo recusada pela política): `falhou` com `saude.listagem_incompleta`;
  - item torto, lista até o fim: `parcial` com `saude.formato_mudou`;
  - lista vazia com `tres_ok_com_vagas`: `parcial` com `saude.zero_inesperado`;
  - lista vazia sem esse histórico: `ok`;
  - lista até o fim com vagas: `ok`.
- Política de navegação de produção: recusa `http://`, `127.0.0.1` e host fora da lista.
- Preferências do perfil: as três chaves gravadas, as outras preservadas, arquivo torto reescrito.
- `preparar_pasta`: não desce em `navegador/`, mas fecha a própria pasta em 0700.
- Lançador de produção: visível, sem `--remote-debugging-port`, sem `headless`; `channel="chrome"` e, na falha, o Chromium; com os dois falhando, `saude.sem_navegador`.
- Tela: sem `DISPLAY` e sem `WAYLAND_DISPLAY`, lê o ambiente do systemd pelo executor falso (com `distrobox-host-exec` quando há `CONTAINER_ID`); valores fora do formato são ignorados; um SEGREDO na saída não aparece no log; sem nada, `saude.sem_tela` e o navegador nem é chamado.
- Banco: a consulta da última leitura com login conta `concluida` e `interrompida` e ignora `rodando` e os outros tipos; a consulta das candidatas a detalhe, já em `banco`, devolve `ocorrencia_id`, deixa de fora vaga com descrição na ocorrência e vaga com detalhe recente por URL, e os testes de hoje do passo de detalhes da busca passam com ela.
- Agenda, `login_vencido` (relógio injetado, fuso fixo fora de UTC):
  - às 9h00 vence; às 9h05, com uma leitura começada às 9h01, não vence;
  - às 9h14 vence; às 9h16, sem leitura desde ontem, não vence (fora da janela de 15 minutos);
  - a pessoa fechou o navegador às 9h02 (execução interrompida com a parada `fechado`): não reabre às 9h03;
  - erro às 9h01 (execução interrompida com a parada `erro`): não repete na janela das 9h;
  - perdeu as 9h e ligou às 15h: não roda às 15h; às 18h roda se a última começou às 14h ou antes; com um "Buscar agora" às 15h30, não roda às 18h, e a próxima é às 9h do dia seguinte;
  - "Buscar agora" às 16h: o horário das 18h é pulado;
  - máquina ligada às 20h depois de perder as 9h e as 18h: não roda; a próxima é às 9h do dia seguinte;
  - relógio que voltou (última no futuro) não trava; sem site ligado, não roda; nada nos primeiros 60 s.
- "Buscar agora": sem site ligado não dispara a leitura com login; com menos de 4 h desde o início da última (concluída ou interrompida) não dispara; com `travas["login"]` presa não dispara outra; senão dispara com motivo `agora` e a rota volta sem esperar; a tela de andamento não mostra a leitura com login.
- `login_horarios`: padrão dos dois lados; valores tortos (formato, repetido, mais de 4, menos de 4 h entre eles) voltam com mensagem, e nada é gravado.
- Migrações: a 0007 migra `execucao` antiga sem perder linha e aceita `login`; `saude` e `execucao_fonte` com o mesmo número de linhas antes e depois; o `CHECK` de `parada` continua recusando valor fora da lista; a 0008 dá a `fonte` a coluna `com_login`, com `0` nas linhas antigas.
- Ajudantes movidos para `banco`: os testes de hoje de `interromper` e do batimento passam com o import novo, e a agenda não tem mais cópia deles.
- Leitores (Parte B): cada um com as fixtures dele; `ler` de fixture com item torto conta o pulado; `ler` de página sem lista dá `formato_mudou`; `pagina_logada` e `e_login` verdadeiras e falsas; `escopos` gera um escopo por par de termo e país, mais os próprios do site; `detalhar` quando o leitor o tem.
- `capturar_logado`, com o site falso e um nome inventado para a conta:
  - limpa e passa: respostas com valor de campo `csrf`, de campo `xsrf`, JWT, `JSESSIONID`, id de conta e nome da conta (nas posições de `campos_conta` e de `--campo`) saem com o marcador e são gravadas, uma a uma;
  - resíduo recusado: o id de conta repetido dentro de uma URL do corpo, e um campo `csrf` fora do marcador, fazem nada ser gravado, e a mensagem não traz o valor;
  - a limpeza acha pela posição: o mesmo nome inventado numa posição não declarada não é trocado pela limpeza (fica para a leitura por gente);
  - e-mail e telefone saem limpos ou a captura é recusada;
  - o meta não tem cookie, cabeçalho nem valor de query;
  - com o `jobot.lock` preso, recusa; enquanto roda, segura o `jobot.lock`.
- Log: depois de uma execução no site falso com um cookie de valor conhecido, um token conhecido e uma URL com query secreta, nenhum dos três aparece no `caplog`.

Painel (integração e tela)

- Sem leitor registrado: a aba não aparece e `/configuracoes/sites-com-login` dá 404.
- Com o leitor do site falso: o interruptor nasce desligado e grava na hora; "Fazer login agora" com a trava presa responde "em andamento"; "Esquecer logins" pede confirmação na página, apaga a pasta só no segundo POST e não toca o banco; o cartão mostra a leitura rodando.
- Todos os textos novos em pt e en; os motivos percorridos nos dois idiomas; nenhum `<input type="checkbox">` sem `.chave`; cor nova com contraste em `test_contraste_minimo`.
- Parte B: o botão "Baixar o navegador" chama o comando de instalação pelo executor falso e mostra os três estados; o `test_privacidade_cita_todos_os_pedidos` cobre os caminhos novos.

## 9. O que fica para o construtor

- Nomes finais de módulos, funções, classes CSS e chaves de i18n, seguindo os que existem.
- O SQL das migrações 0007 (reconstrução de `execucao`) e 0008 (coluna `com_login`), com os nomes de arquivo finais, conferindo as colunas atuais de `execucao` (`0001_inicial.sql:36-44` e `0004_motivo_da_parada.sql:4-5`) e as lições de `registros/padroes.md:5-6`.
- Como o registro de leitores semeia a tabela `fonte` (este desenho não leu `nucleo/coletores/registro.py` nem `carregar_fontes`).
- O novo nome do batimento assíncrono ao mover para `banco`, e todos os chamadores de `parada_de`, `interromper` e `bater` (descoberta e páginas inclusive).
- O nome da função extraída da consulta das candidatas a detalhe (`src/jobot/agenda/execucao.py:270-291`).
- O nome da consulta da última leitura com login em qualquer estado final, irmã de `inicio_da_ultima_completa`.
- Como o `Estado` e o `o_que_roda` recebem a última leitura com login, os horários e "há site ligado", sem quebrar os testes de hoje do `o_que_roda`.
- Os nomes exatos da lista permitida do Playwright 1.65.1 instalado, e como o detector separa um `close` ou um `url` do Playwright de um homônimo de outra biblioteca.
- Se o cabeçalho `user-agent` do evento `request` serve na versão instalada; se não, o terceiro script de `js.py`.
- O jeito de esperar "a página assentou" sem `sleep` fixo (eventos do Playwright) e o de achar o campo de resposta e o `data-callback` de cada widget, conferidos na documentação pública do Playwright 1.65.1, do reCAPTCHA, do Turnstile e do 2Captcha na hora de construir.
- Como reconhecer o desafio gerenciado do Cloudflare (com e sem iframe do Turnstile) e decidir que é "o mesmo desafio" que voltou, de um jeito testável com o site falso.
- Os nomes exatos das chaves de preferência do Chrome na versão do Playwright 1.65.1, conferidos na documentação pública do Chromium.
- Como mapear o erro do Playwright ao abrir (Chrome ausente, Chromium ausente, biblioteca faltando) para os motivos, sem depender do texto exato da mensagem quando der.
- Como detectar que a pessoa fechou o navegador (evento `close`) e transformar isso em interrupção com a parada `fechado`.
- Como mapear termos × países para a busca de cada site (Parte B, por leitor) e o limite de escopos que isso gera, já que o teto de 10 páginas de lista e o rodízio seguram o total. Levar cidades ao `ContextoColeta` é R4 e vai ao `duvidas.md`.
- A lista de bibliotecas de sistema que o Chromium com janela pede no Fedora, para o texto de ajuda de `saude.sem_navegador`.
- Repartir em tarefas `Tn` no plano, seguindo a ordem da seção A11.

## 10. Pontos que batem com o que já existe

- D132.2 e a `fedora-dev`: o Chrome instalado (`channel="chrome"`) não existe no ambiente do dono (`2026-11-13-fase-1-design.md:1436`, `:161`, `:1213`), e o do sistema de fora não serve pelo pipe. No dono, o caminho real é o Chromium do Playwright dentro do container (seção A1).
- D132.6 e o esquema: o tipo `login` exige reconstruir a tabela `execucao` (`0001_inicial.sql:38`), com `saude` e `execucao_fonte` penduradas nela em cascata (`0001_inicial.sql:50`, `0003_execucao_fonte.sql:3`) e a coluna `parada` da `0004_motivo_da_parada.sql:4-5`; `Tipo` (`src/jobot/banco/execucoes.py:25`) e `TIPOS` (`src/jobot/cli/servir.py:49`) mudam junto.
- D132.6 e a ADR 0006 (`:26`): a ADR roda a execução perdida ao ligar; a leitura com login pula o horário perdido. Por isso é pergunta ao dono.
- D132.6 e `inicio_da_ultima_completa` (`src/jobot/banco/execucoes.py:231-236`): ela só conta as concluídas; a leitura com login precisa contar também as interrompidas, por isso a consulta irmã.
- D132.3 e a pasta de dados: hoje `preparar_pasta` desceria no perfil a cada `serve` (`src/jobot/sistema/pastas.py:36-38`, `src/jobot/cli/servir.py:62`).
- D132.20 e a tabela `fonte`: leva só `A` ou `B` (`0001_inicial.sql:6`); a fonte com login ligada quebraria o `coleta_acabou` da busca pública (`src/jobot/banco/execucoes.py:254-260`). A junção com a vaga pública só acontece quando a URL canônica é a mesma (`0001_inicial.sql:63`).
- D132.39 e as camadas: `parada_de`, `interromper`, o batimento (`src/jobot/agenda/execucao.py:112-157`) e a consulta das candidatas a detalhe (`:270-291`) moram hoje na agenda, e o `navegador` não pode importar a agenda; por isso vão para `banco`.
- D132.32 e a gravação: `urls_sem_detalhe` grava "tentado, nada veio" (`src/jobot/banco/gravacao.py:386-391`), então fica vazio na leitura com login; o detalhe vai pela `gravar_cache_detalhe` (`:454-475`), como no passo de detalhes da busca.
- D132.36 e o zero inesperado: reaproveita a regra e a chave da fase 1 (`src/jobot/nucleo/coletores/executor.py:357-363`; `comum.json:76`).
- D132.31 e o reCAPTCHA v3: a fase 2 não usa o v3 (seção 2), embora a ADR 0022 (`:24`) e o cliente (`src/jobot/nucleo/captcha.py:231-235`) o aceitem.
- D132.44 e a ADR 0022: a ADR aceita o Turnstile (`:24`); a fase 2 só resolve o avulso. O `turnstile.render` de `2026-11-15-captcha-design.md:210` fica descartado; o desafio gerenciado do Cloudflare não passa pelo 2Captcha (`src/jobot/nucleo/captcha.py:81-89` não tem `cData` nem `chlPageData`). Pergunta ao dono, com reparo na ADR se confirmar.
- D132.16 e a injeção do token: a exceção estreita está escrita nos anti-objetivos (seção 2).
- D132.45 e os motivos: o primeiro desenho criava `saude.bloqueio_site`; fica `saude.bloqueio`, que já existe (`comum.json:80`), porque chave nova é R4 (`registros/padroes.md:32`).
- D132.12 e os scripts: `limpar_pessoais` e `achar_pessoais` são funções de `scripts/capturar.py` (`:224`, `:247`), não scripts próprios; a docstring de `scripts/capturar.py:1` deixa de valer com o `capturar_logado.py`.
- D132.15 com a regra de coleta educada do `CLAUDE.md` do projeto ("user agent fixo do joBot"): na navegação com login vale o user agent do próprio Chrome. Só muda com o ok do dono (seção 11).
- D132.35 e as cidades: a revisão pediu escopos de termos × cidades, mas o `ContextoColeta` não tem cidade (`src/jobot/nucleo/coletores/base.py:31-35`); as cidades da busca (`0001_inicial.sql:130`) só viram países (`src/jobot/banco/buscas.py:217-224`). O desenho usa termos × países.
- D132.33 e o ciclo de vida: o `parcial` do teto reaproveita a janela de 30 dias da fase 1 (`JANELA_PARCIAL`, `src/jobot/nucleo/tratamento/ciclo_de_vida.py:7`) e o motivo `saude.listagem_incompleta` (`src/jobot/nucleo/coletores/base.py:149`); não há regra nova de ciclo.
- D132.32 e o cache: o cache de detalhe é por URL, de qualquer fonte (`src/jobot/banco/execucoes.py:386`); a leitura com login não abre vaga que outra fonte já tentou detalhar há menos de 30 dias.
- ADR 0006 (`:17`, "Buscar agora busca tudo"): resolvido pelo intervalo mínimo de 4 h (seção A6). ADR 0005 (`:24`, duas por dia): o padrão continua duas; o teto é 6.
- ADR 0005: a lista "Primeiro LinkedIn, Indeed, Catho e Vagas.com" (`:15`) não traz a Gupy, que abre a ordem de mapeamento (`:16`). Este desenho segue a ordem do `:16` (seção 11).
- ADR 0011 (`:25`, `:29`, `:31`): o passo "logins nos sites" da primeira execução é da fase 2; entra na Parte B (seção 6).
- O desenho da fase 1 (`2026-11-13-fase-1-design.md:1491`) dizia "Playwright de execução só se uma fonte exigir JavaScript"; D132.1 substitui isso para a navegação com login, não para as fontes públicas.

## 11. Perguntas pendentes do dono

Só as decisões que pedem resposta do dono. Cada uma tem o número da lista completa da seção 12.

1. (D132.24) Na sua `fedora-dev`, sem Chrome, o joBot usa o Chromium do Playwright: na Parte A, o que já está instalado; a partir do primeiro site, também baixado por um botão. Tudo bem?
   Recomendação: sim. Instalar o Chrome dentro do container também funciona, mas não é necessário.
2. (D132.25) "Buscar agora" também lê os sites com login, se a última leitura com login (terminada bem ou não) começou há 4 horas ou mais? Com isso, no máximo 6 leituras com login por dia.
   Recomendação: sim. Mantém a ADR 0006, e o padrão continua duas por dia.
3. (D132.26) Com CAPTCHA sem 2Captcha, o joBot espera até 15 minutos no total, com as janelas abertas, e depois fecha?
   Recomendação: sim. A janela não fica aberta para sempre, e a próxima leitura tenta de novo.
4. (D132.27) Se a Gupy logada não mostrar nada além da pública, o primeiro site da 0.3.0 passa a ser o LinkedIn?
   Recomendação: sim.
5. (D132.28) O passo "Sites com login" entra no assistente de primeira execução, opcional?
   Recomendação: sim, com o primeiro site (ADR 0011).
6. (D132.15) Na navegação com login vale o user agent do próprio navegador, não o user agent fixo do joBot. Isso contraria a regra de coleta educada do `CLAUDE.md` do projeto, que só muda com o seu ok. Pode?
   Recomendação: sim. Trocar o user agent do Chrome seria mexer no navegador, e o Chrome automatizado já se identifica (`navigator.webdriver`). O `CLAUDE.md` muda no lote do primeiro site.
7. (D132.29) A ADR 0005 põe a Gupy primeiro na ordem de mapeamento (`:16`), mas não a lista entre os sites do `:15`. A Gupy entra na lista?
   Recomendação: sim, com uma nota na ADR 0005 no lote do primeiro site.
8. (D132.19, D132.32) Quando a lista do site não traz a descrição, o joBot abre a página de cada vaga, até 20 por site em cada leitura (as mais novas primeiro), só as que ainda não têm descrição e não tiveram detalhe tentado nos últimos 30 dias (por qualquer fonte). No total, no máximo 30 páginas por site por leitura (10 de lista e 20 de vaga). Tudo bem?
   Recomendação: sim. Sem a descrição, a vaga fica pobre para os filtros e a nota; o cache e o teto seguram as visitas.
9. (D132.30) Página de login vira "precisa login" e nunca recebe token. Fora do login, uma página que responde 403 ou 429 mas mostra um CAPTCHA reconhecido é tratada como CAPTCHA, não como bloqueio. O desafio do Cloudflare ganha 30 s para sair sozinho e depois fica para você resolver. O site só conta como bloqueado se o mesmo desafio voltar depois de resolvido. Tudo bem?
   Recomendação: sim. Muitos sites mandam o desafio com 403 ou 429, e chamar isso de bloqueio desligaria o 2Captcha onde ele mais serve.
10. (D132.31) Para usar o token do 2Captcha, o joBot pode escrever o token no campo do próprio CAPTCHA e chamar a função de retorno que o CAPTCHA declarou, só na página de desafio (nunca no login), sem clicar nem enviar nada? E o reCAPTCHA v3 fica fora da fase 2?
    Recomendação: sim para as duas. É o mínimo para o token servir; o v3 exigiria trocar uma função do site, o que passa da linha do "só leitura".
11. (D132.6) As leituras com login rodam nos horários (9h e 18h), com 15 minutos de tolerância. Um horário perdido (joBot fechado na hora) é pulado, não recuperado ao ligar, e uma leitura que deu erro ou que você interrompeu também conta: não repete na mesma janela. Exemplo: perdeu as 9h, ligou às 15h: não roda às 15h, roda às 18h. Isso foge da ADR 0006, que roda a execução perdida ao ligar. Pode?
    Recomendação: sim. Ler o site em hora estranha, ou de novo logo depois de uma falha, chama mais atenção do site do que esperar o próximo horário; o "Buscar agora" continua lá para quem quiser na hora. A ADR 0006 ganha uma nota.
12. (D132.44) O 2Captcha resolve só o Turnstile avulso numa página; a página inteira de desafio do Cloudflare ("Just a moment") ganha 30 s para sair sozinha e depois fica para você. Isso estreita a ADR 0022, que aceita o Turnstile sem essa distinção. Pode?
    Recomendação: sim. Resolver esse desafio pelo serviço pediria trocar uma função do site; a ADR 0022 ganha um reparo.

Enquanto o dono não responde, o construtor segue as recomendações e registra cada uma no `duvidas.md` como "para confirmar". A lista completa está na seção 12.

## 12. Todas as decisões da D132

Cada item é **decisão da sessão, para confirmar**. "Pergunta ao dono" marca as que estão também na seção 11; "decisão da sessão" marca as que o construtor segue sem perguntar, registradas para o dono ver.

1. Playwright 1.65.1 passa para as dependências de execução, com `==`; o Chromium (mais de 100 MB) vem à parte. Decisão da sessão.
2. O navegador é o Chrome instalado (`channel="chrome"`) e, sem ele, o Chromium do Playwright. Decisão da sessão.
3. Perfil próprio em `<dados>/navegador/`, um contexto persistente para todos os sites; `preparar_pasta` não desce nele. Decisão da sessão.
4. Pacote `navegador/` (único que importa `playwright`) e `nucleo/leitores/` puro, com as regras novas do `test_camadas`. Decisão da sessão.
5. Protocolo `LeitorComLogin` separado do `Coletor`; o JSON das APIs internas da página vem antes do HTML. Decisão da sessão.
6. Tipo de execução `login`, horários padrão 9h e 18h no horário local. `ultima` é o início da última execução `login` concluída ou interrompida, por uma consulta nova em `banco`, irmã de `inicio_da_ultima_completa`. Regra única: o horário `H` vence só dentro de 15 minutos depois dele, se nenhuma leitura com login começou em `[H, agora]` e se `H - ultima >= 4 h`; horário perdido é pulado, nunca recuperado, e leitura que falhou ou foi interrompida não repete na janela (foge da ADR 0006, `:26`, que ganha nota se confirmado). Pergunta ao dono.
7. Quatro chaves `saude.*` novas, todas `falhou`: `precisa_login`, `captcha`, `sem_tela`, `sem_navegador` (chave nova é R4). As reaproveitadas seguem a precedência da seção A4. Decisão da sessão.
8. Liga e desliga por site no grupo "Sites com login"; cada site nasce desligado. Decisão da sessão.
9. Sem tela, a leitura falha com `saude.sem_tela`; nunca roda escondida. Decisão da sessão.
10. CAPTCHA reconhecido: reCAPTCHA v2 (inclusive invisível) e Turnstile avulso; fora do 2Captcha, aviso no painel, `notify-send` e janela parada. Decisão da sessão.
11. Testes só com sites falsos em `127.0.0.1` e uma rota do teste que recusa o resto; `route` e `fulfill` só nos testes. Decisão da sessão.
12. Ordem de mapeamento Gupy, LinkedIn, Vagas.com, Catho, Indeed; captura com `scripts/capturar_logado.py`. Decisão da sessão.
13. README, privacidade, wiki, `CLAUDE.md` e CHANGELOG mudam no lote do primeiro site. Decisão da sessão.
14. Um interruptor do 2Captcha para todos os sites, o da aba Serviços. Decisão da sessão.
15. Sem disfarce: sem stealth, sem mexer em `navigator.webdriver`, user agent do próprio Chrome, contrariando o user agent fixo do `CLAUDE.md`. Pergunta ao dono.
16. As execuções automáticas só navegam, esperam e rolam. Decisão da sessão.
17. Só pipe; nunca porta de depuração nem `connect_over_cdp`. Decisão da sessão.
18. `travas["login"]` é a trava do navegador, um objeto só em `app.state.travas`, dividido entre agenda, "Buscar agora", "Fazer login agora" e "Esquecer logins". Decisão da sessão.
19. Tetos por site em cada leitura: 10 páginas de lista (somando os escopos) e 20 de vaga, 30 no total; 3 a 8 s entre navegações. Pergunta ao dono.
20. Cada site é uma fonte com chave `<site>_logado`, nas mesmas tabelas das públicas. Decisão da sessão.
21. "Esquecer logins" apaga a pasta do perfil inteira, com confirmação na própria página. Decisão da sessão.
22. O perfil é dado sensível: fora do log, da exportação e da cópia antes de migrar. Decisão da sessão.
23. A Parte A não muda nada visível na versão publicada; o grupo só aparece com leitor; a 0.3.0 sai com a Gupy. Decisão da sessão.
24. Na `fedora-dev`, o Chromium do Playwright; na Parte A, só o já instalado; o botão "Baixar o navegador", o texto de privacidade e o teste dele entram no lote do primeiro site. Pergunta ao dono.
25. "Buscar agora" lê os sites com login quando `agora - ultima >= 4 h`, com a mesma `ultima` da D132.6 (concluída ou interrompida); com a regra do horário, há sempre 4 h ou mais entre os inícios de duas leituras com login, terminem como terminarem (no máximo 6 por dia). Pergunta ao dono.
26. Janela parada: até 15 minutos no total, olhando todas as abas paradas ao mesmo tempo. Pergunta ao dono.
27. Se a Gupy logada não trouxer nada a mais, o LinkedIn vira o primeiro site da 0.3.0. Pergunta ao dono.
28. Passo opcional "Sites com login" no assistente de primeira execução, com o primeiro site. Pergunta ao dono.
29. A Gupy entra na lista da ADR 0005 (`:15`), com nota no lote do primeiro site. Pergunta ao dono.
30. Ordem das checagens: host, login, desafio gerenciado do Cloudflare (30 s), página de desafio com widget reconhecido (mesmo com 403 ou 429), bloqueio; o desafio que volta depois do token vira `saude.bloqueio`. Pergunta ao dono.
31. Injeção estreita: só o campo de resposta do widget e o `data-callback` declarado, só em página de desafio que não é login; reCAPTCHA v3 fora da fase 2. Pergunta ao dono.
32. Detalhe: até 20 páginas de vaga por site, depois de gravar os escopos do site. As candidatas saem da consulta da busca (`src/jobot/agenda/execucao.py:270-291`), extraída para `banco` e usada pelas duas leituras: ocorrência aberta, vaga vista pela primeira vez nos últimos 30 dias, sem descrição na ocorrência, sem detalhe tentado nos últimos 30 dias por `detalhe_recente` (por URL, de qualquer fonte), as mais novas primeiro, com o `ocorrencia_id`. Cada página aberta grava pela `gravar_cache_detalhe`; a vaga que o teto não deixou abrir não grava nada no cache e volta na próxima. Pergunta ao dono.
33. Ciclo de vida igual à fase 1: lista até o fim é `ok`; cortada pelo teto é `parcial` com `saude.listagem_incompleta`; falha ou bloqueio não mudam nada. Decisão da sessão.
34. Escopos vêm das buscas da pessoa, mais os próprios do leitor; o teto de 10 páginas é somado entre eles; rodízio pelo visitado há mais tempo; escopo que não coube não grava saúde. Decisão da sessão.
35. Escopos usam termos × países, porque o `ContextoColeta` não tem cidade; levar `busca.cidades` ao `ContextoColeta` é R4. Decisão da sessão.
36. `ler(captura, escopo)` devolve `Leitura(vagas, pulados, formato_mudou)`; `VagaColetada.escopo` vem do escopo passado. Estado do escopo por uma função pura com entradas `leituras`, `parada` opcional, `cortada` e `tres_ok_com_vagas` (calculado pelo navegador com o `HistoricoDoBanco`). Precedência: parada (`precisa_login` > `bloqueio` > `captcha` > `no_limite`; as vagas lidas antes são gravadas, menos quando alguma página do escopo teve `formato_mudou`, e aí nenhuma é gravada; nada fecha; toda parada, `no_limite` inclusive, encerra o site na execução, e os escopos seguintes não são visitados nem gravam saúde) > `formato_mudou` (falhou, nenhuma vaga do escopo gravada, nada fecha) > `cortada`, pelo teto ou por URL da lista recusada pela política (parcial com `listagem_incompleta` se pelo menos uma página foi lida; falhou com `listagem_incompleta` e nada fecha se a URL inicial foi recusada) > pulados (parcial, `formato_mudou`) > zero inesperado (parcial, `saude.zero_inesperado`, regra da fase 1) > `ok`. Uma chamada a `gravar_escopo` por escopo, com `validadores = {}`, `urls_vistas` = páginas de lista do escopo e `urls_sem_detalhe = ()`. Decisão da sessão.
37. Página de login: `input[type=password]`, `e_login(captura)` do leitor ou `prefixos_login` (login e SSO); vira `saude.precisa_login`, e nada é injetado nela, nem 2Captcha. Decisão da sessão.
38. Lista permitida de chamadas ao Playwright, por teste de AST com teste do detector (um ruim por categoria, inclusive `page.on("dialog", ...)` e `all_headers`, e um bom). `Request` só com `url` e `headers`; `Response` só com `url`, `status`, `headers`, `text` e `body`; `headers`, nunca `all_headers`; `on` e `once` só para `response`, `request` e `close`. Proibidos em produção `route`, `fulfill`, `page.request`, `context.request`, `all_headers`, os `eval_*`, `evaluate_handle`, `wait_for_function`, `add_script_tag`, `add_init_script`, `expose_*`, `press_sequentially`, `clear` e as ações na página. Só `navegador/js.py` chama `evaluate`, com scripts literais (rolar, entregar o token e, se o cabeçalho não servir, ler o user agent). O user agent sai do cabeçalho de qualquer pedido da página; token e nome da função entram como argumento; nome validado por regex e resolvido a partir de `window`, sem `eval`; chamada nova na lista só com teste e D. Decisão da sessão.
39. O orquestrador da leitura com login fica em `navegador`; passam da agenda para `banco` `parada_de`, `interromper`, o batimento e a consulta das candidatas a detalhe; o `cli/servir.py` injeta a tarefa `login` no laço como as outras; `navegador` não importa `agenda`. Decisão da sessão.
40. Depois de cada site sem falha geral, `fechar_escopos_extintos` com todos os ids de `escopos(ctx)`, visitados ou não. Decisão da sessão.
41. "Buscar agora" dispara a tarefa `login` com motivo `agora` em `app.state.tarefas`, sem esperar; a tela de andamento mostra só a busca; o estado da leitura com login aparece no grupo "Sites com login". Decisão da sessão.
42. Política de navegação injetada; a de produção só aceita `https` dos hosts do leitor e recusa host local; `page.url` é conferido depois de cada navegação (fora: `precisa_login` se for login ou SSO, senão `saude.bloqueio`). `proxima` recusada depois de uma página lida deixa o escopo `parcial`; URL inicial do escopo recusada o deixa `falhou`, ambos com `saude.listagem_incompleta`. Decisão da sessão.
43. Antes de abrir, o arquivo de preferências do perfil grava `credentials_enable_service = false`, `profile.password_manager_enabled = false` e `autofill.profile_enabled = false`. Decisão da sessão.
44. Desafio gerenciado do Cloudflare, mesmo com iframe do Turnstile: 30 s e depois janela parada, sem 2Captcha; o `turnstile.render` do desenho do 2Captcha fica descartado. Estreita a ADR 0022 (`:24`), que ganha um reparo se o dono confirmar. Pergunta ao dono.
45. Bloqueio do site reaproveita `saude.bloqueio`; não há `saude.bloqueio_site`. Decisão da sessão.
46. Migração 0008: coluna `com_login` na `fonte`; fontes com login semeadas pelo registro de leitores, fora da aba "Fontes" e fora do `coleta_acabou`. Decisão da sessão.
47. Migração 0007 de `execucao` em ordem fixa (criar `execucao_nova` com `parada` e o `CHECK` da 0004, copiar, `DROP execucao`, renomear a nova) e prova de que `saude` e `execucao_fonte` não perdem linha. Decisão da sessão.
48. `login_horarios` aceita de 1 a 4 horários, sem repetição, com pelo menos 4 h entre eles. Decisão da sessão.
49. O `jobot buscar` não roda sites com login; a leitura com login só roda dentro do `serve`. Decisão da sessão.
50. Tela pelo ambiente do systemd do usuário: só as quatro variáveis, com formato validado; a saída crua nunca vai ao log. Decisão da sessão.
51. Falha do site inteiro grava saúde com escopo `''`; site desligado grava `desligada`; a pessoa fechar o navegador interrompe a execução com a parada `fechado`, que já existe, sem valor novo no `CHECK`. Decisão da sessão.
52. "Fazer login agora" observa até 10 minutos, não é execução e não lê vaga; com leitura rodando, responde "em andamento". Decisão da sessão.
53. `capturar_logado` segura o `jobot.lock` enquanto roda; tira query, cookie e cabeçalhos do meta; limpa primeiro (troca por marcador fixo o valor de `csrf`, `xsrf`, JWT, `JSESSIONID` e o que está nas posições de `campos_conta` do leitor, ou de `--campo`, repetível) e só depois recusa o que sobrar, inclusive um valor trocado que reaparece noutro lugar. Nome e dado da conta se tratam pela posição (campo JSON ou seletor), nunca pelo valor literal: o nome real nunca entra em código, teste, fixture ou regra de limpeza, e os testes usam nome inventado; nome achado fora das posições conhecidas vira posição nova e a captura é refeita. A docstring de `scripts/capturar.py` muda junto. Decisão da sessão.
54. Captura só das respostas dos hosts do leitor, JSON ou HTML, até 5 MB cada e 50 por página; log só com host e caminho. Decisão da sessão.
55. Biblioteca de sistema faltando vira `saude.sem_navegador`, com frase fixa na tela e a mensagem do Playwright só no log. Decisão da sessão.
56. Turnstile que devolve outro user agent: o joBot não troca o do navegador; tenta o token e, se não passar, janela parada. Decisão da sessão.
57. `reportCorrect` e `reportIncorrect` do 2Captcha ficam fora da fase 2. Decisão da sessão.
