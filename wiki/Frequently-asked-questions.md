🌐 [Português](Perguntas-frequentes) · **English**

# ❓ Frequently asked questions

**The most common questions about joBot. Click a question to see the answer.**

---

<details>
<summary><strong>Why not use Docker?</strong></summary>

The audience is non-technical and uses ordinary computers. Docker Desktop is heavy and, on Windows and macOS, runs inside a virtual machine.
joBot needs to open a browser window so you can log in, use the microphone, start with the system and create shortcuts. All of this is hard inside a container.
And the Claude Code login would have to be done again in there (on macOS it lives in the Keychain, which the container cannot see). See [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md).
</details>

<details>
<summary><strong>Do I need to log in to Claude inside joBot?</strong></summary>

No. You sign in once to Claude Code, through the terminal, in Anthropic's own flow. joBot only detects that it is ready and uses it.
It never sees your password or your token. That session still waits for the owner's decision on the terms of use; in 0.5.0 and 0.6.0, Claude comes in through the Anthropic API key, added in Settings › Services. See [Using the Claude Code you already have](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#using-claude-code) and [ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md).
</details>

<details>
<summary><strong>Do I have to pay for anything?</strong></summary>

joBot is free and open source. Claude, OpenAI and Gemini are optional, with your key: Claude and OpenAI are paid per use, and Gemini may be billed per use, depending on your Google AI Studio account plan.
The local model, keywords and manual AI are free.
</details>

<details>
<summary><strong>Does it work without AI? And without internet?</strong></summary>

Without AI, yes: joBot uses rules and keywords.
Without internet, new jobs don't arrive. But the dashboard keeps working, and so does the local model, once downloaded. The README has the [table of what works without internet](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#what-works-without-internet).
</details>

<details>
<summary><strong>Does joBot apply on its own?</strong></summary>

No. It prepares the application and helps fill in forms, but you are always the one who reviews and sends.
</details>

<details>
<summary><strong>Can my LinkedIn account be restricted?</strong></summary>

It can. The risk exists, and it can't be reduced to zero.
joBot reduces the risk: you do the login with your own hands, in a regular browser window, it only reads, it visits a few times a day, it goes slowly and it does not get past a CAPTCHA on its own (only your 2Captcha, if you turn it on).
Each site with login has a switch. You decide whether to turn it on.
</details>

<details>
<summary><strong>What does "closed" mean for a LinkedIn job?</strong></summary>

LinkedIn's search sorts by relevance, and joBot reads only the last week. So an open job can drop off the list without having closed.
For LinkedIn, "closed" means "not seen for 30 days". If a job closed by mistake comes back to the list, it reopens by itself.
</details>

<details>
<summary><strong>What if a CAPTCHA shows up?</strong></summary>

The dashboard shows a red warning and the computer shows a notification. The browser window stays still on the page, waiting for you to solve it.
The other sources continue normally. joBot never tries to get past the CAPTCHA on its own.
In the browsing with login, if you save your 2Captcha key and turn on the switch in Settings, Services (it comes off), joBot sends the challenge to 2Captcha first. If it is not solved, the warning above applies.
</details>

<details>
<summary><strong>How do I let joBot read my Gmail?</strong></summary>

With a Google app password, which you create in your account and paste into joBot. You do not need to create a Google Cloud project.
It works with personal Google accounts. It does not work with work or school accounts, with Advanced Protection, or with 2-Step Verification that uses only security keys.
The Gmail card is in Settings, Accounts, and reading the emails stays in phase 6. See the [step-by-step guide](Gmail-app-password) and [ADR 0024](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0024-gmail-por-senha-de-app.md) (Portuguese).
</details>

<details>
<summary><strong>Does my data go to any server?</strong></summary>

There is no joBot server. Your data stays on your computer.
It only goes to the services you turn on: Anthropic, OpenAI or Google (if you turn on an AI task on one of them; depending on the task, the job text goes, your profile without name, email, phone and city, or the résumé text without email, phone and CPF), the AI address you type, Google (if you turn on Gmail) and Telegram (if you turn on the daily summary). It may also go to Jev (if you choose that option in email classification). RunPod never gets your data: the Laya training runs outside the app, only with jobs from public sources. With manual AI, it goes to the chat AI where you paste it.
</details>

<details>
<summary><strong>Will it run on my computer?</strong></summary>

The idea is to run on ordinary computers, with 8 to 16 GB of RAM and no dedicated graphics card, with Linux, Windows or macOS.
</details>
