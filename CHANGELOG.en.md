# Changelog

[Português](CHANGELOG.md) · **English**

All notable changes to the project are recorded in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] - 2026-11-24

AI arrives, optional and off by default: it lists the skills each job asks for, and joBot compares them with the ones in your profile. It runs on the local model, free and without internet once downloaded, or on a service with your key.

### Added

- Settings › AI: turns on the Matching task and chooses where it runs (the local model, the Anthropic API, OpenAI, Google Gemini or an OpenAI-compatible address, such as Ollama, LM Studio and OpenRouter) and with which model. The Turn AI off, All offline and All Claude shortcuts set everything at once. Everything comes off.
- With Matching on and at least one skill in the profile, after each search the AI reads up to 20 jobs not yet read that already match a search, newest first, and lists what each one asks for (switching the service or the model makes it read everything again); each item has to be written in the job. The AI does not see your profile and does not give a score: joBot compares the list with your skills, shows in the job details the ones you have and the ones you are missing, and skills now count in the match.
- Settings › Profile: your skills, one per line, and the Delete profile button.
- Settings › Services: cards for the Anthropic, OpenAI and Google Gemini keys and for the address of an OpenAI-compatible service. The keys stay in the system password vault, and saving a key turns nothing on.
- Test when you turn it on: turning a task on or switching the service, the key or the address sends a short request, with a sample job. If it fails, the task stays off and the AI tab says why.
- Cost in plain sight: paid services show as "billed per use", turning Matching on with one of them asks for confirmation, and joBot makes at most 200 requests a day to each outside service (not counting the test when you turn it on), with the day's count in the AI tab. The Anthropic API, OpenAI and Gemini come marked "experimental, not yet proven": they were only tested against a fake service.
- Settings › Tools: the local model card downloads llama.cpp's `llama-server` (from GitHub) and a Qwen3.5 2B or 4B (from Hugging Face), with the sha256 checked, and picks the model by the computer's memory (1.3 GB to 2.7 GB). The same card has the download bar, the license and origin of each file and the buttons to switch models, Update when a new version comes out and Remove.
- The installer has the Local model box in the Tools step, unticked. Ticked, it downloads the model after installing joBot; if the download fails, joBot stays installed and the screen says to download it later in Settings › Tools.
- For contributors: the scripts in `scripts/treino_laya/` build the set of public jobs, label, train and export Laya, a fine-tune of Qwen3.5 2B for jobs, and calculate the training cost. Laya does not ship in this version yet: it comes in a later version, after the training, if it scores better than the original model.

### Changed

- The Tools tab in Settings always shows, even with no site with login turned on.
- The network request list in Privacy and in the README now names the AI services and the local model downloads (GitHub and Hugging Face, with their CDNs), with the condition of each one. The README gets the table of what works without internet, and the offline package no longer lists audio, which is left for phase 6.

## [0.4.1] - 2026-11-24

**If you have the 0.4.0 window:** install the 0.4.1 window before using Update now in the dashboard. With only the dashboard updated, the 0.4.0 window has no close buttons and no drag area (close it with Alt+F4) and shows the notice to download the new window.

0.4.1 fixes what 0.4.0 broke on Linux: the joBot window becomes a small control, and the dashboard opens in your browser.

### Added

- ADR 0026 (proposed): phase 4 AI. The AI will arrive in two versions, 0.5.0 and 0.6.0, off by default; the local model will be downloaded from the official source, when the person asks, and the AI will only list what the job asks for, without giving a score. The roadmap now shows phase 4 being built.
- ADR 0027: the shell only controls. joBot's window becomes a control with Start, Stop and Open joBot, and the dashboard opens in the person's default browser. It replaces the "Shell" part of ADR 0025.
- The base of the phase 4 AI already ships in this version, off and with no screen to turn it on: the database migration that stores the profile, the skills the AI extracts from each job and the match level, the pydantic dependency, the clients for the Anthropic API and for OpenAI-compatible services, and `jobot ferramentas baixar ia-local`, which downloads llama-server and a model with a checked sha256. None of it runs unless the person turns it on.
- The dashboard screen tests run in Chromium, Firefox and WebKit, because the default browser can be any of them. Before each version, CI installs the joBot window on a virtual desktop, installs joBot through it, starts, opens and stops it from the control and keeps the screenshots.

### Changed

- The joBot window becomes a small control. It shows whether joBot is Running or Stopped and the dashboard address, with a Copy button, and has the Start, Stop and Open joBot buttons. Open joBot opens the dashboard in your default browser (Firefox, Chrome, Edge, Safari or another). When it opens, the window only shows the state: it does not start or open anything by itself. The install screen stays on first launch and, at the end, leads to the control.
- Closing the window while joBot is running asks "Keep joBot running?". Keep running closes only the window, and the dashboard stays on in your browser until you press Stop; Turn off stops joBot and closes. With joBot stopped, the window closes right away. The background service is now only for joBot to start by itself when the computer starts.
- The "Download the new window" button leaves the dashboard banner and moves to the control, which shows it when the running joBot is newer than the window ("Update now" replaces only joBot). If you still have the 0.4.0 window and update only joBot, you see a banner inside it that tells you to install the new window.
- The dashboard looks lighter: the sidebar and the top bar have a solid background instead of blurred glass, and glass stays only in menus and dialogs.
- The progress bar moves smoothly, in the dashboard and in the installer: it starts fast and slows down gradually, without jumping or stopping abruptly between steps.
- The weekly source watcher re-enables itself on every run, so GitHub does not turn it off after 60 days without activity in the repository.

### Removed

- The dashboard no longer runs inside the joBot window. The close, minimize and maximize buttons that joBot drew and the area to drag the window are gone.

### Fixed

- On Linux, the 0.4.0 window made the computer slow and showed the dashboard cut off and out of place. The dashboard now runs in your browser.
- The AppImage no longer leaves copies of about 400 MB in `/tmp`, which many Linux systems keep in memory: when it runs unpacked (without FUSE), the folder is deleted on close, even after a forced exit, and without deleting the one of another launch still in use.
- joBot left running by the window and the browser opened by Open joBot are no longer tied to the AppImage after the window closes: they do not inherit its folder, its open files or the settings from inside it, such as the forced light theme in the browser.
- In Firefox and Safari, the job context menu opens with the mouse.
- In Safari, going back to a dashboard page no longer shows the false notice that the internet dropped.
- In the dashboard: the detail next to the list shows the AI skills, like the job page; the Overview no longer says "Searching now." during company discovery, page reading or login reading; in high contrast, the Jobs and Settings buttons and the selected chip stay visible; the 2Captcha card no longer says browsing with a login does not exist yet; and a broken language, theme or text size value in the database no longer brings the dashboard down. The network request list in Privacy now names Gmail.
- On Windows and Mac, Update now restarts joBot the right way: it redoes each system's automatic start and brings the dashboard back up. On Windows, the dashboard comes back even when the startup task is not rewritten, and the update no longer flashes black terminal windows.
- On Windows and Mac, login reading finds the screen and opens the browser window. On Windows, the browser for that reading opens its profile and gets the system folders it needs to reach the internet.
- On Windows, Settings, Services saves and reads the 2Captcha key: the vault could not open its file.
- In the sources: RemoteOK no longer stores, in the job description, the IP address of whoever ran the search; a huge salary on RemoteOK or Super Estágios no longer brings the search down; the date of Oracle HCM and Workday jobs that comes without a time no longer shows one day early; SmartRecruiters, with no country in the search, asks for jobs in Brazil; and an Abler or Super Estágios sitemap that changed format marks the source as failed instead of bringing zero jobs without notice.
- A broken currency rate in the database no longer shows on screen or goes into the salary conversion.

## [0.4.0] - 2026-11-17

Phase 3 arrives: joBot gets a window of its own and an installer for Windows, Linux and Mac, which installs everything without internet, except the optional browser.

### Added

- Installer for Windows (`-setup.exe`), Linux (AppImage, `.deb` and `.rpm`, the latter experimental) and Mac (`.dmg`, experimental). Each one is about 100 to 200 MB, because it already brings Python 3.14, the libraries and joBot: the installation works without internet and checks the sha256 of every file. The browser for sites with login is not in the installer: if ticked, it comes from the internet through Playwright, without a checked sha256 (Playwright does not publish it). On a Windows without WebView2, the installer warns you with Microsoft's official link and cancels, without downloading anything. No seal (code signing) for now: the README explains how to open it on Windows and on the Mac.
- A window of joBot's own, with an icon, around the same dashboard, which still stays only on your computer. On Windows and Linux the close, minimize and maximize buttons are drawn by joBot; on the Mac, they are the system's. Closing the window closes only the window: with the background service on, the searches go on.
- Install screen on the window's first launch: joBot and Python come locked, the browser comes ticked and can be unticked (it downloads later in Settings › Tools), and the bar shows each step. If something fails, what was done is undone.
- joBot now runs on Windows and on the Mac, each with its own data folder.
- Background service on Windows (Task Scheduler) and on the Mac (LaunchAgent, experimental), besides systemd on Linux.
- "Update now" button in the new version banner and in Settings › General. With the installer, the new version is built next to the current one, checked, and only goes in if it opens; otherwise nothing changes. When the window has a new version too, the "Download the new window" button opens the version page.
- "Quit joBot" button in Settings › General and in the command palette, which stops the server and the searches.
- With the installer, the browser for sites with login downloads through Playwright, during installation (if ticked) or on the Tools screen, and the Tools screen warns when it is outdated after an update.
- Uninstalling on Windows turns off the background service and quits joBot, and never deletes the data folder.
- ADR 0025: desktop app and installer. The window, the install screen, the complete offline installer (except the optional browser) and updating from the dashboard.

### Changed

- The new version banner no longer tells you to open the terminal: it brings the "Update now" button.
- The README explains installing with the installer, the Windows and Mac warnings, where the data lives on each system and how to uninstall; the wiki gets the Install page.

## [0.3.0] - 2026-11-16

Phase 2 arrives: the browser with login and LinkedIn, the first site with login. The dashboard gets a new look, the Accounts tab (with the Gmail card), the Overview and the application queue, and the roadmap now puts the Installer in phase 3.

### Added

- LinkedIn, the first site with login. The reader comes off: you turn it on in Settings, Accounts. It searches for each job title in your searches, with the city and remote, and reads only the last week, sorted by relevance. Because the list is not complete, a LinkedIn job only closes after 30 days without being seen, and reopens if it comes back.
- The Accounts tab shows whether joBot is still signed in to each site, checks on demand and warns when the session ends.
- Gmail card in the Accounts tab: paste an app password, and joBot checks the sign-in read-only. Reading emails comes in phase 6.
- The Tools screen in Settings, to download and remove the browser for sites with login (about 210 MB), with no terminal.
- The optional "Sites with login" step in the first-run assistant: turn on the sites, check the browser and download it, before you see the jobs.
- Login in a regular browser window, with no automation: you sign in however you like (Google, email and password) and close the window. joBot checks the session by itself and never types the password.
- ADR 0023: everything through the dashboard. External tools, updating and quitting get a button, no terminal needed.
- Guide "How to add a new site" (`docs/site-novo.en.md`), with a collector template for a public site and a reader template for a site with login, and a CI guard that checks each site's test, example and name.
- The Overview, a new item in the sidebar: the day on one screen, with what closes soon, the applications and the search, with shortcuts to the jobs and the sources.
- The job timeline, with the date of each step (found, saved, application opened, applied), and the "since" in the Applied tab.
- The "Did you apply?" question after you open a job's application link, with "Yes, I Applied", "Not Yet" and Undo.
- Application by email: when the description has an address, the "Apply by Email" button opens your email app with the job title. joBot sends nothing.
- ADR 0024: Gmail will be read over IMAP with an app password pasted into the dashboard (the card is in Settings, Accounts; reading the emails, in phase 6). The wiki gets the step-by-step guide.
- A window of its own for the dashboard: if the computer has Chrome, Edge or Chromium, `jobot` opens the dashboard with no tabs or address bar, like an app; without them, it opens in a tab.
- Undo and Redo: hiding a job, discarding a suggestion and removing a company happen right away, with an Undo bar (`⌘Z`, `Ctrl+Z` outside the Mac) and a Redo. Deleting a search, removing a site and forgetting logins ask for confirmation in an alert.
- Command palette (`⌘K`, `Ctrl+K` outside the Mac): goes to any screen and changes theme, language and text size, with no mouse.
- Keyboard shortcuts: `/` for search, arrows, `J`, `K`, `Home` and `End` in the list, `⌘,` for Settings, `⌘?` for help and the menu key for the job menu. The "Keyboard shortcuts" wiki page lists them all.
- Text size (Default, Large or Larger) in Settings, General.
- Search progress with steps: the top shows which step joBot is on (for example, "Reading Greenhouse · 13 of 20 queries") and "Show Details".

### Changed

- The job list and the Overview open faster with many jobs: the tabs are counted in a single pass, and the Overview counts only what it shows.
- New roadmap: version 0.3.0 came out after phase 2 ("Overview" screen and complete application queue); phase 3 becomes the Installer and the later phases move up one number, up to phase 9 (release).
- New look for the dashboard, in the style of a Mac app: sidebar with Jobs and Where to Look, job list with the detail beside it, translucent windows and alerts, and the English title of the correction in Title Case ("Something Wrong with This Job?").

### Fixed

- Focus returns to the right chip after changing the filter, even when two values differ only by a space and an `_`.

## [0.2.1] - 2026-11-15

### Changed

- The job list opens without waiting for the filter counts: the chips arrive right after the list. Without JavaScript the chips do not appear.
- The source chip is faster on large databases, thanks to a new index (migration 0006).
- The "Saved." notice disappears by itself after 5 seconds on every Settings screen and does not come back when you refresh the page.

## [0.2.0] - 2026-11-15

### Added

- ADR 0022: CAPTCHA solved by the service the person turns on (2Captcha), only for logged-in browsing.
- Services tab in Settings: save the 2Captcha key, test the key and see the balance. Use comes with logged-in browsing.
- New filters in the job list: country, how many days ago the job was posted and, under "More Filters", salary, city, company and words the job must not have.
- "My country", asked on the first run and kept in Settings, and the currency of converted values, which you choose (your country's by default).

### Changed

- A salary in a foreign currency is shown converted on its own line, below the original value.

## [0.1.1] - 2026-11-15

Clearer errors and fewer surprises. Nothing changes in what joBot searches.

### Added

- A notice on screen when a click fails or the dashboard does not respond. It does not keep trying after the dashboard is closed.
- The screen and `jobot buscar` say why the search stopped.
- A hint in the searches screen: write the variations of a job title, one per line.

### Changed

- The new-version notice now comes on by default. Anyone who already chose keeps the choice.
- Ctrl+C in the terminal exits with code 130.
- The systemctl output goes only to `jobot.log`, not to the screen.

### Fixed

- An error in the dashboard shows a friendly page, instead of the bare 500 error. The 404 and 422 errors also get a message.
- Step 2 of the first run no longer gets stuck: if the background service fails, it finishes with a notice.
- The terminal no longer shows a traceback: the technical error goes to `jobot.log`.

## [0.1.0] - 2026-11-14

Phase 1: the foundation of joBot. You can already install and use it.

### Added

- Dashboard in the browser, at `http://127.0.0.1:47615`, with Jobs, Searches, Sources, Companies, Suggested, Sites and Settings.
- Job search in dozens of public sources, every 3 hours or on demand, with the "Search now" button.
- Job cleanup: removes duplicates and reads salary, field, level, work mode, region and contract type.
- Match score with your search (good, medium, weak), by rules and with the reasons. No AI.
- A status for each job, from "new" to "offer", and the tabs Highlights, All, New, Closing soon, Saved, Applied, Programs and Hidden.
- Tracking of program pages, such as trainee and summer school, in the Sites screen.
- Own company list and weekly discovery of new job boards, which go to Suggested until you approve them.
- Commands `jobot abrir`, `jobot sair`, `jobot serve`, `jobot buscar`, `jobot segundo-plano`, `jobot atualizar` and `jobot avaliar-rotulos`.
- Background service on Linux, through the user's systemd, including from a distrobox container.
- New-version notice, off by default. When on, it only asks `api.github.com` for the newest version, and the request carries the fixed user agent and the IP.
- Eureca, Abler and Gupy, each with its own on/off switch. All come on by default; Eureca's terms ask for prior consent, and anyone who prefers to respect that can turn Eureca off in Settings.
- Dashboard in Portuguese and English, with light and dark themes.
- In the search progress bar, the list of the sources that are still running.
- A "Saved." notice after saving in Settings.
- `jobot abrir` prints the dashboard address and how to quit in the terminal; the search progress bar shows the details phase after collection.
- A country restriction notice on the remote jobs from Himalayas, Jobicy and Remotive.
- Project decisions (ADRs 0001 to 0021) and `duvidas.md`.
- README with badges, diagram, tables and a FAQ, and the English version.
- Star history chart in the README.
- Preview image for social networks (`docs/imagens/previa-social.png`).
- MIT license, Code of Conduct, security policy, contributing guide, support, issue and PR templates, and CODEOWNERS, also in English.
- `CITATION.cff`, `.editorconfig` and `.gitattributes`.

### Changed

- Code of Conduct reports go to the project email.
- The README is no longer only a plan: it describes the phase 1 installation.
- The label rules (field, level, work mode, contract, country and state) were tuned and measured on a set of jobs checked by hand.
- Jobs from Brazil-only sites now come out with the country Brazil.
- The country restriction notice names the countries, such as "Only for residents of: United States and Canada".

### Fixed

- The weekly Common Crawl discovery no longer fails because of huge blocks from other sites, which joBot never downloads.
- Greenhouse accepts very large job boards, such as Stripe's.
- The schedule only starts searching after the first-run wizard is finished.
- In Sources, a source that hit its limit shows the last round it actually ran.
- A foreign country in the searches form no longer turns into a Brazilian state.
- A city with a country's name, such as "Franca, São Paulo", no longer turns into the country.
- In Sources, the "No change" card shows the jobs from the last round that read them and the right next search.
- A newly added tracked page is read on the next scheduler round, without waiting 24 hours.
