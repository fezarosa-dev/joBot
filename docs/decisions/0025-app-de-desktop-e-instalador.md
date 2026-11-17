# 0025. App de desktop e instalador

- **Status:** aceita (as escolhas da sessão listadas na D171, itens 9 a 18, seguem para confirmar; no texto, cada frase que vem delas leva a marca "para confirmar")
- **Data:** 2026-11-17
- **Atualizada:** 2026-11-17, pela D173 e pela D174 do `duvidas.md` (instalador completo e sem rede; o texto por extenso entra na T341)

## Contexto

A fase 3 ([0017](0017-fases.md)) traz o instalador e o app de desktop. A D142 já tinha escolhido o Tauri como casca e a [0023](0023-tudo-pelo-painel.md) pede que tudo se faça pelo painel, sem terminal. Faltavam a distribuição, a assinatura, os pacotes, o Mac, onde fica o código, o que acontece ao fechar a janela e como a janela se atualiza. O dono respondeu em 2026-11-17 (D171). O desenho está em `docs/superpowers/specs/2026-11-17-fase-3-design.md`.

## Decisão

- **Casca.** Um app Tauri 2 (Rust) na pasta `desktop/` do mesmo repositório. Ele dá ao joBot ícone e janela própria em volta do mesmo painel, que continua em 127.0.0.1 e não é reescrito. A casca é um processo à parte: só fala HTTP com o painel e chama o `jobot` e o `uv`; o pacote Python não importa nada dela. Fechar a janela fecha só a janela: o servidor segue se o segundo plano estiver ligado. Sem ícone na bandeja.
- **Tela de instalação na primeira abertura.** Quando a casca não acha o joBot instalado, ela mesma mostra a tela de instalação, igual nos três sistemas, com a lista de ferramentas para marcar (D171.9, para confirmar). joBot e Python vêm travados; o navegador, marcado e opcional (D171.10, para confirmar). ~~Os pacotes do sistema (NSIS, AppImage, `.deb`, `.rpm`, `.dmg`) levam só a casca e o `uv` (D171.9, para confirmar).~~ (superado em 2026-11-17 pela D174.1: levam também o Python, as wheels, o joBot ~~e o Chromium~~ daquela plataforma; o Chromium saiu pela D183.24, decidida pela sessão em 2026-11-17 para o dono confirmar: o joBot não redistribui o Chrome for Testing que o Playwright baixa, e o navegador marcado vem do `playwright install`, com rede.)
- **`uv` embutido.** A casca traz o `uv`, com pastas próprias, separadas de um `uv` que a pessoa já tenha (D171.17, para confirmar). ~~Ele instala o joBot da release do GitHub da mesma versão, com o sha256 conferido.~~ (superado em 2026-11-17 pela D173 e pela D174.1: ele monta um venv a partir dos arquivos que vêm no instalador, com o hash de cada dependência conferido e sem usar a rede.) O `jobot atualizar` ganha o canal `casca`.
- **Release.** Uma tag `vN.N.N` dispara o fluxo de release do GitHub Actions, que gera os instaladores (Windows; Linux em AppImage, `.deb` e `.rpm`; Mac em `.dmg` experimental, testado só no CI), a wheel e o `SHA256SUMS` (e, desde a D174, os pacotes de atualização ~~e o Chromium~~ por plataforma; sem o Chromium desde a D183.24), e publica a release. Só esse fluxo escreve no repositório, com o `GITHUB_TOKEN`; o CI de PR continua sem segredo ([0018](0018-manutencao-pela-comunidade.md)).
- **Atualização da janela.** A casca não se atualiza sozinha; ela também não consulta o GitHub (D171.11, para confirmar): o aviso de versão do painel diz que há versão nova e abre a página da release ([0014](0014-seguranca-e-privacidade.md) e o interruptor de Privacidade continuam valendo).
- **Sem selo por ora.** Os instaladores saem sem assinatura de código, com custo zero, e nenhum certificado é comprado. O dono pede o SignPath Foundation (grátis) quando quiser, depois da 0.4.0.

## Consequências

- O Windows (SmartScreen) e o Mac avisam que o instalador não é reconhecido; o README explica como abrir mesmo assim.
- O `SHA256SUMS` vem da mesma release: protege de arquivo corrompido, não de release adulterada. A assinatura de código cobre isso quando vier.
- O projeto passa a ter Rust e um segundo fluxo de CI (`casca.yml`), sem segredo.
- Desinstalar nunca apaga a pasta de dados (D171.18, para confirmar).

## Ver também

- [0003. Tecnologias e instalação nativa (sem Docker)](0003-stack-e-instalacao-nativa.md)
- [0014. Segurança e privacidade](0014-seguranca-e-privacidade.md)
- [0017. Fases do projeto](0017-fases.md)
- [0018. Manutenção pela comunidade e CI aberto a todo PR](0018-manutencao-pela-comunidade.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [duvidas.md: D138 (instalador), D142 (app de desktop) e D171 (fase 3)](../../duvidas.md)
