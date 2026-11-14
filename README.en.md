<div align="center">

# joBot

**Your personal job search assistant.**<br>
It gathers, filters and organizes jobs from many sites into a nice dashboard that runs on your own computer.

[![MIT license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![status: in development](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)](#roadmap)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](#requirements-and-installation)
[![platform: Linux](https://img.shields.io/badge/platforms-Linux-lightgrey?style=flat-square)](#requirements-and-installation)
<br>
[![FastAPI](https://img.shields.io/badge/FastAPI-dashboard-009688?style=flat-square&logo=fastapi&logoColor=white)](#how-it-works)
[![HTMX](https://img.shields.io/badge/HTMX-interface-3366CC?style=flat-square&logo=htmx&logoColor=white)](#how-it-works)
[![SQLite](https://img.shields.io/badge/SQLite-local%20database-003B57?style=flat-square&logo=sqlite&logoColor=white)](#how-it-works)
[![Playwright](https://img.shields.io/badge/Playwright-browser-2EAD33?style=flat-square)](#job-sources)
[![uv](https://img.shields.io/badge/uv-installs%20and%20runs-DE5FE9?style=flat-square)](#requirements-and-installation)
<br>
[![ruff](https://img.shields.io/badge/ruff-style-D7FF64?style=flat-square)](#how-to-contribute)
[![mypy strict](https://img.shields.io/badge/mypy-strict-2A6DB2?style=flat-square)](#how-to-contribute)
[![pytest + TDD](https://img.shields.io/badge/pytest-%2B%20TDD-0A9EDC?style=flat-square)](#how-to-contribute)
<br>
[![telemetry: none](https://img.shields.io/badge/telemetry-none-success?style=flat-square)](#privacy-and-security)
[![data: on your computer](https://img.shields.io/badge/data-on%20your%20computer-success?style=flat-square)](#privacy-and-security)
[![AI: optional](https://img.shields.io/badge/AI-optional-blueviolet?style=flat-square)](#artificial-intelligence)

[Português](README.md) · **English**

[How it works](#how-it-works) · [Installation](#requirements-and-installation) · [Roadmap](#roadmap) · [FAQ](#faq)

</div>

> [!IMPORTANT]
> **joBot phase 1 (the foundation) is done: version 0.1.0.** It searches public sources for jobs, keeps everything on your computer and shows it in a dashboard. You can already [install and use it](#requirements-and-installation).
> The rest (sites with login, AI, browser extension, Gmail and audio) is still a plan. See the [roadmap](#roadmap). Before you turn on the sources, read the [usage and terms notices](#license-and-notices).

## 📑 Contents

- [What joBot is](#what-is-jobot)
- [Star history](#star-history)
- [What it does not do](#what-it-does-not-do)
- [How it works](#how-it-works)
- [The two versions](#two-versions)
- [Job sources](#job-sources)
- [The dashboard](#dashboard)
- [Artificial intelligence](#artificial-intelligence)
- [Using the Claude Code you already have](#using-claude-code)
- [Privacy and security](#privacy-and-security)
- [Requirements and installation](#requirements-and-installation)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Project decisions](#project-decisions)
- [How to contribute](#how-to-contribute)
- [Support the project](#support-the-project)
- [License and notices](#license-and-notices)

<a id="what-is-jobot"></a>
## 🤖 What joBot is

joBot was born to help young university students find their first job. Then the idea grew: now it aims to help everyone who is looking for work.

Looking for a job today is tiring. You have to open many sites, repeat the same filters and hope you don't miss a deadline.
joBot does this repetitive work for you. It visits job sites, gathers everything in one place and shows what matches what you are looking for.
Everything runs on your computer. One installation serves one person, who can have several saved searches.

What it does today (phase 1):

- 🔎 **Search** for jobs in dozens of public sources: sites, APIs and company job boards.
- 🧹 **Clean up**: removes duplicate jobs, reads the salary and tags the field, level, work mode, region and contract type.
- 🎯 **Rank**: shows how well each job matches your search (● good, ◐ medium, ○ weak) and explains why. In phase 1 this is done by rules, without AI.
- 🗂️ **Organize**: each job has a status, from "new" to "offer".
- 📌 **Track pages** of programs, such as trainee and summer school, and tell you when the text changes.

What comes in the next phases:

- 🔐 **Sites that require login**, with your login done by hand (phase 2).
- ✍️ **Prepare the application**: cover letter, a résumé summary adjusted to the job and a list of what you have and what is missing, always in the job's language (phase 3, with optional AI).
- 🧩 **Help with forms**: a browser extension suggests answers, and you confirm (phase 4).
- 📬 **Read Gmail** (optional): brings in jobs from alert emails and suggests status changes when a recruiter replies (phase 5).

It works for every kind of job and every field: full-time employment (CLT), contractor (PJ), internship, trainee, temporary, apprentice, research and scholarships, programs and summer schools, public exams and notices.
Every feature can be turned on or off.

<a id="star-history"></a>
## ⭐ Star history

If joBot helps you, leave a star on the repository.

<a href="https://www.star-history.com/?repos=fezarosa-dev%2FjoBot&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=fezarosa-dev/joBot&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=fezarosa-dev/joBot&type=date&legend=top-left" />
   <img alt="Chart of the number of GitHub stars of joBot over time" src="https://api.star-history.com/chart?repos=fezarosa-dev/joBot&type=date&legend=top-left" />
 </picture>
</a>

<a id="what-it-does-not-do"></a>
## 🚫 What it does not do

joBot does not do the following, and was planned never to:

- **It does not mass-apply.** There is no "apply to 200 jobs with one click".
- **It does not send anything on its own.** You are always the one who sends the application.
- **It does not type your password.** On sites with login, you sign in with your own hands.
- **It does not bypass CAPTCHA.** If one shows up, it stops and warns you.
- **It does not send telemetry.** joBot does not send usage data to anyone.
- **It does not invent experience.** The AI only uses what is in your profile.

<a id="how-it-works"></a>
## ⚙️ How it works

```mermaid
flowchart LR
    subgraph Fontes["Job sources"]
        P["Public sources<br/>(APIs, job boards, GitHub)"]
        L["Sites with login<br/>(LinkedIn, Indeed...)"]
        G["Gmail<br/>(optional)"]
    end

    C["Collectors<br/>(one per source)"]

    subgraph Nucleo["Core"]
        N1["Removes duplicates"]
        N2["Reads the salary"]
        N3["Labels the job"]
        N4["Controls the life cycle"]
    end

    DB[("SQLite database<br/>on your computer")]
    UI["Dashboard in the browser<br/>127.0.0.1"]
    IA["Optional AI<br/>(Claude, local model or manual)"]
    EXT["Browser extension<br/>(optional)"]

    P --> C
    L --> C
    G --> C
    C --> N1 --> N2 --> N3 --> N4 --> DB
    DB --> UI
    IA <-.-> UI
    EXT <-.-> UI
```

One search cycle, step by step:

1. **At the scheduled time**, joBot wakes up. Public sources: every 3 hours. Or when you press "Search now". (Sites with login arrive in phase 2, with two searches a day.)
2. **Each collector** visits its source calmly and brings the jobs in a single format.
3. **The core** merges duplicate jobs, understands the salary, adds labels and marks as closed the jobs that disappeared.
4. **Everything goes to the SQLite database**, a file that stays on your computer.
5. **The dashboard** shows the result in your browser. It only works on your computer (address 127.0.0.1).
6. **When the AI arrives** (phase 3) and you turn it on, it will calculate the match with your profile and help prepare applications. Until then, the match comes from the rules of your search.

If one source fails, the others keep going. If the computer was off at the scheduled time, the missed search runs when it turns on.

<a id="two-versions"></a>
## 🖥️ The two versions

joBot will have a single core and two "faces". The **local version** is the focus. The **browser version** (GitHub Pages) is for people who don't want to install anything, and it arrives in phase 7.

| | 💻 Local version | 🌐 Browser version (GitHub Pages) |
|---|---|---|
| **Installation** | Native, with uv ([how to install](#requirements-and-installation)) | None: just open the site |
| **Sources** | All | Public sources only |
| **Sites with login** | Yes, with your manual login | No |
| **AI** | Automatic (Claude, local model) or manual | Manual (copy and paste); labels by rules only |
| **Browser extension** | Yes | No |
| **Gmail** | Yes (optional) | No |
| **Audio** | Yes, transcription on your computer | No |
| **Where the data lives** | In the SQLite database on your computer | Your profile stays in your browser (localStorage) |
| **Updates** | Every 3 h (public) and twice a day (login) | Once a day, with an "updated on &lt;date&gt;" notice |

In the browser version, you can export your profile to a file and import it later into the local version. There is also a "download full version" button.
It never uses logins or secrets.

<a id="job-sources"></a>
## 🌎 Job sources

Each source has an on/off switch, in Settings, Sources. In phase 1 the public sources work; sites with login arrive in phase 2.
Three Brazilian portals call for care, because of their terms of use: Eureca, Abler and Gupy. Read the notice in [License and notices](#license-and-notices).

| Group | Examples |
|---|---|
| Job repositories on GitHub | backend-br, frontendbr, soujava, remotejobsbr, developersRJ |
| International sites and APIs | Jobicy, Hacker News "Who is hiring", Remotive, RemoteOK, Himalayas, We Work Remotely |
| Company job boards (recruiting systems, the "ATS") | Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Eightfold, Oracle HCM, InHire, Quickin, Recrutei |
| Brazilian portals | Gupy, CIEE, Sólides, IEL, Super Estágios, Cia de Talentos, Eureca, Abler |
| Careers at big companies | Google, Amazon, Microsoft, NVIDIA |
| Internship boards | Public boards, such as the one at USP |
| 🔐 Sites with login (phase 2, first) | LinkedIn, Indeed, Catho, Vagas.com |
| 🔐 Sites with login (phase 2, later, one at a time) | InfoJobs, Glassdoor, Programathor, GeekHunter, Remotar, Trampos, Revelo, Coodesh |

Also in phase 1:

- **Own company list**, made only of public facts (company name and job board identifier), each one checked against the real address. You add your own in Companies.
- **Weekly discovery** of new job boards through Common Crawl (a public archive of the web). The finds go to Suggested, and nothing enters your search until you approve it. You can turn it off in Settings.
- **Tracking program pages**, such as trainee and summer school, in the Sites screen. The change shows up in the Programs tab.

**Polite collection.** The robot identifies itself, waits between one request and the next and waits longer when the site asks for calm.

**Health of each source.** On every search, each source is marked as ok, partial or failed. You see this in the dashboard.

> [!WARNING]
> **Sites with login carry risk.** LinkedIn, Indeed and others may restrict accounts that access them automatically, and this may go against their terms of use.
> joBot reduces the risk: it opens a visible Chrome, you do the login, it only reads (it does not click "apply", it does not send messages), and it visits rarely and slowly.
> Even so, the risk exists. **You decide whether to turn on each site.**

<a id="dashboard"></a>
## 📋 The dashboard

The dashboard opens in your browser, at `http://127.0.0.1:47615`. The menu has Jobs, Searches, Sources, Companies, Suggested, Sites and Settings.

- **Tabs:** Today's highlights (the best new ones, one per company), All, New, Closing soon, Saved, Applied, Programs and Hidden.
- **Filters** as "chips" (little buttons) with counts. The current filter stays in the page address, so you can save the link. Quick search with the `/` key.
- **Status of each job:** new → saved → applied → interview → rejected or offer.
- **Match with your search:** ● good, ◐ medium, ○ weak, always with the reasons.
- **12-month calendar** on each job, to see deadlines at a glance.
- **Jobs hidden** by a rule can come back. The dashboard shows how many were hidden for each reason.
- **"Something wrong with this job?"**: a button to fix a label or a piece of data.
- **Look inspired by Apple's style:** translucency, smooth animations, light and dark mode following the system. SF font on Mac and Inter on other systems.
- **Languages:** Portuguese and English.

<a id="artificial-intelligence"></a>
## 🧠 Artificial intelligence

The AI is **optional** and arrives in phase 3. Without it, joBot works with rules and keywords, and that is how phase 1 works.

> **Golden rule:** the AI only uses the data in your profile. It never invents experience, courses or skills, and it shows which data it used.
> If information is missing, it asks a question, and your answer is saved in the profile.

### Options

| Option | Cost | Where it runs | Where the data goes | Needs internet? |
|---|---|---|---|---|
| **Claude Code session** ([details](#using-claude-code)) | Uses your Claude subscription | At Anthropic | Anthropic | Yes |
| **Anthropic API key** | Pay per use | At Anthropic | Anthropic | Yes |
| **Local model (Qwen)** | Free | On your computer | Does not leave the computer | No (after downloading) |
| **Keywords** (no AI) | Free | On your computer | Does not leave the computer | No |
| **Manual AI** (copy and paste) | Free in joBot; depends on the chat AI you use | In the chat AI you choose | Wherever you paste it | Depends on the chat AI |

So you don't have to set up task by task, there are three shortcuts:

- **All Claude**: uses Claude for every task.
- **All offline**: uses Qwen, which runs on your computer, for every task.
- **Custom**: you choose the option and the model for each task.

### Default models with Claude

The app uses only two models: Haiku 5.5 (`claude-haiku-5-5`), faster and cheaper, and Sonnet 5.5 (`claude-sonnet-5-5`), more capable.
**The Opus model is never used**, to save cost and your usage limit.

| Task | Model |
|---|---|
| Read the résumé and build the profile | Sonnet 5.5 |
| Match score with the job | Haiku 5.5 |
| Prepare the application | Sonnet 5.5 |
| Browser extension | Sonnet 5.5 |
| Extra questionnaire questions | Sonnet 5.5 |
| Job alert emails | Haiku 5.5 |
| Recruiter replies | Keywords + Haiku 5.5 |

### Offline package

At installation, joBot will ask once whether you want the offline package. It lets you use AI without internet and without paying anything.

| Item | Size | Note |
|---|---|---|
| llama-server (llama.cpp program that runs the model) | ~23 MB Linux · ~25 MB Windows · ~17 MB macOS with Apple chip | Pinned version, checked by checksum |
| Qwen3.5-2B (AI model) | 1.28 GB | For computers with 8 GB of RAM |
| Qwen3.5-4B (AI model) | 2.74 GB | For computers with 12 GB or more |
| Audio transcription (faster-whisper "small") | 484 MB | To answer by speaking |
| Audio transcription "medium" | 1.53 GB | Optional, more accurate |

A "checksum" is a fingerprint of the file: joBot checks that the downloaded file is exactly the expected one.

<a id="using-claude-code"></a>
## ✨ Using the Claude Code you already have

> This section describes phase 3. Phase 1 does not use AI.

If you already use Claude Code on your computer, joBot can use Claude **with no extra login**.
You do not log in to Claude inside joBot. Ever.

### Step by step

1. **Install Claude Code** following the instructions on the [official Claude Code site](https://code.claude.com/docs/en/setup#install-claude-code).
2. **Sign in once through the terminal.** Open the terminal, type `claude` and press Enter. Inside it, type `/login` and follow the instructions, which open the Anthropic site. This login is done with Anthropic itself ([how login works](https://code.claude.com/docs/en/authentication)).
3. **Open joBot.** At step 0 of the first run, it notices on its own that Claude Code is ready and offers this option.

That's it. The account, the subscription, the limits and the cost remain yours.

### What joBot does

- Asks Claude Code whether you are logged in (`claude auth status`).
- Sends requests through Claude Code's headless mode (`claude -p`, [documentation](https://code.claude.com/docs/en/headless)), asking for the answer in a fixed format (JSON).
- Uses only Haiku 5.5 or Sonnet 5.5.
- If there is an error, it shows it in the dashboard. If you are not logged in, it explains how to sign in through the terminal.

### What joBot never does

- Never reads, copies, stores or passes on your Claude credential or token.
- Never shows a Claude login screen inside itself.
- Never bundles or modifies Claude Code.
- Never uses the Opus model.

### Technical precautions

- Call with no tools at all (`--tools ""`), no MCP servers (`--strict-mcp-config`) and without saving the session (`--no-session-persistence`). Details in the [command reference](https://code.claude.com/docs/en/cli-reference).
- Runs in an empty temporary folder, so it doesn't load the settings of some project. Your personal settings in `~/.claude` still apply.
- Removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the call environment (except in "API key" mode). Without this, Claude Code would use the key and the charge would go to the API without you noticing. For the same reason, it removes the cloud provider variables (`CLAUDE_CODE_USE_BEDROCK`, `CLAUDE_CODE_USE_VERTEX` and `CLAUDE_CODE_USE_FOUNDRY`).
- Before each call, it checks with `claude auth status` that the active login is the subscription one. If another method is active (for example, an `apiKeyHelper` in your settings), the dashboard warns you and does not make the call.
- Does not use `--bare`, because that mode does not read the subscription login.
- Does not use or ask for `CLAUDE_CODE_OAUTH_TOKEN`.
- The credential stays where Claude Code keeps it: `~/.claude/.credentials.json` on Linux, `%USERPROFILE%\.claude\.credentials.json` on Windows and the Keychain on macOS. If the `CLAUDE_CONFIG_DIR` variable is set, the folder changes. joBot never opens any of it.

### About Anthropic's rules

Anthropic does not allow third-party apps to offer Claude login, to send requests using people's subscriptions on their behalf, or to collect, store or pass on credentials and tokens. The login must happen in Anthropic's own flow ([official policy](https://code.claude.com/docs/en/legal-and-compliance)). Apps that run Claude Code are also under Anthropic's Commercial Terms: Claude Code cannot be modified and each person signs in with their own account.
joBot does not offer login, does not bundle or modify Claude Code and never touches your credential: each person uses their own, on their own computer.

It also does not share a subscription between people: each one runs their own Claude Code and spends only the limit of their own subscription.
Details in [ADR 0010](docs/decisions/0010-claude-code-da-pessoa.md) (in Portuguese).

<sub>Claude and Claude Code are trademarks of Anthropic. joBot is not affiliated with Anthropic.</sub>

<a id="privacy-and-security"></a>
## 🔒 Privacy and security

> These rules apply to phase 1. The ones that talk about AI, Gmail, extension, audio and the password vault describe the next phases.

- **There is no joBot server.** Your data stays on your computer.
- **No telemetry.** No usage data is sent.
- **Search and check requests only.** joBot only makes network requests in these cases: to the public job sources you leave on (they all come on), including each job's page; to the Central Bank of Brazil, to get the dollar rate, with currency conversion on (it comes on); to Common Crawl, once a week, to discover new companies, and then to those companies' job boards, to check them (it comes on); to the pages you ask it to follow (it comes on, but with no pages on the list there is no request); to a company's website, only when you paste an address, test it or accept a suggestion; to the internet through git and uv, to download the new joBot version, only when you ask to update (the jobot atualizar command). If you turn on the version notice (next item), it also asks GitHub (it comes off). Whoever receives a request sees your computer's IP address, as with any internet request.
- **Version notice off by default.** If you turn it on (Settings, Privacy), once a day joBot asks `api.github.com` which version is the newest. The request carries only joBot's fixed user agent (which includes the version number) and your computer's IP, like any request on the internet. It carries no search and no data of yours. Off, it makes no request at all.
- **Secrets in the system vault.** The Gmail token, the API key and the Telegram token stay in the operating system's password vault. Without a vault, they go to a file that only your user can read, and the dashboard warns you.
- **Protected personal data.** CPF (Brazilian tax ID) and date of birth stay in the database, in a folder that only your user can access and that is not synced to the cloud. The dashboard recommends turning on disk encryption (LUKS, BitLocker or FileVault).
- **Exporting the profile does not include documents** such as the CPF, unless you check that option.
- **Dashboard closed to the outside.** It only accepts connections from your own computer (127.0.0.1) and checks every request.
- **Paired extension.** The extension only talks to joBot after pairing. It never touches password or card fields.
- **Audio deleted.** The recording is transcribed on your computer and deleted right after.
- **Gmail read-only.** Access is read-only, with a Google project created by you.
- **Your data only leaves** for the services you turn on: Anthropic, Google or Telegram, and other optional services (see ADRs [0009](docs/decisions/0009-ia-backends-e-modelos.md) and [0014](docs/decisions/0014-seguranca-e-privacidade.md)).
- **Found a security flaw?** Do not open a public issue. Follow the [security policy](.github/SECURITY.en.md).

<a id="requirements-and-installation"></a>
## 📦 Requirements and installation

> This is the phase 1 installation (version 0.1.0): you download the code and run it with uv. The one-command installer only arrives in phase 8.

### Requirements

- **System:** Linux. Windows and macOS have not been tested yet, and the background service only exists on Linux.
- **Programs:** [git](https://git-scm.com/) and [uv](https://docs.astral.sh/uv/). uv downloads Python 3.14 and the libraries by itself.
- **Memory:** an ordinary computer is enough. The 8 GB of RAM only matter when the local AI arrives (phase 3).
- **Graphics card and Docker:** not needed. The installation is native.
- **Internet:** to download joBot and to search for jobs.

### Install and open

```bash
git clone https://github.com/fezarosa-dev/joBot.git
cd joBot
uv sync --locked
uv run jobot
```

The last command starts joBot and opens the dashboard in your browser, at `http://127.0.0.1:47615`. With nothing after `jobot`, the `abrir` command runs.
If another program already uses port 47615, joBot warns you and opens nothing. Set `JOBOT_PORTA` to another port and run it again.

### Commands

Run all of them from inside the `joBot` folder, with `uv run` in front (for example, `uv run jobot buscar`).

| Command | What it does |
|---|---|
| `jobot abrir` | Opens the dashboard in the browser and starts the server if it is not running yet. This is the default. |
| `jobot sair` | Stops the server. |
| `jobot serve` | Starts only the server, without opening the browser. |
| `jobot buscar` | Runs one search in the terminal and shows how each source went. |
| `jobot segundo-plano ligar` | Turns on the background service, so joBot starts by itself with your user. `desligar` removes the service, and `status` shows how it is. Linux only. |
| `jobot atualizar` | Updates joBot to the newest version and turns back on what was on. |
| `jobot avaliar-rotulos` | For project maintainers: measures the label rules against an examples file of your own. |

### Where the data lives

- Everything stays in the `~/.local/share/jobot` folder, accessible only to your user. To use another folder, set `JOBOT_DADOS`.
- The database is the `jobot.db` file, and the record of what happened is in `logs/jobot.log`.
- Nothing leaves that folder, except the network requests listed in [Privacy and security](#privacy-and-security).

### If you use distrobox

joBot also runs inside a distrobox container, as on Fedora Silverblue.

- **The browser:** there is almost never a browser inside the container. joBot calls the one on the host system with `distrobox-host-exec xdg-open`.
- **The background service:** the service lives in your user's systemd, on the host system, and joBot reaches it through `distrobox-host-exec` and `distrobox-enter`. Both must be available inside the container.
- **The home folder:** the container's must be the same as the system's. If it is not, the dashboard refuses to turn on the background service and says why.
- Run all the commands from inside the container.

### First run

The first time, the dashboard asks two questions. Everything is optional.

| Step | What happens |
|---|---|
| **1. What are you looking for?** | Job titles or keywords, cities, work modes, levels, minimum salary and job languages. This becomes your first search. If you skip it, jobs appear by date, with no match score. You can change it later, in Searches. |
| **2. Background** | Choose whether joBot starts by itself with your user and searches for jobs every 3 hours, even with the dashboard closed. You can change it later, in Settings. |

Then press **Search now**, at the top of the dashboard, or wait for the next scheduled search.

### Updating

Run `uv run jobot atualizar`. The version notice is optional and comes **off by default**: to turn it on, go to Settings, Privacy. The details are in [Privacy and security](#privacy-and-security).

### What the next phases will download

In phase 1, `uv sync` only downloads Python 3.14 (if missing) and joBot's libraries. There is no AI model, no controlled browser and no large file. These items come later, and they are optional:

| Item | Size | When |
|---|---|---|
| Browser controlled by Playwright | To be defined | Phase 2, only for sites with login |
| llama-server | ~17 to 25 MB, depending on the system | Phase 3 (offline package) |
| Qwen3.5-2B **or** Qwen3.5-4B model | 1.28 GB or 2.74 GB | Phase 3 (offline package) |
| Audio transcription "small" | 484 MB | Phase 5 |
| Audio transcription "medium" | 1.53 GB | Phase 5, optional |
| multilingual-e5-small model | ~120 MB | Only if some label falls below 90% accuracy |

<a id="roadmap"></a>
## 🗺️ Roadmap

Each phase only starts after the previous one passes the tests. No dates are promised.

| Phase | What is included | Status |
|---|---|---|
| **1. Base** | Common core, public sources, database, dashboard and scheduling | 🟢 Done (version 0.1.0) |
| **2. Browser with login** | Visible Chrome, site mapping, CAPTCHA handling | ⚪ Planned |
| **3. Local AI** | Offline package (llama-server + Qwen) | ⚪ Planned |
| **4. Browser extension** | Browser extension for forms | ⚪ Planned |
| **5. Audio and Gmail** | Answers by voice and email reading | ⚪ Planned |
| **6. Training** | Learn from what you save and discard | ⚪ Planned |
| **7. GitHub Pages version** | GitHub Pages version, no installation | ⚪ Planned |
| **8. Release** | Installers, README with badges and security review | ⚪ Planned |

<a id="faq"></a>
## ❓ FAQ

The most common questions and answers are on the [FAQ page of the wiki](https://github.com/fezarosa-dev/joBot/wiki/Frequently-asked-questions).

<a id="project-decisions"></a>
## 📚 Project decisions

Each important decision is recorded in a short document called an ADR (architecture decision record).

- **Index (in Portuguese):** [docs/decisions/README.md](docs/decisions/README.md)
- **Open questions (open and resolved, in Portuguese):** [duvidas.md](duvidas.md)

| No. | Decision |
|---|---|
| 0001 | [Scope: what joBot is and what it is not](docs/decisions/0001-escopo-do-jobot.md) |
| 0002 | [Two versions, one core](docs/decisions/0002-duas-versoes-um-nucleo.md) |
| 0003 | [Technologies and native installation (no Docker)](docs/decisions/0003-stack-e-instalacao-nativa.md) |
| 0004 | [Public job sources and polite collection](docs/decisions/0004-fontes-publicas.md) |
| 0005 | [Sites that require login](docs/decisions/0005-sites-com-login.md) |
| 0006 | [Search schedule and background running](docs/decisions/0006-agenda-e-segundo-plano.md) |
| 0007 | [Job data handling: duplicates, life cycle, salary and labels](docs/decisions/0007-tratamento-dos-dados.md) |
| 0008 | [Dashboard and look](docs/decisions/0008-painel-e-visual.md) |
| 0009 | [Artificial intelligence: options, models and offline package](docs/decisions/0009-ia-backends-e-modelos.md) |
| 0010 | [Use the Claude Code the person already has (no login inside joBot)](docs/decisions/0010-claude-code-da-pessoa.md) |
| 0011 | [Profile, résumé, first run and audio](docs/decisions/0011-perfil-e-primeira-execucao.md) |
| 0012 | [Browser extension](docs/decisions/0012-extensao-do-navegador.md) |
| 0013 | [Gmail and notices](docs/decisions/0013-gmail-e-avisos.md) |
| 0014 | [Security and privacy](docs/decisions/0014-seguranca-e-privacidade.md) |
| 0015 | [Model training (phase 6)](docs/decisions/0015-treino.md) |
| 0016 | [License, clean room and work process](docs/decisions/0016-licenca-clean-room-e-processo.md) |
| 0017 | [Project phases](docs/decisions/0017-fases.md) |
| 0018 | [Community maintenance and CI open to every PR](docs/decisions/0018-manutencao-pela-comunidade.md) |
| 0019 | [Project wiki and question form](docs/decisions/0019-wiki-do-projeto.md) |
| 0020 | [Financial support: donations only](docs/decisions/0020-apoio-financeiro.md) |
| 0021 | [No Dependabot: dependencies updated by hand](docs/decisions/0021-sem-dependabot.md) |

<a id="how-to-contribute"></a>
## 🤝 How to contribute

The repository is on GitHub. Phase 1 is done, and the next ones are being planned.

- **Suggestions and job sources** can already be sent through issues, with ready-made forms.
- **Questions** go through the [question form](https://github.com/fezarosa-dev/joBot/issues/new?template=duvida.yml). Read the [FAQ](https://github.com/fezarosa-dev/joBot/wiki/Frequently-asked-questions) first.
- **Code** only after the release (phase 8).
- The wiki is edited through PRs on the `wiki/` folder of the repository.
- The complete rules are in the contribution guide.

Useful links:

- [Contribution guide](.github/CONTRIBUTING.en.md)
- [Code of Conduct](.github/CODE_OF_CONDUCT.en.md)
- [Security policy](.github/SECURITY.en.md)
- [Support](.github/SUPPORT.en.md)
- [Changelog](CHANGELOG.en.md)

<a id="support-the-project"></a>
## 💛 Support the project

joBot is free and kept by one person. If it helps you and you want to chip in for upkeep, you can donate:

- **Pix** (Brazil only), random key:

  ```text
  65c34f26-c646-431f-af90-e5b1d2808ad4
  ```

- **Buy Me a Coffee:** <https://buymeacoffee.com/zanoni.dev>

Donating is optional. joBot stays fully free, with no ads, no affiliate links and no tracking (see [decision 0020](docs/decisions/0020-apoio-financeiro.md)).

Other ways to help and more details are on the [Support the project wiki page](https://github.com/fezarosa-dev/joBot/wiki/Support-the-project).

<a id="license-and-notices"></a>
## ⚖️ License and notices

- **License:** MIT. See the [`LICENSE`](LICENSE) file.
- **Trademarks:** Claude and Claude Code are trademarks of Anthropic. joBot is not affiliated with Anthropic. The other trademarks mentioned belong to their owners.
- **Terms of use:** respect the terms of use of each site you turn on. joBot is gentle with the sources (it waits between requests, uses no login and bypasses no block), but you decide what to turn on, at your own risk.
- **Personal use:** joBot is made for one person to organize their own job search, on their own computer. Do not use it to build a job site or to pass the jobs on to other people: several sources forbid that.
- **Eureca, Abler and Gupy:** these three Brazilian portals have no open API, with published usage rules, for a program like joBot. It reads only what the portals themselves show without login, slowly, and always with the link to the original job. Their terms of use may restrict this use, and each one has its own on/off switch.
- **Eureca and prior consent:** Eureca's terms ask for prior consent, and Eureca comes on like the other sources. If you prefer to respect that request, turn Eureca off in Settings, Sources, by unchecking Eureca and saving.

---

<div align="center">
<sub>[Leia em português](README.md)</sub>
</div>
