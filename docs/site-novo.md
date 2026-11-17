# Como acrescentar um site novo

**Português** · [English](site-novo.en.md)

Um site de vagas entra no joBot de duas formas: por um **coletor**, se a lista de vagas é pública, ou por um **leitor**, se o site pede que a pessoa entre com a própria conta. Este guia leva do "achei um site" ao PR. Há dois moldes que já rodam e passam nos testes: o do coletor (`tests/apoio/molde_coletor.py`) e o do leitor (`tests/apoio/molde_leitor.py`). Você copia o que serve, troca o que muda e deixa os testes dizerem o que falta. Os moldes moram em `tests/apoio/`, fora do código que o joBot executa, então não viram fonte por engano. Para consertar uma fonte que já existe, veja [Como consertar uma fonte que quebrou](consertar-fonte.md).

> [!IMPORTANT]
> O joBot ainda está em desenvolvimento. Pull requests de código só são aceitos depois da publicação (fase 9); veja o [guia de contribuição](../.github/CONTRIBUTING.md). Até lá, o caminho é uma issue "Fonte de vagas" com o site, o que você achou e a captura de um exemplo. Este guia já vale para quem quer se preparar.

<a id="antes"></a>
## 1. Antes de começar

Responda estas quatro perguntas antes de abrir qualquer arquivo:

- **O site é público ou pede login?** Se a lista de vagas aparece sem entrar, é um coletor. Se só aparece depois de entrar, é um leitor (seção 6).
- **Os termos do site proíbem robô?** Leia os termos de uso. Site que proíbe coleta automática não entra como fonte pública (ADR 0004). A Meta fica fora por isso.
- **Ele pede CAPTCHA, desafio anti-robô ou bloqueia o pedido?** Então ele não entra como fonte pública. O joBot nunca contorna login, CAPTCHA nem bloqueio: 401, 403, página de login ou desafio são "falhou", e pronto.
- **Alguém já pediu esse site?** Procure nas issues. Se não, abra primeiro uma issue pelo formulário "Fonte de vagas", com o endereço e a resposta às perguntas acima. A decisão de entrar ou não, e de vir ligado ou desligado, é do mantenedor.

<a id="forma"></a>
## 2. Escolher o molde e a pasta

Veja como o site entrega as vagas e parta do exemplo mais parecido:

| O site | Pasta (em `src/jobot/nucleo/coletores/`) | Parta de |
|---|---|---|
| Busca por cargo, resposta em JSON | `portais/` ou `agregadores/` | `tests/apoio/molde_coletor.py` |
| Busca por cargo, resposta em HTML | `portais/` | o molde do coletor, lendo com `selectolax` como em `src/jobot/nucleo/coletores/portais/usp.py` |
| Sitemap e uma página por vaga | `plataformas/` ou `portais/` | `src/jobot/nucleo/coletores/portais/super_estagios.py` |
| RSS ou XML | `agregadores/` | `src/jobot/nucleo/coletores/agregadores/wwr.py` |
| Sistema de recrutamento usado por várias empresas (ATS) | `plataformas/` | `src/jobot/nucleo/coletores/plataformas/lever.py` |
| Site de carreiras de uma empresa | `carreiras/` | `src/jobot/nucleo/coletores/carreiras/google.py` |
| Pede login | `src/jobot/nucleo/leitores/` | `tests/apoio/molde_leitor.py` |

O `tests/unidade/test_estrutura.py` exige que todo coletor more numa das quatro pastas de tipo e que as chaves achadas sejam exatamente as de `src/jobot/nucleo/dados/fontes.json`.

<a id="copiar"></a>
## 3. Copiar e registrar o coletor

Escolha uma **chave**: letras minúsculas e sublinhado (`minha_fonte`). Ela é a mesma em todos os lugares abaixo.

1. Copie `tests/apoio/molde_coletor.py` para `src/jobot/nucleo/coletores/<pasta>/<chave>.py`.
2. Em cada linha com `# MUDE:`, troque o valor: `CHAVE`, `NOME`, `_HOST`, `_API`, `_POR_PAGINA` e `_MAX_PAGINAS`. Troque `_LIMITES = LimitesDaFonte()` por `_LIMITES = limites(CHAVE)`, com `from jobot.nucleo.coletores.registro import limites` (como `src/jobot/nucleo/coletores/plataformas/greenhouse.py`). O registro acha o arquivo sozinho, pelo `COLETOR` do fim.
3. Copie `tests/unidade/coletores/test_molde_coletor.py` para `tests/unidade/coletores/test_<chave>.py` e `tests/fixtures/molde_coletor/` para `tests/fixtures/<chave>/`. No teste, troque as duas linhas com `# MUDE:` (o módulo da fonte e a pasta dos exemplos).
4. Acrescente a linha da fonte em `src/jobot/nucleo/dados/fontes.json`, no fim: `leva` `"B"`, `intervalo_min` e `max_pedidos` (ou `null`), `espera_s`, `credito_obrigatorio` e `por_escopo` (`{}` na maioria), conforme os termos do site. Falta qualquer um desses campos e o `descobrir()` inteiro quebra, de todos os coletores. `ligada_padrao` é opcional e só o mantenedor muda.
5. Dê um nome à fonte, `fonte.<chave>`, nos dois catálogos: `src/jobot/painel/i18n/pt/comum.json` e `src/jobot/painel/i18n/en/comum.json`.
6. Se a fonte é por empresa (o ATS de várias empresas), acrescente a chave em `ATS_POR_EMPRESA` de `src/jobot/painel/rotas/empresas.py`. Se os termos do site são restritivos, acrescente a chave em `FONTES_FORA` de `scripts/vigia.py` e diga isso na issue, porque o README promete todas as fontes públicas ligadas.

Estas listas são escritas à mão de propósito: impedem que uma fonte suma em silêncio. Quem acrescenta uma fonte atualiza cada uma, e o teste de cada lista reprova com a chave no texto:

- `tests/unidade/test_registro.py`: `LEVA_A` ou `LEVA_B` (na ordem de `src/jobot/nucleo/dados/fontes.json`), `CREDITO`, `LIMITES` e o total de fontes;
- `tests/unidade/test_i18n.py`: a lista `FONTES`;
- `tests/integracao/test_cadastros.py`: a contagem de linhas da tabela `fonte` e a de chaves do `src/jobot/nucleo/dados/fontes.json`;
- `src/jobot/nucleo/coletores/registro.py`: a docstring que diz quantas são as fontes;
- `README.md` e `README.en.md`, `wiki/Como-funciona.md` e `wiki/How-it-works.md`: a tabela das fontes por tipo.

O molde nasce com os testes de um coletor correto (`test_normal`, `test_vazio`, `test_formato_mudou`, `test_429_e_erro_de_rede`, `test_304`, `test_bloqueio` e outros). Não apague nenhum: eles guardam as regras do joBot com o site (vaga que não dá para ler é pulada e o estado vira `parcial`; resposta fora da forma vira `falhou`, nunca exceção).

<a id="capturar"></a>
## 4. Capturar um exemplo

Com o arquivo no lugar e o endereço em `_API`, capture uma resposta real. O comando faz um pedido só, com o user agent e a educação do joBot:

```
uv run python scripts/capturar.py <chave> --escopo <termo> --caso normal
```

- `<chave>` é a chave da fonte; `--escopo` é o termo de busca (fonte por termo pede esse argumento); `--caso` é o nome do exemplo.
- O script grava `tests/fixtures/<chave>/normal.json` (ou `.html`, ou `.xml`) e o `.meta.json` dele. Antes de gravar, ele tira dado pessoal, corta a lista em 5 itens e confere o limite de 50 KB. Rode uma vez e pare: não repita em laço.
- O comando grava **só a primeira página**. A página 2 dos testes de paginação se monta dentro do próprio teste, a partir do `normal` capturado.
- **Leia o arquivo gravado.** O detector só acha nome de pessoa em campos conhecidos: troque nomes soltos por `Pessoa Exemplo` e refaça o `sha256` no `.meta.json` (`sha256sum <arquivo>`).
- O `vazio` e o `formato_mudou` se montam à mão a partir do `normal`, com `montado_a_mao` no `.meta.json`. Os exemplos do molde, em `tests/fixtures/molde_coletor/`, mostram a forma.

Nunca use login, cookie, CAPTCHA nem truque para passar de um bloqueio. Se o site recusar o pedido, a fonte "falhou" e a conversa é na issue.

<a id="ler"></a>
## 5. Ensinar o coletor a ler

É o TDD do projeto, com o exemplo no lugar do site:

1. Troque o exemplo `normal` do molde pelo que você capturou. Rode `uv run pytest tests/unidade/coletores/test_<chave>.py -q`: o `test_normal` tem de **falhar** numa asserção. Isso prova que o teste pega o formato novo.
2. Ajuste `_ler` e `_vaga` no arquivo da fonte para entender o formato do site (os nomes dos campos, a forma da lista). Ajuste também o trecho do teste que monta a página 2: o campo de próxima página do site.
3. Rode de novo até passar. Os testes que não dependem do formato (429, 304, bloqueio) passam sem mudança.
4. Acerte o que o teste afirma dos valores do exemplo (quantidade de vagas, títulos, empresas).

Teste de coletor nunca usa a rede: ele usa os exemplos e uma resposta falsa. Escreva o código do zero: ideias e fatos públicos servem, código de outro projeto nunca (sala limpa).

<a id="login"></a>
## 6. Site com login

O site com login é um **leitor**: ele não faz pedido nenhum, só lê o que o navegador do joBot trouxe depois que a pessoa entrou. O joBot nunca digita a senha, e o desafio anti-robô é achado pelo navegador, não pelo leitor: página de login ou de bloqueio é "falhou".

1. **Capture antes de existir leitor**, com a sua própria conta: `uv run python scripts/capturar_logado.py --caso lista --host <host>`. O navegador abre, você entra com a própria senha, vai até a página que quer guardar e aperta Enter. Sem leitor, `--host` é obrigatório. Use `--campo` para a posição dos dados da conta (nome, e-mail), que saem pela posição, nunca pelo valor. Repita para `--caso vaga` e os outros casos. Sem leitor, cada captura cai em `tests/fixtures/<caso>/` (um arquivo e um `.meta.json` por resposta).
2. **Leia cada arquivo** gravado ali antes do commit, procurando dado pessoal solto. Depois de criar o leitor (passo 4), mova os arquivos para `tests/fixtures/<site>_logado/`.
3. Copie `tests/apoio/molde_leitor.py` para `src/jobot/nucleo/leitores/<site>.py` e troque cada linha com `# MUDE:`. A chave termina em `_logado`.
4. Copie `tests/unidade/test_leitor_molde.py` para `tests/unidade/test_leitor_<site>.py` e `tests/fixtures/molde_logado/` para `tests/fixtures/<site>_logado/`. Troque o módulo, a pasta e os valores esperados de cada exemplo. Faça o TDD como na seção 5: troque o exemplo, veja falhar, ajuste os seletores, veja passar.
5. Registre uma instância do leitor em `LEITORES`, em `src/jobot/nucleo/leitores/registro.py`.
6. Dê o nome da fonte, `fonte.<site>_logado`, nos dois catálogos (`src/jobot/painel/i18n/pt/comum.json` e `src/jobot/painel/i18n/en/comum.json`).
7. Atualize as listas fixas de leitor: a lista `FONTES` de `tests/unidade/test_i18n.py`, o teste do registro em `tests/unidade/test_leitores_estado.py` e a contagem da tabela `fonte` em `tests/integracao/test_cadastros.py`.
8. Cada prefixo de `prefixos_login` é `host` + `caminho`, sem esquema, com o host em minúsculas e igual a um dos `hosts` do leitor (por exemplo `www.exemplo.com/entrar`): o navegador compara com o host e o caminho da URL, sem a query, e um prefixo só de caminho (`/entrar`) nunca casa.

O site com login nasce **desligado**: quem usa liga em Configurações. O leitor só diz o que leu; o estado do escopo sai de `estado_do_escopo`. Nunca ponha senha no código, nunca tente passar de um CAPTCHA, e nunca faça o leitor abrir outra rota quando o site pedir login: o PR que fizer isso não entra.

<a id="conferir"></a>
## 7. Conferir

Primeiro o teste da fonte, que é rápido:

```
uv run pytest tests/unidade/coletores/test_<chave>.py -q
uv run pytest tests/unidade/test_leitor_<site>.py -q
```

(o segundo só para site com login). Depois a guarda e as listas fixas:

```
uv run pytest tests/unidade/test_site_novo.py tests/unidade/test_fixtures.py tests/unidade/test_registro.py tests/unidade/test_i18n.py -q
```

O `tests/unidade/test_site_novo.py` é a guarda de site completo: todo coletor e todo leitor registrado tem teste próprio, o leitor tem exemplo válido e toda fonte tem nome nos dois catálogos. Cada falta que ele acha cita a chave e a seção deste guia que ensina a resolver.

Por fim o que o CI vai rodar:

```
uv run pytest -m "not tela" -q
uv run ruff check
uv run ruff format --check
uv run mypy
```

Se o `ruff format --check` reclamar, `uv run ruff format` arruma. O `mypy` roda em modo estrito: se o contrato do joBot mudou desde o molde, ele aponta onde.

<a id="pr"></a>
## 8. Abrir o PR

O fluxo é o da [seção 7 do guia de conserto](consertar-fonte.md#abrir-pr): um fork, um ramo a partir da `dev` com nome começando por `feat/` (por exemplo `feat/minha-fonte`), commits pequenos em português no formato `tipo(escopo): descrição` e o PR para a `dev` pelo [modelo de PR](../.github/pull_request_template.md).

Para um site novo, o PR leva:

- o coletor ou o leitor, com o teste e os exemplos capturados;
- a linha em `src/jobot/nucleo/dados/fontes.json` e o nome nos dois catálogos;
- as listas fixas da seção 3 (ou da seção 6) atualizadas;
- o `README.md` e o `README.en.md` (a tabela das fontes) e o `CHANGELOG.md` e o `CHANGELOG.en.md`, com o mesmo conteúdo nas duas línguas;
- na descrição: o site, se é público ou com login, o que os termos dele dizem sobre robôs e como você testou.

Sem o exemplo capturado e o teste, o PR não entra. Se a fonte tem termos restritivos, a decisão de vir ligada ou desligada fica com o mantenedor.
