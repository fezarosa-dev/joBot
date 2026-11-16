# Changelog

**Português** · [English](CHANGELOG.en.md)

Todas as mudanças importantes do projeto ficam neste arquivo.

O formato segue o [Keep a Changelog 1.1.0](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Adicionado

- LinkedIn, o primeiro site com login. O leitor vem desligado: você liga em Configurações, Sites com login. Ele busca por cada cargo das suas buscas, com a cidade e o remoto, e lê só a última semana, ordenada por relevância. Como a lista não é completa, uma vaga do LinkedIn só fecha depois de 30 dias sem ser vista, e reabre se voltar.
- A tela Ferramentas em Configurações, para baixar e remover o navegador dos sites com login (uns 210 MB), sem terminal.
- O passo opcional "Sites com login" no assistente de primeira execução: ligar os sites, ver o navegador e baixá-lo, tudo antes de ver as vagas.
- Login numa janela comum do navegador, sem automação: você entra como quiser (Google, e-mail e senha) e fecha a janela. O joBot confere a sessão sozinho e nunca digita a senha.
- ADR 0023: tudo pelo painel. Ferramentas externas, atualização e encerramento passam a ter botão, sem terminal.
- ADR 0024: o Gmail será lido por IMAP com uma senha de app colada no painel (o cartão vem com a aba Contas; a leitura dos e-mails, na fase 6). A wiki ganha o passo a passo.

### Alterado

- Novo roteiro: depois da fase 2 sai a versão 0.3.0 (tela "Panorama" e fila de candidaturas completa); a fase 3 vira o Instalador e as seguintes andam um número, até a fase 9 (publicação).

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
