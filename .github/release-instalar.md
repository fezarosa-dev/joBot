## Como instalar

Baixe **só um arquivo**: o do seu sistema, na lista **Assets** lá embaixo.

| Seu sistema | Baixe | Como instalar |
|---|---|---|
| Windows 10 ou 11 | `joBot_{versao}_x64-setup.exe` | Dois cliques. Se aparecer "O Windows protegeu o computador", clique em **Mais informações** e em **Executar assim mesmo**. Não pede senha de administrador. |
| Ubuntu, Debian, Mint | `joBot_{versao}_amd64.deb` | No terminal, na pasta do download: `sudo apt install ./joBot_{versao}_amd64.deb` |
| Fedora | `joBot-{versao}-1.x86_64.rpm` | No terminal, na pasta do download: `sudo dnf install ./joBot-{versao}-1.x86_64.rpm` |
| Outro Linux | `joBot_{versao}_amd64.AppImage` | Marque como executável (`chmod +x joBot_{versao}_amd64.AppImage`, ou Propriedades › Permissões) e abra. |
| Mac com Apple Silicon (M1 ou mais novo) | `joBot_{versao}_aarch64.dmg` | Abra o `.dmg` e arraste o joBot para Aplicativos. Na primeira vez, se a Apple avisar, abra Ajustes do Sistema › Privacidade e Segurança e clique em **Abrir Mesmo Assim**. |
| Mac com Intel | `joBot_{versao}_x64.dmg` | Igual ao Mac com Apple Silicon. |

Na primeira vez, a janela do joBot instala o resto (o navegador para sites com login e, se você marcar, o modelo local de IA) e vira o controle: aperte **Ligar** e depois **Abrir joBot**. Requisitos e passo a passo: [README](https://github.com/fezarosa-dev/joBot#requisitos-e-instalacao).

**Os outros arquivos você não precisa baixar:**

- `jobot-atualizacao-{versao}-….zip`: usados pelo botão **Atualizar agora** do próprio joBot, um por sistema.
- `jobot-{versao}-py3-none-any.whl` e `restricoes.txt`: para instalar pelo Python (`pip` ou `uv`), uso avançado.
- `SHA256SUMS`: confere se o download veio inteiro: `sha256sum -c SHA256SUMS --ignore-missing`.
- `Source code`: o código desta versão, que o GitHub junta sozinho.

