# Fase 8: versão GitHub Pages (desenho)

Data: 2026-11-24, revisto no mesmo dia com os achados da revisão (seção 17). Decisões de origem: ADR 0002 (duas versões, um núcleo: a base desta fase), 0004 e 0005 (coleta educada; nada com login), 0007 (regras em Python e em JavaScript), 0014 (sem telemetria), 0016 (sala limpa), 0017 (fases), 0018 (CI aberto, vigia), 0021 (dependências à mão), 0023 e 0026 (IA da fase 4); D218 (vigia que se reativa), D219.14 (termos lidos para o treino do Laya), D227 (limpeza de contato), D229 (IA manual). Ordem nova das fases: **D238** (pedido do dono em 2026-11-24, aceito pela sessão, para o dono confirmar: a fase 8 vem antes da fase 5; os números não mudam). Escolhas desta sessão: **D239** (escolha da sessão, para discutir com o dono). Versões alvo: **0.7.0** e **0.8.0** (D239.20, para discutir).

Fatos sobre o código citam o símbolo e o arquivo, conferidos na `dev` em `d16de121` (2026-11-24, a T440 juntada; a release 0.6.0 corre em paralelo e este desenho não mexe nela). Quando a linha andar, procure o símbolo. Valores marcados "(proposta)" foram escolhidos pela sessão e valem para construir; o dono pode trocar.

**Quando entra na `dev`.** Este desenho, o plano e as notas nas ADRs entram na `dev` agora, antes de a release 0.6.0 criar qualquer D novo: o D que a release precisar começa no D240. Se mesmo assim dois ramos criarem o mesmo número, quem entra depois renumera o seu. **Nenhum lote de construção da fase 8 entra na `dev` antes da tag `v0.6.0`**, para nada desta fase sair na 0.6.0, e a fase só começa a ser construída depois que a fase 4 passa nos testes (ADR 0017, Consequências).

## 1. Intenção

Quem não quer instalar nada abre um endereço no navegador e vê as vagas das fontes públicas cujos termos permitem, atualizadas uma vez por dia, com os mesmos filtros, o mesmo visual e o mesmo encaixe por regras da versão local. As buscas, o país e o status de cada vaga ficam só no navegador da pessoa, e o arquivo exportado dali abre na versão local. Toda página diz, no topo, que a versão para baixar é mais completa (ADR 0002).

O site é estático: não há servidor nosso. O GitHub Actions coleta, trata e publica; o navegador do visitante filtra e calcula o encaixe. Nada do visitante sai do navegador dele.

**Duas versões** (D239.20). A **0.7.0** traz a coleta diária, o site com filtros, o encaixe em JavaScript com paridade testada, as buscas, o país e o status no navegador, exportar e importar disso compatível com a versão local, a faixa e um feed Atom das vagas novas. A **0.8.0** traz o perfil no site e no arquivo, a IA manual (copiar e colar), que é quem usa o perfil, e o canal do Discord, que depende do dono (seção 11).

## 2. Objetivos, não objetivos, anti-objetivos

**Objetivos (0.7.0)**

- Coleta diária no GitHub Actions, só com fontes públicas, sem segredo, no ritmo da ADR 0004, reaproveitando o executor, o tratamento e os rótulos do núcleo sem cópia (seção 6).
- Política de publicação por fonte, num arquivo de dados com o endereço, a data e o trecho dos termos lidos: texto inteiro só onde o termo permite; senão só título, empresa, local, data, rótulos e o link para a vaga original; fonte sem anotação fica fora (seção 5).
- Limpeza de contato em toda vaga publicada, lista de bloqueio versionada e um canal de remoção (seção 6.4).
- Site estático em português e inglês, com o visual do painel, sem recurso externo, com CSP e acessível (seção 7).
- Encaixe por regras em JavaScript, com paridade testada contra `nucleo/encaixe.py`; a normalização de texto aplica tabelas exportadas do Python (seção 8).
- Buscas, país e status por vaga (com um retrato mínimo da vaga) no `localStorage`; exportar e importar um arquivo `jobot-perfil` que a versão local também lê e grava (seção 9).
- Feed Atom das vagas novas, só das fontes marcadas para isso (seção 11).

**Objetivos (0.8.0)**

- Perfil no site e no arquivo `jobot-perfil`, nos dois lados (seção 9).
- IA manual no site para `curriculo`, `perguntas` e `candidatura`, com o mesmo texto para copiar e a mesma conferência da resposta colada da versão local (D229), sem chave nem serviço (seção 10).
- Canal do joBot no Discord que qualquer servidor segue, sem bot nosso ligado 24 horas e sem segredo por servidor (seção 11; espera o dono).

**Não objetivos**

- Sites com login, Gmail, extensão, IA automática, áudio, segundo plano (ADR 0002).
- A chave do visitante para um serviço de IA (Haiku): fica para depois desta fase (D239.17).
- Rótulos e tratamento em JavaScript: rodam no Actions, em Python, e o site recebe o resultado (D239.9).
- Habilidades por IA nas vagas do site (o Laya rodando no Actions): só depois de medir tempo e custo de CPU (D239.18). Sem elas, as habilidades do perfil não entram na nota no site, em nenhuma versão desta fase.
- Fontes que pedem termos de busca (o site não conhece as buscas de ninguém): ficam para depois da 0.7.0 (D239.6).
- Busca por texto inteiro com índice (FTS5): o site filtra por texto normalizado em título, empresa e, quando publicado, no texto.
- Arquivo histórico das vagas: o site é um retrato, não um acervo.

**Anti-objetivos**

- Qualquer dado do visitante (buscas, status, perfil, texto colado) saindo do navegador por conta do site.
- Analytics, cookies, fontes ou scripts de terceiros, CDN.
- Segredo no repositório ou no workflow do Pages (ADR 0002, Consequências).
- Republicar texto de vaga onde o termo da fonte não permite, ou contornar bloqueio, CAPTCHA ou limite de uma fonte.
- Emitir dados estruturados `JobPosting` (JSON-LD ou microdados): o site não disputa o Google Jobs com as fontes (teste na seção 13).
- Cópia da lógica do núcleo em Python para outro lugar em Python: o Actions chama o núcleo de verdade.

## 3. Restrições

- Camadas (`tests/unidade/test_camadas.py`): nada muda nas camadas de `src/jobot`. O código da fase fica fora do pacote: scripts de CI em `scripts/` (como o `scripts/vigia.py`) e a fonte do site em `web/` (proposta, D239.11). A exportação e importação na versão local mora em `banco` (formato) e `painel` (botões), nas camadas de hoje.
- Dependências fixadas com `==` e sem dependência nova sem decisão (ADR 0021). Nenhuma entra: o site é JavaScript puro, sem framework, sem bundler e sem `npm`; o build usa o Jinja2 que já está no projeto; o feed usa `xml.etree.ElementTree` da biblioteca padrão; os testes do JavaScript rodam no Chromium do Playwright, que já está no projeto (D239.11, D239.21). As Actions oficiais do GitHub para o Pages (`actions/upload-pages-artifact`, `actions/deploy-pages`) entram fixadas por hash, com a versão em comentário (`test_actions_fixadas_por_hash`).
- Testes sem rede (`tests/conftest.py`): a coleta do Pages roda nos testes só com transporte falso e fixtures; o site de teste é servido em `127.0.0.1`, num subcaminho (seção 7.4).
- Sala limpa (ADR 0016): nada de código ou dado de terceiros; os casos de paridade são gerados das nossas fixtures e do próprio Python.
- Conteúdo de vaga é dado, nunca instrução: no site ele entra por `textContent`, nunca como HTML (seção 7.4).
- O repositório é público: o workflow roda só por agenda, à mão e em push na `main`; nunca em PR, nunca com `pull_request_target` (ADR 0018).

## 4. O que já existe (fatos levantados)

| Peça | Onde está | Serve ao Pages como |
|---|---|---|
| Coletores das fontes públicas, um por arquivo | `nucleo/coletores/{agregadores,carreiras,plataformas,portais}/`, `registro.descobrir()` | reaproveitados sem mudança pelo executor, nas fontes que listam sem termo de busca (o `escopos` de cada uma das que entram foi conferido; a Himalayas lista só por termo e fica fora, seção 5) |
| Executor de uma busca, com saúde e ciclo de vida | `agenda.execucao.executar_busca(con, cliente, relogio, "agora")`, usado por `cli/buscar.py`; os termos vêm de `termos_das_buscas(con)` | a coleta do Pages roda isto num banco temporário, sem buscas (portanto sem termos) |
| Ritmo por fonte | `nucleo/dados/fontes.json` (`intervalo_min`, `max_pedidos`, `espera_s`, `credito_obrigatorio`), `nucleo/http.ClienteEducado` | o mesmo ritmo e o mesmo user agent fixo do joBot |
| Empresas dos ATS | `nucleo/dados/empresas.json` (83 empresas: 28 da Gupy, 15 Greenhouse, 11 SmartRecruiters, 8 Lever, 5 Ashby e outras), `banco.cadastros.empresas_iniciais()` | a lista de escopos das plataformas |
| Tratamento e rótulos | `nucleo/tratamento/tratar.tratar`, `rotulos.rotular` (regras em `dados/rotulos.json`), `locais.py`, `salario.py`, `estagio.py` | rodam no Actions; o site recebe os rótulos prontos |
| Cotação PTAX | `nucleo/cambio.py` (consulta pública do Banco Central) | o Actions publica o salário mensal em reais já convertido |
| Encaixe por regras | `nucleo/encaixe.calcular` (cargo, local, nível, salário, idioma, habilidades; regras de ocultar em `_regra_que_bate`), pesos em `dados/encaixe.json` | porta para JavaScript, com paridade (seção 8) |
| Normalização de texto | `nucleo/texto.normalizar` (NFD sem `unicodedata.combining`, `casefold`, `split()` e junção por espaço, apóstrofo curvo vira reto), `sem_pontas` | o JavaScript aplica tabelas que o Python exporta (seção 8) |
| Limpeza de contato | `nucleo/ia/pedidos.limpar_contato` (`_CONTATO`: e-mail com `@`, telefone e CPF com algarismos; "maria arroba gmail" passa, como diz o comentário); nome de pessoa só sai em `_sem_o_proprio`, que vale para o dono do perfil, não para vaga | base da limpeza das vagas publicadas, com o que falta acrescentado no `coletar` (seção 6.4) |
| Buscas | `modelo.Busca` (cargos, cidades, modalidades, níveis, salário mínimo e moeda, idiomas, regras de ocultar) | o visitante cria as dele no navegador |
| Status da vaga | `vaga.status` em `banco/migracoes/0001_inicial.sql` (`nova`, `salva`, `candidatei`, `entrevista`, `recusada`, `oferta`); ocultar à mão em `vaga.oculta_manual` e `evento.acao` | os mesmos valores no navegador |
| Fonte da vaga | `vaga` não tem coluna `fonte`: a fonte está em `ocorrencia`, e a mesma `url_hash` pode ter ocorrência em mais de uma fonte, com uma só `descricao_texto` | regra da política mais restritiva (seção 5) |
| Perfil | migrações `0012_ia.sql` (habilidades) e `0013_perfil.sql` (contato, cargo, anos, formação, resumo, idiomas, links, experiências, cursos, perguntas) | no site e no arquivo só na 0.8.0 (seção 9) |
| Exportar/importar | **não existe** na versão local (os READMEs deixaram de prometer na T440, D236.3) | nasce nesta fase, nos dois lados (seção 9) |
| IA manual | `nucleo/ia/manual.texto_para_copiar(pedido, idioma)` e `ler_resposta(pedido, colado)`; só `curriculo`, `perguntas`, `candidatura` (D229) | porta para JavaScript na 0.8.0, com paridade (seção 10) |
| Esquemas das respostas da IA | modelos pydantic em `nucleo/ia/esquema.py`; o texto para copiar usa o esquema sem as descrições (D229.6) | o Python exporta o JSON Schema no build; o JavaScript só o lê (D239.16) |
| Visual e textos do painel | `painel/static/css/*.css`, `static/fontes/` (Inter vendorizada), `static/icones/`, catálogos `painel/i18n/{pt,en}/*.json` | o build copia CSS, fonte e ícones; as telas do painel são Jinja com HTMX no servidor e são refeitas no navegador (seção 7) |
| Agendamento que se reativa | `vigia.yml`, último passo `gh api -X PUT .../enable` com `if: always()` (D218) | o mesmo passo no workflow do Pages |
| Token só para a API do GitHub | `scripts/vigia.py` manda o `GITHUB_TOKEN` só a `api.github.com` em https (inclusive no `Link rel=next`) | o mesmo cuidado nos pedidos da fonte `github_issues` no `coletar` (seção 6.2) |
| Permissões por job | `release.yml`: `contents: read` no topo e escrita só no job que publica | o mesmo molde no `pages.yml` (seção 6.1) |

## 5. Termos das fontes: o que o site publica

Publicar vagas num site aberto é republicar conteúdo de terceiros, e uma vaga publicada aqui chega a quem nunca instalou o joBot. A ADR 0004 aceitou fontes de termos restritivos na versão local porque ela é de uso pessoal; isso não vale para o site. A regra desta fase (D239.1):

- **Fonte sem anotação de termos fica fora.** Cada fonte entra num arquivo de dados novo, `nucleo/dados/publicacao.json` (proposta), com `site` (`inteiro`, `resumo` ou `fora`), `feed` (sim ou não), `retencao_dias`, `max_vagas`, o endereço dos termos, a data da leitura e um trecho curto. Um teste exige que toda chave de `descobrir()` esteja no arquivo (coletor novo obriga a decidir) e que toda fonte com `site` diferente de `fora` tenha endereço, data e trecho não vazios.
- **`resumo`**: título, empresa, locais, modalidade, nível, área, contrato, idioma, avisos, salário lido, data de publicação, prazo e o link para a vaga original, com "via <fonte>" e link de volta nas fontes que pedem crédito (ADR 0004, Atribuição), sem `rel="nofollow"`. São fatos sobre a vaga e o que as regras deduzem do texto, não o texto.
- **`inteiro`**: o resumo mais o texto puro da descrição (`descricao_texto`), limpo (seção 6.4), nunca o HTML. Só onde o termo autoriza de forma expressa exibir ou redistribuir.
- **`fora`**: a fonte não é coletada pelo workflow do Pages.
- **Vaga com ocorrência em mais de uma fonte**: vale a política mais restritiva entre as fontes com ocorrência (`fora` antes de `resumo`, `resumo` antes de `inteiro`); texto só se todas forem `inteiro`; feed só se todas tiverem `feed` sim. O `fonte` e o `credito` publicados são os da fonte mais restritiva, e no empate a primeira chave em ordem alfabética. Nas fontes iniciais a colisão é rara (cada uma tem domínio próprio), mas a guarda "`resumo` nunca leva texto" depende desta regra.
- O link de candidatura é sempre o da fonte.

Termos lidos pela sessão em 2026-11-24 (trechos curtos, em inglês como no original; a revisão releu os mesmos endereços e confirmou as leituras de Jobicy, Himalayas, Remotive, RemoteOK, Greenhouse, Lever, Ashby, Y Combinator e GitHub). "Silêncio" quer dizer que a página lida não fala de terceiros: o `resumo` (fatos e link) é defensável, mas não é permissão, e a remoção por empresa passa pelo `bloqueio.json` (seção 6.4).

| Fonte | Termo lido | Trecho | Site | Feed |
|---|---|---|---|---|
| `jobicy` | jobicy.com/jobs-rss-feed (documentação da API) | permite "store, cache, process, and redistribute job data", com crédito; vaga fechada marcada como indisponível; no máximo 1 pedido por segundo | inteiro | sim |
| `remoteok` | remoteok.com/api (campo `legal`) | pede link de volta (sem `nofollow`) e "mention Remote OK as a source"; logo só com permissão; nada sobre redistribuir o texto. A descrição já trouxe o IP de quem pede em base64 (D219.14) | resumo | sim |
| `greenhouse` | docs.greenhouse.io/job-board.html | a API pública serve para "build careers pages"; silêncio sobre terceiros | resumo | sim |
| `lever` | github.com/lever/postings-api | vagas publicadas "are publicly viewable" e "may be scraped by third parties"; silêncio sobre redistribuir o texto | resumo | sim |
| `ashby` | developers.ashbyhq.com/docs/public-job-posting-api | serve ao site de carreiras da própria empresa; vaga com `isListed` falso "should only be available via direct link"; silêncio sobre terceiros | resumo, só `isListed` verdadeiro | sim |
| `github_issues` | Termos do GitHub, seção D.5 e D.8 | a licença entre usuários vale "within the Service"; D.8 não restringe "lawful access to or use of the contents of public repositories"; o corpo das issues traz nomes e contatos de pessoas, e o título é texto livre de qualquer conta | resumo sem corpo (título limpo, repositório, data, link) | **não** (seção 11) |
| `himalayas` | himalayas.app/docs/remote-jobs-api | pode exibir "on your own job board, site or app without asking us first"; proíbe repassar a outros quadros e agregadores, "including through feeds or JobPosting structured data"; pede reler o feed todo dia e tirar o que sumiu, e link visível com a menção da origem | **fora na 0.7.0** (D239.1 e D239.22) | não |
| `wwr` | weworkremotely.com: a página dos termos e a do feed deram 403 para a sessão e para a revisão; resumos de busca apontam uma página "API Terms & Guidelines" que proibiria copiar e guardar os dados (indício, não leitura) | (nenhum trecho lido) | **fora** até uma pessoa ler as duas páginas num navegador (D239.23) | não |
| `remotive` | remotive.com/remote-jobs/api | "Please do not submit Remotive jobs to third Party websites", citando agregadores como Jooble; pede link e crédito; vagas com 24 h de atraso | fora (D239.2) | não |
| `hn_algolia` | ycombinator.com/legal | proíbe "data mining, robots, scraping" e publicar o conteúdo do site sem autorização | fora | não |
| `gupy` | termos lidos na D219.14 (2026-11-24): proíbem agregar, copiar ou duplicar | (ver D219.14) | fora | não |

**Himalayas.** Além dos termos, o coletor não serve sem termo de busca: `Himalayas.escopos` monta um escopo por termo de `ctx.termos` sobre `/jobs/api/search`, e num banco sem buscas isso dá zero escopos. Listar sem termo pede o endpoint de navegação (`/jobs/api`, com cursor, 20 por página), que o coletor não tem. Para voltar numa versão seguinte, precisa de tudo isto: escopo de navegação no coletor, fixture capturada por nós e teto de pedidos (30 pedidos dão 600 vagas); `retencao_dias` 0 (sai no dia em que some de uma leitura boa, e fonte que falhou não mantém as de ontem); nada de feed nem de `JobPosting`; o texto fora de qualquer arquivo de dados com endereço estável anunciado (ou `resumo`); link visível para himalayas.app com a menção da origem (D239.22).

As outras fontes públicas (`smartrecruiters`, `workday`, `eightfold`, `oracle_hcm`, `inhire`, `quickin`, `recrutei`, `solides`, `ciee`, `iel`, `super_estagios`, `cia_de_talentos`, `eureca`, `abler`, `usp`, `google`, `amazon` e a descoberta pelo Common Crawl) **não tiveram os termos lidos nesta rodada e ficam fora** até a tarefa de leitura da 0.7.0 anotar cada uma (D239.3). Eureca, Abler e Gupy já são de termos restritivos pela ADR 0004 e ficam fora sem nova leitura. A SmartRecruiters documenta a API com chave ou OAuth; a leitura dos termos decide se o caminho público que o coletor usa serve a um site aberto. A mesma tarefa confere o `escopos` de cada fonte nova (tem de listar sem termo) e escolhe `max_vagas` e o enriquecimento por fonte (seção 6.3).

Consequência honesta: com a Himalayas e a WWR fora, só a Jobicy publica texto inteiro, e sem as fontes brasileiras a 0.7.0 tem pouca vaga do Brasil (os repositórios de issues e as empresas dos ATS). A leitura dos termos das fontes brasileiras é a primeira tarefa da fase, não um extra.

## 6. Coleta diária no GitHub Actions

### 6.1 O workflow

`pages.yml` (proposta, D239.4):

- Gatilhos: `schedule` uma vez por dia fora do minuto cheio (`41 7 * * *`, proposta; o vigia roda às 6:23 de segunda), `workflow_dispatch` e `push` na `main` só quando muda `web/**` ou os scripts do Pages (aí só monta o site com os dados publicados ontem, sem coletar). Nunca `pull_request` nem `pull_request_target`.
- **Só roda com a variável do repositório ligada** (`vars.JOBOT_PAGES == 'sim'`, que não é segredo): um fork que liga o Actions e o Pages não repete a coleta nas mesmas fontes sem escolher (D239.4).
- Permissões no topo: `contents: read`. Três jobs, cada um com o mínimo:
  - `coletar` (sem escrita): checkout sem credencial persistida, `uv sync --locked`, `uv run python scripts/pages.py coletar` e `montar`, e entrega `site/` como artefato do Pages (`upload-pages-artifact`). O `GITHUB_TOKEN` de leitura vai só aos pedidos a `api.github.com` (seção 6.2).
  - `publicar` (`needs: coletar`; `pages: write` e `id-token: write`, exigidas pelo `deploy-pages`; o `id-token` é o token OIDC do próprio GitHub, não segredo; `environment: github-pages`, que trava o deploy na `main`): só `deploy-pages`.
  - `reativar` (`needs: [coletar, publicar]`, `if: always()`, `actions: write`): `gh api -X PUT repos/$GITHUB_REPOSITORY/actions/workflows/pages.yml/enable` (D218).
- **Sem ramo `dados`** (proposta, D239.7; espera o dono): o `coletar` lê o `vagas.json` de ontem do próprio site publicado (`https://<dono>.github.io/<repo>/dados/vagas.json`; 404 na primeira vez = sem anterior). Isso dispensa o ramo `dados`, o `git push --force`, o `contents: write` e a exceção à ADR 0016. A ADR 0002 cita o ramo `dados`, então a troca é do dono; se ele quiser o ramo, entra um quarto job `dados` com `contents: write` e só o push do commit órfão.
- `concurrency: pages`, sem cancelar a execução em curso; `timeout-minutes` por job (120 no `coletar`, 10 nos outros).
- O `schedule`, o `workflow_dispatch` e o ambiente `github-pages` só valem no ramo padrão (`main`): `pages.yml` e o site vão à `main` num PR **antes** da tag `v0.7.0`, e a 0.7.0 só é marcada depois de alguns dias de execução verde (proposta: 3; o dono diz quantos; seção 14).

### 6.2 A coleta

- **O joBot de verdade num banco temporário** (D239.5). `scripts/pages.py coletar` cria um banco em `JOBOT_DADOS` temporário (migrações de sempre), semeia as fontes e as empresas, liga só as fontes com `site` diferente de `fora` em `publicacao.json` e roda `executar_busca` uma vez, com o `ClienteEducado` de sempre: user agent fixo do joBot, intervalo por host, respeito a 429 e `Retry-After`, `max_pedidos` e limite de enriquecimento de `fontes.json`. O tratamento, os rótulos, a remoção de duplicadas e a cotação são os do núcleo. Nada é copiado.
- **Só fontes que listam sem termo de busca** na 0.7.0 (D239.6): o banco temporário não tem buscas, então `termos_das_buscas(con)` é vazio e fonte que monta escopo por termo coleta zero. As fontes por feed e por empresa listam tudo sem termo; o `escopos` de cada fonte ligada foi conferido (seção 5) e um teste liga cada fonte de `publicacao.json` com `site` diferente de `fora` e confere que ela coleta das fixtures sem termo nenhum. Fonte que exige termo fica fora até o desenho de uma lista fixa de termos amplos (pt e en), numa versão seguinte.
- **Token**: a fonte `github_issues` faz até 5 pedidos por repositório a `api.github.com`, que sem token dá 60 pedidos por hora divididos com outros no IP compartilhado do runner. O `coletar` envolve o transporte e põe o `GITHUB_TOKEN` (só leitura) apenas em pedidos https a `api.github.com`, inclusive no `Link rel=next`, com a mesma guarda do `scripts/vigia.py`; o coletor não muda.
- **Bloqueio e falha**: o runner roda num IP de datacenter; 401, 403, desafio ou página de login é "falhou", como na versão local, e nunca se contorna. Fonte que falhou mantém as vagas de ontem (com a data em que foram vistas) até a retenção dela; o site mostra, por fonte, "atualizada em" e o estado.
- **Ritmo**: uma execução por dia está acima de todo `intervalo_min` de `fontes.json` (o maior é 1440 minutos).

### 6.3 Arquivos publicados, tamanho e retenção

- O site publica, em `dados/`: `vagas.json` (lista de vagas no formato da seção 6.4), `fontes.json` (estado e data por fonte), `meta.json` (`coletado_em`, versão do joBot que coletou, versão das regras `rotulos.VERSAO_REGRAS`, versão do formato) e o feed. O `<noscript>` não aponta para esses arquivos.
- **Retenção** (D239.7): vaga que a fonte ainda lista fica; vaga não vista há `retencao_dias` da fonte (proposta: 7) sai; vaga com prazo vencido sai na hora. O site é um retrato, não um acervo: o "nada é apagado" da versão local vale para o banco de cada pessoa, não para este arquivo público.
- **Data da primeira vista**: `coletar` lê o `vagas.json` de ontem e mantém `vista_em` das vagas que já conhecia (mesmo `url_hash`); vaga nova ganha o `coletado_em` desta execução. "Novas" no site são as vagas com `vista_em` igual ao `coletado_em` do `meta.json`, não "de hoje" no relógio de ninguém.
- **Teto**: `max_vagas` por fonte em `publicacao.json` corta primeiro (as mais recentes ficam); `vagas.json` acima de 20 MB (proposta) é a última barreira e faz o passo falhar alto, sem publicar, e o site fica com o de ontem. O resumo do workflow mostra o tamanho e a contagem por fonte. Estimativa revista: de 0,6 a 0,9 KB por vaga em `resumo` (só os nomes de campo por extenso somam perto de 200 bytes) e uns 4 KB com texto inteiro, só na Jobicy; o número real é medido no ensaio (seção 14) e anotado aqui e na D239.7. Os limites do Pages (site publicado até 1 GB, banda de 100 GB por mês) vêm da documentação do GitHub e são conferidos de novo na tarefa do workflow.
- **Enriquecimento e cache**: banco novo a cada dia perde o ETag (nunca há 304) e o cache de 30 dias do enriquecimento: até 50 detalhes por fonte todo dia, e o que passa de 50 nunca ganha detalhe. `actions/cache` não serve, porque um PR de fork lê o cache da `main`. A troca fica registrada (D239.7) e a tarefa dos termos decide, por fonte, se o enriquecimento roda no Pages.
- **Reativação**: o mesmo passo da D218 em toda execução. Isso também fecha o ponto aberto da ADR 0002 ("pushes no ramo `dados` contam como atividade?"): não importa, porque o workflow se reativa pela API.

### 6.4 Formato de uma vaga publicada e limpeza

Um objeto JSON por vaga, com nomes por extenso (o Pages comprime): `url_hash` (o mesmo da versão local, a chave do status e do importar), `fonte`, `titulo`, `empresa`, `locais` (cidade, UF, país), `modalidade`, `nivel`, `area`, `contrato`, `idioma`, `avisos`, `salario` (mínimo, máximo, moeda, período, plausível) e `salario_mensal_brl` (reais inteiros, já convertidos pela PTAX do dia; `null` sem cotação), `publicada_em`, `prazo`, `vista_em`, `url`, `credito` (nome e link da fonte, quando pede) e `descricao_texto` só nas fontes `inteiro`.

**Link**: `url` e o link do `credito` só com `https:`, sem usuário nem senha na URL; o `coletar` confere ao publicar e tira a vaga cujo link não passa, e o site confere de novo (seção 7.4).

**Limpeza** (D239.24). O que dá para cumprir, e só isso, é o que o site e a página Sobre prometem:

1. `limpar_contato` em `titulo`, `empresa` e `descricao_texto` de toda fonte, no `coletar`, antes de qualquer arquivo ser escrito.
2. No texto inteiro, sai também todo URL e todo `@identificador` (perfil do LinkedIn, `t.me/usuario`, `@usuario`).
3. Nome de pessoa **pode** aparecer no texto inteiro (quem recruta assina a vaga) e não há como tirá-lo por regra: a página Sobre diz isso e não promete o contrário. E-mail escrito por extenso ("maria arroba gmail") também passa, como na versão local.
4. **Remoção**: a página Sobre traz um canal de remoção (o contato é o dono quem escolhe; espera o dono) e um arquivo versionado `nucleo/dados/bloqueio.json` (proposta) só com `url_hash` e chave de empresa normalizada, lido pelo `coletar`: o que está ali não é publicado. Um site público copiado por terceiros não se desfaz, e a Sobre diz isso também.

## 7. O site

### 7.1 Estático e com o visual do painel

- `scripts/pages.py montar` gera `site/` a partir de `web/` (templates Jinja2 com `select_autoescape`, JavaScript, CSS só do site) e copia do painel o CSS, a Inter e os ícones, sem duplicar arquivo no repositório (D239.11). As telas do painel são Jinja com HTMX no servidor e não servem ao site: as telas do site são escritas de novo, em JavaScript, com as mesmas classes de CSS. Os motivos do encaixe (`encaixe.*`) e os rótulos de filtro vêm dos catálogos do painel; texto novo do site vai em `web/i18n/{pt,en}.json`, com teste de chaves iguais nas duas línguas, como o do painel.
- Duas árvores, `pt/` e `en/`, geradas no build, com `lang` e `hreflang` em cada página. A raiz manda para a língua guardada em `jobot:lingua`, se houver; senão para `en/` quando a língua do navegador não começa com `pt` (script próprio, não inline); sem JavaScript fica em português. O seletor de língua é um link comum e grava `jobot:lingua`.
- Páginas: Vagas (lista, filtros e detalhe), Buscas, Exportar e importar, Sobre (de onde vêm as vagas, a tabela de fontes com "via" e os termos, a limpeza e seus limites, o canal de remoção, privacidade e a frase de que o GitHub, que hospeda o site, recebe o IP de quem visita). Na 0.8.0, Perfil e o painel "Preparar com IA" no detalhe.
- JavaScript em módulos ES puros, sem build, sem framework (D239.11). O site precisa de JavaScript para listar as vagas; sem ele, um `<noscript>` explica e aponta o link para baixar o joBot.
- **Navegador mínimo**: o que os módulos e as expressões regulares pedem (o lookbehind pede Safari 16.4); a tarefa do site fixa a lista e mostra um aviso, em vez de página em branco, quando o navegador não tem o que falta.
- "Atualizado em <data>" no topo (ADR 0002); com mais de 2 dias sem atualizar, aviso de que a coleta parou.
- **Buscadores**: `noindex` nas páginas de vagas (proposta, D239.25); se a página inicial e a Sobre são indexadas, o dono decide. O site não disputa resultado de busca com as fontes.

### 7.2 O que roda no navegador

- Filtros: texto (normalizado como `texto.normalizar`, sobre título, empresa e texto publicado), fonte, modalidade, nível, área, contrato, país e UF, idioma, salário mínimo em reais, "novas" (seção 6.3), encaixe (bom, médio) e "mostrar ocultas" com a contagem por motivo (ADR 0007).
- Encaixe por regras de cada vaga contra cada busca do visitante (seção 8), com os motivos e as regras de ocultar ligadas.
- Prazo conferido de novo no navegador pelo dia local de quem visita (o runner é UTC): vaga de prazo vencido no dia local não aparece, mesmo que o arquivo seja de ontem.
- Status por vaga e ocultar à mão, no `localStorage` (seção 9).
- Nada de pedido de rede além de buscar `vagas.json`, `fontes.json` e `meta.json` no próprio site.

### 7.3 Faixa "baixe a versão completa"

Presente no topo de toda página, no fluxo do documento, curta, sem fechar (ADR 0002); grudada no topo só em tela larga, com `scroll-padding-top` para não cobrir o foco (WCAG 2.2, 2.4.11 e 1.4.10). Texto proposto (D239.13): pt "Esta é a versão no navegador. A versão para baixar busca em mais fontes, roda sozinha em segundo plano, tem IA e entra nos sites com login." com o link "Baixar o joBot"; en "This is the browser version. The download searches more sources, runs on its own in the background, has AI and reads sites that need a login." com "Download joBot". O link vai à página Instalar da wiki (pt) e Install (en). O visual segue o aviso do painel. Testada em 320×568 e com o texto a 200%.

### 7.4 Segurança da página

- **CSP** em `<meta http-equiv>` (o Pages não deixa pôr cabeçalho), como primeiro filho do `<head>`, antes de qualquer `<link>` ou `<script>` (teste da ordem): `default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; form-action 'none'; base-uri 'none'; object-src 'none'` (proposta, D239.12), mais `require-trusted-types-for 'script'` se a tarefa do site confirmar que vale em meta. Sem script nem estilo inline. `data:` fica fora do `img-src` enquanto nada usar.
- **Limites conhecidos**: `frame-ancestors` não vale em meta; um script próprio sai da moldura quando `top !== self`, para a página com "Apagar tudo" não ser emoldurada. `'self'` em `<dono>.github.io` cobre todo site do Pages da mesma conta, então `script-src` e `connect-src` aceitam os vizinhos.
- **Sem HTML vindo de dado**: todo texto de vaga e de arquivo importado entra por `textContent`. Guarda de texto em `web/**/*.js` proíbe `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `document.write`, `DOMParser`, `srcdoc`, `eval` e `Function(`; teste com `<img src=x onerror=…>` num título confere que nenhum elemento nasce.
- **Links**: só `https:`, sem usuário e senha na URL, conferidos com `new URL` (protocolo e campos `username` e `password` vazios); senão o link some. Teste com `javascript:`, `data:` e `https://a:b@x`. O mesmo vale no Python ao publicar (seção 6.4).
- **Caminhos**: site de projeto fica em `/<repo>/`; todo caminho do site é relativo, e o teste serve o site num subcaminho de `127.0.0.1` para pegar caminho absoluto.
- **Arquivo importado** é lido no navegador, conferido contra o formato (seção 9) e recusado inteiro se não bater.
- **Origem compartilhada**: o `localStorage` é por origem, e `<dono>.github.io` é a mesma origem para todo site do Pages da mesma conta. Outro site do Pages do dono poderia ler o que está guardado ali. As chaves levam o prefixo `jobot:`, a página Sobre diz isso, e um domínio próprio isolaria a origem (espera o dono, opcional; D239.14). Nenhum outro site da mesma conta deve carregar script de terceiros. Na 0.7.0 o site não guarda contato de ninguém (seção 9).

### 7.5 Acessibilidade e lista longa

As mesmas regras de tela do painel (`registros/padroes-tela.md`): contraste nos dois temas, foco visível, rótulo em todo controle, ordem de tabulação, `aria-live` nos avisos, tudo por teclado. Mais o que uma lista de milhares de vagas montada por JavaScript pede: link de pular para o conteúdo; paginação por "mostrar mais"; a contagem anunciada por `aria-live` depois de cada filtro; ao abrir o detalhe, o foco vai para o título dele e volta à vaga ao fechar; endereço por vaga (`#vaga=<url_hash>`), com o botão voltar do navegador fechando o detalhe. Testadas por Playwright como as do painel, sem biblioteca nova.

## 8. Encaixe em JavaScript e paridade

- **O que porta** (D239.9): só `encaixe.calcular` com `_regra_que_bate`, `_faixa`, `_arredondar`, `casar`, `texto.normalizar` e `sem_pontas`, lendo o mesmo `dados/encaixe.json` copiado no build. Rótulos, locais, salário e câmbio ficam no Python do Actions: o site recebe os campos prontos.
- **Normalizar sem reescrever o Unicode à mão** (D239.26). O JavaScript não tem `unicodedata.combining` (`\p{M}` é outro conjunto e tira vogais do tailandês e do devanágari que o Python mantém), `casefold` (`toLowerCase` depende do contexto, como no sigma final, e não dobra `ß`, `ﬁ` nem `ſ`) nem o `split()` do Python (`\s` inclui U+FEFF e deixa de fora U+001C a U+001F e U+0085). O `montar` exporta do Python `texto_tabelas.json`: as faixas de pontos de código com classe de combinação diferente de zero, o mapa de `casefold` dos pontos que mudam e o conjunto de espaços de `str.split()`. O JavaScript aplica `normalize('NFD')` e essas tabelas, e não decide nada de Unicode sozinho.
- **Entradas no site**: `habilidades_vaga` é sempre `null` (neutro), porque a IA não roda no Actions, e por isso `_habilidades` devolve `None` e as habilidades do perfil não entram na nota (D239.18); `regras_ligadas` e `regras_ocultar` vêm da busca; `pais_padrao` é o país que a pessoa escolhe no site (proposta: BR até escolher). O salário mínimo da busca no site é em reais (`minimo_busca_brl` = centavos ÷ 100, inteiro), e a vaga já traz `salario_mensal_brl`; assim nenhum câmbio roda no navegador (D239.10). Busca importada com mínimo em outra moeda guarda a moeda e o valor e trata o mínimo como sem cotação (nota neutra no salário), como a versão local faz sem cotação.
- **Fonte `resumo`**: sem `descricao_texto`, o cargo só casa pelo título (`cargo_titulo`); `cargo_descricao` nunca acontece. A função é a mesma; o dado é que é menor. A página Sobre diz isso.
- **Paridade** (D239.21): um arquivo de casos gerado pelo Python (`tests/fixtures/encaixe_paridade/casos.json`) junta (a) as vagas das nossas fixtures de coletores passadas por `tratar`, cruzadas com uma grade de buscas, e (b) casos de borda escritos à mão: `ß` e `ẞ`, `İ` turco, sigma final, `ﬁ`, `ſ`, NBSP, U+FEFF, U+001C a U+001F, U+0085, marcas combinantes do latim, do tailandês e do devanágari, apóstrofo curvo, `C++`, `C#`, `.NET`, `\w` Unicode da borda de palavra (o JavaScript precisa de `/u` com `\p{L}\p{N}_`), metade no arredondamento. O teste em Python confere que o arquivo bate com `calcular` de hoje (arquivo velho reprova); o teste de tela carrega o módulo JavaScript no Chromium e compara caso a caso, nota, nível, motivos (chave e parâmetros) e regra de ocultar. Mais um teste exaustivo do `normalizar`: cada ponto de código de U+0000 a U+10FFFF, sem os substitutos, comparado no Chromium com o Python, e os casos de vários caracteres. Regra mudou em `encaixe.py` ou `encaixe.json`: o caso gerado muda e o JavaScript reprova até acompanhar (ADR 0007, Consequências).
- **Limite conhecido**: a paridade fica provada no Chromium do Playwright; o `normalize('NFD')` do navegador de quem visita pode ser de outra versão do Unicode. Por isso as tabelas vêm do Python e o NFD é a única peça do navegador.

## 9. Buscas, status e exportar/importar (perfil na 0.8.0)

- **No navegador (0.7.0)**: buscas (os campos de `modelo.Busca`), o país padrão, a língua e o status por `url_hash`, cada um numa chave `jobot:*` do `localStorage`, com "Apagar tudo" na página Exportar e importar. Leitura e gravação em `try/catch`: sem `localStorage` (modo privado, bloqueado), o site funciona sem guardar e avisa. O site não pede nem guarda contato, nome ou perfil na 0.7.0: o perfil não mudaria nada no site, porque as habilidades não entram na nota (seção 8).
- **Retrato mínimo** (D239.27): quando a vaga sai de `nova` (salva, candidatei e as outras), o site guarda com o status um retrato dela: título, empresa, link, fonte e `vista_em`, que são fatos e link, como no `resumo`. Assim quem marcou "candidatei" não perde a vaga quando ela sai do `vagas.json` em 7 dias ou no prazo; a lista de candidaturas do site mostra o retrato.
- **Arquivo `jobot-perfil`** (D239.15): JSON com `formato: "jobot-perfil"`, `versao: 1`, `exportado_em`, `origem` (`local` ou `pages`), `buscas`, `config` (país padrão), `status` (lista de `url_hash`, status, data e o retrato da seção acima) e `perfil`, opcional. Nunca leva chave de serviço, senha, cookie, sessão de site, e-mail lido ou texto de vaga. Na 0.7.0 nenhum dos lados escreve `perfil`; a versão que não conhece um campo opcional o deixa de fora e diz isso no resumo da importação. Com isso a 0.8.0 acrescenta o perfil na mesma versão 1 do formato, sem v2.
- **Versão local**: "Exportar" e "Importar" em Configurações, com o mesmo formato, em `banco` (ler e gravar) e `painel` (botões, CSRF), com texto nos dois catálogos.
- **Importar**: confere formato, versão e tetos de tamanho; mostra o resumo (quantas buscas e status, o que fica de fora e por quê) e só grava depois do OK. Buscas substituem as de agora (com aviso). Evento ou mudança só quando o status muda: importar o mesmo arquivo duas vezes não cria nada na segunda.
- **Vaga que a versão local não conhece** (D239.27): grava pelo `INSERT ... ON CONFLICT(url_hash) DO UPDATE` de sempre. Vaga conhecida: só o status muda (e o evento `mudou_status`, se mudou), o texto fica. Vaga desconhecida: entra com o retrato (título, empresa, link, a data como `primeira_vista_em` e `ultima_vista_em`), `descricao_texto` vazio, sem ocorrência e com o status importado; a lista mostra a marca "importada do site". Nada é apagado.
- **Teste de ida e volta**: o mesmo arquivo de exemplo é importado e exportado pelos dois lados (Python e JavaScript) e volta igual, campo a campo, com uma busca de mínimo em dólar.
- **0.8.0**: Perfil no site (os mesmos campos da 0.6.0, com "Apagar tudo") e o `perfil` escrito e lido pelos dois lados; o teste de ida e volta passa a cobrir o perfil.

## 10. IA manual no site (0.8.0)

- Só as tarefas sob pedido da versão local: `curriculo`, `perguntas`, `candidatura` (D229.1). O encaixe não tem IA manual.
- **O Python continua a fonte da verdade** (D239.16): no build, `montar` exporta `moldes_ia.json` com, por tarefa, as mensagens fixas do pedido, a ordem dos blocos de dados, a frase `PEDE_JSON` por idioma e o esquema sem as descrições (o mesmo de `texto_para_copiar`, D229.6). O JavaScript só preenche os dados e lê a resposta.
- **Paridade**: o texto para copiar montado no JavaScript é igual, byte a byte, ao de `manual.texto_para_copiar` para as mesmas entradas, com a lista permitida e a limpeza de contato de `pedidos` (D227). Os `\d`, `\s` e `\w` do `_CONTATO` são Unicode no Python: portar a expressão à mão diverge, e ali divergência é contato indo para o chat de IA. Os casos de teste da D227 viram um arquivo usado pelos dois lados, com os dígitos e espaços não ASCII, e o `montar` exporta as classes de caracteres que a expressão usa, no molde das tabelas da seção 8. A leitura da resposta colada aceita e recusa os mesmos casos de `ler_resposta` (D229.3), incluindo o teto de 1 MiB e o bloco de código único. A conferência do esquema em JavaScript cobre só as palavras-chave que os esquemas do joBot usam (tipos, `properties`, `required`, `additionalProperties`, tetos de tamanho e de itens, `enum`); palavra-chave nova no esquema reprova um teste até ser coberta.
- **Currículo**: a pessoa cola o texto do currículo (ler PDF no navegador pediria biblioteca nova; fica fora). **Candidatura**: o texto da vaga vem dos dados quando a fonte é `inteiro`; nas outras, a pessoa abre a vaga original e cola o texto, que fica só no navegador.
- Sem chave, sem serviço, sem pedido de rede: quem copia e cola é a pessoa (D229.5).

## 11. Feed e Discord

- **Feed Atom (0.7.0)** (D239.8): `feed.xml` com as vagas novas da última coleta, só das fontes com `feed` sim em `publicacao.json` (a regra da vaga em duas fontes vale aqui), até 200 entradas, só com título, empresa, local, data, "via <fonte>" e o link original. Não leva texto inteiro, nem da Jobicy. A `github_issues` fica com `feed: não`: o título de issue é texto de qualquer conta, e `@everyone`, link mascarado em Markdown ou convite iriam do feed a canais de terceiros.
- **Como o feed é escrito**: por `xml.etree.ElementTree`, nunca por template; caracteres inválidos em XML 1.0 saem antes; link só `https`. O `id` de cada entrada é estável, tirado do `url_hash`. **Sem arquivo anterior** (primeira execução, ou o `vagas.json` de ontem não veio) o feed sai vazio, e vaga de fonte que volta depois da retenção não conta como nova de novo no mesmo dia em que a fonte volta: senão tudo seria novo e inundaria quem segue.
- **Nível 2 da ideia do dono (0.8.0, espera o dono)** (D239.19): um canal do joBot no servidor do dono, do tipo Anúncios (exige o servidor como Comunidade), que qualquer outro servidor **segue** pelo recurso nativo do Discord ("Seguir"): o Discord cria o webhook no servidor de quem segue, e o repositório nunca guarda nada de outro servidor. Sem bot nosso ligado 24 horas, sem estado por servidor, sem moderação nossa nos outros servidores.
  - **Ritmo**: um bot de RSS posta uma mensagem por entrada (até 200 por dia), e a central de ajuda do Discord dá 10 publicações por hora num canal de Anúncios (a revisão leu; a tarefa confere de novo). Por isso a 0.8.0 publica um segundo feed, `resumo.xml`, com **uma** entrada por dia que junta as novas do dia (até 10 vagas, com o link para a lista).
  - Alimentado de um de dois jeitos, que o dono escolhe: (a, recomendada) um bot de RSS da conta do dono lendo o `resumo.xml`: nenhum segredo entra no Actions, e a regra da ADR 0002 fica de pé; o custo é depender de um serviço de terceiros e do atraso dele. (b) o próprio workflow posta por um webhook do canal do dono, com `allowed_mentions` vazio, guardado como segredo num Environment protegido do GitHub, usado só no agendamento na `main` (PR de fork não vê segredo). Mais simples e sem terceiros, mas abre uma exceção na ADR 0002, que só o dono pode abrir; e, pelo que a revisão sabe e não confirmou, mensagem de webhook num canal de Anúncios não chega aos seguidores sem alguém publicar ou sem um bot com token. **Antes de o dono escolher**, a tarefa confere na documentação do Discord o limite de publicações e se a mensagem de webhook é repassada aos seguidores.
- **Nível 1** (webhook no painel local, cada pessoa no seu canal) é da versão local e fica fora desta fase; vira tarefa pequena da versão local quando o dono quiser (espera o dono).

## 12. Escolhas desta sessão (D239)

Cada item é escolha da sessão, para discutir com o dono, com o desfazer no `duvidas.md` (D239.n é o item n desta lista).

1. Termos: fonte sem anotação fica fora; `publicacao.json` com `site`, `feed`, `retencao_dias`, `max_vagas`, endereço, data e trecho por fonte; teste exige toda chave de `descobrir()` e trecho não vazio fora do `fora`. Texto inteiro só na Jobicy.
2. Remotive fora do site e do feed, apesar de a API existir para exibir vagas: o termo cita agregadores como o tipo de site proibido, e o site do joBot é um agregador.
3. Fontes sem leitura nesta rodada ficam fora até a tarefa de leitura da 0.7.0, com as brasileiras primeiro.
4. Workflow `pages.yml` com agenda diária às 7:41 UTC, à mão e push na `main`; só com `vars.JOBOT_PAGES` ligada; três jobs com permissões mínimas; sem segredo; deploy pelas Actions oficiais do Pages com `environment: github-pages`.
5. A coleta é o executor de verdade num banco temporário, sem cópia do núcleo; o `GITHUB_TOKEN` só nos pedidos a `api.github.com`.
6. Na 0.7.0, só fontes que listam sem termo de busca.
7. Sem ramo `dados` (o `vagas.json` de ontem vem do próprio site publicado; espera o dono, porque a ADR 0002 cita o ramo); retenção por fonte (7 dias, proposta) e prazo vencido; `max_vagas` por fonte e teto de 20 MB; enriquecimento sem cache, decidido por fonte.
8. Feed Atom das vagas novas, só metadados, até 200 entradas, só fontes com `feed` sim (a `github_issues` não), escrito por `ElementTree`, vazio sem arquivo anterior.
9. Rótulos e tratamento no Python do Actions; só o encaixe e a normalização em JavaScript.
10. Salário mínimo da busca no site em reais; busca importada em outra moeda fica sem cotação; o câmbio fica no Actions.
11. Código fora do pacote: `scripts/pages.py` e `web/`; JavaScript puro em módulos ES, sem npm nem build; o build copia CSS, fonte e ícones do painel, e as telas são refeitas.
12. CSP em meta, como primeiro filho do `<head>`, sem nada inline, só `'self'`, sem `data:`; saída da moldura por script.
13. Texto da faixa (pt e en), destino do link (página Instalar da wiki) e faixa no fluxo, grudada só em tela larga.
14. Origem compartilhada do `github.io`: prefixo `jobot:` e aviso; domínio próprio fica com o dono.
15. Formato `jobot-perfil` versão 1, nos dois lados, com `perfil` opcional desde já; importar mostra o resumo e só grava com OK.
16. Esquemas e moldes da IA exportados do Python no build; o JavaScript não tem fonte própria deles.
17. Chave do visitante (Haiku) fora desta fase: chave no `localStorage` fica ao alcance de qualquer falha de script da origem compartilhada, a CSP teria de abrir a API de fora e a chamada direta do navegador pede o cabeçalho de acesso direto da Anthropic.
18. Habilidades por IA nas vagas do site (o Laya no runner, em CPU): só depois de medir; fora desta fase.
19. Discord: feed na 0.7.0; canal de Anúncios do dono que outros servidores seguem na 0.8.0, com um feed de resumo diário, alimentado por bot de RSS (recomendado) ou por webhook em segredo (exceção na ADR 0002, só com o dono).
20. Versões: 0.7.0 (coleta, site, encaixe, buscas, país, status, exportar e importar disso, faixa, feed) e 0.8.0 (perfil, IA manual e canal do Discord).
21. Testes do JavaScript no Chromium do Playwright, a partir do pytest, sem Node no projeto.
22. Himalayas fora na 0.7.0 (o coletor só lista por termo, e o termo pede retenção diária, nada de feed nem de `JobPosting` e crédito visível); as condições de volta ficam na seção 5.
23. We Work Remotely fora até uma pessoa ler os termos num navegador e anotar o trecho.
24. Limpeza: `limpar_contato` em título, empresa e texto de toda fonte; URLs e `@identificadores` fora do texto inteiro; nome de pessoa pode aparecer e a Sobre diz isso; canal de remoção e `bloqueio.json`.
25. `noindex` nas páginas de vagas; nenhum `JobPosting`; nenhum `rel="nofollow"` nos links de crédito.
26. Normalização no JavaScript por tabelas exportadas do Python, com teste exaustivo dos pontos de código; navegador mínimo declarado, com aviso.
27. Retrato mínimo da vaga junto do status, no navegador e no arquivo; vaga desconhecida entra na versão local com o retrato e texto vazio.
28. A 0.7.0 só é marcada depois de `pages.yml` e o site irem à `main` num PR e rodarem alguns dias verdes (proposta: 3).

## 13. Testes

- **Política**: toda chave de `descobrir()` em `publicacao.json`; fonte fora do `fora` com endereço, data e trecho não vazios; `fora` nunca coletada; `resumo` nunca leva `descricao_texto`; `feed` não nunca no feed; vaga em duas fontes segue a mais restritiva (cada um com controle positivo).
- **Fonte sem termo**: cada fonte com `site` diferente de `fora` coleta das fixtures num banco sem buscas (controle: a Himalayas coleta zero, o que mostra que o teste vê o caso).
- **Coleta com dados falsos**: `scripts/pages.py coletar` com transporte falso servindo as fixtures das fontes ligadas, banco em `tmp_path`, relógio injetado; confere o `vagas.json` (formato, `url_hash` igual ao da versão local, `vista_em` mantido de um `anterior` falso, retenção por fonte, prazo vencido fora, fonte que falhou mantém as de ontem, `max_vagas`, teto de tamanho falha, link `javascript:` ou com usuário tirado, `bloqueio.json` respeitado). O token só aparece em pedido https a `api.github.com` (controle: aparece lá). Sem rede.
- **Limpeza, com controle positivo**: e-mail e telefone no título e na empresa saem; `linkedin.com/in/…`, `t.me/usuario` e `@usuario` saem do texto inteiro; o e-mail disfarçado ("maria arroba gmail") passa, e o teste diz isso, para a promessa da Sobre não crescer sem a regra.
- **Feed**: só novas, só `feed` sim, 200 no máximo, vazio sem arquivo anterior, `id` estável; título com `]]>`, `&`, `\x0b` e link `javascript:` não quebram nem passam. `montar` escapa `<script>` num campo (o `select_autoescape` ligado).
- **Workflow por texto, por job**: `pages.yml` sem `pull_request`, sem `pull_request_target`, sem `secrets.`; `contents: read` no topo; cada job com as permissões listadas e só elas (`coletar` sem escrita, `publicar` com `pages` e `id-token` e `environment: github-pages`, `reativar` com `actions: write` e `if: always()`); a condição `vars.JOBOT_PAGES`; Actions fixadas por hash (como a guarda do vigia em `test_vigia.py`).
- **Site (Playwright, `-m tela`, no CI)**: o `site/` montado com dados falsos e servido num subcaminho de `127.0.0.1`; filtros; encaixe e motivos; status, retrato e ocultar sobrevivem a recarregar; sem `localStorage` o site funciona; exportar e importar; faixa em toda página nas duas línguas, em 320×568 e com texto a 200%; paginação, contagem em `aria-live`, foco do detalhe e `#vaga=`; nenhum pedido de rede fora da origem (o teste escuta os pedidos da página); CSP primeiro no `<head>` e sem violação no console; título com `<img src=x onerror=…>` não cria elemento; link `javascript:` some; saída da moldura; prazo pelo dia local; aviso de navegador antigo; acessibilidade como no painel.
- **Paridade**: encaixe e `normalizar` exaustivo (seção 8), ida e volta do `jobot-perfil` (seção 9) e, na 0.8.0, texto para copiar, limpeza de contato e leitura da resposta (seção 10).
- **Guardas de texto**: nenhum `http://` ou `https://` literal em `web/` além da lista permitida (links da wiki e do repositório); nenhum `innerHTML` e família em `web/**/*.js` (seção 7.4); nenhum `JobPosting` nem `application/ld+json` no site montado; nenhum `rel="nofollow"`; `noindex` nas páginas de vagas.
- Nesta máquina, só o arquivo de teste da tarefa e o ruff; suíte inteira, `-m tela` e mypy no CI, como sempre.

## 14. Versões e tarefas

As tarefas estão no plano `docs/superpowers/plans/2026-11-24-fase-8.md` (T800 a T816 na 0.7.0, T830 a T836 na 0.8.0). A ordem da 0.7.0: termos e `publicacao.json`; limpeza e bloqueio; `coletar`; tabelas e `normalizar`; encaixe e paridade; `montar` e a base do site; telas; buscas; formato e importar nos dois lados; feed; `pages.yml`; PR na `main` e dias verdes com a medida do tamanho; documentos; release. A ordem da 0.8.0: perfil; moldes e contato; painel de IA; Discord; documentos; release.

## 15. O que fica fora

Sites com login, Gmail, extensão, IA automática, áudio e segundo plano (ADR 0002); a chave do visitante (D239.17); habilidades por IA nas vagas do site (D239.18); fontes que pedem termo de busca (D239.6), entre elas a Himalayas (D239.22); fontes sem termos lidos (D239.3), entre elas a WWR (D239.23); Remotive, Hacker News e Gupy (seção 5); leitura de PDF no navegador; busca com índice; acervo histórico; o nível 1 do Discord (versão local); domínio próprio (dono).

## 16. O que espera o dono

- Confirmar a ordem nova das fases (D238): a sessão recebeu a pergunta dele e a decisão pelo texto da tarefa, e não tem um "sim" dele depois da pergunta.
- Ligar o Pages no repositório (Settings › Pages › Source: GitHub Actions) e a variável `JOBOT_PAGES` = `sim` antes do primeiro deploy.
- Ramo `dados` ou não (D239.7): a proposta é ler o `vagas.json` de ontem do próprio site, sem o ramo; a ADR 0002 cita o ramo, então a troca é dele.
- O contato do canal de remoção na página Sobre (D239.24).
- Quantos dias de execução verde antes da tag `v0.7.0` (proposta: 3; D239.28).
- Se a página inicial e a Sobre são indexadas pelos buscadores (D239.25).
- Confirmar ou trocar as escolhas da D239, em especial a Remotive fora (D239.2), a Himalayas e a WWR fora (D239.22 e 23) e texto inteiro só na Jobicy (D239.1).
- WWR: ler as duas páginas de termos num navegador, se a sessão não conseguir abrir (D239.23).
- Discord (0.8.0): criar o servidor ou o canal de Anúncios (Comunidade) e escolher entre bot de RSS da conta dele e webhook em segredo (exceção na ADR 0002), depois da conferência da documentação.
- Domínio próprio, se quiser isolar a origem do `localStorage` (D239.14).

## 17. Revisão (2026-11-24)

A revisão do desenho achou 2 pontos que bloqueavam, 7 importantes e 11 menores, todos tratados aqui: a Himalayas não coleta sem termo de busca e tem condições de termo sem resposta (seção 5); a garantia "nenhum contato" não era o que `limpar_contato` entrega (seção 6.4); a WWR sem trecho lido (seção 5); o job único com escrita demais e sem `environment` (seção 6.1); feed sem escape e Discord sem conta de ritmo (seção 11); paridade de Unicode feita à mão (seção 8); perfil pedido na 0.7.0 sem uso (seção 9); status sem retrato (seção 9); e os menores de segurança da página, caminhos, acessibilidade, tamanho, token, dia local, vaga em duas fontes, moeda importada, buscadores e o ensaio só depois da `main`. As escolhas novas estão na D239.22 a D239.28.
