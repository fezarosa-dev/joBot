# Changelog

**Português** · [English](CHANGELOG.en.md)

Todas as mudanças importantes do projeto ficam neste arquivo.

O formato segue o [Keep a Changelog 1.1.0](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

> **Histórico do git reescrito em 2026-11-24**, para tirar um dado pessoal de duas fixtures de teste. Se você clonou o repositório antes dessa data, rode uma vez, na pasta do clone, `git fetch origin && git reset --hard origin/main && uv sync --locked`, ou clone de novo. O reset descarta qualquer mudança local do clone; os seus dados ficam na pasta de dados, fora dele, e não mudam. Fork ou clone de trabalho parte de um clone novo. Quem usa o instalador não precisa fazer nada.

A segunda parte da IA chega, opcional e desligada por padrão: o perfil completo, a leitura do currículo, as perguntas sobre o que falta no perfil e a preparação de candidaturas. O modelo local padrão passa a ser o Laya. As tarefas Currículo, Perguntas e Preparar candidatura são experimentais: confira sempre o que a IA devolve. Os serviços pagos (API da Anthropic, OpenAI e Gemini) seguem sem prova com uma chave de verdade e continuam marcados como experimentais na aba IA.

### Adicionado

- Configurações › Perfil completo: contato, cargo, anos de experiência, formação, resumo, links, idiomas com o nível, habilidades e até 10 experiências e 10 cursos, cada parte com o seu Salvar. Com JavaScript, salvar uma parte não apaga o que foi digitado nas outras. Os campos de contato nunca entram nos pedidos à IA, e Apagar perfil apaga também as experiências, os cursos, as respostas e as candidaturas preparadas.
- Ler o currículo em PDF na aba Perfil: até 5 MB e 20 páginas, lidas no seu computador. Com a tarefa Currículo ligada, a IA preenche o formulário para você conferir; o que não está escrito no currículo vem marcado "Não achei no currículo" e fica fora do Aprovar todas. O e-mail, o telefone e o CPF são tirados do texto antes de ir à IA; o e-mail e o telefone são preenchidos no seu computador, e o CPF não é guardado. O resto do texto vai como está: o nome e a cidade podem ir, se estiverem escritos nele. Nada é gravado antes de você salvar, e o PDF e o texto dele não são guardados. PDF com senha, corrompido, só de imagem ou que não é PDF ganha um aviso próprio.
- Questionário do perfil, com perguntas sobre você que gravam o perfil. Com a tarefa Perguntas ligada, a IA sugere até 5 perguntas sobre o que falta, cada uma com o porquê.
- Preparar candidatura, no detalhe da vaga: com a tarefa ligada, a IA escreve a carta de apresentação e um resumo do perfil para a vaga, no idioma dela. A tela mostra o que você tem e o que falta do que a vaga pede, os dados do perfil que a IA usou, o aviso "Confira antes de usar: a IA pode errar." e um aviso quando a carta cita algo que não está no seu perfil. A carta e o resumo vêm em caixas que você edita e copia; o joBot não envia nada. No modelo local, um perfil muito grande vai cortado (as 30 respostas mais recentes e até 10 mil caracteres), para caber no que o modelo lê de uma vez.
- Perguntas sugeridas: as perguntas que a IA sugere ao preparar uma candidatura esperam você aceitar ou descartar na aba Perfil (até 20 esperam), e só a resposta de uma pergunta aceita vai nos pedidos seguintes.
- IA manual no currículo e na candidatura: o joBot mostra o pedido, você copia e cola no chat de IA que quiser e cola a resposta de volta, que passa pelas mesmas conferências. O joBot não manda nada a ninguém.
- Configurações › IA ganha as tarefas Currículo, Perguntas e Preparar candidatura, cada uma com a frase do que vai e para onde. Elas só rodam quando você pede e não entram no teto de 200 pedidos por dia.
- A primeira execução ganha dois passos opcionais antes da busca: onde a IA roda e o seu perfil. Os dois têm Pular, e a busca chega com o cargo e a cidade do perfil.
- Para quem contribui: a dependência `pypdf`, que lê o currículo num processo à parte, e as migrações do banco do perfil completo e das perguntas sugeridas.

### Alterado

- O modelo local padrão passa a ser o Laya 2B, um ajuste do Qwen3.5 2B para as vagas, treinado com vagas públicas de quatro fontes (Greenhouse, Lever, We Work Remotely e Jobicy), sem vaga de site com login e sem o conjunto de ouro. No ensaio pelo caminho do produto (o modelo que o joBot baixa, servido pelo `llama-server`, só no processador dos computadores do GitHub com Linux, Windows e Mac), ele acertou 79 dos 82 itens do conjunto de ouro, contra 68 ou 69 do Qwen3.5 2B original e os mesmos 79 do 4B, e, nas vagas do conjunto de ouro, levou de 1,7 a 2,7 s por vaga em média e no máximo 6 s, contra de 4 a 6 s em média e até 22 s do 4B; na vaga longa do mesmo ensaio, o Laya levou até 23 s e o 4B até 66 s. O cartão do modelo local em Configurações › Ferramentas e o instalador baixam o Laya (1,3 GB, das versões do joBot no GitHub) em todo computador; a memória só decide o aviso de lentidão. O Qwen3.5 2B e o 4B continuam no cartão, com um botão "Trocar para" para cada um, e quem já baixou um deles continua com ele até trocar. A lista de pedidos de rede de Privacidade e do README cita o Laya.
- A lista de pedidos de rede de Privacidade e do README passa a dizer que, conforme a tarefa, o seu perfil e o texto do currículo vão ao serviço de IA escolhido. Do perfil não vão o nome, o contato e a cidade, e o que você escreveu nos campos de texto (como o resumo e as experiências) vai como você escreveu, menos e-mail, telefone, CPF e o seu nome, quando escrito como está no perfil. Do currículo saem o e-mail, o telefone e o CPF, e o resto vai como está: o nome e a cidade podem ir, se estiverem escritos nele. O README diz o que vai em cada tarefa e deixa de dizer que o joBot guarda CPF e data de nascimento: ele não guarda.
- Quem estava em "Tudo Claude" ou "Tudo offline" na aba IA da 0.5.0 passa a ver "Personalizado": as tarefas novas nascem desligadas, e o Encaixe continua como estava.
- Para quem contribui: `scripts/treino_laya/treinar.py` junta o LoRA pela classe de imagem e texto do Qwen3.5 e copia o tokenizador do repositório original, e o treino deixa a torre de visão de fora; o `requirements.txt` do treino ganha o `torchvision`, o `pillow` e o `flash-linear-attention`.

## [0.5.0] - 2026-11-24

A IA chega, opcional e desligada por padrão: ela lista as habilidades que cada vaga pede, e o joBot compara com as do seu perfil. Ela roda no modelo local, de graça e sem internet depois de baixado, ou num serviço com a sua chave.

### Adicionado

- Configurações › IA: liga a tarefa Encaixe e escolhe onde ela roda (o modelo local, a API da Anthropic, a OpenAI, o Google Gemini ou um endereço compatível com a OpenAI, como o Ollama, o LM Studio e o OpenRouter) e com qual modelo. Os atalhos Desligar a IA, Tudo offline e Tudo Claude configuram tudo de uma vez. Tudo vem desligado.
- Com o Encaixe ligado e ao menos uma habilidade no perfil, depois de cada busca a IA lê até 20 vagas ainda não lidas que já combinam com uma busca, das mais novas para as mais velhas, e lista o que cada uma pede (trocar de serviço ou de modelo faz ler tudo de novo); cada item tem de estar escrito na vaga. A IA não vê o seu perfil e não dá nota: o joBot compara a lista com as suas habilidades, mostra no detalhe da vaga as que você tem e as que faltam, e as habilidades passam a pesar no encaixe.
- Configurações › Perfil: as suas habilidades, uma por linha, e o botão Apagar perfil.
- Configurações › Serviços: cartões para a chave da Anthropic, da OpenAI e do Google Gemini e para o endereço de um serviço compatível com a OpenAI. As chaves ficam no cofre do sistema, e guardar uma chave não liga nada.
- Teste ao ligar: ligar uma tarefa ou trocar o serviço, a chave ou o endereço manda um pedido curto, com uma vaga de exemplo. Se falhar, a tarefa fica desligada e a aba IA diz o motivo.
- Custo à vista: os serviços pagos aparecem como "cobrado por uso", ligar o Encaixe num deles pede confirmação, e o joBot faz no máximo 200 pedidos por dia a cada serviço de fora (fora o teste ao ligar), com a conta do dia na aba IA. A API da Anthropic, a OpenAI e o Gemini vêm marcados "experimental, ainda não provado": só foram testados com um serviço falso.
- Configurações › Ferramentas: o cartão do modelo local baixa o `llama-server` do llama.cpp (do GitHub) e um Qwen3.5 2B ou 4B (do Hugging Face), com o sha256 conferido, e escolhe o modelo pela memória do computador (de 1,3 GB a 2,7 GB). No mesmo cartão ficam a barra do download, a licença e a origem de cada arquivo e os botões para trocar de modelo, Atualizar quando sair versão nova e Remover.
- O instalador traz a caixa Modelo local no passo Ferramentas, desmarcada. Marcada, ela baixa o modelo depois de instalar o joBot; se o download falhar, o joBot fica instalado e a tela manda baixar depois em Configurações › Ferramentas.
- Para quem contribui: os scripts de `scripts/treino_laya/` montam o conjunto de vagas públicas, rotulam, treinam e exportam o Laya, um ajuste do Qwen3.5 2B para as vagas, e calculam o custo do treino. O Laya ainda não vem nesta versão: ele entra numa versão seguinte, depois do treino, se acertar mais que o modelo original.

### Alterado

- A aba Ferramentas de Configurações aparece sempre, mesmo sem site com login ligado.
- A lista de pedidos de rede de Privacidade e do README passa a citar os serviços de IA e os downloads do modelo local (GitHub e Hugging Face, com os CDNs deles), com a condição de cada um. O README ganha a tabela do que funciona sem internet, e o pacote offline deixa de citar o áudio, que fica para a fase 6.

## [0.4.1] - 2026-11-24

**Quem tem a janela 0.4.0:** instale a janela 0.4.1 antes de usar o Atualizar agora do painel. Atualizado só o painel, a janela 0.4.0 fica sem os botões de fechar e de arrastar (feche com Alt+F4) e mostra o aviso para baixar a janela nova.

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
- No Windows e no Mac, o Atualizar agora religa o joBot do jeito certo: refaz o início automático de cada sistema e põe o painel de volta no ar. No Windows, o painel volta mesmo quando a tarefa de início não é regravada, e a atualização não pisca mais janelas pretas de terminal.
- No Windows e no Mac, a leitura com login acha a tela e abre a janela do navegador. No Windows, o navegador dessa leitura abre o perfil e recebe as pastas do sistema de que precisa para entrar na internet.
- No Windows, Configurações, Serviços guarda e lê a chave do 2Captcha: o cofre não abria o arquivo.
- Nas fontes: o RemoteOK não guarda mais, na descrição da vaga, o endereço IP de quem fez a busca; um salário gigante no RemoteOK ou no Super Estágios não derruba mais a busca; a data das vagas do Oracle HCM e do Workday que vem sem hora não aparece mais um dia antes; o SmartRecruiters, sem país na busca, pede as vagas do Brasil; e um sitemap do Abler ou do Super Estágios que mudou de formato marca a fonte como falha em vez de trazer zero vagas sem aviso.
- Uma cotação de moeda estragada no banco não aparece mais na tela nem entra na conversão do salário.

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
