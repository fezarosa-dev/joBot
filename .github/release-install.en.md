## How to install

Download **just one file**: the one for your system, in the **Assets** list below.

| Your system | Download | How to install |
|---|---|---|
| Windows 10 or 11 | `joBot_{versao}_x64-setup.exe` | Double-click it. If "Windows protected your PC" shows up, click **More info** and **Run anyway**. It does not ask for an administrator password. |
| Ubuntu, Debian, Mint | `joBot_{versao}_amd64.deb` | In a terminal, in the download folder: `sudo apt install ./joBot_{versao}_amd64.deb` |
| Fedora | `joBot-{versao}-1.x86_64.rpm` | In a terminal, in the download folder: `sudo dnf install ./joBot-{versao}-1.x86_64.rpm` |
| Other Linux | `joBot_{versao}_amd64.AppImage` | Make it executable (`chmod +x joBot_{versao}_amd64.AppImage`, or Properties › Permissions) and open it. |
| Mac with Apple Silicon (M1 or newer) | `joBot_{versao}_aarch64.dmg` | Open the `.dmg` and drag joBot to Applications. The first time, if Apple warns you, open System Settings › Privacy & Security and click **Open Anyway**. |
| Mac with Intel | `joBot_{versao}_x64.dmg` | Same as the Mac with Apple Silicon. |

The first time, the joBot window installs the rest (the browser for sites with a login and, if you tick it, the local AI model) and becomes the control window: press **Start** and then **Open joBot**. Requirements and step by step: [README](https://github.com/fezarosa-dev/joBot/blob/main/README.en.md#requirements-and-installation).

**You do not need the other files:**

- `jobot-atualizacao-{versao}-….zip`: used by joBot's own **Update now** button, one per system.
- `jobot-{versao}-py3-none-any.whl` and `restricoes.txt`: to install with Python (`pip` or `uv`), advanced use.
- `SHA256SUMS`: checks the download is complete: `sha256sum -c SHA256SUMS --ignore-missing`.
- `Source code`: the code of this version, which GitHub adds on its own.

