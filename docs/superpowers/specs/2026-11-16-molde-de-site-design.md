# Molde de site novo: desenho

Data: 2026-11-16. Decisões de origem: ADR 0004 (fontes públicas e coleta educada), ADR 0005 (sites com login), ADR 0016 (sala limpa: toda fixture é capturada por nós), ADR 0018 (manutenção pela comunidade, CI em todo PR), ADR 0022 (CAPTCHA só pelo serviço da pessoa) e o desenho da fase 2 (`docs/superpowers/specs/2026-11-15-fase-2-design.md`, seções A4, A5, A7, A10 e 6). O pedido do dono está na memória da sessão de 2026-11-16 ("meta 100%"): acrescentar uma plataforma nova tem de ser simples, com um molde pronto, um guia e os passos de captura.

Este documento é a especificação para planejar e construir o molde sem voltar ao dono. Todo fato sobre o código vem com `arquivo:linha`, conferido em 2026-11-16 na árvore da `dev` (worktree `docs/molde-site`). As linhas podem andar: quando a linha não bater, procure pelo nome. As lições de `registros/padroes.md` são citadas por rótulo.

Cada decisão leva um número M1 a M12 (seção 11). Todas são da sessão, tomadas pela recomendação com o dono fora, e estão **para confirmar**. A D156 do `duvidas.md` as resume.

## 1. Intenção e porquê

O joBot vive de coletores que a comunidade mantém (ADR 0018). Consertar uma fonte que quebrou já tem guia (`docs/consertar-fonte.md`), captura (`scripts/capturar.py`) e vigia semanal (`scripts/vigia.py`). Acrescentar uma fonte nova não tem: o caminho existe só no plano da fase 1 ("Molde do coletor", `docs/superpowers/plans/2026-11-13-fase-1.md:109-122`), escrito para agentes que já conhecem o projeto, e no desenho da fase 2 (seção 6), escrito para uma sessão com o dono.

Hoje, quem quer pôr um site novo precisa descobrir sozinho:

- qual coletor existente copiar, e o que nele é particular daquele site;
- que a chave nova precisa estar em `fontes.json` antes de o módulo importar;
- que cinco testes do repositório têm a lista das fontes escrita à mão e quebram de propósito;
- como capturar o exemplo antes de o coletor saber ler a resposta;
- e, para site com login, que o leitor é outro contrato, com outro registro e outra captura.

Daqui a um ano, um site lançado nesse meio-tempo (ou um dos já pedidos: Vagas.com, Catho, Indeed) tem de entrar sem que a pessoa leia os planos da fase 1 e da fase 2. O molde é esse atalho: arquivos de partida que já passam nos testes, um guia curto nas duas línguas e uma guarda no CI que diz o que falta.

## 2. Objetivos, não objetivos e anti-objetivos

Objetivos:

1. Um molde de **coletor público** que já roda, com os testes mínimos do "Molde do coletor" e exemplos montados à mão, pronto para copiar.
2. Um molde de **leitor com login** que já roda, com os testes do contrato `LeitorComLogin` e exemplos montados à mão, pronto para copiar.
3. Um **guia** para quem contribui, em português e inglês, do "achei um site" ao PR: escolher o molde, copiar, registrar, capturar, TDD, conferir.
4. **Passos de captura** que reaproveitam `scripts/capturar.py` e `scripts/capturar_logado.py`, sem modo novo.
5. Uma **guarda no CI** que reprova site registrado sem teste próprio, sem exemplo válido ou sem nome nos catálogos, com a mensagem apontando a seção do guia.

Não objetivos:

- Nenhum site novo. Vagas.com, Catho, Indeed e outros ficam para o futuro; o molde só prepara o caminho. O molde não entra em `fontes.json`, em `LEITORES` nem no painel.
- Gupy continua só pública; LinkedIn continua o único site com login. Nada aqui muda os dois.
- Sem gerador de código (M1).
- Sem mexer no contrato `Coletor` (`src/jobot/nucleo/coletores/base.py:85-99`) nem no `LeitorComLogin` (`src/jobot/nucleo/leitores/base.py:42-67`).
- Sem dependência nova.

Anti-objetivos (o molde nunca ensina nem facilita):

- Contornar login, CAPTCHA, desafio anti-robô ou bloqueio. 401, 403, página de login ou desafio = a fonte "falhou" (ADR 0004; `CLAUDE.md` do projeto). O molde do coletor tem o teste `test_bloqueio` (um pedido só, sem repetir com outro cabeçalho) justamente para isso.
- Trocar o user agent do joBot, tirar o intervalo por host ou ignorar 429 e `Retry-After` (ADR 0004, `docs/decisions/0004-fontes-publicas.md:40`).
- Copiar código ou fixture de outro projeto, ou parafrasear (ADR 0016, `docs/decisions/0016-licenca-clean-room-e-processo.md:21-22`).
- Fixture com e-mail, telefone ou nome de pessoa.
- O joBot digitar senha. No site com login, quem entra é a pessoa.

## 3. Restrições

- Camadas: o molde do coletor só usa o que um coletor de `nucleo` pode usar (biblioteca padrão, `jobot.nucleo`, `selectolax`); o do leitor, o que um leitor pode usar (puro, sem `playwright`). `tests/unidade/test_camadas.py` não vê `tests/apoio`, então quem copia o molde para `src/` passa pela guarda de camadas ali.
- Testes sem rede e sem tempo real (`tests/conftest.py`): os moldes rodam com `httpx.MockTransport` e `RelogioFalso`.
- Toda fixture versionada é nossa e sem dado pessoal: `tests/unidade/test_fixtures.py:68-75` varre todas as pastas de `tests/fixtures/`, as dos moldes inclusive, e `:103-109` prende o teto de 50 KB.
- Documentos para quem contribui são bilíngues (`README`, `CONTRIBUTING`, `consertar-fonte` e agora o guia novo); desenho, plano e `duvidas.md` só em português.
- Nesta máquina rodam só o arquivo de teste da tarefa e o `ruff`; suíte inteira e `mypy` no CI de uma branch `lote/<nome>`.

## 4. Como funciona hoje (fatos conferidos)

### 4.1 Coletor público

- O contrato é o `Coletor` (`src/jobot/nucleo/coletores/base.py:85-99`): atributos `chave`, `nome`, `leva`, `hosts`, `credito_obrigatorio`, `intervalo_min`, `max_pedidos`, `espera_s`, `por_escopo`, e os métodos `escopos`, `coletar`, `detalhar`, `resolver`.
- `juntar_paginas` (`base.py:106`) soma as páginas e traduz as exceções do `HttpEducado` em estado (`LimiteAtingido`, `OrcamentoGasto`, `Parou429`, `Bloqueio`, `ErroDeRede`). O 304 é a página `SEM_MUDANCA` (`base.py:62`), comparada por identidade.
- O registro é por descoberta: `descobrir` (`src/jobot/nucleo/coletores/registro.py:52-63`) importa todo módulo do pacote e junta os `COLETOR`. Os limites vêm de `fontes.json` por `limites(chave)` (`registro.py:47-49`), com `KeyError` se a chave não estiver lá. Como todo coletor lê `_LIMITES = limites("<chave>")` no import (ex.: `src/jobot/nucleo/coletores/plataformas/greenhouse.py:27`), um coletor novo sem linha em `fontes.json` derruba o `descobrir()` inteiro.
- O coletor mora numa das quatro pastas de tipo (`agregadores`, `carreiras`, `plataformas`, `portais`): `tests/unidade/test_estrutura.py:23-38`. `test_estrutura.py:41-43` exige que as chaves achadas sejam exatamente as de `fontes.json`.
- Fonte que não é por empresa responde ao `resolver` com `ValueError` (`src/jobot/nucleo/coletores/agregadores/remotive.py:136-138`). Fonte por empresa entra também em `ATS_POR_EMPRESA` (`src/jobot/painel/rotas/empresas.py:50`) para aparecer no cadastro de empresas.
- Testes de um coletor: um arquivo por fonte em `tests/unidade/coletores/test_<chave>.py`, com um `_coletar` próprio que roda o `ClienteEducado` sobre um `MockTransport` (`tests/unidade/coletores/test_greenhouse.py:47`). Os nomes seguem o "Molde do coletor": `test_normal`, `test_vazio`, `test_formato_mudou`, `test_429_e_erro_de_rede`, `test_304`, `test_bloqueio`, `test_endereco_e_parametros` (`test_greenhouse.py:134-274`). Hoje as 28 fontes têm esse arquivo.
- Exemplos: `tests/fixtures/<chave>/<caso>.<ext>` com `<caso>.meta.json`. `tests/unidade/test_fixtures.py:50-65` exige, para toda chave de `descobrir()`, pasta com pelo menos um caso e o meta completo (`capturar.problemas`, `scripts/capturar.py:403`). O caso montado à mão leva `montado_a_mao` e o `sha256` (`tests/fixtures/greenhouse/formato_mudou.meta.json`).

### 4.2 Listas fixas que um site novo obriga a mexer

Estas listas são escritas à mão de propósito: impedem que uma fonte suma em silêncio.

| Onde | O que prende |
|---|---|
| `tests/unidade/test_registro.py:31-39`, `:42-53`, `:84-99` | `LEVA_A`, `LEVA_B`, `CREDITO`, `LIMITES` (começa na linha 42) e o total de 28 fontes em `fontes.json` |
| `tests/unidade/test_i18n.py:17-21`, `:42` | `FONTES`: toda chave, `linkedin_logado` inclusive, tem `fonte.<chave>` nos catálogos |
| `tests/integracao/test_cadastros.py:186`, `:203`, `:272` | 29 linhas na tabela `fonte` (28 públicas + o leitor) e 28 chaves de `fontes.json` |
| `tests/unidade/test_leitores_estado.py:134-135` | o registro de leitores tem só o `linkedin_logado` |
| `src/jobot/nucleo/coletores/registro.py:1` | a docstring diz "28 fontes" |
| `README.md:186` e o par em inglês, `wiki/Como-funciona.md:106` e `wiki/How-it-works.md` | a tabela das fontes por tipo |

E duas regras de documento:

- `tests/unidade/test_documentos.py:338-341`: README e CHANGELOG dizem que **todas** as fontes públicas vêm ligadas; uma fonte nova com `ligada_padrao: false` reprova esse teste e pede mudar o texto (decisão do dono, R4).
- `scripts/vigia.py:48`, `:128-131`: o vigia testa toda chave de `descobrir()` menos `FONTES_FORA` (termos restritivos). Fonte nova entra no vigia sozinha; fonte com termos restritivos vai para `FONTES_FORA`.

### 4.3 Site com login

- O contrato é o `LeitorComLogin` (`src/jobot/nucleo/leitores/base.py:42-67`): `chave` terminada em `_logado`, `nome`, `hosts`, `url_login`, `url_entrada`, `prefixos_login`, `respostas`, `campos_conta`, `rolar`, `lista_tem_descricao`, `lista_exaustiva`, e os métodos puros `escopos`, `e_login`, `pagina_logada`, `pagina_bloqueada`, `proxima`, `ler`, `detalhar`. O navegador entrega `Captura` e `RespostaCapturada` (`base.py:13-26`); o leitor devolve `Leitura(vagas, pulados, formato_mudou)` (`base.py:35-39`).
- O registro é explícito: `LEITORES = (LinkedIn(),)` (`src/jobot/nucleo/leitores/registro.py:6`), com `ValueError` para chave sem `_logado` ou repetida (`:9-18`).
- O estado do escopo sai de uma função pura com precedência fixa: parada (`precisa_login` > `bloqueio` > `captcha` > `no_limite`), depois `formato_mudou`, cortada, pulados, zero inesperado, ok (`src/jobot/nucleo/leitores/estado.py:26-52`). O leitor só diz o que leu; quem decide o estado é essa função.
- A fonte com login nasce desligada: `semear_leitores` grava `ligada = 0, com_login = 1` (`src/jobot/banco/cadastros.py:125-136`).
- Limites da navegação, iguais para todo site: `MAX_LISTA = 10` páginas de lista e `MAX_VAGA = 20` páginas de vaga por site, espera de 3 a 8 s entre navegações, janela parada de 900 s (`src/jobot/navegador/limites.py:10-16`). A política só abre `https` dos `hosts` do leitor, nunca host local (`src/jobot/navegador/politica.py:35-47`). `lista_exaustiva = False` faz a vaga ausente só fechar depois de 30 dias (`src/jobot/nucleo/tratamento/ciclo_de_vida.py:7`, `:43`).
- O desafio anti-robô é achado pelo navegador (`achar_widget`), não pelo leitor (`src/jobot/nucleo/leitores/linkedin.py`, `pagina_bloqueada` devolve `False` com esse comentário). O leitor só reconhece a página de bloqueio própria do site.
- Exemplos de leitor: `tests/fixtures/linkedin_logado/` (HTML com `.meta.json`), lidos por `tests/unidade/test_leitor_linkedin.py:17`. Nenhum teste passa essa pasta por `capturar.problemas`, porque `test_fixtures.py:64` só percorre `descobrir()`, que não vê leitores. É a lacuna que `registros/padroes.md` («Fixtures») registra ("Fixture de leitor fora do `descobrir()`: `sha256` à mão com `capturar.problemas(pasta)`").
- Há um leitor mínimo de teste, o `LeitorFalso` (`tests/apoio/site_falso.py:548`), mas ele lê o HTML e o JSON do site falso local e serve aos testes do navegador; não é um ponto de partida limpo.

### 4.4 Captura

- `scripts/capturar.py <fonte> [--escopo <id>] --caso <nome>` (docstring `:1-25`, `main` em `:614-626`) só aceita chave de `descobrir()`. Ele roda o próprio coletor e para na primeira resposta (`_Capturado`, `:466`, `:491`): o pedido é o que o `coletar` faz, e a leitura da resposta não importa. Sem `--escopo`, usa o primeiro de `escopos(ContextoColeta((), (), ()))`; fonte sem escopo próprio (por termo, por empresa) pede `--escopo` (`:537-541`). Tira dado pessoal, reduz a 5 itens e 50 KB, grava o meta e recusa se sobrar algo.
- `scripts/capturar_logado.py [<leitor>] --caso <nome> [--host H]... [--campo C]... [--login URL] [--recorte SELETOR]... [--tirar REGEX]...` (docstring `:1-35`, `main` em `:591`): abre o navegador do joBot, a pessoa entra com a própria senha e navega, e a captura grava. **Sem leitor**, `--host` é obrigatório e entra todo JSON desses hosts e o HTML final: dá para capturar o site antes de existir leitor. Os dados da conta saem pela posição (`--campo`, ou `campos_conta` do leitor), nunca pelo valor.

### 4.5 Documentos para quem contribui

- `docs/consertar-fonte.md` e `.en.md`: sete seções numeradas, com âncoras iguais nas duas línguas.
- `tests/unidade/test_guia_consertar_fonte.py:13-14`: o guia tem as mesmas seções em pt e en (`:76`), todo comando `jobot` e todo caminho citado existem (`:86`), os links relativos existem (`:107`) e o `CONTRIBUTING` cita o guia (`:117`). `GUIAS` é um dicionário de um guia só.
- `.github/CONTRIBUTING.md:13-17`: sugestão de fonte por issue (formulário `fonte.yml`); PR de código só depois da fase 9.
- Divergência achada: `docs/consertar-fonte.md:8` diz "depois da publicação (fase 8)"; o `CONTRIBUTING.md:15` e o roteiro novo dizem fase 9 (`CHANGELOG.md`, "Alterado" do "Não lançado"). Correção R1 na T299.
- `wiki/Arquitetura.md:374` e `wiki/Architecture.md:374` linkam o guia de conserto.
- Divergência achada, fora deste guia: `README.md:190`, `README.en.md:190`, `wiki/Como-funciona.md:110`, `wiki/How-it-works.md:110` e a ordem de mapeamento em `wiki/Roteiro.md:51` e `wiki/Roadmap.md:51` listam Gupy (com login), Vagas.com, Catho e Indeed como sites com login da fase 2; hoje só o LinkedIn tem login, a Gupy é só pública e os outros ficam para o futuro. A T300 alinha os textos; nenhum teste prende essas linhas.

## 5. O como

### 5.1 (a) Molde do coletor público

**Forma escolhida (M2):** busca por termo, resposta JSON, paginada por número de página. É a forma dos portais que a comunidade pede (Vagas.com, Catho, Indeed buscam por cargo e paginam) e exercita o que todo coletor precisa: escopo, paginação, 304, item pulado, formato mudou, 429, bloqueio. Para as outras formas, o guia aponta um coletor real (5.4).

**Arquivos (M1):**

- `tests/apoio/molde_coletor.py`: o coletor de partida.
- `tests/unidade/coletores/test_molde_coletor.py`: os testes do molde, que são também o teste de partida da fonte nova.
- `tests/fixtures/molde_coletor/`: `normal.json` (uma página, a que o `capturar.py` grava), `vazio.json`, `formato_mudou.json`, cada um com `.meta.json` montado à mão (M4).

O `capturar.py` grava só a primeira resposta (`scripts/capturar.py:466`, `:491`), então o molde tem uma página capturada e nada de `normal_p2.json`. Os testes de paginação montam a página 2 no próprio código do teste, a partir do `normal.json` (trocando o campo de próxima página ou de cursor, de modo que a página 1 diga que há próxima e a 2 diga que não há).

O molde fica em `tests/apoio`, não em `src/`: assim o `descobrir()` não o acha, ele não vira fonte, não entra no vigia e não mexe nas listas fixas. Ele não apodrece: o `pytest` roda os testes dele em todo PR, e o `mypy --strict` confere o protocolo por `alvo: Coletor = molde_coletor.COLETOR` no teste.

**O que o molde tem (assinaturas; o corpo é do construtor):**

- No topo, as constantes que mudam, cada uma com o comentário `# MUDE:` dizendo o quê: `CHAVE = "molde_coletor"`, `NOME = "Molde"`, `_HOST = "vagas.exemplo.invalid"`, `_API = f"https://{_HOST}/api/vagas"`, `_POR_PAGINA = 20`, `_MAX_PAGINAS = 5`.
- `_LIMITES = LimitesDaFonte()`, com `# MUDE: na cópia, limites(CHAVE)` (o molde não está em `fontes.json`).
- `class _FormatoMudou(Exception)`.
- `_vaga(escopo: str, item: object) -> VagaColetada | None`: `None` se faltar título, empresa ou URL http(s) (`ValueError` da `VagaColetada` vira `None`).
- `_ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, bool]`: vagas legíveis, quantas puladas, se há próxima página. `_FormatoMudou` se não é JSON, se falta a lista, ou se a lista tem itens e nenhum é legível.
- `class Molde` com os atributos do `Coletor` lidos de `_LIMITES`, `hosts = (_HOST,)`, e:
  - `escopos(ctx) -> Sequence[str]`: os termos de `ctx.termos`, com `strip`, sem vazios e sem repetidos (`registros/padroes.md` («Coletor paginado»)).
  - `coletar(escopo, http) -> ResultadoEscopo`: gerador de páginas `GET _API` com `params={"q": escopo, "pagina": n}` e `condicional=True`; 304 dá `SEM_MUDANCA` (o próprio objeto); para quando a página diz que não há próxima; passou de `_MAX_PAGINAS` com próxima ainda presente, `parcial` com `saude.limite_atingido` (`shortcut:` no código); item pulado com resultado `ok` vira `parcial` com `saude.formato_mudou`; `_FormatoMudou` vira `falhou` com `saude.formato_mudou`. As exceções do `HttpEducado` ficam com `juntar_paginas`. O módulo importa `juntar_paginas` pelo nome, para o `test_304` espiar.
  - `detalhar(item: Item, http)` devolve `None` (a lista já traz a descrição), com o comentário de quando trocar. O parâmetro é `Item` (`VagaColetada | UrlListada`, `base.py:54`), como em `greenhouse.py:166` e `remotive.py:132`: tipo mais estreito reprova a linha `alvo: Coletor = molde_coletor.COLETOR` no `mypy --strict`.
  - `resolver` levanta `ValueError` (fonte por termo, não por empresa).
- `COLETOR = Molde()`.

**Testes do molde** (`test_molde_coletor.py`, nomes do "Molde do coletor"):

- `test_cumpre_o_protocolo`: `alvo: Coletor = molde_coletor.COLETOR` e `alvo.chave == molde_coletor.CHAVE`.
- `test_escopos_um_por_termo`: termos repetidos e com espaço viram um escopo cada; vazio sai.
- `test_normal`: duas páginas (o `normal.json` e a página 2 montada no teste), estado `ok`, número de vagas certo, campos lidos, `url` http(s), `fonte == CHAVE`, `escopo` igual ao termo.
- `test_vazio`: zero vagas, `ok`.
- `test_formato_mudou`: um item fora do formato no meio de bons dá `parcial` com `saude.formato_mudou`; lista só com itens tortos, ou sem a lista, dá `falhou`; nunca exceção.
- `test_paginacao_para_no_teto`: com `_MAX_PAGINAS` pequeno por `monkeypatch` e a próxima sempre presente, `parcial` com `saude.limite_atingido` e exatamente `_MAX_PAGINAS` pedidos.
- `test_429_e_erro_de_rede`: 429 dá `no_limite` com `saude.parou_429`; erro de rede na página 1 dá `falhou`, na página 2 dá `parcial`.
- `test_304`: o coletor devolve exatamente `base.SEM_MUDANCA` (espia `molde_coletor.juntar_paginas` por `monkeypatch` e afirma `pagina is base.SEM_MUDANCA`); estado `sem_mudanca`.
- `test_bloqueio`: 403 dá `falhou` com `saude.bloqueio`, um pedido só.
- `test_endereco_e_parametros`: host, caminho, método `GET` e os parâmetros `q` e `pagina` exatos.
- `test_resolver_recusa`: `ValueError`.
- `test_fixtures_do_molde_sem_problemas`: `capturar.problemas(PASTA) == []` para `tests/fixtures/molde_coletor` (carregando `scripts/capturar.py` como `tests/unidade/test_fixtures.py:15-23`). `test_fixtures.py:64` só percorre `descobrir()`, que não vê o molde; este teste fica no arquivo do molde e sobrevive à cópia, com `PASTA` trocada.

**Na cópia** (o guia diz, 5.4): o arquivo vai para `src/jobot/nucleo/coletores/<tipo>/<chave>.py`, o teste para `tests/unidade/coletores/test_<chave>.py`, troca-se `molde_coletor` pela chave nos dois, as constantes `# MUDE:` mudam, `_LIMITES` passa a `limites(CHAVE)`, e os exemplos montados à mão dão lugar aos capturados (o `formato_mudou` montado à mão a partir do `normal` capturado, como manda o "Molde do coletor"). O trecho do teste que monta a página 2 passa a seguir o campo de próxima página do site.

### 5.2 (b) Molde do leitor com login

**Forma escolhida (M3):** lista em HTML, escopo por termo, próxima página por link, descrição só na página da vaga (`lista_tem_descricao = False`, `detalhar` presente). É a forma do LinkedIn sem as particularidades dele (cartão por `componentkey`, datas relativas, salário, cidade e remoto).

**Arquivos:**

- `tests/apoio/molde_leitor.py`: o leitor de partida.
- `tests/unidade/test_leitor_molde.py`: os testes do molde (nome no padrão `test_leitor_<chave sem _logado>.py`, que a guarda da 5.6 espera).
- `tests/fixtures/molde_logado/`: `lista.html`, `lista_p2.html`, `vazia.html`, `login.html`, `bloqueio.html`, `vaga.html`, `torta.html`, cada um com `.meta.json` montado à mão (M4).

**O que o molde tem:**

- Constantes `# MUDE:` no topo: `CHAVE = "molde_logado"` (o sufixo `_logado` é obrigatório, `registro.py:13-14`), `NOME`, `_HOST = "vagas.exemplo.invalid"`, `URL_LOGIN`, `URL_ENTRADA`, `PREFIXOS_LOGIN` (host e caminho, como compara o `casa_login`, `politica.py:50`), `_CARTAO` (seletor de cada vaga da lista), `_PROXIMA` (seletor do link da próxima página), `_MARCA_LOGADA` (seletor de algo que só aparece logado e não depende de vaga), `_MARCA_BLOQUEIO` (seletor da página de bloqueio própria do site), `_DESCRICAO`.
- `class MoldeLogado` com os atributos do `LeitorComLogin` (`respostas = ()`, `campos_conta` com a posição do nome da conta no cabeçalho, `rolar = False`, `lista_tem_descricao = False`, `lista_exaustiva = False`) e:
  - `escopos(ctx) -> Sequence[EscopoLogado]`: um por termo, `EscopoLogado(termo, f"https://{_HOST}/busca?q={quote_plus(termo)}")`.
  - `e_login(captura) -> bool`: a URL casa `PREFIXOS_LOGIN`.
  - `pagina_logada(html, url) -> bool`: fora do login e com `_MARCA_LOGADA`, ignorando o que estiver dentro da descrição de vaga (texto de terceiro).
  - `pagina_bloqueada(html, url) -> bool`: `_MARCA_BLOQUEIO` presente. O desafio anti-robô (CAPTCHA, Cloudflare) **não** é do leitor: o navegador acha.
  - `proxima(captura) -> str | None`: o `href` de `_PROXIMA`, resolvido contra a URL, só `https` e só `_HOST`; senão `None`.
  - `ler(captura, escopo) -> Leitura`: lista não achada, `formato_mudou=True`; itens e nenhum legível, `formato_mudou=True`; item torto no meio, pulado e contado; lista vazia legível, `Leitura((), 0, False)`. Cada vaga com `fonte = CHAVE`, `escopo = escopo.id`, URL canônica da vaga.
  - `detalhar(captura, vaga) -> VagaColetada | None`: a vaga com a descrição de `_DESCRICAO`; `None` se a página não tem a descrição.
- `LEITOR = MoldeLogado()`.

**Testes do molde** (`test_leitor_molde.py`, os do passo 3 da Parte B do desenho da fase 2, mais o das fixtures):

- `test_cumpre_o_protocolo`: `alvo: LeitorComLogin = molde_leitor.LEITOR`; `chave` termina em `_logado`.
- `test_escopos_um_por_termo`.
- `test_e_login_pela_url` e `test_pagina_de_login_nao_e_logada`.
- `test_pagina_logada_pela_marca` e `test_marca_dentro_da_descricao_nao_conta`.
- `test_pagina_bloqueada`.
- `test_proxima_da_lista` e `test_proxima_fora_do_host_e_none`.
- `test_ler_lista`: vagas, campos, `fonte`, `escopo`.
- `test_ler_lista_vazia_e_valida`, `test_sem_lista_e_formato_mudou`, `test_item_torto_conta_pulado`, `test_so_itens_tortos_e_formato_mudou`.
- `test_detalhar_traz_a_descricao` e `test_detalhar_sem_descricao_e_none`.
- `test_estado_com_o_molde`: as leituras do molde passadas a `estado_do_escopo` dão `ok`, `parcial` com `saude.formato_mudou` (pulado) e `falhou` com `saude.formato_mudou` (sem lista), para mostrar a quem copia que o estado não é do leitor.
- `test_fixtures_do_molde_sem_problemas`: `capturar.problemas(PASTA) == []` para `tests/fixtures/molde_logado`. Nenhum teste de hoje passa a pasta de um leitor por `capturar.problemas`; este fica no arquivo do molde e sobrevive à cópia.

**Na cópia:** `src/jobot/nucleo/leitores/<site>.py`, `tests/unidade/test_leitor_<site>.py` (o nome do LinkedIn: `test_leitor_linkedin.py`), fixtures em `tests/fixtures/<site>_logado/` capturadas com `capturar_logado.py`, e o leitor entra em `LEITORES` (`registro.py:6`).

**Sinais de "falhou"**, que o guia repete: página de login (`e_login`, `prefixos_login`) dá `saude.precisa_login`; página de bloqueio do site dá `saude.bloqueio`; desafio anti-robô dá `saude.captcha` (achado pelo navegador; o 2Captcha só age se a pessoa pôs a chave e ligou, ADR 0022); 429 dá `no_limite`; lista sumida dá `saude.formato_mudou`. Em nenhum caso o leitor tenta outra rota.

**Limites e janela:** o leitor não escolhe teto nem espera; valem os de `navegador/limites.py` para todo site (10 páginas de lista, 20 de vaga, 3 a 8 s entre navegações). Site que pede menos que isso (termos ou ritmo) é R4: vai ao `duvidas.md` antes, porque `limites.py` é global.

### 5.3 (c) Gerador ou cópia

**Decisão M1: cópia de arquivos de exemplo testados, sem gerador.**

- Alternativa: `scripts/novo_site.py <chave> --tipo <pasta> --nome <nome>`, que gera o coletor, o teste e a pasta de fixtures e edita `fontes.json` e os catálogos.
- Por que não: um site novo entra talvez uma vez por ano. O gerador é um script a mais para testar e manter, e ele só faz a parte fácil (trocar um nome em dois arquivos). A parte difícil, ler o site, não se gera. As edições mecânicas em JSON e nas listas fixas são poucas, e cada uma já tem um teste que reprova com mensagem clara. O molde testado não apodrece; um molde em texto (`.py.txt` em `docs/`) apodreceria.
- Quando rever: se dois PRs de site novo errarem a mesma troca mecânica, o gerador passa a valer a pena.

### 5.4 (d) Guia para quem contribui

**Onde mora (M8):** `docs/site-novo.md` e `docs/site-novo.en.md`, ao lado do guia de conserto. Ligado de: `.github/CONTRIBUTING.md` e `.en.md` (um item novo em "Como ajudar agora"), `wiki/Arquitetura.md` e `wiki/Architecture.md` (uma frase ao lado do link do conserto, `:374`), e o formulário `.github/ISSUE_TEMPLATE/fonte.yml` (uma linha no texto de abertura). Sem página nova na wiki: a wiki é para quem usa, e página nova pede o par em `PARES` de `test_wiki.py`, as duas listas do `_Sidebar.md` e link nos READMEs (`registros/padroes.md` («Doc»)).

**Seções (iguais nas duas línguas, com âncora fixa; o teste confere):**

1. `antes` — Antes de começar: o site é público ou pede login? Tem termos que proíbem robô (a Meta fica fora, ADR 0004)? Pede CAPTCHA para ver a lista? Se sim, ele não entra como fonte pública. Abra primeiro uma issue "Fonte de vagas". Status: PR de código só depois da fase 9; até lá, a issue com a captura e o que você achou.
2. `forma` — Escolher o molde e a pasta: tabela "seu site parece com":

   | O site | Pasta | Parta de |
   |---|---|---|
   | Busca por cargo, JSON | `portais/` ou `agregadores/` | `tests/apoio/molde_coletor.py` |
   | Busca por cargo, HTML | `portais/` | o molde, lendo com `selectolax` como `src/jobot/nucleo/coletores/portais/usp.py` |
   | Sitemap e uma página por vaga | `plataformas/` ou `portais/` | `src/jobot/nucleo/coletores/portais/super_estagios.py` |
   | RSS ou XML | `agregadores/` | `src/jobot/nucleo/coletores/agregadores/wwr.py` |
   | Sistema de recrutamento por empresa (ATS) | `plataformas/` | `src/jobot/nucleo/coletores/plataformas/lever.py` |
   | Pede login | `nucleo/leitores/` | `tests/apoio/molde_leitor.py` |

3. `copiar` — Copiar e registrar (coletor público): os arquivos, a troca do nome, a linha em `src/jobot/nucleo/dados/fontes.json` (leva `B`, `intervalo_min` e `credito_obrigatorio` conforme os termos), `fonte.<chave>` em `src/jobot/painel/i18n/pt/comum.json` e em `src/jobot/painel/i18n/en/comum.json`, e as listas fixas da seção 4.2, uma por linha. Fonte por empresa: `ATS_POR_EMPRESA`. Termos restritivos: `FONTES_FORA` do vigia e uma issue para decidir se a fonte vem desligada (o README promete todas ligadas).
4. `capturar` — Capturar o exemplo: `uv run python scripts/capturar.py <chave> --escopo <termo> --caso normal`; leia o arquivo gravado; rode uma vez e pare. O comando grava só a primeira página. O `formato_mudou` e o `vazio` se montam à mão a partir do `normal` capturado, com `montado_a_mao` no meta; a página 2 dos testes de paginação também se monta no teste, a partir do `normal`.
5. `ler` — Ensinar o coletor a ler (TDD): troque o exemplo do molde pelo capturado, veja `test_normal` falhar numa asserção, ajuste `_ler` e `_vaga`, veja passar. Ajuste também o trecho do teste que monta a página 2 (o campo de próxima página do site). Os testes que não dependem do formato (429, 304, bloqueio) passam sem mudança.
6. `login` — Site com login: a pessoa captura com a própria conta (`uv run python scripts/capturar_logado.py --caso lista --host <host>` antes de existir leitor; `--campo` para a posição do nome da conta); lê cada arquivo; copia o molde do leitor; TDD; registra em `LEITORES`; `fonte.<chave>` nos catálogos; listas fixas de leitor. O site nasce desligado. Nunca digitar senha por código, nunca contornar CAPTCHA.
7. `conferir` — Rodar a guarda e os testes: `uv run pytest tests/unidade/coletores/test_<chave>.py`, `uv run pytest tests/unidade/test_site_novo.py tests/unidade/test_fixtures.py tests/unidade/test_registro.py tests/unidade/test_i18n.py`, `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`.
8. `pr` — Abrir o PR: o mesmo fluxo da seção 7 do guia de conserto, com o README e o CHANGELOG nas duas línguas (a tabela de fontes).

O guia de conserto e o guia novo se citam um ao outro (uma linha em cada).

**Como escrever o guia para passar na guarda** (`problemas()` de `tests/unidade/test_guia_consertar_fonte.py:65-72` reprova o que não existe):

- caminho entre crases sempre completo, a partir da raiz: `src/jobot/nucleo/dados/fontes.json`, `src/jobot/painel/i18n/en/comum.json`; nunca `fontes.json` nem `en/comum.json` soltos;
- âncora só dentro de link, como `[copiar](site-novo.md#copiar)`; entre crases, `docs/site-novo.md#copiar` conta como caminho que não existe;
- marcador de caminho sem espaço: `test_leitor_<site>.py`, não `<chave sem _logado>`;
- a exigência de ao menos um comando `jobot` (`test_guia_consertar_fonte.py:89`) vale só para o guia de conserto; o guia novo cita `scripts/capturar.py` e `uv run pytest`, e não precisa de comando `jobot`.

### 5.5 (e) Passos de captura

**Decisão M7: sem modo novo nos scripts.**

- Coletor público: a ordem é copiar o molde, pôr o endereço em `_API`, pôr a linha em `fontes.json` e só então capturar. O `capturar.py` roda o `coletar` do molde e para na primeira resposta (`scripts/capturar.py:466`, `:491`), então o pedido certo sai mesmo com o `_ler` ainda do molde. Fonte por termo pede `--escopo <termo>` (`:537-541`).
- Site com login: captura sem leitor, com `--host` (docstring de `scripts/capturar_logado.py`); a pessoa entra com a própria senha; nome da conta sai pela posição (`--campo`); toda captura logada é lida por gente antes do commit (desenho da fase 2, A10).
- Alternativa: `capturar.py --url <URL> --fonte <chave>`, para capturar antes de existir coletor. Por que não: o caminho acima já funciona e o modo novo seria mais um ramo a testar na limpeza de dado pessoal, a parte mais sensível do script.

### 5.6 (f) O que o CI confere

**Decisão M5: guarda nova `tests/unidade/test_site_novo.py`.** Ela percorre os coletores de `descobrir()` e os leitores de `leitores()` e, por site, junta o que falta numa lista com a seção do guia. Uma função pura do próprio arquivo de teste, `faltas(raiz: Path, coletores: Iterable[str], leitores: Iterable[str]) -> list[str]`, faz a conta; os testes:

- `test_todo_site_registrado_esta_completo`: `faltas(RAIZ, descobrir(), [l.chave for l in leitores()]) == []`.
- `test_faltas_acha_coletor_sem_teste`, `test_faltas_acha_leitor_sem_teste`, `test_faltas_acha_leitor_com_exemplo_ruim` (pasta sem meta, ou meta com `sha256` errado), `test_faltas_acha_site_sem_nome_no_catalogo` (só no pt, só no en): cada um monta uma árvore em `tmp_path` com um único defeito e afirma o texto da falta, inclusive a âncora do guia (`docs/site-novo.md#copiar`, `#login`). São o controle positivo que impede a guarda de nascer verde à toa (`registros/padroes.md` («Teste que nasce verde»)).
- `test_moldes_ficam_fora_do_registro`: `molde_coletor` não está em `descobrir()` e `molde_logado` não está em `leitores()`.

O que `faltas` confere:

- coletor: `tests/unidade/coletores/test_<chave>.py` existe (o exemplo já é coberto por `test_fixtures.py:50-65`);
- leitor: `tests/unidade/test_leitor_<chave sem _logado>.py` existe e `capturar.problemas(tests/fixtures/<chave>) == []` (fecha a lacuna da 4.3);
- todo site: `fonte.<chave>` em `src/jobot/painel/i18n/pt/comum.json` e em `en/comum.json`.

**Decisão M6: as listas fixas da 4.2 ficam.** A guarda não as substitui; o guia as lista. Alternativa: derivar as listas de `descobrir()` e `leitores()`. Por que não: derivar tira a proteção contra perder uma fonte em silêncio, que é o motivo de elas existirem.

**Decisão M9: o guia novo entra na guarda do guia de conserto.** `test_guia_consertar_fonte.py` passa a percorrer os dois guias (mesmas seções nas duas línguas, comandos e caminhos que existem, links relativos), e a conferência do `CONTRIBUTING` passa a pedir os dois. Os caminhos que o guia cita (`tests/apoio/molde_coletor.py`, `tests/apoio/molde_leitor.py`, `tests/unidade/test_site_novo.py`) existem, então o teste prende guia e molde juntos: renomear o molde sem mexer no guia reprova.

## 6. Riscos

- **Molde que vira fonte por engano.** Se alguém mover o molde para `src/`, ele entra no `descobrir()`, quebra `test_estrutura.py:41-43` (chave fora de `fontes.json`) e a `test_moldes_ficam_fora_do_registro`. Risco coberto.
- **Molde que diverge do contrato.** Mudou o `Coletor` ou o `LeitorComLogin`: o `mypy --strict` reprova o molde pelas anotações `alvo: Coletor` e `alvo: LeitorComLogin`. Coberto no CI (o `mypy` roda lá, não nesta máquina).
- **Quem copia esquece uma lista fixa.** O teste da lista reprova com a chave no texto; o guia diz qual é. Aceito.
- **Fixture do molde com cara de dado real.** Host `.invalid` (reservado, nunca resolve), empresas e títulos inventados, sem nome de pessoa; `test_fixtures.py` varre também essa pasta.
- **Guia que promete o que o joBot não faz.** O guia é vigiado pelo mesmo teste do guia de conserto (comandos e caminhos que existem). A frase sobre PR de código segue o `CONTRIBUTING` (fase 9).
- **Site com termos restritivos.** O molde não decide; o guia manda abrir issue, e a decisão de ligar por padrão é do dono (o README promete todas ligadas, `test_documentos.py:338`).
- **Leitor copiado que tenta contornar bloqueio.** O molde só reconhece a página; a parada e o estado são do navegador e de `estado_do_escopo`. A revisão de PR olha isso; o guia repete o anti-objetivo.
- **Divergência fase 8 / fase 9** nos guias: corrigida na T299 (R1).

## 7. Testes esperados

| Teste | Prova |
|---|---|
| `tests/unidade/coletores/test_molde_coletor.py` (12 testes da 5.1) | o molde do coletor cumpre o contrato e os estados do "Molde do coletor" |
| `tests/unidade/test_leitor_molde.py` (18 testes da 5.2) | o molde do leitor cumpre o contrato e a regra de `Leitura` |
| `tests/unidade/test_site_novo.py` (6 testes da 5.6) | todo site registrado tem teste, exemplo válido (leitor) e nome nos dois catálogos; a guarda acha cada falta |
| `tests/unidade/test_guia_consertar_fonte.py` (estendido) | os dois guias têm as mesmas seções em pt e en, caminhos e comandos que existem, links vivos, e o `CONTRIBUTING` cita os dois |
| `tests/unidade/test_fixtures.py` (sem mudança) | varre só `descobrir()`; não vê as pastas dos moldes. Quem prende `capturar.problemas` nelas (sem dado pessoal, `sha256` certo) são os `test_fixtures_do_molde_sem_problemas` de cada molde |
| `tests/unidade/test_documentos.py` (sem mudança) | o CHANGELOG continua com as mesmas seções nas duas línguas |

## 8. O que fica para o construtor

- O corpo das funções dos moldes, desde que caiba nas assinaturas e nos testes acima. Molde curto: quem copia lê tudo, então menos é melhor.
- O texto exato das vagas inventadas das fixtures (sem nome de pessoa, sem e-mail, sem telefone).
- Como generalizar `test_guia_consertar_fonte.py` (dicionário de guias, `parametrize`), desde que os testes de hoje continuem com o mesmo nome ou com nome parametrizado que os contenha.
- A redação do guia, nas duas línguas, no tom do guia de conserto (frases curtas, um passo por vez).

## 9. Pontos que batem com o que já existe

- "Molde do coletor" do plano da fase 1 (`docs/superpowers/plans/2026-11-13-fase-1.md:109-122`): o molde novo é a versão executável dele; o plano antigo não muda.
- Parte B do desenho da fase 2 (seção 6): o passo 3 (TDD do leitor) é o conjunto de testes do molde do leitor.
- `registros/padroes.md` («Fixtures», «Coletor paginado», «Ciclo de vida», «ATS e sitemap», «Teste que nasce verde», «Doc»): o molde segue cada uma; a guarda fecha a lacuna de «Fixtures».
- ADR 0018: o CI roda em PR de fora; a guarda nova roda junto, sem segredo.

## 10. Perguntas pendentes

Nenhuma bloqueia. As escolhas da seção 11 estão para confirmar.

## 11. Todas as decisões (para confirmar)

| # | Decisão | Alternativa | Motivo |
|---|---|---|---|
| M1 | Molde = arquivos de exemplo testados em `tests/apoio/`, copiados à mão; sem gerador | `scripts/novo_site.py` que gera os arquivos e edita os JSON | site novo é raro; o gerador só faz a parte fácil e é mais código a manter; o molde testado não apodrece. Rever se dois PRs errarem a mesma troca |
| M2 | Molde do coletor: busca por termo, JSON, paginada por número | copiar o Greenhouse | os sites pedidos buscam por cargo e paginam; o Greenhouse é por empresa, sem página e com particularidades (teto de 32 MB, `resolver`) |
| M3 | Molde do leitor: HTML, termo, link de próxima, `detalhar` presente | só apontar o LinkedIn e o `LeitorFalso` | o LinkedIn tem particularidades demais; o `LeitorFalso` serve ao site falso dos testes do navegador |
| M4 | Exemplos dos moldes montados à mão, host `vagas.exemplo.invalid`, `montado_a_mao` no meta | capturar de um site real | o molde não é um site; capturar de um site real seria acrescentar uma fonte |
| M5 | Guarda `tests/unidade/test_site_novo.py` (teste por site, exemplo de leitor válido, nome nos dois catálogos), com controle positivo em `tmp_path` | confiar só nas listas fixas | as listas fixas não pegam leitor sem exemplo válido (lacuna de «Fixtures») nem apontam o guia |
| M6 | As listas fixas da 4.2 ficam; o guia as lista | derivá-las do registro | derivar tira a proteção contra perder fonte em silêncio |
| M7 | Sem modo novo em `capturar.py` nem em `capturar_logado.py` | `capturar.py --url` | o molde copiado já faz o pedido; o logado já captura sem leitor |
| M8 | Guia em `docs/site-novo.md` e `.en.md`, ligado do `CONTRIBUTING`, da página Arquitetura da wiki e do formulário `fonte.yml`; sem página nova na wiki | página nova na wiki | o público é quem mexe no código; página nova na wiki pede par, barra lateral e README |
| M9 | O guia novo entra na guarda de `test_guia_consertar_fonte.py` | teste próprio para o guia novo | a mesma regra para os dois guias, num lugar só |
| M10 | O guia segue o `CONTRIBUTING`: PR de código só depois da fase 9; até lá, issue com a captura; e o guia de conserto passa de "fase 8" para "fase 9" | deixar o guia de conserto como está | os dois documentos dizem a mesma coisa |
| M11 | Site público com termos restritivos: o guia manda abrir issue e pôr em `FONTES_FORA`; ligar ou não por padrão é do dono | o molde já trazer `ligada_padrao: false` | o README promete todas as fontes ligadas (`test_documentos.py:338`); trocar isso é decisão do dono |
| M12 | Uma linha no "Não lançado" do CHANGELOG, nas duas línguas ("Adicionado": guia e molde para acrescentar um site) | sem CHANGELOG | é documento para quem contribui, e o CHANGELOG já lista o guia de conserto |
