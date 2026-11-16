# Molde de site novo: plano de implementação

> Cada tarefa roda num worktree próprio, tirado da `dev`, e passa por revisão de outra pessoa ou sessão, diferente de quem implementou. TDD com vermelho válido: o teste-alvo falha numa asserção do comportamento pedido. Erro de import, de coleta ou zero testes não valem como vermelho. Por isso, quando o arquivo testado ainda não existe, o primeiro passo cria o esqueleto (as assinaturas, com corpo que devolve o valor errado), e só então o teste falha numa asserção.

**Objetivo:** dar a quem contribui um caminho simples para acrescentar um site de vagas, público ou com login: dois moldes que já rodam, um guia nas duas línguas e uma guarda no CI. Nenhum site novo entra.

**Desenho:** `docs/superpowers/specs/2026-11-16-molde-de-site-design.md` (seções 5.1 a 5.6, decisões M1 a M12, todas para confirmar).

**Base:** `dev` atual. Escolhas novas que aparecerem vão para o `duvidas.md` (R4); o resto segue as regras de desvio R1 a R3.

## Restrições globais

- Ler `registros/padroes.md` antes de cada tarefa, sobretudo «Fixtures», «Coletor paginado», «Teste que nasce verde», «Teste de navegador» e «Doc».
- Os moldes moram em `tests/apoio/`, nunca em `src/`: não entram em `descobrir()`, em `fontes.json`, em `LEITORES`, nos catálogos do painel nem no vigia.
- Sem dependência nova (ADR 0021). Sem mudar o contrato `Coletor` (`src/jobot/nucleo/coletores/base.py`) nem o `LeitorComLogin` (`src/jobot/nucleo/leitores/base.py`).
- Exemplos dos moldes montados à mão: host `vagas.exemplo.invalid`, empresas e títulos inventados, sem e-mail, telefone ou nome de pessoa, `montado_a_mao` e `sha256` certo no meta, cada arquivo abaixo de 50 KB (`tests/unidade/test_fixtures.py`).
- Sala limpa (ADR 0016): nada copiado nem parafraseado de outro projeto.
- Os moldes nunca ensinam a contornar login, CAPTCHA, desafio ou bloqueio: 401, 403, página de login ou desafio = "falhou".
- Testes sem rede e sem tempo real: `httpx.MockTransport` e `RelogioFalso`, como em `tests/unidade/coletores/test_greenhouse.py`.
- Documentos para quem contribui nas duas línguas (pt e en), com as mesmas seções. Este plano e o desenho ficam só em português.
- Nesta máquina: o arquivo de teste da tarefa (vermelho e verde) e `uv run ruff check && uv run ruff format --check`. Suíte inteira, `mypy` e `-m tela` no CI de `lote/molde-site`.

## Escolhas deste plano

| Escolha | Decisão | Onde no desenho |
|---|---|---|
| Gerador ou cópia | cópia de arquivos testados, sem `scripts/novo_site.py` | M1, 5.3 |
| Forma do molde público | busca por termo, JSON, paginada por número | M2, 5.1 |
| Forma do molde com login | HTML, escopo por termo, link de próxima, `detalhar` | M3, 5.2 |
| Exemplos dos moldes | montados à mão, host `.invalid` | M4 |
| Guarda do CI | `tests/unidade/test_site_novo.py` com controle positivo em `tmp_path` | M5, 5.6 |
| Listas fixas de fontes | ficam; o guia as lista | M6, 4.2 |
| Captura | sem modo novo nos scripts | M7, 5.5 |
| Onde mora o guia | `docs/site-novo.md` e `.en.md`, sem página nova na wiki | M8, 5.4 |

## Foco da revisão

- Vermelho válido em cada tarefa: falha de asserção, com a saída no retorno.
- O molde não vira fonte: nada em `src/`, `fontes.json`, `LEITORES` ou catálogos.
- O molde do coletor segue o "Molde do coletor" do plano da fase 1 (`docs/superpowers/plans/2026-11-13-fase-1.md`, seção com esse nome): 304 por identidade, 403 com um pedido só, teto por constante com `shortcut:`, item pulado vira `parcial`.
- O leitor de molde não decide estado nem trata desafio anti-robô: só reconhece a página do próprio site.
- Guarda que não nasce verde: cada falta tem um controle positivo que a acha.
- Guia sem promessa falsa: todo comando e caminho citado existe (o teste confere), a regra de PR é a do `CONTRIBUTING` (fase 9).
- Entrega reduzida ("v1", "por enquanto", "TODO", "stub"): gravidade alta.

### T296: molde do coletor público
`depende_de: —` · M1, M2, M4

O molde executável do "Molde do coletor": um coletor por termo, JSON, paginado, que passa nos testes de sempre e serve de ponto de partida.

**Arquivos:**
- criar `tests/apoio/molde_coletor.py`;
- criar `tests/unidade/coletores/test_molde_coletor.py`;
- criar `tests/fixtures/molde_coletor/normal.json` (uma página: o `capturar.py` grava só a primeira resposta, `scripts/capturar.py:466`, `:491`), `vazio.json`, `formato_mudou.json`, cada um com `.meta.json` (`montado_a_mao`, `sha256`). Não há `normal_p2.json`: os testes de paginação montam a página 2 no próprio teste, a partir do `normal.json` (trocando o campo de próxima página ou de cursor).

**Interfaces** (`tests/apoio/molde_coletor.py`; o corpo é do construtor, curto, com `# MUDE:` em cada linha que muda na cópia):
- constantes `CHAVE = "molde_coletor"`, `NOME`, `_HOST = "vagas.exemplo.invalid"`, `_API`, `_POR_PAGINA`, `_MAX_PAGINAS`;
- `_LIMITES = LimitesDaFonte()` com o comentário de que a cópia usa `limites(CHAVE)`;
- `class _FormatoMudou(Exception)`;
- `def _vaga(escopo: str, item: object) -> VagaColetada | None`;
- `def _ler(escopo: str, texto: str) -> tuple[list[VagaColetada], int, bool]` (vagas, pulados, tem próxima);
- `class Molde` com os atributos do `Coletor` e `escopos(self, ctx: ContextoColeta) -> Sequence[str]`, `async coletar(self, escopo: str, http: HttpEducado) -> ResultadoEscopo`, `async detalhar(self, item: Item, http: HttpEducado) -> VagaColetada | None` (devolve `None`; `Item = VagaColetada | UrlListada`, `src/jobot/nucleo/coletores/base.py:54`, como `greenhouse.py:166` e `remotive.py:132`: parâmetro mais estreito reprova no `mypy --strict` a linha `alvo: Coletor = molde_coletor.COLETOR`), `async resolver(self, identificador: str, http: HttpEducado) -> Mapping[str, str]` (levanta `ValueError`);
- `COLETOR = Molde()`;
- `juntar_paginas` importado pelo nome no módulo, para o `test_304` espiar.

**Testes** (`tests/unidade/coletores/test_molde_coletor.py`; no topo, só duas linhas a mudar na cópia: o módulo do alvo e `PASTA`):
- `test_cumpre_o_protocolo`: `alvo: Coletor = molde_coletor.COLETOR`; `alvo.chave == molde_coletor.CHAVE`.
- `test_escopos_um_por_termo`: `ContextoColeta(termos=(" dev ", "dev", "", "dados"), ...)` dá `["dev", "dados"]`.
- `test_normal`: duas páginas (o `normal.json` e a página 2 montada no teste), `estado == "ok"`, número de vagas certo, `fonte == CHAVE`, `escopo == "dev"`, toda `url` começa com `https://`.
- `test_vazio`: zero vagas, `ok`.
- `test_formato_mudou`: item torto entre bons dá `parcial` e `saude.formato_mudou`; só itens tortos, ou sem a lista, dá `falhou` e `saude.formato_mudou`; nenhuma exceção sai.
- `test_paginacao_para_no_teto`: `monkeypatch` em `_MAX_PAGINAS = 2`, próxima sempre presente: `parcial`, `saude.limite_atingido`, `pedidos == 2`.
- `test_429_e_erro_de_rede`: 429 dá `no_limite` e `saude.parou_429`; erro de rede na página 1 dá `falhou`, na 2 dá `parcial`.
- `test_304`: espiando `molde_coletor.juntar_paginas`, a página entregue `is base.SEM_MUDANCA`; `estado == "sem_mudanca"`.
- `test_bloqueio`: 403 dá `falhou`, `saude.bloqueio` e exatamente um pedido.
- `test_endereco_e_parametros`: método `GET`, host `vagas.exemplo.invalid`, caminho de `_API`, parâmetros `q` e `pagina` exatos.
- `test_resolver_recusa`: `pytest.raises(ValueError)`.
- `test_fixtures_do_molde_sem_problemas`: `capturar.problemas(PASTA) == []` (módulo `scripts/capturar.py` carregado como em `tests/unidade/test_fixtures.py:15-23`); `PASTA` é a segunda linha a mudar na cópia. Existe porque `test_fixtures.py:64` só percorre `descobrir()`.

- [ ] **Esqueleto:** criar `molde_coletor.py` com as assinaturas, cada método devolvendo o valor oposto ao esperado: `escopos` devolve `[]`, `coletar` devolve `ResultadoEscopo((), "falhou", "esqueleto", 0)` sem fazer pedido, `detalhar` devolve o próprio `item` quando for `VagaColetada` (em vez de `None`), `resolver` devolve `{}` (em vez de levantar `ValueError`). As fixtures vão montadas à mão com o meta.
- [ ] **Teste que falha antes:** escrever `test_molde_coletor.py` com os 12 testes.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/coletores/test_molde_coletor.py -q`. Vermelho esperado: todos falham numa asserção (`[] != ["dev", "dados"]`, estado `falhou` em vez de `ok`, zero pedidos em vez de um, `resolver` sem `ValueError`), menos os que nascem verdes contra o esqueleto: `test_cumpre_o_protocolo` e `test_fixtures_do_molde_sem_problemas`. Erro de import ou de coleta não vale.
- [ ] **Prova por mutação dos que nascem verdes** (cópia local, sem commitar; `registros/padroes.md:27`, «Teste que nasce verde»): trocar o `chave` da classe `Molde` por outro texto reprova `test_cumpre_o_protocolo`; mudar um byte de `normal.json` sem refazer o `sha256` do meta reprova `test_fixtures_do_molde_sem_problemas`. Anotar no retorno; o `mypy` (que checa as assinaturas) roda no CI.
- [ ] **Implementar** o molde, curto e comentado só onde o porquê não se vê; `shortcut:` no teto de páginas.
- [ ] **Ver passar:** `uv run pytest tests/unidade/coletores/test_molde_coletor.py tests/unidade/test_fixtures.py -q` e `uv run ruff check && uv run ruff format --check`.
- [ ] **Conferir que o molde não virou fonte:** `uv run pytest tests/unidade/test_estrutura.py tests/unidade/test_registro.py -q` sem mudança.

### T297: molde do leitor com login
`depende_de: —` · M1, M3, M4

O molde executável do `LeitorComLogin`: lista em HTML, escopo por termo, próxima por link, descrição pela página da vaga.

**Arquivos:**
- criar `tests/apoio/molde_leitor.py`;
- criar `tests/unidade/test_leitor_molde.py`;
- criar `tests/fixtures/molde_logado/lista.html`, `lista_p2.html`, `vazia.html`, `login.html`, `bloqueio.html`, `vaga.html`, `torta.html`, cada um com `.meta.json` (`montado_a_mao`, `sha256`). Nenhum nome de pessoa: o nome da conta no cabeçalho é o texto `Conta de exemplo`, na posição de `campos_conta`. O `achar_pessoais` (`scripts/capturar.py:247`) não pega nome livre, então a regra é do construtor e do revisor.

**Interfaces** (`tests/apoio/molde_leitor.py`):
- constantes `# MUDE:` `CHAVE = "molde_logado"`, `NOME`, `_HOST`, `URL_LOGIN`, `URL_ENTRADA`, `PREFIXOS_LOGIN`, `_CARTAO`, `_PROXIMA`, `_MARCA_LOGADA`, `_MARCA_BLOQUEIO`, `_DESCRICAO`;
- `class MoldeLogado` com os atributos do `LeitorComLogin` (`respostas = ()`, `rolar = False`, `lista_tem_descricao = False`, `lista_exaustiva = False`) e `escopos(self, ctx: ContextoColeta) -> Sequence[EscopoLogado]`, `e_login(self, captura: Captura) -> bool`, `pagina_logada(self, html: str, url: str) -> bool`, `pagina_bloqueada(self, html: str, url: str) -> bool`, `proxima(self, captura: Captura) -> str | None`, `ler(self, captura: Captura, escopo: EscopoLogado) -> Leitura`, `detalhar(self, captura: Captura, vaga: VagaColetada) -> VagaColetada | None`;
- `LEITOR = MoldeLogado()`.

**Testes** (`tests/unidade/test_leitor_molde.py`):
- `test_cumpre_o_protocolo`: `alvo: LeitorComLogin = molde_leitor.LEITOR`; `alvo.chave.endswith("_logado")`.
- `test_escopos_um_por_termo`: um `EscopoLogado` por termo, URL `https://vagas.exemplo.invalid/busca?q=...` com o termo codificado.
- `test_e_login_pela_url` e `test_pagina_de_login_nao_e_logada`.
- `test_pagina_logada_pela_marca` e `test_marca_dentro_da_descricao_nao_conta`.
- `test_pagina_bloqueada`: `bloqueio.html` sim, `lista.html` não.
- `test_proxima_da_lista`: URL absoluta da página 2; `test_proxima_fora_do_host_e_none`: link para outro host ou `http` dá `None`.
- `test_ler_lista`: número de vagas, `fonte == CHAVE`, `escopo == escopo.id`, `pulados == 0`, `formato_mudou is False`.
- `test_ler_lista_vazia_e_valida`: `Leitura((), 0, False)`.
- `test_sem_lista_e_formato_mudou`: `login.html` lida como lista dá `formato_mudou is True`.
- `test_item_torto_conta_pulado` e `test_so_itens_tortos_e_formato_mudou` (`torta.html`).
- `test_detalhar_traz_a_descricao` e `test_detalhar_sem_descricao_e_none`.
- `test_estado_com_o_molde`: as leituras do molde em `estado_do_escopo` dão `ok`, `parcial` com `saude.formato_mudou`, e `falhou` com `saude.formato_mudou`.
- `test_fixtures_do_molde_sem_problemas`: `capturar.problemas(PASTA) == []` para `tests/fixtures/molde_logado`; `PASTA` é uma das linhas a mudar na cópia.

- [ ] **Esqueleto:** criar `molde_leitor.py` com as assinaturas, cada método devolvendo o valor oposto ao esperado: `e_login`, `pagina_logada` e `pagina_bloqueada` devolvem `True`; `proxima` devolve a `URL_ENTRADA` (em vez de `None`); `detalhar` devolve a própria `vaga` (em vez de `None`); `escopos` devolve `()`; `ler` devolve `Leitura((), 0, True)`. Cada teste de sim/não traz os dois casos, então uma constante sempre reprova um deles. Criar as fixtures com o meta.
- [ ] **Teste que falha antes:** escrever `test_leitor_molde.py` com os 18 testes.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_leitor_molde.py -q`. Vermelho esperado: falham numa asserção `test_ler_lista`, `test_ler_lista_vazia_e_valida`, `test_e_login_pela_url`, `test_proxima_da_lista`, `test_detalhar_sem_descricao_e_none` e os demais menos os que nascem verdes contra o esqueleto: `test_cumpre_o_protocolo`, `test_sem_lista_e_formato_mudou` e `test_fixtures_do_molde_sem_problemas`.
- [ ] **Prova por mutação dos que nascem verdes** (cópia local, sem commitar; `registros/padroes.md:27`): com o leitor pronto, trocar `chave` por um texto sem `_logado` reprova `test_cumpre_o_protocolo`; fazer `ler` devolver `Leitura((), 0, False)` quando `_CARTAO` não existe reprova `test_sem_lista_e_formato_mudou`; mudar um byte de `lista.html` sem refazer o `sha256` reprova `test_fixtures_do_molde_sem_problemas`. Anotar no retorno.
- [ ] **Implementar** o leitor com `selectolax`, puro, sem `playwright`.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_leitor_molde.py tests/unidade/test_fixtures.py -q` e `uv run ruff check && uv run ruff format --check`.
- [ ] **Conferir que o molde não entrou no registro:** `uv run pytest tests/unidade/test_leitores_estado.py -q` sem mudança.

### T298: guarda de site completo
`depende_de: —` · M5, M6

Roda em paralelo com T296 e T297: os testes dela não importam os moldes, e `test_moldes_ficam_fora_do_registro` usa as chaves como texto. Esse teste só passa a valer de verdade quando o lote junta as três tarefas (antes disso os moldes não existem e ele passa à toa); a sessão o roda de novo na junção (ver "Depois das tarefas").

A guarda no CI: todo coletor e todo leitor registrados têm teste próprio, o leitor tem exemplo válido e todo site tem nome nos dois catálogos. Fecha a lacuna de «Fixtures» (exemplo de leitor fora do `descobrir()`).

**Arquivos:**
- criar `tests/unidade/test_site_novo.py`.

**Interfaces** (no próprio arquivo de teste):
- `RAIZ: Path` (raiz do repositório);
- `def faltas(raiz: Path, coletores: Iterable[str], leitores: Iterable[str]) -> list[str]`: uma linha por falta, cada uma com a chave e a âncora do guia (`docs/site-novo.md#copiar` para coletor e catálogo, `#login` para leitor). Confere `tests/unidade/coletores/test_<chave>.py`; `tests/unidade/test_leitor_<chave sem _logado>.py`; `capturar.problemas(raiz / "tests/fixtures" / <chave do leitor>) == []` (carregar `scripts/capturar.py` como em `tests/unidade/test_fixtures.py`); `fonte.<chave>` em `src/jobot/painel/i18n/pt/comum.json` e `en/comum.json`.

**Testes:**
- `test_todo_site_registrado_esta_completo`: `faltas(RAIZ, descobrir(), [l.chave for l in leitores()]) == []`.
- `test_faltas_acha_coletor_sem_teste`: árvore mínima em `tmp_path` só sem o arquivo de teste; a falta cita a chave e `#copiar`.
- `test_faltas_acha_leitor_sem_teste`: idem, `#login`.
- `test_faltas_acha_leitor_com_exemplo_ruim`: meta sem `sha256` certo; a falta cita a pasta.
- `test_faltas_acha_site_sem_nome_no_catalogo`: chave só no pt; a falta cita `en`.
- `test_moldes_ficam_fora_do_registro`: `"molde_coletor" not in descobrir()` e `"molde_logado"` fora de `leitores()`.

- [ ] **Esqueleto:** `faltas` devolvendo `[]`.
- [ ] **Teste que falha antes:** os 6 testes.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_site_novo.py -q`. Vermelho esperado: os 4 `test_faltas_acha_*` falham em `[] == ...` / falta não achada. `test_todo_site_registrado_esta_completo` e `test_moldes_ficam_fora_do_registro` passam já no vermelho: são a guarda e o controle do registro, provados pelos 4 controles positivos (`registros/padroes.md` «Teste que nasce verde»).
- [ ] **Implementar** `faltas`, lendo os catálogos com `json`.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_site_novo.py -q` e `uv run ruff check && uv run ruff format --check`.
- [ ] **Prova por mutação** (anotar no retorno, sem commitar): renomear `tests/unidade/coletores/test_remotive.py` e apagar `fonte.linkedin_logado` do `en/comum.json` numa cópia local; `test_todo_site_registrado_esta_completo` reprova com as duas faltas; desfazer.
- [ ] Se `test_todo_site_registrado_esta_completo` achar falta real hoje (o desenho espera que não: as 28 fontes têm teste, o LinkedIn tem `test_leitor_linkedin.py`), conserto R1 da fixture ou do catálogo, citado no retorno; se o `sha256` dos exemplos do `linkedin_logado` estiver errado, corrigi-lo com `capturar.problemas` como manda «Fixtures».

### T299: guia de site novo, nas duas línguas
`depende_de: T296, T297, T298` · M8, M9, M10, M11, M12

O guia que leva quem contribui do "achei um site" ao PR, e as ligações para ele.

**Arquivos:**
- criar `docs/site-novo.md` e `docs/site-novo.en.md`;
- modificar `tests/unidade/test_guia_consertar_fonte.py` (passa a vigiar os dois guias);
- modificar `.github/CONTRIBUTING.md` e `.github/CONTRIBUTING.en.md` (um item novo que liga o guia);
- modificar `wiki/Arquitetura.md` e `wiki/Architecture.md` (uma frase ao lado do link do guia de conserto);
- modificar `.github/ISSUE_TEMPLATE/fonte.yml` (uma linha no texto de abertura, nas duas línguas como o formulário já faz);
- modificar `docs/consertar-fonte.md` e `.en.md` (uma linha que liga o guia novo; R1: "fase 8" vira "fase 9", como o `CONTRIBUTING`);
- modificar `CHANGELOG.md` e o par em inglês (uma linha em "Não lançado" / "Adicionado").

**Interfaces** (seções do guia, com âncora fixa e o mesmo número nas duas línguas; o conteúdo de cada uma está no desenho, 5.4):
1. `antes` — público ou com login, termos, CAPTCHA, issue primeiro, regra de PR (fase 9).
2. `forma` — tabela "seu site parece com" (molde ou coletor real de referência, e a pasta de tipo).
3. `copiar` — copiar e registrar: arquivos, troca do nome, `fontes.json`, catálogos, `ATS_POR_EMPRESA` se por empresa, `FONTES_FORA` e issue se termos restritivos, e as listas fixas (desenho, 4.2), uma por linha.
4. `capturar` — `uv run python scripts/capturar.py <chave> --escopo <termo> --caso normal`, ler o arquivo, montar `vazio` e `formato_mudou` à mão.
5. `ler` — TDD: trocar o exemplo, ver falhar, ajustar, ver passar.
6. `login` — `uv run python scripts/capturar_logado.py --caso lista --host <host>` sem leitor, `--campo`, ler cada arquivo, copiar o molde do leitor, `LEITORES`, catálogo, listas fixas de leitor, nasce desligado; nunca senha por código nem CAPTCHA contornado.
7. `conferir` — comandos de teste, `ruff` e `mypy`, com `tests/unidade/test_site_novo.py`.
8. `pr` — o fluxo da seção 7 do guia de conserto, mais README e CHANGELOG nas duas línguas.

**Testes** (`tests/unidade/test_guia_consertar_fonte.py`, generalizado; os testes de hoje continuam, parametrizados pelo guia):
- `test_guia_tem_as_mesmas_secoes_em_pt_e_en[site-novo]`: mesmas âncoras e o mesmo número de seções em pt e en.
- `test_comandos_e_caminhos_citados_existem[site-novo]`: todo caminho citado existe (`tests/apoio/molde_coletor.py`, `tests/apoio/molde_leitor.py`, `tests/unidade/test_site_novo.py`, `scripts/capturar.py`, `scripts/capturar_logado.py`, `src/jobot/nucleo/dados/fontes.json`...), todo comando `jobot` citado também. A exigência de ao menos um comando `jobot` (`test_guia_consertar_fonte.py:89`) fica só para o guia de conserto (parâmetro da generalização); o guia novo não a tem. A exigência de citar `scripts/capturar.py` vale para os dois.
- `test_links_relativos_do_guia_existem[site-novo]`.
- `test_contributing_cita_o_guia[site-novo]`: o `CONTRIBUTING` pt cita `docs/site-novo.md` e o en cita `docs/site-novo.en.md`, além do guia de conserto.
- `test_guia_de_site_novo_liga_os_moldes` (novo): o guia pt e o en citam os dois moldes e a guarda.
- `test_guia_de_conserto_e_o_contributing_dizem_a_mesma_fase` (novo): a fase citada para PR de código em `docs/consertar-fonte.md` e `.en.md` é a mesma do `CONTRIBUTING` (hoje: 8 contra 9, então falha).

- [ ] **Teste que falha antes:** generalizar `test_guia_consertar_fonte.py` (dicionário de guias com `site-novo`) e escrever os dois testes novos.
- [ ] **Ver falhar:** `uv run pytest tests/unidade/test_guia_consertar_fonte.py -q`. Vermelho esperado: `test_contributing_cita_o_guia[site-novo]` (o `CONTRIBUTING` não cita o guia novo) e `test_guia_de_conserto_e_o_contributing_dizem_a_mesma_fase` (8 != 9) falham numa asserção. Os testes `[site-novo]` que precisam do arquivo falham na asserção de existência, escrita como `assert caminho.exists()` antes de ler, não como erro de leitura.
- [ ] **Escrever** os dois guias, no tom do guia de conserto: frases curtas, um passo por vez, sem citar a máquina do dono. Para passar em `problemas()` (`test_guia_consertar_fonte.py:65-72`): caminho entre crases sempre completo (`src/jobot/nucleo/dados/fontes.json`, `src/jobot/painel/i18n/en/comum.json`, nunca `fontes.json` nem `en/comum.json`); âncora só dentro de link (`[copiar](site-novo.md#copiar)`, nunca `docs/site-novo.md#copiar` entre crases); marcador sem espaço (`test_leitor_<site>.py`). Passo `capturar` e `ler`: o comando grava só a primeira página; a página 2 dos testes de paginação é montada no teste, a partir do `normal` capturado. Ligar do `CONTRIBUTING`, da wiki, do `fonte.yml` e do guia de conserto; trocar "fase 8" por "fase 9"; linha no CHANGELOG pt e en.
- [ ] **Ver passar:** `uv run pytest tests/unidade/test_guia_consertar_fonte.py tests/unidade/test_documentos.py tests/unidade/test_wiki.py -q` e `uv run ruff check && uv run ruff format --check`.
- [ ] **Ler o guia como quem chega:** seguir os passos de `copiar` contra os moldes reais (sem gravar nada) e conferir que cada lista fixa citada existe com o nome citado.

### T300: alinhar README e wiki sobre os sites com login
`depende_de: —` · só documentos

Hoje o texto diz que Gupy (com login), Vagas.com, Catho e Indeed são sites com login da fase 2. O que vale: o LinkedIn é o único site com login; a Gupy é só pública; Vagas.com, Catho e Indeed ficam para o futuro. A divergência está citada no desenho (4.5); o molde de site novo é o caminho para esses sites entrarem.

**Arquivos (texto nas duas línguas, mesmas seções):**
- modificar `README.md` e `README.en.md`: o nó do diagrama (`:116`, "LinkedIn, Indeed..."), a linha da tabela de fontes (`:190`, "Sites com login (fase 2, primeiro, nesta ordem)") e o aviso de risco (`:205`, cita Indeed);
- modificar `wiki/Como-funciona.md` e `wiki/How-it-works.md` (`:110`, a mesma linha da tabela);
- modificar `wiki/Roteiro.md` e `wiki/Roadmap.md` (`:51`, a ordem de mapeamento dos sites). Os planos de fase não se apagam: a frase continua dizendo a ordem prevista, mas deixa claro que hoje só o LinkedIn tem login e que a Gupy é pública.
- Antes de editar, procurar por `Catho`, `Indeed` e `Vagas.com` em `README*`, `wiki/` e `.github/` e tratar toda ocorrência que diga que são sites com login de agora. As linhas seguintes da tabela (InfoJobs, Glassdoor etc.) seguem o mesmo critério: texto de futuro, não de agora.

**Testes:** nenhum teste prende essas linhas (conferido: `tests/unidade/test_documentos.py` só trava as frases de `CITA` e a de fontes ligadas, e `tests/unidade/test_wiki.py` só confere os pares pt e en da wiki). Rodar `uv run pytest tests/unidade/test_documentos.py tests/unidade/test_wiki.py -q` antes e depois, e `ruff`. Não há executor de teste para o texto novo: a verificação é `grep -rn "Gupy (com login)\|Gupy (with login)" README.md README.en.md wiki/` sem resultado e a leitura do diff pelo revisor.

- [ ] **Rodar antes:** os dois testes acima, verdes.
- [ ] **Editar** os oito arquivos nas duas línguas, sem apagar plano de fase.
- [ ] **Rodar depois:** os mesmos testes e o `grep` acima.

## Depois das tarefas

- Juntar as cinco numa branch `lote/molde-site`, subir e esperar o CI (suíte inteira, `mypy`, `-m tela`). Verde: entra na `dev`, a `dev` sobe e a branch remota é apagada.
- Na junção, com os moldes presentes, provar `test_moldes_ficam_fora_do_registro` por mutação em cópia local: mover `tests/apoio/molde_coletor.py` para `src/jobot/nucleo/coletores/portais/` com a chave em `fontes.json`, e ele reprova (e `test_estrutura.py` também).
- Lições novas da revisão vão para `registros/padroes.md` (teto de 64 linhas).
- A D156, com as escolhas M1 a M12, já está no `duvidas.md` como "para confirmar".
