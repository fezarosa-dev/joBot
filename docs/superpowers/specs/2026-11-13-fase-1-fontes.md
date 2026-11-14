# joBot — Fase 1: apêndice de fontes

- **Data da conferência:** 2026-11-13
- **Acompanha:** [desenho da fase 1](2026-11-13-fase-1-design.md)
- **O que é:** os fatos que o construtor precisa para escrever cada coletor. Tudo aqui foi visto ao vivo em 2026-11-13, por captura própria, sem login.
- **O que não tem:** amostra de vaga, dado pessoal, nome de recrutador ou e-mail. As amostras de teste nascem na captura de cada fonte (desenho, seção 9).

Marcas usadas:

- **[a confirmar]** — ponto que a conferência não testou. O construtor confere na captura da fonte e corrige este apêndice.

A Q6 (termos de uso) foi decidida pelo dono em 2026-11-13: Meta fora; Eureca, Abler e Gupy dentro, cada uma com chave liga/desliga, ritmo educado, link para a vaga original e aviso no README (seção 4; desenho, seção 20.2). Não há mais marca de espera neste apêndice.

Regra de leitura: quando o site mudar e este apêndice ficar errado, vale o site. O construtor corrige o apêndice no mesmo commit do coletor.

---

## 1. Regras que valem para toda fonte

1. Só endereço público, sem login. Nunca contornar login, CAPTCHA nem bloqueio contra robôs.
2. O `robots.txt` não bloqueia a coleta (decisão do dono, Q1). A educação vem de outro lugar: user agent honesto, intervalo, obediência a 429 e `Retry-After`, limites documentados.
3. User agent: `joBot/<versão> (+https://github.com/fezarosa-dev/joBot)`.
4. Intervalo mínimo por host: 1 s. Onde este apêndice pede mais, vale o maior.
5. Pedido condicional sempre que a fonte devolve `ETag` ou `Last-Modified`. Resposta 304 conta como "sem mudança" (desenho, seção 10.2).
6. Teto de resposta: 5 MB. As exceções estão marcadas em cada fonte (Google e Common Crawl).
7. O link que o painel abre é sempre o da vaga na origem. O joBot não republica vaga.
8. Crédito "via <fonte>" com link é obrigatório nas cinco fontes da seção 2.2 e mostrado em todas as outras.
9. Nenhum coletor guarda e-mail, telefone, nome de recrutador ou autor da postagem.
10. `intervalo_min` (minutos entre execuções da fonte) existe em sete fontes. Em três, porque os termos ou os limites pedem: Remotive 360, Jobicy 60 e We Work Remotely 60. Em quatro, como intervalo prático, por decisão da sessão em 2026-11-13, sem exigência dos termos: Google 1440, Himalayas 1440, RemoteOK 360 e Amazon 360. As outras fontes não têm. O "buscar agora" respeita o `intervalo_min` (desenho, seção 8.3).

Falta conferir em todas: os testes do grupo B1 e B3 e o da PTAX usaram um user agent genérico. O construtor repete o primeiro pedido de cada fonte com o user agent do joBot e registra se algo muda.

---

## 2. Leva A

### 2.1 GitHub Issues

- **Endereço:** `GET https://api.github.com/repos/{org}/{repo}/issues`
- **Repositórios (nome exato) e vagas abertas vistas:**

| Repositório | Abertas | Observação |
|---|---|---|
| `backend-br/vagas` | 42 | ativo |
| `frontendbr/vagas` | 8 | ativo |
| `soujava/vagas-java` | 16 | ativo |
| `remotejobsbr/design-ux-vagas` | 15 | só design e UX; poucas vagas vivas |
| `developersRJ/vagas` | 8 | parado; última vaga de agosto de 2026 |

- **Parâmetros:** `state=open`, `per_page=100` (máximo), `sort`, `direction`, `since`, `labels` (várias = E), `page`.
- **Paginação:** seguir o cabeçalho `Link` com `rel="next"`. Não montar a URL da página seguinte à mão. Na captura, o `Link` aponta para `/repositories/<id>/issues?...&page=2&after=<cursor>`, não para o caminho `/repos/{org}/{repo}/issues` do pedido, e o coletor o segue como vier. Nenhum dos cinco repositórios passou de uma página.
- **Autenticação:** nenhuma. Sem token, o limite é de 60 pedidos por hora por IP. O IP pode ser compartilhado com outros programas da casa.
- **Cache:** devolve `ETag` e `cache-control: max-age=60`. `If-None-Match` devolveu 304. Não foi confirmado se o 304 poupa a cota.
- **Cota esgotada:** esperada como 403 ou 429, com `x-ratelimit-remaining: 0`. Não foi capturada (não se gasta a cota de propósito); o tratamento está na D51.
- **Campos:**
  - id externo: `owner/repo#number`;
  - título: `title`;
  - descrição: `body`, em Markdown;
  - etiquetas: `labels[].name`;
  - datas: `created_at`, `closed_at`;
  - link: `html_url`;
  - estado: `state` e `state_reason` (`completed`, `not_planned`, `reopened`).
- **Descartar:** todo item que tem a chave `pull_request`. A API de issues devolve pull requests junto.
- **Descrição:** Markdown de formulário ou de modelo, com seções `##` ou `###`. Nem toda postagem segue o modelo. O leitor precisa ser tolerante: seção ausente não é erro.
- **Etiquetas mudam por repositório:**
  - `backend-br/vagas`: `Remoto`, `Híbrido`, `Presencial`; de `Estagiário` a `Especialista`; `CLT`, `PJ`, `Contrato`, `Freelance`; e de moderação (`verificada`, `em-triagem`, `Stale`, `link-quebrado`);
  - `frontendbr/vagas`: etiquetas de estado (UF), `Freela`, `Alocado`;
  - `soujava/vagas-java`: `HomeOffice`, `Semi-presencial`, `job opportunity`;
  - `remotejobsbr/design-ux-vagas`: `Junior`, `Pleno`, `Senior`, sem acento;
  - `developersRJ/vagas`: faixas de salário em etiqueta (por exemplo `1k-5k`, com emoji na frente).
- **Fechamento:** coletar só `state=open`. Vaga fechada some da lista. O título de issue fechada às vezes vira "Vaga encerrada".
- **Contagem:** `open_issues_count` do repositório inclui pull requests. Não usar como total de vagas.
- **Termos:** os Termos de Serviço do GitHub (seção H) e a política de uso aceitável (seção 7) proíbem spam e venda de dado pessoal. Não pedem atribuição. O joBot não extrai contato do texto; só mostra o link.

### 2.2 APIs públicas de vaga remota

As cinco fontes desta seção exigem crédito com link de volta. O painel mostra "via <fonte>" com link para a vaga na origem.

#### Remotive

- **Endereço:** `GET https://remotive.com/api/remote-jobs`. Categorias em `GET https://remotive.com/api/remote-jobs/categories`.
- **Resposta:** `{job-count, total-job-count, jobs[]}`, mais as chaves `00-warning` e `0-legal-notice` na raiz (avisos de uso, não são vagas). Sem paginação. 16 vagas no dia da conferência. Devolve `Last-Modified`, não devolve `ETag`.
- **Filtros:** `category`, `company_name`, `search` e `limit` existem na documentação, mas não mudaram a resposta no teste. Filtrar localmente.
- **Campos:** `id`, `title`, `company_name`, `candidate_required_location`, `salary` (texto livre), `publication_date` (ISO sem fuso), `url`, `description` (HTML), `job_type`, `category`, `tags` (lista), `company_logo` e `company_logo_url`.
- **Limites:** no máximo cerca de 4 consultas por dia. Mais de 2 por minuto é bloqueado. As vagas entram na API com 24 horas de atraso.
- **Termos e atribuição:** link de volta para a URL da vaga na Remotive e crédito à Remotive. Proíbe repassar as vagas para site de terceiros.
- **`intervalo_min` da fonte:** 360.

#### RemoteOK

- **Endereço:** `GET https://remoteok.com/api`
- **Resposta:** lista JSON. O primeiro elemento não é vaga: traz `last_updated` e `legal`. Pular.
- **Filtro:** só `?tag=` funciona. Sem paginação. Devolve as cerca de 100 vagas mais novas (98 vistas). Cada resposta pesa perto de 600 KB.
- **Campos:** `id` (texto), `position`, `company`, `location` (muitas vezes vazio), `salary_min` e `salary_max` (dólar por ano; 0 quer dizer ausente), `date` (ISO com fuso) e `epoch` (inteiro), `url`, `apply_url`, `description` (HTML), `tags` (lista), `slug`, `logo` e `company_logo`. A `url` e a `apply_url` trazem `remoteOK.com` em caixa mista.
- **Cuidado:** forçar UTF-8 na leitura: o `Content-Type` vem sem `charset`. Não há `ETag` nem `Last-Modified`.
- **Termos e atribuição:** link de volta para a URL da vaga, sem `rel="nofollow"`, citando "Remote OK". Não usar o logotipo.
- **Limites:** nenhum limite numérico publicado. Cada resposta pesa perto de 600 KB; o coletor faz um pedido por execução.
- **`intervalo_min` da fonte:** 360. É intervalo prático, decisão da sessão em 2026-11-13; os termos não pedem.

#### Jobicy

- **Endereço:** `GET https://jobicy.com/api/jobs`. O endereço antigo `/api/v2/remote-jobs` ainda responde, mas o coletor usa o novo.
- **Parâmetros:** `count` (1 a 100), `cursor`, `geo` (por exemplo `geo=brazil`), `industry`, `tag`. Listas de valores em `?get=locations` (55) e `?get=industries` (22).
- **Paginação:** por cursor (`nextCursor`, `hasMore`). O cursor vale 24 horas. Cursor vencido ou filtro trocado no meio devolve 400.
- **Janela:** só vagas dos últimos 7 dias. Vaga nova aparece 3 horas depois de publicada.
- **Campos:** `id`, `jobTitle`, `companyName`, `jobGeo`, `salaryMin`, `salaryMax`, `salaryCurrency`, `salaryPeriod` (pouco confiáveis), `pubDate` (ISO com fuso), `url`, `jobDescription` (HTML), `jobExcerpt`, `jobLevel`, `jobIndustry[]`, `jobType[]` (as duas são listas). `jobGeo` é texto livre.
- **Raiz da resposta:** `apiVersion`, `documentationUrl`, `friendlyNotice`, `jobCount`, `lastUpdate`, `nextCursor`, `hasMore`, `appliedFilters`, `statusCode`, `success` e `jobs[]`. Devolve `Last-Modified`, não devolve `ETag`. Resultado vazio é 200 com uma `message` e `nextCursor` nulo.
- **Termos e atribuição:** crédito claro à Jobicy com link direto. O botão de candidatura aponta para a página da vaga na Jobicy.
- **Limites:** começar uma nova passada automática no máximo uma vez por hora. `intervalo_min` da fonte: 60.
- **[a confirmar]:** `GET https://jobicy.com/api/jobs/status?ids=` (consulta de estado por id) não foi testado.

#### Himalayas

- **Endereços:**
  - busca: `GET https://himalayas.app/jobs/api/search` — o coletor usa este;
  - lista geral: `GET https://himalayas.app/jobs/api` (119.361 vagas; não usar para varrer tudo).
- **Parâmetros da busca:** `q`, `country` (ISO de duas letras), `worldwide`, `exclude_worldwide`, `seniority`, `employment_type`, `company`, `timezone`, `sort=recent`, `page` (começa em 1). 20 por página.
- **Teste:** `q=python&country=BR&sort=recent` devolveu `totalCount` 949.
- **Campos:** `guid` (URL canônica da vaga; é o id), `title`, `companyName`, `companySlug`, `locationRestrictions[]`, `timezoneRestrictions[]`, `minSalary`, `maxSalary`, `currency`, `salaryPeriod`, `pubDate` (epoch em segundos; é a data da última atualização), `expiryDate` (epoch), `applicationLink`, `description` (HTML), `excerpt`, `seniority[]`, `employmentType`, `categories`, `parentCategories` e `companyLogo`.
- **Raiz da resposta:** `comments`, `updatedAt`, `offset`, `limit`, `totalCount` e `jobs[]`. `pubDate` e `expiryDate` vêm em segundos desde 1970. Devolve `Last-Modified`.
- **Termos e atribuição (termos da API, cláusula 113):** o botão de candidatura usa o `applicationLink` sem mudar nada. O painel identifica a Himalayas como fonte, com link visível. Proíbe repassar para outros sites de vaga. Pede cache, respeito aos limites e remoção de vaga vencida. No joBot, a vaga vencida sai das listas do painel; o registro dela fica no banco, só no computador da pessoa (desenho, seção 7.6).
- **Cuidado:** a limpeza de parâmetros de rastreamento (desenho, seção 10.1) não toca no `applicationLink`. A chave de duplicata usa o `guid`.
- **Limites:** sem chave, o limite é menor e não é publicado. Os dados mudam uma vez por dia. Regra do coletor: até 30 pedidos por execução, 2 s entre eles.
- **`intervalo_min` da fonte:** 1440, porque os dados mudam uma vez por dia. É intervalo prático, decisão da sessão em 2026-11-13; os termos não pedem intervalo. O que não couber nos 30 pedidos fica para o dia seguinte.

#### We Work Remotely

- **Endereços:** `https://weworkremotely.com/remote-jobs.rss` (geral, 100 itens) e `https://weworkremotely.com/categories/<slug>.rss`.
- **Categorias:** `all-other-remote-jobs`, `remote-back-end-programming-jobs`, `remote-customer-support-jobs`, `remote-design-jobs`, `remote-devops-sysadmin-jobs`, `remote-front-end-programming-jobs`, `remote-full-stack-programming-jobs`, `remote-management-and-finance-jobs`, `remote-product-jobs`, `remote-programming-jobs`, `remote-sales-and-marketing-jobs`.
- **Formato:** RSS 2.0.
- **Campos:** `<title>` no formato "Empresa: Cargo" (cortar no primeiro ": "), `<link>` igual ao `<guid>`, `<pubDate>` (RFC 822), `<region>`, `<category>`, `<description>` (HTML escapado). Os feeds de categoria também trazem `<expires_at>`, `<type>`, `<skills>`, `<country>` e `<state>`, como o geral (conferido em `remote-devops-sysadmin-jobs`). Ordem dos elementos de cada item: `title`, `region`, `country`, `state`, `skills`, `category`, `type`, `description`, `pubDate`, `expires_at`, `guid`, `link`. Alguns itens trazem também `<media:content>`. O `<country>` começa com a bandeira em emoji, que o coletor tira. O feed geral e os de categoria devolvem `ETag` fraco.
- **Limites:** `<ttl>60` e `cache-control: max-age=3600`. No máximo uma leitura por hora por feed. `intervalo_min` da fonte: 60.
- **Termos e atribuição:** os links têm de apontar de volta para o We Work Remotely.
- **Cuidado:** alguns feeds de categoria ficam atrasados em relação ao geral.

### 2.3 Hacker News — "Who is hiring"

- **Achar o tópico do mês:** `GET https://hn.algolia.com/api/v1/search_by_date?query="Ask HN: Who is hiring"&tags=story,author_whoishiring&hitsPerPage=5`
  - aceitar só título que começa com "Ask HN: Who is hiring?";
  - ignorar "Who wants to be hired?" e "Freelancer? Seeking freelancer?";
  - o tópico novo aparece no dia 1 ou 2 de cada mês.
- **Ler os comentários:** `GET https://hn.algolia.com/api/v1/items/<id do tópico>` — um pedido só, cerca de 440 KB, 242 comentários de primeiro nível em `children[]`. Só o primeiro nível é vaga.
- **Alternativa paginada:** `search_by_date?tags=comment,story_<id>&hitsPerPage=100&page=N`.
- **Campos:** `id`, `created_at`, `text` (HTML com entidades e `<p>` sem fechar); a resposta traz ainda `author`, `children`, `created_at_i`, `options`, `parent_id`, `points`, `story_id`, `title`, `type` e `url`, que o coletor não usa. Não há `ETag` nem `Last-Modified`. Link da vaga: `https://news.ycombinator.com/item?id=<id>`.
- **Primeira linha:** costuma ser `Empresa | Cargo | Local | REMOTE ou ONSITE | …`. É só costume. O leitor tenta e, se não der, guarda o texto inteiro como descrição.
- **Não guardar:** o autor do comentário.
- **Limites:** nenhum limite oficial publicado na API. Uma leitura por execução basta.
- **Termos:** nunca buscar páginas de `news.ycombinator.com`. Os termos do site proíbem a raspagem. O coletor usa só a API de busca.

### 2.4 ATS com lista pública por empresa

#### Greenhouse

- **Endereço:** `GET https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`
- **Extras:** detalhe em `/jobs/{id}?pay_transparency=true`. Nome da empresa em `/v1/boards/{token}`.
- **Paginação:** nenhuma. A lista inteira vem numa resposta (`meta.total`).
- **Campos:** `id`, `title`, `company_name`, `location.name`, `first_published` (ISO com fuso), `updated_at`, `application_deadline`, `absolute_url`, `content`, `departments`, `offices`, `language`.
- **Não tem:** campo de remoto, de salário ou de nível. Saem do texto.
- **Descrição:** HTML **escapado em entidades**. Passar por `html.unescape` antes de limpar.
- **Cuidados:** `absolute_url` pode apontar para o site da empresa, com `?gh_jid=`. A resposta chega a cerca de 3 MB em quadros grandes.
- **Erros:** identificador inexistente devolve 404 com `{"status":404,"error":"Job not found"}`. Quadro vazio devolve 200 com zero vagas.
- **Limites e termos:** nenhum limite nem atribuição documentados.
- **[a confirmar]:** o host da União Europeia (`boards-api.eu.greenhouse.io`) não foi testado. Os termos de uso gerais do Greenhouse não foram lidos; só a documentação da API.

#### Lever

- **Endereço:** `GET https://api.lever.co/v0/postings/{site}?mode=json`
- **Paginação:** `skip` e `limit`. Sem eles, vem tudo.
- **Campos:** `id` (UUID), `text` (título), `categories.location`, `categories.allLocations`, `categories.commitment`, `categories.department`, `categories.team`, `country`, `workplaceType` (`remote`, `hybrid`, `onsite`), `salaryRange{currency,interval,min,max}` (opcional; não apareceu ao vivo), `createdAt` (epoch em **milissegundos**), `hostedUrl`, `applyUrl`, `descriptionPlain`, `description`, `lists[]`, `additional`, além de `opening`, `descriptionBody` e as versões `Plain` de `opening`, `descriptionBody` e `additional`. O `salaryRange` não apareceu na captura da `starkbank`.
- **Não tem:** nome da empresa. Usar o nome da lista de empresas.
- **Cache e paginação:** devolve `ETag` fraco. `skip` além do total devolve 200 com lista vazia.
- **Erros:** identificador inexistente devolve 404 com `{"ok":false,"error":"Document not found"}`.
- **Limites:** nenhum documentado. Manter 1 s entre pedidos.
- **[a confirmar]:** o host da União Europeia (`api.eu.lever.co`) não foi testado.

#### Ashby

- **Endereço:** `GET https://api.ashbyhq.com/posting-api/job-board/{nome}?includeCompensation=true`
- **Paginação:** nenhuma.
- **Campos:** `id` (UUID), `title`, `location`, `secondaryLocations`, `address.postalAddress`, `isRemote`, `workplaceType` (`Remote`, `Hybrid`, `OnSite`; só `Remote` foi visto), `compensation.scrapeableCompensationSalarySummary` (texto curto com a faixa), `compensation.compensationTierSummary`, `compensation.compensationTiers[].components[]` (`compensationType`, `interval`, `currencyCode`, `minValue`, `maxValue`), `publishedAt` (ISO com fuso), `jobUrl`, `applyUrl`, `descriptionHtml`, `descriptionPlain`, `department`, `team`, `employmentType`, `isListed`.
- **Raiz da resposta:** `{jobs[], apiVersion}`. Na `compensation` há também `shouldDisplayCompensationOnJobPostings`, e a `belvo` traz campos nulos. Devolve `ETag` fraco.
- **Filtrar:** só `isListed=true`.
- **Não tem:** nome da empresa. Usar o nome da lista de empresas.
- **Erros:** identificador inexistente devolve 404 em texto puro ("Not Found").
- **Cuidados:** a resposta chega a 4,5 MB com remuneração. Fica perto do teto de 5 MB. `cache-control: max-age=60`.

#### SmartRecruiters

- **Lista:** `GET https://api.smartrecruiters.com/v1/companies/{id}/postings?limit=100&offset=0&country=br`
- **Paginação:** `limit` (máximo 100) e `offset`. Resposta `{offset, limit, totalFound, content[]}`.
- **Filtros:** `q`, `country` (ISO em minúsculas).
- **Campos da lista:** `id`, `name`, `company.name`, `location{city, region, country, remote, hybrid, fullLocation}`, `releasedDate` (ISO em UTC), `experienceLevel`, `department`, `function`, `typeOfEmployment`. A captura traz ainda `uuid`, `jobAdId`, `refNumber`, `industry`, `customField`, `defaultJobAd`, `location.address` e `location.hybridDescription`.
- **A lista não traz descrição.** Detalhe: `GET https://api.smartrecruiters.com/v1/companies/{id}/postings/{postingId}`, com `jobAd.sections.{companyDescription, jobDescription, qualifications, additionalInformation}.text` (HTML), `postingUrl` e `applyUrl`. O detalhe traz também `creator` (vazio). Devolve `ETag`.
- **Cuidados:** o identificador diferencia maiúsculas de minúsculas. Empresa inexistente devolve 200 com `totalFound=0`: zero vagas não prova que o identificador está certo.
- **Custo:** um pedido de detalhe por vaga. O detalhe entra no orçamento de enriquecimento (desenho, seção 10.6).
- **Limites e termos:** a API de vagas é documentada como pública e sem chave. Nenhum limite oficial publicado.

### 2.5 Gupy

- **Endereço:** `GET https://portal.gupy.io/api/job-search/jobs`
- **Parâmetros testados:** `jobName` (termo; sem ele lista tudo), `limit` (até 100; 200 devolve 400), `offset`, `sortBy=publishedDate`, `sortOrder=desc`, `workplaceType` (`remote`, `hybrid`, `on-site`), `state` (nome por extenso), `type`, `isPWD`.
- **Parâmetros [a confirmar]:** `city` e `badge` existem no código do portal, mas não foram testados ao vivo.
- **Busca por empresa (`careerPageName`, decisão 29, conferida na captura de 2026-11-14):** o parâmetro funciona. A API aceita o `careerPage.publicationName`, sem espaços nas pontas, que está no `<script id="__NEXT_DATA__">` da página `https://<identificador>.gupy.io/`, em `props.pageProps.careerPage`. O `name` e o `<title>` da página não servem. A comparação é por caixa exata: `Agriness` devolve 4 vagas e `agriness` devolve 0. O `jobUrl` das vagas tem o host `<identificador>.gupy.io`, e, só no escopo de empresa, vaga de outro host é descartada pelo coletor (o escopo `cargo:` não filtra host, D53). O `careerPageUrl` vem vazio. Nove empresas do `empresas.json` levam o nome em `parametros.careerPageName`: `porto`, `vempracbc`, `beepsaude`, `hapvidandi`, `spdmpaisfor`, `afyamedicina`, `cnaidiomas`, `ihara` e `ourofinoagro`. O resolver da Gupy devolve o `careerPageName` junto com o identificador, e a T51 grava esse par em `parametros` (D53).
- **Resposta:** `{data[], pagination{total, limit, offset}}`.
- **Paginação:** `pagination.total` é cortado em 100. Nunca confiar nele. Avançar o `offset` de `limit` em `limit` até `data` vir vazio ou menor que `limit`.
- **Campos:** `id` (inteiro), `name`, `careerPageName` (nome da empresa), `city`, `state` (vazios quando a vaga é remota), `workplaceType`, `publishedDate` (ISO em UTC), `applicationDeadline`, `jobUrl`, `description`, `type`, `disabilities`, `badges`.
- **Valores de `type`:** `vacancy_type_effective`, `vacancy_legal_entity`, `vacancy_type_talent_pool`, `vacancy_type_internship`, `vacancy_type_temporary`, `vacancy_type_autonomous`. É tipo de contrato, não nível. O nível sai do título e do texto.
- **Não tem:** campo de salário. Só aparece se estiver escrito na descrição.
- **Descrição:** texto puro, sem as quebras de linha. Os títulos de seção vêm colados no corpo.
- **Cuidados:**
  - o endereço é interno do portal, sem contrato publicado. O coletor valida o formato e falha com mensagem clara;
  - o endereço antigo `portal.api.gupy.io/api/job` devolve 404. Não usar;
  - `jobUrl` vem com `?jobBoardSource=gupy_portal`. Esse parâmetro sai na limpeza de link;
  - um filtro combinado (`remote` + `state` + `sortOrder=desc`) devolveu vagas antigas no teste. Preferir filtrar localmente;
  - a página de carreira `https://<empresa>.gupy.io/` traz as vagas embutidas, mas sem descrição nem data. Não é usada na fase 1.
- **Limites:** nenhum publicado. Regra do coletor: 2 s entre pedidos e até 30 pedidos por execução. O que não couber fica para a execução seguinte (rodízio de escopos; desenho, seção 8.1).
- **Termos (candidatos, versão de 01/07/2026):** proíbem "agregar, copiar ou duplicar partes" do serviço. Não falam de coleta automática de forma explícita. Não pedem atribuição.
- **Decisão do dono (Q6, 2026-11-13):** a Gupy entra. Tem chave liga/desliga, ritmo educado (a regra de limites acima), sempre o link para a vaga original e aviso no README. O uso é pessoal, no computador de cada um, e nada é republicado.

---

## 3. Leva B

### 3.1 ATS brasileiros

#### InHire

- **Lista:** `GET https://api.inhire.app/job-posts/public/pages` com o cabeçalho `X-Tenant: {tenant}`. O tenant é o subdomínio de `{tenant}.inhire.app`.
- **Paginação:** nenhuma. Vem tudo de uma vez.
- **Detalhe:** `GET https://api.inhire.app/job-posts/public/pages/{jobId}`, com o mesmo cabeçalho. Só o detalhe traz a descrição (HTML), o `publishedAt` e o `contractType` (corrigido pela captura de 2026-11-13).
- **Forma da lista:** as vagas vêm em `jobsPage`, com `tenantName` na raiz da resposta (corrigido pela captura de 2026-11-13).
- **Campos da lista:** `jobId`, `displayName` (pode vir com espaços nas pontas), `location`, `workplaceType` (`On-site`, `Hybrid`, `Remote`), `status` e `careerPageId`. A lista não traz `contractType` (corrigido pela captura de 2026-11-13).
- **Link da vaga:** `https://{tenant}.inhire.app/vagas/{jobId}`. O link vem do código do site e responde 200 (conferido na rede em 2026-11-14), mas a vaga é montada no navegador e não foi vista aberta **[a confirmar]**.
- **Erros:** tenant inexistente devolve 404 com `{"message":"Tenant not found"}`.
- **Limites:** a documentação oficial fala em 20 pedidos por segundo, para a API autenticada. O coletor fica no intervalo padrão. As respostas não trazem cabeçalho de limite nem `ETag` (corrigido pela captura de 2026-11-13).
- **Vistos:** `riachuelo` (591 vagas), `carreiras` (3).

#### Quickin

- **Lista:** `GET https://api.quickin.io/public/{account_id}/jobs?sort=-created_at&page=N`
- **Resposta:** `{docs, total, limit, page, pages}`. 30 por página, fixo.
- **Achar o `account_id`:** ele tem 24 caracteres hexadecimais e sai do HTML de `https://jobs.quickin.io/{slug}/jobs`, no bloco `__NUXT_DATA__` (`pinia.careerSite.site.account_id`). Guardar em `parametros` da empresa (desenho, seção 8.6): não muda.
- **Campos:** `_id`, `title`, `company_id.name`, `city`, `region`, `country`, `workplace_type`, `remuneration`, `currency`, `remuneration_period`, `created_at`, `career_url`, `description`, `requirements`, `benefits` (HTML), `contract_id.name`.
- **A lista já traz a descrição inteira.** Não precisa de detalhe.
- **Vistos:** `connectforpeople` (85 vagas), `quickin` (2).

#### Recrutei

- **Lista:** `POST https://api.recrutei.com.br/api/v2/vacancies/per-departments/{label}`, corpo `{}`. Responde **HTTP 202** com JSON. Tratar 202 como sucesso.
- **Detalhe:** só em HTML, em `https://jobs.recrutei.com.br/{label}/vacancy/{id}-{slug}`. Os dados estão em `__NEXT_DATA__`, em `props.pageProps.retorno.vacancy`.
- **Campos da lista:** `id`, `title`, `company_name`, `location` (lista `[cidade, UF, país]` ou o texto "Não informado"), `remote`, `salary` (texto, como "A combinar"), `regime`.
- **Campos do detalhe:** `published_at` ("dd/mm/aaaa hh:mm:ss"), `expired_at`, `public_link`, `description` (HTML), `benefits`, `skills`.
- **Campo `remote`:** 0 quer dizer presencial (confirmado). Pela ordem do site, 1 seria remoto, 2 presencial ou remoto e 3 híbrido **[a confirmar]**.
- **Cuidados:** o endereço não é documentado. Existe uma chave da API antiga embutida no site: **não usar**.
- **Vistos:** `ucm-business-solutions` e `daguilar-consultoria-rh` (7 vagas cada).

#### Sólides

- **Lista:** `GET https://apigw.solides.com.br/jobs/v3/companies/{slug}/vacancies?page=N&take=25`
- **Resposta:** `{totalPages, currentPage, count, data}`. `take` máximo 25. `page` começa em 1. O slug é o subdomínio de `{slug}.vagas.solides.com.br`.
- **Campos:** `id`, `title`, `companyName`, `city.name`, `state.code`, `homeOffice`, `jobType`, `salary{initialRange, finalRange, negotiable, type}`, `createdAt`, `date.due`, `description` (HTML, já na lista), `seniority[].name`, `recruitmentContractType`.
- **Link da vaga:** montar `https://{slug}.vagas.solides.com.br/vaga/{id}`. O campo `redirectLink` vem quebrado: não usar.
- **Cuidado:** endereço não documentado.
- **Vistos:** `diefra` (18 vagas), `bamex` (1).

#### Abler

- **Só há caminho por HTML.**
- **Índice:** `https://candidatos.abler.com.br/sitemap.xml` — um arquivo de 3,6 MB, com 14.292 endereços e `<lastmod>`. O filtro pelos recentes vale só para URL nova (ver o contrato, abaixo).
- **Detalhe:** `https://candidatos.abler.com.br/vagas/{slug}-{n}`. Os dados estão em `window.__NUXT__`, em `state.candidate.vacancy.vacancy`.
- **Cuidado de leitura:** `window.__NUXT__` é uma expressão de função JavaScript, não JSON puro. Ler como texto, sem executar JavaScript.
- **Campos:** `id`, `title`, `companyName`, `cityAndState`, `address`, `workTypes[]`, `salary`, `salaryValue`, `publishedAt`, `closeOn`, `fullUrl`, `description`, `roleDescription`, `mandatoryRequirements`, `levelOfInterests[]`, `status`.
- **Não usar:** a API JSON `hulk-smash.abler.com.br` recusa origem de fora (403 `ORIGIN_NOT_ALLOWED`). É bloqueio: o joBot não contorna e nunca forja o cabeçalho `Origin`.
- **Custo:** um pedido por vaga. É a fonte mais cara e mais frágil da leva B. Fica por último.
- **Contrato (desenho, DR-70):** fonte de sitemap. O coletor devolve `UrlListada` de todas as URLs do sitemap, com o endereço e o `lastmod`. O filtro de 30 dias vale só para URL nova e é do executor: URL que já tem ocorrência dessa fonte conta como vista, com qualquer data. A vaga só é gravada depois do detalhe, com título e empresa, dentro do orçamento de enriquecimento (desenho, seções 8.1 e 10.6).
- **Status da vaga:** `status` vem "Em andamento" em todas as amostras, e o coletor trata a vaga como aberta sem filtrar por status (`abler.py`, `detalhar`). Só se conhece esse valor. Uma vaga encerrada com `lastmod` recente entraria como aberta; quando aparecer um segundo valor, o coletor passa a recusar status não vazio fora dos abertos conhecidos (D82).
- **Sitemap sem `<loc>`:** entrada sem `<loc>` deixa o escopo `parcial` com `saude.formato_mudou`; sitemap em que nenhuma `<url>` vira vaga é `falhou` só depois da T126: hoje o Abler dá `parcial` nesse caso (`abler.py:124` só testa as entradas puladas). O sitemap não traz `ETag` nem `Last-Modified`: sem pedido condicional (`abler.py:467`).
- **Busca real (2026-11-14, conferido na rede em 2026-11-14):** `ok`, 50 vagas em 51 pedidos, em 2 min. Para em 50 pelo orçamento de detalhes do executor (`MAX_DETALHES_POR_FONTE`, `agenda/execucao.py:54`); o resto entra nas rodadas seguintes (D74).
- **Termos (cláusula 6):** proíbem reproduzir o conteúdo sem autorização.
- **Decisão do dono (Q6, 2026-11-13):** a Abler entra. Tem chave liga/desliga, ritmo educado, sempre o link para a vaga original e aviso no README.

### 3.2 Portais de estágio e de primeiro emprego

#### CIEE

- **Endereço:** `GET https://api.ciee.org.br/vagas/vitrine-vaga/publicadas?page=0&size=1000&sort=codigoVaga,desc&tipoVaga=ESTAGIO` (e `tipoVaga=APRENDIZ`)
- **Resposta:** página no formato `content[]`, `totalElements`, `totalPages`, `last`. `page` começa em 0.
- **Volume:** 5.186 vagas (4.176 de estágio e 1.002 de aprendiz). Com `size=1000`, são 6 pedidos. Em 2026-11-14 vieram 3.962 vagas de estágio, em 4 pedidos (conferido na rede em 2026-11-14).
- **Campos:** `codigoVaga`, `nomeEmpresa`, `local.cidade`, `local.uf`, `local.bairro`, `bolsaAuxilio` com `tipoAuxilioBolsa` (`Mensal` ou `Hora`), `bolsaAuxilioDe`, `bolsaAuxilioAte`, `salario`, `salarioDe`, `salarioAte` (aprendiz), `atividades[]`, `descricao`, `beneficios[]`, `horarioEntrada`, `horarioSaida`, `requisitos.semestreInicio`, `requisitos.semestreFinal`, `nivelEscolar` (`SU`, `EM`, `TE`, `T`, `EF`), `tipoVaga`.
- **Empresa em sigilo:** `nomeEmpresa` pode vir só com espaço (" "): 134 de 3.962 vagas de estágio em 2026-11-14 (conferido na rede em 2026-11-14). A vaga não se descarta (D74, T116).
- **Não tem título:** montar com `areaProfissional` e `nivelEscolar`.
- **Não tem data:** registrar a data em que o joBot viu a vaga pela primeira vez.
- **Link da vaga:** `https://portal.ciee.org.br/quero-uma-vaga/?codigoVaga={codigoVaga}`
- **Descrição:** texto puro.
- **Tamanho da resposta:** cada página com `size=1000` tem cerca de 1,07 MB e cabe no teto de 5 MB (conferido na rede em 2026-11-14).

#### IEL

- **Endereço:** `GET https://carreiras.iel.org.br/{UF}` — página HTML com todas as vagas do estado embutidas.
- **Como ler:** as vagas estão nos blocos `self.__next_f.push`. Extrair os objetos que começam com `{"vagaOrigem"`. Cada vaga aparece duas vezes: tirar a repetição por `vagaIdentificador`.
- **Estados com vaga:** ES, MT, PE, SC, PR, DF, AL, MG, PA, MS, RN, PB, AM, RO, TO, SE, SP, AC, GO. São cerca de 19 pedidos. A maior página (PE) tem 1,3 MB e 289 vagas. Total: 2.028.
- **Campos:** `vagaIdentificador`, `vagaTitulo`, `vagaEmpresaNome` (quase sempre vazio: empresa em sigilo), `vagaCidade`, `vagaEstadoSigla`, `vagaModeloTrabalho`, `vagaSalario` (texto), `vagaInclusao` (ISO sem fuso), `vagaUrl`, `vagaObservacao`, `vagaRequisitos`, `vagaBeneficios`, `vagaHorarios`, `vagaCursos`, `vagaEscolaridadeDe`, `vagaEscolaridadeAte`, `vagaTipo`.
- **Plano B:** `https://carreiras.iel.org.br/sitemap.xml` mais a página de detalhe `/{UF}/vaga/{tipo}/{id}/{slug}`.
- **Página de UF sem vaga:** mostra o título "Nenhuma vaga encontrada!" (conferido na rede em 2026-11-14). UF que o portal não tem (por exemplo `/BA`) responde HTTP 500 (conferido na rede em 2026-11-14).
- **O sitemap guarda entradas velhas:** GO tinha 1 entrada de 2026-04 e a página dizia "Nenhuma vaga encontrada!"; SP tinha 5 no sitemap e 3 na página (conferido na rede em 2026-11-14). BA, CE, MA, PI, RJ, RS, AP e RR não aparecem no sitemap (conferido na rede em 2026-11-14): a lista fixa de 19 UFs vale (D74).
- **Cuidado:** não é contrato público. O formato embutido pode mudar a cada versão do site.

#### Super Estágios

- **Índice:** `GET https://www.superestagios.com.br/sitemap_vagas.php` — 2.668 endereços `/vaga/{id}` com `lastmod`. `cache-control: max-age=3600`.
- **Detalhe:** `GET https://www.superestagios.com.br/vaga/{id}` — HTML com JSON-LD do tipo `JobPosting`.
- **Campos do JSON-LD:** `identifier.value`, `title`, `hiringOrganization.name`, `jobLocation.address`, `baseSalary`, `datePosted`, `validThrough`, `url`, `description`.
- **Rótulos no HTML:** "Atividades a serem desenvolvidas:", "Requisito:", "Nível:", "Cursos:".
- **Sitemap real:** `<urlset>` sem namespace (o coletor aceita com e sem o namespace do protocolo). `lastmod` e `datePosted` vêm só com data (AAAA-MM-DD); sem fuso, valem meia-noite de Brasília (-03:00, como o `validThrough`), marcado com `shortcut:` no coletor para conferir (`super_estagios.py:40-43`). Não há `ETag` nem `Last-Modified` no sitemap, só `cache-control`: sem pedido condicional.
- **Padrão do endereço:** só entra URL `https://www.superestagios.com.br/vaga/<número>`; outro host, host local ou listagem é descartada e contada em `saude.sem_detalhe_n:<n>`, com estado `ok` (`super_estagios.py:92,271`). Entrada sem `<loc>` deixa o escopo `parcial` com `saude.formato_mudou`; sitemap com entradas e nenhuma legível é `falhou`. O `detalhar` devolve `None` para 404 e 410 (o executor guarda por 30 dias) e deixa 403, 429 e 5xx subirem (`super_estagios.py:284`).
- **Empresa em sigilo:** a página mostra `Empresa: CONFIDENCIAL`, na tabela e no JSON-LD, e esse é o valor que vira `empresa`. A T126 troca por `Super Estágios`, como o CIEE faz com `CIEE`, para vagas de empresas diferentes não se misturarem (D83).
- **Busca real (2026-11-14, conferido na rede em 2026-11-14):** `ok`, 50 vagas em 51 pedidos, em 1 min; para em 50 pelo orçamento de detalhes do executor (D74).
- **Custo:** um pedido por vaga. A primeira carga é fatiada: só as vagas com `lastmod` recente, dentro do orçamento de enriquecimento.
- **Contrato (desenho, DR-70):** fonte de sitemap. O coletor devolve `UrlListada` de todas as URLs do sitemap, com o endereço e o `lastmod`. O filtro de 30 dias vale só para URL nova e é do executor: URL que já tem ocorrência dessa fonte conta como vista, com qualquer data. A vaga só é gravada depois do detalhe, com título e empresa, dentro do orçamento de enriquecimento (desenho, seções 8.1 e 10.6).
- **[a confirmar]:** só uma página de detalhe foi vista. Conferir o formato em mais vagas.

#### Cia de Talentos

- **Endereço:** `POST https://vagas.ciadetalentos.com.br/applicant/rest/applicant/authentication/filter`, corpo `{"locale":"pt"}`. Não pede login, apesar do nome.
- **Resposta:** um pedido devolve tudo (27 programas).
- **Campos:** `opportunityId`, `opportunityName`, `companyName`, `opportunityLocations`, `countFinishDays`, `opportunityHotsiteUrl`, `opportunityInscriptionUrl`, `opportunityDescription` (HTML), `opportunityAreas`, `hiringType`, `hiringTypeId`.
- **Prazo:** data de hoje mais `countFinishDays`. Ignorar `daysRemainingForInscription`.
- **Tipo:** `hiringTypeId` 1 é trainee; 2 e 3 são estágio.
- **Forma da resposta:** é uma lista pura, sem envelope (corrigido pela captura de 2026-11-13).
- **Campos que podem vir nulos:** `opportunityDescription` e `hiringType` (corrigido pela captura de 2026-11-13).
- **Link:** `opportunityHotsiteUrl` aponta para hosts diferentes (`marketing.ciadetalentos.com`, `vagas.ciadetalentos.com.br/hotsite/...`, `www.ciadetalentos.com.br`) e pode ser igual ao link de inscrição (corrigido pela captura de 2026-11-13).
- **Tipo:** existe `hiringTypeId` 13 ("Ensino Médio", Banco de Talentos), fora do mapa 1/2/3 (corrigido pela captura de 2026-11-13).
- **Prazo:** `daysRemainingForInscription` veio "Encerra hoje" em todos, mesmo com `countFinishDays` até 107 (corrigido pela captura de 2026-11-13): confirma que só vale `countFinishDays`.
- **robots.txt:** o de `vagas.ciadetalentos.com.br` responde 404 e o de `www.ciadetalentos.com.br` diz `Allow: /` (corrigido pela captura de 2026-11-13).
- **Cuidado:** são programas, não vagas individuais. Endereço não documentado.

#### Mural da USP

Não existe um mural único. Duas unidades têm lista pública:

| Unidade | Endereço | Formato | Vistas |
|---|---|---|---|
| Instituto de Física | `https://portal.if.usp.br/carreiras/pt-br/oportunidades` | tabela HTML; detalhe em `/carreiras/pt-br/node/{id}` | 7 |
| FEA | `https://estagios.fea.usp.br/` | "Mural de Vagas" em HTML; detalhe em `/vagas/{id}` | 4 |

- A lista completa da FEA (`/vagas`) pede login da USP e devolve 403. O coletor usa só a página inicial.
- Volume baixo (11 no total). Leitura de HTML com seletores.
- No detalhe do IF o rótulo do campo da empresa é "Oportunidade:"; na lista é "Instituição:". O coletor usa o da lista (corrigido pela captura de 2026-11-13).
- Fora: IME (pede login) e Poli (postagens com PDF).

#### Eureca

- **Decisão do dono (Q6, 2026-11-13):** a Eureca entra. Tem chave liga/desliga, ritmo educado, sempre o link para a vaga original e aviso no README.
- **Termos (7.1 a 7.3):** pedem consentimento prévio e expresso. As notas da conferência de 2026-11-13 recomendam pedir autorização à Eureca antes de ligar o coletor, porque o endereço foi achado lendo o código do aplicativo de candidatos. A pergunta ao dono segue aberta na D80: (a) manter ligada, (b) deixar desligada por padrão até a autorização (recomendada), (c) tirar da fase 1.
- **Endereço:** `GET https://candidate-api.eureca.me/opportunities?page=N&pageSize=200`, JSON, sem login (decisão A42). O endereço sai do código do aplicativo `app.eureca.me`; nenhum login nem bloqueio é contornado (conferido na rede em 2026-11-14).
- **Resposta e paginação:** `{items, total, page, pageSize}`. `page` começa em 1; sem parâmetros a API devolve a página 1 com `pageSize` 200, e o pedido com `pageSize=200` explícito foi aceito na busca real. O coletor para quando a página vem menor que `pageSize` ou quando `page * pageSize >= total`. Teto local: `MAX_PAGINAS = 10` (2.000 vagas, hoje há 9); ao chegar nele o escopo fica `parcial` com `saude.limite_atingido` (`eureca.py:34,168`).
- **Cabeçalhos:** a API não manda `ETag` nem `Last-Modified`: sem pedido condicional. Ritmo da fonte: `espera_s` 2 s (`fontes.json`).
- **Campos da lista:** `id` (UUID), `name`, `companyName`, `description` (HTML), `cityName` e `stateAcronym`, `workModel` (`presencial`, `remoto` ou `hibrido`), `contractTypeKey` (`internship`), `salary`, `publishedAt`, `createdAt` e `endApplying`. A lista já traz a descrição: não há `detalhar`.
- **Salário:** `null` em parte das vagas e, nas outras, `{display, minCents, maxCents}`, com `display` igual a `range` ou `undisclosed` e valores em centavos (190000 a 220000, por exemplo). O coletor converte para BRL, sem período; com `undisclosed` o salário fica sem valor. A nota de 2026-11-13 dizia que `salary` "veio null": isso valia só para o detalhe de uma vaga.
- **Local:** na lista, `cityName` e `stateAcronym` vêm preenchidos em 5 das 8 vagas da captura (Salvador/BA, por exemplo); as notas diziam "nulos", e isso vale para o detalhe. `workplaceCities` só existe no detalhe e não é lido; `locations.cities` com mais de uma cidade segue lido só por `cityName` (D82).
- **Modalidade:** a lista traz `workModel` e também `workModels[]`; na vaga `019fdbd4` da captura, `workModel` é `presencial` e `workModels` é `['presencial','hibrido']`. A T126 deixa `modalidade_declarada` vazia quando `workModels` tem mais de um valor, e o rotulador lê o texto (D83).
- **Datas:** `publishedAt` veio `null` nas 8 vagas da lista; o coletor usa `createdAt` quando falta, no formato `2026-11-10 13:02:42.445557+00`, que o `fromisoformat` lê (`eureca.py:105`). `startApplying` só existe no detalhe. `endApplying` é um instante em UTC (`2027-01-01T02:59:00.000Z` é 23:59 de 31/12 em São Paulo): o prazo é o dia local (`eureca.py:59-61`), conforme a DP8.
- **Link da vaga:** `https://app.eureca.me/vagas/{id}`, da rota `/vagas/$jobId` do aplicativo; o id só entra se for UUID (`eureca.py:30,35,89`). Na busca real o link saiu no formato esperado (conferido na rede em 2026-11-14); falta abrir um no navegador.
- **Fora:** `/programs` lista programas (grupos de vagas), e cada vaga já traz `programName`.
- **Busca real (2026-11-14, conferido na rede em 2026-11-14):** `ok`, 9 vagas em 1 pedido (D74, D80).

### 3.3 ATS de empresa grande

Os testes deste grupo usaram user agent genérico. Repetir o primeiro pedido com o user agent do joBot.

#### Workday

- **Lista:** `POST https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
  - corpo: `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}`;
  - cabeçalhos: `Content-Type: application/json`, `Accept: application/json`, `Accept-Language`.
- **Detalhe:** `GET https://{tenant}.{wdN}.myworkdayjobs.com/wday/cxs/{tenant}/{site}{externalPath}`
- **Paginação:** `limit` máximo 20 (50 devolve 400). O `total` só vem na primeira página (`offset` 0): nas páginas com `offset` maior que 0 ele vem 0. Guardar o `total` do `offset` 0 e parar numa página curta (corrigido pela captura de 2026-11-13).
- **Filtro de Brasil:** os ids de faceta vêm na primeira resposta e mudam por empresa. O id de país do Brasil visto em duas empresas foi `1a29bb1357b240ab99a2fa755cc87c0e` (numa em `locationCountry`, na outra só em `locations`). Não fixar: ler da resposta. Há tenant cuja faceta só tem `locations`, sem país (corrigido pela captura de 2026-11-13).
- **Campos da lista:** `externalPath` (chave estável), `title`, `locationsText`, `bulletFields`, `postedOn` (texto relativo, como "Posted 3 Days Ago"; a captura confirma (corrigido pela captura de 2026-11-13)).
- **Campos do detalhe (`jobPostingInfo`):** `id`, `jobReqId`, `location`, `jobRequisitionLocation.country.alpha2Code`, `startDate`, `endDate`, `externalUrl`, `jobDescription` (HTML), `timeType`. Empresa em `hiringOrganization.name`.
- **Data:** usar `startDate` do detalhe. O `postedOn` da lista não serve como data.
- **Vistos:** `mastercard.wd1`, site `CorporateCareers` (855 vagas; 13 em São Paulo); `santander.wd3`, site `SantanderCareers` (1.051; 333 no Brasil).
- **Falhas vistas:** um tenant devolveu HTTP 521 e outro 422. Tenant e site entram na lista de empresas só depois de conferidos.
- **Em manutenção:** o `POST /jobs` responde 303 para `community.workday.com/maintenance-page`, que leva a `static.community.workday.com/maintenance-page.html` (200 `text/html`, "Workday is currently unavailable.") (conferido na rede em 2026-11-14). A queda é por data center (`wd1` em 2026-11-14; `wd5` deu 521 em 2026-11-13). Tratar como fora do ar, não como formato mudado.
- **Limites:** nenhum documentado.

#### Eightfold

Cada empresa está numa de duas gerações da API.

- **Geração PCSX:**
  - lista: `GET https://{host}/api/pcsx/search?domain={domínio}&query=&location=Brazil&start=0&sort_by=timestamp` — 10 por página, fixo; total em `data.count`;
  - detalhe: `GET https://{host}/api/pcsx/position_details?position_id={id}&domain={domínio}&hl=pt-BR`;
  - campos: `positions[].id`, `name`, `locations[]`, `standardizedLocations[]` (Brasil começa com "BR"), `workLocationOption` (`onsite`, `hybrid`, `remote_local`), `postedTs` (epoch em segundos), `department`, `displayJobId`; no detalhe, `publicUrl` e `jobDescription` (HTML);
  - a lista e o detalhe PCSX vêm dentro de `data` (`data.positions`, `data.count`, `data.jobDescription`) (corrigido pela captura de 2026-11-13). A lista não traz descrição: o `detalhar` busca o HTML. O coletor não usa o `publicUrl`: monta `https://{host}/careers/job/{id}` (corrigido pela captura de 2026-11-13).
- **Geração v2:**
  - lista: `GET https://{host}/api/apply/v2/jobs?domain={domínio}&start=0&num=10&location=Brazil&sort_by=timestamp`;
  - detalhe: `GET https://{host}/api/apply/v2/jobs/{id}?domain={domínio}`;
  - campos: `id`, `name`, `business_unit`, `location`, `locations`, `work_location_option`, `t_create`, `canonicalPositionUrl`, `job_description`;
  - a lista v2 vem sem `data`, com `positions` e `count` na raiz, e já traz `job_description` como texto achatado: a vaga entra com descrição em texto e o detalhe v2 só roda se alguém o chamar por fora (corrigido pela captura de 2026-11-13).
- **Como saber a geração:** PCSX devolve 403 com "PCSX is not enabled for this user." → usar v2. A v2 devolve 403 com "Not authorized for PCSX" → usar PCSX. Guardar a geração em `parametros` da empresa (desenho, seção 8.6). Ao cadastrar, o `resolver` tenta a PCSX e depois a v2, e acha o `domain` no endereço, na lista de domínios conhecidos ou no `Sitemap` do `robots.txt` (corrigido pela captura de 2026-11-13).
- **Países e paginação:** a API filtra pelo nome do país em inglês (`location=Brazil`); o coletor traduz o código do país da busca e ignora o código que não conhece. Sem país nenhum na busca, usa o Brasil. A página seguinte começa depois do que veio (`start` soma os itens recebidos); para numa página com menos de 10 ou quando `start` chega ao total; trava em 100 páginas por país (corrigido pela captura de 2026-11-13).
- **Vistos:**

| Empresa | Host | Domínio | Geração | Vagas no Brasil |
|---|---|---|---|---|
| Mercado Livre | `mercadolibre.eightfold.ai` | `mercadolibre.com` | PCSX | 396 |
| NVIDIA | `jobs.nvidia.com` | `nvidia.com` | PCSX | 1 (de 2.691) |
| Microsoft | `apply.careers.microsoft.com` | `microsoft.com` | PCSX | 24 |
| Bayer | `bayer.eightfold.ai` | `bayer.com` | v2 | 15 |

- **Microsoft:** devolveu 429, sem `Retry-After`, duas vezes, com o filtro `work_site`. Não usar esse filtro. Pelo menos 5 s entre pedidos. Uma vez por dia. Um 429 encerra só o escopo da Microsoft até o dia seguinte; as outras empresas do Eightfold continuam. Esses valores ficam no escopo da Microsoft, não na fonte (`por_escopo` no `fontes.json`: `intervalo_min` 1440, `espera_s` 5, `para_no_429`; desenho, seção 8.1).
- **Microsoft, 2026-11-14:** deu 429 logo depois de 41 pedidos a 1 s em `bayer` e `mercadolibre`; meia hora depois, dois pedidos com 30 s entre eles deram 200. O 429 vem com `x-ef-ns` "unknown" (recusado antes da API) e o `Retry-After` não foi visto (conferido na rede em 2026-11-14). O mais provável é limite por IP na borda do Eightfold (D74, T117).

#### Oracle HCM

- **Lista:** `GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList.secondaryLocations&finder=findReqs;siteNumber={siteNumber},facetsList=LOCATIONS%3BWORKPLACE_TYPES%3BPOSTING_DATES,limit=25,offset=0,sortBy=POSTING_DATES_DESC,selectedLocationsFacet={GeographyId}`
- **Detalhe:** `GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails?expand=all&onlyData=true&finder=ById;Id=%22{Id}%22,siteNumber={siteNumber}`
- **Paginação:** `limit` e `offset` ficam **dentro** do `finder`. `limit=200` foi aceito. Total em `items[0].TotalJobsCount`.
- **`siteNumber`:** sai do HTML da página de carreira, no atributo `data-sitenumber`.
- **Filtro de Brasil:** o `GeographyId` do Brasil muda por empresa (300000000106728 numa, 300000000289141 na outra). O coletor o lê de `items[0].locationsFacet`, e a lista é filtrada só pela faceta, sem `keyword`. Correção pela busca real de 2026-11-14 (conferido na rede em 2026-11-14): a descoberta sem filtro traz só as maiores localidades (18 facetas na Oracle, 40 no JPMorgan) e o Brasil não aparece, então o coletor deu `ok` com 0 vagas. Com `keyword=Brazil` a faceta do Brasil vem (o id achado na conferência de 2026-11-13 já foi com `keyword="Brazil"` e `facetsList=LOCATIONS`), e a lista filtrada só pela faceta traz 8 vagas na Oracle e 20 no JPMorgan. A T126 (entregue em 2026-11-14) repete a descoberta uma vez com `keyword=<nome do país em inglês>` quando a faceta não vem (`oracle_hcm.py:237-239`); a palavra vai entre aspas, como o site manda (`oracle_hcm.py:207-208`). Só sem a faceta nas duas descobertas o escopo termina `ok` vazio (D74). Conferido ao vivo em 2026-11-14 depois da entrega: 8 vagas na Oracle e 20 no JPMorgan, e a API aceitou a keyword com aspas. A faceta com hierarquia ("SAO PAULO, SP, Brazil") só vale como país quando o nome não tem vírgula e `ler_locais` dá o país do escopo.
- **Vaga com o Brasil só como local secundário:** o filtro pelo Brasil traz também vaga cujo `PrimaryLocation` é de outro país (a Oracle trouxe uma do México). O coletor guarda `PrimaryLocation` e `secondaryLocations` em `locais` e deixa o tratamento decidir (`oracle_hcm.py:128`).
- **Nome da empresa:** nem a lista nem o detalhe o trazem. O coletor usa o nome do cadastro, guardado por `escopos`, e cai no primeiro rótulo do host (`eeho`) sem cadastro (`oracle_hcm.py:173,196`), o mesmo atalho do Workday (D50).
- **Prazo:** `PostingEndDate` e `ExternalPostedEndDate` vieram `null` em todas as amostras. O coletor lê o prazo quando vem (`oracle_hcm.py:151,309`), mas nunca o viu preenchido.
- **Endereço aceito:** `siteNumber` casa `[A-Za-z0-9_]{1,50}` e o host só vale em `*.oraclecloud.com` (`oracle_hcm.py:37,38`); domínio próprio da empresa fica de fora. O resolver aceita `https://<host>/hcmUI/CandidateExperience/<idioma>/sites/<site>[/...]`.
- **Campos:** `Id`, `Title`, `PrimaryLocation`, `PrimaryLocationCountry`, `secondaryLocations`, `PostedDate`, `PostingEndDate`, `ShortDescriptionStr`; no detalhe, `ExternalDescriptionStr`, `ExternalResponsibilitiesStr`, `ExternalQualificationsStr` (HTML).
- **Link da vaga:** `https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{Id}`
- **Vistos:** `eeho.fa.us2.oraclecloud.com` (`CX_45001`, site `jobsearch`; 2.835 vagas, 8 no Brasil); `jpmc.fa.oraclecloud.com` (`CX_1001`; 14 no Brasil; 20 na busca real de 2026-11-14).
- **Observação:** API documentada oficialmente. Nenhuma empresa brasileira foi achada neste ATS.

### 3.4 Sites de carreira

#### Google

- **Endereço:** `GET https://www.google.com/about/careers/applications/jobs/feed.xml`
- **Um pedido devolve tudo:** 3.271 vagas. **19,8 MB sem compressão, 3,9 MB com gzip.** Passa do teto padrão de 5 MB: o coletor declara teto próprio de 32 MB e lê o XML em fluxo (`xml.etree.ElementTree.iterparse`).
- **Filtro local:** `locations/location/country == 'Brazil'` (49 vagas).
- **Campos:** `job/jobid`, `title`, `employer`, `locations/location/{city, state, country}`, `remote`, `isRemote`, `isHybrid`, `published` (ISO em UTC), `url`, `description` (HTML escapado), `jobtype`, `categories`, `languageCode`.
- **Limites:** nenhum limite publicado. A resposta traz `Cache-Control: max-age=1500` e `Last-Modified`. Usar `If-Modified-Since`, para só baixar o feed de novo quando ele muda. **[a confirmar]:** se o feed responde 304.
- **Valores vistos (captura de 2026-11-13):** `remote` vale `onsite` (ou `remote`), e `isRemote` e `isHybrid` valem `Yes` ou `No` (`google.py:54-58`). O `url` vem em `careers.google.com` e redireciona com 301. `state` às vezes vem vazio ou como `State of Minas Gerais`.
- **Busca real (2026-11-14, conferido na rede em 2026-11-14):** `ok`, 49 vagas em 1 pedido, em 2 s. O 304 ainda não foi visto: uma só rodada.
- **Risco aceito:** se o feed trocar `Brazil` por `BR` ou `Brasil`, a coleta dá `ok` vazio, e o vigia pega a fonte que zerou (D82).
- **`intervalo_min` da fonte:** 1440, porque o feed é grande e muda uma vez por dia. É intervalo prático, decisão da sessão em 2026-11-13; os termos não pedem.

#### Amazon

- **Endereço:** `GET https://www.amazon.jobs/en/search.json?normalized_country_code[]=BRA&result_limit=100&offset=N&sort=recent`
- **Paginação:** `result_limit` máximo 100. Total em `hits`. 406 vagas no Brasil = 5 pedidos.
- **Campos:** `id_icims`, `id`, `title`, `company_name`, `normalized_location`, `locations[]`, `posted_date`, `job_path`, `description`, `basic_qualifications`, `preferred_qualifications` (HTML simples), `job_category`, `job_schedule_type`.
- **Cuidados:**
  - cada item de `locations[]` é um texto JSON: passar por `json.loads`. O `type` diz `ONSITE` ou `VIRTUAL`;
  - `posted_date` vem em inglês por extenso ("November 13, 2026");
  - link da vaga: `https://www.amazon.jobs` + `job_path`.
- **Correções pela entrega e pela busca real:** o `id_icims` é o número que está no `job_path`, e o coletor o usa como `id_externo` (o `id` em UUID fica sem uso). O `job_path` tem de casar `/(?!/)[\w.~%/-]+`: uma barra só, sem `?`, `#` nem host; vaga fora disso é pulada e o escopo fica `parcial` com `saude.formato_mudou` (`amazon.py:40,107`). `locations[].type` só foi visto como `ONSITE` (5 vagas); `VIRTUAL` só existe nos testes, montado à mão. A API não traz salário estruturado, e `url_next_step` (`account.amazon.jobs`) não é usado: `url_candidatura` fica vazia. `posted_date` não traz hora: o coletor a lê hoje como meia-noite UTC, e a T126 muda para meia-noite de Brasília (D83).
- **Escopo e teto:** o escopo é o código ISO de 2 letras (`BR`), convertido para `BRA` por uma tabela de 18 países (`amazon.py:35`); sem países nas buscas, `BR`. Teto de 30 páginas (`MAX_PAGINAS = 30`, `amazon.py:32`, 3.000 vagas por país), acima disso `parcial` com `saude.limite_atingido`.
- **Busca real (2026-11-14, conferido na rede em 2026-11-14):** `ok`, 407 vagas em 5 pedidos, todas com descrição (a conferência de 2026-11-13 viu 406).
- **Limites:** nenhum publicado; endereço não oficial. Regra do coletor: 2 s entre pedidos (5 pedidos cobrem o Brasil).
- **`intervalo_min` da fonte:** 360. É intervalo prático, decisão da sessão em 2026-11-13; os termos não pedem.

#### Microsoft e NVIDIA

Usam Eightfold, geração PCSX. Ver a seção 3.3.

#### Meta — fora

Fora por decisão do dono (Q6, 2026-11-13). Ver a seção 4.

---

## 4. Fontes que ficam fora e por quê

| Fonte | Motivo | Estado |
|---|---|---|
| Meta (site de carreira) | Os termos de coleta automática proíbem a coleta sem permissão expressa por escrito. O caminho técnico existe, mas não é usado. | fora, por decisão do dono (Q6, 2026-11-13) |
| Abler, API JSON | Recusa origem de fora (403). É bloqueio; não se contorna. A Abler segue pelo caminho de HTML. | fora, definitivo |
| Hacker News, páginas do site | Os termos proíbem raspar o site. A leitura usa só a API de busca. | fora, definitivo |
| Gupy, API antiga (`portal.api.gupy.io`) | Devolve 404. | fora, definitivo |
| Gupy, página de carreira por empresa | Sem descrição e sem data. A API do portal cobre melhor. | fora na fase 1 |
| USP: IME e Poli | IME pede login. Poli publica em PDF dentro de postagem. | fora, definitivo |
| Common Crawl, API de consulta (CDX) | Limite pesado, instável e resposta cortada. O índice bruto cobre (seção 5). | fora, definitivo |
| Workday de empresa cujo tenant falhou | Um tenant devolveu 521 e outro 422. Só entra tenant conferido. | fora até conferir |

As fontes com caminho público que não aparecem nesta tabela entram na fase 1.

Eureca, Abler e Gupy têm termos restritivos e entram mesmo assim, por decisão do dono (Q6, 2026-11-13): cada uma com chave liga/desliga, ritmo educado, link para a vaga original e aviso no README. A Eureca tem endereço público confirmado na busca real de 2026-11-14 (seção 3.2); a pergunta da autorização segue na D80.

---

## 5. Descoberta de empresas — Common Crawl

- **Lista de índices:** `GET https://index.commoncrawl.org/collinfo.json`. Sai um índice novo mais ou menos por mês. O joBot olha essa lista uma vez por semana e só roda a descoberta quando aparece um id novo.
- **Índice visto:** `CC-MAIN-2026-43`.
- **Caminho usado (índice bruto):**
  1. baixar `https://data.commoncrawl.org/cc-index/collections/{id}/indexes/cluster.idx` — texto, **104,5 MB**, uma linha a cada 3.000 registros, no formato `<chave SURT> <data>\t<arquivo cdx>\t<offset>\t<tamanho>\t<n>`;
  2. achar as linhas cujo prefixo cobre os hosts de interesse;
  3. buscar só esses blocos com pedido de faixa (`Range: bytes=<offset>-<offset+tamanho-1>`) em `https://data.commoncrawl.org/cc-index/collections/{id}/indexes/cdx-NNNNN.gz`. Cada bloco é um gzip independente, de 250 a 330 KB, com linhas `<surt> <data> <json>`.
- **Prefixos:** `io,greenhouse,boards)/`, `io,greenhouse,job-boards)/`, `co,lever,jobs)/`, `com,ashbyhq,jobs)/`, `io,gupy,`.
- **Volume:** cerca de 35 blocos, perto de 8,6 MB, além do `cluster.idx`.
- **Teto de resposta:** o `cluster.idx` passa do teto de 5 MB. A descoberta declara teto próprio de 128 MB só para esse arquivo, lê em fluxo e não guarda o arquivo.
- **Ritmo:** 10 s entre pedidos, uma nova tentativa no máximo, conferir o tamanho recebido. Resposta 503 quer dizer "devagar": parar e tentar no dia seguinte.
- **Rendimento (índice de outubro de 2026):** 725 subdomínios da Gupy, 1.080 nomes do Ashby, 1.759 do Greenhouse (parcial) e 267 da Lever.
- **Termos:** não pedem atribuição.
- **Depois da descoberta:** cada identificador achado é testado no ATS. Só vira sugestão a empresa que tem vaga no Brasil ou remota. A sugestão espera a aprovação do dono no painel.

---

## 6. Câmbio — PTAX do Banco Central

Conferido ao vivo em 2026-11-13. Sem chave e sem login.

- **Base:** `https://olinda.bcb.gov.br/olinda/servico/PTAX/versao/v1/odata/`
- **Moedas:** `GET Moedas?$format=json` devolve `value[]` com `simbolo`, `nomeFormatado` e `tipoMoeda`. Dez moedas: AUD, CAD, CHF, DKK, EUR, GBP, JPY, NOK, SEK, USD.
- **Cotação de um período (o joBot usa este):**

  `GET CotacaoMoedaPeriodo(moeda=@moeda,dataInicial=@dataInicial,dataFinalCotacao=@dataFinalCotacao)?@moeda='USD'&@dataInicial='11-06-2026'&@dataFinalCotacao='11-13-2026'&$format=json&$filter=tipoBoletim eq 'Fechamento'`

  - datas no formato **MM-DD-AAAA**, entre aspas simples;
  - devolve uma linha por dia útil, só o boletim de fechamento.
- **Cotação de um dia:** `GET CotacaoMoedaDia(moeda=@moeda,dataCotacao=@dataCotacao)?@moeda='USD'&@dataCotacao='11-12-2026'&$format=json`
  - devolve todos os boletins do dia (abertura, intermediários e fechamento);
  - neste recurso o fechamento vem como `tipoBoletim` **"Fechamento PTAX"**; no recurso de período vem como **"Fechamento"**.
- **Campos de cada linha:** `cotacaoCompra`, `cotacaoVenda` (reais por unidade da moeda), `paridadeCompra`, `paridadeVenda`, `dataHoraCotacao` ("AAAA-MM-DD hh:mm:ss.ffffff", hora de Brasília), `tipoBoletim`.
- **Fim de semana e feriado:** a resposta vem com HTTP 200 e `value` vazio. Por isso o joBot pede um período de 7 dias e usa a última linha.
- **Horário:** o fechamento do dia sai perto das 13h de Brasília. Antes disso, vale o do dia útil anterior.
- **Cabeçalhos:** a resposta não trouxe `ETag`, `Last-Modified` nem `Cache-Control`. O cache é do joBot (desenho, seção 10.3).
- **Limites:** nenhum publicado. O joBot faz um pedido por moeda por dia, só das moedas que aparecem em vaga.
- **Moeda fora da lista:** não tem cotação. A vaga mostra só o valor original e não é eliminada pelo filtro de salário.
- **Falta conferir:** o teste usou user agent genérico. Repetir com o user agent do joBot.

---

## 7. Lista inicial de empresas

Conferida ao vivo em 2026-11-13: cada empresa respondeu com pelo menos uma vaga no Brasil ou remota. São 67 empresas. Elas entram ligadas na primeira execução. O dono revê e remove pelo painel quando quiser.

Como ler a coluna "Vagas vistas":

- Greenhouse, Lever, Ashby e Gupy: total do quadro da empresa;
- SmartRecruiters: só as vagas no Brasil (filtro `country=br`).

A coluna "Brasil ou remoto" é a contagem feita na conferência. Ela usa o campo de local e pode estar um pouco inflada onde "remoto" não cita o país.

Conferência ao vivo de 2026-11-14 (`scripts/conferir_empresas.py`, `dev` `fa22d1e`): as 83 empresas do `empresas.json`, o primeiro escopo de cada uma, filtro `BR`, termo `developer`, até 5 pedidos por empresa. 81 de 83 respondem: 76 `ok` e 5 `no_limite` pelo teto de pedidos do próprio script (`saude.orcamento`), que conta como resposta (`scripts/conferir_empresas.py:31,43-45`). Os 2 que não respondem são a Mastercard (manutenção do Workday) e a Microsoft (`no_limite` por `saude.parou_429`, que não conta). Beep Saúde e CNA Idiomas (Gupy) responderam `ok` com 0 vagas. Localiza&Co, Sicredi, Hapvida (Gupy), Santander (Workday) e Mercado Livre (Eightfold) pararam no teto de pedidos do script (`no_limite`, `saude.orcamento`), então a contagem de vagas deles é um mínimo. A Mastercard (Workday) falhou com `saude.erro_de_rede` (manutenção, HTTP 303) e a Microsoft (Eightfold) parou em 429. A divisão por fonte e as decisões estão na D74.

### 7.1 Greenhouse (15)

| Empresa | Área | Identificador | Vagas vistas | Brasil ou remoto |
|---|---|---|---:|---|
| C6 Bank | banco/finanças | `c6bank` | 157 | sim: 156 de 157 com local no Brasil |
| XP Inc. | banco/finanças (investimentos) | `xpinc` | 116 | sim: 95 de 116 no Brasil ou remotas |
| Banco PAN | banco/finanças | `bancopan` | 15 | sim: 12 de 15 |
| Agibank (quadro de vagas futuras) | banco/finanças | `agibankvagasfuturas` | 37 | sim: 37 de 37 (é banco de talentos/vagas futuras, não vaga imediata) |
| EBANX | finanças/pagamentos | `ebanx` | 34 | sim: 23 de 34 |
| iFood | varejo/delivery e logística | `ifoodcarreiras` | 75 | sim: 72 de 75 |
| VTEX | varejo (comércio eletrônico) | `vtex` | 32 | sim: 17 de 32 |
| BEES (AB InBev) | indústria (bebidas) / B2B varejo | `bees` | 52 | sim: 52 de 52 (Campinas e São Paulo) |
| Wellhub (Gympass) | saúde/bem-estar | `gympass` | 83 | sim: 38 de 83 no Brasil (filtro estrito) |
| Vitta | saúde | `vitta` | 3 | sim: 3 de 3 (São Paulo) |
| Arco Educação | educação | `arcoeducacao` | 43 | sim: 39 de 43 |
| QuintoAndar | tecnologia/imobiliário | `quintoandar` | 102 | sim: 80 de 102 |
| Wildlife Studios | tecnologia (jogos) | `wildlifestudios` | 14 | sim: 14 de 14 (São Paulo) |
| Jusbrasil | tecnologia (jurídico) | `jusbrasil` | 20 | sim: 19 de 20 |
| Kunumi | tecnologia (IA) | `kunumi` | 7 | sim: 7 de 7 (Brasil / remoto Brasil) |

### 7.2 Lever (8)

| Empresa | Área | Identificador | Vagas vistas | Brasil ou remoto |
|---|---|---|---:|---|
| Banco BV | banco/finanças | `bv` | 12 | sim: 12 de 12 |
| Stark Bank | banco/finanças | `starkbank` | 4 | sim: 4 de 4 (São Paulo, presencial) |
| Flash | finanças/benefícios (RH) | `flashapp` | 19 | sim: 19 de 19 |
| Jeeves | finanças (fintech internacional) | `tryjeeves` | 77 | sim: 24 de 77 com país BR/São Paulo (filtro estrito) |
| Zippi | finanças (crédito) | `zippi` | 4 | sim: 4 de 4 (São Paulo, remoto) |
| CI&T | tecnologia (serviços) | `ciandt` | 108 | sim: 102 de 108 |
| Minders | tecnologia (consultoria) | `minders` | 21 | sim: 7 de 21 (São Paulo, híbrido) |
| Handoff | construção (tecnologia para obras) | `handoff` | 10 | sim: 3 de 10 (São Paulo, híbrido) |

### 7.3 Ashby (5)

| Empresa | Área | Identificador | Vagas vistas | Brasil ou remoto |
|---|---|---|---:|---|
| OpenAI | tecnologia (IA) | `openai` | 836 | sim, 9 das 836 vagas são em São Paulo |
| Airwallex | banco/finanças (pagamentos internacionais) | `airwallex` | 484 | sim, 3 das 484 vagas são em São Paulo |
| Belvo | banco/finanças (open finance LATAM) | `belvo` | 3 | sim, 2 das 3 citam São Paulo/remoto, mas uma delas é banco de currículos (CV for Future Opportunities); vaga real no Brasil = 1 |
| Supabase | tecnologia (banco de dados/dev tools) | `supabase` | 77 | remoto global: 26 das 77 vagas têm isRemote=true e local 'Remote, Global'; nenhuma cita o Brasil |
| Zapier | tecnologia (automação SaaS) | `zapier` | 10 | 1 das 10 vagas é remota e inclui South America/Latin America; o Brasil não é citado |

### 7.4 SmartRecruiters (11)

| Empresa | Área | Identificador | Vagas vistas | Brasil ou remoto |
|---|---|---|---:|---|
| Bosch Group | indústria (autopeças, ferramentas, eletrônica) | `BoschGroup` | 107 | sim, 107 vagas no Brasil (filtro country=br), por exemplo em Joinville e Campinas |
| Experian (Serasa Experian) | banco/finanças (crédito, bureau) | `Experian` | 178 | sim, 178 vagas no Brasil (country=br), em São Paulo |
| Syngenta Group | agro (sementes e defensivos) | `SyngentaGroup` | 42 | sim, 42 vagas no Brasil (country=br), por exemplo em Cuiabá e Dois Vizinhos; inclui anúncio de franquia |
| Eurofins | saúde/laboratórios (análises clínicas, farma, alimentos) | `Eurofins` | 69 | sim, 69 vagas no Brasil (country=br), por exemplo em Belo Horizonte |
| Wabtec | indústria/logística ferroviária | `Wabtec` | 41 | sim, 41 vagas no Brasil (country=br), em Monte Alto e Paulínia |
| NielsenIQ | varejo/dados de consumo | `NielsenIQ` | 6 | sim, 6 vagas no Brasil (country=br), em Barueri |
| Avery Dennison | indústria (etiquetas e materiais) | `AveryDennison` | 4 | sim, 4 vagas no Brasil (country=br), em Blumenau e Vinhedo |
| ServiceNow | tecnologia (software corporativo) | `ServiceNow` | 4 | sim, 4 vagas no Brasil (country=br), em São Paulo e Brasília |
| Netbr | tecnologia (segurança e identidade, empresa brasileira) | `Netbr1` | 5 | sim, 5 vagas no Brasil (country=br), em São Paulo/Pinheiros, marcadas como remote=true |
| Ubisoft | tecnologia (games) | `Ubisoft2` | 1 | sim, 1 vaga no Brasil (country=br), em São Paulo |
| Endava | tecnologia (consultoria de software) | `Endava` | 1 | sim, 1 vaga no Brasil (country=br), em São Paulo |

### 7.5 Gupy (28)

| Empresa | Área | Identificador | Vagas vistas | Brasil ou remoto |
|---|---|---|---:|---|
| Localiza&Co | mobilidade/locação de veículos | `localiza` | 894 | sim (todas no Brasil) |
| Grupo TecnoSpeed | tecnologia | `grupotecnospeed` | 5 | sim (5 no Brasil, 4 remotas) |
| Agriness | tecnologia (agrotech) | `agriness` | 4 | sim (4 no Brasil, 4 remotas) |
| Certsys | tecnologia | `certsys` | 3 | sim (3 no Brasil, 3 remotas) |
| Montreal \| Tecnologia e Inovação | tecnologia | `montreal` | 60 | sim (60 no Brasil, 13 remotas) |
| Quality Digital | tecnologia | `qualitydigital` | 42 | sim (41 no Brasil, 14 remotas) |
| Porto (Porto Seguro) | seguros/finanças | `porto` | 144 | sim (144 no Brasil) |
| Sicredi | banco/finanças (cooperativa de crédito) | `sicredi` | 911 | sim (901 no Brasil, 11 remotas) |
| Carajás Home Center | varejo | `carajas` | 64 | sim (64 no Brasil) |
| Fortbras | varejo (autopeças) | `fortbras` | 332 | sim (332 no Brasil) |
| CLAMED Farmacêuticos | varejo (farmácias) | `clamedfarma` | 80 | sim (80 no Brasil) |
| Ambev | indústria (bebidas) | `ambev` | 318 | sim (316 no Brasil, 5 remotas) |
| WEG | indústria (eletromecânica) | `weg` | 88 | sim (85 no Brasil) |
| Suzano | indústria (papel e celulose) | `suzano` | 70 | sim (70 no Brasil) |
| CBC - Companhia Brasileira de Cartuchos | indústria | `vempracbc` | 31 | sim (31 no Brasil) |
| Aché Laboratórios Farmacêuticos | indústria farmacêutica | `vagasache` | 52 | sim (52 no Brasil) |
| Beep Saúde | saúde | `beepsaude` | 75 | sim (75 no Brasil) |
| Hapvida | saúde | `hapvidandi` | 732 | sim (732 no Brasil, 1 remota) |
| SPDM/PAIS Fortaleza | saúde | `spdmpaisfor` | 36 | sim (36 no Brasil) |
| TPC Logística Inteligente | logística | `tpc` | 69 | sim (69 no Brasil) |
| GrupoSC Distribuidora de Medicamentos | logística/distribuição | `gruposc` | 142 | sim (142 no Brasil) |
| Grupo Positivo | educação/tecnologia | `positivo` | 92 | sim (92 no Brasil) |
| Rede Batista de Educação | educação | `redebatistadeeducacao` | 49 | sim (49 no Brasil) |
| Afya (Carreira Médica) | educação/saúde | `afyamedicina` | 20 | sim (20 no Brasil, 12 remotas) |
| CNA Idiomas | educação | `cnaidiomas` | 59 | sim (59 no Brasil, 1 remota) |
| Cocamar Cooperativa Agroindustrial | agro | `cocamar` | 40 | sim (40 no Brasil) |
| IHARA | agro (defensivos) | `ihara` | 16 | sim (16 no Brasil) |
| Ourofino Agrociência | agro | `ourofinoagro` | 7 | sim (7 no Brasil, 1 remota) |

Observações:

- O `careerPageName` da API é o `publicationName` da página da empresa, com caixa exata (decisão 29, seção 2.5). Em nove empresas ele difere do identificador e está em `parametros.careerPageName`. Na Hapvida o nome é genérico ("Página de Carreira"), e o escopo baixa vagas de mais de uma empresa até o filtro de host do `jobUrl` as descartar (D50).
- O quadro `agibankvagasfuturas` é banco de talentos ("vagas futuras"), não vaga imediata. O painel mostra a etiqueta de banco de talentos.
- Agriness, Certsys e Grupo TecnoSpeed têm de 3 a 5 vagas. Podem zerar em poucos dias; zero nelas não é falha.
- Nas vagas remotas globais (Supabase, Zapier), a conferência não leu a descrição para saber se aceitam contratação a partir do Brasil.
- Na Gupy, algumas vagas vêm sem país ou com "BRASIL" em maiúsculas. O normalizador de local trata os dois casos.
- Áreas fracas na lista: logística pura e saúde fora da Gupy. Agro vem só pela Gupy e pela SmartRecruiters.

### 7.6 Empresas testadas e descartadas

Ficam fora da lista inicial. O motivo evita que alguém teste de novo sem necessidade.

| Testado | Motivo |
|---|---|
| Nubank (greenhouse: nubank e 3141592653589793238462643383279nubank) | Os dois identificadores responderam 200 com 0 vagas hoje. O quadro com nome longo aparece nos links indexados, mas a API devolveu a lista vazia. |
| Sound Agriculture (greenhouse: soundagriculture) | Respondeu 200 com 0 vagas. A busca na web mostrava vagas de agro no Mato Grosso, que já estão fechadas. |
| Arva Intelligence (greenhouse: arvaintelligence) | Tem 3 vagas, todas em Houston, Texas, nenhuma no Brasil ou remota aceitando Brasil. |
| Zenvia (greenhouse: zenvia) | A API devolveu 404, embora haja links job-boards.greenhouse.io/zenvia indexados (o identificador provavelmente mudou ou o quadro saiu). |
| bhub (greenhouse: bhub) | A API devolveu 404. |
| Creditas (greenhouse: creditas; lever: creditas) | 404 nos dois ATS, embora a busca mostre links job-boards.greenhouse.io/creditas. |
| Loft, Olist, Cora, Alice, Pismo, Dock, Solfácil (greenhouse) | Identificadores chutados pelo nome da empresa; a API devolveu 404 para todos. |
| dLocal (lever: dlocal) | Respondeu 200 com 0 vagas. |
| Relay Commerce (lever: relay-commerce) | Respondeu 200 com 0 vagas. |
| CloudWalk (lever: cloudwalk) | A API devolveu 404, embora haja links jobs.lever.co/cloudwalk indexados (pode ter migrado de ATS ou usar o host da UE). |
| Kovi, Lavoro (lever) | Identificadores chutados; a API devolveu 404. |
| Visa (SmartRecruiters: Visa) | 0 vagas no Brasil com country=br |
| PUMA (PUMA) | 0 vagas no Brasil; identificador pode estar errado (o SR responde 200 com 0 para id inexistente) |
| IKEA (IKEA) | 0 vagas no Brasil |
| Sodexo (Sodexo) | 0 vagas no Brasil; identificador incerto |
| Publicis Groupe (PublicisGroupe) | 0 vagas no Brasil; identificador incerto |
| Freudenberg (Freudenberg) | 0 vagas no Brasil; identificador incerto |
| Syngenta (Syngenta) | 0 vagas; o identificador certo é SyngentaGroup, que está na lista |
| McDonald's (McDonaldsCorporation) | 0 vagas no Brasil |
| Skechers (Skechers) | 0 vagas no Brasil |
| Teleperformance (Teleperformance) | 0 vagas no Brasil; identificador incerto |
| CEVA Logistics (CEVALogistics) | 0 vagas no Brasil; identificador incerto |
| Straumann Group/Neodent (StraumannGroup1) | quadro existe (visto em busca), mas 0 vagas com country=br hoje |
| Pluxee, LVMH, DHL, EFEducationFirst, Adidas, Philips, Yara (SmartRecruiters) | 0 vagas no Brasil; identificadores chutados, sem confirmação de que existem no SR |
| Deel (Ashby: deel) | quadro responde 200, mas com 0 vagas |
| Ramp, Notion, Ashby, PostHog, Trustly (Ashby) | quadro responde, mas nenhuma vaga no Brasil nem remota para LATAM/global (180, 167, 76, 10 e 41 vagas no total) |
| cloudwalk, tractian, cumbuca, cayena, clara, kovi, pomelo, jusbrasil, alice, rippling, descomplica, fintual, kushki, swile, omie, wellhub, loggi, solinftec, traive (Ashby) | HTTP 404: não têm quadro no Ashby com esse nome (podem usar outro ATS ou outro slug) |

Identificador "chutado" quer dizer: testado pelo nome da empresa, sem prova de que ela usa aquele ATS. Um 404 nesses casos não diz onde a empresa publica as vagas.

---

## 8. O que falta conferir (resumo)

| Item | Onde |
|---|---|
| Primeiro pedido de cada fonte com o user agent do joBot | Workday, Eightfold, Oracle HCM, CIEE, IEL, Super Estágios, Cia de Talentos, USP, PTAX |
| `city` e `badge` na API do portal da Gupy | 2.5 |
| Abrir no navegador um link `app.eureca.me/vagas/<id>` (o formato saiu certo na busca real); resposta da Eureca ao pedido de autorização (D80) | 3.2 |
| Consulta de estado por id na Jobicy | 2.2 |
| Host europeu da Lever e do Greenhouse | 2.4 |
| Link montado da vaga na InHire | 3.1 |
| Valores 1, 2 e 3 do campo `remote` da Recrutei | 3.1 |
| Tamanho da resposta do CIEE com `size=1000` | 3.2 |
| `lastmod` e `datePosted` do Super Estágios sem fuso (valem Brasília) e o 404 de uma vaga que saiu do ar mas ainda está no sitemap (a busca real não registrou nenhum) | 3.2 |
| Se o 304 do GitHub poupa a cota | 2.1 |
| Resposta 404 de cada fonte: a captura não a alcança, porque o `ClienteEducado` levanta antes de devolver o corpo | 2.1 a 2.5 |
| Pedido condicional (304) nas fontes que devolvem `ETag` ou `Last-Modified`: não foi testado na rede | 2.1 a 2.5 |
| Páginas além da primeira (GitHub, Himalayas, Jobicy, Gupy): só a primeira foi vista na captura | 2.1, 2.2, 2.5 |
| Se o feed do Google responde 304 ao `If-Modified-Since` (a busca real de 2026-11-14 foi uma rodada só) | 3.4 |
| Oracle HCM: valor de `PostingEndDate` preenchido (o segundo pedido de descoberta com `keyword` da T126 já foi conferido na rede em 2026-11-14: 8 vagas na Oracle, 20 no JPMorgan) | 3.3 |
| Amazon: `locations[].type` igual a `VIRTUAL` numa vaga real | 3.4 |
| Abler: um segundo valor de `status` além de "Em andamento" | 3.1 |
| Termos de uso gerais do Greenhouse e da Lever (só a documentação das APIs foi lida) | 2.4 |
