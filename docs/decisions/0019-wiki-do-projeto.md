# 0019. Wiki do projeto e formulário de dúvida

- **Status:** aceita
- **Data:** 2026-11-14

## Contexto

O README cresceu e ficou difícil de percorrer. Quem não achava resposta nas perguntas frequentes caía no formulário de sugestão, que não é o lugar de uma dúvida.

O projeto quer ser mantido pela comunidade (ver a [0018](0018-manutencao-pela-comunidade.md)). Para isso, a ajuda precisa ser fácil de achar e a documentação precisa poder ser corrigida por qualquer pessoa, por PR (pedido de integração).

## Decisão

- Um formulário de issue (relato no GitHub) de dúvida, com o rótulo `question`. Ele pede para ler as perguntas frequentes antes e para não colocar dado pessoal.
- A wiki do GitHub fica ligada, com as páginas Início, Perguntas frequentes e Tirar dúvida, em português e em inglês.
- As perguntas frequentes têm fonte única na wiki. O README só aponta para lá.
- O texto da wiki mora na pasta `wiki/` do repositório e é editado por PR, como qualquer arquivo.
- Um workflow (tarefa automática do GitHub Actions) copia a pasta para a wiki a cada push na `main`. Ele usa shell próprio, só o checkout oficial como action, e o token do próprio GitHub com apenas `contents: write`. Nunca roda em `pull_request`, para código de fora não ter acesso a esse token.
- A edição direta na wiki do GitHub fica só com quem mantém o projeto (padrão do GitHub). A edição direta é sobrescrita na próxima cópia, então toda mudança vai pela pasta `wiki/`.
- A wiki é um repositório à parte (`joBot.wiki.git`). Ela convive com o GitHub Pages da fase 7, que sai de um ramo ou do GitHub Actions.
- Páginas futuras: "Como consertar uma fonte" (o guia da [0018](0018-manutencao-pela-comunidade.md)) e "Instalação".

## Consequências

- Página nova precisa das duas línguas. Um teste confere os pares e os links entre páginas.
- O formulário de dúvida e a página de suporte apontam para a wiki.
- Mudança na wiki só aparece depois que chega na `main`.
- Antes da primeira cópia, a wiki precisa estar ligada nas configurações do repositório e ter uma primeira página criada pela web. Senão o robô falha, pois o repositório da wiki só passa a existir depois disso.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
