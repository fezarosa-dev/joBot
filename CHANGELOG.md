# Changelog

**Português** · [English](CHANGELOG.en.md)

Todas as mudanças importantes do projeto ficam neste arquivo.

O formato segue o [Keep a Changelog 1.1.0](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

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
- Decisões do projeto (ADRs 0001 a 0021) e o `duvidas.md`.
- README com selos, diagrama, tabelas e perguntas frequentes, e a versão em inglês.
- Gráfico de estrelas no README.
- Imagem de prévia para redes sociais (`docs/imagens/previa-social.png`).
- Licença MIT, Código de Conduta, política de segurança, guia de contribuição, suporte, modelos de issue e de PR e CODEOWNERS, também em inglês.
- `CITATION.cff`, `.editorconfig` e `.gitattributes`.

### Alterado

- Denúncias do Código de Conduta vão para o e-mail do projeto.
- O README deixou de ser só plano: descreve a instalação da fase 1.

### Corrigido

- A descoberta semanal pelo Common Crawl não falha mais por causa de blocos enormes de outros sites, que o joBot nunca baixa.
- A Greenhouse aceita quadros de vagas muito grandes, como o da Stripe.
- A agenda só começa a buscar depois que o assistente de primeira execução termina.
- Em Fontes, uma fonte que atingiu o limite mostra a última rodada que ela de fato fez.
