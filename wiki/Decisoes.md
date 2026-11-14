🌐 **Português** · [English](Decisions)

# 📚 Decisões

**Cada escolha importante do joBot, com o porquê guardado por escrito.**

---

Uma ADR (registro de decisão de arquitetura) é um texto curto que guarda uma decisão: o contexto em que ela foi tomada, o que ficou decidido e as consequências. Assim, quem chegar depois entende o porquê das escolhas.

> [!TIP]
> Quer o detalhe? Cada linha tem um link para a ADR completa. O [índice das ADRs](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/README.md) explica como registrar uma decisão nova.

## 🗂️ Todas as decisões

| Nº | Decisão | Em uma linha | |
|---|---|---|---|
| 0001 | **Escopo: o que o joBot é e o que não é** | Busca, filtra, ranqueia e organiza vagas num painel local; nunca envia candidatura sozinho; toda função pode ser desligada. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0001-escopo-do-jobot.md) |
| 0002 | **Duas versões, um núcleo** | Um núcleo comum, uma versão para baixar (o foco) e uma versão GitHub Pages (fase 7) só com fontes públicas, sem logins nem segredos. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0002-duas-versoes-um-nucleo.md) |
| 0003 | **Tecnologias e instalação nativa (sem Docker)** | Python 3.14, FastAPI + Jinja2 + HTMX, SQLite, Playwright e uv; instalação nativa, sem Docker. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md) |
| 0004 | **Fontes públicas de vagas e coleta educada** | Cada fonte com chave liga/desliga; coleta educada, sem nunca contornar login, CAPTCHA ou bloqueio anti-robô. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0004-fontes-publicas.md) |
| 0005 | **Sites que exigem login** | Chrome visível, você faz o login com as próprias mãos, o joBot só lê, visita duas vezes por dia e nunca contorna CAPTCHA. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0005-sites-com-login.md) |
| 0006 | **Agenda das buscas e segundo plano** | Fontes públicas a cada 3 horas, sites com login duas vezes por dia; segundo plano é escolha sua; busca perdida roda quando o computador liga. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0006-agenda-e-segundo-plano.md) |
| 0007 | **Tratamento das vagas: duplicadas, ciclo de vida, salário e rótulos** | Duplicadas pelo endereço, vaga fecha quando some e nunca é apagada, salário convertido pela PTAX, rótulos medidos num gabarito de 329 vagas. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0007-tratamento-dos-dados.md) |
| 0008 | **Painel e visual** | Abas, filtros na URL, status de cada vaga, visual no estilo Apple, português e inglês; o painel só escuta em 127.0.0.1. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0008-painel-e-visual.md) |
| 0009 | **Inteligência artificial: opções, modelos e pacote offline** | IA opcional, com uma opção por tarefa; com o Claude, só Haiku 5.5 e Sonnet 5.5, nunca Opus; pacote offline com Qwen; a IA nunca inventa dado. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md) |
| 0010 | **Usar o Claude Code que a pessoa já tem (sem login dentro do joBot)** | Sem login do Claude no joBot; ele chama o Claude Code no modo sem tela, sem ferramentas, e nunca toca na credencial. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md) |
| 0011 | **Perfil, currículo, primeira execução e áudio** | Currículo em PDF lido pela IA e revisado por você, questionário de cerca de 25 perguntas, áudio transcrito no computador e apagado. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0011-perfil-e-primeira-execucao.md) |
| 0012 | **Extensão do navegador** | Sugere respostas nos formulários e você confirma; nunca toca em campos de senha ou cartão; pareada com o app. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0012-extensao-do-navegador.md) |
| 0013 | **Gmail e avisos** | Gmail opcional e só leitura, com projeto Google da própria pessoa; resumo diário opcional no Telegram, desligado por padrão. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0013-gmail-e-avisos.md) |
| 0014 | **Segurança e privacidade** | Segredos no cofre do sistema, dados pessoais numa pasta só sua, sem telemetria, painel fechado para fora do computador. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0014-seguranca-e-privacidade.md) |
| 0015 | **Treino de modelos (fase 6)** | Modelos ajustados só entram se ganharem no gabarito; modelos públicos nunca treinam com dado pessoal. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0015-treino.md) |
| 0016 | **Licença, sala limpa e processo de trabalho** | Licença MIT; fatos públicos sim, código e dados de teste de terceiros nunca; TDD, ramos main e dev, documentação em português e inglês. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0016-licenca-clean-room-e-processo.md) |
| 0017 | **Fases do projeto** | Oito fases, da base (fase 1) à publicação (fase 8). | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0017-fases.md) |
| 0018 | **Manutenção pela comunidade e CI aberto a todo PR** | Cada fonte com coletor, exemplos e testes próprios, para qualquer pessoa consertar; testes automáticos em todo PR, inclusive de fork. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0018-manutencao-pela-comunidade.md) |
| 0019 | **Wiki do projeto e formulário de dúvida** | Wiki em português e inglês, editada por PR na pasta wiki/; perguntas frequentes só aqui; formulário de dúvida. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0019-wiki-do-projeto.md) |
| 0020 | **Apoio financeiro: só doação** | O projeto aceita só doação; tudo continua grátis, sem anúncio, sem afiliado e sem rastreio. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0020-apoio-financeiro.md) |
| 0021 | **Sem Dependabot: atualização de dependência à mão** | Sem Dependabot de versão nem de segurança; os alertas ficam e a atualização é manual no fim de cada fase. | [ler](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0021-sem-dependabot.md) |

## ❔ Dúvidas

As decisões que dependem do dono do projeto, abertas e resolvidas, ficam no [duvidas.md](https://github.com/fezarosa-dev/joBot/blob/main/duvidas.md).
