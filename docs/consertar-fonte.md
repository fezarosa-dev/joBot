# Como consertar uma fonte que quebrou

**Português** · [English](consertar-fonte.en.md)

Uma fonte é um site de vagas que o joBot lê. Cada fonte tem um **coletor**: um arquivo de código que sabe pedir as vagas ao site e entender a resposta. Quando o site muda o formato sem avisar, o coletor deixa de entender e a fonte "quebra". Este guia mostra, passo a passo, como achar o que mudou e consertar. O exemplo é o Greenhouse, o primeiro coletor do projeto (`src/jobot/nucleo/coletores/greenhouse.py`).

> [!IMPORTANT]
> O joBot ainda está em desenvolvimento. Para mexer no código, clone o repositório e rode `uv sync` dentro dele (o [`uv`](https://docs.astral.sh/uv/) instala o Python 3.14 e as dependências). Pull requests de código só são aceitos depois da publicação (fase 8), e o fluxo da seção 7 vale a partir daí; veja o [guia de contribuição](../.github/CONTRIBUTING.md). Até lá, um conserto pode virar uma issue com o que você achou.

<a id="saber-qual"></a>
## 1. Como saber qual fonte quebrou

Há três caminhos. Os dois primeiros dizem a **fonte** e o **motivo**; o terceiro avisa mesmo quando ninguém olhou o painel.

- **Tela Fontes do painel.** Abra o painel (`jobot abrir`) e entre em "Fontes". Cada fonte mostra como foi a última busca. As que estão "Falhou" ou "Parcial" mostram o motivo, por exemplo "O formato da fonte mudou" (`saude.formato_mudou`).
- **Link "Reportar problema".** Ao lado do motivo, o link abre no GitHub o formulário "Fonte quebrou" já com a fonte e o motivo preenchidos. Você vê e pode editar tudo antes de enviar. O joBot não manda nada sozinho: só o seu clique abre o link, e o GitHub fica sabendo a fonte e o motivo nesse momento. Em fonte por empresa, a fonte aparece como `greenhouse/<empresa>`.
- **Issue do vigia.** Toda segunda-feira o vigia (`.github/workflows/vigia.yml` e `scripts/vigia.py`) testa de verdade um escopo de cada fonte pública e abre uma issue com o rótulo `fonte-quebrada` e o título "Fonte quebrada / broken source: <fonte>". Ele atualiza a issue toda semana e a fecha quando a fonte volta. Eureca, Abler e Gupy ficam de fora, porque os termos delas são restritivos. Bloqueio de IP não conta como quebra para o vigia, porque ele roda de um servidor do GitHub.

Os motivos que valem conserto são: `saude.formato_mudou`, `saude.zero_inesperado`, `saude.empresa_nao_encontrada`, `saude.bloqueio`, `saude.tempo_esgotado`, `saude.erro_de_rede`, `saude.resposta_grande` e `saude.listagem_incompleta`. Os avisos de limite de ritmo (cota, intervalo, 429, limite atingido, orçamento) não são defeito: o joBot só parou para ser educado com o site, e basta esperar.

Antes de mexer no código, espere uma busca ou duas e abra o site no navegador. Muita "quebra" é o site fora do ar por um tempo (`saude.erro_de_rede`, `saude.tempo_esgotado`). `saude.empresa_nao_encontrada` costuma ser só uma empresa que trocou de identificador: confira o identificador no site da empresa antes de culpar o coletor.

<a id="capturar"></a>
## 2. Capturar a página de novo

O script `scripts/capturar.py` faz **um** pedido ao vivo, do mesmo jeito que o joBot faz (mesmo user agent, mesma educação com o site), e guarda a resposta como exemplo. Antes de gravar, ele tira dado pessoal, corta a lista em 5 itens e confere o limite de 50 KB.

```
uv run python scripts/capturar.py greenhouse --escopo vitta --caso novo
```

- `greenhouse` é a chave da fonte, a mesma da tela Fontes.
- `--escopo` é o identificador da empresa, para fontes por empresa (aqui `vitta`). Em fonte sem empresa, deixe de fora.
- `--caso novo` é o nome do exemplo. Use um nome novo: assim o exemplo antigo continua lá para você comparar.

O script grava `tests/fixtures/<fonte>/<caso>.json` (ou `.html`, ou `.xml`, conforme a fonte) e o `tests/fixtures/<fonte>/<caso>.meta.json`, com o endereço, a data, o código HTTP e o `sha256` do arquivo. Rode uma vez e pare: não repita em laço, nem contra um site que está bloqueando você.

Se ele recusar, a mensagem diz por quê. "nada capturado" quer dizer que o site não respondeu com a página (bloqueado, fora do ar). "dado pessoal que a limpeza não pegou" quer dizer que nada foi gravado, porque sobrou e-mail, telefone ou documento: não coloque esse conteúdo à mão no repositório, descreva o caso numa issue. O detector só acha nome de pessoa em campos conhecidos, então **leia o arquivo gravado** procurando nomes soltos em texto livre e troque por `Pessoa Exemplo`; depois refaça o `sha256` no `.meta.json`.

Nunca use login, cookie, CAPTCHA nem truque para passar de um bloqueio. Se o site pede qualquer um deles, a fonte fica "falhou" e pronto.

<a id="comparar"></a>
## 3. Achar o que mudou

Compare o exemplo antigo (`normal`) com o novo:

```
git diff --no-index tests/fixtures/<fonte>/normal.json tests/fixtures/<fonte>/<caso>.json
```

As vagas trocam toda hora, então os **valores** sempre vão diferir. Olhe os **nomes dos campos** e a **forma** da resposta: um campo que sumiu, outro com nome novo, um número que virou texto, uma lista que agora vem dentro de outro objeto, uma página HTML com outra estrutura.

No exemplo do Greenhouse, o coletor lê `title`, `company_name`, `absolute_url`, `content`, `location`, `departments`, `first_published` e `application_deadline` de cada item da lista `jobs`. Se o site passasse a mandar `name` no lugar de `title` e `url` no lugar de `absolute_url`, a vaga seria pulada e a fonte ficaria "Parcial" com `saude.formato_mudou`. O exemplo `tests/fixtures/greenhouse/formato_mudou.json` mostra justamente uma resposta quebrada assim.

O que cada fonte devolve em condições normais está descrito no [apêndice das fontes](superpowers/specs/2026-11-13-fase-1-fontes.md) (o Greenhouse está na seção 2.4). Se o site mudou, o apêndice também fica desatualizado: avise na descrição do PR.

<a id="ajustar"></a>
## 4. Ajustar o coletor

Antes de mexer no código, faça o primeiro passo da seção 5 (trocar o exemplo `normal` pelo novo) e rode o teste do coletor: ele tem de falhar. Isso prova que o teste pega a quebra. Só então corrija o código, que é o TDD do projeto: teste primeiro, falha, conserto, passa.

O contrato de todo coletor está em `src/jobot/nucleo/coletores/base.py`. Cada coletor oferece:

- `escopos`: a lista do que buscar (por empresa, por país, ou um só).
- `coletar`: faz o pedido e devolve as vagas, o estado (`ok`, `sem_mudanca`, `parcial`, `falhou` ou `no_limite`) e o motivo.
- `detalhar`: só nas fontes em que a lista não traz a descrição; abre cada vaga.
- `resolver`: só nas fontes por empresa; entende o endereço que a pessoa colou.

No Greenhouse, o conserto de um campo renomeado mora em `_vaga`, que lê uma vaga da lista. Regras do molde que o conserto não pode quebrar:

- Vaga sem título, empresa ou endereço válido é **pulada**, e o estado vira `parcial`, nunca `ok`. Um `ok` fecharia por engano a vaga que foi pulada.
- Resposta sem a forma esperada vira `falhou` com `saude.formato_mudou`, nunca exceção.
- Motivo novo não se inventa no coletor: use as chaves `saude.*` que existem em `src/jobot/painel/i18n/pt/comum.json`. Se faltar uma, descreva na descrição do PR.
- O coletor não mexe em `src/jobot/nucleo/coletores/registro.py` nem em `src/jobot/nucleo/dados/fontes.json`. O registro acha o arquivo sozinho; limites de ritmo e intervalos ficam neste último.
- Código escrito do zero. Você pode usar ideias e fatos públicos, nunca copiar código de outro projeto (sala limpa).

<a id="atualizar-exemplo"></a>
## 5. Atualizar o exemplo e os testes

1. Troque o exemplo `normal` pelo novo: substitua `tests/fixtures/<fonte>/normal.json` e o `tests/fixtures/<fonte>/normal.meta.json` pelos arquivos do caso novo, e apague o caso `novo` que sobrou. Se preferir, rode a captura de novo com `--caso normal`.
2. Refaça os casos **montados à mão** a partir do `normal` novo. O `.meta.json` deles tem o campo `montado_a_mao`, que diz de onde vieram. No Greenhouse são `formato_mudou`, `nao_encontrado` e `prazo`; `normal` e `vazio` não têm esse campo; confira o `vazio` também, que pode ter mudado de forma. Depois de mexer num arquivo, atualize o `sha256` no `.meta.json` (no Linux, `sha256sum <arquivo>` dá o valor): o teste `tests/unidade/test_fixtures.py` confere.
3. Se o formato quebrado é um caso que ainda não tinha teste, acrescente um exemplo e um teste em `tests/unidade/coletores/test_<fonte>.py`, no mesmo estilo dos que já existem.
4. Ajuste o que o teste afirma de valores do exemplo (quantidade de vagas, títulos), que mudam com o exemplo novo.

Teste de coletor nunca usa a rede: ele usa os exemplos e uma resposta falsa. O exemplo é a única ponte entre o site real e os testes.

<a id="testar"></a>
## 6. Rodar os testes, o lint e os tipos

Primeiro só o teste da fonte, que é rápido:

```
uv run pytest tests/unidade/coletores/test_<fonte>.py -q
```

Depois os quatro conferem que o CI vai rodar:

```
uv run pytest -m "not tela" -q
uv run ruff check
uv run ruff format --check
uv run mypy
```

O `pytest` roda todos os testes menos os de tela (que precisam do navegador e rodam só no CI). O `ruff check` e o `ruff format --check` cuidam do estilo e o `mypy` cuida dos tipos, em modo estrito. Os quatro precisam passar. Se o `ruff format --check` reclamar, `uv run ruff format` arruma.

<a id="abrir-pr"></a>
## 7. Abrir o PR

O fluxo é o do [guia de contribuição](../.github/CONTRIBUTING.md):

1. Faça um fork e crie um ramo a partir da `dev`, com o nome começando por `fix/` (por exemplo `fix/greenhouse-campos`).
2. Faça commits pequenos, em português, no formato `tipo(escopo): descrição`, como `fix(coletor): lê o título novo do Greenhouse`.
3. Abra o PR para a `dev` pelo [modelo de PR](../.github/pull_request_template.md). Diga qual fonte quebrou, o motivo que a tela ou o vigia mostrou, o que mudou no site e como você testou. Se foi uma issue do vigia, cite o número.
4. PR de conserto precisa levar o **exemplo capturado novo** e o **teste**. Sem eles, não entra.

O primeiro PR de quem nunca contribuiu pode esperar o mantenedor liberar a execução dos testes no GitHub. É uma trava contra abuso, não um julgamento do seu conserto.
