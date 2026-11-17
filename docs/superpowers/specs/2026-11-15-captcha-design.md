# CAPTCHA pelo 2Captcha e IA pela sessão: desenho

Data: 2026-11-15. Decisões de origem: D124 (2Captcha) e D125 (IA pela sessão), em `duvidas.md`. Registro: ADR 0022 (`docs/decisions/0022-captcha-pelo-servico-da-pessoa.md`).
Este documento é a especificação para planejar e construir sem voltar ao dono. Todo fato sobre o código vem com `arquivo:linha`, conferido na `dev` de 2026-11-15; as linhas podem andar, então procure pelo nome quando a linha não bater. Fato sobre o 2Captcha, o Claude Code e o Codex vem de páginas públicas, com o endereço na parte em que é usado.

Cada decisão deste documento é **decisão da sessão, para confirmar com o dono (D124)**, menos o que o dono pediu com as próprias palavras (seção 1) e o que já estava decidido em ADR. A parte F é da D125.

## 1. Intenção e porquê

Pedido do dono, por voz, em 2026-11-15, em resumo:

- na aba Configurações, um campo para a chave de API do 2Captcha e um liga/desliga para usar ou não;
- nas telas com CAPTCHA da navegação automática, se a chave estiver posta e ligada, o 2Captcha resolve;
- interface bonita, com animações, e "nada de controle padrão do HTML (nada de quadradinho azul de checkbox)";
- na configuração da IA: rodar pela sessão do Claude Code e, se der, pela sessão do Codex da OpenAI, com um botão de download ao lado, que baixa ou leva à página de download.

Por quê: hoje, quando um site com login mostra CAPTCHA, a janela fica parada esperando a pessoa (ADR 0005). Para quem acompanha poucos sites, isso basta. Para quem deixa o joBot rodar duas vezes por dia sozinho, a busca trava até a pessoa voltar. O 2Captcha é um serviço pago que resolve o desafio por pessoa de fora; a pessoa que já tem conta lá quer usar.

O joBot continua de uso pessoal: a chave é da pessoa, o saldo é da pessoa, o risco com os termos dos sites é da pessoa (ADR 0004 e 0005). O projeto só dá o botão e mostra o risco com franqueza.

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos

1. A pessoa guarda a chave do 2Captcha em Configurações, numa aba nova "Serviços", e liga ou desliga o uso num interruptor.
2. A pessoa testa a chave num botão e vê o saldo.
3. Na navegação com login (fase 2), com a chave posta e o interruptor ligado, o joBot manda o desafio ao 2Captcha, recebe o token e segue.
4. Qualquer falha cai no comportamento de hoje da ADR 0005: aviso vermelho e janela parada para a pessoa resolver.
5. A tela é bonita e acessível: interruptor animado, campos com estilo próprio, estado de espera e resultado com animação leve, tudo respeitando "reduzir movimento".
6. Fica registrado, sem construir agora, que a IA pode rodar pela sessão do Codex CLI da pessoa, e que cada backend de sessão ganha um botão "Baixar" (parte F).

Não objetivos (ficam como estão)

- As fontes públicas (ADR 0004) não mudam: CAPTCHA, 401, 403 ou bloqueio continua sendo "a fonte falhou". O 2Captcha nunca age nelas.
- hCaptcha fica fora: não está na documentação pública do 2Captcha (conferido em 2026-11-15).
- Proxy do 2Captcha, tarefas com proxy e CAPTCHA de imagem ou de texto ficam fora.
- Nada de resolver CAPTCHA na fase 1, que não tem navegador (`pyproject.toml:13-20`: o Playwright só existe no grupo `dev`, `pyproject.toml:28-29`).
- Nada de configuração para o teto de gasto: o teto é valor fixo no código.
- O joBot continua sem digitar senha, sem clicar em "candidatar" e sem mexer na conta (ADR 0005). Resolver CAPTCHA não muda isso.
- Parte F: nada é construído agora.

Anti-objetivos (o que isto não pode fazer)

- Nunca usar o 2Captcha sem chave salva e interruptor ligado. Nasce desligado.
- Nunca mandar dado pessoal ao 2Captcha: só o endereço da página, a `sitekey` (código público do desafio na página) e o user agent do navegador.
- Nunca deixar a chave aparecer no HTML devolvido, no log, numa mensagem de erro, numa exceção, na URL, na linha de comando ou num teste.
- Nunca gastar sem limite: no máximo 30 resoluções por dia.
- Nunca esconder gasto: cada resolução vai para o `jobot.log`, com o custo.
- Nunca insistir: uma tentativa por página por rodada.
- Nunca carregar recurso externo no painel: o link do site do 2Captcha abre no navegador da pessoa.

## 3. Restrições

Do `CLAUDE.md` do projeto, das ADRs e das lições (`registros/padroes.md`):

- Painel só em `127.0.0.1`, sem recurso externo, CSP sem script inline (`painel/app.py:19-20`: `script-src 'self'; style-src 'self'`). JS só em arquivo próprio (`painel/static/js/app.js`).
- O painel não importa `httpx` (`tests/unidade/test_camadas.py:48-49`). O pedido ao 2Captcha sai do núcleo, pelo `ClienteEducado`, e o painel só chama uma função do núcleo, do jeito que `painel/rotas/empresas.py:106-116` já faz.
- O núcleo é puro: não importa outra camada, nem FastAPI, nem Jinja2 (`CLAUDE.md`, seção Mapa). O cofre da chave mora em `sistema` (acessa o sistema) e o núcleo recebe a chave como texto.
- Sem dependência nova sem decisão. A `keyring` já foi decidida na ADR 0014 (licença MIT) e ainda não está no `pyproject.toml`; entra fixada com `==`. Se não instalar no Python 3.14, vai ao `duvidas.md`; nunca se tenta um nome parecido.
- Segredo e privacidade: ADR 0014. Esta decisão emenda uma linha dela (ADR 0022).
- Todo texto novo do painel entra em `i18n/pt` e `i18n/en`, com o mesmo conjunto de chaves; chave com parâmetro é contrato. Conjunto fechado traduzido por `t("prefixo." ~ codigo)` pede teste que percorre o conjunto nos dois idiomas.
- Interruptor: o padrão mora só em `cadastros.PADROES` (`banco/cadastros.py:32-42`); o teste prova os dois lados.
- Falha de sistema na tela vira chave de i18n fixa; o detalhe vai ao log. Aqui o detalhe nunca leva a chave: o teste põe um segredo na exceção e confere que ele aparece zero vezes na resposta e zero no log.
- Rede nova muda os quatro textos juntos: README em pt e en e `configuracoes.privacidade.telemetria` em pt e en (`painel/i18n/pt/configuracoes.json:45`), que listam todo caminho de rede, com o teste `test_privacidade_cita_todos_os_pedidos` (`tests/unidade/test_documentos.py:435-441`).
- Coleta educada: o `ClienteEducado` com o user agent fixo (`nucleo/http.py:219`), relógio injetado e nenhum teste com rede (`tests/conftest.py` bloqueia tudo fora de `127.0.0.1`).

## 4. Como funciona hoje (fatos conferidos)

Regra atual de CAPTCHA

- ADR 0005, seção "CAPTCHA" (`docs/decisions/0005-sites-com-login.md:25-29`): aviso vermelho no painel e no computador; a janela fica parada para a pessoa resolver; as outras fontes continuam; "o joBot nunca tenta contornar CAPTCHA".
- ADR 0014 (`docs/decisions/0014-seguranca-e-privacidade.md:18`): "O joBot nunca digita senha e nunca contorna CAPTCHA."
- ADR 0004: fontes públicas, "nunca contorna login, CAPTCHA ou bloqueio anti-robô" (seção "Coleta educada"). O `CLAUDE.md` do projeto repete isso na regra de coleta educada.
- ADR 0017 (`docs/decisions/0017-fases.md:15`): a fase 2 é "Chrome visível, mapeamento dos sites e tratamento de CAPTCHA". Status: planejada.
- O 401 e o 403 viram `Bloqueio` no cliente (`nucleo/http.py`, classe `Bloqueio`): a fonte falhou.
- Texto público que diz "não contorna CAPTCHA": `README.md:105` (e o par em inglês), `wiki/A-ideia-e-a-historia.md:51` e `:60`, `wiki/Perguntas-frequentes.md:48` e `:53-56`, e os resumos de decisões em `wiki/Decisoes.md` e `wiki/Decisions.md`. Eles continuam certos para a fase 1; quando a navegação com login existir, mudam junto (seção 6).

Cliente HTTP

- `ClienteEducado` (`nucleo/http.py:202`): user agent fixo `joBot/<versão> (+https://github.com/fezarosa-dev/joBot)` (`:219`), pausa por host (`_enviar`, travas por host), três esperas em 429 e 503 (`ESPERAS_LIMITE`, `:21`), duas novas tentativas em erro de rede ou 5xx (`ESPERAS_ERRO`, `:22`), cinco saltos de redirecionamento (`MAX_SALTOS`).
- `HttpDoEscopo.pedir` aceita `POST` com `corpo_json` (`nucleo/http.py:302-312`; o protocolo em `:50-61`). O escopo (`ClienteEducado.escopo`, `:225`) recebe `espera_s`, que é a pausa mínima entre pedidos ao mesmo host.
- Não existe lista de hosts permitidos no cliente. O `_conferir` (`:238`) só confere o esquema `http` ou `https` e tira `Cookie`, `Origin`, `Authorization` e `Referer`. A conferência de DNS e de host local roda só nos saltos de redirecionamento (`_conferir_salto`). Então `api.2captcha.com` passa sem mudar o cliente. O construtor confere isso com um teste.
- Cabeçalhos aceitos em pedido: `accept`, `accept-language`, `content-type`, `range`, `x-tenant` (`:24`). A chave do 2Captcha vai no corpo JSON (`clientKey`), não em cabeçalho.
- O painel já monta um `ClienteEducado` por pedido, com o transporte de teste em `app.state.transporte` e o relógio do painel (`painel/rotas/empresas.py:106-116`), e limita o tempo com `asyncio.timeout(PRAZO_S)` (`PRAZO_S = 120.0`, `:55`). O botão "Testar chave" segue esse molde.
- Risco conhecido: o cliente repete o pedido em erro de rede e em 5xx (`ESPERAS_ERRO`). Um `createTask` repetido pode abrir duas tarefas e cobrar duas vezes. Ver seção 5, parte D.

Configuração

- `cadastros.PADROES` (`banco/cadastros.py:32-42`) guarda o padrão de cada interruptor; `ler_config` (`:226`) e `gravar_config` (`:240`) leem e gravam a tabela `config`. O teste `test_todo_interruptor_da_13_7_tem_caso` (`tests/integracao/test_integracao_final.py:532-537`) exige um caso de teste para toda chave de `PADROES` que termine em `_ligada`, `_ligadas`, `_ligado` ou `_ligados`.
- Configurações: `GRUPOS = ("fontes", "funcoes", "segundo-plano", "aparencia", "privacidade")` (`painel/rotas/configuracoes.py:36`), `_PARCIAIS` (`:47`), `_CONTEXTOS` (`:103`), `_GRAVADORES` (`:215`); as abas vêm de `GRUPOS` (`:117`) e o texto da aba de `configuracoes.grupo.<slug com _>` (`painel/i18n/pt/configuracoes.json:4-8`). O teste de tela confere as abas (`tests/tela/test_configuracoes.py:40-55`).
- Segredo: não há código de cofre. A `keyring` não está nas dependências (`pyproject.toml:13-20`). A pasta de dados já fecha arquivos em 0600 (`sistema/pastas.py:10`, `preparar_pasta` em `:32-38`).
- O texto de privacidade lista cada pedido de rede (`painel/i18n/pt/configuracoes.json:45`, par em `en`) e não cita o 2Captcha.

Visual

- O interruptor atual é o `.chave`: um `<input type="checkbox">` com `appearance: none`, trilho e bolinha que corre com mola (`painel/static/css/configuracoes.css:140-182`), macro em `templates/configuracoes/_interruptor.html:2-9`. Já tem foco visível (`:175`) e estado desativado (`:180`, só `opacity: 0.5`). Não estica ao apertar e não anima a cor do trilho com tom próprio de "desativado".
- Tokens de movimento: `--mola` e `--duracao` (`painel/static/css/base.css:44-45`); `prefers-reduced-motion` zera tudo (`base.css:340-350`) e o `.chave` repete a regra (`configuracoes.css:207-211`).
- Campos: só o `input[type="number"]` tem estilo próprio (`configuracoes.css`, regra `.config-form .campo input[type="number"]`); texto e senha ainda não. Botões `.botao`, `.botao-primario` e `.botao-secundario` existem e usam `transform: scale(0.96)` ao apertar.
- O HTMX é configurado com `includeIndicatorStyles: false` (`templates/base.html:29`): a classe `htmx-request` é posta no elemento, mas nenhum estilo vem de graça. O CSS do projeto desenha o indicador.
- O token CSRF vai em todo pedido do HTMX (`painel/static/js/app.js:7-9`); o foco vai para o `[data-foco]` do trecho trocado (`:13-22`).
- Link que abre fora usa `target="_blank" rel="noopener noreferrer"` (`templates/base.html:76`, `templates/fontes/pagina.html:13`), e o cabeçalho `Referrer-Policy: no-referrer` já vai em toda resposta (`painel/app.py`, `CABECALHOS`).

IA

- ADR 0009: backends incluem a "sessão do Claude Code" (ADR 0010); teste ao ligar com sinal de espera, ✓ ou erro com o que fazer, e o backend fica desligado se falhar. Tudo da fase 4 (a IA; a numeração atual está na ADR 0017). Não há código de IA.
- ADR 0010: o joBot não tem login do Claude; roda `claude auth status` e `claude -p`; a marca aparece só em texto simples, com o aviso de que o joBot não é afiliado.

Fatos públicos usados (conferidos em 2026-11-15)

- 2Captcha, API JSON em `https://api.2captcha.com`: `createTask`, `getTaskResult` e `getBalance`, com `clientKey` no corpo. `getBalance` devolve `{"errorId":0,"balance":...}`. Resposta de `getTaskResult`: `status` `processing` ou `ready`, e `solution` e `cost` quando pronto. Erro vem com `errorId` diferente de zero, inclusive com HTTP 200. Páginas: <https://2captcha.com/api-docs/get-task-result>, <https://2captcha.com/api-docs/get-balance>, <https://2captcha.com/api-docs/report-correct>.
- Tarefas sem proxy: `RecaptchaV2TaskProxyless` (`websiteURL`, `websiteKey`; opcionais `isInvisible`, `userAgent`, `cookies`; resposta `gRecaptchaResponse`), `RecaptchaV3TaskProxyless` (`websiteURL`, `websiteKey`, `minScore`; opcional `pageAction`) e `TurnstileTaskProxyless` (`websiteURL`, `websiteKey`; opcionais `action`, `data`, `pagedata`; resposta `token`). Páginas: <https://2captcha.com/api-docs/recaptcha-v2>, <https://2captcha.com/api-docs/recaptcha-v3>, <https://2captcha.com/api-docs/cloudflare-turnstile>.
- Limites: esperar pelo menos 5 s entre consultas de resultado; `ERROR_NO_SLOT_AVAILABLE` pede 5 s de espera; `ERROR_ZERO_BALANCE` pede 60 s; frequência errada pode bloquear a conta. Página: <https://2captcha.com/api-docs/limits>.
- Códigos de erro: 1 chave inexistente, 2 sem vaga no momento, 10 sem saldo, 11 IP não permitido, 12 CAPTCHA não resolvível (o preço volta), 21 IP bloqueado, 23 tarefa não suportada, 31 `sitekey` inválida, 55 conta suspensa, 110 parâmetro errado. Página: <https://2captcha.com/api-docs/error-codes>.
- Preço oficial por mil resoluções: reCAPTCHA v2 de R$ 5 a R$ 15,50; v3 de R$ 7,50 a R$ 15,50; Turnstile R$ 7,50. Página: <https://2captcha.com/pricing>. O preço muda; o joBot mostra o custo que a API devolve (`cost`), não uma tabela fixa.
- Tela "Just a moment" do Cloudflare: a documentação só descreve o fluxo com navegador (interceptar a chamada de renderização do Turnstile e rodar o retorno com o token). Um cliente HTTP puro, sem navegador, não basta.
- Claude Code: página oficial de instalação <https://code.claude.com/docs/en/setup>; exige conta paga (Pro, Max, Team, Enterprise ou Console).
- Codex CLI (OpenAI): página <https://learn.chatgpt.com/docs/codex/cli>. Entrar com a conta do ChatGPT usa a assinatura; `codex exec "<tarefa>"` roda sem interação com as credenciais salvas. A documentação recomenda chave de API para automação e descreve o uso do plano do ChatGPT em automação privada como avançado, sem autorizar nem proibir. Os Termos de Uso vigentes da OpenAI não foram lidos (a página recusou o acesso). Páginas: <https://learn.chatgpt.com/docs/auth>, <https://learn.chatgpt.com/docs/non-interactive-mode.md>, <https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan>.

## 5. O como decidido, por parte

### Parte A. Escopo: só a navegação com login

- O 2Captcha só age na navegação com login da fase 2: Chrome visível pelo Playwright, com o perfil do joBot (ADR 0005).
- Por quê:
  - a fase 1 não tem navegador (seção 4);
  - o token sozinho não passa o desafio do Cloudflare num cliente HTTP (seção 4);
  - as fontes públicas ficam educadas e mantidas pela comunidade (ADR 0004, ADR 0018): um CAPTCHA ali quer dizer "esta fonte não quer robô", e o joBot respeita.
- Vem desligado. O interruptor fica travado (desativado) enquanto não houver chave salva.
- O que entra antes da fase 2, junto da 0.2.0: a aba "Serviços" com o cartão do 2Captcha, o cofre da chave, o interruptor e o botão de teste, mais o cliente da API no núcleo (saldo e resolver), testado offline. A cola com o navegador (achar o desafio na página e injetar o token) entra com a fase 2.
- O cartão diz com franqueza que o recurso vale para a navegação com login, que chega numa versão futura (parte C).

### Parte B. A chave e o interruptor

- Onde fica a chave: no cofre de senhas do sistema, pela biblioteca `keyring` (ADR 0014), fixada com `==` no `pyproject.toml`. Sem cofre: arquivo legível só pelo usuário (0600) na pasta de dados, e aviso no painel. Num computador sem cofre (comum em Linux sem ambiente gráfico completo e dentro de distrobox), o arquivo é o caminho normal; o aviso diz isso sem alarme.
- O cofre e o arquivo moram em `sistema` (novo módulo, por exemplo `sistema/cofre.py`); o núcleo e o painel recebem a chave como texto. O arquivo nasce com `os.open` e modo 0600 explícito, não depende do umask (mesma lição do log, `sistema/pastas.py:44-48`), e ignora symlink.
- Onde fica o interruptor: tabela `config`, chave `captcha_ligado` (nome no padrão das outras: termina em `_ligado`, `banco/cadastros.py:32-42`), com padrão `False` em `cadastros.PADROES`. O teste de `tests/integracao/test_integracao_final.py:532-537` passa a exigir um caso para ela.
- O interruptor grava na hora, num POST próprio (`hx-post` ao mudar, com o CSRF do `app.js:7-9`), e o servidor recusa ligar quando não há chave salva (a trava não é só do HTML). Desligar sempre pode.
- A chave nunca volta ao HTML: a tela mostra só "•••• " e os 4 últimos caracteres, e só quando a chave tem 12 caracteres ou mais; chave mais curta mostra só os pontos. O campo de digitar vem sempre vazio.
- Salvar com o campo vazio mantém a chave atual. Apagar a chave é um POST próprio, com CSRF, que também desliga o interruptor.
- A chave é recortada e confere o formato antes de salvar: só letras, números, tamanho de 16 a 64, e sem espaço ou quebra de linha no meio. Valor torto volta com mensagem, sem 500 e sem gravar.

### Parte C. O cartão na aba "Serviços"

Uma aba nova, `servicos`, no fim de `GRUPOS` (`painel/rotas/configuracoes.py:36`), com texto `configuracoes.grupo.servicos` ("Serviços" e "Services"). Dentro, um cartão do 2Captcha, de cima para baixo:

1. Título e uma frase: "Resolve CAPTCHA por você na navegação com login, que chega numa versão futura."
2. O interruptor "Usar o 2Captcha", com a ajuda: "Desligado, o joBot para e espera você resolver, como sempre." Desativado, com a explicação "Salve uma chave primeiro", enquanto não houver chave.
3. O campo da chave, mascarado, com o botão olho (mostrar e ocultar o que a pessoa digitou; a chave salva nunca volta), o botão "Salvar" e o botão "Apagar chave" (só aparece com chave salva).
4. O botão "Testar chave". Testa a chave digitada no campo, se houver, senão a salva; não grava. Mostra o saldo ("Chave válida. Saldo: 0,94") ou o erro em linguagem simples.
5. O aviso honesto, sempre visível, sem esconder em "saiba mais":
   - vale só para a navegação com login, que ainda não existe; as fontes públicas nunca usam;
   - resolver CAPTCHA pode ir contra os termos de alguns sites, e a conta deles pode ser restringida;
   - cada resolução custa dinheiro da conta da pessoa no 2Captcha; o joBot para depois de 30 por dia;
   - o que vai ao 2Captcha: o endereço da página, o código público do desafio e o user agent do navegador; nenhum dado pessoal.
6. O link "Abrir o site do 2Captcha" (`target="_blank" rel="noopener noreferrer"`, endereço <https://2captcha.com>), para a pessoa criar conta e pôr saldo.

O texto da privacidade (`configuracoes.privacidade.telemetria`) e o README ganham a frase do 2Captcha ("só com a chave posta e o interruptor ligado, na navegação com login, ao 2Captcha"), nos quatro lugares juntos (seção 3).

### Parte D. O cliente da API (núcleo)

- Módulo novo no núcleo, `nucleo/captcha.py` (nome final do construtor), puro: recebe um `HttpEducado`, a chave e o relógio injetado; nunca lê banco, arquivo ou cofre.
- Duas funções públicas:
  - `saldo(http, chave)`: `POST https://api.2captcha.com/getBalance` com `{"clientKey": chave}`; devolve o saldo como `Decimal` (nunca `float`).
  - `resolver(http, chave, desafio, relogio)`: `createTask`, depois `getTaskResult` até `ready`; devolve `Solucao(token, custo, user_agent_do_token)` ou levanta um erro do conjunto fechado.
- O `desafio` é uma dataclass imutável: `tipo` (`recaptcha_v2`, `recaptcha_v3` ou `turnstile`), `url`, `sitekey`, `user_agent`, e os opcionais de cada tipo (`invisivel`, `acao`, `min_score`). Tipo fora do conjunto é recusado antes de qualquer pedido.
- Tarefas usadas, todas sem proxy: `RecaptchaV2TaskProxyless` (com `isInvisible`), `RecaptchaV3TaskProxyless` (com `minScore` e `pageAction`) e `TurnstileTaskProxyless`. O `userAgent` do navegador vai em todas que o aceitam; a resposta do Turnstile traz também um `userAgent`, e a fase 2 confere na documentação se o navegador precisa usá-lo.
- Consulta: pelo escopo `ClienteEducado.escopo(espera_s=5.0, condicional=False)`, que já garante 5 s entre pedidos ao mesmo host (`nucleo/http.py:225`, `_enviar`). Tempo-limite total de 180 s por resolução, com `asyncio.timeout`; estourou, vira "tempo esgotado".
- `ERROR_NO_SLOT_AVAILABLE` espera 5 s e tenta de novo dentro dos 180 s; `ERROR_ZERO_BALANCE` não tenta de novo (a doc pede 60 s, mas o joBot desiste e avisa saldo zero).
- Duplicação: o `createTask` não passa pela repetição automática do cliente (que repete em erro de rede e 5xx, `ESPERAS_ERRO`). O construtor garante isso do jeito que o cliente permitir (por exemplo, `max_pedidos` do escopo, ou um parâmetro novo do `pedir` para "não repetir"), com teste: erro de rede no `createTask` não abre segunda tarefa. Se o jeito pedir mudança de contrato público do `HttpEducado`, é R4: vai ao `duvidas.md`.
- Erros: um conjunto fechado, `Falha.CHAVE_INVALIDA`, `SEM_SALDO`, `SEM_VAGA`, `NAO_RESOLVIVEL`, `IP_BLOQUEADO`, `CONTA_SUSPENSA`, `TEMPO_ESGOTADO`, `OUTRO`. Mapa da API para o conjunto: 1 → chave inválida; 10 → sem saldo; 2 → sem vaga; 12 → não resolvível; 11 e 21 → IP bloqueado; 55 → conta suspensa; qualquer outro código ou resposta fora do formato → outro. O texto vem do catálogo `captcha.erro.<codigo>`, em pt e en. O código bruto e a resposta crua vão só ao log, sem a chave.
- Resposta fora do formato (JSON torto, `errorId` ausente, `status` desconhecido, token vazio) é "outro", nunca sucesso.
- Depois que o token funciona ou falha na página, a fase 2 pode chamar `reportCorrect` ou `reportIncorrect`; isso não entra agora. O construtor só deixa o `taskId` na `Solucao`.

### Parte E. Visual e movimento

Princípios (as skills de design do projeto, em linguagem simples): mexer só o que dá retorno, sempre com mola curta, nunca travar a pessoa, e tudo continua legível sem movimento.

- Interruptor: melhorar o `.chave` que já existe (`configuracoes.css:140-182`):
  - a bolinha estica um pouco para os lados enquanto o botão está apertado (`:active`), e volta com a mola (`--mola`);
  - o trilho muda de cor em transição, com o tom do destaque quando ligado;
  - anel de foco visível (já há `:focus-visible`, `:175`), com o mesmo token `--foco`;
  - estado desativado de verdade: trilho opaco mais claro, bolinha sem sombra, cursor `not-allowed`, e a explicação do porquê ao lado, em texto (não só `opacity`);
  - continua sendo um `<input type="checkbox">` por baixo, com `role="switch"` e rótulo, para leitor de tela e teclado (espaço liga e desliga).
- Campos de texto e de chave: classe nova `.campo-texto` (em `configuracoes.css`), com borda, raio, altura mínima de 2,5 rem, `font: inherit`, cores só dos tokens da casca (`--borda`, `--superficie`, `--texto`), foco com anel e `transition` curta de borda e sombra. O olho do navegador (`::-ms-reveal`) fica escondido e o do joBot é um botão com `aria-pressed` e rótulo "Mostrar o que digitei" / "Ocultar".
- Botão "Testar chave": enquanto o pedido corre, a classe `htmx-request` (que o CSS do projeto desenha, `base.html:29`) troca o texto por um indicador de espera (um pontinho que pulsa) e desativa o botão; sem pedido duplo.
- Resultado do teste: entra num `<div aria-live="polite">` com fade de 200 ms e deslize de 6 px para cima; verde com ✓ ou vermelho com ✕ e a explicação do que fazer, usando tokens já contrastados (qualquer cor nova pede token em `base.css` e par em `test_contraste_minimo`, como na lição de CSS).
- Troca do interruptor: o servidor devolve o trecho do cartão atualizado e um "Salvo" no `aria-live`, que some sozinho depois de 2 s (a T193 passou para 5 s em todas as telas de Configurações; ver D131).
- Tudo respeita `prefers-reduced-motion` (`base.css:340-350` já zera `transition` e `animation`; o construtor não pode usar `!important` contra isso). Sem movimento, o resultado só aparece.
- Nada de controle padrão: nenhum `<input type="checkbox">` sem a classe `.chave`, nenhum `<select>` sem estilo no cartão; o botão e o link usam `.botao`.
- JS só em arquivo próprio: o olho e o fechamento do aviso entram no `app.js` (CSP, seção 3), sem script inline.
- Acessibilidade: todo campo com `<label>`, ajuda ligada por `aria-describedby`, `aria-live` na região do resultado (vazia sai do layout, lição de `:empty`), foco visível, ordem de tabulação na ordem da tela, alvos de toque com pelo menos 2,5 rem.

### Parte F. IA pela sessão do Claude Code e do Codex (só registro; fase 4)

Nada é construído agora. É a D125 e a emenda na ADR 0009.

- A sessão do Claude Code já está decidida (ADR 0010, ADR 0009).
- Entra também, para confirmar, a sessão do Codex CLI da pessoa: o joBot roda `codex exec` numa pasta temporária vazia, com a saída em formato fixo (as opções exatas são conferidas na fase 4), no mesmo molde da 0010 (a pessoa entra pelo fluxo da própria OpenAI; o joBot nunca toca na credencial). Teste ao ligar, no molde da 0009 (sinal de espera, ✓ ou erro com o que fazer).
- Antes de construir, conferir nos termos da OpenAI se o uso do plano do ChatGPT em automação pessoal é permitido (a documentação recomenda chave de API e não autoriza nem proíbe o plano, seção 4). Se não for permitido, o Codex entra só com chave de API, que é o backend OpenAI que já existe na ADR 0009.
- "Codex" é marca da OpenAI. O joBot não é afiliado à OpenAI. O nome aparece só em texto simples, como o do Claude Code na ADR 0010.
- Botão "Baixar" ao lado de cada backend de sessão. Pela [ADR 0023](../../decisions/0023-tudo-pelo-painel.md), ele faz o joBot instalar a ferramenta pelo instalador oficial dela (Claude Code: <https://code.claude.com/docs/en/setup>; Codex: a página oficial do Codex CLI, endereço conferido na fase 4, hoje <https://learn.chatgpt.com/docs/codex/cli>), a pedido da pessoa, e o joBot nunca remove essas ferramentas. O painel só mostra o botão e não carrega recurso externo; quem baixa é o joBot. A página oficial continua como link ao lado, para quem quiser ver antes.
- O botão aparece quando o programa não é achado no `PATH` (`shutil.which`); com o programa instalado, o botão some e o teste ao ligar assume. O link da página oficial é `target="_blank" rel="noopener noreferrer"`.

## 6. O que fica para o construtor

- Nomes finais de módulos, funções, chaves de i18n e classes CSS, seguindo o padrão das existentes.
- Verificar que a `keyring` instala no Python 3.14 e escolher o módulo do cofre; sem cofre disponível, o arquivo 0600. Pacote que não instala: nunca um nome parecido; vai ao `duvidas.md`.
- Onde mora o contador do teto de 30 resoluções por dia (sugestão: uma chave em `config` com o dia local e o número; dia de calendário compara com o dia local, não com UTC) e o cuidado de contar antes de pedir, para a repetição do cliente não furar o teto.
- O jeito de impedir a repetição do `createTask` (parte D), e o limite de tamanho do corpo da resposta (`teto_bytes` do `pedir`).
- A cola da fase 2 (achar o desafio na página, injetar o token, `turnstile.render`, o retorno do reCAPTCHA) fica no plano da fase 2.
- Quando o 2Captcha puder agir de verdade, atualizar juntos: `README.md` e `README.en.md` (as linhas "Não contorna CAPTCHA" e "Does not bypass CAPTCHA"), as páginas da `wiki/` que repetem isso (seção 4) e o `CLAUDE.md` do projeto (a regra de coleta educada passa a dizer "sem chave do 2Captcha ligada" para a navegação com login). Nada disso muda agora.
- O teste de documentos (`tests/unidade/test_documentos.py`, `test_changelog_cita_as_adrs_que_existem`) agora aceita a última ADR citada em qualquer ponto do CHANGELOG, então a 0.1.0 não é reescrita; a 0022 já está em "Não lançado" nos dois CHANGELOGs.
- Repartir em tarefas `Tn` no plano (sugestão: cofre e `PADROES`; cliente da API no núcleo; aba "Serviços" e rotas; visual e `app.js`; textos de privacidade e README).

## 7. Perguntas pendentes do dono

1. O teto de 30 resoluções por dia está bom?
   Recomendação: sim. Pelo preço público (de R$ 0,005 a R$ 0,0155 por resolução, seção 4), 30 por dia custam de R$ 0,15 a R$ 0,47 por dia. Valor fixo no código; mudar é uma linha.
2. A chave sem cofre do sistema pode ficar num arquivo só do usuário (0600), com aviso?
   Recomendação: sim. É o que a ADR 0014 já diz para os outros segredos.
3. O 2Captcha vale para todos os sites com login, ou a pessoa escolhe por site?
   Recomendação: todos, com o interruptor único agora. A escolha por site (cada site já tem o seu liga/desliga, ADR 0005) pode vir na fase 2, se o dono quiser, porque o risco com os termos muda de site para site.
4. O saldo aparece só quando a pessoa clica em "Testar chave"?
   Recomendação: sim. Assim o joBot não faz pedido ao 2Captcha sem a pessoa pedir ou sem uma resolução em andamento.
5. O nome da aba é "Serviços"?
   Recomendação: sim. Cabe a chave do 2Captcha agora e, na fase 4, o cartão das IAs de sessão.
6. Codex: se os termos da OpenAI não permitirem o plano do ChatGPT em automação, entra só com chave de API?
   Recomendação: sim (D125).

Enquanto o dono não responde, o construtor segue as recomendações e registra cada uma no `duvidas.md` como "para confirmar".

## 8. Testes esperados, por parte

Todos com o relógio injetado e sem rede (`tests/conftest.py`). Teste de rede do cliente usa `httpx.MockTransport` pelo `ClienteEducado`, e o servidor local só em `127.0.0.1`.

A. Escopo (`tests/unidade/test_captcha.py`, `tests/integracao/test_rota_configuracoes.py`)
- `captcha_ligado` vem `False` por `PADROES`; sem linha vale o padrão e `False` gravado se mantém (os dois lados).
- Nenhuma função do núcleo de fonte pública chama o cliente do 2Captcha: teste por AST ou por `grep` do módulo nos coletores e na `agenda` (a fase 1 nunca importa `captcha`).
- `nucleo/captcha.py` não importa FastAPI, Jinja2, `sistema` nem `banco` (`tests/unidade/test_camadas.py`).

B. Chave e interruptor (`tests/unidade/test_cofre.py`, `tests/integracao/test_rota_configuracoes.py`)
- Gravar, ler e apagar com cofre falso; sem cofre, o arquivo nasce 0600 pelo `os.open`, com a pasta fechada; symlink no lugar do arquivo é recusado.
- Ligar sem chave: 4xx no servidor (não só `disabled` no HTML); com chave: grava. Apagar a chave desliga.
- Salvar com o campo vazio mantém a chave; chave torta (espaço, curta, longa, caractere fora de letra e número) volta com mensagem, nada gravado e sem 500.
- Segredo nunca no HTML: o teste salva uma chave de teste e confere que a página mostra só os 4 últimos caracteres (ou só pontos se tiver menos de 12), e que a chave inteira não aparece em nenhuma resposta, nem no `Location`.
- Segredo nunca no log: o teste põe o segredo na exceção do cofre e na do cliente e confere `sum(SEGREDO in r.getMessage() for r in caplog.records) == 0`, e zero na resposta (o log guarda só o tipo do erro e o código da API).

C. O cartão (`tests/integracao/test_rota_configuracoes.py`, `tests/tela/test_configuracoes.py`)
- A aba `servicos` existe e abre; `GRUPOS` e o teste de abas acompanham (`tests/tela/test_configuracoes.py:40-55`).
- Todas as chaves novas em pt e en, mesmo conjunto; os códigos de erro percorridos nos dois idiomas.
- Teste de tela: sem chave, o interruptor está desativado e a explicação aparece; salvar uma chave habilita; ligar grava (espera da resposta real com `page.expect_response`, sem `sleep`); "Testar chave" mostra o indicador de espera e depois o saldo (rota falsa por `page.route`) ou o erro; claro e escuro.
- Contraste: cor nova entra em `test_contraste_minimo`.
- O link do 2Captcha tem `target="_blank"` e `rel="noopener noreferrer"`; nenhum recurso externo é carregado (a CSP segue igual, `painel/app.py:19-20`).

D. Cliente da API (`tests/unidade/test_captcha.py`, com `MockTransport` e `RelogioFalso`)
- `saldo`: devolve `Decimal`; `errorId` diferente de zero vira a falha do conjunto; resposta torta vira "outro".
- `resolver`, um caso por tipo (reCAPTCHA v2 comum e invisível, v3 com `minScore`, Turnstile): o corpo do `createTask` leva `type`, `websiteURL`, `websiteKey` e o `userAgent`, e nada de pessoal; o token sai da chave certa de cada resposta.
- Consulta: `processing` duas vezes e depois `ready` espera 5 s entre as consultas (relógio injetado, sem `sleep` real); passou de 180 s, `TEMPO_ESGOTADO`.
- Cada código do mapa de erros (1, 2, 10, 11, 12, 21, 55 e um desconhecido) vira a falha esperada; `ERROR_NO_SLOT_AVAILABLE` tenta de novo; `ERROR_ZERO_BALANCE` não.
- Resposta com token vazio ou `status` desconhecido não é sucesso.
- Erro de rede no `createTask` não abre segunda tarefa (conta os `createTask` no transporte falso).
- Tipo fora do conjunto é recusado sem pedido.
- Teto: a 31ª resolução do dia local é recusada antes do pedido, e o contador zera no dia seguinte (entrada fora de UTC).
- A chave nunca aparece na mensagem de nenhuma exceção do módulo.

E. Visual (`tests/tela/test_configuracoes.py`)
- O interruptor muda de estado com espaço e com clique; o `role="switch"` e o `aria-checked` acompanham.
- Com `reduced_motion="reduce"` do Playwright, a `transition-duration` computada do `.chave` e da bolinha é `0s`.
- O botão de teste fica `disabled` e com a classe `htmx-request` durante o pedido (rota que demora, controlada por evento, sem `sleep`).
- A região do resultado tem `aria-live="polite"` e sai do layout quando vazia (geometria medida, lição de `:empty`).
- Nenhum `<input type="checkbox">` do cartão sem a classe `.chave`.

F. IA pela sessão (nada agora)
- Quando a fase 4 construir: o botão "Baixar" só aparece sem o programa no `PATH` (com `shutil.which` falso nos dois casos) e instala pelo instalador oficial (executor falso, offline); o link da página oficial é o oficial e tem `rel="noopener noreferrer"`; o teste ao ligar do Codex segue o da 0009 (offline, com executável falso).
