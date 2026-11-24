🌐 **Português** · [English](Install)

# 📦 Instalar

**Como instalar o joBot pelo instalador, em Windows, Linux e Mac, passo a passo.**

---

> [!NOTE]
> O instalador chega na versão 0.4.0. Para instalar pelo código (git e uv), veja o [README](https://github.com/fezarosa-dev/joBot#requisitos-e-instalacao).

## 1. Baixe o arquivo do seu sistema

Na [página da versão mais nova](https://github.com/fezarosa-dev/joBot/releases/latest), em "Assets":

| Sistema | Baixe |
|---|---|
| Windows 10 ou 11 (64 bits) | o arquivo que termina em `-setup.exe` |
| Linux (qualquer distro de 64 bits) | o que termina em `.AppImage` |
| Debian e Ubuntu | o que termina em `.deb` |
| Fedora | o que termina em `.rpm` (experimental: ainda não testado no CI) |
| Mac com Apple Silicon (M1 ou mais novo) | o que termina em `_aarch64.dmg` (experimental) |
| Mac com Intel | o que termina em `_x64.dmg` (experimental) |

Cada arquivo tem de cerca de 100 a 200 MB (o do Windows uns 120 MB, os do Mac uns 105 MB, o `.deb` e o `.rpm` uns 125 MB e o AppImage uns 200 MB), porque já traz o Python 3.14, as bibliotecas e o joBot. O navegador dos sites com login não vem no arquivo: ele vem da internet, se você o marcar na instalação. Os outros arquivos da página (`jobot-atualizacao-...zip`, a wheel e o `restricoes.txt`) são para a atualização e para quem desenvolve: você não precisa deles.

**Quer conferir o arquivo?** Baixe também o `SHA256SUMS` para a mesma pasta. No Linux e no Mac, rode `sha256sum --ignore-missing -c SHA256SUMS` (no Mac, `shasum -a 256 --ignore-missing -c SHA256SUMS`); no Windows, `Get-FileHash` no PowerShell e compare com a linha do arquivo. Isso confere que o download não veio quebrado; como o `SHA256SUMS` sai da mesma release, ele não prova a origem (isso fica para a assinatura de código, quando vier).

## 2. Abra

- **Windows:** dois cliques no `-setup.exe`. Se aparecer "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**. O aviso aparece porque o instalador ainda não tem selo (assinatura de código). Ele instala só para o seu usuário, sem senha de administrador.
- **Linux, AppImage:** marque o arquivo como executável (`chmod +x` no arquivo, ou Propriedades, Permissões) e abra. Se ele reclamar de FUSE, prefira o `.deb` ou o `.rpm`. Se quiser o AppImage mesmo assim, rode `TMPDIR=~/.cache ./joBot_<versão>_amd64.AppImage --appimage-extract-and-run`: ele se desempacota na pasta `~/.cache`, no disco, e não no `/tmp`, que em muitos Linux fica na memória. Ao fechar, a pasta é apagada.
- **Linux, `.deb` ou `.rpm`:** `sudo apt install ./` ou `sudo dnf install ./` seguido do nome do arquivo. Depois abra o joBot pelo menu de aplicativos.
- **Mac:** abra o `.dmg` e arraste o joBot para Aplicativos. Na primeira vez, aparece que a Apple não conseguiu verificar o joBot: feche o aviso, abra Ajustes do Sistema › Privacidade e Segurança, desça até a mensagem sobre o joBot e clique em **Abrir Mesmo Assim**, confirmando com a sua senha.

## 3. A tela de instalação

Na primeira abertura, a janela do joBot mostra a tela de instalação.

1. **Ferramentas:** joBot e Python 3.14 vêm marcados e travados. O navegador para sites com login (LinkedIn e outros em que você entra) vem marcado e é o único que vem da internet: o joBot o baixa pelo Playwright, dos servidores do Playwright (uns 210 MB). Se você desmarcar, os sites com login ficam desligados até você baixar o navegador em Configurações › Ferramentas.
2. **Instalando:** nada é baixado, exceto o navegador, se marcado. O joBot confere o sha256 de cada arquivo e de cada biblioteca; se algum não bater, nada é instalado e a tela pede para baixar o instalador de novo. O navegador fica fora dessa conferência: o Playwright não publica o sha256 dele, e o download vem por HTTPS. Sem internet, a instalação funciona igual sem o navegador: se o download dele falhar, a tela oferece seguir sem ele.
3. **Pronto:** a janela vira o controle do joBot. Aperte **Ligar** e depois **Abrir joBot**: o painel abre no seu navegador padrão, com as perguntas da primeira execução.

Se a instalação falhar no meio, o que ela fez é desfeito, e "Tentar de novo" começa do zero.

## 4. Depois de instalar

- **A janela do joBot é um controle.** Ela mostra se o joBot está **Ligado** ou **Parado**, o endereço do painel (com **Copiar**) e os botões **Ligar**, **Parar** e **Abrir joBot**. Abrir joBot, que só aparece com o joBot ligado, abre o painel no seu navegador padrão. Ao abrir, a janela só mostra o estado: não liga nem abre nada sozinha.
- **Fechar a janela** com o joBot ligado pergunta **Deixar o joBot ligado?**. **Deixar ligado** fecha só a janela, e o painel segue no navegador até você abrir a janela e apertar **Parar**; **Desligar** para o joBot e fecha. Com o joBot parado, fecha direto. O segundo plano (Configurações › Segundo plano) serve para o joBot ligar sozinho quando o computador inicia. Pelo painel, **Encerrar o joBot**, em Configurações › Geral, também para tudo.
- **Atualizar:** quando sai versão nova, o painel avisa numa faixa; aperte **Atualizar agora**. A versão nova é montada ao lado da atual e só entra se abrir. A atualização troca só o joBot, não a janela. Quando a janela também tem versão nova, ela mostra **Baixar a janela nova**, que abre a página da versão: baixe e abra o instalador de novo, e os seus dados ficam.
- **Os seus dados** ficam em `~/.local/share/jobot` no Linux, `%LOCALAPPDATA%\joBot` no Windows e `~/Library/Application Support/joBot` no Mac.

## 5. Desinstalar

Desinstalar nunca apaga os seus dados. O navegador também fica, na pasta do Playwright; para tirá-lo, aperte **Remover** em Configurações › Ferramentas antes.

- **Windows:** Configurações › Aplicativos, joBot, **Desinstalar**. O desinstalador desliga o segundo plano, encerra o joBot e apaga a pasta `%LOCALAPPDATA%\joBot\app`.
- **Linux:** desligue o segundo plano e use **Encerrar o joBot**; remova o pacote (`sudo apt remove` ou `sudo dnf remove`) ou apague o `.AppImage`; apague à mão a pasta `~/.local/share/jobot-app`.
- **Mac:** desligue o segundo plano e use **Encerrar o joBot**; arraste o joBot para o Lixo e apague à mão a pasta `~/Library/Application Support/joBot/app`.

## 🛠️ Se algo der errado

- **"Um arquivo do instalador não é o esperado":** o download veio quebrado. Baixe o instalador de novo.
- **Abrir joBot não abriu o navegador:** a janela mostra o motivo. Aperte **Copiar** e cole o endereço no seu navegador. No Linux, o joBot abre o navegador pelo `xdg-open`, do pacote `xdg-utils`.
- **Windows sem o WebView2:** o Windows 11 e o 10 atualizado já trazem o WebView2, de que a janela precisa. Sem ele, o instalador não baixa nada: avisa, com o link oficial da Microsoft (https://developer.microsoft.com/microsoft-edge/webview2/), e cancela. Instale o WebView2 por esse link e abra o instalador de novo.
- **Outra dúvida:** veja as [perguntas frequentes](Perguntas-frequentes) ou [tire a dúvida](Tirar-duvida).
