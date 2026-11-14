Português: [Perguntas frequentes](Perguntas-frequentes)

<details>
<summary><strong>Why not use Docker?</strong></summary>

The audience is non-technical and uses ordinary computers. Docker Desktop is heavy and, on Windows and macOS, runs inside a virtual machine.
joBot needs to open a visible Chrome so you can log in and solve CAPTCHAs, use the microphone, start with the system and create shortcuts. All of this is hard inside a container.
And the Claude Code login would have to be done again in there (on macOS it lives in the Keychain, which the container cannot see). See [ADR 0003](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0003-stack-e-instalacao-nativa.md).
</details>

<details>
<summary><strong>Do I need to log in to Claude inside joBot?</strong></summary>

No. You sign in once to Claude Code, through the terminal, in Anthropic's own flow. joBot only detects that it is ready and uses it.
It never sees your password or your token. See [Using the Claude Code you already have](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#using-claude-code) and [ADR 0010](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0010-claude-code-da-pessoa.md).
</details>

<details>
<summary><strong>Do I have to pay for anything?</strong></summary>

joBot is free and open source. Claude is optional and paid, by subscription or through the API.
The local model, keywords and manual AI are free.
</details>

<details>
<summary><strong>Does it work without AI? And without internet?</strong></summary>

Without AI, yes: joBot uses rules and keywords.
Without internet, new jobs don't arrive. But the dashboard keeps working, and so does the local model.
</details>

<details>
<summary><strong>Does joBot apply on its own?</strong></summary>

No. It prepares the application and helps fill in forms, but you are always the one who reviews and sends.
</details>

<details>
<summary><strong>Can my LinkedIn account be restricted?</strong></summary>

It can. The risk exists, and it can't be reduced to zero.
joBot reduces the risk: you do the login with your own hands, it only reads, it visits a few times a day, it goes slowly and it never bypasses CAPTCHA.
Each site with login has a switch. You decide whether to turn it on.
</details>

<details>
<summary><strong>What if a CAPTCHA shows up?</strong></summary>

The dashboard shows a red warning and the computer shows a notification. The browser window stays still on the page, waiting for you to solve it.
The other sources continue normally. joBot never tries to get past the CAPTCHA on its own.
</details>

<details>
<summary><strong>Does my data go to any server?</strong></summary>

There is no joBot server. Your data stays on your computer.
It only goes to the services you turn on: Anthropic (if you use Claude), Google (if you turn on Gmail) and Telegram (if you turn on the daily summary). It may also go to Jev (if you choose that option in email classification) and to RunPod (only in the phase 6 training). With manual AI, it goes to the chat AI where you paste it.
</details>

<details>
<summary><strong>Will it run on my computer?</strong></summary>

The idea is to run on ordinary computers, with 8 to 16 GB of RAM and no dedicated graphics card, with Linux, Windows or macOS.
</details>
