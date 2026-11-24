# 0010. Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-17 (o texto legal atual do Claude Code e a sessão que espera o dono, para confirmar, D185 e [0026](0026-ia-da-fase-4.md); a instalação pelo joBot, D138)

## Contexto

O dono do projeto perguntou se a pessoa vai precisar fazer login do Claude dentro do joBot, ou dentro de um container. Container é uma caixa isolada onde um programa roda separado do resto do computador.

A Anthropic, empresa que faz o Claude, tem regras claras para apps de terceiros. Em resumo, um app de terceiros não pode:

- oferecer a tela de login do Claude dentro dele;
- usar a assinatura de alguém (planos Free, Pro, Max ou Ultra) para mandar pedidos em nome dessa pessoa;
- coletar, guardar ou repassar credenciais ou tokens do Claude. Credencial é o que prova quem você é, como uma senha. Token é uma espécie de senha gerada pelo sistema depois do login.

Além disso, um produto que roda o Claude Code fica sob os Termos Comerciais da Anthropic: o Claude Code não pode ser modificado, os métodos de login dele não podem ser removidos e cada pessoa entra com a própria chave de API, assinatura ou provedor. O nome "Claude Code" só pode aparecer em texto simples, nunca no nome ou no logo do produto.

O login tem de acontecer sempre pelo fluxo da própria Anthropic. Por isso esta decisão define como o joBot usa o Claude sem tocar no login.

O projeto está em desenvolvimento e ainda não tem código. Tudo abaixo é o que está planejado.

## Decisão

### Login

- O joBot não tem login do Claude.
- A pessoa instala o Claude Code ~~pelo site oficial~~ (desde a D138.7, também pelo joBot, que roda o instalador oficial a pedido dela e nunca o remove; ver [0023](0023-tudo-pelo-painel.md)) e entra uma vez pelo fluxo da Anthropic. Para isso, ela abre o terminal (a janela de comandos de texto do computador), roda `claude` e segue o `/login`.
- A credencial fica onde o Claude Code já guarda: na pasta `~/.claude` no Linux e no Windows (`%USERPROFILE%\.claude` no Windows) e no Keychain no macOS. Keychain é o cofre de senhas do macOS. O joBot nunca abre esse lugar. Se a variável `CLAUDE_CONFIG_DIR` estiver definida, a pasta muda; o joBot também não abre essa outra pasta.

### Como o joBot descobre se o Claude está pronto

- O joBot roda `claude auth status`.
- Se a pessoa estiver logada, o comando mostra um JSON (um formato de texto organizado em campos) com o campo `authMethod` e termina com código 0.
- Se não estiver logada, termina com código 1.
- O passo 0 da primeira execução usa essa resposta para oferecer o Claude sozinho, sem a pessoa precisar configurar nada.

### Como o joBot chama o Claude

- O joBot roda o Claude Code no modo sem tela (`claude -p`), com estas opções:
  - `--output-format json` e `--json-schema`: a resposta vem num formato fixo, no campo `structured_output`;
  - `--model claude-haiku-5-5` ou `--model claude-sonnet-5-5`;
  - `--tools ""`: nenhuma ferramenta ligada;
  - `--strict-mcp-config`: nenhum servidor MCP. MCP é um jeito de ligar o Claude a programas extras; aqui não liga nenhum;
  - `--no-session-persistence`: a conversa não fica salva.
- Código de saída diferente de zero é falha. Também é falha quando o campo `structured_output` não vem na resposta (por exemplo, numa recusa). Nos dois casos, a falha aparece no painel.
- Se a pessoa não estiver logada, o painel explica como entrar pelo terminal. O `/login` não funciona dentro do `claude -p`.

### Cuidados obrigatórios

- Nunca ler, copiar, guardar ou repassar credencial ou token do Claude.
- Nunca oferecer tela de login do Claude dentro do joBot.
- Nunca empacotar nem modificar o Claude Code.
- Tirar `ANTHROPIC_API_KEY` e `ANTHROPIC_AUTH_TOKEN` do ambiente da chamada, exceto no modo "chave da API". Com uma dessas variáveis presente, o Claude Code usa a chave, e a cobrança vai para a API sem a pessoa perceber. Pelo mesmo motivo, tirar também as variáveis que mandam o Claude Code para um provedor de nuvem (`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` e `CLAUDE_CODE_USE_FOUNDRY`).
- Antes de chamar no modo assinatura, rodar `claude auth status` e só seguir se o `authMethod` indicar o login da assinatura. Uma configuração como o `apiKeyHelper` (script que entrega uma chave de API) não sai pelo ambiente; se outro método estiver ativo, o painel mostra qual é e não faz a chamada. Os valores exatos de `authMethod` são conferidos quando esse backend for implementado.
- Rodar a chamada numa pasta temporária vazia. Assim o Claude Code não carrega hooks (comandos automáticos que rodam em certos momentos), arquivo `.mcp.json` ou `CLAUDE.md` de algum projeto. As configurações pessoais da pessoa em `~/.claude` continuam valendo.
- Não usar `--bare` no modo assinatura. Essa opção pula hooks e configurações, mas também não lê o login da assinatura: só aceita chave de API.
- Não usar nem pedir `CLAUDE_CODE_OAUTH_TOKEN` (um token de longa duração gerado por `claude setup-token`).

### Marca

- O nome aparece só em texto simples, como "funciona com o Claude Code". Nunca no nome do produto e nunca com logo.
- Junto vai o aviso: Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.

### Modelos

- Só Haiku 5.5 (`claude-haiku-5-5`) e Sonnet 5.5 (`claude-sonnet-5-5`), conforme a tarefa (ver 0009).
- Nunca Opus, para poupar o limite de uso da pessoa.

## Consequências

- Zero login extra: quem já usa o Claude Code no computador só escolhe essa opção.
- Cada pessoa usa a própria assinatura e os próprios limites. A conta e o custo são dela.
- Sem Docker isso funciona direto. Num container seria preciso logar de novo lá dentro ou dar ao container acesso à pasta de credenciais. E no macOS o login fica no Keychain, que o container não enxerga.
- Quem não tem o Claude usa chave da API, modelo local, palavras-chave ou IA manual.
- A versão GitHub Pages não usa o Claude Code.

## Regras da Anthropic

- O dono do projeto leu as regras da Anthropic e decidiu que esse uso está dentro delas: cada pessoa roda o próprio Claude Code, no próprio computador, com a própria assinatura e dentro do próprio limite. Nada é compartilhado entre pessoas, e o joBot não oferece login nem toca em credenciais.
- A opção fica mantida, com os cuidados técnicos acima.
- Registrado em duvidas.md (D1, resolvida em 2026-11-13).

## Fase 4: a sessão espera o dono (2026-11-17, para confirmar)

- O texto legal atual do Claude Code (página de política legal e de conformidade, lida em 2026-11-17) diz que o login das assinaturas serve ao uso comum do Claude Code e que quem constrói produto deve usar chave de API. A D1 e esta ADR continuam como desenho do backend, mas a pergunta volta ao dono: ele libera o login da assinatura para o joBot? (D185.5, para confirmar.)
- Até a resposta, nada da sessão do Claude Code é construído na fase 4, nem o botão Baixar dele no instalador (D185.5 e D185.17, para confirmar). Com a resposta, um lote próprio constrói e prova na máquina do dono, com os cuidados acima.
- O instalador oficial do Claude Code é um script remoto sem sha256 fixado; baixar e rodar sem sha256 também espera o dono (D185.18, para confirmar).
- "Tudo Claude" passa a usar a API da Anthropic, cobrada por uso, e diz isso na tela (D185.28, para confirmar).

## Fontes

Documentação oficial do Claude Code (em inglês). O texto acima resume essas páginas com palavras próprias.

- Política legal e de conformidade: <https://code.claude.com/docs/en/legal-and-compliance>
- Autenticação: <https://code.claude.com/docs/en/authentication>
- Modo sem tela: <https://code.claude.com/docs/en/headless>
- Referência dos comandos: <https://code.claude.com/docs/en/cli-reference>

## Ver também

- [0003. Tecnologias e instalação nativa (sem Docker)](0003-stack-e-instalacao-nativa.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0011. Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D185 (fase 4)](../../duvidas.md)
