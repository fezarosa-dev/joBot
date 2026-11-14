🌐 **Português** · [English](Technologies)

# 🧰 Tecnologias

**As ferramentas do joBot, para que serve cada uma e por que foram escolhidas.**

---

## 🧱 A base

| Tecnologia | Para quê | Por quê |
|---|---|---|
| 🐍 **Python** (3.14 ou mais nova) | A linguagem do joBot inteiro. | Escolhida na [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md). |
| 📦 **uv** | Instalar e rodar o joBot e as bibliotecas dele. | A instalação é nativa e planejada para um comando, sem Docker. |
| ⚡ **FastAPI** (0.162.7) + **Uvicorn** (0.54.0) | O servidor do painel. | O painel abre no seu navegador e só aceita conexões do próprio computador (127.0.0.1). |
| 🧩 **Jinja2** (3.1.6) | Montar as páginas do painel. | As páginas saem prontas do servidor. |
| 🔁 **HTMX** | Atualizar partes da página sem recarregar tudo. | Interface ágil com pouco JavaScript. O arquivo fica dentro do app. |
| 🗄️ **SQLite** | O banco de dados. | Um arquivo só, que fica no seu computador. Nenhum servidor de banco para instalar. |
| 🌐 **httpx** (0.28.1) | Pedir as páginas e APIs das fontes de vagas. | É o único cliente HTTP do joBot, onde mora a coleta educada (identificação e intervalo entre pedidos). |
| 🔍 **selectolax** (1.0.2) | Ler o HTML das páginas de vagas. | Separar os dados da vaga do resto da página. |
| 🎭 **Playwright** (1.65.1) | Controlar um navegador. | Abre um Chrome visível para você fazer login e resolver CAPTCHA (fase 2). Também roda os testes de tela. |

## ✅ Qualidade

| Tecnologia | Para quê | Por quê |
|---|---|---|
| 🧪 **pytest** (9.2.0) | Rodar os testes. | TDD em todo código: escrever o teste, ver falhar, implementar, ver passar. |
| 🧹 **ruff** (0.17.5) | Estilo e erros comuns. | Um estilo só em todo o projeto. |
| 🔎 **mypy** strict (2.4.1) | Conferir os tipos. | No modo estrito, erros de tipo aparecem antes de rodar. |
| 🤖 **GitHub Actions** | Tarefas automáticas no GitHub. | Roda os testes em todo PR (pedido de integração), inclusive de fork, de graça em repositório público. Também copia esta wiki e vai gerar a versão GitHub Pages (fase 7). |

> [!NOTE]
> As versões entre parênteses são as que o [`pyproject.toml`](https://github.com/fezarosa-dev/joBot/blob/main/pyproject.toml) fixa hoje.
> Dependência nova só entra com justificativa e com licença compatível com a MIT (evitando GPL e AGPL).

## 🧠 Inteligência artificial (opcional)

A IA é opcional. Sem ela, o joBot funciona com regras e palavras-chave ([ADR 0009](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md)).

| Opção | Custo | Onde roda |
|---|---|---|
| **Sessão do Claude Code** que você já tem | Usa a sua assinatura do Claude | Na Anthropic |
| **Chave da API da Anthropic** | Pago por uso | Na Anthropic |
| **Modelo local** (Qwen, via llama-server do llama.cpp) | Grátis | No seu computador, sem internet depois de baixar |
| **Palavras-chave** (sem IA) | Grátis | No seu computador |
| **IA manual** (copiar e colar) | Grátis no joBot | Na IA de chat que você escolher |

- Com o Claude, o app usa só Haiku 5.5 e Sonnet 5.5. **O Opus nunca é usado**, para poupar custo e o seu limite de uso.
- O joBot **não tem login do Claude**. Ele usa o Claude Code que já está no seu computador, no modo sem tela, sem ferramentas e sem tocar na sua credencial ([ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md)).
- O modelo local roda pelo `llama-server`, em versão fixa e conferida por checksum (impressão digital do arquivo). Sem Ollama e sem PyTorch.
- A transcrição de áudio usa o faster-whisper, no seu computador, e o áudio é apagado logo depois.

<sub>Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.</sub>

## 🐳 Por que sem Docker

A instalação é nativa ([ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md)):

- O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
- Um Chrome visível para login manual e CAPTCHA fica difícil dentro de um container.
- Microfone, início com o sistema e atalho são coisas do sistema operacional.
- O login do Claude Code teria de ser feito de novo dentro do container (no macOS ele fica no Keychain, que o container não enxerga).

## 💻 Onde roda

- **Sistemas:** Linux, Windows e macOS. O desenvolvimento acontece no Linux; os instaladores de Windows e macOS chegam na fase 8.
- **Memória:** 8 GB de RAM (16 GB deixam tudo mais folgado).
- **Placa de vídeo:** não precisa.
