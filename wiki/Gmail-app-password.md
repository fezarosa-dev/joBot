🌐 [Português](Gmail-senha-de-app) · **English**

# 🔑 Gmail with an app password

**How to let joBot read your Gmail, step by step, without creating a Google project.**

---

> [!NOTE]
> The Gmail card is in Settings, Accounts. Reading the alert emails and the recruiters' replies stays in phase 6; for now the card only checks the sign-in.

## 🤔 What it is and why joBot uses it

An **app password** is a 16-letter password that Google creates just for one program. It is not your account password. You paste it into joBot, and it uses it to sign in to your inbox over IMAP (the standard way email programs read messages).

This way you do not need to create a Google Cloud project, or wait for Google to approve anything. It takes a few minutes.

## ✅ Before you start

- You need a personal Google account (Gmail). For now joBot only works with Gmail.
- App passwords are **not available** for work or school accounts (managed Google Workspace), for people who use Google's Advanced Protection, and for people whose 2-Step Verification uses only security keys. In those cases Gmail is unavailable for now. The path of your own Google Cloud project is a future task.
- Since January 2025, IMAP is always on for personal accounts. There is nothing to turn on.

## 1️⃣ Turn on 2-Step Verification

1. Open the [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) page of your Google account.
2. If it is already on, skip to step 2. If not, follow Google's screens to turn it on.

Google help: [2-Step Verification](https://support.google.com/accounts/answer/185839).

## 2️⃣ Create the app password

1. Open the [app passwords](https://myaccount.google.com/apppasswords) page.
2. Give the password a name, for example `joBot`.
3. Click create. Google shows 16 letters, in 4 groups separated by spaces.
4. Copy the 16 letters. **Google shows the password only once.** If you close the window without copying it, delete that password and create another.

Google help: [app passwords](https://support.google.com/accounts/answer/185833).

## 3️⃣ Paste it into joBot

1. In the joBot dashboard, open Settings, Accounts, and go to the Gmail card.
2. Type your Gmail address and paste the app password. You can paste it with the spaces: joBot removes them.
3. Click **Check now**. joBot signs in to the inbox read-only, without changing anything.

The card shows the state:

- **Signed in**: it worked.
- **Needs to sign in again**: Google refused the password. Create another app password and paste it again.
- **Could not check**: it was not possible to reach Google, for example with no internet. Try again in a moment.

## 🔄 I changed my Google account password. Now what?

Google deletes all app passwords when you change the account password. The Gmail card changes to **Needs to sign in again**. Do step 2 again and paste the new app password.

## 🗑️ How to delete the app password

Open the [app passwords](https://myaccount.google.com/apppasswords) page again and delete the password named `joBot`. joBot loses access right away.

## 🔒 What joBot does with the password

- Keeps the address and the app password only on your computer, in the system password vault. Without a vault, they go to a file that only your user can read, and the dashboard warns you.
- Uses the password only to sign in to the inbox and read. joBot only opens the mailbox read-only. Keep in mind that the app password itself gives full access to your email (read, delete and send) to whoever has it; only joBot limits itself to reading.
- Never types your Google account password.

Want to know why it was chosen? See [ADR 0024](https://github.com/fezarosa-dev/joBot/blob/main/docs/decisions/0024-gmail-por-senha-de-app.md) (Portuguese) and the [frequently asked questions](Frequently-asked-questions).
