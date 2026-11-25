# Fase 8: versão GitHub Pages (desenho)

Data: 2026-11-24. Decisões de origem: ADR 0002 (duas versões, um núcleo: a base desta fase), 0004 e 0005 (coleta educada; nada com login), 0007 (regras em Python e em JavaScript), 0014 (sem telemetria), 0016 (sala limpa), 0017 (fases), 0018 (CI aberto, vigia), 0021 (dependências à mão), 0023 e 0026 (IA da fase 4); D218 (vigia que se reativa), D219.14 (termos lidos para o treino do Laya), D229 (IA manual). Ordem nova das fases: **D238** (decidida pelo dono em 2026-11-24: a fase 8 vem antes da fase 5; os números não mudam). Escolhas desta sessão: **D239** (escolha da sessão, para discutir com o dono). Versões alvo: **0.7.0** e **0.8.0** (D239.20).

Fatos sobre o código citam o símbolo e o arquivo, conferidos na `dev` em `d16de121` (2026-11-24, a T440 juntada; a release 0.6.0 corre em paralelo e este desenho não mexe nela). Quando a linha andar, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar. **Nenhum lote da fase 8 entra na `dev` antes da tag `v0.6.0`**, para nada desta fase sair na 0.6.0, e a fase só começa a ser construída depois que a fase 4 passa nos testes (ADR 0017, Consequências).

## 1. Intenção

Quem não quer instalar nada abre um endereço no navegador e vê as vagas das fontes públicas, atualizadas uma vez por dia, com os mesmos filtros, o mesmo visual e o mesmo encaixe por regras da versão local. O perfil, as buscas e o status de cada vaga ficam só no navegador da pessoa, e o arquivo exportado dali abre na versão local. Toda página diz, numa faixa no topo, que a versão para baixar é mais completa (ADR 0002).

O site é estático: não há servidor nosso. O GitHub Actions coleta, trata e publica; o navegador do visitante filtra e calcula o encaixe. Nada do visitante sai do navegador dele.

**Duas versões** (D239.20). A **0.7.0** traz a coleta diária, o site com filtros, o encaixe em JavaScript com paridade testada, o perfil e as buscas no navegador, exportar e importar compatível com a versão local, a faixa e um feed Atom das vagas novas. A **0.8.0** traz a IA manual (copiar e colar) no site e o canal do Discord, que depende do dono (seção 11).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos (0.7.0)**

- Coleta diária no GitHub Actions, só com fontes públicas, sem segredo, no ritmo da ADR 0004, reaproveitando o executor, o tratamento e os rótulos do núcleo sem cópia (seção 6).
- Política de publicação por fonte, num arquivo de dados com a data e o trecho dos termos lidos: texto inteiro só onde o termo permite; senão só título, empresa, local, data, rótulos e o link para a vaga original; fonte sem anotação fica fora (seção 5).
- Ramo `dados` sobrescrito a cada dia, reativação do agendamento pela API (D218), tamanho com teto e retenção curta (seção 6).
- Site estático em português e inglês, com o visual do painel, sem recurso externo, com CSP e acessível (seção 7).
- Encaixe por regras em JavaScript, com paridade testada contra `nucleo/encaixe.py` sobre casos gerados e casos de borda (seção 8).
- Perfil, buscas e status por vaga no `localStorage`; exportar e importar um arquivo `jobot-perfil` que a versão local também lê e grava (seção 9).
- Feed Atom das vagas novas do dia, só das fontes cujos termos não proíbem repassar (seção 11).

**Objetivos (0.8.0)**

- IA manual no site para `curriculo`, `perguntas` e `candidatura`, com o mesmo texto para copiar e a mesma conferência da resposta colada da versão local (D229), sem chave nem serviço (seção 10).
- Canal do joBot no Discord que qualquer servidor segue, sem bot nosso ligado 24 horas e sem segredo por servidor (seção 11; espera o dono).

**Não objetivos**

- Sites com login, Gmail, extensão, IA automática, áudio, segundo plano (ADR 0002).
- A chave do visitante para um serviço de IA (Haiku): fica para depois desta fase (D239.17).
- Rótulos e tratamento em JavaScript: rodam no Actions, em Python, e o site recebe o resultado (D239.9).
- Habilidades por IA nas vagas do site (o Laya rodando no Actions): só depois de medir tempo e custo de CPU (D239.18).
- Fontes que pedem termos de busca (o site não conhece as buscas de ninguém): ficam para depois da 0.7.0 (D239.6).
- Busca por texto inteiro com índice (FTS5): o site filtra por texto normalizado em título, empresa e, quando publicado, no texto.
- Arquivo histórico das vagas: o site é um retrato do dia, não um acervo.

**Anti-objetivos**

- Qualquer dado do visitante (perfil, buscas, status, texto colado) saindo do navegador por conta do site.
- Analytics, cookies, fontes ou scripts de terceiros, CDN.
- Segredo no repositório ou no workflow do Pages (ADR 0002, Consequências).
- Republicar texto de vaga onde o termo da fonte não permite, ou contornar bloqueio, CAPTCHA ou limite de uma fonte.
- Cópia da lógica do núcleo em Python para outro lugar em Python: o Actions chama o núcleo de verdade.

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py`): nada muda nas camadas de `src/jobot`. O código da fase fica fora do pacote: scripts de CI em `scripts/` (como o `scripts/vigia.py`) e a fonte do site em `web/` (proposta, D239.11). A exportação e importação do perfil na versão local mora em `banco` (formato) e `painel` (botões), nas camadas de hoje.
- Dependências fixadas com `==` e sem dependência nova sem decisão (ADR 0021). Nenhuma entra: o site é JavaScript puro, sem framework, sem bundler e sem `npm`; o build usa o Jinja2 que já está no projeto; os testes do JavaScript rodam no Chromium do Playwright, que já está no projeto (D239.11, D239.21). As Actions oficiais do GitHub para o Pages (`actions/upload-pages-artifact`, `actions/deploy-pages`) entram fixadas por hash, com a versão em comentário (`test_actions_fixadas_por_hash`).
- Testes sem rede (`tests/conftest.py`): a coleta do Pages roda nos testes só com transporte falso e fixtures; o site de teste é servido em `127.0.0.1`.
- Sala limpa (ADR 0016): nada de código ou dado de terceiros; os casos de paridade são gerados das nossas fixtures.
- Conteúdo de vaga é dado, nunca instrução: no site ele entra por `textContent`, nunca por `innerHTML` (seção 7.4).
- O repositório é público: o workflow roda só por agenda, à mão e em push na `main`; nunca em PR, nunca com `pull_request_target` (ADR 0018).

## 4. O que já existe (fatos levantados)

| Peça | Onde está | Serve ao Pages como |
|---|---|---|
| Coletores das fontes públicas, um por arquivo | `nucleo/coletores/{agregadores,carreiras,plataformas,portais}/`, `registro.descobrir()` | reaproveitados sem mudança, pelo executor |
| Executor de uma busca, com saúde e ciclo de vida | `agenda.execucao.executar_busca(con, cliente, relogio, "agora")`, usado por `cli/buscar.py` | a coleta do Pages roda isto num banco temporário |
| Ritmo por fonte | `nucleo/dados/fontes.json` (`intervalo_min`, `max_pedidos`, `espera_s`, `credito_obrigatorio`), `nucleo/http.ClienteEducado` | o mesmo ritmo e o mesmo user agent fixo do joBot |
| Empresas dos ATS | `nucleo/dados/empresas.json` (83 empresas: 28 da Gupy, 15 Greenhouse, 11 SmartRecruiters, 8 Lever, 5 Ashby e outras), `banco.cadastros.empresas_iniciais()` | a lista de escopos das plataformas |
| Tratamento e rótulos | `nucleo/tratamento/tratar.tratar`, `rotulos.rotular` (regras em `dados/rotulos.json`), `locais.py`, `salario.py`, `estagio.py` | rodam no Actions; o site recebe os rótulos prontos |
| Cotação PTAX | `nucleo/cambio.py` (consulta pública do Banco Central) | o Actions publica o salário mensal em reais já convertido |
| Encaixe por regras | `nucleo/encaixe.calcular` (cargo, local, nível, salário, idioma, habilidades; regras de ocultar em `_regra_que_bate`), pesos em `dados/encaixe.json` | porta para JavaScript, com paridade (seção 8) |
| Normalização de texto | `nucleo/texto.normalizar` (NFD sem marcas, `casefold`, espaços simples, apóstrofo curvo vira reto), `sem_pontas` | porta para JavaScript, com casos de borda |
| Buscas | `modelo.Busca` (cargos, cidades, modalidades, níveis, salário mínimo e moeda, idiomas, regras de ocultar) | o visitante cria as dele no navegador |
| Status da vaga | `vaga.status` em `banco/migracoes/0001_inicial.sql` (`nova`, `salva`, `candidatei`, `entrevista`, `recusada`, `oferta`); ocultar à mão em `evento.acao` | os mesmos valores no navegador |
| Perfil | migrações `0012_ia.sql` (habilidades) e `0013_perfil.sql` (contato, cargo, anos, formação, resumo, idiomas, links, experiências, cursos, perguntas) | o mesmo conteúdo no navegador e no arquivo exportado |
| Exportar/importar o perfil | **não existe** na versão local (os READMEs deixaram de prometer na T440, D236.3) | nasce nesta fase, nos dois lados (seção 9) |
| IA manual | `nucleo/ia/manual.texto_para_copiar(pedido, idioma)` e `ler_resposta(pedido, colado)`; só `curriculo`, `perguntas`, `candidatura` (D229) | porta para JavaScript na 0.8.0, com paridade (seção 10) |
| Esquemas das respostas da IA | modelos pydantic em `nucleo/ia/esquema.py`; o texto para copiar usa o esquema sem as descrições (D229.6) | o Python exporta o JSON Schema no build; o JavaScript só o lê (D239.16) |
| Visual e textos do painel | `painel/static/css/*.css`, `static/fontes/` (Inter vendorizada), `static/icones/`, catálogos `painel/i18n/{pt,en}/*.json` | o build copia os arquivos; os motivos `encaixe.*` saem do mesmo catálogo |
| Agendamento que se reativa | `vigia.yml`, último passo `gh api -X PUT .../enable` com `if: always()` (D218) | o mesmo passo no workflow do Pages |

## 5. Termos das fontes: o que o site publica

Publicar vagas num site aberto é republicar conteúdo de terceiros, e uma vaga publicada aqui chega a quem nunca instalou o joBot. A ADR 0004 aceitou fontes de termos restritivos na versão local porque ela é de uso pessoal; isso não vale para o site. A regra desta fase (D239.1):

- **Fonte sem anotação de termos fica fora.** Cada fonte entra num arquivo de dados novo, `nucleo/dados/publicacao.json` (proposta), com `site` (`inteiro`, `resumo` ou `fora`), `feed` (sim ou não), o endereço dos termos, a data da leitura e um trecho curto. Um teste exige que toda chave de `descobrir()` esteja no arquivo: coletor novo obriga a decidir.
- **`resumo`**: título, empresa, locais, modalidade, nível, área, contrato, idioma, avisos, salário lido, data de publicação, prazo e o link para a vaga original, com "via <fonte>" e link de volta nas fontes que pedem crédito (ADR 0004, Atribuição). São fatos sobre a vaga e o que as regras deduzem do texto, não o texto.
- **`inteiro`**: o resumo mais o texto puro da descrição (`descricao_texto`), nunca o HTML. Só onde o termo autoriza de forma expressa exibir ou redistribuir.
- **`fora`**: a fonte não é coletada pelo workflow do Pages.
- O link de candidatura é sempre o da fonte (na Himalayas, o `applicationLink` deles, como já faz a versão local).

Termos lidos pela sessão em 2026-11-24 (trechos curtos, em inglês como no original):

| Fonte | Termo lido | Trecho | Site | Feed |
|---|---|---|---|---|
| `jobicy` | jobicy.com/jobs-rss-feed (documentação da API) | permite "store, cache, process, and redistribute job data", com crédito; vaga fechada marcada como indisponível; no máximo 1 pedido por segundo | inteiro | sim |
| `himalayas` | himalayas.app/docs/remote-jobs-api | pode exibir "on your own job board, site or app without asking us first"; proíbe repassar a outros quadros, agregadores, Google Jobs e LinkedIn, "also covers feeds"; candidatura pelo `applicationLink` | inteiro | **não** |
| `remoteok` | remoteok.com/api (campo `legal`) | pede link de volta e "mention Remote OK as a source"; logo só com permissão; nada sobre redistribuir o texto. A descrição já trouxe o IP de quem pede em base64 (D219.14) | resumo | sim |
| `wwr` | aviso do feed, lido pela sessão da D219 em 2026-11-24 (crédito e link); nesta rodada a página dos termos deu 403 e o cabeçalho do feed não traz aviso | (sem trecho novo) | resumo | não, até reler |
| `greenhouse` | docs.greenhouse.io/job-board.html | a API pública serve para "build careers pages"; não fala de terceiros nem de redistribuir | resumo | sim |
| `lever` | github.com/lever/postings-api | vagas publicadas "are publicly viewable" e "may be scraped by third parties"; não fala de redistribuir o texto | resumo | sim |
| `ashby` | developers.ashbyhq.com/docs/public-job-posting-api | serve ao site de carreiras da própria empresa; vaga com `isListed` falso "should only be available via direct link" | resumo, só `isListed` verdadeiro | sim |
| `github_issues` | Termos do GitHub, seção D.5 e D.8 | a licença entre usuários vale "within the Service"; D.8 não restringe "lawful access to or use of the contents of public repositories"; o corpo das issues traz nomes e contatos de pessoas | resumo sem corpo (título, repositório, data, link) | sim |
| `remotive` | remotive.com/remote-jobs/api | "Please do not submit Remotive jobs to third Party websites", citando agregadores como Jooble; pede link e crédito; vagas com 24 h de atraso | fora (D239.2) | não |
| `hn_algolia` | ycombinator.com/legal | proíbe "data mining, robots, scraping" e publicar o conteúdo do site sem autorização | fora | não |
| `gupy` | termos lidos na D219.14 (2026-11-24): proíbem agregar, copiar ou duplicar | (ver D219.14) | fora | não |

As outras fontes públicas (`smartrecruiters`, `workday`, `eightfold`, `oracle_hcm`, `inhire`, `quickin`, `recrutei`, `solides`, `ciee`, `iel`, `super_estagios`, `cia_de_talentos`, `eureca`, `abler`, `usp`, `google`, `amazon` e a descoberta pelo Common Crawl) **não tiveram os termos lidos nesta rodada e ficam fora** até uma tarefa da 0.7.0 ler e anotar cada uma (D239.3). Eureca, Abler e Gupy já são de termos restritivos pela ADR 0004 e ficam fora sem nova leitura. A SmartRecruiters documenta a API com chave ou OAuth; a leitura dos termos decide se o caminho público que o coletor usa serve a um site aberto.

Consequência honesta: sem as fontes brasileiras, a 0.7.0 tem pouca vaga do Brasil (os cinco repositórios de issues e as empresas dos ATS). A leitura dos termos das fontes brasileiras é a primeira tarefa da fase, não um extra.

## 6. Coleta diária no GitHub Actions

### 6.1 O workflow

`pages.yml` (proposta, D239.4):

- Gatilhos: `schedule` uma vez por dia fora do minuto cheio (`41 7 * * *`, proposta; o vigia roda às 6:23 de segunda), `workflow_dispatch` e `push` na `main` só quando muda `web/**` ou os scripts do Pages (aí só monta o site com os dados do dia, sem coletar). Nunca `pull_request` nem `pull_request_target`.
- Permissões: `contents: write` (só para o ramo `dados`), `pages: write` e `id-token: write` (exigidas pelo `deploy-pages`; o `id-token` é o token OIDC do próprio GitHub, não segredo), `actions: write` (só para o passo da D218). Nenhum `secrets.*`.
- `concurrency: pages`, sem cancelar a execução em curso; `timeout-minutes: 120`.
- Passos: checkout sem credencial persistida; `uv sync --locked`; buscar o `dados` de ontem (`git fetch origin dados`, vazio na primeira vez); `uv run python scripts/pages.py coletar`; `uv run python scripts/pages.py montar`; gravar o `dados` (seção 6.3); `upload-pages-artifact` e `deploy-pages`; por último, com `if: always()`, `gh api -X PUT repos/$GITHUB_REPOSITORY/actions/workflows/pages.yml/enable` (D218).
- O `schedule` só vale no ramo padrão (`main`): o site só começa a se atualizar depois do merge na `main`. Forks não rodam agendamentos por padrão.

### 6.2 A coleta

- **O joBot de verdade num banco temporário** (D239.5). `scripts/pages.py coletar` cria um banco em `JOBOT_DADOS` temporário (migrações de sempre), semeia as fontes e as empresas, liga só as fontes com `site` diferente de `fora` em `publicacao.json` e roda `executar_busca` uma vez, com o `ClienteEducado` de sempre: user agent fixo do joBot, intervalo por host, respeito a 429 e `Retry-After`, `max_pedidos` e limite de enriquecimento de `fontes.json`. O tratamento, os rótulos, a remoção de duplicadas e a cotação são os do núcleo. Nada é copiado.
- **Só fontes que não pedem termo de busca** na 0.7.0 (D239.6): o site não tem as buscas de ninguém. As fontes por feed e por empresa listam tudo sem termo. Fonte que exige termo fica fora até o desenho de uma lista fixa de termos amplos (pt e en), numa versão seguinte.
- **Bloqueio e falha**: o runner roda num IP de datacenter; 401, 403, desafio ou página de login é "falhou", como na versão local, e nunca se contorna. Fonte que falhou mantém as vagas de ontem (com a data em que foram vistas) até a retenção; o site mostra, por fonte, "atualizada em" e o estado.
- **Ritmo**: uma execução por dia está acima de todo `intervalo_min` de `fontes.json` (o maior é 1440 minutos).

### 6.3 Ramo `dados`, tamanho e retenção

- O ramo `dados` guarda só o que o site publica: `vagas.json` (lista de vagas no formato da seção 6.4), `fontes.json` (estado e data por fonte), `meta.json` (`atualizado_em`, versão do joBot que coletou, versão das regras `rotulos.VERSAO_REGRAS`, versão do formato) e o feed. É **sobrescrito a cada dia** por um commit órfão único e `git push --force` (ADR 0002), para o repositório não crescer com o histórico dos dados. É a única exceção à regra de não reescrever histórico (ADR 0016), e vale só para esse ramo, que nenhuma pessoa edita.
- **Retenção** (D239.7): vaga que a fonte ainda lista fica; vaga não vista há 7 dias sai; vaga com prazo vencido sai na hora. O site é um retrato, não um acervo: o "nada é apagado" da versão local vale para o banco de cada pessoa, não para este arquivo público.
- **Data da primeira vista**: `coletar` lê o `vagas.json` de ontem e mantém `vista_em` das vagas que já conhecia (mesmo `url_hash`); vaga nova ganha a data de hoje. É o que permite o filtro "novas hoje" e o feed.
- **Teto**: `vagas.json` com mais de 20 MB (proposta) faz o passo falhar alto, sem publicar, e o site fica com o de ontem. O resumo do workflow mostra o tamanho e a contagem por fonte. Estimativa: resumo com cerca de 400 bytes por vaga; texto inteiro (Jobicy e Himalayas, algumas centenas de vagas) com cerca de 4 KB; poucos MB no total, e o Pages serve comprimido. Os limites do Pages (site publicado até 1 GB, banda de 100 GB por mês) vêm da documentação do GitHub e são conferidos de novo na tarefa do workflow.
- **Reativação**: o mesmo passo da D218 em toda execução. Isso também fecha o ponto aberto da ADR 0002 ("pushes no ramo `dados` contam como atividade?"): não importa, porque o workflow se reativa pela API.

### 6.4 Formato de uma vaga publicada

Um objeto JSON por vaga, com nomes por extenso (o Pages comprime): `url_hash` (o mesmo da versão local, a chave do status e do importar), `fonte`, `titulo`, `empresa`, `locais` (cidade, UF, país), `modalidade`, `nivel`, `area`, `contrato`, `idioma`, `avisos`, `salario` (mínimo, máximo, moeda, período, plausível) e `salario_mensal_brl` (reais inteiros, já convertidos pela PTAX do dia; `null` sem cotação), `publicada_em`, `prazo`, `vista_em`, `url`, `credito` (nome e link da fonte, quando pede) e `descricao_texto` só nas fontes `inteiro`. Nenhum e-mail, telefone ou nome de pessoa: as fontes `inteiro` passam pela mesma limpeza de contato da IA (`pedidos`, D227) antes de publicar, e o teste usa fixtures com contato falso.

## 7. O site

### 7.1 Estático e com o visual do painel

- `scripts/pages.py montar` gera `site/` a partir de `web/` (templates Jinja2, JavaScript, CSS só do site) e copia do painel o CSS, a Inter e os ícones, sem duplicar arquivo no repositório (D239.11). Os motivos do encaixe (`encaixe.*`) e os rótulos de filtro vêm dos catálogos do painel; texto novo do site vai em `web/i18n/{pt,en}.json`, com teste de chaves iguais nas duas línguas, como o do painel.
- Duas árvores, `/pt/` e `/en/`, geradas no build. A raiz manda para `/en/` quando a língua do navegador não começa com `pt` (script próprio, não inline); sem JavaScript fica em português. O seletor de língua é um link comum.
- Páginas: Vagas (lista, filtros e detalhe), Buscas, Perfil, Exportar e importar, Sobre (de onde vêm as vagas, a tabela de fontes com "via" e os termos, privacidade). Na 0.8.0, o painel "Preparar com IA" no detalhe.
- JavaScript em módulos ES puros, sem build, sem framework (D239.11). O site precisa de JavaScript para listar as vagas; sem ele, um `<noscript>` explica e aponta o link para os dados.
- "Atualizado em <data>" no topo (ADR 0002); com mais de 2 dias sem atualizar, aviso de que a coleta parou.

### 7.2 O que roda no navegador

- Filtros: texto (normalizado como `texto.normalizar`, sobre título, empresa e texto publicado), fonte, modalidade, nível, área, contrato, país e UF, idioma, salário mínimo em reais, "novas hoje", encaixe (bom, médio) e "mostrar ocultas" com a contagem por motivo (ADR 0007).
- Encaixe por regras de cada vaga contra cada busca do visitante (seção 8), com os motivos e as regras de ocultar ligadas.
- Status por vaga e ocultar à mão, no `localStorage`.
- Nada de pedido de rede além de buscar `vagas.json`, `fontes.json` e `meta.json` no próprio site.

### 7.3 Faixa "baixe a versão completa"

Fixa no topo de toda página, curta, sem fechar (ADR 0002). Texto proposto (D239.13): pt "Esta é a versão no navegador. A versão para baixar busca em mais fontes, roda sozinha em segundo plano, tem IA e entra nos sites com login." com o link "Baixar o joBot"; en "This is the browser version. The download searches more sources, runs on its own in the background, has AI and reads sites that need a login." com "Download joBot". O link vai à página Instalar da wiki (pt) e Install (en). O visual segue o aviso do painel.

### 7.4 Segurança da página

- **CSP** em `<meta http-equiv>` (o Pages não deixa pôr cabeçalho): `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'` (proposta, D239.12). Sem script nem estilo inline; o `frame-ancestors` não vale em meta e fica como teto conhecido.
- Todo texto de vaga entra por `textContent`. Link de vaga só com `https:` e host conferido como URL (`new URL`), senão o link some; teste com `javascript:` e `data:`.
- Arquivo importado é lido no navegador, conferido contra o formato (seção 9) e recusado inteiro se não bater; nenhum campo dele vira HTML.
- **Origem compartilhada**: o `localStorage` é por origem, e `<dono>.github.io` é a mesma origem para todo site do Pages da mesma conta. Outro site do Pages do dono poderia ler o perfil guardado ali. As chaves levam o prefixo `jobot:`, a página Sobre diz isso, e um domínio próprio isolaria a origem (espera o dono, opcional; D239.14). Nenhum outro site da mesma conta deve carregar script de terceiros.

### 7.5 Acessibilidade

As mesmas regras de tela do painel (`registros/padroes-tela.md`): contraste nos dois temas, foco visível, rótulo em todo controle, ordem de tabulação, `aria-live` nos avisos, tudo por teclado. Testadas por Playwright como as do painel, sem biblioteca nova.

## 8. Encaixe em JavaScript e paridade

- **O que porta** (D239.9): só `encaixe.calcular` com `_regra_que_bate`, `_faixa`, `_arredondar`, `casar`, `texto.normalizar` e `sem_pontas`, lendo o mesmo `dados/encaixe.json` copiado no build. Rótulos, locais, salário e câmbio ficam no Python do Actions: o site recebe os campos prontos. Isso reduz o que precisa de paridade a umas 200 linhas.
- **Entradas no site**: `habilidades_vaga` é sempre `null` (neutro) na 0.7.0, porque a IA não roda no Actions; `habilidades_perfil` vem do perfil; `regras_ligadas` e `regras_ocultar` da busca; `pais_padrao` do perfil (proposta: o país da cidade de moradia, senão BR). O salário mínimo da busca no site é só em reais (`minimo_busca_brl` = centavos ÷ 100, inteiro), e a vaga já traz `salario_mensal_brl`; assim nenhum câmbio roda no navegador (D239.10).
- **Fonte `resumo`**: sem `descricao_texto`, o cargo só casa pelo título (`cargo_titulo`); `cargo_descricao` nunca acontece. A função é a mesma; o dado é que é menor. A página Sobre diz isso.
- **Paridade** (D239.21): um arquivo de casos gerado pelo Python (`tests/fixtures/encaixe_paridade/casos.json`) junta (a) as vagas das nossas fixtures de coletores passadas por `tratar`, cruzadas com uma grade de buscas, e (b) casos de borda escritos à mão: `ß` e `ẞ` (`casefold` vira `ss`, `toLowerCase` não), `İ` turco, NBSP e espaços Unicode (`str.split()` e `\s` do JavaScript diferem), marcas combinantes, apóstrofo curvo, `C++`, `C#`, `.NET`, `\w` Unicode da borda de palavra (o JavaScript precisa de `/u` com `\p{L}\p{N}_`), metade no arredondamento. O teste em Python confere que o arquivo bate com `calcular` de hoje (arquivo velho reprova); o teste de tela carrega o módulo JavaScript no Chromium e compara caso a caso, nota, nível, motivos (chave e parâmetros) e regra de ocultar. Regra mudou em `encaixe.py` ou `encaixe.json`: o caso gerado muda e o JavaScript reprova até acompanhar (ADR 0007, Consequências).

## 9. Perfil, buscas e exportar/importar

- **No navegador**: perfil (os mesmos campos da 0.6.0: contato, cargo atual, anos, formação, resumo, idiomas, links, habilidades, experiências, cursos, respostas das perguntas), buscas (os campos de `modelo.Busca`) e status por `url_hash`, cada um numa chave `jobot:*` do `localStorage`, com "Apagar tudo" na página Perfil. Leitura e gravação em `try/catch`: sem `localStorage` (modo privado, bloqueado), o site funciona sem guardar e avisa.
- **Arquivo `jobot-perfil`** (D239.15): JSON com `formato: "jobot-perfil"`, `versao: 1`, `exportado_em`, `origem` (`local` ou `pages`), `perfil`, `buscas` e `status` (lista de `url_hash`, status e data). Nunca leva chave de serviço, senha, cookie, sessão de site, e-mail lido ou dado de vaga além do `url_hash`. A versão local ganha "Exportar" e "Importar" em Configurações › Perfil com o mesmo formato, em `banco` (ler e gravar) e `painel` (botões, CSRF), com texto nos dois catálogos.
- **Importar**: confere formato, versão e tetos de tamanho; mostra o resumo (quantos campos, buscas, status) e só grava depois do OK. Perfil e buscas substituem os de agora (com aviso); status de vaga que o lado de lá não conhece fica de fora e aparece na contagem. Na versão local, importar não apaga vaga nem `evento`: status importado vira evento novo `mudou_status`.
- **Teste de ida e volta**: o mesmo arquivo de exemplo é importado e exportado pelos dois lados (Python e JavaScript) e volta igual, campo a campo.

## 10. IA manual no site (0.8.0)

- Só as tarefas sob pedido da versão local: `curriculo`, `perguntas`, `candidatura` (D229.1). O encaixe não tem IA manual.
- **O Python continua a fonte da verdade** (D239.16): no build, `montar` exporta `moldes_ia.json` com, por tarefa, as mensagens fixas do pedido, a ordem dos blocos de dados, a frase `PEDE_JSON` por idioma e o esquema sem as descrições (o mesmo de `texto_para_copiar`, D229.6). O JavaScript só preenche os dados e lê a resposta.
- **Paridade**: o texto para copiar montado no JavaScript é igual, byte a byte, ao de `manual.texto_para_copiar` para as mesmas entradas, com a lista permitida e a limpeza de contato de `pedidos` (D227) portadas e testadas; a leitura da resposta colada aceita e recusa os mesmos casos de `ler_resposta` (D229.3), incluindo o teto de 1 MiB e o bloco de código único. A conferência do esquema em JavaScript cobre só as palavras-chave que os esquemas do joBot usam (tipos, `properties`, `required`, `additionalProperties`, tetos de tamanho e de itens, `enum`); palavra-chave nova no esquema reprova um teste até ser coberta.
- **Currículo**: a pessoa cola o texto do currículo (ler PDF no navegador pediria biblioteca nova; fica fora). **Candidatura**: o texto da vaga vem dos dados quando a fonte é `inteiro`; nas outras, a pessoa abre a vaga original e cola o texto, que fica só no navegador.
- Sem chave, sem serviço, sem pedido de rede: quem copia e cola é a pessoa (D229.5).

## 11. Feed e Discord

- **Feed Atom (0.7.0)** (D239.8): `feed.xml` com as vagas novas do dia (`vista_em` de hoje), só das fontes com `feed` sim em `publicacao.json`, até 200 entradas, só com título, empresa, local, data, "via <fonte>" e o link original. Não leva texto inteiro, nem da Jobicy. Serve a qualquer leitor de feed e a bots de RSS para Discord, Telegram ou Slack que cada servidor escolha, sem segredo nosso.
- **Nível 2 da ideia do dono (0.8.0, espera o dono)** (D239.19): um canal do joBot no servidor do dono, do tipo Anúncios (exige o servidor como Comunidade), que qualquer outro servidor **segue** pelo recurso nativo do Discord ("Seguir"): o Discord cria o webhook no servidor de quem segue, e o repositório nunca guarda nada de outro servidor. Sem bot nosso ligado 24 horas, sem estado por servidor, sem moderação nossa nos outros servidores. O canal é alimentado de um de dois jeitos, que o dono escolhe:
  - (a, recomendada) um bot de RSS da conta do dono lendo o `feed.xml`: nenhum segredo entra no Actions, e a regra da ADR 0002 fica de pé; o custo é depender de um serviço de terceiros e do atraso dele;
  - (b) o próprio workflow posta por um webhook do canal do dono, guardado como segredo num Environment protegido do GitHub, usado só no agendamento na `main` (PR de fork não vê segredo). Mais simples e sem terceiros, mas abre uma exceção na ADR 0002, que só o dono pode abrir.
  Em qualquer dos dois, só entram as fontes com `feed` sim, e uma mensagem por dia com até 10 vagas por mensagem, dentro do limite do Discord.
- **Nível 1** (webhook no painel local, cada pessoa no seu canal) é da versão local e fica fora desta fase; vira tarefa pequena da versão local quando o dono quiser (espera o dono).

## 12. Escolhas desta sessão (D239)

Cada item é escolha da sessão, para discutir com o dono, com o desfazer no `duvidas.md` (D239.n é o item n desta lista).

1. Termos: fonte sem anotação fica fora; `publicacao.json` com `site` e `feed` por fonte, data e trecho; teste exige toda chave de `descobrir()`.
2. Remotive fora do site e do feed, apesar de a API existir para exibir vagas: o termo cita agregadores como o tipo de site proibido, e o site do joBot é um agregador.
3. Fontes sem leitura nesta rodada ficam fora até a tarefa de leitura da 0.7.0, com as brasileiras primeiro.
4. Workflow `pages.yml` com agenda diária às 7:41 UTC, à mão e push na `main`; sem segredo; deploy pelas Actions oficiais do Pages.
5. A coleta é o executor de verdade num banco temporário, sem cópia do núcleo.
6. Na 0.7.0, só fontes que não pedem termo de busca.
7. Retenção: 7 dias sem ser vista ou prazo vencido sai; teto de 20 MB no `vagas.json`.
8. Feed Atom das vagas novas, só metadados, até 200 entradas, só fontes com `feed` sim.
9. Rótulos e tratamento no Python do Actions; só o encaixe e a normalização em JavaScript.
10. Salário mínimo da busca no site só em reais; o câmbio fica no Actions.
11. Código fora do pacote: `scripts/pages.py` e `web/`; JavaScript puro em módulos ES, sem npm nem build; o build copia o visual do painel.
12. CSP em meta, sem nada inline, só `'self'`.
13. Texto da faixa (pt e en) e destino do link (página Instalar da wiki).
14. Origem compartilhada do `github.io`: prefixo `jobot:` e aviso; domínio próprio fica com o dono.
15. Formato `jobot-perfil` versão 1, nos dois lados; importar mostra o resumo e só grava com OK; status desconhecido fica fora.
16. Esquemas e moldes da IA exportados do Python no build; o JavaScript não tem fonte própria deles.
17. Chave do visitante (Haiku) fora desta fase: chave no `localStorage` fica ao alcance de qualquer falha de script da origem compartilhada, a CSP teria de abrir a API de fora e a chamada direta do navegador pede o cabeçalho de acesso direto da Anthropic. Fica como opção para depois, ainda desligada por padrão.
18. Habilidades por IA nas vagas do site (o Laya no runner, em CPU): só depois de medir; fora desta fase.
19. Discord: feed na 0.7.0; canal de Anúncios do dono que outros servidores seguem na 0.8.0, alimentado por bot de RSS (recomendado) ou por webhook em segredo (exceção na ADR 0002, só com o dono).
20. Versões: 0.7.0 (coleta, site, encaixe, perfil, exportar e importar, faixa, feed) e 0.8.0 (IA manual e canal do Discord).
21. Testes do JavaScript no Chromium do Playwright, a partir do pytest, sem Node no projeto.

## 13. Testes

- **Política**: toda chave de `descobrir()` em `publicacao.json`; `fora` nunca coletada; `resumo` nunca leva `descricao_texto`; `feed` não nunca no feed (cada um com controle positivo).
- **Coleta com dados falsos**: `scripts/pages.py coletar` com transporte falso servindo as fixtures das fontes ligadas, banco em `tmp_path`, relógio injetado; confere o `vagas.json` (formato, `url_hash` igual ao da versão local, `vista_em` mantido de um `anterior` falso, retenção de 7 dias, prazo vencido fora, fonte que falhou mantém as de ontem, teto de tamanho falha) e o feed (só novas, só `feed` sim, 200 no máximo). Sem rede.
- **Workflow por texto**: `pages.yml` sem `pull_request`, sem `pull_request_target`, sem `secrets.`, com as permissões listadas e só elas, Actions fixadas por hash, último passo de reativação com `if: always()` (como a guarda do vigia em `test_vigia.py`).
- **Site (Playwright, `-m tela`, no CI)**: o `site/` montado com dados falsos e servido em `127.0.0.1`; filtros; encaixe e motivos; status e ocultar sobrevivem a recarregar; sem `localStorage` o site funciona; exportar e importar; faixa em toda página nas duas línguas; nenhum pedido de rede fora da origem (o teste escuta os pedidos da página); CSP sem violação no console; texto de vaga com `<script>` aparece como texto; link `javascript:` some; acessibilidade como no painel.
- **Paridade**: encaixe (seção 8), ida e volta do `jobot-perfil` (seção 9) e, na 0.8.0, texto para copiar e leitura da resposta (seção 10).
- **Guarda de texto**: nenhum `http://` ou `https://` literal em `web/` além da lista permitida (links da wiki e do repositório).
- Nesta máquina, só o arquivo de teste da tarefa e o ruff; suíte inteira, `-m tela` e mypy no CI, como sempre.

## 14. Versões e tarefas (proposta)

A numeração das tarefas sai do plano; a ordem abaixo é a proposta.

**0.7.0**

1. Ler e anotar os termos das fontes que ficaram fora (brasileiras primeiro) e criar `publicacao.json` com o teste.
2. `scripts/pages.py coletar` com os testes de coleta falsa.
3. Encaixe e normalização em JavaScript, o gerador de casos e o teste de paridade.
4. `scripts/pages.py montar`, templates de `web/`, catálogos pt e en, CSP, faixa.
5. Telas do site: vagas, filtros, detalhe, buscas, status.
6. Perfil no navegador e o formato `jobot-perfil`; exportar e importar nos dois lados.
7. Feed Atom.
8. `pages.yml`, com a guarda de texto; ensaio por `workflow_dispatch` depois do merge na `main`.
9. Documentos (README pt e en, wiki Instalar e Como funciona, página nova sobre a versão no navegador, CHANGELOG) e release 0.7.0.

**0.8.0**

1. Moldes da IA exportados no build e a paridade do texto para copiar e da leitura.
2. Painel "Preparar com IA" no site (currículo, perguntas, candidatura).
3. Canal do Discord, no jeito que o dono escolher (seção 11).
4. Documentos e release 0.8.0.

## 15. O que fica fora

Sites com login, Gmail, extensão, IA automática, áudio e segundo plano (ADR 0002); a chave do visitante (D239.17); habilidades por IA nas vagas do site (D239.18); fontes que pedem termo de busca (D239.6); fontes sem termos lidos (D239.3); Remotive, Hacker News e Gupy (seção 5); leitura de PDF no navegador; busca com índice; acervo histórico; o nível 1 do Discord (versão local); domínio próprio (dono).

## 16. O que espera o dono

- Ligar o Pages no repositório (Settings › Pages › Source: GitHub Actions) antes do primeiro deploy.
- Confirmar ou trocar as escolhas da D239, em especial a Remotive fora (D239.2) e a política de texto inteiro só na Jobicy e na Himalayas (D239.1).
- Discord (0.8.0): criar o servidor ou o canal de Anúncios (Comunidade) e escolher entre bot de RSS da conta dele e webhook em segredo (exceção na ADR 0002).
- Domínio próprio, se quiser isolar a origem do `localStorage` (D239.14).
