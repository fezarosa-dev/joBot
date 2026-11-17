# Changelog

[Português](CHANGELOG.md) · **English**

All notable changes to the project are recorded in this file.

The format follows [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
- New filters in the job list: country, how many days ago the job was posted and, under "More filters", salary, city, company and words the job must not have.
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
