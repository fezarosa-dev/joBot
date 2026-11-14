# 0018. Manutenção pela comunidade e CI aberto a todo PR

- **Status:** aceita
- **Data:** 2026-11-14
- **Atualizada:** 2026-11-14 (vigia semanal e `jobot atualizar` passam para a fase 1, a pedido do dono)

## Contexto

O dono quer, com o joBot pronto, divulgar bastante o projeto para muita gente usar, e que quem gostar ajude a manter. Quando um site de vagas mudar o formato e um coletor (o código que lê as vagas de uma fonte) quebrar, alguém da comunidade percebe e abre um PR (pedido de integração).

O dono mantém o projeto sozinho. O maior custo de longo prazo é manter os coletores, porque os sites mudam sem aviso. Para o dono, essa é a beleza do código aberto.

Em 2026-11-14 o dono pediu que o vigia semanal e a atualização fácil da instalação, antes planejados para a fase 8, entrem já na fase 1, junto com tudo o que deixar o projeto bom para a comunidade, para quem usa e para ele.

## Decisão

- O projeto é desenhado para ser mantido pela comunidade: cada fonte tem um arquivo de coletor no molde comum (T06), com a sua pasta de exemplos capturados do site e testes próprios (T17). Assim, o conserto de uma fonte normalmente fica nesses dois lugares.
- Guia bilíngue "Como consertar uma fonte que quebrou", em português e em inglês, citado no guia de contribuição (T83). Ele sai depois que existirem o script de captura (T17) e o primeiro coletor (T27) (decisão 20), para usar comandos e exemplo reais. Por proposta do redator, a confirmar (D34), também espera a tela de fontes com o link (T50) e o vigia (T84), para não citar recurso que ainda não existe.
- A tela de fontes (T50) ganha um link "reportar problema". Ele abre um modelo novo de issue (relato de problema no GitHub), "fonte quebrou" (`fonte-quebrou.yml`, em português e em inglês, também da T50), com só dois campos já preenchidos: a chave da fonte e o motivo. A pessoa vê e pode editar o formulário antes de enviar. O modelo "Fonte de vagas" que existe hoje serve para sugerir fonte nova, não para relatar quebra.
  - O motivo é uma das chaves `saude.*` que já existem no catálogo (`src/jobot/painel/i18n/*/comum.json`), nunca o texto de uma exceção. Ficam de fora `saude.excecao` e os contadores (`saude.parcial_n` e `saude.sem_detalhe_n`, que levam `{n}`). Hoje o conjunto é: `saude.formato_mudou`, `saude.zero_inesperado`, `saude.empresa_nao_encontrada`, `saude.bloqueio`, `saude.tempo_esgotado`, `saude.erro_de_rede`, `saude.resposta_grande` e `saude.listagem_incompleta` (esta entra com o ajuste F3, decisão 16). Chave nova de motivo passa pela sessão, que diz se ela gera o link.
  - Os estados de limite de ritmo (`saude.cota`, `saude.intervalo`, `saude.parou_429`, `saude.limite_atingido` e `saude.orcamento`) não são quebra de fonte e não geram o link.
  - Em fonte por empresa, a chave leva o identificador da empresa, que mostra o que a pessoa acompanha. Ele vai na URL do link: ao clicar, o GitHub já recebe a chave, antes de a pessoa ver o formulário (fica nos registros do GitHub, não no joBot). Por isso a tela mostra, ao lado do link, o que vai (a fonte e o motivo), e a pessoa pode editar o formulário antes de enviar a issue (escolha do redator, D31). Nunca vai dado pessoal, busca, cidade ou conteúdo de vaga.
  - É um link comum, aberto só pelo clique da pessoa: o joBot não envia nada por conta própria, de acordo com a regra de "sem telemetria" da [0014](0014-seguranca-e-privacidade.md).
- Isso gera trabalho novo, que o plano da fase 1 cobre, cada item com teste ou conferência: o link e o modelo de issue na T50 (com teste de que a URL carrega só a chave e um motivo do conjunto fechado acima); o guia de conserto (T83); o vigia semanal (T84); e o `jobot atualizar` (T85).
- CI (testes automáticos no GitHub) roda em todo PR, inclusive de fork (cópia do repositório feita por outra pessoa) e para a `dev`. O repositório é público, e o GitHub Actions em runner padrão não cobra minutos de repositório público (mesma fonte da [0002](0002-duas-versoes-um-nucleo.md)).
  - O gatilho é `pull_request`, nunca `pull_request_target` (que roda com mais permissões e é perigoso com código de fora).
  - O token é só de leitura e nenhum segredo entra no CI.
  - A aprovação do GitHub para o primeiro PR de quem nunca contribuiu deve ficar ligada (Settings > Actions > General > Fork pull request workflows). Essa configuração não está no repositório: o dono confere na tela do GitHub antes de divulgar o projeto. É a principal trava contra abuso de minutos, e o custo é o primeiro PR de cada pessoa esperar o ok do dono.
- Vigia semanal das fontes (T84, fase 1): um fluxo do GitHub Actions que roda toda semana, testa de verdade cada fonte pública e abre uma issue quando uma delas quebra. Segue o ritmo e os limites da [0004](0004-fontes-publicas.md) e deixa de fora as fontes de termos restritivos que a 0004 nomeia (Eureca, Abler e Gupy). Roda só por agenda e à mão, nunca em PR, sem segredo e com permissão de escrever só em issues. Como roda de IP de datacenter do GitHub, bloqueio de IP não conta como quebra do coletor. Por proposta do redator, a confirmar (D31), a exceção que sai de `escopos` ou de `coletar` conta como quebra; erro do `detalhar` vai só para o resumo, salvo em fonte de escopo único quando todos os detalhes tentados falham (D31), e a issue leva só o nome do tipo, nunca o texto da exceção; o vigia só mexe nas issues que ele mesmo abriu (autor `github-actions[bot]`), nunca nas de pessoas, mesmo que tragam a marca dele. É script de CI, fora do joBot instalado, e é o único código do projeto que leva token (o `GITHUB_TOKEN`, só para `api.github.com`). O `schedule` só vale no ramo padrão, então o vigia só começa a rodar depois do merge na `main`, e o GitHub desliga o `schedule` de repositório público sem atividade por 60 dias (D31).
- `jobot atualizar` (T85, fase 1): um comando e um aviso no painel que levam o conserto a quem já usa o joBot. Para o servidor e o segundo plano antes, religa depois, recusa quando há mudança local e mostra as novidades do CHANGELOG. Atende a instalação por clone do repositório e a por `uv tool`; qualquer outra recusa e explica, porque o canal de instalação para o público fica para a fase 8.
  - O aviso de versão no painel faz uma checagem por dia ao GitHub (`api.github.com`). Por causa da regra da [0014](0014-seguranca-e-privacidade.md) de que os dados só saem do computador para os serviços que a pessoa ligar, ele nasce **desligado** e a pessoa liga no interruptor de Privacidade. O pedido leva só o user agent fixo, que traz a versão do joBot, sem cookie, busca nem identificador; o GitHub também vê o IP, como em qualquer pedido.
- PR de fora: o dono escolhe quais PRs serão revisados, por quem e o que conferir em cada um. Não há revisão automática por padrão.

## Consequências

- A [0016](0016-licenca-clean-room-e-processo.md) deixa de limitar os testes do GitHub ao PR para a `main`.
- Cada fonte nova ou consertada precisa trazer exemplo capturado e teste. PR sem isso não entra.
- O guia de contribuição (português e inglês) será atualizado quando o guia de conserto existir. Até lá, PR de código segue aceito só depois da fase 8, como está.
- A fase 1 cresce com a T83, a T84 e a T85, e a fase 8 deixa de ter o vigia e a atualização (ver [0017](0017-fases.md)).
- O dono ainda precisa confirmar duas coisas, registradas no `duvidas.md`: a aprovação do primeiro PR de quem nunca contribuiu e o guia de conserto sair só depois da T17, da T27, da T50 e da T84 (D34). A D31 guarda as escolhas do redator (canal de instalação do `jobot atualizar`, aviso de versão desligado por padrão, regras do vigia) e a pendência de pôr o GitHub, para o aviso de versão, na lista de serviços que a pessoa liga da [0014](0014-seguranca-e-privacidade.md).

## Ver também

- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0004. Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0017. Fases do projeto](0017-fases.md)
