# Decisões do projeto (ADRs)

Um ADR (registro de decisão de arquitetura) é um texto curto que guarda uma decisão: o contexto em que ela foi tomada, o que ficou decidido e as consequências. Assim, quem chegar depois entende o porquê das escolhas.

Estas decisões vieram de 9 rodadas de perguntas e respostas feitas em 2026-11-13, mais ajustes depois. O projeto está em desenvolvimento e ainda não tem código; nada aqui descreve algo pronto.

| Nº | Decisão | Status |
|---|---|---|
| 0001 | [Escopo: o que o joBot é e o que não é](0001-escopo-do-jobot.md) | aceita |
| 0002 | [Duas versões, um núcleo](0002-duas-versoes-um-nucleo.md) | aceita |
| 0003 | [Tecnologias e instalação nativa (sem Docker)](0003-stack-e-instalacao-nativa.md) | aceita |
| 0004 | [Fontes públicas de vagas e coleta educada](0004-fontes-publicas.md) | aceita |
| 0005 | [Sites que exigem login](0005-sites-com-login.md) | aceita |
| 0006 | [Agenda das buscas e segundo plano](0006-agenda-e-segundo-plano.md) | aceita |
| 0007 | [Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos](0007-tratamento-dos-dados.md) | aceita |
| 0008 | [Painel e visual](0008-painel-e-visual.md) | aceita |
| 0009 | [Inteligência artificial: opções, modelos e pacote offline](0009-ia-backends-e-modelos.md) | aceita |
| 0010 | [Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)](0010-claude-code-da-pessoa.md) | aceita |
| 0011 | [Perfil, currículo, primeira execução e áudio](0011-perfil-e-primeira-execucao.md) | aceita |
| 0012 | [Extensão do navegador](0012-extensao-do-navegador.md) | aceita |
| 0013 | [Gmail e avisos](0013-gmail-e-avisos.md) | aceita |
| 0014 | [Segurança e privacidade](0014-seguranca-e-privacidade.md) | aceita |
| 0015 | [Treino de modelos (fase 6)](0015-treino.md) | aceita |
| 0016 | [Licença, sala limpa e processo de trabalho](0016-licenca-clean-room-e-processo.md) | aceita |
| 0017 | [Fases do projeto](0017-fases.md) | aceita |
| 0018 | [Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md) | aceita |
| 0019 | [Wiki do projeto e formulário de dúvida](0019-wiki-do-projeto.md) | aceita |

## Como registrar uma nova decisão

1. Copie o formato de uma ADR existente.
2. Use o próximo número livre, com quatro dígitos, e um nome de arquivo curto (por exemplo, `0019-assunto.md`).
3. Comece com o status `proposta`. Quando a decisão for confirmada, mude para `aceita`. Se outra decisão a trocar, mude para `substituída por NNNN`, com o número da nova.
4. Acrescente a linha na tabela acima.

Decisões que dependem do dono do projeto, abertas e resolvidas, ficam em [duvidas.md](../../duvidas.md).
