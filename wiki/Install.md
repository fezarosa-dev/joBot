🌐 [Português](Instalar) · **English**

# 📦 Install

**How to install joBot with the installer, on Windows, Linux and Mac, step by step.**

---

> [!NOTE]
> The installer arrives in version 0.4.0. To install from the code (git and uv), see the [README](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#requirements-and-installation).

## 1. Download the file for your system

On the [latest version page](https://github.com/fezarosa-dev/joBot/releases/latest), under "Assets":

| System | Download |
|---|---|
| Windows 10 or 11 (64-bit) | the file ending in `-setup.exe` |
| Linux (any 64-bit distro) | the one ending in `.AppImage` |
| Debian and Ubuntu | the one ending in `.deb` |
| Fedora | the one ending in `.rpm` (experimental: not tested in CI yet) |
| Mac with Apple Silicon (M1 or newer) | the one ending in `_aarch64.dmg` (experimental) |
| Mac with Intel | the one ending in `_x64.dmg` (experimental) |

Each file is about 100 to 200 MB (the Windows one about 120 MB, the Mac ones about 105 MB, the `.deb` and the `.rpm` about 125 MB and the AppImage about 200 MB), because it already brings Python 3.14, the libraries and joBot. The browser for sites with login is not in the file: it comes from the internet, if you tick it during installation. The other files on the page (`jobot-atualizacao-...zip`, the wheel and `restricoes.txt`) are for updates and for developers: you do not need them.

**Want to check the file?** Also download `SHA256SUMS` to the same folder. On Linux and on the Mac, run `sha256sum --ignore-missing -c SHA256SUMS` (on the Mac, `shasum -a 256 --ignore-missing -c SHA256SUMS`); on Windows, `Get-FileHash` in PowerShell and compare with the file's line. This checks that the download did not arrive broken; since `SHA256SUMS` comes from the same release, it does not prove where the file came from (that is left to code signing, when it comes).

## 2. Open it

- **Windows:** double-click the `-setup.exe`. If "Windows protected your PC" appears, click **More info** and then **Run anyway**. The warning appears because the installer has no seal (code signing) yet. It installs for your user only, without an administrator password.
- **Linux, AppImage:** mark the file as executable (`chmod +x` on the file, or Properties, Permissions) and open it. If it complains about FUSE, prefer the `.deb` or the `.rpm`. If you want the AppImage anyway, run `TMPDIR=~/.cache ./joBot_<version>_amd64.AppImage --appimage-extract-and-run`: it unpacks into the `~/.cache` folder, on disk, and not into `/tmp`, which many Linux systems keep in memory. When you close it, the folder is deleted.
- **Linux, `.deb` or `.rpm`:** `sudo apt install ./` or `sudo dnf install ./` followed by the file name. Then open joBot from the applications menu.
- **Mac:** open the `.dmg` and drag joBot to Applications. The first time, a message says Apple could not verify joBot: close it, open System Settings › Privacy & Security, scroll down to the message about joBot and click **Open Anyway**, confirming with your password.

## 3. The install screen

On first launch, the joBot window shows the install screen.

1. **Tools:** joBot and Python 3.14 come ticked and locked. Only two items come from the internet: the browser for sites with login (LinkedIn and others you sign in to), which comes ticked, and the AI **Local model**, which comes unticked. joBot downloads the browser through Playwright, from Playwright's servers (about 210 MB), and the Local model from GitHub (`llama-server` and Laya, about 1.3 GB, from the llama.cpp and joBot releases), with its sha256 checked; the original Qwen3.5, from Hugging Face, only if you switch later in Settings › Tools. If you untick the browser, the sites with login stay off until you download it in Settings › Tools; the model can be downloaded there later too.
2. **Installing:** nothing else is downloaded besides the browser and the Local model, if ticked. joBot checks the sha256 of every file and every library; if any does not match, nothing is installed and the screen asks you to download the installer again. The browser is left out of this check: Playwright does not publish its sha256, and the download comes over HTTPS. Without internet, the installation works the same without the browser: if its download fails, the screen offers to go on without it. The Local model is downloaded after joBot is already installed: if its download fails, joBot stays installed and the screen says why.
3. **Done:** the window becomes the joBot control. Press **Start** and then **Open joBot**: the dashboard opens in your default browser, with the first-run questions.

If the installation fails midway, what it did is undone, and "Try again" starts from scratch.

## 4. After installing

- **The joBot window is a control.** It shows whether joBot is **Running** or **Stopped**, the dashboard address (with **Copy**) and the **Start**, **Stop** and **Open joBot** buttons. Open joBot, which only shows while joBot is running, opens the dashboard in your default browser. When the window opens, it only shows the state: it does not start or open anything by itself.
- **Closing the window** while joBot is running asks **Keep joBot running?**. **Keep running** closes only the window, and the dashboard stays on in your browser until you open the window and press **Stop**; **Turn off** stops joBot and closes. With joBot stopped, it closes right away. The background service (Settings › Background) is for joBot to start by itself when the computer starts. From the dashboard, **Quit joBot**, in Settings › General, also stops everything.
- **Updating:** when a new version comes out, the dashboard tells you in a banner; press **Update now**. The new version is built next to the current one and only goes in if it opens. The update replaces only joBot, not the window. When the window has a new version too, it shows **Download the new window**, which opens the version page: download and open the installer again, and your data stays.
- **Your data** lives in `~/.local/share/jobot` on Linux, `%LOCALAPPDATA%\joBot` on Windows and `~/Library/Application Support/joBot` on the Mac.

## 5. Uninstall

Uninstalling never deletes your data. The browser stays too, in the Playwright folder; to remove it, press **Remove** in Settings › Tools first. The local model stays too, in the `ferramentas` folder inside the data folder, and takes up to about 2.8 GB (the larger model alone is 2.7 GB); to remove it, press **Remove** on the model card, on the same screen, before uninstalling, or delete the `ferramentas` folder afterwards.

- **Windows:** Settings › Apps, joBot, **Uninstall**. The uninstaller turns off the background service, quits joBot and deletes the `%LOCALAPPDATA%\joBot\app` folder.
- **Linux:** turn off the background service and use **Quit joBot**; remove the package (`sudo apt remove` or `sudo dnf remove`) or delete the `.AppImage`; delete the `~/.local/share/jobot-app` folder by hand.
- **Mac:** turn off the background service and use **Quit joBot**; drag joBot to the Trash and delete the `~/Library/Application Support/joBot/app` folder by hand.

## 🛠️ If something goes wrong

- **"A file in the installer is not the expected one":** the download came broken. Download the installer again.
- **Open joBot did not open the browser:** the window shows the reason. Press **Copy** and paste the address into your browser. On Linux, joBot opens the browser with `xdg-open`, from the `xdg-utils` package.
- **Windows without WebView2:** Windows 11 and an up-to-date Windows 10 already have WebView2, which the window needs. Without it, the installer downloads nothing: it warns you, with Microsoft's official link (https://developer.microsoft.com/microsoft-edge/webview2/), and cancels. Install WebView2 from that link and open the installer again.
- **Another question:** see the [frequently asked questions](Frequently-asked-questions) or [ask a question](Ask-a-question).
