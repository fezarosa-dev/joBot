# 0023. Tudo pelo painel: ferramentas, atualização e encerramento

- **Status:** aceita
- **Data:** 2026-11-15
- **Atualizada:** 2026-11-17 (Ferramentas sempre visível e o Modelo local removível; Claude Code e Codex esperam o dono; tudo para confirmar, D185 e [0026](0026-ia-da-fase-4.md))

## Contexto

O joBot é feito para quem nunca abriu um terminal (ADR 0003 e 0017). Hoje, atualizar e encerrar são comandos (`jobot atualizar`), e o navegador do Playwright é baixado por uma ação avulsa. Quando o instalador chegar (fase 3, ADR 0017), a pessoa vai escolher quais ferramentas quer. A escolha tem de poder mudar depois, sem terminal.

O dono respondeu às perguntas do memo em 2026-11-15. Este ADR junta as respostas que mudam como o joBot lida com ferramentas externas. A ordem das fases e as versões estão na [0017](0017-fases.md). Os detalhes e o que falta confirmar estão na D138 do `duvidas.md`.

## Decisão

### Tudo pelo painel

- Quem usa nunca precisa do terminal. O que hoje é comando ganha botão no painel, a começar por "Atualizar o joBot" e "Encerrar".
- Os comandos de terminal ficam como estão: este ADR não os tira (o `jobot atualizar` é da [0018](0018-manutencao-pela-comunidade.md)).

### Instalador com lista de ferramentas

- O instalador (fase 3) mostra uma lista de ferramentas para marcar.
- As ferramentas 100% essenciais vêm marcadas e não dá para desmarcar. Decisão da sessão, para confirmar: são o joBot e o Python que ele usa. O navegador para sites com login é opcional: vem marcado, mas dá para desmarcar.
- O que a pessoa não marcar aparece depois no painel, para baixar quando quiser. O painel também deixa refazer a escolha.
- A lista mostra só o que o joBot já usa naquela versão. ~~O Claude Code e o Codex entram junto com a IA (fase 4).~~ (2026-11-17, para confirmar: ver "Fase 4" abaixo)
- A tela do instalador tem de ser muito bonita, para dar confiança a quem instala. Pode usar uma linguagem diferente do resto do joBot, se for mais adequada para essa tela. A tecnologia e a assinatura de código (custos) ainda não foram escolhidas e ficam para decidir com o dono (D138).

### Tela Ferramentas

- Fica em Configurações. Cada ferramenta mostra o estado, o tamanho e um botão "Baixar".
- O navegador pode ser removido pela tela. O Claude Code e o Codex o joBot instala, pelos instaladores oficiais deles, mas nunca remove.
- O botão "Baixar o navegador" (T240) vira o primeiro item da tela Ferramentas. O cartão dos sites com login passa a apontar para lá.

### Limites que ficam

- O joBot nunca vê senha nem token das ferramentas que instala. O login do Claude Code e do Codex é feito pela própria ferramenta ([0010](0010-claude-code-da-pessoa.md)).
- O painel continua sem carregar recurso externo e escutando só em `127.0.0.1` ([0014](0014-seguranca-e-privacidade.md)). Quem baixa é o joBot, a pedido da pessoa; o painel só mostra o botão.

## Fase 4 (2026-11-17, para confirmar)

- A tela Ferramentas fica sempre visível; o navegador continua aparecendo só com um site com login (D185.20, para confirmar).
- O Modelo local (o `llama-server` e o modelo Qwen) entra na lista do instalador, desmarcado, e na tela Ferramentas, com o tamanho à vista. Ele pode ser removido pela tela, como o navegador (D185.17 a D185.19, para confirmar).
- O Claude Code e o Codex esperam o dono e não entram na lista da fase 4 (D185.5, D185.6 e D185.17, para confirmar).

## Consequências

- A [0009](0009-ia-backends-e-modelos.md) muda: o botão "Baixar" do Claude Code e do Codex passa a instalar pelo instalador oficial, e o joBot nunca remove essas ferramentas.
- A [0017](0017-fases.md) muda: a fase 3 vira o Instalador; as fases seguintes andam um número.
- Cada botão novo precisa de texto nos catálogos `pt` e `en` e de teste.
- Antes de construir, o dono confirma o que a D138 deixa em aberto. Se não confirmar, vale a opção marcada como recomendada.
- Desfazer: tirar a tela Ferramentas e os botões; os comandos de terminal continuam.

## Ver também

- [0003. Stack e instalação nativa](0003-stack-e-instalacao-nativa.md)
- [0005. Sites que exigem login](0005-sites-com-login.md)
- [0009. Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md)
- [0010. Usar o Claude Code que a pessoa já tem](0010-claude-code-da-pessoa.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0017. Fases do projeto](0017-fases.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D185 (fase 4)](../../duvidas.md)
