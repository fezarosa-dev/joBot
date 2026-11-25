# 0017. Fases do projeto

- **Status:** aceita
- **Data:** 2026-11-13
- **Atualizada:** 2026-11-16 (versões 0.1.1, 0.2.0 e 0.2.1 entre a fase 1 e a fase 2; fase 3 vira o Instalador, as seguintes andam um número, e a versão 0.3.0 traz o Panorama e a fila, D138; fase 3 com o app de desktop, D142, e o ajuste do Laya antes da fase 4, D141; fase 2 concluída e 0.3.0); 2026-11-17 (fase 3 começa a ser construída, D171 e [0025](0025-app-de-desktop-e-instalador.md); fase 3 concluída na 0.4.0; fase 4 começa a ser construída, rumo à 0.5.0, e o ajuste do Laya antes da fase 4 fica adiado, para confirmar, D185 e [0026](0026-ia-da-fase-4.md)); 2026-11-24 (o dono autoriza o treino do Laya antes da fase 4, e a 0.5.0 sai sem o Laya treinado, D219; a 0.5.0 sai com a primeira parte da fase 4, rumo à 0.6.0, T421; o Laya é o modelo local padrão da 0.6.0, D219 e D237); 2026-11-24 (a pedido do dono, ~~para confirmar,~~ a fase 8, versão GitHub Pages, é construída antes da fase 5, extensão do navegador; os números não mudam; a fase 8 entra em desenho, D238 e D239); 2026-11-24 (o dono decide a ordem nova, D238)

## Contexto

O projeto é grande. Ir por fases deixa cada entrega testada antes da próxima. Hoje as fases 1, 2 e 3 estão concluídas, as versões 0.1.0, 0.1.1, 0.2.0, 0.2.1, 0.3.0, 0.4.0, 0.4.1 e 0.5.0 já saíram (a 0.2.0 traz filtros novos e deixa o 2Captcha preparado para a fase 2; a 0.2.1 deixa a lista de vagas mais rápida e faz o aviso «Salvo.» sumir sozinho; a 0.3.0 traz o navegador com login, o LinkedIn, o visual novo do painel, a aba Contas, o Panorama e a fila de candidaturas; a 0.4.0 traz a janela própria e o instalador para Windows, Linux e Mac; a 0.4.1 corrige o Linux; a 0.5.0 traz a primeira parte da fase 4, a IA opcional); a fase 4 está sendo construída, a fase 8 está em desenho e as outras fases estão planejadas. Em 2026-11-15 o dono decidiu a ordem LinkedIn (fase 2), Panorama e fila, versão 0.3.0, instalador, IA local (D138).

## Decisão

- Fase 1, Base: núcleo comum, fontes públicas, banco, painel e agenda, mais o vigia semanal das fontes e o `jobot atualizar` (ver [0018](0018-manutencao-pela-comunidade.md)). Os detalhes ficam para o desenho da fase 1. Status: concluída.
- Entre a fase 1 e a fase 2 saem três versões pequenas: a 0.1.1 (nenhum erro trava o programa e todo erro aparece com o que a pessoa pode fazer), a 0.2.0 (filtros novos na tela de vagas, país e moeda) e a 0.2.1 (a lista de vagas abre mais rápido e o aviso "Salvo." some sozinho). A ordem das fases não muda.
- Fase 2, Navegador com login: Chrome visível, mapeamento dos sites e tratamento de CAPTCHA. Status: concluída na 0.3.0 (navegador com login e o primeiro site).
- Depois da fase 2 sai a versão 0.3.0, num lote separado do login: a tela "Panorama" (visão geral das vagas e da busca) e a fila de candidaturas completa (link de candidatura por e-mail, a pergunta "Você se candidatou?" quando a pessoa volta ao painel e as datas de cada passo). Só depois dela começa a fase 3.
- Fase 3, Instalador: só 64 bits; Windows e Linux primeiro, Mac depois (testado só no GitHub Actions). A tela do instalador mostra uma lista de ferramentas para marcar: as essenciais vêm marcadas e não dá para desmarcar. As outras, se ficarem sem marca, aparecem depois no painel para baixar quando a pessoa quiser (ver [0023](0023-tudo-pelo-painel.md)). Status: concluída na 0.4.0 (janela própria e instalador; desenho e decisões na D171 e na [0025](0025-app-de-desktop-e-instalador.md)).
- Fase 4, IA local: pacote offline (llama-server + Qwen). Status: sendo construída; a 0.5.0 trouxe a primeira parte, rumo à 0.6.0; a fase sai em duas versões, a 0.5.0 e a 0.6.0 (para confirmar: desenho e escolhas na D185 e na [0026](0026-ia-da-fase-4.md)).
- Fase 5, Extensão do navegador. Status: planejada; construída depois da fase 8 (D238, decidida pelo dono).
- Fase 6, Áudio e Gmail. Status: planejada.
- Fase 7, Treino. Status: planejada.
- Fase 8, Versão GitHub Pages. Status: em desenho (`docs/superpowers/specs/2026-11-24-fase-8-design.md`, escolhas na D239, parte delas decidida pelo dono); construída logo depois da fase 4 e antes da fase 5 (D238, decidida pelo dono), em duas versões, a 0.7.0 e a 0.8.0 (D238; versões na D239.20, para discutir).
- Fase 9, Publicação: README com selos e revisão de segurança (os instaladores saíram desta fase e foram para a fase 3). Status: planejada.

## App de desktop na fase 3 e Laya antes da fase 4 (2026-11-15)

- A fase 3 inclui, além do instalador, o app de desktop: uma casca Tauri com ícone e janela própria em volta do mesmo painel, que continua em 127.0.0.1. O mesmo projeto Tauri gera o instalador (D142). O visual de app do Mac vem da D140.
- ~~O ajuste fino do Laya (ADR 0015) acontece antes da fase 4, e o Laya ajustado entra no encaixe junto com o Qwen local (D141).~~ ~~O ajuste do Laya antes da fase 4 está adiado, para confirmar (2026-11-17, D185.8): o treino custa, e o dono decide se autoriza o gasto ou adia; até lá, a fase 4 segue com as habilidades pela IA escolhida ([0026](0026-ia-da-fase-4.md)).~~ O dono autorizou o treino do Laya antes da fase 4 em 2026-11-24 (D219, [0015](0015-treino.md)), no RunPod, só na Community Cloud e pela GPU de menor custo total. A 0.5.0 sai sem o Laya treinado, ~~que entra numa versão seguinte~~ e ele é o modelo local padrão da 0.6.0 (D219, confirmada pelo dono em 2026-11-24, D237). Os outros treinos seguem na fase 7.
- Nenhuma fase muda de número nem de nome.

## Fase 8 antes da fase 5 (2026-11-24, decidida pelo dono)

- A pedido do dono, em 2026-11-24, a versão GitHub Pages (fase 8) é construída logo depois da fase 4, antes da extensão do navegador (fase 5) (D238, decidida pelo dono). A ordem de execução fica: 4, 8, 5, 6, 7, 9.
- Os números e os nomes das fases não mudam. "Cada fase só começa depois que a anterior passa nos testes" vale na ordem nova: a fase 8 começa depois da fase 4 (a 0.6.0).
- Nada da fase 8 depende das fases 5, 6 ou 7. O desenho e as escolhas estão na D239; o plano é `docs/superpowers/plans/2026-11-24-fase-8.md`.

## Consequências

- Cada fase só começa depois que a anterior passa nos testes.

## Ver também

- [0001. Escopo: o que o joBot é e o que não é](0001-escopo-do-jobot.md)
- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [0025. App de desktop e instalador](0025-app-de-desktop-e-instalador.md)
- [0026. IA da fase 4: tarefas, backends e modelo local](0026-ia-da-fase-4.md)
- [duvidas.md: D141 (Laya antes da fase 4), D142 (app de desktop), D171 (fase 3), D185 (fase 4), D219 (treino do Laya), D238 (fase 8 antes da 5) e D239 (fase 8)](../../duvidas.md)
