# Padrões e armadilhas do joBot

Lições que as revisões acharam. Leia antes de começar uma tarefa. Uma linha por lição.

- Toda tarefa que mexe em esquema lista os gatilhos de banco de forma explícita (os de `evento` e o `BEFORE DELETE` de `vaga`), não só as tabelas.
- `INSERT OR REPLACE`, `REPLACE` e `DROP TABLE` apagam a linha sem disparar o gatilho de `DELETE`, mas as cascatas rodam: grave com `INSERT ... ON CONFLICT DO UPDATE` e, na migração, desligue `foreign_keys` antes do `BEGIN`.
- `vaga_fts` e os gatilhos dela só existem quando `tem_fts5(con)` é verdadeiro; código e teste não podem supor FTS5.
- Toda grandeza de dinheiro diz a unidade no nome ou no tipo: `Salario` em centavos da moeda original; reais inteiros só nas colunas `_brl` do banco.
- Flags de comportamento (ex.: `para_no_429`) atravessam todas as camadas, de `fontes.json` até o `HttpDoEscopo`; teste a ponta e o meio.
- Sitemap: a janela de 30 dias filtra só URL nova; URL já conhecida conta como vista.
- Decisão do plano (DP) não contradiz decisão do redator (DR); havendo conflito, vale o desenho e o caso vai para `duvidas`.
- Arquivos compartilhados (`registro.py`, `fontes.json`, i18n `comum.json`) são fechados antes da onda; coletor não mexe neles.
- Toda condição do dono vira critério de aceite com teste.
- Vermelho de teste que depende do `tests/conftest.py`: prove com `uv run pytest --noconftest <arquivo>`, sem tirar arquivo do lugar.
- `ruff format` 0.17 formata blocos de código em `.md`: o `extend-exclude = ["*.md"]` do `pyproject.toml` fica.
- No `nucleo`, use import absoluto (`jobot.nucleo.x`): o teste de camadas só enxerga import absoluto.
- Nome de arquivo de teste único em todo `tests/` (sem `__init__.py` e sem `--import-mode=importlib`, nomes repetidos colidem no pytest e no mypy).
- A guarda de rede dos testes só aceita `127.0.0.1` e `::1` literais: servidor local em teste usa o IP, nunca `localhost`.
- mypy strict nos testes: monkeypatch em módulo falso segue o padrão `_falso(monkeypatch, nome)` de `tests/unidade/test_repositorio.py`.
- O CI roda `pytest -m tela` e sai com 5 se não houver teste de tela: a primeira tarefa de tela (T36) cria ao menos um.
- Código que faz chmod ou varre a pasta de dados ignora symlink (`is_symlink` antes de `stat`/`chmod`); o teste cobre alvo fora da pasta e link quebrado.
- Arquivo de log, inclusive o da rotação, nasce 0600 por `os.open` com modo explícito, sem depender do umask; o teste roda `doRollover`.
- Teste que mexe nos handlers do logger `jobot` usa fixture que remove e fecha o handler no fim, senão vaza entre testes.
- Migração que reconstrói `vaga` (DROP TABLE + RENAME) recria `vaga_sem_delete` e, se existir `vaga_fts`, `vaga_fts_insert` e `vaga_fts_update`; o teste confere `sqlite_master`.
- Para saber se há FTS5, leitura e gravação olham se `vaga_fts` existe em `sqlite_master`, não `tem_fts5(con)`: o banco guarda a decisão da migração 0001.
- sqlite3 em modo legado: `executescript` faz COMMIT antes de rodar. Transação de vários comandos vai inteira num `executescript` com BEGIN dentro, ou numa conexão sem transação aberta.
- `abrir()` deixa o isolation_level legado: quem grava chama `con.commit()`, e `migrar()` recusa conexão com transação aberta.
- Para testar uma mutação sem tocar no worktree: copie `src` para uma pasta temporária e rode `PYTHONPATH=<cópia>/src uv run pytest` (o PYTHONPATH vem antes da instalação editável).
- Dataclass frozen com campo Mapping (`Empresa`, `Busca`, `Motivo`) não é hasheável: não use em set nem como chave de dict.
- `_confere_http` só confere esquema e host e nunca reescreve a URL (`url_candidatura` é guardada sem mudança); o escape do href é do painel.
- `VagaColetada` e `VagaTratada` são kw_only: código e teste constroem por nome; helpers de teste (`_vaga`, `_tratada`) partem de um dict base com `base | campos`.
- Teste que declara `relogio: Relogio = RelogioFalso()` faz o mypy strict provar o Protocol; siga o padrão para outros Protocols.
- `tests/apoio` se importa como `apoio.x` (o `tests/conftest.py` põe `tests/` no sys.path): não ponha `__init__.py` em `tests/` nem mude o import-mode.
- Chaves de i18n com parâmetro são contrato: `saude.parcial_n` e `saude.sem_detalhe_n` usam `n`; `saude.excecao` usa `tipo`. Nome errado levanta KeyError em `t()`.
- `t()` não normaliza idioma: passe sempre o resultado de `idioma_inicial` (`pt` ou `en`), nunca o Accept-Language cru.
- JSON com chave duplicada no mesmo arquivo passa batido (`json.loads` sobrescreve): o teste de catálogo usa `object_pairs_hook` para pegar repetição.
- `uv_build` empacota os `.json` dentro de `src/jobot` sem mexer no `pyproject.toml`: dado em JSON ao lado do código não é R4.
