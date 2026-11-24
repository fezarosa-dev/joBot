🌐 [Português](Tecnologias) · **English**

# 🧰 Technologies

**joBot's tools, what each one is for and why it was chosen.**

---

## 🧱 The base

| Technology | What for | Why |
|---|---|---|
| 🐍 **Python** (3.14 or newer) | The language of all of joBot. | Chosen in [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md). |
| 📦 **uv** | Install and run joBot and its libraries. | The installation is native, without Docker; the phase 3 installer already brings `uv` and everything it installs. |
| ⚡ **FastAPI** (0.162.7) + **Uvicorn** (0.54.0) | The dashboard server. | The dashboard opens in your browser and only accepts connections from your own computer (127.0.0.1). |
| 🧩 **Jinja2** (3.1.6) | Build the dashboard pages. | The pages come ready from the server. |
| 🔁 **HTMX** | Update parts of the page without reloading everything. | A responsive interface with little JavaScript. The file ships inside the app. |
| 🗄️ **SQLite** | The database. | A single file that stays on your computer. No database server to install. |
| 🌐 **httpx** (0.28.1) | Request the pages and APIs of the job sources. | It is joBot's only HTTP client, where polite collection lives (identification and a pause between requests). |
| 🔍 **selectolax** (1.0.2) | Read the HTML of job pages. | Separate the job data from the rest of the page. |
| 🔐 **keyring** (25.7.0) | Keep the 2Captcha key in the system password vault. | The key is not left in a plain file; without a vault, it goes to a file only you can read (ADR 0014). |
| 🎭 **Playwright** (1.65.1) | Control a browser. | Reads the sites with login, using the session you opened (phase 2). It also runs the screen tests. |
| 📄 **pypdf** (7.1.1) | Read the text of the PDF résumé in the Profile tab (0.6.0). | Runs in a separate process, with a time limit and a page limit; the PDF and its text are not saved. |

## ✅ Quality

| Technology | What for | Why |
|---|---|---|
| 🧪 **pytest** (9.2.0) | Run the tests. | TDD in all code: write the test, see it fail, implement, see it pass. |
| 🧹 **ruff** (0.17.5) | Style and common mistakes. | A single style across the project. |
| 🔎 **mypy** strict (2.4.1) | Check the types. | In strict mode, type errors show up before running. |
| 🤖 **GitHub Actions** | Automatic tasks on GitHub. | Runs the tests on every PR (pull request), including from forks, free for public repositories. It also copies this wiki and will build the GitHub Pages version (phase 8). |

> [!NOTE]
> The versions in parentheses are the ones [`pyproject.toml`](https://github.com/fezarosa-dev/joBot/blob/main/pyproject.toml) pins today.
> A new dependency only comes in with a reason and a license compatible with MIT (avoiding GPL and AGPL).

## 🧠 Artificial intelligence (optional)

AI is optional. Without it, joBot works with rules and keywords ([ADR 0009](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0009-ia-backends-e-modelos.md)).

| Option | Cost | Where it runs |
|---|---|---|
| **Local model** (Qwen, via llama.cpp's llama-server), since 0.5.0 | Free | On your computer, offline after the download |
| **Anthropic API key**, since 0.5.0 (experimental) | Pay per use | At Anthropic |
| **OpenAI or Google Gemini key**, since 0.5.0 (experimental) | Pay per use (Gemini may be billed per use, depending on your Google AI Studio account plan) | At OpenAI or Google |
| **OpenAI-compatible address** (Ollama, LM Studio, OpenRouter), since 0.5.0 (experimental: the same client only ran against the local model's `llama-server`, in CI) | Depends on the service | Wherever the address points |
| **Keywords** (no AI) | Free | On your computer |
| **Manual AI** (copy and paste), in 0.6.0 | Free in joBot | In the chat AI you choose |
| **Claude Code session** you already have (waiting for the owner) | Uses your Claude subscription | At Anthropic |

- With Claude, the app only uses Haiku 5.5 and Sonnet 5.5. **Opus is never used**, to save cost and your usage limit.
- joBot **has no Claude login**. It uses the Claude Code already on your computer, in headless mode, with no tools and without touching your credentials ([ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md)).
- The Claude Code session waits for the owner's decision on the terms of use and has not been built yet; in 0.5.0, Claude comes in through the Anthropic API key.
- The local model runs through `llama-server`, in a pinned version checked by checksum (a fingerprint of the file), on the processor only. joBot downloads it from GitHub (`llama-server`) and Hugging Face (the Qwen3.5 model), only when you ask. joBot does not bring Ollama or PyTorch; if you already use Ollama or LM Studio, you can point the compatible address at it.
- "Experimental" means the service was only tested against a fake service, because CI has no paid key.
- Laya, a fine-tune of Qwen3.5 2B for jobs, does not ship in 0.5.0 yet: it comes in a later version, after the training.
- Audio transcription will use faster-whisper, on your computer, and delete the audio right after (phase 6).

<sub>Claude and Claude Code are trademarks of Anthropic. joBot is not affiliated with Anthropic.</sub>

## 🐳 Why no Docker

The installation is native ([ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md)):

- Docker Desktop is heavy and, on Windows and macOS, runs inside a virtual machine.
- Opening a browser window for you to log in is hard inside a container.
- Microphone, starting with the system and shortcuts are operating system features.
- The Claude Code login would have to be done again inside the container (on macOS it lives in the Keychain, which the container cannot see).

## 💻 Where it runs

- **Systems:** Linux, Windows and macOS. Development happens on Linux; the phase 3 installers cover Windows, Linux and Mac (the Mac is experimental).
- **Memory:** 8 GB of RAM (16 GB gives more room).
- **Graphics card:** not needed.
