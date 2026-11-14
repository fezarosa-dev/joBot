# 0017. Fases do projeto

- **Status:** aceita
- **Data:** 2026-11-13

## Contexto

O projeto é grande. Ir por fases deixa cada entrega testada antes da próxima. Hoje a fase 1 está em andamento e nenhuma fase está pronta.

## Decisão

- Fase 1, Base: núcleo comum, fontes públicas, banco, painel e agenda, mais o vigia semanal das fontes e o `jobot atualizar` (ver [0018](0018-manutencao-pela-comunidade.md)). Os detalhes ficam para o desenho da fase 1. Status: em andamento.
- Fase 2, Navegador com login: Chrome visível, mapeamento dos sites e tratamento de CAPTCHA. Status: planejada.
- Fase 3, IA local: pacote offline (llama-server + Qwen). Status: planejada.
- Fase 4, Extensão do navegador. Status: planejada.
- Fase 5, Áudio e Gmail. Status: planejada.
- Fase 6, Treino. Status: planejada.
- Fase 7, Versão GitHub Pages. Status: planejada.
- Fase 8, Publicação: instaladores, README com selos, revisão de segurança. Status: planejada.

## Consequências

- Cada fase só começa depois que a anterior passa nos testes.

## Ver também

- [0001. Escopo: o que o joBot é e o que não é](0001-escopo-do-jobot.md)
- [0002. Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md)
- [0016. Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
