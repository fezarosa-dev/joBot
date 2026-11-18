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

1. **Tools:** joBot and Python 3.14 come ticked and locked. The browser for sites with login (LinkedIn and others you sign in to) comes ticked and is the only thing that comes from the internet: joBot downloads it through Playwright, from Playwright's servers (about 210 MB). If you untick it, the sites with login stay off until you download the browser in Settings › Tools.
2. **Installing:** nothing is downloaded, except the browser, if ticked. joBot checks the sha256 of every file and every library; if any does not match, nothing is installed and the screen asks you to download the installer again. The browser is left out of this check: Playwright does not publish its sha256, and the download comes over HTTPS. Without internet, the installation works the same without the browser: if its download fails, the screen offers to go on without it.
3. **Done:** the window opens the dashboard, with the first-run questions.

If the installation fails midway, what it did is undone, and "Try again" starts from scratch.

## 4. After installing

- **Closing the window** closes only the window. With the background service on (Settings › Background), the searches go on; to stop everything, use **Quit joBot** in Settings › General.
- **Updating:** when a new version comes out, the dashboard tells you in a banner; press **Update now**. The new version is built next to the current one and only goes in if it opens. If the window has a new version too, **Download the new window** opens the version page: download and open the installer again, and your data stays.
- **Your data** lives in `~/.local/share/jobot` on Linux, `%LOCALAPPDATA%\joBot` on Windows and `~/Library/Application Support/joBot` on the Mac.

## 5. Uninstall

Uninstalling never deletes your data. The browser stays too, in the Playwright folder; to remove it, press **Remove** in Settings › Tools first.

- **Windows:** Settings › Apps, joBot, **Uninstall**. The uninstaller turns off the background service, quits joBot and deletes the `%LOCALAPPDATA%\joBot\app` folder.
- **Linux:** turn off the background service and use **Quit joBot**; remove the package (`sudo apt remove` or `sudo dnf remove`) or delete the `.AppImage`; delete the `~/.local/share/jobot-app` folder by hand.
- **Mac:** turn off the background service and use **Quit joBot**; drag joBot to the Trash and delete the `~/Library/Application Support/joBot/app` folder by hand.

## 🛠️ If something goes wrong

- **"A file in the installer is not the expected one":** the download came broken. Download the installer again.
- **The window did not open and the dashboard showed up in the browser:** the system has an old version of the window component (common on older Linux). joBot works the same in the browser.
- **Windows without WebView2:** Windows 11 and an up-to-date Windows 10 already have WebView2, which the window needs. Without it, the installer downloads nothing: it warns you, with Microsoft's official link (https://developer.microsoft.com/microsoft-edge/webview2/), and cancels. Install WebView2 from that link and open the installer again.
- **Another question:** see the [frequently asked questions](Frequently-asked-questions) or [ask a question](Ask-a-question).
