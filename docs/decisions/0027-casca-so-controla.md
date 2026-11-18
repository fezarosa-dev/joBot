# 0027. A casca só controla; o painel abre no navegador da pessoa

- **Status:** aceita
- **Data:** 2026-11-18
- **Origem:** D206 do `duvidas.md` (decisão do dono). Troca a parte "Casca" da [0025](0025-app-de-desktop-e-instalador.md).

## Contexto

Na 0.4.0, a casca Tauri mostrava o painel dentro da própria janela. Cada sistema usa nela um motor diferente: WebKitGTK no Linux, WebView2 no Windows e WKWebView no Mac. Os testes de tela só rodavam no Chromium do Playwright. No Linux do dono, o AppImage da 0.4.0 deixou o PC lento até travar e mostrou o visual quebrado, com partes cortadas e fora do lugar. Três causas estão confirmadas:

- **O WebKitGTK desenha o painel de outro jeito.** O visual tem efeitos como vidro desfocado (`backdrop-filter`), animações contínuas e ícones SVG usados como máscara. No Chromium esses efeitos são leves; no WebKitGTK pesam e quebram. Como só o Chromium era testado, nada disso apareceu antes da release.
- **O AppImage se extrai no `/tmp`.** Em muitos Linux, entre eles o Fedora do dono, o `/tmp` fica na RAM. Cada abertura ocupava uns 400 MB de memória e os arquivos ficavam lá depois de fechar.
- **Ninguém abriu o app antes da release.** O CI provava que o instalador instala e que o servidor responde, mas não que a janela funciona.

A falta de memória teve também uma causa fora do joBot: temporários dos testes da sessão de desenvolvimento enchiam o mesmo `/tmp`.

## Decisão

- **A casca vira um controle pequeno.** É uma janela com o estado do painel (ligado ou parado), o endereço e os botões **Ligar** e **Parar**. Com o painel no ar, aparece o botão **Abrir joBot**, que abre o endereço no navegador padrão da pessoa. Ninguém precisa decorar `127.0.0.1` nem a porta. A casca é a mesma nos três sistemas.
- **O painel nunca mais roda dentro do WebKitGTK, do WebView2 nem do WKWebView.** A janela da casca só desenha o controle e a tela de instalação, que são páginas simples e sem efeitos.
- **Fica como estava na 0.4.0:**
  - a tela de instalação na primeira abertura;
  - o aviso de versão nova, que abre a página da release;
  - fechar a janela fecha só a janela: com o segundo plano ligado, o joBot continua buscando vagas.
- **O painel tem que funcionar em qualquer navegador moderno.** O navegador padrão pode ser o Firefox (o padrão do Fedora), o Chrome, o Edge ou o Safari. Os testes de tela passam a rodar no Chromium, no Firefox e no WebKit do Playwright.
- **O visual fica leve.** Saem os efeitos que pesam fora do Chromium, como `backdrop-filter` em áreas grandes, animações infinitas e ícones por máscara SVG. Entram versões que dão a mesma cara.
- **O AppImage não deixa nada no `/tmp`.** A extração passa a ficar no disco, ou é apagada ao fechar.
- **Antes de cada release, alguém abre a casca de verdade num desktop.** Essa conferência entra no fluxo de release, e o CI ganha um teste que abre a janela do controle.

## Consequências

- **Menos risco de quebra.** A parte pesada roda no navegador que a pessoa já usa e que os testes cobrem, e a janela do Tauri fica com páginas simples.
- **A pessoa passa a usar duas janelas:** o controle e a aba do navegador. É o mesmo modelo de outros apps locais, como o Syncthing e o Jupyter.
- **O CI de tela fica mais lento,** porque roda três motores em vez de um.
- **A 0.4.0 continua publicada,** porque as releases são imutáveis. A correção sai na 0.4.1.

## Ver também

- [0025. App de desktop e instalador](0025-app-de-desktop-e-instalador.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [duvidas.md: D206](../../duvidas.md)
