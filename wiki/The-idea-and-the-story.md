🌐 [Português](A-ideia-e-a-historia) · **English**

# 💡 The idea and the story

**Why joBot exists, what it wants to be and what it will never do.**

---

## 🌱 How it all started

joBot was born to help young university students find their first job.
Then the idea expanded to everyone. Today joBot is designed for every kind of job and every field: full-time employment (CLT), contractor (PJ), internship, trainee, temporary, apprentice, research and scholarships, programs and summer schools, public exams and notices.

### Timeline

| When | What happened |
|---|---|
| 2026-11-13 | The main decisions were made in 9 rounds of questions and answers and recorded in short documents, the ADRs (ADR 0001 to 0017). |
| 2026-11-14 | The project was redesigned to be maintained by the community (ADR 0018), got this wiki (ADR 0019) and decided to accept only donations as support (ADR 0020). |
| Now | Phase 1 of 8 (the base) is complete: joBot 0.1.0 already works. See the [roadmap](Roadmap). |

## 😩 The problem

Looking for a job today is tiring. You have to open many sites, repeat the same filters and hope you don't miss a deadline.

## 💡 The idea

A personal dashboard that gathers and organizes jobs for you.

- 🖥️ **It runs on your computer.** One installation serves one person, who can have several saved searches.
- 🔒 **Privacy first.** There is no joBot server. Your data stays with you.
- 🧠 **Optional AI.** Without AI, joBot works with rules and keywords. With AI, it calculates how well a job matches your profile and helps prepare applications, but it only uses what is in your profile.
- 🎚️ **Everything can be turned off.** Every feature and every source has an on/off switch.

## ✅ What it will do

- 🔎 **Search** for jobs in dozens of sources: public sites, company job boards and, if you want, sites that require login.
- 🧹 **Clean up**: remove duplicate jobs, read the salary and tag the field, level, work mode, region and contract type.
- 🎯 **Rank**: show how well each job matches you (● good, ◐ medium, ○ weak) and explain why.
- 🗂️ **Organize**: each job has a status, from "new" to "offer".
- ✍️ **Prepare the application**: cover letter, a résumé summary adjusted to the job and a list of what you have and what is missing, always in the job's language.
- 🧩 **Help with forms**: a browser extension suggests answers, and you confirm.
- 📬 **Read Gmail** (optional): bring in jobs from alert emails and suggest status changes when a recruiter replies.

## 🚫 What it does not do

> [!IMPORTANT]
> - **It does not mass-apply.** There is no "apply to 200 jobs with one click".
> - **It does not send anything on its own.** You are always the one who sends the application.
> - **It does not type your password.** On sites with login, you sign in with your own hands.
> - **It does not bypass CAPTCHA.** If one shows up, it stops and warns you.
> - **It does not send telemetry.** joBot does not send usage data to anyone.
> - **It does not invent experience.** The AI only uses what is in your profile.

## 🧭 Principles

| | Principle | What it means |
|:---:|---|---|
| 🖥️ | **Runs on your computer** | The dashboard only works on your own computer (address 127.0.0.1). The data stays in a local database. |
| 🤝 | **Polite collection** | The robot identifies itself, waits between one request and the next and waits longer when the site asks for calm. It never bypasses login, CAPTCHA or anti-robot blocks. |
| 📖 | **Open source (MIT)** | Anyone can read, use and improve the code, under the MIT license. |
| 🧼 | **Clean room** | Public ideas and facts can be used. Third-party code and test data are never copied. |
| 🌍 | **Maintained by the community** | Job sites change without notice. Each source has its own collector (the code that reads the jobs from a source), with its own examples and tests, so anyone can fix it. |
| 🎁 | **Free** | joBot is free. The project only accepts donations, with no ads, no affiliate links and no tracking. See [Support the project](Support-the-project). |

## 🔗 Learn more

- [How it works](How-it-works): the path of a job to the dashboard.
- [Decisions](Decisions): every project decision in one line.
- [README](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#what-is-jobot): the full description.
