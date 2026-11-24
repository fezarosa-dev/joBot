🌐 **Português** · [English](Technologies)

# 🧰 Tecnologias

**As ferramentas do joBot, para que serve cada uma e por que foram escolhidas.**

---

## 🧱 A base

| Tecnologia | Para quê | Por quê |
|---|---|---|
| 🐍 **Python** (3.14 ou mais nova) | A linguagem do joBot inteiro. | Escolhida na [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md). |
| 📦 **uv** | Instalar e rodar o joBot e as bibliotecas dele. | A instalação é nativa, sem Docker; o instalador da fase 3 já traz o `uv` e tudo o que ele instala. |
| ⚡ **FastAPI** (0.162.7) + **Uvicorn** (0.54.0) | O servidor do painel. | O painel abre no seu navegador e só aceita conexões do próprio computador (127.0.0.1). |
| 🧩 **Jinja2** (3.1.6) | Montar as páginas do painel. | As páginas saem prontas do servidor. |
| 🔁 **HTMX** | Atualizar partes da página sem recarregar tudo. | Interface ágil com pouco JavaScript. O arquivo fica dentro do app. |
| 🗄️ **SQLite** | O banco de dados. | Um arquivo só, que fica no seu computador. Nenhum servidor de banco para instalar. |
| 🌐 **httpx** (0.28.1) | Pedir as páginas e APIs das fontes de vagas. | É o único cliente HTTP do joBot, onde mora a coleta educada (identificação e intervalo entre pedidos). |
| 🔍 **selectolax** (1.0.2) | Ler o HTML das páginas de vagas. | Separar os dados da vaga do resto da página. |
| 🔐 **keyring** (25.7.0) | Guardar a chave do 2Captcha no cofre de senhas do sistema. | A chave não fica num arquivo comum; sem cofre, vai a um arquivo que só você lê (ADR 0014). |
| 🎭 **Playwright** (1.65.1) | Controlar um navegador. | Lê os sites com login, usando a sessão que você abriu (fase 2). Também roda os testes de tela. |
| 📄 **pypdf** (7.1.1) | Ler o texto do currículo em PDF na aba Perfil (0.6.0). | Roda num processo à parte, com prazo e limite de páginas; o PDF e o texto não são guardados. |

## ✅ Qualidade

| Tecnologia | Para quê | Por quê |
|---|---|---|
| 🧪 **pytest** (9.2.0) | Rodar os testes. | TDD em todo código: escrever o teste, ver falhar, implementar, ver passar. |
| 🧹 **ruff** (0.17.5) | Estilo e erros comuns. | Um estilo só em todo o projeto. |
| 🔎 **mypy** strict (2.4.1) | Conferir os tipos. | No modo estrito, erros de tipo aparecem antes de rodar. |
| 🤖 **GitHub Actions** | Tarefas automáticas no GitHub. | Roda os testes em todo PR (pedido de integração), inclusive de fork, de graça em repositório público. Também copia esta wiki e vai gerar a versão GitHub Pages (fase 8). |

> [!NOTE]
> As versões entre parênteses são as que o [`pyproject.toml`](https://github.com/fezarosa-dev/joBot/blob/main/pyproject.toml) fixa hoje.
> Dependência nova só entra com justificativa e com licença compatível com a MIT (evitando GPL e AGPL).

## 🧠 Inteligência artificial (opcional)

A IA é opcional. Sem ela, o joBot funciona com regras e palavras-chave ([ADR 0009](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md)).

| Opção | Custo | Onde roda |
|---|---|---|
| **Modelo local** (o Laya, por padrão, via llama-server do llama.cpp), desde a 0.5.0 | Grátis | No seu computador, sem internet depois de baixar |
| **Chave da API da Anthropic**, desde a 0.5.0 (experimental) | Pago por uso | Na Anthropic |
| **Chave da OpenAI ou do Google Gemini**, desde a 0.5.0 (experimental) | Pago por uso (o Gemini pode ser cobrado por uso, conforme o plano da sua conta no Google AI Studio) | Na OpenAI ou no Google |
| **Endereço compatível com a OpenAI** (Ollama, LM Studio, OpenRouter), desde a 0.5.0 (experimental: o mesmo cliente só rodou contra o `llama-server` do modelo local, no CI) | Depende do serviço | Onde o endereço apontar |
| **Palavras-chave** (sem IA) | Grátis | No seu computador |
| **IA manual** (copiar e colar), desde a 0.6.0, no currículo e na candidatura | Grátis no joBot | Na IA de chat que você escolher |
| **Sessão do Claude Code** que você já tem (espera o dono) | Usa a sua assinatura do Claude | Na Anthropic |

- Com o Claude, o app usa só Haiku 5.5 e Sonnet 5.5. **O Opus nunca é usado**, para poupar custo e o seu limite de uso.
- O joBot **não tem login do Claude**. Ele usa o Claude Code que já está no seu computador, no modo sem tela, sem ferramentas e sem tocar na sua credencial ([ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md)).
- A sessão do Claude Code espera a decisão do dono sobre os termos de uso e ainda não foi construída; na 0.5.0 e na 0.6.0, o Claude entra pela chave da API da Anthropic.
- O modelo local roda pelo `llama-server`, em versão fixa e conferida por checksum (impressão digital do arquivo), só no processador. O joBot o baixa do GitHub (o `llama-server`, das versões do llama.cpp, e o Laya, das versões do joBot) e do Hugging Face (o Qwen3.5, se você trocar), só quando você pede. O joBot não traz Ollama nem PyTorch; quem já usa o Ollama ou o LM Studio pode apontar o endereço compatível para ele.
- "Experimental" quer dizer que o serviço só foi testado com um serviço falso, porque o CI não tem chave paga.
- Desde a 0.6.0, o modelo local padrão é o Laya, um ajuste do Qwen3.5 2B para as vagas, treinado com vagas públicas; o Qwen3.5 2B e o 4B originais ficam como opção em Configurações › Ferramentas.
- Desde a 0.6.0, com a tarefa ligada, a IA também lê o currículo, sugere perguntas para o perfil e prepara candidaturas. As perguntas e a candidatura levam o perfil sem nome, e-mail, telefone e cidade; o currículo leva o texto do PDF sem e-mail, telefone e CPF, e o nome e a cidade escritos nele vão junto. Na IA manual, o joBot só mostra o pedido para você copiar.
- A transcrição de áudio vai usar o faster-whisper, no seu computador, e apagar o áudio logo depois (fase 6).

<sub>Claude e Claude Code são marcas da Anthropic. O joBot não é afiliado à Anthropic.</sub>

## 🐳 Por que sem Docker

A instalação é nativa ([ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md)):

- O Docker Desktop é pesado e, no Windows e no macOS, roda dentro de uma máquina virtual.
- Abrir uma janela do navegador para você fazer o login fica difícil dentro de um container.
- Microfone, início com o sistema e atalho são coisas do sistema operacional.
- O login do Claude Code teria de ser feito de novo dentro do container (no macOS ele fica no Keychain, que o container não enxerga).

## 💻 Onde roda

- **Sistemas:** Linux, Windows e macOS. O desenvolvimento acontece no Linux; os instaladores da fase 3 cobrem Windows, Linux e Mac (o Mac é experimental).
- **Memória:** 8 GB de RAM (16 GB deixam tudo mais folgado).
- **Placa de vídeo:** não precisa.
