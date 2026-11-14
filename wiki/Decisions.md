🌐 [Português](Decisoes) · **English**

# 📚 Decisions

**Every important joBot choice, with the reason kept in writing.**

---

An ADR (architecture decision record) is a short text that keeps one decision: the context in which it was made, what was decided and the consequences. That way, whoever comes later understands the reasons behind the choices.

> [!IMPORTANT]
> The ADRs are written in **Portuguese only**. The titles and summaries below are translated; the linked documents are in Portuguese.

> [!TIP]
> Want the details? Each row links to the full ADR. The [ADR index](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/README.md) explains how to record a new decision.

## 🗂️ All decisions

| No. | Decision | In one line | |
|---|---|---|---|
| 0001 | **Scope: what joBot is and what it is not** | Searches, filters, ranks and organizes jobs in a local dashboard; never sends an application on its own; every feature can be turned off. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0001-escopo-do-jobot.md) |
| 0002 | **Two versions, one core** | One common core, a download version (the focus) and a GitHub Pages version (phase 7) with public sources only, no logins or secrets. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0002-duas-versoes-um-nucleo.md) |
| 0003 | **Technologies and native installation (no Docker)** | Python 3.14, FastAPI + Jinja2 + HTMX, SQLite, Playwright and uv; native installation, no Docker. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md) |
| 0004 | **Public job sources and polite collection** | Each source has an on/off switch; polite collection, never bypassing login, CAPTCHA or anti-robot blocks. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0004-fontes-publicas.md) |
| 0005 | **Sites that require login** | Visible Chrome, you log in with your own hands, joBot only reads, visits twice a day and never bypasses CAPTCHA. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0005-sites-com-login.md) |
| 0006 | **Search schedule and background** | Public sources every 3 hours, sites with login twice a day; background is your choice; a missed search runs when the computer turns on. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0006-agenda-e-segundo-plano.md) |
| 0007 | **Job processing: duplicates, life cycle, salary and labels** | Duplicates by address, a job closes when it disappears and is never deleted, salary converted by the PTAX rate, labels measured on a 329-job reference set. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0007-tratamento-dos-dados.md) |
| 0008 | **Dashboard and look** | Tabs, filters in the URL, status for each job, Apple-style look, Portuguese and English; the dashboard only listens on 127.0.0.1. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0008-painel-e-visual.md) |
| 0009 | **Artificial intelligence: options, models and offline package** | Optional AI, with one option per task; with Claude, only Haiku 5.5 and Sonnet 5.5, never Opus; offline package with Qwen; the AI never invents data. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md) |
| 0010 | **Use the Claude Code the person already has (no login inside joBot)** | No Claude login in joBot; it calls Claude Code in headless mode, with no tools, and never touches the credentials. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md) |
| 0011 | **Profile, résumé, first run and audio** | Résumé PDF read by the AI and reviewed by you, a questionnaire of about 25 questions, audio transcribed on the computer and deleted. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0011-perfil-e-primeira-execucao.md) |
| 0012 | **Browser extension** | Suggests answers in forms and you confirm; never touches password or card fields; paired with the app. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0012-extensao-do-navegador.md) |
| 0013 | **Gmail and notifications** | Optional, read-only Gmail, with the person's own Google project; optional daily summary on Telegram, off by default. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0013-gmail-e-avisos.md) |
| 0014 | **Security and privacy** | Secrets in the system vault, personal data in a folder only you can access, no telemetry, dashboard closed to the outside. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0014-seguranca-e-privacidade.md) |
| 0015 | **Model training (phase 6)** | Fine-tuned models only come in if they win on the reference set; public models never train on personal data. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0015-treino.md) |
| 0016 | **License, clean room and work process** | MIT license; public facts yes, third-party code and test data never; TDD, main and dev branches, docs in Portuguese and English. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0016-licenca-clean-room-e-processo.md) |
| 0017 | **Project phases** | Eight phases, from the base (phase 1) to the release (phase 8). | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0017-fases.md) |
| 0018 | **Community maintenance and CI open to every PR** | Each source has its own collector, examples and tests, so anyone can fix it; automatic tests on every PR, including from forks. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0018-manutencao-pela-comunidade.md) |
| 0019 | **Project wiki and question form** | Wiki in Portuguese and English, edited by PR in the wiki/ folder; FAQ only here; question form. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0019-wiki-do-projeto.md) |
| 0020 | **Financial support: donations only** | The project only accepts donations; everything stays free, with no ads, no affiliate links and no tracking. | [read](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0020-apoio-financeiro.md) |

## ❔ Open questions

Decisions that depend on the project owner, open and resolved, are in [duvidas.md](https://github.com/fezarosa-dev/joBot/blob/main/duvidas.md) (Portuguese only).
