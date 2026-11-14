# 0018. Manutenção pela comunidade e CI aberto a todo PR

- **Status:** aceita
- **Data:** 2026-11-14

## Contexto

O dono quer, com o joBot pronto, divulgar bastante o projeto para muita gente usar, e que quem gostar ajude a manter. Quando um site de vagas mudar o formato e um coletor (o código que lê as vagas de uma fonte) quebrar, alguém da comunidade percebe e abre um PR (pedido de integração).

O dono mantém o projeto sozinho. O maior custo de longo prazo é manter os coletores, porque os sites mudam sem aviso. Para o dono, essa é a beleza do código aberto.

## Decisão

- O projeto é desenhado para ser mantido pela comunidade: cada fonte tem um arquivo de coletor no molde comum (T06), com a sua pasta de exemplos capturados do site e testes próprios (T17). Assim, o conserto de uma fonte normalmente fica nesses dois lugares.
- Guia bilíngue "Como consertar uma fonte que quebrou", em português e em inglês, citado no guia de contribuição. Ele é escrito depois que existirem o script de captura (T17) e o primeiro coletor (T27), para usar comandos e exemplo reais.
- A tela de fontes (T50) ganha um link "reportar problema". Ele abre um modelo novo de issue (relato de problema no GitHub), "fonte quebrou", em português e em inglês, com só dois campos já preenchidos: a chave da fonte e o motivo. O motivo é um código fechado (bloqueada, formato mudou, fora do ar, no limite), nunca o texto de uma exceção. A pessoa vê e pode editar o formulário antes de enviar. Em fonte por empresa, a chave leva o identificador da empresa, que mostra o que a pessoa acompanha; por isso a pessoa confere antes de enviar. Nunca vai dado pessoal, busca, cidade ou conteúdo de vaga. O modelo "Fonte de vagas" que existe hoje serve para sugerir fonte nova, não para relatar quebra.
- Isso gera trabalho novo que o plano ainda precisa cobrir, cada item com teste ou conferência: o link da T50 com teste de que a URL carrega só chave e código de motivo; o modelo de issue "fonte quebrou"; o guia de conserto, que depende da T17 e da T27.
- CI (testes automáticos no GitHub) roda em todo PR, inclusive de fork (cópia do repositório feita por outra pessoa) e para a `dev`. O repositório é público, e o GitHub Actions em runner padrão não cobra minutos de repositório público (mesma fonte da [0002](0002-duas-versoes-um-nucleo.md)).
  - O gatilho é `pull_request`, nunca `pull_request_target` (que roda com mais permissões e é perigoso com código de fora).
  - O token é só de leitura e nenhum segredo entra no CI.
  - A aprovação do GitHub para o primeiro PR de quem nunca contribuiu deve ficar ligada (Settings > Actions > General > Fork pull request workflows). Essa configuração não está no repositório: o dono confere na tela do GitHub antes de divulgar. É a principal trava contra abuso de minutos, e o custo é o primeiro PR de cada pessoa esperar o ok do dono.
- Planejado para a fase 8, com detalhes a decidir lá: um vigia semanal no GitHub Actions que testa cada fonte de verdade e abre issue quando uma quebra, e um jeito fácil de atualizar a instalação, para o conserto chegar em quem já usa.
- PR de fora: o dono escolhe quais PRs serão revisados, por quem e o que conferir em cada um. Não há revisão automática por padrão.

## Consequências

- A [0016](0016-licenca-clean-room-e-processo.md) deixa de limitar os testes do GitHub ao PR para a `main`.
- Cada fonte nova ou consertada precisa trazer exemplo capturado e teste. PR sem isso não entra.
- O guia de contribuição (português e inglês) será atualizado quando o guia de conserto existir. Até lá, PR de código segue aceito só depois da fase 8, como está.

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0017. Fases do projeto](0017-fases.md)
