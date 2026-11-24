# 0027. A casca só controla; o painel abre no navegador da pessoa

- **Status:** aceita
- **Data:** 2026-11-18
- **Atualizada:** 2026-11-18, na verificação da 0.4.1 (o aviso da janela nova, a tela de instalação e o que o CI prova; D207.12, D208.4, D212.10, D212.11 e D214.2); 2026-11-23, fechar a janela com o painel no ar pergunta antes (D215, decisão do dono); 2026-11-24, na T356: o texto passa a dizer o que foi feito no visual (D210), no AppImage (D211, D217) e no servidor deixado ligado (D217).
- **Origem:** D206 do `duvidas.md` (decisão do dono, com o motivo nas palavras dela). Troca a parte "Casca" da [0025](0025-app-de-desktop-e-instalador.md).

## Contexto

Na 0.4.0, a casca Tauri mostrava o painel dentro da própria janela. Cada sistema usa nela um motor diferente: WebKitGTK no Linux, WebView2 no Windows e WKWebView no Mac. Os testes de tela só rodavam no Chromium do Playwright. No Linux do dono, o AppImage da 0.4.0 deixou o PC lento até travar e mostrou o visual quebrado, com partes cortadas e fora do lugar. Três causas foram achadas:

- **O WebKitGTK desenha o painel de outro jeito.** O visual tem efeitos como vidro desfocado (`backdrop-filter`), animações contínuas e ícones SVG usados como máscara. No Chromium esses efeitos são leves; no WebKitGTK pesam e quebram. Como só o Chromium era testado, nada disso apareceu antes da release.
- **O AppImage deixou cópias extraídas no `/tmp`.** Em muitos Linux, entre eles o Fedora do dono, o `/tmp` fica na RAM. Ficaram lá duas pastas de uns 400 MB cada. Aberto normalmente, o AppImage não se extrai: monta em `/tmp/.mount_*` e desmonta ao sair. A extração veio da opção `--appimage-extract-and-run`, que a sessão passou ao dono no teste da 0.4.0; nesse modo, a pasta fica depois de fechar: o runtime deste AppImage não a apaga nem numa saída normal (visto depois, na D217.1), e no PC travado nada mais rodava para apagá-la.
- **Ninguém abriu o app antes da release.** O CI provava que o instalador instala e que o servidor responde, mas não que a janela funciona.

A falta de memória teve também uma causa fora do joBot: temporários dos testes da sessão de desenvolvimento enchiam o mesmo `/tmp`.

## Decisão

- **A casca vira um controle pequeno.** É uma janela com o estado do painel (ligado ou parado), o endereço e os botões **Ligar** e **Parar**. Com o painel no ar, aparece o botão **Abrir joBot**, que abre o endereço no navegador padrão da pessoa. Ninguém precisa decorar `127.0.0.1` nem a porta. A casca é a mesma nos três sistemas.
- **O painel nunca mais roda dentro do WebKitGTK, do WebView2 nem do WKWebView.** A janela da casca só desenha o controle e a tela de instalação. O controle é uma página simples, sem efeitos e sem o CSS do painel; a tela de instalação ainda usa o CSS do painel, com vidro só no alerta de fechar.
- **Fica como estava na 0.4.0:**
  - a tela de instalação na primeira abertura;
  - ~~o aviso de versão nova, que abre a página da release;~~ o aviso de versão nova na faixa do painel. O "Baixar a janela nova", que abre a página da release, muda de lugar: na casca 0.4.1 ele fica no controle, quando o painel no ar é mais novo que a casca; na casca 0.4.0, que ainda mostra o painel na janela dela, a faixa do painel o mostra sempre;
  - ~~fechar a janela fecha só a janela: com o segundo plano ligado, o joBot continua buscando vagas. Sem ele, fechar a janela para o joBot que ela ligou, e o controle avisa isso.~~ Trocado pelo D215 (decisão do dono): fechar a janela do controle com o painel no ar pergunta "Deixar o joBot ligado?". **Deixar ligado** fecha só a janela, e o painel segue no ar até alguém apertar Parar; **Desligar** para o joBot e fecha. Com o painel parado, fecha direto. Vale com o segundo plano ligado ou desligado: ele fica só para o joBot ligar sozinho quando o computador inicia. Fechar a janelinha não pode derrubar a aba do navegador sem a pessoa saber.
- **O painel tem que funcionar em qualquer navegador moderno.** O navegador padrão pode ser o Firefox (o padrão do Fedora), o Chrome, o Edge ou o Safari. Os testes de tela passam a rodar no Chromium, no Firefox e no WebKit do Playwright.
- **O visual fica leve.** Saem os efeitos que pesam fora do Chromium. A lateral e a barra do topo trocam o vidro desfocado (`backdrop-filter`) por fundo sólido, com a mesma cara nos temas claro e escuro; o vidro fica só em camadas pequenas e passageiras (`<dialog>` e `popover`: menu, paleta, alertas). Animação sem fim só existe com trabalho em curso e respeita o movimento reduzido. Os ícones por máscara SVG ficaram: as capturas do WebKit, do Firefox e do Chromium os mostram certos; o que falhar troca-se ícone a ícone (D210).
- **O AppImage não deixa nada no `/tmp`.** Se ele rodar extraído, a casca lança um vigia que apaga a pasta depois que ela e o runtime saem, mesmo depois de uma saída à força; antes, ele espera quem ainda usa a pasta (outra abertura do mesmo AppImage, um programa de dentro dela) e troca o nome dela, para não apagar a extração de outra abertura (D211, D217). Para não prender o AppImage, o que vive mais que a casca nasce fora dele: o navegador do Abrir joBot e o joBot deixado ligado saem sem o ambiente do AppRun, na casa da pessoa e sem os descritores herdados da casca (D207.1, D217). Montado com FUSE, a montagem `/tmp/.mount_*` deve sumir quando a casca fecha; a abertura de verdade antes da tag confere com `ls /tmp/.mount_*`.
- **Antes de cada release, alguém abre a casca de verdade num desktop.** Essa conferência entra no fluxo de release, antes da tag, e o CI ganha um teste que abre a janela: a tela de instalação, a instalação por ela e o controle. O CI usa um Xvfb sem GPU, só no Linux; o que ele não prova (GPU, Wayland, FUSE, as janelas do Windows e do Mac) fica para essa abertura de verdade.

## Consequências

- **Menos risco de quebra.** A parte pesada roda no navegador que a pessoa já usa e que os testes cobrem, e a janela do Tauri fica com páginas simples.
- **A pessoa passa a usar duas janelas:** o controle e a aba do navegador. É o mesmo modelo de outros apps locais, como o Syncthing e o Jupyter.
- **O CI de tela fica mais lento,** porque roda três motores em vez de um.
- **A 0.4.0 continua publicada,** porque as releases são imutáveis. A correção sai na 0.4.1.

## Ver também

- [0025. App de desktop e instalador](0025-app-de-desktop-e-instalador.md)
- [0023. Tudo pelo painel](0023-tudo-pelo-painel.md)
- [duvidas.md: D206](../../duvidas.md)
- [duvidas.md: D215](../../duvidas.md) (fechar a janela do controle)
- [duvidas.md: D207 a D214 e D217](../../duvidas.md) (as escolhas das tarefas da 0.4.1)
