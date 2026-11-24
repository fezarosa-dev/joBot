# Changelog

**Português** · [English](CHANGELOG.en.md)

Todas as mudanças importantes do projeto ficam neste arquivo.

O formato segue o [Keep a Changelog 1.1.0](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

A 0.4.1 corrige o que a 0.4.0 quebrou no Linux: a janela do joBot vira um controle pequeno, e o painel abre no seu navegador.

### Adicionado

- ADR 0026 (proposta): IA da fase 4. A IA chegará em duas versões, a 0.5.0 e a 0.6.0, desligada por padrão; o modelo local será baixado da fonte oficial, a pedido da pessoa, e a IA só listará o que a vaga pede, sem dar nota. O roteiro passa a mostrar a fase 4 sendo construída.
- ADR 0027: a casca só controla. A janela do joBot vira um controle com Ligar, Parar e Abrir joBot, e o painel abre no navegador padrão da pessoa. Troca a parte "Casca" da ADR 0025.
- A base da IA da fase 4 já vem nesta versão, desligada e sem tela para ligar: a migração do banco que guarda o perfil, as habilidades que a IA tirar de cada vaga e o nível de encaixe, a dependência pydantic, os clientes da API da Anthropic e de serviços compatíveis com a OpenAI e o `jobot ferramentas baixar ia-local`, que baixa o llama-server e um modelo com sha256 conferido. Nada disso roda sem a pessoa ligar.
- Os testes de tela do painel rodam no Chromium, no Firefox e no WebKit, porque o navegador padrão pode ser qualquer um deles. Antes de cada versão, o CI instala a janela do joBot num desktop virtual, instala o joBot por ela, liga, abre e para pelo controle e guarda as capturas.

### Alterado

- A janela do joBot vira um controle pequeno. Ela mostra se o joBot está Ligado ou Parado e o endereço do painel, com o botão Copiar, e tem os botões Ligar, Parar e Abrir joBot. Abrir joBot abre o painel no seu navegador padrão (Firefox, Chrome, Edge, Safari ou outro). Ao abrir, a janela só mostra o estado: não liga nem abre nada sozinha. A tela de instalação continua na primeira abertura e, no fim, leva ao controle.
- Fechar a janela com o joBot ligado pergunta "Deixar o joBot ligado?". Deixar ligado fecha só a janela, e o painel segue no navegador até você apertar Parar; Desligar para o joBot e fecha. Com o joBot parado, a janela fecha direto. O segundo plano passa a servir só para o joBot ligar sozinho quando o computador inicia.
- O botão "Baixar a janela nova" sai da faixa do painel e vai para o controle, que o mostra quando o joBot no ar é mais novo que a janela (o "Atualizar agora" troca só o joBot). Quem ainda tem a janela 0.4.0 e atualiza só o joBot vê, dentro dela, uma faixa que manda instalar a janela nova.
- O visual do painel fica mais leve: a barra lateral e a barra do topo têm fundo sólido em vez de vidro desfocado, e o vidro fica só em menus e diálogos.
- A barra de progresso anda de forma fluida, no painel e na instalação: começa rápida e vai freando aos poucos, sem pular nem parar de repente entre uma etapa e outra.
- O vigia semanal das fontes se reativa a cada execução, para o GitHub não desligá-lo depois de 60 dias sem atividade no repositório.

### Removido

- O painel não roda mais dentro da janela do joBot. Saem os botões de fechar, minimizar e maximizar que o joBot desenhava e a área de arrastar a janela.

### Corrigido

- No Linux, a janela da 0.4.0 deixava o computador lento e mostrava o painel cortado e fora do lugar. Agora o painel roda no seu navegador.
- O AppImage não deixa mais cópias de uns 400 MB no `/tmp`, que em muitos Linux fica na memória: rodando desempacotado (sem FUSE), a pasta é apagada ao fechar, mesmo depois de uma saída à força, e sem apagar a de outra abertura que ainda está em uso.
- O joBot deixado ligado pela janela e o navegador aberto pelo Abrir joBot não ficam mais presos ao AppImage depois que a janela fecha: não herdam a pasta, os arquivos abertos nem as configurações de dentro dele, como o tema claro forçado no navegador.
- No Firefox e no Safari, o menu de contexto das vagas abre pelo mouse.
- No Safari, voltar a uma página do painel não mostra mais o aviso falso de que a internet caiu.
- No painel: o detalhe ao lado da lista mostra as habilidades da IA, como a página da vaga; o Panorama não diz mais "Buscando agora." durante a descoberta de empresas, a leitura de páginas ou a leitura com login; no alto contraste, os botões de Vagas e de Configurações e o chip ligado ficam visíveis; o cartão do 2Captcha não diz mais que a navegação com login ainda não existe; e um valor estragado de idioma, tema ou tamanho do texto no banco não derruba mais o painel. A lista de pedidos de rede de Privacidade passa a citar o Gmail.

## [0.4.0] - 2026-11-17

A fase 3 chega: o joBot ganha uma janela própria e um instalador para Windows, Linux e Mac, que instala tudo sem internet, menos o navegador opcional.

### Adicionado

- Instalador para Windows (`-setup.exe`), Linux (AppImage, `.deb` e `.rpm`, este experimental) e Mac (`.dmg`, experimental). Cada um tem de cerca de 100 a 200 MB, porque já traz o Python 3.14, as bibliotecas e o joBot: a instalação funciona sem internet e confere o sha256 de cada arquivo. O navegador dos sites com login não vem no instalador: marcado, ele vem da internet pelo Playwright, sem sha256 conferido (o Playwright não o publica). No Windows sem o WebView2, o instalador avisa com o link oficial da Microsoft e cancela, sem baixar nada. Por enquanto sem selo (assinatura de código): o README explica como abrir no Windows e no Mac.
- Uma janela própria do joBot, com ícone, em volta do mesmo painel, que continua só no seu computador. No Windows e no Linux os botões de fechar, minimizar e maximizar são desenhados pelo joBot; no Mac, são os do sistema. Fechar a janela fecha só a janela: com o segundo plano ligado, as buscas seguem.
- Tela de instalação na primeira abertura da janela: joBot e Python vêm travados, o navegador vem marcado e dá para desmarcar (ele baixa depois em Configurações › Ferramentas), e a barra mostra cada etapa. Se algo falhar, o que foi feito é desfeito.
- O joBot passa a rodar no Windows e no Mac, cada um com a sua pasta de dados.
- Segundo plano no Windows (Agendador de Tarefas) e no Mac (LaunchAgent, experimental), além do systemd do Linux.
- Botão "Atualizar agora" na faixa de versão nova e em Configurações › Geral. Pelo instalador, a versão nova é montada ao lado da atual, conferida, e só entra se abrir; senão, nada muda. Quando a janela também tem versão nova, o botão "Baixar a janela nova" abre a página da versão.
- Botão "Encerrar o joBot" em Configurações › Geral e na paleta de comandos, que para o servidor e as buscas.
- Pelo instalador, o navegador dos sites com login baixa pelo Playwright, na instalação (se marcado) ou na tela Ferramentas, e a tela Ferramentas avisa quando ele fica desatualizado depois de uma atualização.
- Desinstalar pelo Windows desliga o segundo plano e encerra o joBot, e nunca apaga a pasta de dados.
- ADR 0025: app de desktop e instalador. A janela, a tela de instalação, o instalador completo e sem rede (menos o navegador opcional) e a atualização pelo painel.

### Alterado

- A faixa de versão nova não manda mais abrir o terminal: ela traz o botão "Atualizar agora".
- O README explica a instalação pelo instalador, os avisos do Windows e do Mac, onde ficam os dados em cada sistema e como desinstalar; a wiki ganha a página Instalar.

## [0.3.0] - 2026-11-16

A fase 2 chega: o navegador com login e o LinkedIn, o primeiro site com login. O painel ganha um visual novo, a aba Contas (com o cartão do Gmail), o Panorama e a fila de candidaturas, e o roteiro passa a pôr o Instalador na fase 3.

### Adicionado

- LinkedIn, o primeiro site com login. O leitor vem desligado: você liga em Configurações, Contas. Ele busca por cada cargo das suas buscas, com a cidade e o remoto, e lê só a última semana, ordenada por relevância. Como a lista não é completa, uma vaga do LinkedIn só fecha depois de 30 dias sem ser vista, e reabre se voltar.
- A aba Contas mostra se o joBot ainda está conectado em cada site, confere na hora e avisa quando a sessão cai.
- Cartão do Gmail na aba Contas: cole a senha de app, e o joBot confere o login só para leitura. A leitura dos e-mails vem na fase 6.
- A tela Ferramentas em Configurações, para baixar e remover o navegador dos sites com login (uns 210 MB), sem terminal.
- O passo opcional "Sites com login" no assistente de primeira execução: ligar os sites, ver o navegador e baixá-lo, tudo antes de ver as vagas.
- Login numa janela comum do navegador, sem automação: você entra como quiser (Google, e-mail e senha) e fecha a janela. O joBot confere a sessão sozinho e nunca digita a senha.
- ADR 0023: tudo pelo painel. Ferramentas externas, atualização e encerramento passam a ter botão, sem terminal.
- Guia "Como acrescentar um site novo" (`docs/site-novo.md`), com um molde de coletor para site público e um de leitor para site com login, e uma guarda no CI que confere o teste, o exemplo e o nome de cada site.
- O Panorama, um item novo na barra lateral: o dia numa tela, com o que fecha logo, as candidaturas e a busca, com atalhos para as vagas e as fontes.
- A linha do tempo da vaga, com a data de cada passo (vista, salva, candidatura aberta, candidatei), e o "desde" na aba Candidatei.
- A pergunta "Você se candidatou?" depois que você abre o link de candidatura de uma vaga, com "Sim, me candidatei", "Ainda não" e Desfazer.
- Candidatura por e-mail: quando a descrição traz um endereço, o botão "Candidatar-se por e-mail" abre o seu programa de e-mail com o título da vaga. O joBot não envia nada.
- ADR 0024: o Gmail será lido por IMAP com uma senha de app colada no painel (o cartão está em Configurações, Contas; a leitura dos e-mails, na fase 6). A wiki ganha o passo a passo.
- Uma janela própria para o painel: se o computador tem Chrome, Edge ou Chromium, o `jobot` abre o painel sem abas nem barra de endereço, como um aplicativo; sem eles, abre numa aba.
- Desfazer e Refazer: ocultar uma vaga, descartar uma sugestão e remover uma empresa acontecem na hora, com uma faixa de Desfazer (`⌘Z`, `Ctrl+Z` fora do Mac) e de Refazer. Apagar uma busca, remover um site e esquecer logins pedem confirmação num alerta.
- Paleta de comandos (`⌘K`, `Ctrl+K` fora do Mac): vai a qualquer tela e troca tema, idioma e tamanho do texto, sem mouse.
- Atalhos de teclado: `/` para a busca, setas, `J`, `K`, `Home` e `End` na lista, `⌘,` para Configurações, `⌘?` para a ajuda e a tecla de menu para o menu da vaga. A página "Atalhos de teclado" na wiki lista todos.
- Tamanho do texto (Padrão, Grande ou Maior) em Configurações, Geral.
- Progresso da busca com etapas: o topo mostra em que passo o joBot está (por exemplo, "Lendo Greenhouse · 13 de 20 consultas") e o "Ver detalhes".

### Alterado

- A lista de vagas e o Panorama abrem mais rápido com muitas vagas: as abas são contadas numa passada só, e o Panorama conta só o que mostra.
- Novo roteiro: a versão 0.3.0 saiu depois da fase 2 (tela "Panorama" e fila de candidaturas completa); a fase 3 vira o Instalador e as seguintes andam um número, até a fase 9 (publicação).
- Visual novo do painel, no estilo de um aplicativo do Mac: barra lateral com Vagas e Onde buscar, lista de vagas com o detalhe ao lado, janelas e alertas translúcidos, e o título em inglês da correção em Title Case ("Something Wrong with This Job?").

### Corrigido

- O foco volta ao chip certo depois de trocar o filtro, mesmo quando dois valores diferem só por um espaço e um `_`.

## [0.2.1] - 2026-11-15

### Alterado

- A lista de vagas abre sem esperar a contagem dos filtros: os chips chegam logo depois da lista. Sem JavaScript os chips não aparecem.
- O chip de fonte ficou mais rápido em bancos grandes, graças a um índice novo (migração 0006).
- O aviso "Salvo." some sozinho depois de 5 segundos em todas as telas de Configurações e não volta ao atualizar a página.

## [0.2.0] - 2026-11-15

### Adicionado

- ADR 0022: CAPTCHA resolvido pelo serviço que a pessoa liga (2Captcha), só na navegação com login.
- Aba Serviços em Configurações: guarde a chave do 2Captcha, teste a chave e veja o saldo. O uso chega com a navegação com login.
- Filtros novos na lista de vagas: país, publicada há quantos dias e, em "Mais filtros", salário, cidade, empresa e palavras que a vaga não pode ter.
- "Meu país", perguntado na primeira execução e guardado em Configurações, e a moeda dos valores convertidos, que você escolhe (a do seu país por padrão).

### Alterado

- O salário em moeda estrangeira aparece convertido numa linha própria, embaixo do valor original.

## [0.1.1] - 2026-11-15

Erros mais claros e menos surpresas. Nada muda no que o joBot busca.

### Adicionado

- Aviso na tela quando um clique falha ou o painel não responde. Ele não insiste depois que o painel é fechado.
- A tela e o `jobot buscar` dizem por que a busca parou.
- Dica na tela de buscas: escreva as variações de um cargo, uma por linha.

### Alterado

- O aviso de versão agora vem ligado por padrão. Quem já escolheu mantém a escolha.
- Ctrl+C no terminal sai com o código 130.
- A saída do systemctl vai só para o `jobot.log`, não para a tela.

### Corrigido

- Um erro no painel mostra uma página amigável, no lugar do erro 500 seco. Os erros 404 e 422 também ganham uma mensagem.
- O passo 2 da primeira execução não prende mais: se o segundo plano falhar, conclui com um aviso.
- O terminal não mostra mais traceback: o erro técnico vai para o `jobot.log`.

## [0.1.0] - 2026-11-14

A fase 1: a base do joBot. Já dá para instalar e usar.

### Adicionado

- Painel no navegador, em `http://127.0.0.1:47615`, com Vagas, Buscas, Fontes, Empresas, Sugeridas, Sites e Configurações.
- Busca de vagas em dezenas de fontes públicas, a cada 3 horas ou na hora, pelo botão "Buscar agora".
- Limpeza das vagas: tira repetidas e lê salário, área, nível, modalidade, região e tipo de contrato.
- Nota de encaixe com a sua busca (bom, médio, fraco), por regras e com os motivos. Sem IA.
- Status de cada vaga, de "nova" até "oferta", e abas Destaques, Todas, Novas, Fecham logo, Salvas, Candidatei, Programas e Ocultas.
- Acompanhamento de páginas de programas, como trainee e escola de verão, na tela Sites.
- Lista de empresas própria e descoberta semanal de novos quadros de vagas, que vão para Sugeridas até você aprovar.
- Comandos `jobot abrir`, `jobot sair`, `jobot serve`, `jobot buscar`, `jobot segundo-plano`, `jobot atualizar` e `jobot avaliar-rotulos`.
- Segundo plano no Linux, pelo systemd do usuário, inclusive a partir de um container distrobox.
- Aviso de versão nova, desligado por padrão. Ligado, só pede ao `api.github.com` a versão mais nova, e o pedido leva o user agent fixo e o IP.
- Eureca, Abler e Gupy, cada um com a sua chave liga/desliga. Todas vêm ligadas por padrão; os termos da Eureca pedem consentimento prévio, e quem preferir respeitar desliga a Eureca em Configurações.
- Painel em português e em inglês, com tema claro e escuro.
- Na barra de andamento da busca, a lista das fontes que ainda estão rodando.
- Aviso "Salvo." depois de salvar em Configurações.
- `jobot abrir` escreve no terminal o endereço do painel e como sair; a barra de andamento da busca mostra a fase de detalhes depois da coleta.
- Aviso de restrição a países nas vagas remotas da Himalayas, Jobicy e Remotive.
- Decisões do projeto (ADRs 0001 a 0021) e o `duvidas.md`.
- README com selos, diagrama, tabelas e perguntas frequentes, e a versão em inglês.
- Gráfico de estrelas no README.
- Imagem de prévia para redes sociais (`docs/imagens/previa-social.png`).
- Licença MIT, Código de Conduta, política de segurança, guia de contribuição, suporte, modelos de issue e de PR e CODEOWNERS, também em inglês.
- `CITATION.cff`, `.editorconfig` e `.gitattributes`.

### Alterado

- Denúncias do Código de Conduta vão para o e-mail do projeto.
- O README deixou de ser só plano: descreve a instalação da fase 1.
- As regras de rótulo (área, nível, modalidade, contrato, país e estado) foram ajustadas e medidas num conjunto de vagas conferidas à mão.
- Vagas de sites só brasileiros saem com o país Brasil.
- O aviso de restrição a países diz quais são os países, como "Só para quem mora em: Estados Unidos e Canadá".

### Corrigido

- A descoberta semanal pelo Common Crawl não falha mais por causa de blocos enormes de outros sites, que o joBot nunca baixa.
- A Greenhouse aceita quadros de vagas muito grandes, como o da Stripe.
- A agenda só começa a buscar depois que o assistente de primeira execução termina.
- Em Fontes, uma fonte que atingiu o limite mostra a última rodada que ela de fato fez.
- Um país de fora no formulário de buscas não vira mais um estado brasileiro.
- Uma cidade com nome de país, como "Franca, São Paulo", não vira mais o país.
- Em Fontes, o cartão "Sem mudança" mostra as vagas da última rodada que leu e a próxima busca certa.
- Uma página acompanhada nova é lida na próxima volta da agenda, sem esperar 24 horas.
