🌐 [Português](Tecnologias) · **English**

# 🧰 Technologies

**joBot's tools, what each one is for and why it was chosen.**

---

## 🧱 The base

| Technology | What for | Why |
|---|---|---|
| 🐍 **Python** (3.14 or newer) | The language of all of joBot. | Chosen in [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md). |
| 📦 **uv** | Install and run joBot and its libraries. | The installation is native and planned for one command, without Docker. |
| ⚡ **FastAPI** (0.162.7) + **Uvicorn** (0.54.0) | The dashboard server. | The dashboard opens in your browser and only accepts connections from your own computer (127.0.0.1). |
| 🧩 **Jinja2** (3.1.6) | Build the dashboard pages. | The pages come ready from the server. |
| 🔁 **HTMX** | Update parts of the page without reloading everything. | A responsive interface with little JavaScript. The file ships inside the app. |
| 🗄️ **SQLite** | The database. | A single file that stays on your computer. No database server to install. |
| 🌐 **httpx** (0.28.1) | Request the pages and APIs of the job sources. | It is joBot's only HTTP client, where polite collection lives (identification and a pause between requests). |
| 🔍 **selectolax** (1.0.2) | Read the HTML of job pages. | Separate the job data from the rest of the page. |
| 🎭 **Playwright** (1.65.1) | Control a browser. | Opens a visible Chrome so you can log in and solve CAPTCHAs (phase 2). It also runs the screen tests. |

## ✅ Quality

| Technology | What for | Why |
|---|---|---|
| 🧪 **pytest** (9.2.0) | Run the tests. | TDD in all code: write the test, see it fail, implement, see it pass. |
| 🧹 **ruff** (0.17.5) | Style and common mistakes. | A single style across the project. |
| 🔎 **mypy** strict (2.4.1) | Check the types. | In strict mode, type errors show up before running. |
| 🤖 **GitHub Actions** | Automatic tasks on GitHub. | Runs the tests on every PR (pull request), including from forks, free for public repositories. It also copies this wiki and will build the GitHub Pages version (phase 7). |

> [!NOTE]
> The versions in parentheses are the ones [`pyproject.toml`](https://github.com/fezarosa-dev/joBot/blob/main/pyproject.toml) pins today.
> A new dependency only comes in with a reason and a license compatible with MIT (avoiding GPL and AGPL).

## 🧠 Artificial intelligence (optional)

AI is optional. Without it, joBot works with rules and keywords ([ADR 0009](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md)).

| Option | Cost | Where it runs |
|---|---|---|
| **Claude Code session** you already have | Uses your Claude subscription | At Anthropic |
| **Anthropic API key** | Pay per use | At Anthropic |
| **Local model** (Qwen, via llama.cpp's llama-server) | Free | On your computer, offline after the download |
| **Keywords** (no AI) | Free | On your computer |
| **Manual AI** (copy and paste) | Free in joBot | In the chat AI you choose |

- With Claude, the app only uses Haiku 5.5 and Sonnet 5.5. **Opus is never used**, to save cost and your usage limit.
- joBot **has no Claude login**. It uses the Claude Code already on your computer, in headless mode, with no tools and without touching your credentials ([ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md)).
- The local model runs through `llama-server`, in a pinned version checked by checksum (a fingerprint of the file). No Ollama and no PyTorch.
- Audio transcription uses faster-whisper, on your computer, and the audio is deleted right after.

<sub>Claude and Claude Code are trademarks of Anthropic. joBot is not affiliated with Anthropic.</sub>

## 🐳 Why no Docker

The installation is native ([ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md)):

- Docker Desktop is heavy and, on Windows and macOS, runs inside a virtual machine.
- A visible Chrome for manual login and CAPTCHA is hard inside a container.
- Microphone, starting with the system and shortcuts are operating system features.
- The Claude Code login would have to be done again inside the container (on macOS it lives in the Keychain, which the container cannot see).

## 💻 Where it runs

- **Systems:** Linux, Windows and macOS. Development happens on Linux; the Windows and macOS installers arrive in phase 8.
- **Memory:** 8 GB of RAM (16 GB gives more room).
- **Graphics card:** not needed.
