# Panorama e fila de candidaturas: desenho

Data: 2026-11-16. Decisões de origem: ADR 0001 (o joBot nunca envia candidatura), ADR 0013 (sem push nem ntfy), ADR 0014 (segurança e privacidade), ADR 0017 (fases e a versão 0.3.0), ADR 0023 (tudo pelo painel), D138 (itens 1, 2, 3 e 9), D139 (Contas), D143 e D144 (visual de Mac e o plano dele). As decisões novas ficam em `duvidas.md` como D147.

Este documento é a especificação para planejar e construir o lote "Panorama e fila" sem voltar ao dono. Ele fecha a versão 0.3.0, que sai entre a fase 2 e a fase 3 (`wiki/Roteiro.md:35`, `docs/decisions/0017-fases.md:16`, `README.md:445`, `CHANGELOG.md:20`). Todo fato sobre o código vem com `arquivo:linha`, conferido em 2026-11-16 na árvore da `dev` com o plano de Contas por cima. As linhas podem andar: quando a linha não bater, procure pelo nome. As lições de `registros/padroes.md` são citadas pelo rótulo, como `padroes.md («Esquema»)`.

Cada decisão leva o número da lista completa da seção 11 (D147.1 a D147.31). Todas são da sessão e estão "para confirmar" com o dono. O que veio do dono está na D138: o Panorama entra na 0.3.0 (item 2) e a fila completa traz o link de candidatura por e-mail, a pergunta "Você se candidatou?" e as datas de cada passo (item 3). A candidatura automática foi recusada (item 1, Q3) e continua fora.

## 1. Intenção e porquê

O painel abre direto na lista de vagas (`src/jobot/painel/rotas/vagas.py:448-453`). O que diz como vai a procura está espalhado: a contagem de cada aba fica na lateral, a saúde das fontes em Fontes, o estado das contas em Configurações. Não existe um lugar que responda, num olhar, "o que tem de novo, o que vence logo, em que pé estão as minhas candidaturas e se a busca está funcionando".

Na fila de candidaturas, o status já anda (Nova, Salva, Candidatei, Entrevista, Oferta ou Recusada), mas a vaga só guarda a data da última troca (`status_em`, `src/jobot/banco/migracoes/0001_inicial.sql:87`). O histórico existe na tabela `evento` (`0001_inicial.sql:158-174`), e nenhuma tela mostra esse histórico. O botão "Candidatar-se" abre o site da vaga numa aba nova (`src/jobot/painel/templates/detalhe/pagina.html:52-53`). Depois disso o joBot não sabe o que aconteceu, e a pessoa precisa lembrar de voltar e apertar "Me candidatei". Quando a vaga pede o currículo por e-mail, o endereço fica perdido no meio da descrição.

O dono pediu as duas coisas para a 0.3.0 (D138.2 e D138.3). O Panorama dá a visão de cima. A fila completa fecha o ciclo: o joBot pergunta, quando a pessoa volta, se ela se candidatou, guarda a data de cada passo e facilita a candidatura por e-mail. O joBot nunca envia nada (ADR 0001).

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos

1. Uma tela "Panorama" (en "Overview"), primeiro item da lateral, com quatro grupos: Hoje, Candidaturas, A busca e O que aparece (D147.1 a D147.10).
2. No detalhe da vaga, uma linha do tempo com a data de cada passo, tirada do histórico que já existe, sem esquema novo (D147.12 a D147.14).
3. Quando a pessoa abre a candidatura de uma vaga e depois volta ao painel, uma faixa pergunta "Você se candidatou a {vaga}?", com "Sim, me candidatei" e "Ainda não" (D147.15 a D147.21).
4. Uma vaga cujo texto pede candidatura por e-mail ganha o botão "Candidatar-se por e-mail", que abre o programa de e-mail da pessoa com o assunto preenchido, e o endereço à vista com "Copiar endereço" (D147.22 a D147.26).

Não objetivos

- Editar a data de um passo à mão.
- Lembrete de acompanhamento ("faz 15 dias que você se candidatou e não houve resposta"). Pode virar uma `Tn` depois, já com as datas guardadas.
- Gráfico ao longo do tempo (vagas por dia, candidaturas por semana): pede guardar contagens por dia, coisa que o banco não faz hoje.
- Personalizar o Panorama: esconder, reordenar ou trocar grupos.
- Atualizar o Panorama sozinho enquanto ele está aberto. Abrir de novo ou apertar ⌘R mostra os números novos.
- Ler o `mailto:` que a própria fonte manda no campo de candidatura (seção 10, P2).
- Candidatura dentro do painel, formulário e anexo de currículo.

Anti-objetivos

- O joBot nunca envia candidatura nem e-mail. O botão de e-mail só abre o programa de e-mail da pessoa, que decide se envia (ADR 0001, D138.1, ADR 0013).
- Nenhuma biblioteca de gráfico, nenhum recurso externo e nenhum JavaScript para desenhar (CSP, `src/jobot/painel/app.py:19-23`).
- Nenhum alerta modal para a pergunta "Você se candidatou?". A pergunta fica numa faixa e não trava o uso (HIG: alertas só para o que é crítico; feedback integrado à interface).
- Nenhuma IA nem modelo para achar o e-mail ou montar o Panorama.
- O joBot não guarda o endereço de e-mail achado: ele é lido do texto da vaga na hora de mostrar.

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py`): a função que acha o e-mail é pura e fica em `nucleo`; as consultas novas ficam em `banco`; o painel não importa `httpx`. O painel já importa `agenda` (`src/jobot/painel/rotas/fontes.py:19`), e o Panorama pode fazer o mesmo.
- CSP com `style-src 'self'` (`src/jobot/painel/app.py:20`): o atributo `style` é recusado. A largura das barras não pode vir por `style="width:…"`.
- Banco: gravação com `INSERT ... ON CONFLICT DO UPDATE`; nada é apagado; `evento` só recebe acréscimo, e a lista de ações é fechada por CHECK (`0001_inicial.sql:161`). Mudar esse CHECK exige reconstruir a tabela com os gatilhos `evento_sem_update` e `evento_sem_delete` (`0001_inicial.sql:167-174`). Este desenho não mexe em `evento` (`padroes.md («Esquema»)`).
- Número da migração: a regra da D144.E3 (`docs/superpowers/plans/2026-11-16-visual-mac.md:32`) vale aqui. Hoje existem as migrações 0001 a 0008; o visual usa a 0009 (`0009_andamento.sql`, T246) e Contas a 0010 (`0010_sessao_site.sql`, D146.E1). Este lote usa a 0011, e quem entrar depois troca o número do arquivo e do teste antes de juntar (`padroes.md («Teste de migração»)`).
- Texto novo nos catálogos `pt` e `en` (`padroes.md («i18n»)`). Em inglês, botões em Title Case; em português, só a primeira letra maiúscula (D143).
- A tela continua funcionando sem JavaScript; o único JavaScript próprio é `src/jobot/painel/static/js/app.js` (`app.js:1`), sem script inline (`padroes.md («JS do painel»)`).
- Visual de Mac (D143): lateral, barra de ferramentas, faixas de aviso opacas sob a barra, grupos opacos sem vidro no conteúdo, um botão principal por tela, tokens de `base.css`, ícones Lucide da versão fixada.
- Dia de calendário (prazo) compara com o dia local, não com UTC (`padroes.md («Dia de calendário»)`).
- Testes com a rede bloqueada e relógio injetado. Teste e fixture nunca têm e-mail de pessoa: só domínios reservados, como `example.com` e `example.org` (`padroes.md («Fixtures»)`).
- Conteúdo de terceiros (regra 14.3 da fase 1, `docs/superpowers/specs/2026-11-13-fase-1-design.md:1414`): link da descrição nunca vira clicável, e só "ver na fonte", "via <fonte>" e o de candidatura são clicáveis, e só em `http` ou `https`. O botão de e-mail da 5.7 é uma exceção a essa regra: está registrada na D147.22 e na D147.24, entra como nota na regra 14.3 e na ADR 0014 (5.9) e só vale para um endereço que passou pela lista fechada de caracteres da 5.7.

## 4. Como funciona hoje (fatos conferidos)

**Abas e contagens.**
- `leitura.ABAS` define as abas por SQL (`src/jobot/banco/leitura.py:28-36`):
  - "novas" é status Nova vista nos últimos 3 dias (`leitura.py:25`);
  - "fecham_logo" usa o prazo entre hoje e daqui a 7 dias (`leitura.py:27`);
  - "salvas" é `v.status = 'salva'`;
  - "candidatei" é `status IN ('candidatei','entrevista','recusada','oferta')` (`leitura.py:33`).
- `contar_abas(con, busca_id, agora)` conta cada aba com uma consulta `COUNT` (`leitura.py:429-441`).
- `contar_chips(con, f, agora)` conta por valor de cada chip: área, nível, modalidade, contrato, UF, fonte, encaixe e país (`leitura.py:65-74`, `:378`). Na aba Candidatei, conta também o grupo "status" (`_CHIPS_DA_ABA`, `leitura.py:75`).
- `grupos_dos_chips(con, estado, agora, idioma)` transforma essas contagens em grupos com rótulo, ordem (encaixe de bom a fraco; os outros do mais contado ao menos) e a URL de cada chip (`src/jobot/painel/rotas/vagas.py:306-342`).

**Busca escolhida.**
- `busca_efetiva` devolve a busca da URL ou, sem ela, a primeira ativa (`vagas.py:84-90`).
- O visual de Mac grava a escolha em `busca_escolhida` e usa a mesma busca nas contagens e nos links da lateral em toda página (D143.50, D144.E16).

**Status e histórico.**
- `vaga.status` aceita seis valores e tem um CHECK; `status_em` guarda a data da última troca (`0001_inicial.sql:85-87`).
- `mudar_status` (`src/jobot/banco/acoes.py:82-100`):
  - para trás grava `desfez`;
  - de Nova para Salva grava `salvou`;
  - o resto grava `mudou_status`;
  - status igual não grava nada.
- `_trocar_status` atualiza `status` e `status_em` e grava o evento com `de` e `para` (`acoes.py:73-79`). Os degraus estão em `_DEGRAU` (`acoes.py:20`).
- A rota `POST /vagas/{vaga_id}/status` chama a ação (`vagas.py:521-531`). O detalhe e a linha da lista montam os botões de próximo passo e de desfazer pelo mapa `proximos` e `anterior` (`detalhe/pagina.html:7-8,55-65`, `vagas/corpo.html:7-8,68-77`).

**Candidatar-se.**
- O detalhe escolhe o link: primeiro a `url_candidatura` http de alguma fonte; sem ela, a URL da vaga na fonte (`src/jobot/painel/rotas/detalhe.py:129,141-148`).
- O botão é `<a class="primario" target="_blank" rel="noopener noreferrer">` com a chave `detalhe.candidatar` (`detalhe/pagina.html:52-53`). Os textos são "Candidatar-se" e "Apply" (`i18n/pt/detalhe.json:10`, `i18n/en/detalhe.json:10`).
- A `url_candidatura` vem do JSON da ocorrência (`leitura.py:466-476`, `0001_inicial.sql:116`).
- `confere_http` recusa o que não é http(s) (`src/jobot/nucleo/modelo.py:118`), e `_confere_vaga` aplica essa regra à `url_candidatura` (`modelo.py:124-127`).
- O RemoteOK descarta em silêncio um `apply_url` fora de http(s), por exemplo `mailto:` (`src/jobot/nucleo/coletores/agregadores/remoteok.py:74-83`).
- A descrição fica em `vaga.descricao_texto` (`0001_inicial.sql:66`) e aparece no detalhe (`detalhe/pagina.html:155-160`), como texto puro: link dentro dela não vira clicável (regra 14.3 da fase 1, `2026-11-13-fase-1-design.md:1414`). A lista de fontes do detalhe está em `detalhe/pagina.html:73-80`.
- No detalhe, os botões de status são um `<form method="post">` sem nenhum atributo `hx-`: a rota responde 303 e a página recarrega (`detalhe/pagina.html:56-63`). Só o cartão da lista usa HTMX: com `HX-Request`, a rota de status devolve `vagas/corpo.html`, o corpo do cartão (`_resposta`, `vagas.py:498-519`).
- A listagem não lê `status_em`: `_COLUNAS` traz `v.status` e `v.primeira_vista_em`, mas não `v.status_em` (`leitura.py:86-99`), e o dataclass `Item` não tem esse campo (`leitura.py:130-163`); as linhas viram `Item` por `_item` (`leitura.py:343`, `:374`). `Detalhe` herda de `Item` (`leitura.py:174`) e também usa `_COLUNAS` (`leitura.py:456`).

**Execução e saúde.**
- `inicio_da_ultima_completa(con, tipo)` (`src/jobot/banco/execucoes.py:238`), `execucao_atual(con)` (`execucoes.py:263`) e `ultimas_que_rodaram(con)` (`execucoes.py:312`).
- O agendador roda a busca 3 horas depois do início da última completa (`src/jobot/agenda/agendador.py:21-25`).
- A tela de Fontes calcula o estado e a próxima rodada de cada fonte em `_cartoes` (`src/jobot/painel/rotas/fontes.py:136-236`).
- Os estados de saúde são `ok`, `sem_mudanca`, `parcial`, `falhou`, `desligada` e `no_limite` (`0001_inicial.sql:53`).

**Casca.**
- A faixa de versão se pede sozinha: `#aviso-versao hx-get="/aviso-versao" hx-trigger="load"` (`src/jobot/painel/templates/base.html:64`). A faixa de erro tem `role='alert'` (`base.html:68-71`).
- Contas acrescenta `#aviso-contas` logo depois da faixa de versão (desenho de Contas, 5.5).
- O visual de Mac fixa a ordem das faixas: erro, versão, contas, Desfazer (`docs/superpowers/specs/2026-11-15-visual-mac-design.md:231`).
- `app.js` põe o token CSRF no cabeçalho `X-CSRF-Token` de todo pedido do HTMX (`app.js:5-10`).
- O CSRF vale para todo método fora de GET, HEAD e OPTIONS (`src/jobot/painel/seguranca.py`). A CSP tem `connect-src 'self'` e `form-action 'self'`, e o painel manda `Referrer-Policy: no-referrer` (`app.py:19-25`).
- Datas na tela: `data_curta` e `data_completa` (`src/jobot/painel/formatos.py:84,92`).

## 5. O como

### 5.1 Onde o Panorama fica

- Rota `GET /panorama`, num arquivo próprio, `src/jobot/painel/rotas/panorama.py`. A página usa a casca do visual de Mac: lateral, barra com o título "Panorama" e grupos opacos na área de conteúdo, numa coluna só, no estilo dos Ajustes (D147.1).
- Na lateral, "Panorama" é o primeiro item, numa seção sem título acima de "Vagas", com `aria-current="page"` quando a tela está aberta. O item entra no ajudante único da lateral (D144.E4). Ícone Lucide `layout-dashboard`, conferido na versão fixada; se ele não existir, vale `gauge` (D147.1).
- `GET /` continua levando a Vagas, como hoje (`vagas.py:448-453`) (D147.2).
- A barra de ferramentas leva o mesmo menu pop-up de busca de Vagas. O Panorama segue a busca escolhida (D143.50): a busca da URL vence, depois a gravada, depois a primeira ativa. As contagens que dependem da busca usam essa busca. Salvas e Candidatei contam por status, sem a busca, como as abas fazem hoje (`leitura.py:32-33`) (D147.3).
- Os quatro grupos têm ordem fixa: Hoje, Candidaturas, A busca e O que aparece. Cada grupo tem um `<h2>` e uma seção com `aria-labelledby` (D147.4).
- Estado vazio: sem nenhuma linha na tabela `vaga` (função nova `tem_vaga(con)` em `banco/leitura.py`, `SELECT EXISTS(SELECT 1 FROM vaga)`), a tela mostra a frase com o caminho para a primeira busca e só o grupo A busca, que diz se a busca rodou e se alguma fonte falhou (tabela de estados, 5.10). "Buscar agora" continua na barra como o botão principal; o Panorama não ganha botão principal próprio.

### 5.2 Os quatro grupos

**Hoje** (D147.5)
- Cinco números grandes, com o rótulo embaixo e nesta ordem: Novas, Fecham logo, Salvas, Candidatei e Todas.
- Os números vêm de uma chamada a `contar_abas(con, busca_id, agora)` e os rótulos são as chaves `vagas.aba.*` que já existem.
- Cada número é um link para `/vagas?aba=<chave>` com a busca escolhida.
- Zero aparece como "0" e não some, ao contrário da lateral: aqui o zero informa.

**Candidaturas** (D147.6, D147.7)
- Contagem por passo, em texto: Candidatei, Entrevista, Oferta e Recusada.
  - Os números vêm do grupo "status" de `contar_chips(con, Filtros(aba="candidatei"), agora)` (`leitura.py:75`).
  - Os rótulos usam `vagas.status.*`.
  - Passo com zero mostra "0".
  - O status não é um filtro de Vagas, por isso os passos não viram link. O grupo termina com o link "Ver candidaturas" para a aba Candidatei.
- "Para responder" (âncora `#para-responder`):
  - lista as perguntas "Você se candidatou?" pendentes, da mais recente para a mais antiga, com os mesmos dois botões da faixa (5.6);
  - sem nenhuma pendente, mostra "Nenhuma pergunta esperando.".
- "Salvas que fecham em até 7 dias":
  - até 5 vagas salvas com prazo entre hoje e daqui a 7 dias, da que fecha primeiro para a que fecha por último;
  - cada uma com título, empresa e "fecha {data}", e link para `/vagas/{id}`;
  - o grupo termina com "Ver salvas";
  - a consulta é uma função nova em `banco/leitura.py`, `salvas_que_fecham(con, agora, limite)`, com a mesma expressão de prazo de `_FECHA_LOGO` (`leitura.py:27`) e o mesmo `:hoje` local, sem copiar a regra, e mais `v.fechada_em IS NULL`: a aba Salvas inclui vaga fechada na fonte (`leitura.py:32`, DR-24), e uma salva já fechada não pode aparecer como "fecha {data}" (`padroes.md («Dia de calendário»)`).

**A busca** (D147.8)
- Última busca completa: `inicio_da_ultima_completa(con, "busca")` (`execucoes.py:238`), mostrada com `data_completa`. Sem nenhuma, a frase diz "Nenhuma busca completa ainda.".
- Próxima busca automática: a mesma `agenda` que `_cartoes` já calcula (`fontes.py:147-151`): o início da última completa mais `INTERVALOS["busca"]` (`agendador.py:21-22`), e `None` quando não há busca completa ou quando o relógio voltou (início depois de `agora`, RF4). Esse cálculo sai de `_cartoes` para uma função compartilhada, por exemplo `proxima_busca(con, agora) -> datetime | None` num módulo de `painel/`, e `_cartoes` e o Panorama passam a chamar a mesma função, sem cópia (`padroes.md («Painel»)`). O Panorama mostra o valor arredondado ao minuto, como "por volta das {hora}". Com `None`, ou se essa hora já passou, a linha some: o agendador roda a busca logo.
- Com `execucao_atual(con)` (`execucoes.py:263`) rodando, a linha diz "Buscando agora." e o andamento continua na barra.
- Fontes com problema: quantas fontes ligadas têm estado `falhou` ou `parcial` nos cartões de Fontes, mais o link "Ver fontes". O cálculo vem de `_cartoes` (`fontes.py:136`), que fica pública e é reaproveitada sem cópia (`padroes.md («Painel»)`). Com zero, a linha depende do resto (D147.30):
  - "Todas as fontes funcionaram da última vez que rodaram." só quando existe busca completa (`inicio_da_ultima_completa` não é `None`) e todo cartão ligado está em `ok` ou `sem_mudanca`. O texto não fala "na última busca", porque o estado de cada cartão vem da última execução de qualquer tipo que gravou linha da fonte (`saude_recente`, sem filtro de tipo), e não só da busca;
  - nos outros casos (sem busca completa, ou com cartão ligado em `no_limite` ou `sem_execucao`), a linha some. `no_limite` e `sem_execucao` não contam como problema, como na tela de Fontes, mas também não deixam dizer que todas funcionaram.
- Contas que precisam de você: quantas contas têm a queda aberta, pela mesma consulta da faixa de Contas (desenho de Contas, 5.5; D146.E14), mais o link "Ver contas". Com zero, a linha some. Esta linha depende do lote Contas na `dev`.

**O que aparece** (D147.9, D147.10)
- Quatro blocos: Encaixe, Modalidade, Área e Fonte, contados na aba Todas da busca escolhida.
- Os dados vêm de `grupos_dos_chips(con, estado, agora, idioma)` (`vagas.py:306`). O `estado` não se monta à mão (`Estado` tem cerca de 16 campos, e o da busca é `busca_id`, `vagas.py:104-122`): sai de `ler_estado(params, con, ex)` (`vagas.py:189`), como em `vagas.py:460`, com os parâmetros de URL `aba=todas` e `busca={id}` da busca escolhida. Essa chamada já traz rótulo, ordem e a URL do chip. O Panorama só filtra os quatro grupos e corta.
- Encaixe mostra todos os níveis, de bom a fraco. Os outros blocos mostram os 5 maiores e terminam com "Ver em Vagas" para `/vagas?aba=todas`.
- Cada linha é um link para a URL do chip, com o rótulo, a barra e o número.
- Cada bloco abre com uma frase que resume o gráfico: "Mais comum: {valor}, com {n} de {total} vagas.". O `{total}` é a contagem da aba Todas. Na Fonte, uma vaga pode vir de mais de uma fonte, e a frase continua certa porque fala de uma fonte só.

### 5.3 As barras

- Desenho no servidor, sem JavaScript e sem biblioteca. A CSP recusa o atributo `style` (`app.py:20`), então cada barra é um SVG em linha: `<svg class="barra" aria-hidden="true" focusable="false"><rect width="{pct}%" height="100%"/></svg>`. A largura em porcentagem é um atributo de geometria do SVG, não estilo (D147.10).
- `{pct}` é o número da linha dividido pelo maior número do bloco, vezes 100, arredondado para inteiro. Linha com número maior que zero tem no mínimo 2%, para continuar visível.
- A barra é decorativa (`aria-hidden`). O número e o rótulo estão no texto do link, e o leitor de tela lê "Remoto, 120". A frase de resumo do bloco é o texto descritivo do gráfico (HIG, `charting-data`).
- Cor: `fill: var(--destaque)` sobre um trilho `--trilho-progresso`. O par entra no teste de contraste gráfico a 3:1 (D144.E11, `contraste-grafico`). Em `forced-colors`, o preenchimento vira `CanvasText`.
- Sem animação na entrada.

### 5.4 Datas de cada passo

- Sem esquema novo. Uma função nova em `banco/leitura.py`, `datas_dos_passos(con, vaga_id) -> Mapping[str, str]`, lê o histórico da vaga em `evento` (D147.12).
- Regra: para cada passo (`salva`, `candidatei`, `entrevista`, `oferta`, `recusada`), vale o `criado_em` do último evento com `para` igual ao passo e `acao IN ('salvou','mudou_status')`.
- Só entram os passos até o status atual pelo caminho Nova, Salva, Candidatei, Entrevista e depois Oferta ou Recusada (`_DEGRAU`, `acoes.py:20`).
- Oferta e Recusada valem o mesmo degrau, e `mudar_status` vai de uma para a outra com `mudou_status` (`acoes.py:82-100`). Do par, só o passo atual entra no caminho: com status Recusada, uma Oferta anterior não aparece, e vice-versa. O histórico completo continua em `evento`.
- Passo pulado (de Nova direto para Candidatei, por exemplo) não tem data e não aparece.
- Passo desfeito e não refeito fica fora, porque está acima do status atual.
- Passo desfeito e refeito mostra a data mais nova.
- O detalhe ganha a seção "Linha do tempo" (D147.13), uma lista em ordem com `data_curta`:
  - "Vista em {data}", pela `primeira_vista_em`;
  - "Abriu a candidatura em {data}", quando há registro de abertura (5.5);
  - um item por passo com data.
  
  A seção fica logo abaixo dos botões de status. No detalhe, a troca de status é um POST normal com 303 e a página recarrega (`detalhe/pagina.html:56-63`), então a linha do tempo sai certa sem nada extra. Este lote não põe HTMX no form de status do detalhe. Quando a troca vem da faixa (5.6), o bloco do status e da linha do tempo se pede de novo pelo evento `vaga-mudou-{id}` (D147.29).
- Na aba Candidatei, cada linha mostra "{status} desde {data}", pelo `status_em` que a vaga já guarda (`0001_inicial.sql:87`). A coluna não está na listagem hoje: o construtor acrescenta `v.status_em` em `_COLUNAS` (`leitura.py:86`) e o campo `status_em: str | None` em `Item` (`leitura.py:130`). `Detalhe` herda o campo. Com `status_em` nulo (vaga antiga), a linha mostra só o status, sem "desde".
- As datas não são editáveis nesta versão (D147.14).

### 5.5 Registro da abertura da candidatura

**Tabela nova** (R4, esquema; D147.15). Migração `0011_candidatura.sql`:

```sql
CREATE TABLE candidatura (                 -- quando a pessoa abriu a candidatura de uma vaga pelo painel
  vaga_id   INTEGER PRIMARY KEY REFERENCES vaga(id),  -- sem CASCADE: vaga nunca é apagada
  abriu_em  TEXT NOT NULL,                 -- a última vez que abriu
  perguntar INTEGER NOT NULL DEFAULT 1 CHECK (perguntar IN (0,1))  -- 1: a pergunta "Você se candidatou?" está aberta
);
CREATE TRIGGER candidatura_sem_delete BEFORE DELETE ON candidatura
BEGIN SELECT RAISE(ABORT, 'candidatura não é apagada'); END;
```

- Uma linha por vaga. Gravação só com `INSERT ... ON CONFLICT(vaga_id) DO UPDATE` (`padroes.md («Esquema»)`).
- O teste de migração confere a tabela, o CHECK e o gatilho, e segue `padroes.md («Teste de migração»)`.
- Alternativas recusadas:
  - uma ação nova em `evento`, que exige reconstruir a tabela e os gatilhos;
  - uma chave JSON em `config`, sem chave estrangeira e sem CHECK.

**Rota** (D147.17). `POST /vagas/{vaga_id}/candidatura` responde 204, sem corpo.
- Grava `abriu_em = agora` e `perguntar = 1` só se o status da vaga é Nova ou Salva. Com status Candidatei ou acima, responde 204 sem gravar.
- Vaga que não existe: `LookupError`, que vira 404 (contrato de `acoes.py`).
- A gravação fica numa função nova em `banco/acoes.py`, `abriu_candidatura(con, vaga_id, agora)`, sob `BEGIN IMMEDIATE` (`_transacao`).
- Abrir de novo atualiza `abriu_em` e reabre a pergunta.

**Clique** (D147.16).
- O link de candidatura (o http e o de e-mail, 5.7) ganha `data-candidatura="/vagas/{id}/candidatura"` e continua um link normal: `target="_blank"` para o http, `mailto:` para o e-mail.
- `app.js` escuta o clique por delegação no `document`. Em `a[data-candidatura]` ele chama `fetch(url, {method: "POST", keepalive: true, headers: {"X-CSRF-Token": token}})` e não chama `preventDefault`. O link abre como sempre.
- A CSP já permite o pedido (`connect-src 'self'`), e o CSRF é o do cabeçalho (`app.js:5-10`).
- Sem JavaScript, a abertura não é registrada, e a pessoa usa "Me candidatei" como hoje.
- Alternativa recusada: um `GET` local que registra e redireciona para a URL da vaga. Funciona sem JavaScript, mas é um GET com efeito, que outra página pode disparar, e o painel passaria a redirecionar para fora.

### 5.6 A pergunta "Você se candidatou?"

**Faixa** (D147.18).
- `base.html` ganha `<div id="aviso-candidatura" role="status" hx-get="/aviso-candidatura" hx-trigger="load, focus from:window" hx-include="find input[name=mostrando]" hx-swap="innerHTML"></div>`, depois de `#aviso-contas` e antes da faixa de Desfazer. O `div` fica fixo na página (a região `role="status"` existe antes do conteúdo mudar); só o conteúdo dele é trocado.
- A ordem das faixas passa a ser: erro, versão, contas, candidatura, Desfazer.
- O `focus from:window` faz a pergunta aparecer quando a pessoa volta à janela do joBot depois de se candidatar na outra aba.
- **A faixa não escuta `candidatura-mudou`.** No HTMX 2.0.11 fixado, o `HX-Trigger` da resposta dispara antes da troca (`static/vendor/htmx.min.js`, o `HX-Trigger` sai no `beforeOnLoad`; só `HX-Trigger-After-Swap` sai depois). Se a faixa escutasse o evento, o GET levaria a chave `mostrando` velha, a regra do 204 não valeria e a resposta trocaria a confirmação recém-mostrada: o "Desfazer" sumiria logo depois de aparecer, e depois de "Ainda não" a mesma faixa seria refeita, com novo anúncio do leitor de tela. A escuta é desnecessária: toda rota que dispara o evento (resposta e desfazer) já devolve e troca a própria faixa, inclusive quando o botão está em "Para responder" (que mira `#aviso-candidatura`). Só `#para-responder` escuta o evento.
- A rota `GET /aviso-candidatura` fica em `src/jobot/painel/rotas/aviso_candidatura.py`, no molde de `aviso_versao.py`.
  - A consulta busca a pergunta pendente mais recente: `perguntar = 1` e status da vaga Nova ou Salva, por `julianday(abriu_em)` decrescente, nunca pela ordem do texto: `abriu_em` é ISO com fuso, e fusos diferentes entre gravações (UTC e local, horário de verão) erram na ordem textual; o banco já compara por `julianday` (`leitura.py:25`). A consulta fica numa função nova em `banco/leitura.py`, `perguntas_pendentes(con, limite)`, que devolve as linhas e o total.
  - Sem pendente, a rota devolve um fragmento vazio.
  - **Sem troca à toa** (D147.18). Todo fragmento da faixa leva um `<input type="hidden" name="mostrando">` com a chave do que está à vista: `p{vaga_id}-{total}` para uma pergunta, `c{vaga_id}-{total}` para a confirmação com "Desfazer" e `v-0` para a faixa vazia; `{total}` é o número de pendentes. O `hx-include` manda essa chave no GET (o seletor estendido `find` existe no HTMX 2.0.11 fixado, `static/vendor/htmx.min.js`). A rota responde **204, sem corpo,** quando o total de pendentes é o mesmo da chave e: a chave é `p` com a mesma vaga no topo, ou a chave é `c` ou `v`. O HTMX 2.0.11 não troca nada num 204 (`responseHandling`, `static/vendor/htmx.min.js`). Assim a volta de foco à janela não refaz a faixa, o leitor de tela não anuncia a mesma pergunta de novo e um botão focado não some. A confirmação fica à vista até mudar o número de pendentes (a pessoa abriu outra candidatura ou respondeu outra pergunta) ou até a próxima página.
  - Erro do GET (5xx): o HTMX não troca o conteúdo nas respostas 4xx e 5xx, e a faixa fica como estava. Não há texto de erro próprio; a faixa de erro da casca segue como hoje.
- O texto da faixa:
  - "Você se candidatou a {titulo} ({empresa})?";
  - embaixo, menor: "Você abriu a candidatura {quando}.", com `data_completa`;
  - à direita, os botões "Sim, me candidatei" e "Ainda não";
  - com mais de uma pendente, o link "e mais {n} para responder" leva a `/panorama#para-responder`.
- A faixa não tem botão de fechar: "Ainda não" é o jeito de dispensar.
- Visual igual ao das outras faixas: opaca, ícone Lucide `circle-help` (conferir), texto de 13px.

**Respostas** (D147.19).
- `POST /vagas/{vaga_id}/candidatura/resposta` com o campo `resposta`, que vale `sim` ou `ainda_nao`. Outro valor responde 422.
- A gravação fica numa função nova em `banco/acoes.py`, `responder_candidatura(con, vaga_id, sim, agora)`, numa transação só:
  - `sim` troca o status para Candidatei pelo mesmo `_trocar_status` (`acoes.py:73`), com evento `mudou_status` e `de`/`para`, e grava `perguntar = 0`;
  - `ainda_nao` só grava `perguntar = 0`;
  - pergunta que já foi respondida, ou vaga que já está em Candidatei ou acima, não muda nada: a rota responde com a próxima pendente.
- A resposta HTMX troca o conteúdo da faixa e manda `HX-Trigger: candidatura-mudou, vaga-mudou-{vaga_id}`: o primeiro para o "Para responder" do Panorama se atualizar (a faixa já foi trocada pela própria resposta e não escuta o evento), o segundo para a vaga que está na tela se atualizar ("A vaga na tela", abaixo). A forma com vírgula dispara os dois eventos no HTMX 2.0.11 fixado. Depois de `ainda_nao`, a faixa mostra a próxima pendente, ou fica vazia. Depois de `sim`, a faixa mostra "{titulo} marcada como Candidatei." com o botão "Desfazer".
  - Desfazer em vez de confirmar (HIG, `undo-and-redo`).
  - **O "Desfazer" tem rota própria**, porque `POST /vagas/{id}/status` responde ao HTMX com `vagas/corpo.html`, o corpo do cartão da lista (`_resposta` em `painel/rotas/vagas.py`), que não serve para a faixa. A rota é `POST /vagas/{vaga_id}/candidatura/desfazer`, sem campo de status: o servidor não confia no formulário para saber para onde voltar (D147.19).
  - A gravação fica numa função nova em `banco/acoes.py`, `desfazer_candidatura(con, vaga_id, agora) -> bool`, sob `_transacao`. Ela lê o último evento de status da vaga (`acao IN ('salvou','mudou_status','desfez')` e `para IS NOT NULL`, porque o `desfez` de `trazer_de_volta` grava `de` e `para` nulos). Só quando esse evento é um `mudou_status` para `candidatei` vindo de `nova` ou `salva`, e o status atual é Candidatei, ela troca para o `de` dele pelo mesmo `_trocar_status` com a ação `desfez`, e devolve `True`. Em qualquer outro caso (a vaga já andou por outro caminho), não muda nada e devolve `False`. Ela não mexe em `perguntar`: a pergunta não volta.
  - Com HTMX, devolve o fragmento da faixa (a próxima pendente, ou a faixa vazia) com `HX-Trigger: candidatura-mudou, vaga-mudou-{vaga_id}`, também quando não mudou nada; o botão tem `hx-post` e `hx-target="#aviso-candidatura"`. Sem HTMX, responde 303 para o `voltar` do formulário, pelo `de_volta`.
- No Panorama, "Para responder" usa o mesmo trecho de template (com outro prefixo de id, seção 8) e as mesmas rotas de resposta. Os botões dele têm `hx-target="#aviso-candidatura"`: a confirmação com "Desfazer" aparece na faixa, no mesmo lugar de sempre. A lista fica num `<div id="para-responder" hx-get="/panorama/para-responder" hx-trigger="candidatura-mudou from:body">`, e essa rota devolve só a lista.
- A lista de "Para responder" vem renderizada pelo servidor na carga do Panorama (com `voltar=/panorama`); o `hx-get` só a refaz depois do evento.
- Sem JavaScript, os botões são um `<form method="post">` normal com o campo CSRF e o campo `voltar`, e a rota responde com 303 pelo `de_volta`, como as outras ações (`padroes.md («Tela com HTMX»)`). Na prática isso só vale para "Para responder": a faixa é preenchida só pelo `hx-get`, e sem JavaScript a abertura nem é registrada (5.5), então a faixa não aparece. É o esperado.
- **De onde sai o `voltar` da faixa** (D147.31). O painel manda `Referrer-Policy: no-referrer`, então a rota não tem `Referer`. O `GET /aviso-candidatura` lê o cabeçalho `HX-Current-URL` (o endereço da página, com esquema e host), pega o caminho e a consulta e passa pela mesma regra do `de_volta`: só caminho do próprio painel, sem esquema, sem host, sem `//` e sem `\`; fora disso, `/`. A regra sai do `de_volta` para uma função pequena em `painel/seguranca.py` (por exemplo `caminho_do_painel(url) -> str`), que o `de_volta` passa a usar, para as duas não se separarem (`padroes.md («Painel»)`). O valor vai no campo `voltar` dos dois formulários do fragmento.

**A vaga na tela** (D147.29). A pessoa costuma responder com o detalhe da mesma vaga aberto: só o detalhe tem o link de candidatura, ela abre a candidatura em outra aba e volta. Sem nada a mais, depois de "Sim" o detalhe continuaria com "Status: Salva", os botões do status velho e uma linha do tempo sem Candidatei; e o "Desfazer" velho do detalhe levaria a vaga de Candidatei direto para o `anterior` da tela, o que a pessoa não pediu. O mesmo vale para o cartão da vaga em Vagas.
- O evento é por vaga, `vaga-mudou-{vaga_id}`, porque o painel roda com `allowEval: false` (`base.html`) e o filtro de evento do HTMX (`[detail...]`) não está disponível; com um evento só, todos os cartões da lista (até 50) se pediriam de novo.
- **Detalhe.** O grupo `.acoes` e a seção "Linha do tempo" ficam dentro de `<div id="estado-da-vaga" hx-get="{{ retorno }}" hx-trigger="vaga-mudou-{id} from:body" hx-select="#estado-da-vaga" hx-swap="outerHTML">`. O `GET /vagas/{vaga_id}` já existe, não tem efeito colateral e devolve a página inteira; o `hx-select` tira dela só o bloco. Não há rota nova nem `data-foco`: o foco fica na faixa. O `hx-select` é herdado: filho que ganhar `hx-*` no futuro precisa de `hx-select="unset"`.
- **Cartão da lista.** O `<article id="vaga-{id}">` de `vagas/cartao.html` ganha `hx-get="/vagas/{id}/cartao?busca=…&voltar=…" hx-trigger="vaga-mudou-{id} from:body" hx-swap="innerHTML"`. A rota nova `GET /vagas/{vaga_id}/cartao` fica em `painel/rotas/vagas.py` e usa o mesmo `_resposta`, que ganha o parâmetro `foco: bool = True`; aqui vai `False`, para não tirar o foco da faixa.
- Sem corrida com o disparo antes da troca: o `HX-Trigger` sai no `beforeOnLoad`, mas a gravação já foi feita (a resposta só sai depois do `commit`), e esses dois blocos não usam a chave `mostrando`. O `GET` de cada um lê o banco já atualizado.
- Alternativa descartada: a resposta da faixa levar o bloco por `hx-swap-oob` quando `HX-Current-URL` aponta para a mesma vaga. Precisa decidir pela URL qual página está aberta, montar o contexto do detalhe dentro de outro módulo de rota, e gera `htmx:oobErrorNoTarget` quando o bloco não está na página. Dá mais código e mais caso de borda.

**Regras** (D147.20, D147.21).
- A data do passo Candidatei é a hora da resposta, porque é quando a pessoa disse. A hora em que ela abriu a candidatura aparece na linha do tempo, separada ("Abriu a candidatura em…").
- "Ainda não" não pergunta de novo, e não existe prazo para a pergunta expirar. Abrir a candidatura de novo pergunta de novo.
- Marcar Candidatei por outro caminho ("Me candidatei" no detalhe ou na lista) tira a vaga da pergunta, porque a consulta só traz status Nova ou Salva.

### 5.7 Candidatura por e-mail

**Achar o endereço** (D147.22).
- Função pura nova `src/jobot/nucleo/candidatura.py`, `email_de_candidatura(texto: str) -> str | None`. O detalhe chama a função na hora de mostrar, com `vaga.descricao_texto`. Sem esquema novo e sem reprocessar vagas.
- Regras:
  - procura um endereço por uma lista fechada de caracteres, em ASCII e com até 254 caracteres no todo:
    - a parte local só tem `A-Z`, `a-z`, `0-9`, `.`, `_`, `+` e `-`, com 1 a 64 caracteres;
    - o domínio tem dois ou mais rótulos separados por `.`, cada rótulo com 1 a 63 caracteres de `A-Z`, `a-z`, `0-9` e `-`, sem `-` no começo nem no fim;
    - o endereço precisa estar separado do resto: antes e depois dele só vale começo ou fim do texto, espaço, quebra de linha, `(`, `)`, `<`, `>`, `,`, `;`, `:` ou o ponto de fim de frase. Qualquer outro caractere encostado nele (`?`, `&`, `=`, `%`, `#`, `/`, aspas, letra fora de ASCII) o recusa inteiro: a função não corta o endereço para ele caber, ela recusa e segue para o próximo. Assim, nada que o texto traz vira `cc=`, `bcc=`, `body=` ou outro parâmetro no `mailto:` (`rh@example.com?cc=…`, `rh@example.com&bcc=…` e `rh%0A@example.com` são recusados);
  - o endereço só conta se estiver na mesma frase ou na mesma linha de uma palavra-gatilho de candidatura em pt, en ou es: currículo, curriculum, CV, candidat-, envie, enviar, mande, send, resume, apply, application, postula-, hoja de vida;
  - recusa endereços com `noreply` ou `no-reply` no nome;
  - devolve o primeiro que passar, sem o separador de fim e em minúsculas no domínio.
- A lista de gatilhos fica numa constante do módulo, com teste por idioma.
- O endereço não é guardado. Ele aparece só na tela da vaga, que já mostra a descrição inteira.

**Botões** (D147.23, D147.24).
- Prioridade, mantendo um botão principal só (D143):
  - com link http próprio de candidatura, ele continua o principal, e o e-mail, se achado, vira um botão secundário;
  - sem link http próprio e com e-mail achado, o principal vira "Candidatar-se por e-mail", e a vaga na fonte continua na lista de fontes do detalhe (`detalhe/pagina.html:73-80`);
  - sem nenhum dos dois, fica como hoje: o botão abre a vaga na fonte.
- **Exceção à regra 14.3** (D147.22, D147.24). A regra 14.3 da fase 1 diz que link da descrição nunca vira clicável e que só os links de fonte e de candidatura são clicáveis, em `http` ou `https` (`2026-11-13-fase-1-design.md:1414`). O botão de e-mail é a única exceção: um `href` com esquema `mailto:`, montado pelo joBot a partir de um endereço que passou pela lista fechada acima. O resto da descrição continua texto puro, e nenhum outro esquema é aceito. A exceção entra como nota na regra 14.3 e na ADR 0014 (5.9).
- O `href` é montado só com o endereço já validado, sem nenhum outro texto da descrição: `mailto:{endereço}?subject={titulo}`. O título passa pelo filtro `urlencode` do Jinja2 e é o único parâmetro; não há corpo, porque quem escreve é a pessoa. O endereço entra no `href` sem codificar, porque a lista fechada não tem nenhum caractere reservado de URL.
- O link tem `data-candidatura`, então o clique também registra a abertura (D147.26). Ele não tem `target`, porque o `mailto:` abre o programa de e-mail.
- Embaixo do botão vem o texto "Endereço para candidatura: {email}", que dá para selecionar, e o botão "Copiar endereço".
  - O botão vem com `hidden`, e o `app.js` tira o `hidden`. Sem JavaScript, o endereço continua à vista.
  - O `app.js` copia com `navigator.clipboard.writeText` (o painel em `127.0.0.1` é um contexto seguro) e escreve "Endereço copiado." numa região `role="status"` ao lado.
  - Se a cópia falhar, a região diz "Não deu para copiar. Selecione o endereço e copie.".
- Uma linha pequena explica: "O joBot não envia nada: o e-mail sai do seu programa de e-mail." (ADR 0001).

**Fora deste lote** (D147.25). O `mailto:` que a própria fonte manda no campo de candidatura continua descartado (`remoteok.py:74-83`). Aceitá-lo muda `confere_http` e o contrato de `VagaColetada` (`modelo.py:118-154`). É contrato público dos coletores, por isso vai como R4 (seção 10, P2).

### 5.8 Textos (i18n)

Arquivo novo `src/jobot/painel/i18n/{pt,en}/panorama.json`, mais chaves em `casca.json`, `detalhe.json` e `vagas.json`. Os rótulos das abas e dos status reaproveitam `vagas.aba.*` e `vagas.status.*`, e o "Desfazer" reaproveita `vagas.acao.desfazer`.

| Chave | pt | en |
|---|---|---|
| `casca.lateral.panorama` | Panorama | Overview |
| `panorama.titulo` | Panorama | Overview |
| `panorama.busca_contada` | Contando a busca {busca}. | Counting the search {busca}. |
| `panorama.sem_busca` | Nenhuma busca ativa: o encaixe não aparece. | No active search: fit isn't shown. |
| `panorama.vazio` | Ainda não há vagas. Aperte "Buscar agora" para fazer a primeira busca. | No jobs yet. Click "Search Now" to run the first search. |
| `panorama.hoje.titulo` | Hoje | Today |
| `panorama.candidaturas.titulo` | Candidaturas | Applications |
| `panorama.candidaturas.ver` | Ver candidaturas | View Applications |
| `panorama.responder.titulo` | Para responder | Waiting for Your Answer |
| `panorama.responder.vazio` | Nenhuma pergunta esperando. | No questions waiting. |
| `panorama.fecham.titulo` | Salvas que fecham em até 7 dias | Saved Jobs Closing Within 7 Days |
| `panorama.fecham.prazo` | fecha {data} | closes {data} |
| `panorama.fecham.vazio` | Nenhuma vaga salva fecha nos próximos 7 dias. | No saved jobs close in the next 7 days. |
| `panorama.fecham.ver` | Ver salvas | View Saved Jobs |
| `panorama.busca.titulo` | A busca | Search |
| `panorama.busca.ultima` | Última busca completa: {quando}. | Last complete search: {quando}. |
| `panorama.busca.nunca` | Nenhuma busca completa ainda. | No complete search yet. |
| `panorama.busca.proxima` | Próxima busca automática por volta das {hora}. | Next automatic search around {hora}. |
| `panorama.busca.rodando` | Buscando agora. | Searching now. |
| `panorama.busca.fontes_ok` | Todas as fontes funcionaram da última vez que rodaram. | All sources worked the last time they ran. |
| `panorama.busca.fontes_problema` | Fontes com problema: {n} | Sources with problems: {n} |
| `panorama.busca.ver_fontes` | Ver fontes | View Sources |
| `panorama.busca.contas` | Contas que precisam de você: {n} | Accounts that need you: {n} |
| `panorama.busca.ver_contas` | Ver contas | View Accounts |
| `panorama.aparece.titulo` | O que aparece | What Shows Up |
| `panorama.aparece.descricao` | Vagas abertas na busca, por encaixe, modalidade, área e fonte. | Open jobs in the search, by fit, work mode, area, and source. |
| `panorama.aparece.mais_comum` | Mais comum: {valor}, com {n} de {total} vagas. | Most common: {valor}, with {n} of {total} jobs. |
| `panorama.aparece.ver` | Ver em Vagas | View in Jobs |
| `casca.aviso_candidatura.pergunta` | Você se candidatou a {titulo} ({empresa})? | Did you apply to {titulo} ({empresa})? |
| `casca.aviso_candidatura.quando` | Você abriu a candidatura {quando}. | You opened the application {quando}. |
| `casca.aviso_candidatura.sim` | Sim, me candidatei | Yes, I Applied |
| `casca.aviso_candidatura.ainda_nao` | Ainda não | Not Yet |
| `casca.aviso_candidatura.mais` | e mais {n} para responder | and {n} more to answer |
| `casca.aviso_candidatura.marcada` | {titulo} marcada como Candidatei. | {titulo} marked as Applied. |
| `detalhe.passos.titulo` | Linha do tempo | Timeline |
| `detalhe.passos.vista` | Vista em {data} | Found {data} |
| `detalhe.passos.abriu` | Abriu a candidatura em {data} | Opened the application {data} |
| `detalhe.passos.salva` | Salva em {data} | Saved {data} |
| `detalhe.passos.candidatei` | Candidatei em {data} | Applied {data} |
| `detalhe.passos.entrevista` | Entrevista em {data} | Interview {data} |
| `detalhe.passos.oferta` | Oferta em {data} | Offer {data} |
| `detalhe.passos.recusada` | Recusada em {data} | Rejected {data} |
| `detalhe.candidatar_email` | Candidatar-se por e-mail | Apply by Email |
| `detalhe.candidatar_email_rotulo` | Candidatar-se por e-mail (abre o seu programa de e-mail) | Apply by email (opens your email app) |
| `detalhe.email.endereco` | Endereço para candidatura: {email} | Application address: {email} |
| `detalhe.email.copiar` | Copiar endereço | Copy Address |
| `detalhe.email.copiado` | Endereço copiado. | Address copied. |
| `detalhe.email.nao_copiou` | Não deu para copiar. Selecione o endereço e copie. | Couldn't copy. Select the address and copy it. |
| `detalhe.email.aviso` | O joBot não envia nada: o e-mail sai do seu programa de e-mail. | joBot doesn't send anything: the email goes out from your email app. |
| `vagas.linha.desde` | {status} desde {data} | {status} since {data} |

O texto "Buscar agora" e "Search Now" em `panorama.vazio` precisa bater com a chave do botão da barra; o construtor confere a chave real e o teste de i18n pega a diferença (`padroes.md («Texto de tela trocado»)`). Os títulos dos blocos de "O que aparece" usam os rótulos de grupo de chips que Vagas já tem.

### 5.9 Documentos

- `README.md` e `README.en.md`:
  - na descrição do painel (perto de `README.md:214`), uma linha sobre o Panorama e a fila: a pergunta, as datas e o e-mail;
  - na seção de privacidade, uma linha dizendo que o joBot guarda, só no computador da pessoa, quando ela abriu a candidatura de cada vaga.
- `wiki/Como-funciona.md` e `wiki/How-it-works.md`: as mesmas linhas, perto de `Como-funciona.md:124`.
- `CHANGELOG.md`, em "[Não lançado]": Panorama, linha do tempo, pergunta "Você se candidatou?" e candidatura por e-mail.
- `docs/decisions/0008-painel-e-visual.md`: uma nota com o item Panorama na lateral.
- `docs/decisions/0001-escopo-do-jobot.md`: uma nota de que o registro de abertura é local e que o botão de e-mail só abre o programa da pessoa.
- `docs/decisions/0014-seguranca-e-privacidade.md` e a regra 14.3 de `docs/superpowers/specs/2026-11-13-fase-1-design.md` (linha 1414): uma nota com a exceção do botão de e-mail (5.7): só `mailto:`, só um endereço que passou pela lista fechada de caracteres, montado pelo joBot, com o título como único parâmetro. Link da descrição continua não clicável.
- O Roteiro não muda, porque já promete os dois.

### 5.10 Estados e de onde vêm

Todo estado tem um teste em `tests/integracao/test_rota_panorama.py` (ou no arquivo da faixa, onde indicado).

| Estado | De onde vem | Hoje | Candidaturas | A busca | O que aparece | Teste |
|---|---|---|---|---|---|---|
| Antes da primeira execução | `config.primeira_execucao_concluida` falso, como em `raiz` (`vagas.py:450-451`) | `GET /panorama` responde 303 para `/primeira-execucao/1`, igual a `/` | (não aparece) | (não aparece) | (não aparece) | `test_antes_da_primeira_execucao_redireciona` |
| Banco sem vagas | `tem_vaga(con)` falso: nenhuma linha em `vaga`. Não é "Todas = 0": a aba Todas exclui fechadas, vencidas e ocultas (`_NA_LISTA`, `leitura.py:20-24, 29`), e Salvas e Candidatei contam por status sem esse filtro (`leitura.py:32-33`). Com vagas só fechadas ou ocultas, a tela fica normal e mostra os zeros | some; fica só a frase `panorama.vazio` | some | aparece (é onde a pessoa vê que a busca roda) | some | `test_banco_vazio_mostra_estado_vazio`, `test_so_vagas_fechadas_com_candidatura_nao_e_vazio` (Todas = 0, uma Candidatei e uma Salva fechadas com pergunta pendente: Hoje, Candidaturas e "Para responder" aparecem) |
| Sem busca ativa | `busca_efetiva` devolve `None` (`vagas.py:84-90`) | conta sem encaixe, então nenhuma vaga fica oculta por motivo, só as ocultas à mão (`_OCULTA` e `_DE` de `leitura.py`); o menu de busca some e a frase `panorama.sem_busca` toma o lugar de `panorama.busca_contada` | normal | normal | o bloco Encaixe some (sem busca, não há encaixe); os outros três ficam | `test_sem_busca_ativa_esconde_encaixe` |
| Nenhuma busca completa | `inicio_da_ultima_completa` devolve `None` | normal | normal | "Nenhuma busca completa ainda."; a linha da próxima busca some, e a frase `fontes_ok` não aparece mesmo com todo cartão ligado em `ok` (com fonte em `falhou` ou `parcial`, "Fontes com problema" continua) | normal | `test_sem_busca_completa`, `test_sem_busca_completa_sem_frase_de_fontes_ok` |
| Buscando | `execucao_atual` não é `None` | normal | normal | "Buscando agora."; a linha da próxima busca some | normal | `test_buscando_agora` |
| Relógio voltou | início da última completa depois de `agora` | normal | normal | `proxima_busca` devolve `None` e a linha some, como em Fontes (`fontes.py:150`) | normal | `test_proxima_com_relogio_que_voltou` |
| Fontes todas bem | existe busca completa e todo cartão ligado está em `ok` ou `sem_mudanca` | normal | normal | "Todas as fontes funcionaram da última vez que rodaram." | normal | `test_fontes_todas_ok` |
| Fonte no limite ou sem execução | nenhum cartão ligado em `falhou` ou `parcial`, e algum em `no_limite` ou `sem_execucao` | normal | normal | a linha das fontes some: não é problema, mas também não é "todas funcionaram" | normal | `test_fonte_no_limite_ou_sem_execucao_sem_frase` |
| Fontes com problema | cartões ligados em `falhou` ou `parcial` | normal | normal | "Fontes com problema: {n}" e "Ver fontes" | normal | `test_fontes_com_problema_conta_falhou_e_parcial` |
| Sem contas em queda | consulta da faixa de Contas sem queda aberta, ou lote Contas ausente | normal | normal | a linha de contas some | normal | `test_sem_contas_em_queda_sem_linha` |
| Contas em queda | consulta da faixa de Contas | normal | normal | "Contas que precisam de você: {n}" e "Ver contas" | normal | `test_contas_em_queda` |
| Sem pergunta pendente | `perguntas_pendentes` vazio | normal | "Nenhuma pergunta esperando." | normal | normal | `test_para_responder_vazio` |
| Erro no `GET /aviso-candidatura` | resposta 5xx | a faixa fica como estava (o HTMX não troca em 4xx e 5xx) | | | | `test_rota_aviso_candidatura.py::test_erro_nao_quebra_a_pagina` (a rota com o banco quebrado responde 500 com os cabeçalhos de segurança; a página continua) |

## 6. Riscos

- **Pergunta chata.** Quem abre muitas candidaturas de uma vez vê a faixa a cada volta à janela. Mitigação: uma faixa só, com "e mais {n}", e "Ainda não" dispensa de vez. Se incomodar, a próxima versão pode trocar o gatilho `focus from:window` só por `load`.
- **Leitor de tela e foco.** Refazer a faixa a cada volta de foco faria o leitor de tela anunciar a mesma pergunta de novo, dentro de `role="status"`, e tiraria o foco de um botão da faixa. Mitigação: a rota responde 204 quando o que está à vista não mudou (5.6, chave `mostrando`), e a confirmação com "Desfazer" fica até mudar o número de pendentes ou a página. Se a chave `mostrando` falhar (campo ausente), o pior caso é voltar ao comportamento de refazer a faixa, sem perder dado.
- **Endereço de e-mail como link.** O botão de e-mail é a única exceção à regra 14.3 (5.7). Mitigação: lista fechada de caracteres, separador obrigatório em volta do endereço, `href` montado só com o endereço validado e o título codificado, e testes de injeção (`?cc=`, `&bcc=`, `%0A`).
- **Falso positivo do e-mail.** O texto pode citar o e-mail de uma pessoa da empresa que não é para candidatura. Mitigação: a palavra-gatilho na mesma frase, a recusa de `noreply` e o endereço à vista antes de qualquer clique. O joBot não envia nada, então o pior caso é a pessoa abrir um e-mail para o endereço errado e ver o erro antes de enviar.
- **Sem programa de e-mail configurado.** No Linux, `mailto:` pode não abrir nada. O endereço à vista e o "Copiar endereço" cobrem esse caso.
- **Próxima busca imprecisa.** A previsão é o início da última completa mais 3 horas. Ela não sabe se o joBot está rodando em segundo plano nem se o computador vai estar ligado. Por isso o texto diz "por volta de", e a linha some quando a hora passa.
- **Custo do Panorama.** São mais de 30 consultas por abertura: 7 `COUNT` de `contar_abas` (um por aba, `leitura.py:429-441`); em cada uma das duas chamadas de `contar_chips`, uma consulta por chip e mais uma de "publicada" (`leitura.py:378-406`), cerca de 20 no total; e as de saúde de `_cartoes` (`saude_recente` e duas `ultimas_que_rodaram`, `fontes.py:137-139`). `grupos_dos_chips` também calcula todos os grupos, e o Panorama usa só 4. Se precisar, a contagem do grupo "status" pode vir de um `GROUP BY v.status` simples. Com dezenas de milhares de vagas, cada uma usa os índices que já existem (`0001_inicial.sql:92-95`). Se o tempo passar de 300 ms numa base grande, o construtor mede e registra o caso numa `Tn`, sem cache neste lote.
- **`keepalive` perdido.** Se o navegador fecha a janela no mesmo instante, o registro pode não chegar. O efeito é só não perguntar, e "Me candidatei" continua lá.
- **Dados pessoais.** A tabela `candidatura` diz em quais vagas a pessoa mostrou interesse. Ela fica no banco local, como o status, e não sai da máquina (ADR 0014).
- **Conflito de número de migração** com o visual e com Contas: a regra da D144.E3 resolve.

## 7. Testes esperados

Unidade (`tests/unidade/`):
- `test_email_de_candidatura.py`:
  - `test_acha_email_com_gatilho_pt`, `test_acha_email_com_gatilho_en`, `test_acha_email_com_gatilho_es`;
  - `test_ignora_email_sem_gatilho`, `test_ignora_noreply`, `test_tira_pontuacao_do_fim`, `test_recusa_endereco_longo`, `test_texto_vazio_devolve_none`;
  - `test_recusa_caracteres_de_query_no_local` e `test_recusa_caracteres_de_query_no_dominio` (`?cc=`, `&bcc=`, `=`, `%0A`, `#`, `/` encostados no endereço), `test_recusa_fora_de_ascii`, `test_recusa_rotulo_com_hifen_na_ponta`;
  - só endereços em `example.com` e `example.org`.
- `test_datas_dos_passos.py`:
  - `test_passos_em_ordem`, `test_passo_pulado_sem_data`, `test_desfeito_e_refeito_vale_o_mais_novo`, `test_desfeito_fica_fora`;
  - `test_salva_por_salvou`, `test_oferta_e_recusada_depois_de_entrevista`;
  - `test_oferta_depois_recusada` (de Oferta para Recusada: só Recusada aparece, com a sua data).
- `test_candidatura.py` (banco):
  - `test_abriu_grava_e_reabre_pergunta`, `test_abriu_com_candidatei_nao_grava`, `test_abriu_vaga_inexistente_lookuperror`;
  - `test_responder_sim_muda_status_e_fecha_pergunta`, `test_responder_sim_grava_evento_mudou_status`, `test_responder_ainda_nao_so_fecha`, `test_responder_duas_vezes_nao_muda_nada`;
  - `test_pendentes_so_nova_e_salva`, `test_pendentes_mais_recente_primeiro` (com `abriu_em` gravados em fusos diferentes);
  - `test_desfazer_volta_e_grava_desfez`, `test_desfazer_so_com_status_candidatei`, `test_desfazer_nao_reabre_pergunta`;
  - `test_desfazer_volta_ao_de_do_ultimo_evento` (de Nova, volta a Nova, e não ao anterior do fluxo; sem campo do formulário), `test_desfazer_ignora_desfez_da_ocultacao` ("Sim", `ocultar`, `trazer_de_volta` e depois `desfazer_candidatura` devolve `True` e volta o status).
- `test_salvas_que_fecham.py`: `test_prazo_hoje_ate_7_dias_dia_local`, `test_so_salvas`, `test_limite_e_ordem`, `test_salva_fechada_na_fonte_fica_fora`.
- `test_migracoes.py`:
  - a 0011 cria `candidatura` com CHECK e o gatilho sem DELETE (`test_candidatura_sem_delete`, `test_perguntar_so_0_ou_1`);
  - a versão conta os `.sql`.
- `test_camadas.py`: o `nucleo/candidatura.py` passa sem importar outra camada (o teste que já existe cobre).
- `test_i18n.py`: as chaves novas existem nos dois idiomas (o teste que já existe cobre).

Integração do painel (`tests/integracao/`):
- `test_rota_panorama.py`:
  - `test_quatro_grupos_em_ordem`, `test_numeros_hoje_batem_com_contar_abas`, `test_numero_e_link_para_a_aba_com_busca`;
  - `test_candidaturas_por_passo`, `test_para_responder_lista_pendentes`, `test_fecham_ate_5`;
  - `test_ultima_e_proxima_busca`, `test_proxima_some_quando_passou`, `test_proxima_com_relogio_que_voltou`, `test_fontes_com_problema_conta_falhou_e_parcial`;
  - `test_sem_busca_completa_sem_frase_de_fontes_ok` (controle: a mesma montagem com uma busca completa mostra a frase), `test_fonte_no_limite_ou_sem_execucao_sem_frase` (parametrizado: nem a frase nem "Fontes com problema");
  - `test_proxima_igual_a_de_fontes` (o Panorama e a tela de Fontes mostram a mesma próxima busca, pela função compartilhada);
  - `test_barras_sem_atributo_style`, `test_barra_aria_hidden_e_numero_no_texto`, `test_frase_mais_comum`;
  - `test_busca_escolhida_vale`, `test_lateral_tem_panorama_com_aria_current`;
  - um teste por linha da tabela de estados (5.10);
  - `test_ids_unicos_com_faixa_e_para_responder` (com uma pendente, a faixa e "Para responder" na mesma página não repetem nenhum `id`);
  - `test_para_responder_fragmento` (`GET /panorama/para-responder` devolve só a lista).
- `test_rota_aviso_candidatura.py`:
  - `test_sem_pendente_fragmento_vazio`, `test_mostra_a_mais_recente`, `test_e_mais_n_leva_ao_panorama`;
  - `test_resposta_sim_troca_status_e_dispara_evento` (os nomes do `HX-Trigger`, separados por vírgula, são exatamente `candidatura-mudou` e `vaga-mudou-{id}`), `test_resposta_invalida_422`, `test_resposta_sem_js_303`;
  - `test_voltar_sai_do_hx_current_url` (com `HX-Current-URL` de `/vagas/{id}?busca=…`, o campo `voltar` do fragmento é esse caminho com a consulta; com host de fora, `//`, `\` ou sem o cabeçalho, é `/`);
  - `test_desfazer_volta_ao_status_anterior_sem_reabrir`, `test_post_sem_csrf_recusado`;
  - `test_desfazer_devolve_fragmento_da_faixa` (com `HX-Request`, `POST /vagas/{id}/candidatura/desfazer` devolve o fragmento da faixa, não `vagas/corpo.html`, com `HX-Trigger` de nomes exatamente `candidatura-mudou` e `vaga-mudou-{id}`), `test_desfazer_ignora_campo_para` (um `para=salva` mandado à mão numa vaga que veio de Nova volta a Nova), `test_desfazer_sem_js_303`;
  - `test_mesmo_estado_responde_204` (com `mostrando` igual à pergunta do topo e o mesmo total), `test_confirmacao_fica_com_mesmo_total_204`, `test_pendente_nova_troca_a_faixa`.
- `test_rota_detalhe.py`:
  - `test_linha_do_tempo`, `test_link_de_candidatura_tem_data_candidatura`;
  - `test_email_vira_secundario_com_link_http`, `test_email_vira_principal_sem_link_http`, `test_mailto_com_assunto_codificado`;
  - `test_mailto_sem_parametro_injetado` (descrição com `rh@example.com?cc=outro@example.org`, `rh@example.com&bcc=…` e `%0A`: nenhum botão de e-mail; com endereço válido, o `href` tem só `subject` como parâmetro);
  - `test_sem_email_fica_como_hoje`, `test_copiar_vem_hidden`;
  - `test_detalhe_estado_escuta_a_vaga` (o `#estado-da-vaga` tem `hx-get` igual ao `retorno`, `hx-trigger="vaga-mudou-{id} from:body"`, `hx-select="#estado-da-vaga"` e `hx-swap="outerHTML"`, e contém o status e a linha do tempo).
- `test_rota_vagas.py`: `test_candidatei_mostra_desde`, `test_status_em_nulo_sem_desde` (vaga antiga com `status_em` nulo mostra só o status), `test_cartao_escuta_a_vaga` (o `<article id="vaga-{id}">` tem o `hx-get` de `/vagas/{id}/cartao` com `busca` e `voltar`, e `hx-trigger="vaga-mudou-{id} from:body"`), `test_cartao_get_devolve_corpo_sem_foco` (com `HX-Request`, o status atual e nenhum `data-foco`; controle: o `POST /vagas/{id}/status` continua com `data-foco`).
- `test_rota_candidatura.py`: `test_post_204`, `test_post_vaga_inexistente_404`, `test_post_sem_csrf_recusado`.
- `test_estaticos.py` / `test_contraste.py`: o ícone novo no `lucide.meta.json` e o par da barra no teste gráfico.

Tela (`-m tela`, Playwright, no Actions):
- `test_tela_pergunta_candidatura.py`:
  - clicar em "Candidatar-se" abre a aba nova e registra a abertura;
  - voltar à janela mostra a faixa;
  - "Sim, me candidatei" muda o status, e "Desfazer" volta;
  - depois de "Sim, me candidatei", com a rede parada, "Desfazer" continua visível e não há um segundo `GET /aviso-candidatura` com troca (o mesmo com o botão de "Para responder" no Panorama e uma pergunta na faixa);
  - o link de candidatura aponta para um servidor local de teste, nunca para a rede.
- `test_tela_cartao_atualiza_depois_da_faixa`: em Vagas, "Sim" na faixa atualiza o status do cartão da vaga, sem tirar o foco da faixa, e "Desfazer" volta.
- `test_tela_detalhe_atualiza_depois_da_faixa`: no detalhe de uma vaga Salva com pergunta pendente, "Sim, me candidatei" na faixa e a espera pelo `GET` do detalhe (`expect_response`); a `.situacao` diz Candidatei, o botão com `value="nova"` some e o de próximo passo é Entrevista; depois, "Desfazer" na faixa volta a Salva e o botão de desfazer do detalhe volta a ter `value="nova"`.
- `test_tela_copiar_email.py`: o botão aparece com JavaScript e escreve "Endereço copiado.".
- `test_tela_panorama.py`: navegação por teclado pelos links dos números e das barras, e o foco visível.

## 8. O que fica para o construtor

- O nome exato do ícone Lucide do Panorama e da faixa, na versão fixada (o padrão é `layout-dashboard` e `circle-help`).
- O CSS dos grupos, dos números grandes e das barras, com os tokens de `base.css` (tamanho do número, espaço entre blocos, altura da barra). Os números entram como "proposta" no plano, como no visual.
- A lista final de palavras-gatilho do e-mail, mantendo pt, en e es e um teste por idioma.
- Onde fica o trecho de template da pergunta, que é compartilhado entre a faixa e o Panorama (por exemplo `templates/candidatura/_pergunta.html`). O trecho recebe um prefixo de id (`faixa` ou `responder`), e todo `id` e `aria-labelledby` dele leva esse prefixo e o id da vaga, para não repetir id quando a faixa e "Para responder" estão na mesma página.
- Como `_cartoes` de Fontes vira pública: nome e módulo, sem cópia. O cálculo da próxima busca sai de `_cartoes` (`fontes.py:147-151`) para a função compartilhada da 5.2, com o mesmo caso do relógio que voltou, e `_cartoes` passa a chamá-la.
- A listagem ganha `status_em`: `v.status_em` em `_COLUNAS` (`leitura.py:86`) e `status_em: str | None` em `Item` (`leitura.py:130`), que `Detalhe` herda. Conferir quem monta `Item` e `Detalhe` à mão nos testes.
- As rotas novas sob `/vagas/` (`/candidatura`, `/candidatura/resposta`, `/candidatura/desfazer`) moram num módulo registrado antes de `detalhe.py`, senão `/vagas/{vaga_id}` responde 422 (`padroes.md («Painel»)`).
- O `Estado` de `grupos_dos_chips` no Panorama sai de `ler_estado` com `aba=todas` e `busca={id}` (5.2), não de um `Estado(...)` montado à mão.
- As chaves reais dos rótulos de grupo dos chips e do botão "Buscar agora", para reaproveitar.

## 9. Pontos que batem com o que já existe

- As contagens do Panorama são as mesmas da lateral e das abas (`contar_abas`) e dos chips (`grupos_dos_chips`). Um número no Panorama nunca diverge da tela de Vagas.
- A troca de status da resposta "Sim" e a do "Desfazer" da faixa passam pelo mesmo `_trocar_status`, com os mesmos eventos (`mudou_status` e `desfez`). O "Desfazer" da faixa tem rota própria só porque a resposta HTMX de `POST /vagas/{id}/status` é o corpo do cartão da lista (`_resposta` em `painel/rotas/vagas.py`).
- A vaga na tela se atualiza com o que já existe: o detalhe pede de novo o próprio `GET /vagas/{id}` e tira o bloco com `hx-select`; o cartão usa o mesmo `_resposta` dos botões da lista, com `foco=False`.
- O `voltar` da faixa passa pela mesma regra do `de_volta`, numa função só.
- A próxima busca do Panorama e a de Fontes saem da mesma função (5.2).
- A faixa nova segue o molde de `#aviso-versao` e `#aviso-contas`: uma rota própria, um fragmento vazio quando não há o que dizer, opaca e na ordem fixa das faixas.
- A busca escolhida é a do visual (D143.50). O Panorama não cria regra nova de busca.
- O registro do clique usa o token CSRF do `app.js` e o `_transacao` do banco, sem mecanismo novo.
- A candidatura por e-mail respeita a ADR 0001 como a "Candidatar-se" de hoje: o joBot só abre, a pessoa envia.

## 10. Perguntas pendentes

- **P1 (R4, esquema).** Aprovar a tabela `candidatura` na 0011 (5.5). Opções: (a) a tabela nova; (b) uma ação nova em `evento`, reconstruindo a tabela e os gatilhos; (c) nada no banco, e a pergunta não existe. Recomendo (a).
- **P2 (R4, contrato dos coletores).** Aceitar `mailto:` no campo de candidatura que a fonte manda. Opções: (a) deixar fora, como agora; (b) um campo novo `email_candidatura` em `VagaColetada`, validado à parte, com os coletores que o têm passando a preencher; (c) afrouxar `confere_http` para aceitar `mailto:` na `url_candidatura`. Recomendo (a) neste lote e (b) numa `Tn` depois, se aparecer fonte que mande e-mail. A (c) mexe na regra 14.3 para todo coletor e para todo esquema que passar por `confere_http`; a exceção da 5.7 é bem mais estreita: só `mailto:`, só no botão que o joBot monta e só com o endereço que passou pela lista fechada de caracteres.
- **P3.** Panorama como tela inicial. Opções: (a) `/` continua em Vagas; (b) `/` vai para o Panorama. Recomendo (a), porque o uso diário é a lista. Mudar depois é uma linha em `raiz`.
- **P4.** A data do passo Candidatei. Opções: (a) a hora da resposta, com a abertura mostrada à parte; (b) a hora da abertura, o que grava um evento com data anterior a outros. Recomendo (a).
- **P5.** O registro do clique. Opções: (a) `fetch` com `keepalive` no `app.js`, que exige JavaScript; (b) um `GET` local que registra e redireciona, que funciona sem JavaScript mas é um GET com efeito. Recomendo (a).

## 11. Todas as decisões da D147

Todas da sessão, para confirmar com o dono.

1. **D147.1** Panorama em `GET /panorama`, primeiro item da lateral numa seção sem título acima de "Vagas", título "Panorama"/"Overview", ícone Lucide `layout-dashboard` (ou `gauge`).
2. **D147.2** `GET /` continua levando a Vagas (P3).
3. **D147.3** O Panorama segue a busca escolhida, com o mesmo menu pop-up de Vagas; Salvas e Candidatei contam sem busca, como as abas.
4. **D147.4** Quatro grupos fixos, nesta ordem: Hoje, Candidaturas, A busca e O que aparece. Sem personalizar.
5. **D147.5** Hoje: Novas, Fecham logo, Salvas, Candidatei e Todas, por `contar_abas`; cada número é um link para a aba; zero aparece.
6. **D147.6** Candidaturas por passo pelo grupo "status" de `contar_chips(aba="candidatei")`, em texto, sem link por passo, com "Ver candidaturas".
7. **D147.7** "Para responder" lista todas as pendentes; "Salvas que fecham em até 7 dias" mostra até 5, por prazo, pela função nova `salvas_que_fecham`, sem vaga já fechada na fonte. O estado vazio do Panorama é "nenhuma linha em `vaga`" (`tem_vaga`), nunca "Todas = 0".
8. **D147.8** A busca: última completa, próxima "por volta das" (última completa mais 3 horas, some quando passa), "Buscando agora", fontes com `falhou` ou `parcial` pelos cartões de Fontes, e contas em queda (depende de Contas). A próxima busca sai de uma função compartilhada com Fontes, extraída de `_cartoes`, com o caso do relógio que voltou. Os estados de cada grupo estão na tabela da 5.10.
9. **D147.9** O que aparece: Encaixe (todos os níveis), Modalidade, Área e Fonte (5 maiores), por `grupos_dos_chips` na aba Todas, cada linha como link para o chip, e uma frase "Mais comum" por bloco.
10. **D147.10** Barras em SVG em linha com `<rect width="%">`, `aria-hidden`, o número no texto, no mínimo 2%, cor `--destaque` sobre `--trilho-progresso`, sem animação e sem atributo `style`.
11. **D147.11** O Panorama não se atualiza sozinho enquanto está aberto, fora o "Para responder", que segue o evento `candidatura-mudou`. Fora do Panorama, o status e a linha do tempo do detalhe e o cartão da lista seguem o evento da própria vaga (D147.29).
12. **D147.12** Datas dos passos tiradas de `evento`, sem esquema: o último `salvou` ou `mudou_status` com `para` igual ao passo, só até o status atual; passo pulado não aparece; de Oferta e Recusada, só o passo atual aparece.
13. **D147.13** "Linha do tempo" no detalhe: vista, abertura da candidatura e um item por passo com data; "{status} desde {data}" na linha da aba Candidatei, pelo `status_em`, que entra em `_COLUNAS` e `Item`; com `status_em` nulo, sem "desde". No detalhe, a troca de status segue POST com 303, sem HTMX.
14. **D147.14** As datas não são editáveis nesta versão.
15. **D147.15** Tabela `candidatura` (`vaga_id`, `abriu_em`, `perguntar`) na `0011_candidatura.sql`, com gatilho sem DELETE e gravação com `ON CONFLICT` (P1).
16. **D147.16** O clique é registrado por `fetch` POST com `keepalive` e o cabeçalho CSRF no `app.js`, por delegação em `a[data-candidatura]`, sem impedir o link; sem JavaScript, não registra (P5).
17. **D147.17** `POST /vagas/{id}/candidatura` responde 204 e só grava com status Nova ou Salva; vaga inexistente dá 404; abrir de novo reabre a pergunta.
18. **D147.18** A pergunta fica na faixa `#aviso-candidatura`, depois de Contas e antes de Desfazer, com `hx-trigger="load, focus from:window"`, sem escutar `candidatura-mudou` (o `HX-Trigger` dispara antes da troca e levaria a chave `mostrando` velha, apagando o "Desfazer"; quem dispara o evento já troca a faixa). Ela mostra a mais recente, tem "e mais {n}" para o Panorama e não tem botão de fechar. A rota responde 204 quando o que está à vista (campo `mostrando`) não mudou, para não refazer a faixa a cada foco.
19. **D147.19** `POST /vagas/{id}/candidatura/resposta` com `sim` ou `ainda_nao`, numa transação; `sim` troca o status para Candidatei com `mudou_status` e mostra "marcada como Candidatei" com "Desfazer"; outro valor dá 422; sem JavaScript, responde 303. O "Desfazer" tem rota própria, `POST /vagas/{id}/candidatura/desfazer`, sem campo de status: o servidor volta ao `de` do último evento de status (com `para` não nulo), só quando ele é um `mudou_status` de Nova ou Salva para Candidatei e o status ainda é Candidatei; grava `desfez`, devolve o fragmento da faixa e não reabre a pergunta. Os botões de "Para responder" no Panorama miram a faixa.
20. **D147.20** A data do passo Candidatei é a hora da resposta; a abertura aparece à parte na linha do tempo (P4).
21. **D147.21** "Ainda não" não pergunta de novo e a pergunta não expira; abrir de novo pergunta de novo; marcar Candidatei por outro caminho tira a vaga da pergunta.
22. **D147.22** O e-mail é achado pela função pura `nucleo/candidatura.email_de_candidatura` na descrição, na hora de mostrar, só com palavra-gatilho na mesma frase ou na mesma linha (pt, en, es) e sem `noreply`; o endereço não é guardado. Lista fechada de caracteres: local `A-Za-z0-9._+-`, domínio com rótulos `A-Za-z0-9-` separados por pontos; o endereço não tem espaço, em volta dele só valem os separadores da 5.7, e `?`, `&`, `=`, `%`, `#`, `/` ou caractere fora de ASCII encostados recusam o endereço inteiro.
23. **D147.23** Prioridade dos botões: o link http próprio é o principal, e o e-mail fica secundário; sem link http próprio, o e-mail vira o principal; sem nenhum dos dois, fica como hoje.
24. **D147.24** O botão de e-mail usa `mailto:` com o assunto igual ao título (passado por `urlencode`, único parâmetro), sem corpo, montado só com o endereço validado. É a única exceção à regra 14.3 da fase 1 (link de terceiro só em http ou https), registrada como nota na regra 14.3 e na ADR 0014. O endereço fica à vista, com "Copiar endereço" por JavaScript (vem `hidden`), e uma linha diz que o joBot não envia nada.
25. **D147.25** O `mailto:` mandado pela fonte fica fora deste lote (P2).
26. **D147.26** O clique no botão de e-mail também registra a abertura.
27. **D147.27** Ordem: o lote vem depois do lote Contas (T269 a T279) e do portão T258 do visual. O lado de trás (migração 0011, funções de `banco` e `nucleo`) pode entrar na `dev` antes, sem mudar tela. As telas entram juntas e fecham a 0.3.0.
28. **D147.28** Privacidade: a tabela `candidatura` fica só no banco local; README e wiki ganham uma linha sobre isso.
29. **D147.29** Depois de "Sim" ou "Desfazer" na faixa, a vaga na tela se atualiza: as duas rotas mandam também o evento `vaga-mudou-{id}`; no detalhe, `#estado-da-vaga` (status e linha do tempo) pede de novo o próprio `GET /vagas/{id}` com `hx-select`; na lista, o cartão pede `GET /vagas/{id}/cartao`, rota nova que usa `_resposta` com `foco=False`. Evento por vaga porque `allowEval: false` tira o filtro de evento. Sem `hx-swap-oob`.
30. **D147.30** A frase das fontes: "Fontes com problema: {n}" com `falhou` ou `parcial`; "Todas as fontes funcionaram da última vez que rodaram." só com busca completa e todo cartão ligado em `ok` ou `sem_mudanca`; nos outros casos (`no_limite`, `sem_execucao`, sem busca completa), a linha some.
31. **D147.31** O `voltar` da faixa sai do `HX-Current-URL` (caminho e consulta), pela mesma regra do `de_volta`, numa função de `painel/seguranca.py` que as duas usam; fora da regra, `/`. Sem JavaScript a faixa não aparece; "Para responder" vem renderizada pelo servidor na carga do Panorama.
